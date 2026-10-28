"""Unit tests for prompt construction abstraction."""

from app.schemas.chat import ChatMessage, MessageRole
from app.services.prompt import PromptBuilder


def test_prompt_builder_basic() -> None:
    """Test building a basic prompt without prior history."""
    builder = PromptBuilder(default_system_prompt="You are a companion.")
    messages = builder.build_prompt_messages(user_message="Hello!")

    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "You are a companion."}
    assert messages[1] == {"role": "user", "content": "Hello!"}


def test_prompt_builder_with_history() -> None:
    """Test assembling prompt messages with conversation history."""
    builder = PromptBuilder(default_system_prompt="Base system.")
    history = [
        ChatMessage(
            role=MessageRole.USER,
            content="Turn 1 user",
            timestamp="2026-09-22T00:00:00Z"
        ),
        ChatMessage(
            role=MessageRole.ASSISTANT,
            content="Turn 1 assistant",
            timestamp="2026-09-22T00:00:01Z"
        ),
    ]

    messages = builder.build_prompt_messages(
        user_message="Turn 2 user",
        history=history,
    )

    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Turn 1 user"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "Turn 1 assistant"
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "Turn 2 user"


def test_prompt_builder_project_context() -> None:
    """Test injecting project context into system instructions."""
    builder = PromptBuilder(default_system_prompt="Base system.")
    messages = builder.build_prompt_messages(
        user_message="List files",
        project_context="Root: E:/project\nFiles: 3",
    )

    assert len(messages) == 2
    assert "--- Project Context ---" in messages[0]["content"]
    assert "E:/project" in messages[0]["content"]


def test_prompt_builder_debug_summary() -> None:
    """Test generating a debug summary of the constructed prompt."""
    builder = PromptBuilder()
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    summary = builder.format_debug_summary(messages)
    assert summary["total_messages"] == 2
    assert summary["roles"] == ["system", "user"]
    assert summary["total_chars"] == 6


def test_prompt_builder_screen_context_permitted() -> None:
    """Phase 14: Screen context is injected into system prompt when explicitly permitted."""
    from app.schemas.chat import ScreenContextPayload

    payload = ScreenContextPayload(
        user_granted_permission=True,
        window_title="VS Code — main.py",
        display_name="Display 1",
        captured_at="2026-10-28T12:00:00Z",
    )
    builder = PromptBuilder(default_system_prompt="Base system.")
    messages = builder.build_prompt_messages(
        user_message="Explain what is on my screen",
        screen_context=payload,
    )

    assert len(messages) == 2
    sys_content = messages[0]["content"]
    assert "--- Screen Context (User-Granted) ---" in sys_content
    assert "Active Window: VS Code — main.py" in sys_content
    assert "Display: Display 1" in sys_content
    assert "Captured At: 2026-10-28T12:00:00Z" in sys_content
    assert "Do not persist captured screen data to long-term memory" in sys_content


def test_prompt_builder_screen_context_denied() -> None:
    """Phase 14: Screen context is NOT injected when user_granted_permission is False."""
    from app.schemas.chat import ScreenContextPayload

    payload = ScreenContextPayload(
        user_granted_permission=False,
        window_title="Hidden Window",
    )
    builder = PromptBuilder(default_system_prompt="Base system.")
    messages = builder.build_prompt_messages(
        user_message="Explain what is on my screen",
        screen_context=payload,
    )

    assert len(messages) == 2
    sys_content = messages[0]["content"]
    assert "--- Screen Context (User-Granted) ---" not in sys_content
    assert "Hidden Window" not in sys_content

