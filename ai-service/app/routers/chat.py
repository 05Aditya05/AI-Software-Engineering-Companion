"""
Chat router for the AI Service.

Receives chat requests forwarded from the Node.js backend.
Delegates business logic, conversation state, and response generation
to the ChatService layer.

In Phase 6, optionally assembles controlled project context from the
configured project root and passes it to the ChatService.
"""

from fastapi import APIRouter, status

from app.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import default_chat_service

router = APIRouter(tags=["chat"])


def _get_project_context() -> str | None:
    """
    Build project context if a project root is configured.

    Returns None if no project root is set or project service fails.
    The LLM prompt will simply omit the project context section in that case.
    """
    if not settings.project_root or not settings.project_root.strip():
        return None
    try:
        from app.services.project_service import ProjectService  # noqa: PLC0415

        svc = ProjectService(settings.project_root)
        return svc.build_context()
    except Exception:
        # Never let project context errors break the chat endpoint
        return None


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def process_chat(request: ChatRequest) -> ChatResponse:
    """
    Process incoming chat message and return a structured response.

    Delegates to the service layer for validation, session tracking,
    prompt assembly, and response formatting. Domain exceptions are caught
    by centralized exception handlers in app/main.py.

    If PROJECT_ROOT is configured, current project context is assembled
    and included in the system prompt automatically.
    """
    project_context = _get_project_context()
    return default_chat_service.process_message(request, project_context=project_context)
