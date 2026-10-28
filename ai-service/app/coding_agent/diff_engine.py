"""
Unified diff generator and canonical hashing engine (Phase 11).

Provides clean unified diff generation using Python's standard `difflib`,
and deterministic SHA-256 fingerprinting for tamper-evident proposals.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from typing import Sequence

from app.coding_agent.schemas import FileChange


def generate_unified_diff(
    relative_path: str,
    original_content: str | None,
    proposed_content: str | None,
) -> str:
    """
    Generate standard unified diff format for a file change.

    Args:
        relative_path: Clean relative path of the target file (POSIX separators).
        original_content: Existing content before modification, or None if new file.
        proposed_content: Proposed content, or None if file is being deleted.

    Returns:
        Unified diff string with standard diff headers.
    """
    clean_path = relative_path.replace("\\", "/")

    if original_content is None and proposed_content is None:
        return ""

    if original_content is None:
        # File creation: from /dev/null to b/<path>
        from_file = "/dev/null"
        to_file = f"b/{clean_path}"
        from_lines: list[str] = []
        to_lines = proposed_content.splitlines(keepends=True) if proposed_content else []
    elif proposed_content is None:
        # File deletion: from a/<path> to /dev/null
        from_file = f"a/{clean_path}"
        to_file = "/dev/null"
        from_lines = original_content.splitlines(keepends=True) if original_content else []
        to_lines = []
    else:
        # File modification
        from_file = f"a/{clean_path}"
        to_file = f"b/{clean_path}"
        from_lines = original_content.splitlines(keepends=True)
        to_lines = proposed_content.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            from_lines,
            to_lines,
            fromfile=from_file,
            tofile=to_file,
            lineterm="\n",
        )
    )

    if not diff_lines:
        return ""

    return "".join(diff_lines)


def compute_proposal_hash(
    project_root: str,
    changes: Sequence[FileChange],
) -> str:
    """
    Compute a deterministic SHA-256 fingerprint of a proposal.

    The hash covers the normalized project root and a canonically sorted,
    JSON-encoded representation of every change (path, action, proposed_content).
    Any tampering or post-proposal modification alters this hash.
    """
    norm_root = project_root.strip().replace("\\", "/").rstrip("/").lower()

    canonical_items = []
    for c in sorted(changes, key=lambda x: x.path):
        canonical_items.append({
            "action": c.action,
            "path": c.path.replace("\\", "/"),
            "proposed_content": c.proposed_content if c.proposed_content is not None else "",
        })

    payload = {
        "project_root": norm_root,
        "changes": canonical_items,
    }

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
