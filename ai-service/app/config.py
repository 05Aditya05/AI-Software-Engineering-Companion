"""
Application configuration.

Loads settings from environment variables using Pydantic Settings.
All configuration access should go through this module.
"""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Service
    app_name: str = "AI Software Engineering Companion — AI Service"
    app_version: str = "0.1.0"
    companion_name: str = "AI Software Engineering Companion"
    debug: bool = Field(default=True, description="Enable debug mode")
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")

    # Conversation settings
    max_conversation_history: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum messages retained per in-memory conversation session"
    )
    default_system_prompt: str = Field(
        default=(
            "You are the AI Software Engineering Companion — a focused, pragmatic engineering "
            "partner for software developers. You specialise in:\n"
            "- Software architecture and design decisions\n"
            "- Debugging analysis and root-cause identification\n"
            "- Code review, refactoring guidance, and best practices\n"
            "- Testing strategy (unit, integration, end-to-end)\n"
            "- Development workflow and tooling\n"
            "- Technology selection and trade-off analysis\n\n"
            "Behaviour guidelines:\n"
            "- Be precise and concise. Prefer concrete examples over vague generalities.\n"
            "- Prefer minimal, safe changes when suggesting code modifications.\n"
            "- Acknowledge uncertainty rather than guessing.\n"
            "- Do NOT claim to have access to the user's project files or codebase unless "
            "project context has been explicitly provided to you in this conversation.\n"
            "- This is a current-session conversation only. You do not have long-term memory "
            "of past sessions."
        ),
        description="Default system instruction establishing the SE companion persona"
    )

    # Backend service URL (for inter-service communication)
    backend_url: str = Field(
        default="http://localhost:3001",
        description="Node.js backend URL",
    )

    # Gemini LLM configuration (Phase 4)
    gemini_api_key: str = Field(
        default="",
        description="Gemini API key — loaded from GEMINI_API_KEY env var",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model identifier",
    )
    llm_timeout_ms: int = Field(
        default=30000,
        ge=1000,
        description="LLM request timeout in milliseconds",
    )

    # Gemini Embedding configuration (Phase 9.2)
    embedding_model: str = Field(
        default="gemini-embedding-001",
        description="Gemini embedding model identifier",
    )

    # PostgreSQL connection (Phase 9.1)
    database_url: SecretStr = Field(
        default=SecretStr(""),
        description="Async PostgreSQL URL loaded from DATABASE_URL; never log this value",
    )

    # Project understanding configuration (Phase 6)
    project_root: str = Field(
        default="",
        description="Absolute path to the project root for project-understanding features",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton instance
settings = Settings()
