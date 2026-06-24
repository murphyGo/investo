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
import tomllib
from pathlib import Path

# Source-side regex patterns. Each is matched against every line
# (case-sensitive) of every ``.py`` file under ``SRC_ROOT``. Order
# is the AC-2.2 order so error output is predictable.
SOURCE_PATTERNS: list[tuple[str, str]] = [
    ("anthropic_sdk_import", r"^\s*(from anthropic|import anthropic)"),
    ("shell_true", r"subprocess\.(run|Popen)\([^)]*shell\s*=\s*True"),
    ("string_form_subprocess", r"subprocess\.(run|Popen)\(\s*\"[^\"]*\"\s*[,)]"),
]

_REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = _REPO_ROOT / "src"
PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _dependency_name(requirement: str) -> str:
    """Return the normalized package name before extras/version/markers."""
    head = requirement.split(";", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9_.-]+)", head)
    if match is None:
        return ""
    return match.group(1).replace("_", "-").lower()


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
    """Return ``(index, dependency_group, requirement)`` for Anthropic deps.

    The parser follows PEP 621: ``[project] dependencies = [...]`` and every
    ``[project.optional-dependencies]`` group. Malformed TOML fails closed by
    returning a synthetic offender.
    """
    if not PYPROJECT.exists():
        return []
    try:
        payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return [(0, "pyproject.toml", f"malformed TOML: {exc}")]

    offenders: list[tuple[int, str, str]] = []
    project = payload.get("project", {})
    dependencies = project.get("dependencies", [])
    if isinstance(dependencies, list):
        for index, requirement in enumerate(dependencies):
            if isinstance(requirement, str) and _dependency_name(requirement) == "anthropic":
                offenders.append((index, "project.dependencies", requirement))
    else:
        offenders.append((0, "project.dependencies", "dependencies must be an array"))

    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group, requirements in optional.items():
            if not isinstance(requirements, list):
                offenders.append(
                    (0, f"project.optional-dependencies.{group}", "group must be an array")
                )
                continue
            for index, requirement in enumerate(requirements):
                if isinstance(requirement, str) and _dependency_name(requirement) == "anthropic":
                    offenders.append((index, f"project.optional-dependencies.{group}", requirement))
    else:
        offenders.append(
            (0, "project.optional-dependencies", "optional-dependencies must be a table")
        )
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
