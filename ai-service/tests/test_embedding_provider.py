"""
Tests for the embedding provider abstraction and GeminiEmbeddingProvider.

All tests use mocks — no real Gemini API key is required.
An optional live smoke test is included at the end, gated by API key availability.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import LLMProviderError
from app.providers.base import EmbeddingProvider, EmbeddingResponse
from app.providers.embedding import (
    DEFAULT_OUTPUT_DIMENSIONALITY,
    MAX_BATCH_SIZE,
    GeminiEmbeddingProvider,
)


# ------------------------------------------------------------------
# EmbeddingProvider abstraction tests
# ------------------------------------------------------------------

def test_embedding_response_dataclass() -> None:
    """EmbeddingResponse holds embeddings, model, provider, dimension."""
    resp = EmbeddingResponse(
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        model="m",
        provider="p",
        dimension=2,
    )
    assert len(resp.embeddings) == 2
    assert resp.model == "m"
    assert resp.provider == "p"
    assert resp.dimension == 2


def test_embedding_response_defaults() -> None:
    """EmbeddingResponse has sensible defaults."""
    resp = EmbeddingResponse()
    assert resp.embeddings == []
    assert resp.model == ""
    assert resp.dimension == 0


def test_embedding_provider_is_abstract() -> None:
    """Cannot instantiate EmbeddingProvider directly."""
    with pytest.raises(TypeError):
        EmbeddingProvider()  # type: ignore[abstract]


def test_concrete_embedding_provider_must_implement_embed() -> None:
    """Subclass without embed() raises TypeError."""

    class Incomplete(EmbeddingProvider):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


# ------------------------------------------------------------------
# GeminiEmbeddingProvider construction tests
# ------------------------------------------------------------------

def test_gemini_embedding_raises_on_missing_api_key() -> None:
    """Empty api_key raises LLMProviderError."""
    with pytest.raises(LLMProviderError) as exc_info:
        GeminiEmbeddingProvider(api_key="")
    assert exc_info.value.code == "LLM_MISSING_API_KEY"


def test_gemini_embedding_raises_on_whitespace_api_key() -> None:
    """Whitespace-only api_key treated as missing."""
    with pytest.raises(LLMProviderError) as exc_info:
        GeminiEmbeddingProvider(api_key="   ")
    assert exc_info.value.code == "LLM_MISSING_API_KEY"


# ------------------------------------------------------------------
# Helper: create provider with mock client
# ------------------------------------------------------------------

def _make_embedding_provider(
    mock_vectors: list[list[float]] | None = None,
    model: str = "gemini-embedding-001",
    output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
):
    """Create a GeminiEmbeddingProvider with its SDK client fully mocked."""
    if mock_vectors is None:
        mock_vectors = [[0.1] * 768]

    # Build mock ContentEmbedding objects
    mock_embeddings = []
    for vec in mock_vectors:
        emb = MagicMock()
        emb.values = vec
        mock_embeddings.append(emb)

    mock_response = MagicMock()
    mock_response.embeddings = mock_embeddings

    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = mock_response

    with patch("app.providers.embedding.Client", return_value=mock_client):
        provider = GeminiEmbeddingProvider(
            api_key="fake-key",
            model=model,
            output_dimensionality=output_dimensionality,
        )
    provider._client = mock_client
    return provider, mock_client


# ------------------------------------------------------------------
# Input validation tests
# ------------------------------------------------------------------

def test_embed_rejects_empty_list() -> None:
    """Empty text list is rejected."""
    provider, _ = _make_embedding_provider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed([])
    assert exc_info.value.code == "EMBEDDING_VALIDATION_ERROR"
    assert "empty list" in exc_info.value.message.lower()


def test_embed_rejects_empty_string() -> None:
    """List containing an empty string is rejected."""
    provider, _ = _make_embedding_provider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed([""])
    assert exc_info.value.code == "EMBEDDING_VALIDATION_ERROR"
    assert "index 0" in exc_info.value.message


def test_embed_rejects_whitespace_only_string() -> None:
    """Whitespace-only text is rejected."""
    provider, _ = _make_embedding_provider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["   "])
    assert exc_info.value.code == "EMBEDDING_VALIDATION_ERROR"


def test_embed_rejects_oversized_batch() -> None:
    """Batch larger than MAX_BATCH_SIZE is rejected."""
    provider, _ = _make_embedding_provider()
    texts = [f"text {i}" for i in range(MAX_BATCH_SIZE + 1)]
    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(texts)
    assert exc_info.value.code == "EMBEDDING_VALIDATION_ERROR"
    assert str(MAX_BATCH_SIZE) in exc_info.value.message


def test_embed_rejects_non_string_in_list() -> None:
    """Non-string elements are rejected."""
    provider, _ = _make_embedding_provider()
    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed([123])  # type: ignore[list-item]
    assert exc_info.value.code == "EMBEDDING_VALIDATION_ERROR"


# ------------------------------------------------------------------
# Successful embedding tests
# ------------------------------------------------------------------

def test_embed_single_text_returns_correct_response() -> None:
    """Single text returns EmbeddingResponse with one vector."""
    vec = [0.1, 0.2, 0.3]
    provider, mock_client = _make_embedding_provider(mock_vectors=[vec])

    result = provider.embed(["Hello world"])

    assert isinstance(result, EmbeddingResponse)
    assert len(result.embeddings) == 1
    assert result.embeddings[0] == vec
    assert result.model == "gemini-embedding-001"
    assert result.provider == "gemini"
    assert result.dimension == 3

    # Verify SDK was called correctly
    call_kwargs = mock_client.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-embedding-001"
    assert call_kwargs["contents"] == ["Hello world"]
    assert call_kwargs["config"].output_dimensionality == DEFAULT_OUTPUT_DIMENSIONALITY


def test_embed_multiple_texts_returns_multiple_vectors() -> None:
    """Multiple texts produce matching number of vectors."""
    vecs = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    provider, _ = _make_embedding_provider(mock_vectors=vecs)

    result = provider.embed(["a", "b", "c"])

    assert len(result.embeddings) == 3
    assert result.embeddings[1] == [0.3, 0.4]
    assert result.dimension == 2


def test_embed_passes_output_dimensionality_to_config() -> None:
    """Custom output_dimensionality is forwarded to EmbedContentConfig."""
    provider, mock_client = _make_embedding_provider(
        mock_vectors=[[1.0] * 1536], output_dimensionality=1536
    )
    provider.embed(["test"])

    config = mock_client.models.embed_content.call_args.kwargs["config"]
    assert config.output_dimensionality == 1536


def test_embed_uses_custom_model_name() -> None:
    """Custom model name is forwarded to the SDK."""
    provider, mock_client = _make_embedding_provider(model="custom-model")
    provider.embed(["test"])

    call_kwargs = mock_client.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == "custom-model"


# ------------------------------------------------------------------
# Malformed response tests
# ------------------------------------------------------------------

def test_embed_handles_empty_response() -> None:
    """Empty response raises LLMProviderError."""
    provider, mock_client = _make_embedding_provider()

    mock_response = MagicMock()
    mock_response.embeddings = None
    mock_client.models.embed_content.return_value = mock_response

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "EMBEDDING_EMPTY_RESPONSE"


def test_embed_handles_empty_embeddings_list() -> None:
    """Response with empty embeddings list raises LLMProviderError."""
    provider, mock_client = _make_embedding_provider()

    mock_response = MagicMock()
    mock_response.embeddings = []
    mock_client.models.embed_content.return_value = mock_response

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "EMBEDDING_EMPTY_RESPONSE"


def test_embed_handles_null_values_in_embedding() -> None:
    """Embedding entry with values=None raises LLMProviderError."""
    provider, mock_client = _make_embedding_provider()

    emb = MagicMock()
    emb.values = None
    mock_response = MagicMock()
    mock_response.embeddings = [emb]
    mock_client.models.embed_content.return_value = mock_response

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "EMBEDDING_EMPTY_RESPONSE"


# ------------------------------------------------------------------
# API error handling tests (mirrors GeminiProvider patterns)
# ------------------------------------------------------------------

def test_embed_handles_auth_error() -> None:
    """ClientError 401 raises LLM_AUTH_ERROR."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_embedding_provider()
    mock_client.models.embed_content.side_effect = genai_errors.ClientError(401, {})

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "LLM_AUTH_ERROR"


