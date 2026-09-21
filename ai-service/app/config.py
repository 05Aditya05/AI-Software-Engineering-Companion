"""
Application configuration.

Loads settings from environment variables using Pydantic Settings.
All configuration access should go through this module.
"""

from pydantic import Field
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
            "You are the AI Software Engineering Companion, a serious, pragmatic "
            "engineering partner. You assist developers with architecture, planning, "
            "code changes, debugging, and testing. Always adhere to project conventions, "
            "prefer minimal and safe changes, and explain your reasoning clearly."
        ),
        description="Default system instruction establishing companion persona"
    )

    # Backend service URL (for inter-service communication)
    backend_url: str = Field(
        default="http://localhost:3001",
        description="Node.js backend URL",
    )

    # LLM configuration (provider abstraction — Phase 4)
    llm_provider: str = Field(
        default="openai",
        description="LLM provider: openai, anthropic, google, ollama",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for the LLM provider",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="Model name to use",
    )

    # Embedding configuration (Phase 9)
    embedding_provider: str = Field(
        default="openai",
        description="Embedding provider",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton instance
settings = Settings()
