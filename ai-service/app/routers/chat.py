"""
Chat router for the AI Service.

Receives chat requests forwarded from the Node.js backend.
Delegates business logic, conversation state, and response generation
to the ChatService layer.

In Phase 6, optionally assembles controlled project context from the
configured project root and passes it to the ChatService.

In Phase 8, when a project root is configured, a ToolRegistry is
created and injected so that the ChatService can use the
AgentOrchestrator for tool-augmented reasoning.
"""

from fastapi import APIRouter, status

from app.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import default_chat_service
from app.tools.registry import ToolRegistry

router = APIRouter(tags=["chat"])

# ------------------------------------------------------------------
# Module-level lazy singleton for ToolRegistry
# ------------------------------------------------------------------
_tool_registry: ToolRegistry | None = None


def _get_tool_registry() -> ToolRegistry | None:
    """Build a ToolRegistry if a valid project root is configured."""
    global _tool_registry  # noqa: PLW0603
    if _tool_registry is not None:
        return _tool_registry

    if not settings.project_root or not settings.project_root.strip():
        return None

    try:
        from app.tools.project_tools import create_default_tool_registry  # noqa: PLC0415

        _tool_registry = create_default_tool_registry(settings.project_root)
        return _tool_registry
    except Exception:
        return None


def _get_project_context() -> str | None:
    """
    Build project context if a project root is configured.

    Returns None if no project root is set or project service fails.
    The LLM prompt will simply omit the project context section in that case.

    Phase 8: also appends tool descriptions so the LLM knows which
    tools are available.

    Integration Bridge: appends relevant verified engineering lessons
    and decisions from long-term memory when database is configured.
    """
    if not settings.project_root or not settings.project_root.strip():
        return None
    try:
        from app.services.project_service import ProjectService  # noqa: PLC0415

        svc = ProjectService(settings.project_root)
        context = svc.build_context()

        # Append memory section if DB configured
        try:
            mem_section = _get_verified_memory_summary(settings.project_root)
            if mem_section:
                context += "\n\n" + mem_section
        except Exception:
            pass

        # Append tool instructions if registry is available
        registry = _get_tool_registry()
        if registry is not None:
            from app.services.agent_orchestrator import build_tool_prompt_section  # noqa: PLC0415

            tool_section = build_tool_prompt_section(registry)
            if tool_section:
                context += "\n\n--- Available Tools ---\n" + tool_section

        return context
    except Exception:
        # Never let project context errors break the chat endpoint
        return None


def _get_verified_memory_summary(project_root: str) -> str | None:
    """Synchronously retrieve up to 3 verified lessons/decisions for prompt injection."""
    db_url = settings.database_url.get_secret_value()
    if not db_url:
        return None

    try:
        import asyncio
        import concurrent.futures
        from pathlib import Path
        from app.db import get_session
        from app.memory.schemas import MemorySearchRequest
        from app.memory.service import MemoryService
        from app.models.memory import MemoryVerificationStatus

        svc = MemoryService()
        norm_root = str(Path(project_root).resolve()).lower()

        async def _fetch():
            req = MemorySearchRequest(
                verification_status=MemoryVerificationStatus.VERIFIED,
                limit=6,
                offset=0,
            )
            async for session in get_session():
                _, entries = await svc.search(session, req)
                return entries
            return []

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                entries = pool.submit(asyncio.run, _fetch()).result()
        else:
            entries = asyncio.run(_fetch())

        # Enforce project isolation: global OR active project
        relevant = [
            e for e in entries
            if e.scope == "global" or (e.scope == "project" and e.project_root and str(Path(e.project_root).resolve()).lower() == norm_root)
        ][:3]

        if not relevant:
            return None

        lines = ["--- Long-Term Memory (Verified Engineering Lessons) ---"]
        for m in relevant:
            lines.append(f"- [{m.category}] {m.summary}: {m.content[:200]} (Source: {m.source})")

        return "\n".join(lines)
    except Exception:
        return None



@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def process_chat(request: ChatRequest) -> ChatResponse:
    """
    Process incoming chat message and return a structured response.

    Delegates to the service layer for validation, session tracking,
    prompt assembly, and response formatting. Domain exceptions are caught
    by centralized exception handlers in app/main.py.

    If PROJECT_ROOT is configured, current project context is assembled
    and included in the system prompt automatically. Phase 8 also provides
    tool-augmented reasoning via the AgentOrchestrator.
    """
    project_context = _get_project_context()
    tool_registry = _get_tool_registry()
    return default_chat_service.process_message(
        request,
        project_context=project_context,
        tool_registry=tool_registry,
    )

