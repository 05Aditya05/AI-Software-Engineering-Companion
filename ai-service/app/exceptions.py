"""
Domain exceptions for the AI Service.

Defines custom, structured exceptions used across the service and domain layers.
These are mapped to HTTP responses by centralized exception handlers.
"""


class AIServiceException(Exception):
    """Base exception for all domain-level AI service errors."""

    def __init__(self, message: str, code: str = "AI_SERVICE_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ValidationError(AIServiceException):
    """Raised when incoming data fails business validation rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="VALIDATION_ERROR")


class SessionNotFoundError(AIServiceException):
    """Raised when a requested conversation session does not exist."""

    def __init__(self, conversation_id: str) -> None:
        super().__init__(
            f"Conversation session '{conversation_id}' was not found.",
            code="SESSION_NOT_FOUND",
        )
