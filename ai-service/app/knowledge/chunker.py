"""
Chunker and ingestion pipeline (Phase 9.3).

Discovers eligible project files through the existing ProjectService
security boundary, reads them safely, and splits content into
overlapping line-based chunks with deterministic metadata.

Design parameters (documented in knowledge.md §12.3):
  - CHUNK_SIZE_CHARS: target chunk size in characters (~2000–4000)
  - OVERLAP_CHARS: overlap between consecutive chunks (~10–15%)
  - MAX_FILE_BYTES: inherited from ProjectService (64 KB)
  - MAX_FILES: inherited from ProjectService (40)

Security guarantees (delegated to ProjectService):
  - Path traversal rejected.
  - Symlink targets outside project root rejected.
  - .env / secret / credential files never read.
  - Binaries and unsupported extensions skipped.
  - node_modules, .git, .venv, build outputs excluded.
  - No shell execution during indexing.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from app.services.project_service import (
    ALLOWED_EXTENSIONS,
    EXCLUDED_DIRS,
    MAX_FILE_BYTES,
    ProjectService,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunking configuration
# ---------------------------------------------------------------------------

# Target chunk size in characters.  Matches ~500–1 000 tokens at ~4 char/token.
CHUNK_SIZE_CHARS: int = 1_500

# Overlap between consecutive chunks.  ~10 % of chunk size keeps context intact.
OVERLAP_CHARS: int = 150

# Hard cap on files to walk (prevents OOM on huge monorepos).
MAX_INDEXABLE_FILES: int = 200


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FileChunk:
    """
    A single chunk produced by the chunker.

    Attributes:
        file_path:         Normalized POSIX relative path from project root.
        content:           Raw text content of the chunk.
        chunk_index:       Zero-based position of this chunk within the file.
        line_start:        1-based line number of the first line in the chunk.
        line_end:          1-based line number of the last line in the chunk.
        source_fingerprint: SHA-256 hex digest of the chunk *content*.
    """

    file_path: str
    content: str
    chunk_index: int
    line_start: int
    line_end: int
    source_fingerprint: str


# ---------------------------------------------------------------------------
# Core chunking logic
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of *text* encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_content(raw: str) -> str:
    """
    Normalize line endings to LF and strip a trailing newline.

    Handles CRLF (Windows), CR (old Mac), and LF (Unix) uniformly so
    that fingerprints are stable across platforms.
    """
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def chunk_text(
    text: str,
    file_path: str,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = OVERLAP_CHARS,
) -> list[FileChunk]:
    """
    Split *text* into overlapping line-based chunks.

    Lines are grouped until the chunk reaches *chunk_size* characters.
    The next chunk starts *overlap* characters before the end of the
    previous one to preserve context across boundaries.

    Args:
        text:       Normalized file text (LF line endings).
        file_path:  Relative POSIX path used for metadata.
        chunk_size: Target maximum size of each chunk in characters.
        overlap:    Approximate character overlap between adjacent chunks.

    Returns:
        List of FileChunk instances.  Empty files produce an empty list.
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    chunks: list[FileChunk] = []
    chunk_index = 0
    i = 0  # current line index

    while i < len(lines):
        # Accumulate lines into a chunk
        chunk_lines: list[str] = []
        chunk_chars = 0
        start_line_idx = i

        while i < len(lines):
            line = lines[i]
            chunk_lines.append(line)
            chunk_chars += len(line)
            i += 1
            if chunk_chars >= chunk_size:
                break

        content = "".join(chunk_lines).rstrip("\n")
        if not content.strip():
            # Skip empty or whitespace-only chunks
            continue

        line_start = start_line_idx + 1  # 1-based
        line_end = start_line_idx + len(chunk_lines)  # 1-based

        chunks.append(
            FileChunk(
                file_path=file_path,
                content=content,
                chunk_index=chunk_index,
                line_start=line_start,
                line_end=line_end,
                source_fingerprint=_sha256(content),
            )
        )
        chunk_index += 1

        # Apply overlap: step back by *overlap* characters
        if overlap > 0 and i < len(lines):
            stepped_back = 0
            while i > start_line_idx + 1 and stepped_back < overlap:
                i -= 1
                stepped_back += len(lines[i])

    return chunks


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _is_safe_path(path: Path, root: Path) -> bool:
    """
    Reject path traversal and symlink targets outside the project root.

    Returns False if the resolved path escapes *root*.
    """
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
        return True
    except (ValueError, OSError):
        return False


