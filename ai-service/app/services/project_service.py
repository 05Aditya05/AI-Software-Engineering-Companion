"""
Project understanding service.

Provides controlled, read-only access to the project's files and
directory structure. Produces structured context summaries for use
in LLM prompts.

Security guarantees enforced by this module:
  - All access is rooted at the configured project root.
  - Path traversal outside the root is rejected.
  - .env files and known credential files are excluded.
  - node_modules, .git, .venv, dist, build, .next are excluded.
  - Binary files are skipped.
  - Individual file size is capped at MAX_FILE_BYTES.
  - Total context size is capped at MAX_CONTEXT_CHARS.
  - Maximum number of files read is capped at MAX_FILES.

This module does NOT execute shell commands or write to the filesystem.
"""

import os
from pathlib import Path


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".ts", ".tsx", ".js", ".jsx",
    ".py",
    ".json", ".md", ".txt",
    ".yaml", ".yml",
    ".css", ".html",
})

EXCLUDED_DIRS: frozenset[str] = frozenset({
    "node_modules", ".git", ".venv", "venv",
    "dist", "build", ".next", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "coverage", ".coverage",
})

# Secret / credential file names — never read
EXCLUDED_FILE_NAMES: frozenset[str] = frozenset({
    ".env", ".env.local", ".env.production", ".env.staging",
    ".env.development", ".env.test",
    "secrets.json", "credentials.json", "service-account.json",
    ".netrc", ".npmrc", ".pypirc",
    "id_rsa", "id_ed25519", "id_ecdsa",
})

MAX_FILE_BYTES: int = 64 * 1024        # 64 KB per file
MAX_FILES: int = 40                     # max files to read
MAX_CONTEXT_CHARS: int = 80_000        # max total chars in assembled context

# Files to prioritize — read these first regardless of discovery order
PRIORITY_FILE_NAMES: tuple[str, ...] = (
    "README.md", "readme.md",
    "architecture.md",
    "package.json",
    "requirements.txt", "requirements.lock",
    "pyproject.toml",
    "tsconfig.json",
    ".env.example",
)


