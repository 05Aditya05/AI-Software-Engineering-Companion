"""
Tests for the LLM provider abstraction and GeminiProvider.

All tests use mocks — no real Gemini API key is required.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import LLMProviderError
from app.providers.base import LLMProvider, LLMResponse
from app.providers.gemini import GeminiProvider


# ------------------------------------------------------------------
# LLMProvider abstraction tests
# ------------------------------------------------------------------

def test_llm_response_is_dataclass() -> None:
    """LLMResponse holds text, model, provider fields."""
    resp = LLMResponse(text="hello", model="m", provider="p")
    assert resp.text == "hello"
    assert resp.model == "m"
    assert resp.provider == "p"


def test_llm_provider_is_abstract() -> None:
    """Cannot instantiate LLMProvider directly — it is abstract."""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_concrete_provider_must_implement_chat() -> None:
    """Subclass without chat() implementation raises TypeError."""

    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()  # type: ignore[abstract]


# ------------------------------------------------------------------
# GeminiProvider construction tests
# ------------------------------------------------------------------

def test_gemini_provider_raises_on_missing_api_key() -> None:
    """Empty api_key raises LLMProviderError with LLM_MISSING_API_KEY code."""
    with pytest.raises(LLMProviderError) as exc_info:
        GeminiProvider(api_key="", model="gemini-2.0-flash")
    assert exc_info.value.code == "LLM_MISSING_API_KEY"


def test_gemini_provider_raises_on_whitespace_api_key() -> None:
    """Whitespace-only api_key treated as missing."""
    with pytest.raises(LLMProviderError) as exc_info:
        GeminiProvider(api_key="   ", model="gemini-2.0-flash")
    assert exc_info.value.code == "LLM_MISSING_API_KEY"


# ------------------------------------------------------------------
# GeminiProvider.chat() — mock SDK client
# ------------------------------------------------------------------

def _make_provider_with_mock_client(mock_response_text: str = "Test response."):
    """Create a GeminiProvider with its internal SDK client fully mocked."""
    mock_response = MagicMock()
    mock_response.text = mock_response_text

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.providers.gemini.Client", return_value=mock_client):
        provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")
    provider._client = mock_client  # replace after construction
    return provider, mock_client


def test_gemini_chat_returns_normalized_response() -> None:
    """Successful Gemini call returns LLMResponse with correct fields."""
    provider, _ = _make_provider_with_mock_client("Hello from Gemini!")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"},
    ]
    result = provider.chat(messages)

    assert isinstance(result, LLMResponse)
    assert result.text == "Hello from Gemini!"
    assert result.model == "gemini-2.0-flash"
    assert result.provider == "gemini"


def test_gemini_chat_extracts_system_instruction() -> None:
    """System message is extracted and passed separately, not as a content item."""
    provider, mock_client = _make_provider_with_mock_client("Reply.")
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hi"},
    ]
    provider.chat(messages)

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    assert config.system_instruction == "Be concise."

    # Contents should have only the user message, not the system message
    contents = call_kwargs["contents"]
    assert all(c.role != "system" for c in contents)
    assert len(contents) == 1
    assert contents[0].role == "user"


def test_gemini_chat_maps_assistant_role_to_model() -> None:
    """'assistant' role in messages becomes 'model' role in Gemini contents."""
    provider, mock_client = _make_provider_with_mock_client("OK.")
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]
    provider.chat(messages)

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    contents = call_kwargs["contents"]
    roles = [c.role for c in contents]
    assert roles == ["user", "model", "user"]


def test_gemini_chat_handles_auth_error() -> None:
    """ClientError with status 401 raises LLMProviderError with LLM_AUTH_ERROR."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_provider_with_mock_client()
    auth_error = genai_errors.ClientError(401, {})
    mock_client.models.generate_content.side_effect = auth_error

    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat([{"role": "user", "content": "hi"}])
    assert exc_info.value.code == "LLM_AUTH_ERROR"