def test_embed_handles_rate_limit() -> None:
    """ClientError 429 raises LLM_RATE_LIMIT."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_embedding_provider()
    mock_client.models.embed_content.side_effect = genai_errors.ClientError(429, {})

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "LLM_RATE_LIMIT"


def test_embed_handles_server_error() -> None:
    """ServerError raises LLM_SERVER_ERROR."""
    from google.genai import errors as genai_errors

    provider, mock_client = _make_embedding_provider()
    mock_client.models.embed_content.side_effect = genai_errors.ServerError(500, {})

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "LLM_SERVER_ERROR"


def test_embed_handles_timeout() -> None:
    """Timeout exception raises LLM_TIMEOUT."""
    provider, mock_client = _make_embedding_provider()

    class FakeTimeout(Exception):
        pass

    FakeTimeout.__name__ = "TimeoutError"
    mock_client.models.embed_content.side_effect = FakeTimeout("timeout exceeded")

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code in ("LLM_TIMEOUT", "LLM_PROVIDER_ERROR")


def test_embed_handles_generic_error() -> None:
    """Unexpected exception raises LLM_PROVIDER_ERROR."""
    provider, mock_client = _make_embedding_provider()
    mock_client.models.embed_content.side_effect = RuntimeError("something broke")

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert exc_info.value.code == "LLM_PROVIDER_ERROR"


def test_embed_sanitizes_api_key_from_errors() -> None:
    """API key is redacted from error messages."""
    from google.genai import errors as genai_errors

    secret_key = "AIzaSySecretTestKey999"
    mock_client = MagicMock()
    server_error = genai_errors.ServerError(
        500,
        {"error": {"code": 500, "message": f"Invalid key {secret_key}.", "status": "INTERNAL"}},
    )
    mock_client.models.embed_content.side_effect = server_error

    with patch("app.providers.embedding.Client", return_value=mock_client):
        provider = GeminiEmbeddingProvider(api_key=secret_key)
    provider._client = mock_client

    with pytest.raises(LLMProviderError) as exc_info:
        provider.embed(["hello"])
    assert secret_key not in exc_info.value.message
    assert "[REDACTED]" in exc_info.value.message


# ------------------------------------------------------------------
# Max batch boundary test
# ------------------------------------------------------------------

def test_embed_accepts_max_batch_size() -> None:
    """Exactly MAX_BATCH_SIZE texts is accepted."""
    vecs = [[0.5] * 4 for _ in range(MAX_BATCH_SIZE)]
    provider, _ = _make_embedding_provider(mock_vectors=vecs)
    texts = [f"text {i}" for i in range(MAX_BATCH_SIZE)]
    result = provider.embed(texts)
    assert len(result.embeddings) == MAX_BATCH_SIZE


# ------------------------------------------------------------------
# Optional live smoke test — only runs if GEMINI_API_KEY is set
# ------------------------------------------------------------------

def test_live_gemini_embedding_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional: verify a real embed call if API key is available.

    This test is skipped automatically when GEMINI_API_KEY is not configured.
    It never prints or logs the key.
    """
    import os

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        pytest.skip("GEMINI_API_KEY not configured — skipping live smoke test")

    provider = GeminiEmbeddingProvider(api_key=api_key)
    result = provider.embed(["Hello world, this is a test embedding."])

    assert len(result.embeddings) == 1
    assert len(result.embeddings[0]) == DEFAULT_OUTPUT_DIMENSIONALITY
    assert result.model == "gemini-embedding-001"
    assert result.provider == "gemini"
    assert result.dimension == DEFAULT_OUTPUT_DIMENSIONALITY
