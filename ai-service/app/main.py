"""
FastAPI application factory.

Creates and configures the FastAPI application instance.
Mounts routers, middleware, and exception handlers.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import AIServiceException
from app.routers import health, chat
from app.routers import knowledge as knowledge_router
from app.routers import memory as memory_router
from app.routers import coding_agent as coding_agent_router
from app.routers import git as git_router
from app.routers import observability as observability_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler — startup and shutdown logic."""
    # Startup
    print(f"""
+==================================================+
|  AI Software Engineering Companion -- AI Service  |
+==================================================+
|  Status:  Running                                 |
|  Port:    {str(settings.port):<40}|
|  Debug:   {str(settings.debug):<40}|
|  Health:  http://localhost:{settings.port}/api/health{' ' * max(0, 14 - len(str(settings.port)))}|
+==================================================+
    """)
    yield
    # Shutdown
    print("AI Service shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered software engineering companion service",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Frontend
            "http://localhost:3001",  # Backend
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(AIServiceException)
    async def ai_service_exception_handler(_req: Request, exc: AIServiceException) -> JSONResponse:
        if exc.code == "VALIDATION_ERROR":
            status_code = 400
        elif exc.code == "LLM_RATE_LIMIT":
            status_code = 429
        elif exc.code == "LLM_AUTH_ERROR":
            status_code = 401
        elif exc.code == "SESSION_NOT_FOUND":
            status_code = 404
        elif exc.code == "LLM_TIMEOUT":
            status_code = 504
        else:
            status_code = 500

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "error",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
        )

    # Mount routers
    app.include_router(health.router, prefix="/api/health")
    app.include_router(chat.router, prefix="/api/chat")
    app.include_router(knowledge_router.router, prefix="/api/knowledge")
    app.include_router(memory_router.router, prefix="/api/memory")
    app.include_router(coding_agent_router.router, prefix="/api/agent")
    app.include_router(git_router.router, prefix="/api/git")
    app.include_router(observability_router.router, prefix="/api/observability")

    # Root endpoint
    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


# Application instance
app = create_app()
