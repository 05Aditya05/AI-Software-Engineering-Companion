"""
Gemini embedding provider implementation.

Wraps the google-genai SDK embedding endpoint.  All Gemini-specific
objects are confined to this module — nothing Gemini-specific is
exported to callers.

Model notes (as of 2026):
    text-embedding-004   → shut down Jan 2026
    gemini-embedding-001 → current; default 3072-d, supports
                            Matryoshka truncation (768 / 1536 / 3072)
"""

from google.genai import Client, errors as genai_errors
from google.genai import types as genai_types

from app.exceptions import LLMProviderError
from app.providers.base import EmbeddingProvider, EmbeddingResponse

# Gemini API accepts up to 100 content entries per embed_content call.
MAX_BATCH_SIZE = 100

# Default output dimensionality — matches project_knowledge Vector(768).
DEFAULT_OUTPUT_DIMENSIONALITY = 768


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider backed by the Google Gemini API.

    Accepts plain-text strings and returns fixed-dimension float vectors.
    Raw Gemini SDK objects do not leave this class.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        timeout_ms: int = 30000,
        output_dimensionality: int = DEFAULT_OUTPUT_DIMENSIONALITY,
    ) -> None:
        """
        Args:
            api_key:               Gemini API key.  Must be non-empty.
            model:                 Embedding model identifier.
            timeout_ms:            HTTP request timeout in milliseconds.
            output_dimensionality: Number of dimensions in output vectors.
        """
        if not api_key or not api_key.strip():
            raise LLMProviderError(
                "Gemini API key is not configured. "
                "Set the GEMINI_API_KEY environment variable.",
                code="LLM_MISSING_API_KEY",
            )
        self._api_key = api_key
        self._model = model
        self._output_dimensionality = output_dimensionality
        self._client = Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=timeout_ms),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        """
        Compute embeddings for one or more texts.

        Inputs are validated, then sent to the Gemini embedding endpoint
        in a single call (up to MAX_BATCH_SIZE).  If *texts* exceeds the
        batch limit the call is rejected up-front; callers should split
        beforehand.

        Args:
            texts: Non-empty list of non-empty strings.

        Returns:
            EmbeddingResponse with one vector per input text.

        Raises:
            LLMProviderError: On validation failure or any API error.
        """
        self._validate_input(texts)

        config = genai_types.EmbedContentConfig(
            output_dimensionality=self._output_dimensionality,
        )

        try:
            response = self._client.models.embed_content(
                model=self._model,
                contents=texts,
                config=config,
            )
        except genai_errors.ClientError as exc:
            self._handle_client_error(exc)
        except genai_errors.ServerError as exc:
            self._handle_server_error(exc)
        except Exception as exc:
            self._handle_generic_error(exc)

        return self._normalise_response(response)

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_input(texts: list[str]) -> None:
        """Raise LLMProviderError for clearly invalid inputs."""
        if not texts:
            raise LLMProviderError(
                "Cannot embed an empty list of texts.",
                code="EMBEDDING_VALIDATION_ERROR",
            )
        if len(texts) > MAX_BATCH_SIZE:
            raise LLMProviderError(
                f"Batch size {len(texts)} exceeds the maximum of {MAX_BATCH_SIZE}. "
                "Split inputs into smaller batches.",
                code="EMBEDDING_VALIDATION_ERROR",
            )
        for idx, t in enumerate(texts):
            if not isinstance(t, str) or not t.strip():
                raise LLMProviderError(
                    f"Text at index {idx} is empty or not a string.",
                    code="EMBEDDING_VALIDATION_ERROR",
                )

    # ------------------------------------------------------------------
    # Response normalisation
    # ------------------------------------------------------------------

    def _normalise_response(
        self, response: genai_types.EmbedContentResponse
    ) -> EmbeddingResponse:
        """Convert the SDK response into our normalised dataclass."""
        if not response or not response.embeddings:
            raise LLMProviderError(
                "Gemini returned an empty embedding response.",
                code="EMBEDDING_EMPTY_RESPONSE",
            )

        vectors: list[list[float]] = []
        for emb in response.embeddings:
            if emb.values is None:
                raise LLMProviderError(
                    "Gemini returned an embedding entry with no values.",
                    code="EMBEDDING_EMPTY_RESPONSE",
                )
            vectors.append(list(emb.values))

        dimension = len(vectors[0]) if vectors else 0
        return EmbeddingResponse(
            embeddings=vectors,
            model=self._model,
            provider="gemini",
            dimension=dimension,
        )

    # ------------------------------------------------------------------
    # Error handling (mirrors GeminiProvider conventions)
    # ------------------------------------------------------------------

    def _sanitize(self, message: str) -> str:
        """Strip API key from error messages."""
        if self._api_key and self._api_key in message:
            return message.replace(self._api_key, "[REDACTED]")
        return message

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
                f"Gemini embedding rate limit exceeded (429 RESOURCE_EXHAUSTED){detail}",
                code="LLM_RATE_LIMIT",
            ) from exc
        raw_msg = self._sanitize(getattr(exc, "message", None) or str(exc))
        raise LLMProviderError(
            f"Gemini embedding request error ({status or 400}): {raw_msg}",
            code="LLM_CLIENT_ERROR",
        ) from exc

    def _handle_server_error(self, exc: genai_errors.ServerError) -> None:
        code = getattr(exc, "code", 500)
        status_name = getattr(exc, "status", None) or "SERVER_ERROR"
        raw_msg = self._sanitize(getattr(exc, "message", None) or "")
        detail = f": {raw_msg}" if raw_msg else ". Please retry later."
        raise LLMProviderError(
            f"Gemini embedding server error ({code} {status_name}){detail}",
            code="LLM_SERVER_ERROR",
        ) from exc

    def _handle_generic_error(self, exc: Exception) -> None:
        exc_name = type(exc).__name__
        if "Timeout" in exc_name or "timeout" in str(exc).lower():
            raise LLMProviderError(
                "Gemini embedding request timed out.",
                code="LLM_TIMEOUT",
            ) from exc
        raw_msg = self._sanitize(str(exc))
        raise LLMProviderError(
            f"Unexpected error from Gemini embedding API: {raw_msg}",
            code="LLM_PROVIDER_ERROR",
        ) from exc
