"""
Chat router for the AI Service.

Receives chat requests forwarded from the Node.js backend.
In Phase 2, this returns a deterministic structured mock response proving
the communication pipeline is operational across all service boundaries.
In Phase 4, this endpoint will hook into the LLM provider abstraction.
"""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def process_chat(request: ChatRequest) -> ChatResponse:
    """
    Process incoming chat message and return a structured response.

    Phase 2 implementation:
    Returns a deterministic mock response showing message receipt, assigned
    conversation ID, timestamp, and metadata.
    """
    # Defensive check: ensure message is not purely whitespace
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must contain at least one non-whitespace character."
        )

    # Use existing conversation ID or generate a new one
    active_conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"

    now_iso = datetime.now(timezone.utc).isoformat()

    # Deterministic response proving AI service reached successfully
    reply_text = (
        f"[AI Service Phase 2 Mock] Hello! I received your message: \"{cleaned_message}\". "
        f"The end-to-end communication pipeline (Frontend -> Backend -> AI Service -> Frontend) is operational!"
    )

    return ChatResponse(
        message=reply_text,
        source="ai-service",
        conversation_id=active_conversation_id,
        timestamp=now_iso,
        status="success",
        meta={
            "mock": True,
            "phase": "phase-2",
            "received_chars": len(cleaned_message),
        }
    )
