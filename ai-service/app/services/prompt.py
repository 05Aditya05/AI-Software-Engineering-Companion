"""
Prompt construction abstraction.

Builds structured prompt messages from system instructions, project context,
and conversation history. In Phase 4, the output of this builder will be fed
directly into LLM provider client calls.
"""

from typing import Any

from app.config import settings
from app.schemas.chat import ChatMessage, MessageRole


class PromptBuilder:
    """
    Constructs normalized prompt message sequences for language models.
    """

    def __init__(self, default_system_prompt: str = settings.default_system_prompt) -> None:
        self._default_system_prompt = default_system_prompt

    def build_prompt_messages(
        self,
        user_message: str,
        history: list[ChatMessage] | None = None,
        system_prompt: str | None = None,
        project_context: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Assemble a list of role/content message dictionaries.

        Structure:
        1. System message (base system prompt + optional project context)
        2. Prior conversation history messages (role/content)
        3. Current user message
        """
        messages: list[dict[str, str]] = []

        # 1. Base system prompt
        active_system_prompt = (system_prompt or self._default_system_prompt).strip()
        if project_context and project_context.strip():
            active_system_prompt += f"\n\n--- Project Context ---\n{project_context.strip()}"

        if active_system_prompt:
            messages.append({
                "role": MessageRole.SYSTEM.value,
                "content": active_system_prompt,
            })

        # 2. Historical messages
        if history:
            for item in history:
                messages.append({
                    "role": item.role.value,
                    "content": item.content,
                })

        # 3. New incoming user message
        messages.append({
            "role": MessageRole.USER.value,
            "content": user_message.strip(),
        })

        return messages

    def format_debug_summary(self, prompt_messages: list[dict[str, str]]) -> dict[str, Any]:
        """Produce a lightweight summary of the constructed prompt for observability."""
        return {
            "total_messages": len(prompt_messages),
            "roles": [m["role"] for m in prompt_messages],
            "total_chars": sum(len(m["content"]) for m in prompt_messages),
        }
