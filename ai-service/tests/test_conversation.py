"""Unit tests for conversation session and history management."""

from app.schemas.chat import MessageRole
from app.services.conversation import ConversationManager, ConversationSession


def test_session_creation() -> None:
    """Test creating an empty conversation session."""
    session = ConversationSession(conversation_id="conv-test-1", max_history=10)
    assert session.conversation_id == "conv-test-1"
    assert len(session.get_messages()) == 0


def test_session_history_bounded() -> None:
    """Test that session enforces max_history limit by trimming older messages."""
    session = ConversationSession(conversation_id="conv-bounded", max_history=3)
    manager = ConversationManager(max_history=3)

    for i in range(5):
        manager.add_user_message("conv-bounded", f"Message #{i}")

    history = manager.get_history("conv-bounded")
    assert len(history) == 3
    # Should retain the 3 most recent messages (2, 3, 4)
    assert history[0].content == "Message #2"
    assert history[1].content == "Message #3"
    assert history[2].content == "Message #4"


def test_manager_get_or_create_auto_id() -> None:
    """Test generating a unique session ID when none is provided."""
    manager = ConversationManager()
    session1 = manager.get_or_create_session()
    session2 = manager.get_or_create_session()
    assert session1.conversation_id.startswith("conv-")
    assert session2.conversation_id.startswith("conv-")
    assert session1.conversation_id != session2.conversation_id


def test_manager_add_and_retrieve_messages() -> None:
    """Test adding both user and assistant messages and retrieving history."""
    manager = ConversationManager()
    conv_id = "conv-turns"

    user_msg = manager.add_user_message(conv_id, "How do I run tests?")
    assert user_msg.role == MessageRole.USER

    asst_msg = manager.add_assistant_message(conv_id, "Use npm test.")
    assert asst_msg.role == MessageRole.ASSISTANT

    history = manager.get_history(conv_id)
    assert len(history) == 2
    assert history[0].role == MessageRole.USER
    assert history[1].role == MessageRole.ASSISTANT


def test_manager_clear_session() -> None:
    """Test clearing messages from an existing session."""
    manager = ConversationManager()
    conv_id = "conv-clear"
    manager.add_user_message(conv_id, "Test message")
    assert len(manager.get_history(conv_id)) == 1

    cleared = manager.clear_session(conv_id)
    assert cleared is True
    assert len(manager.get_history(conv_id)) == 0

    # Clearing non-existent session returns False
    assert manager.clear_session("conv-nonexistent") is False
