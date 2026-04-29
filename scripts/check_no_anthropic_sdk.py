#!/usr/bin/env python3
"""CI guard — fail the build if the Anthropic SDK or shell-form
subprocess invocation reaches ``src/`` or ``pyproject.toml``.

Implements NFR-002 AC-2.2 / AC-2.3 + NFR-007 AC-7.1 / AC-7.6 for the
u2 briefing unit (and repo-wide enforcement). The Anthropic SDK is
forbidden by US-009: every LLM call must go through the Claude Code
CLI subprocess wrapper in ``src/investo/briefing/claude_code.py``.

Three source-code regexes are checked against every ``.py`` file
under ``SRC_ROOT``:

    1. ``^\\s*(from anthropic|import anthropic)``
       — direct SDK import.
    2. ``subprocess\\.(run|Popen)\\([^)]*shell\\s*=\\s*True``
       — ``shell=True`` opens command-injection risk.
    3. ``subprocess\\.(run|Popen)\\(\\s*"[^"]*"\\s*[,)]``
       — string-form first arg → likely ``shell=True`` candidate.

In addition, ``pyproject.toml`` is scanned for ``anthropic`` listed
under ``[project.dependencies]`` or ``[project.optional-dependencies]``.

The CI lint job runs this script directly. The unit test
``tests/unit/briefing/test_no_anthropic_sdk.py`` also subprocess-runs
it on the current tree and asserts a clean exit.

Usage::

    python scripts/check_no_anthropic_sdk.py

Exit codes:
    0 — clean tree
    1 — at least one offender; details printed to stderr

Style mirrors u1's ``scripts/check_no_paid_apis.py``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Source-side regex patterns. Each is matched against every line
# (case-sensitive) of every ``.py`` file under ``SRC_ROOT``. Order
# is the AC-2.2 order so error output is predictable.
SOURCE_PATTERNS: list[tuple[str, str]] = [
    ("anthropic_sdk_import", r"^\s*(from anthropic|import anthropic)"),
    ("shell_true", r"subprocess\.(run|Popen)\([^)]*shell\s*=\s*True"),
    ("string_form_subprocess", r"subprocess\.(run|Popen)\(\s*\"[^\"]*\"\s*[,)]"),
]

# Pyproject section header → flagged dep regex (case-sensitive). Both
# locations are checked because either is a real install path.
PYPROJECT_DEP_SECTIONS: tuple[str, ...] = (
    "[project.dependencies]",
    "[project.optional-dependencies]",
)
PYPROJECT_DEP_PATTERN = re.compile(r"^\s*[\"']?anthropic", re.IGNORECASE)

_REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = _REPO_ROOT / "src"
PYPROJECT = _REPO_ROOT / "pyproject.toml"


def find_source_offenders() -> list[tuple[Path, int, str, str]]:
    """Return ``(path, line_no, pattern_name, line_text)`` for every
    line under ``SRC_ROOT`` that matches a source-side pattern.

    Returns an empty list on a clean tree.
    """
    compiled = [(name, re.compile(pat)) for name, pat in SOURCE_PATTERNS]
    offenders: list[tuple[Path, int, str, str]] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, regex in compiled:
                if regex.search(line):
                    offenders.append((path, line_no, name, line.rstrip()))
    return offenders


def find_pyproject_offenders() -> list[tuple[int, str, str]]:
    """Return ``(line_no, section_header, line_text)`` for any
    ``anthropic`` dep listed under a flagged pyproject section.

    Returns ``[]`` if pyproject is missing or clean.
    """
    if not PYPROJECT.exists():
        return []
    text = PYPROJECT.read_text(encoding="utf-8")
    offenders: list[tuple[int, str, str]] = []
    current_section: str | None = None
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped
            continue
        if current_section in PYPROJECT_DEP_SECTIONS and PYPROJECT_DEP_PATTERN.search(line):
            offenders.append((line_no, current_section or "?", line.rstrip()))
    return offenders


def main() -> int:
    src_offenders = find_source_offenders()
    pyproject_offenders = find_pyproject_offenders()

    if not src_offenders and not pyproject_offenders:
        return 0

    print("Anthropic SDK / shell-subprocess violations detected:", file=sys.stderr)
    print("(NFR-002 AC-2.2 / AC-2.3 + NFR-007 AC-7.1 / AC-7.6)", file=sys.stderr)

    for path, line_no, name, line in src_offenders:
        rel = path.relative_to(_REPO_ROOT)
        print(f"  {rel}:{line_no}: [{name}] {line}", file=sys.stderr)

    for line_no, section, line in pyproject_offenders:
        rel = PYPROJECT.relative_to(_REPO_ROOT)
        print(f"  {rel}:{line_no}: anthropic dep in {section}: {line}", file=sys.stderr)

    print(
        "\nFix: route every LLM call through "
        "src/investo/briefing/claude_code.py (Claude Code CLI subprocess, "
        "list-form args, no shell=True). Remove the anthropic dependency "
        "if present.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
