"""
Chat router for the AI Service.

Receives chat requests forwarded from the Node.js backend.
Delegates business logic, conversation state, and response generation
to the ChatService layer.
"""

from fastapi import APIRouter, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import default_chat_service

router = APIRouter(tags=["chat"])


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def process_chat(request: ChatRequest) -> ChatResponse:
    """
    Process incoming chat message and return a structured response.

    Delegates to the service layer for validation, session tracking,
    prompt assembly, and response formatting. Domain exceptions are caught
    by centralized exception handlers in app/main.py.
    """
    return default_chat_service.process_message(request)
