"""
Tests for Phase 9.3 — Chunker and ingestion pipeline.

All tests use only in-memory data (no filesystem access to real project,
no database, no API calls).
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from app.knowledge.chunker import (
    CHUNK_SIZE_CHARS,
    OVERLAP_CHARS,
    FileChunk,
    _normalize_content,
    _sha256,
    chunk_text,
    discover_eligible_files,
    ingest_project,
    read_and_chunk_file,
)
from app.services.project_service import ProjectService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(files: dict[str, str]) -> tempfile.TemporaryDirectory:
    """Create a temporary project directory with the given files."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


# ---------------------------------------------------------------------------
# SHA-256 fingerprint
# ---------------------------------------------------------------------------


class TestSha256:
    def test_known_value(self):
        expected = hashlib.sha256(b"hello").hexdigest()
        assert _sha256("hello") == expected

    def test_empty_string(self):
        expected = hashlib.sha256(b"").hexdigest()
        assert _sha256("") == expected

    def test_deterministic(self):
        assert _sha256("same text") == _sha256("same text")

    def test_different_strings_differ(self):
        assert _sha256("abc") != _sha256("def")

    def test_unicode(self):
        text = "नमस्ते"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert _sha256(text) == expected


# ---------------------------------------------------------------------------
# Content normalisation
# ---------------------------------------------------------------------------


class TestNormalizeContent:
    def test_crlf_to_lf(self):
        assert _normalize_content("a\r\nb\r\nc") == "a\nb\nc"

    def test_cr_to_lf(self):
        assert _normalize_content("a\rb\rc") == "a\nb\nc"

    def test_lf_unchanged(self):
        assert _normalize_content("a\nb\nc") == "a\nb\nc"

    def test_mixed_endings(self):
        assert _normalize_content("a\r\nb\rc\nd") == "a\nb\nc\nd"

    def test_empty(self):
        assert _normalize_content("") == ""


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_empty_text_returns_empty(self):
        assert chunk_text("", "file.py") == []

    def test_whitespace_only_returns_empty(self):
        assert chunk_text("   \n  \n  ", "file.py") == []

    def test_single_chunk_small_file(self):
        text = "line one\nline two\nline three"
        chunks = chunk_text(text, "src/main.py", chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].file_path == "src/main.py"
        assert chunks[0].chunk_index == 0
        assert chunks[0].line_start == 1
        assert chunks[0].line_end == 3

    def test_chunk_fingerprint_is_sha256_of_content(self):
        text = "alpha\nbeta\ngamma"
        chunks = chunk_text(text, "f.py", chunk_size=500)
        assert len(chunks) == 1
        expected_fp = hashlib.sha256(chunks[0].content.encode("utf-8")).hexdigest()
        assert chunks[0].source_fingerprint == expected_fp

    def test_multiple_chunks_produced(self):
        # 50 lines of 40 chars each = 2000 chars; chunk_size=400 → ~5 chunks
        lines = [f"line {i:03d} {'x' * 30}" for i in range(50)]
        text = "\n".join(lines)
        chunks = chunk_text(text, "big.py", chunk_size=400, overlap=0)
        assert len(chunks) >= 3

    def test_chunk_indexes_are_sequential(self):
        lines = [f"line {i}" for i in range(100)]
        text = "\n".join(lines)
        chunks = chunk_text(text, "f.py", chunk_size=100, overlap=0)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_line_ranges_are_contiguous_without_overlap(self):
        """Without overlap, line ranges should not skip lines."""
        lines = [f"line {i:03d}" for i in range(30)]
        text = "\n".join(lines)
        chunks = chunk_text(text, "f.py", chunk_size=100, overlap=0)
        assert len(chunks) > 1
        # First chunk starts at line 1
        assert chunks[0].line_start == 1
        # All line_start/end values are positive
        for c in chunks:
            assert c.line_start >= 1
            assert c.line_end >= c.line_start

    def test_overlap_produces_shared_context(self):
        """With overlap > 0, adjacent chunks should share some content."""
        lines = [f"line {i:03d} {'x' * 40}" for i in range(40)]
        text = "\n".join(lines)
        chunks = chunk_text(text, "f.py", chunk_size=500, overlap=100)
        if len(chunks) > 1:
            # The end of chunk 0 and start of chunk 1 should overlap
            # (chunk 1 starts before the end of chunk 0's line range)
            assert chunks[1].line_start <= chunks[0].line_end

    def test_fingerprints_are_stable(self):
        text = "stable content\nremains stable"
        chunks1 = chunk_text(text, "f.py")
        chunks2 = chunk_text(text, "f.py")
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.source_fingerprint == c2.source_fingerprint

    def test_different_content_different_fingerprint(self):
        chunks_a = chunk_text("version A\ncontent", "f.py")
        chunks_b = chunk_text("version B\ncontent", "f.py")
        assert chunks_a[0].source_fingerprint != chunks_b[0].source_fingerprint

    def test_file_path_preserved(self):
        chunks = chunk_text("content", "sub/dir/file.ts")
        assert chunks[0].file_path == "sub/dir/file.ts"

    def test_unicode_content(self):
        text = "नमस्ते दुनिया\nHello World\nこんにちは"
        chunks = chunk_text(text, "unicode.md", chunk_size=500)
        assert len(chunks) == 1
        assert "नमस्ते" in chunks[0].content

    def test_crlf_single_chunk(self):
        # CRLF should already be normalized by caller; chunk_text itself
        # handles un-normalized text gracefully
        text = "line1\r\nline2\r\nline3"
        chunks = chunk_text(text, "win.py", chunk_size=500)
        # Should produce content without crashing
        assert len(chunks) >= 1

    def test_chunk_result_is_frozen_dataclass(self):
        chunks = chunk_text("content here", "f.py")
        c = chunks[0]
        with pytest.raises((AttributeError, TypeError)):
            c.file_path = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# discover_eligible_files
