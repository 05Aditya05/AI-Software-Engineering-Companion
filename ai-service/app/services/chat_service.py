"""
Chat service layer.

Encapsulates conversational processing logic, separating business rules
and state management from the FastAPI HTTP transport layer.
The LLMProvider abstraction is injected; the service has no knowledge
of which specific provider is in use.

Phase 8 adds optional AgentOrchestrator integration: when a ToolRegistry
is present, requests are routed through the orchestrator's bounded tool
loop.  When no registry is configured, the existing direct-LLM path is
used (Phase 5/6 behaviour preserved).
"""

from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.exceptions import LLMProviderError, ValidationError
from app.providers.base import LLMProvider, LLMResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.conversation import ConversationManager
from app.services.prompt import PromptBuilder
from app.tools.registry import ToolRegistry


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

    When a *tool_registry* is provided the service delegates to the
    AgentOrchestrator for tool-augmented reasoning.  Otherwise the
    direct LLM call path is used (Phase 5/6 behaviour).
    """

    def __init__(
        self,
        conversation_manager: ConversationManager | None = None,
        prompt_builder: PromptBuilder | None = None,
        provider: LLMProvider | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.conversation_manager = conversation_manager or ConversationManager()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self._provider = provider  # None means "lazy-init on first call"
        self._tool_registry = tool_registry

    def process_message(
        self,
        request: ChatRequest,
        project_context: str | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> ChatResponse:
        """
        Process an incoming chat request through the core AI pipeline.

        1. Validates input
        2. Retrieves or initializes conversation session
        3. Retrieves prior message history
        4. Constructs prompt messages (with optional project context)
        5. Generates reply via LLM (direct or via AgentOrchestrator)
        6. Records conversation turns
        7. Returns structured ChatResponse
        """
        import time
        from app.services.telemetry import default_telemetry_service

        t_start = time.perf_counter()

        try:
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
                screen_context=request.screen_context,
            )
            prompt_summary = self.prompt_builder.format_debug_summary(prompt_messages)

            # 5. Generate reply — via orchestrator if tools available, else direct
            active_registry = tool_registry if tool_registry is not None else self._tool_registry
            reply_text, extra_meta = self._generate_reply(prompt_messages, tool_registry=active_registry)

            now_iso = datetime.now(timezone.utc).isoformat()
            total_duration_ms = (time.perf_counter() - t_start) * 1000

            # 6. Record turns in conversation history
            self.conversation_manager.add_user_message(
                conversation_id=conv_id,
                content=cleaned_message,
                metadata=request.client_metadata,
            )
            self.conversation_manager.add_assistant_message(
                conversation_id=conv_id,
                content=reply_text,
                metadata=extra_meta.get("llm_meta"),
            )

            # Record turn telemetry
            llm_meta = extra_meta.get("llm_meta") or {}
            model_name = extra_meta.get("model") or llm_meta.get("model")
            provider_name = extra_meta.get("provider") or llm_meta.get("provider")
            prompt_chars = prompt_summary.get("total_chars", len(cleaned_message))
            tool_calls = extra_meta.get("agent_tool_calls", [])

            try:
                default_telemetry_service.record_turn(
                    conversation_id=conv_id,
                    total_duration_ms=total_duration_ms,
                    llm_duration_ms=total_duration_ms,
                    tool_calls_count=len(tool_calls),
                    prompt_chars=prompt_chars,
                    response_chars=len(reply_text),
                    model=model_name,
                    provider=provider_name,
                    success=True,
                )
            except Exception:
                pass

            # 7. Construct structured response
            meta: dict[str, Any] = {
                "history_length": len(history),
                "prompt_summary": prompt_summary,
            }
            if request.screen_context and request.screen_context.user_granted_permission:
                meta["screen_context_attached"] = True
                if request.screen_context.window_title:
                    meta["screen_window_title"] = request.screen_context.window_title
            meta.update(extra_meta)

            return ChatResponse(
                message=reply_text,
                source="ai-service",
                conversation_id=conv_id,
                timestamp=now_iso,
                status="success",
                meta=meta,
            )
        except Exception as exc:
            total_duration_ms = (time.perf_counter() - t_start) * 1000
            try:
                default_telemetry_service.record_turn(
                    conversation_id=request.conversation_id or "unknown",
                    total_duration_ms=total_duration_ms,
                    success=False,
                    error=str(exc),
                )
            except Exception:
                pass
            raise

    # ------------------------------------------------------------------
    # Reply generation
    # ------------------------------------------------------------------

    def _generate_reply(
        self,
        prompt_messages: list[dict[str, str]],
        tool_registry: ToolRegistry | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Generate a reply, routing through the orchestrator if tools exist.

        Returns:
            (reply_text, extra_metadata_dict)
        """
        provider = self._resolve_provider()

        if tool_registry is not None:
            return self._generate_via_orchestrator(provider, prompt_messages, tool_registry)

        return self._generate_direct(provider, prompt_messages)

    def _generate_direct(
        self, provider: LLMProvider, prompt_messages: list[dict[str, str]]
    ) -> tuple[str, dict[str, Any]]:
        """Phase 5/6 direct-LLM path (no tools)."""
        llm_response = provider.chat(prompt_messages)
        meta = {
            "provider": llm_response.provider,
            "model": llm_response.model,
            "llm_meta": {"model": llm_response.model, "provider": llm_response.provider},
        }
        return llm_response.text, meta

    def _generate_via_orchestrator(
        self,
        provider: LLMProvider,
        prompt_messages: list[dict[str, str]],
        tool_registry: ToolRegistry,
    ) -> tuple[str, dict[str, Any]]:
        """Phase 8 orchestrator path (with tools)."""
        from app.services.agent_orchestrator import AgentOrchestrator  # noqa: PLC0415

        orchestrator = AgentOrchestrator(
            provider=provider,
            registry=tool_registry,
        )
        agent_response = orchestrator.process(prompt_messages)
        meta: dict[str, Any] = {
            "agent_steps_used": agent_response.steps_used,
            "agent_tool_calls": agent_response.tool_calls_made,
            "llm_meta": {},
        }
        return agent_response.message, meta

    # ------------------------------------------------------------------
    # Provider helpers
    # ------------------------------------------------------------------

    def _resolve_provider(self) -> LLMProvider:
        """Resolve the provider (lazy-init if needed)."""
        if self._provider is None:
            self._provider = _build_default_provider()
        return self._provider


# Default singleton instance for dependency injection.
# Provider is lazy-initialised on first request so that import-time
# configuration errors are surfaced at runtime, not startup.
default_chat_service = ChatService()
