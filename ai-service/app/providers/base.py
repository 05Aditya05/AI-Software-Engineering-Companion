"""
LLM and embedding provider abstractions.

Defines normalized response types and abstract base classes
that all provider implementations must satisfy.

Gemini-specific (or any other provider-specific) objects must NOT
appear outside of their respective provider modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """
    Normalized response returned by any LLM provider.

    Provider-specific response objects are converted into this
    structure before leaving the provider module.
    """

    text: str
    model: str
    provider: str


@dataclass
class EmbeddingResponse:
    """
    Normalized response returned by any embedding provider.

    Each entry in *embeddings* corresponds to the input text at the
    same index.  Provider-specific objects are converted into this
    structure before leaving the provider module.
    """

    embeddings: list[list[float]] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    dimension: int = 0


class LLMProvider(ABC):
    """
    Abstract base for LLM provider implementations.

    ChatService depends on this interface, not on any concrete SDK.
    """

    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        """
        Send a list of role/content message dicts and return a normalized response.

        Args:
            messages: Ordered list of {"role": str, "content": str} dicts.
                      Roles follow the application convention: "system", "user", "assistant".

        Returns:
            LLMResponse with normalized text, model name, and provider identifier.

        Raises:
            LLMProviderError: On any provider-level failure (auth, timeout, API error).
        """


class EmbeddingProvider(ABC):
    """
    Abstract base for embedding provider implementations.

    Accepts a list of plain-text strings and returns their vector
    representations.  Concrete providers handle batching, dimension
    configuration, and API-specific error conversion internally.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResponse:
        """
        Compute embeddings for one or more texts.

        Args:
            texts: Non-empty list of non-empty strings to embed.

        Returns:
            EmbeddingResponse with one embedding vector per input text.

        Raises:
            LLMProviderError: On any provider-level failure.
        """
