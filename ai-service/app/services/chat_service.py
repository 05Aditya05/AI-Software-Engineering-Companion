"""
Chat service layer.

Encapsulates conversational processing logic, separating business rules
and state management from the FastAPI HTTP transport layer.
The LLMProvider abstraction is injected; the service has no knowledge
of which specific provider is in use.
"""

from datetime import datetime, timezone

from app.config import settings
from app.exceptions import LLMProviderError, ValidationError
from app.providers.base import LLMProvider, LLMResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversation import ConversationManager
from app.services.prompt import PromptBuilder


def _build_default_provider() -> LLMProvider:
    """Construct the default GeminiProvider from application settings.

    Import is deferred to avoid importing Gemini SDK at module level
    (keeps tests that mock the provider independent of the SDK).
    """
    from app.providers.gemini import GeminiProvider  # noqa: PLC0415

    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_ms=settings.llm_timeout_ms,
    )


class ChatService:
    """
    Core service coordinating conversation state, prompt construction,
    and LLM response generation.
    """

    def __init__(
        self,
        conversation_manager: ConversationManager | None = None,
        prompt_builder: PromptBuilder | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.conversation_manager = conversation_manager or ConversationManager()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self._provider = provider  # None means "lazy-init on first call"

    def process_message(
        self,
        request: ChatRequest,
        project_context: str | None = None,
    ) -> ChatResponse:
        """
        Process an incoming chat request through the core AI pipeline.

        1. Validates input
        2. Retrieves or initializes conversation session
        3. Retrieves prior message history
        4. Constructs prompt messages (with optional project context)
        5. Calls LLM provider
        6. Records conversation turns
        7. Returns structured ChatResponse
        """
        # 1. Validation
        cleaned_message = request.message.strip()
        if not cleaned_message:
            raise ValidationError("Message must contain at least one non-whitespace character.")

        # 2. Session resolution
        session = self.conversation_manager.get_or_create_session(request.conversation_id)
        conv_id = session.conversation_id

        # 3. Retrieve prior history
        history = session.get_messages()

        # 4. Construct prompt sequence
        prompt_messages = self.prompt_builder.build_prompt_messages(
            user_message=cleaned_message,
            history=history,
            project_context=project_context,
        )
        prompt_summary = self.prompt_builder.format_debug_summary(prompt_messages)

        # 5. Generate reply via LLM provider
        llm_response = self._call_provider(prompt_messages)
        reply_text = llm_response.text

        now_iso = datetime.now(timezone.utc).isoformat()

        # 6. Record turns in conversation history
        self.conversation_manager.add_user_message(
            conversation_id=conv_id,
            content=cleaned_message,
            metadata=request.client_metadata,
        )
        self.conversation_manager.add_assistant_message(
            conversation_id=conv_id,
            content=reply_text,
            metadata={"model": llm_response.model, "provider": llm_response.provider},
        )

        # 7. Construct structured response
        return ChatResponse(
            message=reply_text,
            source="ai-service",
            conversation_id=conv_id,
            timestamp=now_iso,
            status="success",
            meta={
                "provider": llm_response.provider,
                "model": llm_response.model,
                "history_length": len(history),
                "prompt_summary": prompt_summary,
            },
        )

    def _call_provider(self, prompt_messages: list[dict[str, str]]) -> LLMResponse:
        """Resolve the provider (lazy-init if needed) and call it."""
        if self._provider is None:
            self._provider = _build_default_provider()
        return self._provider.chat(prompt_messages)


# Default singleton instance for dependency injection.
# Provider is lazy-initialised on first request so that import-time
# configuration errors are surfaced at runtime, not startup.
default_chat_service = ChatService()
