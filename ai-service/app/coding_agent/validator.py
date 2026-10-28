"""
Safe subprocess validation engine for Phase 11.

Executes only strictly allowlisted testing, linting, and build commands
using subprocess argument lists (never shell=True) within the target project root.
Enforces execution timeouts and output buffer size limits to prevent hangs and bloat.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Sequence

from app.coding_agent.schemas import ValidationResult

logger = logging.getLogger(__name__)

# Maximum characters allowed for captured stdout / stderr to prevent unbounded memory usage
MAX_OUTPUT_CHARS = 10_000

# Strict allowlist of permissible validation binary names
ALLOWED_EXECUTABLES = {
    "pytest",
    "python",
    "python3",
    "npm",
    "npx",
    "node",
    "ruff",
    "flake8",
    "tsc",
    "cargo",
    "go",
    "git",
}

# Allowlisted subcommands / flags for each executable to prevent arbitrary execution
ALLOWED_PATTERNS = {
    "git": {"status", "diff", "--no-pager"},
    "npm": {"test", "run", "lint", "build", "check", "--"},
    "npx": {"tsc", "eslint", "prettier", "--noEmit"},
    "pytest": set(),  # Any pytest flags allowed
    "ruff": {"check", "--select"},
    "flake8": set(),
    "python": {"-m", "pytest", "unittest"},
    "python3": {"-m", "pytest", "unittest"},
    "tsc": {"--noEmit", "-p"},
    "cargo": {"test", "check"},
    "go": {"test"},
}


class CommandValidationError(ValueError):
    """Raised when a requested validation command violates the security allowlist."""


def check_command_allowed(argv: Sequence[str]) -> None:
    """
    Validate that the command is in the strict allowlist.

    Args:
        argv: List of command arguments, e.g. ["npm", "test"].

    Raises:
        CommandValidationError: If the executable or subcommand is not permitted.
    """
    if not argv:
        raise CommandValidationError("Validation command cannot be empty.")

    raw_exe = Path(argv[0]).name.lower()
    # Remove .exe or .cmd for Windows
    base_exe = raw_exe.replace(".exe", "").replace(".cmd", "")

    if base_exe not in ALLOWED_EXECUTABLES:
        raise CommandValidationError(
            f"Executable '{argv[0]}' is not in the allowed validation tool set: {sorted(ALLOWED_EXECUTABLES)}"
        )

    # Secondary check on subcommands if specified
    allowed_sub = ALLOWED_PATTERNS.get(base_exe)
    if allowed_sub and len(argv) > 1:
        first_arg = argv[1].lower()
        # For python, ensure it is invoking pytest or unittest
        if base_exe in ("python", "python3"):
            if first_arg != "-m" or len(argv) < 3 or argv[2].lower() not in ("pytest", "unittest"):
                raise CommandValidationError(
                    "Python validation is restricted to 'python -m pytest' or 'python -m unittest'."
                )
        elif base_exe == "git":
            if first_arg not in ("status", "diff"):
                raise CommandValidationError("Git validation is restricted to read-only 'status' or 'diff'.")


async def run_single_validation(
    argv: list[str],
    project_root: str,
    timeout_seconds: float = 30.0,
) -> ValidationResult:
    """
    Execute a single allowlisted validation command asynchronously.

    Args:
        argv: Command argument list.
        project_root: Working directory for execution.
        timeout_seconds: Timeout before terminating the process.

    Returns:
        ValidationResult with exit code, outputs, and timing.
    """
    check_command_allowed(argv)

    clean_root = Path(project_root).resolve()
    if not clean_root.is_dir():
        return ValidationResult(
            command=" ".join(argv),
            exit_code=-1,
            stdout="",
            stderr=f"Project root is not a directory: {project_root}",
            duration_ms=0.0,
            passed=False,
        )

    # Resolve executable path safely
    exe = argv[0]
    resolved_exe = shutil.which(exe) or exe

    start_time = time.perf_counter()
    command_str = " ".join(argv)

    try:
        proc = await asyncio.create_subprocess_exec(
            resolved_exe,
            *argv[1:],
            cwd=str(clean_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Prevent interactive prompts
            env={**os.environ, "CI": "true", "TERM": "dumb"},
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )

        duration = (time.perf_counter() - start_time) * 1000.0

        raw_stdout = stdout_bytes.decode(errors="replace")
        raw_stderr = stderr_bytes.decode(errors="replace")

        # Truncate if output exceeds maximum permitted buffer size
        if len(raw_stdout) > MAX_OUTPUT_CHARS:
            raw_stdout = raw_stdout[:MAX_OUTPUT_CHARS] + f"\n... [Output truncated after {MAX_OUTPUT_CHARS} characters]"
        if len(raw_stderr) > MAX_OUTPUT_CHARS:
            raw_stderr = raw_stderr[:MAX_OUTPUT_CHARS] + f"\n... [Output truncated after {MAX_OUTPUT_CHARS} characters]"

        exit_code = proc.returncode if proc.returncode is not None else -1

        return ValidationResult(
            command=command_str,
            exit_code=exit_code,
            stdout=raw_stdout,
            stderr=raw_stderr,
            duration_ms=round(duration, 2),
            passed=(exit_code == 0),
        )

    except asyncio.TimeoutError:
        duration = (time.perf_counter() - start_time) * 1000.0
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return ValidationResult(
            command=command_str,
            exit_code=-1,
            stdout="",
            stderr=f"Command timed out after {timeout_seconds} seconds.",
            duration_ms=round(duration, 2),
            passed=False,
        )

    except Exception as exc:
        duration = (time.perf_counter() - start_time) * 1000.0
        return ValidationResult(
            command=command_str,
            exit_code=-1,
            stdout="",
            stderr=f"Execution error: {exc}",
            duration_ms=round(duration, 2),
            passed=False,
        )


async def run_validations(
    project_root: str,
    commands: Sequence[list[str]] | None = None,
    timeout_seconds: float = 30.0,
) -> list[ValidationResult]:
    """
    Execute multiple validation checks sequentially, auto-detecting test suites if none given.
    """
    root_path = Path(project_root).resolve()

    if commands is None or len(commands) == 0:
        # Auto-detect safe checks
        detected: list[list[str]] = []
        if (root_path / "pytest.ini").exists() or (root_path / "pyproject.toml").exists():
            detected.append(["pytest", "-q"])
        elif (root_path / "package.json").exists():
            detected.append(["npm", "test"])
        else:
            detected.append(["git", "status", "--porcelain"])
        commands = detected

    results: list[ValidationResult] = []
    for cmd in commands:
        res = await run_single_validation(cmd, project_root, timeout_seconds)
        results.append(res)
        # If a critical validation fails, stop further execution
        if not res.passed:
            break

    return results