def discover_eligible_files(service: ProjectService) -> list[Path]:
    """
    Walk the project root and return absolute paths of indexable files.

    Uses the same exclusion rules as ProjectService:
      - EXCLUDED_DIRS are never entered.
      - Secret / credential filenames are skipped.
      - Only ALLOWED_EXTENSIONS are returned.
      - Files exceeding MAX_FILE_BYTES are skipped.
      - Symlinks whose targets escape the root are rejected.
      - At most MAX_INDEXABLE_FILES files are returned.

    Args:
        service: Initialized ProjectService (provides root + helpers).

    Returns:
        Sorted list of absolute Path objects.
    """
    root = service.root
    eligible: list[Path] = []

    def _walk(directory: Path) -> None:
        if len(eligible) >= MAX_INDEXABLE_FILES:
            return
        try:
            children = sorted(directory.iterdir())
        except (PermissionError, OSError) as exc:
            logger.debug("Cannot iterate %s: %s", directory, exc)
            return

        for child in children:
            if len(eligible) >= MAX_INDEXABLE_FILES:
                return

            # Reject symlinks whose target escapes the project root
            if child.is_symlink() and not _is_safe_path(child, root):
                logger.debug("Rejecting out-of-root symlink: %s", child)
                continue

            if child.is_dir():
                if child.name in EXCLUDED_DIRS:
                    continue
                _walk(child)
            elif child.is_file():
                if service.is_excluded_file(child):
                    continue
                if child.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                try:
                    if child.stat().st_size > MAX_FILE_BYTES:
                        logger.debug("Skipping oversized file: %s", child)
                        continue
                    if child.stat().st_size == 0:
                        logger.debug("Skipping empty file: %s", child)
                        continue
                except OSError:
                    continue
                eligible.append(child)

    _walk(root)
    return sorted(eligible)


# ---------------------------------------------------------------------------
# High-level ingestion
# ---------------------------------------------------------------------------


def read_and_chunk_file(
    abs_path: Path,
    project_root: Path,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = OVERLAP_CHARS,
) -> list[FileChunk]:
    """
    Read a single file and return its chunks.

    Handles Unicode, CRLF line endings, and unsupported encodings
    gracefully (falls back to 'replace' error mode so indexing
    continues even for partially invalid files).

    Args:
        abs_path:     Absolute path to the file (already validated by caller).
        project_root: Resolved project root for relative-path computation.
        chunk_size:   Target chunk size in characters.
        overlap:      Character overlap between chunks.

    Returns:
        List of FileChunk instances (empty if the file cannot be read
        or produces no meaningful content).
    """
    try:
        raw = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", abs_path, exc)
        return []

    text = _normalize_content(raw)
    rel_path = abs_path.relative_to(project_root).as_posix()
    return chunk_text(text, rel_path, chunk_size=chunk_size, overlap=overlap)


def ingest_project(
    service: ProjectService,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = OVERLAP_CHARS,
) -> list[FileChunk]:
    """
    Discover and chunk all eligible files in the project.

    Args:
        service:    Initialized ProjectService.
        chunk_size: Target chunk size in characters.
        overlap:    Character overlap between chunks.

    Returns:
        Flat list of FileChunk instances across all eligible files.
    """
    files = discover_eligible_files(service)
    all_chunks: list[FileChunk] = []

    for abs_path in files:
        chunks = read_and_chunk_file(abs_path, service.root, chunk_size, overlap)
        all_chunks.extend(chunks)

    logger.info(
        "Ingested %d chunks from %d files under %s",
        len(all_chunks),
        len(files),
        service.root,
    )
    return all_chunks