class ProjectService:
    """
    Controlled, read-only project-understanding service.

    All methods raise ValueError for invalid / out-of-root paths.
    """

    def __init__(self, project_root: str) -> None:
        """
        Args:
            project_root: Absolute path to the project root directory.

        Raises:
            ValueError: If project_root is empty or not an existing directory.
        """
        if not project_root or not project_root.strip():
            raise ValueError("project_root must be a non-empty path.")

        resolved = Path(project_root).resolve()
        if not resolved.is_dir():
            raise ValueError(
                f"project_root does not exist or is not a directory: {project_root}"
            )
        self._root = resolved

    @property
    def root(self) -> Path:
        """Resolved project root path."""
        return self._root

    # ------------------------------------------------------------------
    # Directory discovery
    # ------------------------------------------------------------------

    def list_structure(self, max_depth: int = 4) -> list[str]:
        """
        Return a list of relative paths describing the project structure.

        Excluded directories and secret files are omitted.
        Binary files and files without allowed extensions are omitted.

        Args:
            max_depth: Maximum directory depth to traverse.

        Returns:
            Sorted list of relative path strings.
        """
        entries: list[str] = []
        self._walk(self._root, depth=0, max_depth=max_depth, entries=entries)
        return sorted(entries)

    def _walk(
        self,
        directory: Path,
        depth: int,
        max_depth: int,
        entries: list[str],
    ) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(directory.iterdir())
        except PermissionError:
            return

        for child in children:
            rel = child.relative_to(self._root)
            rel_str = rel.as_posix()

            if child.is_dir():
                if child.name in EXCLUDED_DIRS:
                    continue
                entries.append(rel_str + "/")
                self._walk(child, depth + 1, max_depth, entries)
            elif child.is_file():
                if self._is_excluded_file(child):
                    continue
                if child.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                entries.append(rel_str)

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def read_file(self, relative_path: str) -> str:
        """
        Read an allowed text file within the project root.

        Args:
            relative_path: Path relative to the project root.

        Returns:
            File contents as a string.

        Raises:
            ValueError: If the path escapes the root, is excluded, or is too large.
            FileNotFoundError: If the file does not exist.
            IsADirectoryError: If the path points to a directory.
        """
        target = self._resolve_safe(relative_path)

        if target.is_dir():
            raise IsADirectoryError(f"Path is a directory: {relative_path}")

        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        if self._is_excluded_file(target):
            raise ValueError(f"Access to file '{relative_path}' is not permitted.")

        if target.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File extension '{target.suffix}' is not in the allowed list."
            )

        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(
                f"File '{relative_path}' exceeds maximum size "
                f"({size} bytes > {MAX_FILE_BYTES} bytes)."
            )

        return target.read_text(encoding="utf-8", errors="replace")

    def get_file_metadata(self, relative_path: str) -> dict[str, object]:
        """
        Return basic metadata for a file within the project root.

        Returns:
            Dict with keys: path, size_bytes, extension, is_allowed.

        Raises:
            ValueError: If path escapes root.
        """
        target = self._resolve_safe(relative_path)
        exists = target.exists() and target.is_file()
        return {
            "path": relative_path,
            "size_bytes": target.stat().st_size if exists else None,
            "extension": target.suffix.lower() if exists else None,
            "is_allowed": (
                exists
                and not self._is_excluded_file(target)
                and target.suffix.lower() in ALLOWED_EXTENSIONS
            ),
        }

    # ------------------------------------------------------------------
    # Context construction
    # ------------------------------------------------------------------

    def build_context(self) -> str:
        """
        Assemble a structured context string from the most relevant project files.

        Prioritises files listed in PRIORITY_FILE_NAMES, then reads additional
        allowed files up to MAX_FILES and MAX_CONTEXT_CHARS limits.

        Returns:
            Multi-section context string ready for inclusion in an LLM prompt.
        """
        # 1. Discover all allowed files
        all_files = [p for p in self.list_structure() if not p.endswith("/")]

        # 2. Re-order: priority files first, then the rest
        def sort_key(rel_path: str) -> tuple[int, str]:
            name = Path(rel_path).name
            try:
                return (0, str(PRIORITY_FILE_NAMES.index(name)))
            except ValueError:
                return (1, rel_path)

        ordered = sorted(all_files, key=sort_key)

        # 3. Read files up to limits
        sections: list[str] = []
        total_chars = 0
        files_read = 0

        # Always include directory structure first
        structure = self.list_structure()
        structure_text = "## Project Structure\n\n" + "\n".join(structure)
        sections.append(structure_text)
        total_chars += len(structure_text)

        for rel_path in ordered:
            if files_read >= MAX_FILES:
                break
            if total_chars >= MAX_CONTEXT_CHARS:
                break
            try:
                content = self.read_file(rel_path)
            except (ValueError, FileNotFoundError, IsADirectoryError, OSError):
                continue

            remaining = MAX_CONTEXT_CHARS - total_chars
            if len(content) > remaining:
                content = content[:remaining] + "\n... [truncated]"

            section = f"## {rel_path}\n\n```\n{content}\n```"
            sections.append(section)
            total_chars += len(section)
            files_read += 1

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_safe(self, relative_path: str) -> Path:
        """Resolve a relative path and verify it stays within the project root.

        Raises:
            ValueError: If the resolved path escapes the project root.
        """
        # Reject obviously dangerous patterns
        if not relative_path or not relative_path.strip():
            raise ValueError("relative_path must be non-empty.")

        # Use os.path.normpath to collapse ../ sequences before resolving
        candidate = (self._root / relative_path).resolve()

        try:
            candidate.relative_to(self._root)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: '{relative_path}' escapes the project root."
            )

        return candidate

    @staticmethod
    def _is_excluded_file(path: Path) -> bool:
        """Return True if the file should never be read."""
        return path.name in EXCLUDED_FILE_NAMES or path.name.startswith(".env")
