"""
Gemini LLM provider implementation.

Wraps the google-genai SDK. All Gemini-specific objects are confined
to this module — nothing Gemini-specific is exported to callers.

Mapping between application message roles and Gemini content roles:
    "system"    → extracted as system_instruction in GenerateContentConfig
    "user"      → "user" content role
    "assistant" → "model" content role
"""

from google.genai import Client, errors as genai_errors
from google.genai import types as genai_types

from app.exceptions import LLMProviderError
from app.providers.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    """
    LLM provider backed by the Google Gemini API.

    Accepts the application-normalized messages list and returns an
    application-normalized LLMResponse. Raw Gemini SDK objects do not
    leave this class.
    """

    def __init__(self, api_key: str, model: str, timeout_ms: int = 30000) -> None:
        """
        Args:
            api_key:    Gemini API key. Must be non-empty.
            model:      Gemini model identifier, e.g. "gemini-2.0-flash".
            timeout_ms: HTTP request timeout in milliseconds.
        """
        if not api_key or not api_key.strip():
            raise LLMProviderError(
                "Gemini API key is not configured. "
                "Set the GEMINI_API_KEY environment variable.",
                code="LLM_MISSING_API_KEY",
            )
        self._model = model
        self._timeout_ms = timeout_ms
        self._client = Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=timeout_ms),
        )

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        """
        Send messages to Gemini and return a normalized response.

        The "system" role message is extracted and passed as
        system_instruction; remaining messages are converted to Gemini
        Content objects using "user" / "model" roles.

        Args:
            messages: Ordered list of {"role": str, "content": str} dicts.

        Returns:
            LLMResponse with response text, model name, and provider name.

        Raises:
            LLMProviderError: On any Gemini API failure.
        """
        system_instruction: str | None = None
        contents: list[genai_types.Content] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part(text=content)],
                    )
                )
            elif role == "assistant":
                contents.append(
                    genai_types.Content(
                        role="model",
                        parts=[genai_types.Part(text=content)],
                    )
                )

        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except genai_errors.ClientError as exc:
            # 4xx errors: authentication failure, invalid request, etc.
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status == 401 or status == 403:
                raise LLMProviderError(
                    "Gemini authentication failed. Verify your GEMINI_API_KEY.",
                    code="LLM_AUTH_ERROR",
                ) from exc
            if status == 429:
                raise LLMProviderError(
                    "Gemini rate limit exceeded. Please retry later.",
                    code="LLM_RATE_LIMIT",
                ) from exc
            raise LLMProviderError(
                f"Gemini request error: {exc}",
                code="LLM_CLIENT_ERROR",
            ) from exc
        except genai_errors.ServerError as exc:
            raise LLMProviderError(
                "Gemini server error. Please retry later.",
                code="LLM_SERVER_ERROR",
            ) from exc
        except Exception as exc:
            # Covers httpx timeout, connectivity issues, etc.
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                raise LLMProviderError(
                    "Gemini request timed out.",
                    code="LLM_TIMEOUT",
                ) from exc
            raise LLMProviderError(
                "Unexpected error communicating with Gemini.",
                code="LLM_PROVIDER_ERROR",
            ) from exc

        text = self._extract_text(response)
        return LLMResponse(text=text, model=self._model, provider="gemini")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(response: genai_types.GenerateContentResponse) -> str:
        """Extract plain text from a Gemini response object.

        Raises:
            LLMProviderError: If no usable text is found in the response.
        """
        try:
            text = response.text
            if text:
                return text
        except (AttributeError, ValueError):
            pass

        # Fallback: iterate candidates/parts
        try:
            for candidate in response.candidates or []:
                for part in (candidate.content.parts or []):
                    if part.text:
                        return part.text
        except (AttributeError, TypeError):
            pass

        raise LLMProviderError(
            "Gemini returned an empty or unparseable response.",
            code="LLM_EMPTY_RESPONSE",
        )
