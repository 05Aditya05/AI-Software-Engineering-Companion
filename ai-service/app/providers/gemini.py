"""
Gemini LLM provider implementation.

Wraps the google-genai SDK. All Gemini-specific objects are confined
to this module — nothing Gemini-specific is exported to callers.

Mapping between application message roles and Gemini content roles:
    "system"    → extracted as system_instruction in GenerateContentConfig
    "user"      → "user" content role
    "assistant" → "model" content role
"""

import time

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
        self._api_key = api_key
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
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
        )

        max_transient_retries = 2
        response = None

        for attempt in range(max_transient_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                break
            except genai_errors.ServerError as exc:
                status = getattr(exc, "code", None)
                if status == 503 and attempt < max_transient_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                self._handle_server_error(exc)
            except genai_errors.ClientError as exc:
                self._handle_client_error(exc)
            except Exception as exc:
                self._handle_generic_error(exc)

        if response is None:
            raise LLMProviderError(
                "Gemini did not return a response.",
                code="LLM_EMPTY_RESPONSE",
            )

        text = self._extract_text(response)
        return LLMResponse(text=text, model=self._model, provider="gemini")

    def _sanitize(self, message: str) -> str:
        """Strip API key or sensitive credentials from error messages."""
        if hasattr(self, "_api_key") and self._api_key and self._api_key in message:
            return message.replace(self._api_key, "[REDACTED]")
        return message

    def _handle_server_error(self, exc: genai_errors.ServerError) -> None:
        code = getattr(exc, "code", 500)
        status_name = getattr(exc, "status", None) or "SERVER_ERROR"
        raw_msg = self._sanitize(getattr(exc, "message", None) or "")
        detail = f": {raw_msg}" if raw_msg else ". Please retry later."
        raise LLMProviderError(
            f"Gemini server error ({code} {status_name}){detail}",
            code="LLM_SERVER_ERROR",
        ) from exc

    def _handle_client_error(self, exc: genai_errors.ClientError) -> None:
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if status in (401, 403):
            raise LLMProviderError(
                "Gemini authentication failed. Verify your GEMINI_API_KEY.",
                code="LLM_AUTH_ERROR",
            ) from exc
        if status == 429:
            raw_msg = self._sanitize(getattr(exc, "message", None) or "")
            detail = f": {raw_msg}" if raw_msg else ". Please retry later."
            raise LLMProviderError(
                f"Gemini rate limit exceeded (429 RESOURCE_EXHAUSTED){detail}",
                code="LLM_RATE_LIMIT",
            ) from exc
        raw_msg = self._sanitize(getattr(exc, "message", None) or str(exc))
        raise LLMProviderError(
            f"Gemini request error ({status or 400}): {raw_msg}",
            code="LLM_CLIENT_ERROR",
        ) from exc

    def _handle_generic_error(self, exc: Exception) -> None:
        exc_name = type(exc).__name__
        if "Timeout" in exc_name or "timeout" in str(exc).lower():
            raise LLMProviderError(
                "Gemini request timed out.",
                code="LLM_TIMEOUT",
            ) from exc
        raw_msg = self._sanitize(str(exc))
        raise LLMProviderError(
            f"Unexpected error communicating with Gemini: {raw_msg}",
            code="LLM_PROVIDER_ERROR",
        ) from exc

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
