"""
FastAPI application factory.

Creates and configures the FastAPI application instance.
Mounts routers, middleware, and exception handlers.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health


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

    # Mount routers
    app.include_router(health.router, prefix="/api/health")

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
