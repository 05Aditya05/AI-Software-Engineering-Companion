"""
Conversation and message handling abstraction.

Provides in-memory session and message history management with bounded
history retention. Decouples state tracking from API routes and prepares
the foundation for multi-turn conversational agents.
"""

from datetime import datetime, timezone
from typing import Any
import uuid

from app.config import settings
from app.schemas.chat import ChatMessage, MessageRole


class ConversationSession:
    """Represents an active multi-turn conversation session."""

    def __init__(
        self,
        conversation_id: str,
        max_history: int = settings.max_conversation_history
    ) -> None:
        self.conversation_id = conversation_id
        self.max_history = max_history
        now_iso = datetime.now(timezone.utc).isoformat()
        self.created_at = now_iso
        self.updated_at = now_iso
        self.messages: list[ChatMessage] = []

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the session history, enforcing max history limit."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc).isoformat()

        # Keep only the most recent messages up to max_history
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def get_messages(self) -> list[ChatMessage]:
        """Return a shallow copy of messages in this session."""
        return list(self.messages)

    def clear(self) -> None:
        """Clear all messages in this session."""
        self.messages.clear()
        self.updated_at = datetime.now(timezone.utc).isoformat()


class ConversationManager:
    """
    Manages in-memory conversation sessions across the service lifecycle.
    """

    def __init__(self, max_history: int = settings.max_conversation_history) -> None:
        self._max_history = max_history
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create_session(
        self,
        conversation_id: str | None = None
    ) -> ConversationSession:
        """Retrieve an existing session or create a new one with a unique ID."""
        active_id = conversation_id.strip() if conversation_id and conversation_id.strip() else None

        if not active_id:
            active_id = f"conv-{uuid.uuid4().hex[:12]}"

        if active_id not in self._sessions:
            self._sessions[active_id] = ConversationSession(
                conversation_id=active_id,
                max_history=self._max_history
            )

        return self._sessions[active_id]

    def get_session(self, conversation_id: str) -> ConversationSession | None:
        """Retrieve a session by ID, or None if it doesn't exist."""
        return self._sessions.get(conversation_id.strip())

    def add_user_message(
        self,
        conversation_id: str,
        content: str,
        metadata: dict[str, Any] | None = None
    ) -> ChatMessage:
        """Add a user message to the specified conversation session."""
        session = self.get_or_create_session(conversation_id)
        msg = ChatMessage(
            role=MessageRole.USER,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata
        )
        session.add_message(msg)
        return msg

    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        metadata: dict[str, Any] | None = None
    ) -> ChatMessage:
        """Add an assistant message to the specified conversation session."""
        session = self.get_or_create_session(conversation_id)
        msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata
        )
        session.add_message(msg)
        return msg

    def get_history(self, conversation_id: str) -> list[ChatMessage]:
        """Return message history for a conversation session."""
        session = self.get_session(conversation_id)
        return session.get_messages() if session else []

    def clear_session(self, conversation_id: str) -> bool:
        """Clear messages in a session. Returns True if found, False otherwise."""
        session = self.get_session(conversation_id)
        if session:
            session.clear()
            return True
        return False

    @property
    def session_count(self) -> int:
        """Number of active sessions stored in memory."""
        return len(self._sessions)