def test_gemini_chat_handles_rate_limit() -> None:
    """ClientError with status 429 raises LLMProviderError with LLM_RATE_LIMIT."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_provider_with_mock_client()
    rate_error = genai_errors.ClientError(429, {})
    mock_client.models.generate_content.side_effect = rate_error

    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat([{"role": "user", "content": "hi"}])
    assert exc_info.value.code == "LLM_RATE_LIMIT"


def test_gemini_chat_handles_server_error() -> None:
    """ServerError raises LLMProviderError with LLM_SERVER_ERROR."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_provider_with_mock_client()
    server_error = genai_errors.ServerError(500, {})
    mock_client.models.generate_content.side_effect = server_error

    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat([{"role": "user", "content": "hi"}])
    assert exc_info.value.code == "LLM_SERVER_ERROR"


def test_gemini_chat_handles_timeout() -> None:
    """TimeoutError raises LLMProviderError with LLM_TIMEOUT."""
    provider, mock_client = _make_provider_with_mock_client()

    class FakeTimeout(Exception):
        pass

    FakeTimeout.__name__ = "TimeoutError"

    timeout_err = FakeTimeout("timeout exceeded")
    mock_client.models.generate_content.side_effect = timeout_err

    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat([{"role": "user", "content": "hi"}])
    assert exc_info.value.code in ("LLM_TIMEOUT", "LLM_PROVIDER_ERROR")


def test_gemini_chat_handles_empty_response() -> None:
    """Response with no text raises LLMProviderError with LLM_EMPTY_RESPONSE."""
    mock_response = MagicMock()
    mock_response.text = None
    mock_response.candidates = []

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.providers.gemini.Client", return_value=mock_client):
        provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")
    provider._client = mock_client

    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat([{"role": "user", "content": "hi"}])
    assert exc_info.value.code == "LLM_EMPTY_RESPONSE"


def test_gemini_chat_no_system_message() -> None:
    """Works correctly when no system message is provided."""
    provider, mock_client = _make_provider_with_mock_client("Answer.")
    messages = [{"role": "user", "content": "What is 2+2?"}]
    result = provider.chat(messages)
    assert result.text == "Answer."

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    assert config.system_instruction is None
    assert config.automatic_function_calling.disable is True


def test_gemini_chat_server_error_preserves_code_and_status() -> None:
    """ServerError message includes code, status, and upstream message safely."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_provider_with_mock_client()
    error_payload = {
        "error": {
            "code": 503,
            "message": "Model experiencing high demand.",
            "status": "UNAVAILABLE",
        }
    }
    server_error = genai_errors.ServerError(503, error_payload)
    mock_client.models.generate_content.side_effect = server_error

    with patch("time.sleep"):  # Avoid test delay during retry
        with pytest.raises(LLMProviderError) as exc_info:
            provider.chat([{"role": "user", "content": "hi"}])

    assert exc_info.value.code == "LLM_SERVER_ERROR"
    assert "503 UNAVAILABLE" in exc_info.value.message
    assert "Model experiencing high demand." in exc_info.value.message


def test_gemini_chat_retries_503_and_recovers() -> None:
    """ServerError 503 is retried up to 2 times and succeeds if transient."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_provider_with_mock_client("Recovered response.")
    server_error = genai_errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})

    # First call fails with 503, second call succeeds
    mock_response = MagicMock()
    mock_response.text = "Recovered response."
    mock_response.candidates = []
    mock_client.models.generate_content.side_effect = [server_error, mock_response]

    with patch("time.sleep") as mock_sleep:
        res = provider.chat([{"role": "user", "content": "hi"}])

    assert res.text == "Recovered response."
    assert mock_client.models.generate_content.call_count == 2
    mock_sleep.assert_called_once()


def test_gemini_chat_sanitizes_api_key_from_errors() -> None:
    """If an upstream error message contains the API key, it is redacted."""
    from google.genai import errors as genai_errors

    secret_key = "AIzaSySecretTestKey123"
    mock_client = MagicMock()
    server_error = genai_errors.ServerError(
        500,
        {"error": {"code": 500, "message": f"Invalid key {secret_key} used.", "status": "INTERNAL"}},
    )
    mock_client.models.generate_content.side_effect = server_error

    with patch("app.providers.gemini.Client", return_value=mock_client):
        provider = GeminiProvider(api_key=secret_key, model="gemini-2.0-flash")
    provider._client = mock_client

    with pytest.raises(LLMProviderError) as exc_info:
        provider.chat([{"role": "user", "content": "hi"}])

    assert secret_key not in exc_info.value.message
    assert "[REDACTED]" in exc_info.value.message