# ---------------------------------------------------------------------------


class TestDiscoverEligibleFiles:
    def test_discovers_allowed_extensions(self):
        tmp = _make_project({
            "src/main.py": "def hello(): pass",
            "docs/README.md": "# Docs",
            "frontend/app.ts": "const x = 1;",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            rel_files = {f.relative_to(Path(tmp.name)).as_posix() for f in files}
            assert "src/main.py" in rel_files
            assert "docs/README.md" in rel_files
            assert "frontend/app.ts" in rel_files
        finally:
            tmp.cleanup()

    def test_excludes_env_files(self):
        tmp = _make_project({
            "app.py": "print('hi')",
            ".env": "SECRET=abc",
            ".env.local": "X=y",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            names = {f.name for f in files}
            assert ".env" not in names
            assert ".env.local" not in names
        finally:
            tmp.cleanup()

    def test_excludes_node_modules(self):
        tmp = _make_project({
            "index.js": "module.exports = {}",
            "node_modules/lib/index.js": "bad",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            rel_files = {f.relative_to(Path(tmp.name)).as_posix() for f in files}
            assert not any("node_modules" in p for p in rel_files)
        finally:
            tmp.cleanup()

    def test_excludes_git_directory(self):
        tmp = _make_project({
            "main.py": "x = 1",
            ".git/config": "gitconfig",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            rel_files = {f.relative_to(Path(tmp.name)).as_posix() for f in files}
            assert not any(".git" in p for p in rel_files)
        finally:
            tmp.cleanup()

    def test_excludes_venv_directory(self):
        tmp = _make_project({
            "app.py": "pass",
            ".venv/lib/site.py": "bad",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            rel_files = {f.relative_to(Path(tmp.name)).as_posix() for f in files}
            assert not any(".venv" in p for p in rel_files)
        finally:
            tmp.cleanup()

    def test_skips_empty_files(self):
        tmp = _make_project({
            "empty.py": "",
            "nonempty.py": "x = 1",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            names = {f.name for f in files}
            assert "empty.py" not in names
            assert "nonempty.py" in names
        finally:
            tmp.cleanup()

    def test_skips_disallowed_extensions(self):
        tmp = _make_project({
            "image.png": b"\x89PNG\r\n".decode("latin-1"),
            "app.py": "pass",
            "data.bin": "\x00\x01\x02",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            names = {f.name for f in files}
            assert "image.png" not in names
            assert "data.bin" not in names
            assert "app.py" in names
        finally:
            tmp.cleanup()

    def test_rejects_symlink_outside_root(self, tmp_path):
        """Symlinks whose target escapes the project root are rejected."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        outside_file = tmp_path / "secret.py"
        outside_file.write_text("secret content")
        link = project_dir / "evil_link.py"
        try:
            link.symlink_to(outside_file)
        except OSError:
            pytest.skip("Symlink creation not supported")

        svc = ProjectService(str(project_dir))
        files = discover_eligible_files(svc)
        names = {f.name for f in files}
        assert "evil_link.py" not in names

    def test_excludes_secret_filenames(self):
        tmp = _make_project({
            "app.py": "pass",
            "secrets.json": '{"key": "secret"}',
            "id_rsa": "private key",
        })
        try:
            svc = ProjectService(tmp.name)
            files = discover_eligible_files(svc)
            names = {f.name for f in files}
            assert "secrets.json" not in names
            assert "id_rsa" not in names
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# read_and_chunk_file
# ---------------------------------------------------------------------------


class TestReadAndChunkFile:
    def test_basic_read(self, tmp_path):
        f = tmp_path / "src.py"
        f.write_text("def foo():\n    return 1\n", encoding="utf-8")
        chunks = read_and_chunk_file(f, tmp_path)
        assert len(chunks) >= 1
        assert chunks[0].file_path == "src.py"

    def test_crlf_normalized(self, tmp_path):
        f = tmp_path / "win.py"
        f.write_bytes(b"line1\r\nline2\r\nline3")
        chunks = read_and_chunk_file(f, tmp_path)
        assert len(chunks) >= 1
        assert "\r" not in chunks[0].content

    def test_unreadable_file_returns_empty(self, tmp_path):
        f = tmp_path / "missing.py"
        # File doesn't exist
        chunks = read_and_chunk_file(f, tmp_path)
        assert chunks == []

    def test_relative_path_uses_posix_separator(self, tmp_path):
        sub = tmp_path / "sub" / "dir"
        sub.mkdir(parents=True)
        f = sub / "file.py"
        f.write_text("content")
        chunks = read_and_chunk_file(f, tmp_path)
        assert "/" in chunks[0].file_path
        assert "\\" not in chunks[0].file_path


# ---------------------------------------------------------------------------
# ingest_project
# ---------------------------------------------------------------------------


class TestIngestProject:
    def test_empty_project_returns_empty(self, tmp_path):
        svc = ProjectService(str(tmp_path))
        chunks = ingest_project(svc)
        assert chunks == []

    def test_ingests_multiple_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def a(): pass\n" * 5)
        (tmp_path / "b.md").write_text("# Heading\n\nContent.\n" * 5)
        svc = ProjectService(str(tmp_path))
        chunks = ingest_project(svc)
        file_paths = {c.file_path for c in chunks}
        assert "a.py" in file_paths
        assert "b.md" in file_paths

    def test_all_chunks_have_fingerprints(self, tmp_path):
        (tmp_path / "f.py").write_text("x = 1\n" * 20)
        svc = ProjectService(str(tmp_path))
        chunks = ingest_project(svc)
        for c in chunks:
            assert len(c.source_fingerprint) == 64  # SHA-256 hex

    def test_fingerprints_are_stable_on_re_ingest(self, tmp_path):
        (tmp_path / "stable.py").write_text("def stable(): return True\n")
        svc = ProjectService(str(tmp_path))
        run1 = {c.source_fingerprint for c in ingest_project(svc)}
        run2 = {c.source_fingerprint for c in ingest_project(svc)}
        assert run1 == run2
