"""
Tests for Phase 9.6 — SemanticSearchTool and ToolRegistry integration.

No real database or embedding API is used.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.retrieval import RetrievalResult, RetrievalService
from app.models.project_knowledge import EMBEDDING_DIMENSION
from app.providers.base import EmbeddingProvider, EmbeddingResponse
from app.tools.base import PermissionLevel, ToolResult
from app.tools.semantic_search_tool import EXCERPT_CHARS, SemanticSearchTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_retrieval_service(
    results: list[RetrievalResult] | None = None,
    raise_error: Exception | None = None,
) -> RetrievalService:
    provider = MagicMock(spec=EmbeddingProvider)
    svc = MagicMock(spec=RetrievalService)
    if raise_error:
        svc.search = AsyncMock(side_effect=raise_error)
    else:
        svc.search = AsyncMock(return_value=results or [])
    return svc


def _make_tool(
    results: list[RetrievalResult] | None = None,
    raise_error: Exception | None = None,
) -> SemanticSearchTool:
    svc = _make_retrieval_service(results=results, raise_error=raise_error)
    tool = SemanticSearchTool(retrieval_service=svc, project_root="/project")
    return tool


# ---------------------------------------------------------------------------
# Tool interface
# ---------------------------------------------------------------------------


class TestSemanticSearchToolInterface:
    def test_name(self):
        tool = _make_tool()
        assert tool.name == "semantic_search"

    def test_permission_is_read_only(self):
        tool = _make_tool()
        assert tool.permission == PermissionLevel.READ_ONLY

    def test_description_is_non_empty(self):
        tool = _make_tool()
        assert len(tool.description) > 20

    def test_input_schema_has_query(self):
        tool = _make_tool()
        schema = tool.input_schema
        assert "query" in schema["properties"]
        assert "query" in schema.get("required", [])

    def test_input_schema_has_top_k(self):
        tool = _make_tool()
        schema = tool.input_schema
        assert "top_k" in schema["properties"]


# ---------------------------------------------------------------------------
# execute() — validation
# ---------------------------------------------------------------------------


class TestSemanticSearchToolExecute:
    def test_missing_query_returns_fail(self):
        tool = _make_tool()
        result = tool.execute({})
        assert not result.success
        assert result.error.code == "MISSING_PARAMETER"

    def test_empty_query_returns_fail(self):
        tool = _make_tool()
        result = tool.execute({"query": "   "})
        assert not result.success
        assert result.error.code == "MISSING_PARAMETER"

    def test_valid_query_with_no_results(self):
        tool = _make_tool(results=[])
        with patch.object(tool, "_run_search", return_value=[]):
            result = tool.execute({"query": "authentication"})
        assert result.success
        assert result.data["total_results"] == 0

    def test_returns_results_with_correct_fields(self):
        results = [
            RetrievalResult(
                file_path="src/auth.py",
                content="def authenticate(user): ...",
                line_start=5,
                line_end=15,
                chunk_index=0,
                score=0.92,
            )
        ]
        tool = _make_tool(results=results)
        with patch.object(tool, "_run_search", return_value=results):
            result = tool.execute({"query": "authentication"})

        assert result.success
        assert result.data["total_results"] == 1
        item = result.data["results"][0]
        assert item["file_path"] == "src/auth.py"
        assert item["line_start"] == 5
        assert item["line_end"] == 15
        assert "score" in item
        assert "excerpt" in item

    def test_excerpt_is_capped(self):
        long_content = "x" * 2000
        results = [
            RetrievalResult(
                file_path="big.py",
                content=long_content,
                line_start=1,
                line_end=100,
                chunk_index=0,
                score=0.9,
            )
        ]
        tool = _make_tool(results=results)
        with patch.object(tool, "_run_search", return_value=results):
            result = tool.execute({"query": "query"})

        excerpt = result.data["results"][0]["excerpt"]
        assert len(excerpt) <= EXCERPT_CHARS + 1  # +1 for ellipsis char

    def test_embedding_error_returns_fail(self):
        from app.exceptions import LLMProviderError

        tool = _make_tool(raise_error=LLMProviderError("embed failed", code="LLM_RATE_LIMIT"))
        with patch.object(
            tool,
            "_run_search",
            side_effect=LLMProviderError("embed failed", code="LLM_RATE_LIMIT"),
        ):
            result = tool.execute({"query": "query"})
        assert not result.success

    def test_db_error_returns_fail(self):
        tool = _make_tool(raise_error=RuntimeError("db connection failed"))
        with patch.object(
            tool,
            "_run_search",
            side_effect=RuntimeError("db connection failed"),
        ):
            result = tool.execute({"query": "query"})
        assert not result.success

    def test_top_k_default_applied(self):
        tool = _make_tool(results=[])
        with patch.object(tool, "_run_search", return_value=[]) as mock_run:
            tool.execute({"query": "test"})
        # Just verify it doesn't crash with default top_k

    def test_top_k_invalid_type_uses_default(self):
        tool = _make_tool(results=[])
        with patch.object(tool, "_run_search", return_value=[]):
            result = tool.execute({"query": "test", "top_k": "not_a_number"})
        assert result.success  # Should not crash


# ---------------------------------------------------------------------------
# ToolRegistry integration
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    def test_semantic_search_tool_can_be_registered(self):
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        tool = _make_tool()
        registry.register(tool)
        assert registry.has_tool("semantic_search")

    def test_semantic_search_listed_in_tool_list(self):
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(_make_tool())
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "semantic_search" in names

    def test_semantic_search_permission_enforced(self):
        """semantic_search is READ_ONLY — should execute under READ_ONLY budget."""
        from app.tools.registry import ToolRegistry

        registry = ToolRegistry()
        tool = _make_tool(results=[])
        registry.register(tool)
        with patch.object(tool, "_run_search", return_value=[]):
            result = registry.execute(
                "semantic_search",
                {"query": "test"},
                max_allowed_permission=PermissionLevel.READ_ONLY,
            )
        assert result.success

    def test_create_default_registry_without_db_has_base_tools(self):
        """Factory should register base 4 tools even when DB/API key absent."""
        import tempfile

        from app.tools.project_tools import create_default_tool_registry

        with tempfile.TemporaryDirectory() as tmp:
            registry = create_default_tool_registry(tmp)
            assert registry.has_tool("list_files")
            assert registry.has_tool("read_file")
            assert registry.has_tool("search_code")
            assert registry.has_tool("inspect_file")
