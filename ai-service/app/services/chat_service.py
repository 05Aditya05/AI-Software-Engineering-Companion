"""
Chat service layer.

Encapsulates conversational processing logic, separating business rules
and state management from the FastAPI HTTP transport layer.
In Phase 4, the LLM provider will be invoked directly inside this service.
"""

from datetime import datetime, timezone
from typing import Any

from app.exceptions import ValidationError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversation import ConversationManager
from app.services.prompt import PromptBuilder


class ChatService:
    """
    Core service coordinating conversation state, prompt construction,
    and response generation.
    """

    def __init__(
        self,
        conversation_manager: ConversationManager | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.conversation_manager = conversation_manager or ConversationManager()
        self.prompt_builder = prompt_builder or PromptBuilder()

    def process_message(self, request: ChatRequest) -> ChatResponse:
        """
        Process an incoming chat request through the core AI pipeline.

        1. Validates input
        2. Retrieves or initializes conversation session
        3. Retrieves prior message history
        4. Constructs prompt messages
        5. Generates reply (deterministic mock in Phase 3)
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
        )
        prompt_summary = self.prompt_builder.format_debug_summary(prompt_messages)

        # 5. Generate reply (clean hook for Phase 4 LLM provider)
        reply_text = self._generate_reply(
            user_message=cleaned_message,
            prompt_messages=prompt_messages,
            turn_count=len(history) // 2 + 1,
        )

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
            metadata={"mock": True, "turn": len(history) // 2 + 1},
        )

        # 7. Construct structured response
        return ChatResponse(
            message=reply_text,
            source="ai-service",
            conversation_id=conv_id,
            timestamp=now_iso,
            status="success",
            meta={
                "mock": True,
                "phase": "phase-3",
                "received_chars": len(cleaned_message),
                "history_length": len(history),
                "prompt_summary": prompt_summary,
            },
        )

    def _generate_reply(
        self,
        user_message: str,
        prompt_messages: list[dict[str, str]],
        turn_count: int,
    ) -> str:
        """
        Generate response text.

        In Phase 3, this returns a deterministic structured mock response.
        In Phase 4, this method will dispatch to the configured LLM provider.
        """
        return (
            f"[AI Service Phase 3 Core] Received: \"{user_message}\". "
            f"Active conversation turn #{turn_count} processed via service layer. "
            f"Prompt constructed with {len(prompt_messages)} message context."
        )


# Default singleton instance for dependency injection
default_chat_service = ChatService()
