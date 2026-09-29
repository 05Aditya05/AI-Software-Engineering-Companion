"""
LLM provider abstraction.

Defines the normalized response type and the abstract base class
that all LLM provider implementations must satisfy.

Gemini-specific (or any other provider-specific) objects must NOT
appear outside of their respective provider modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


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
