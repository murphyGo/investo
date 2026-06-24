#!/usr/bin/env python3
"""CI cost guard — fail the build on paid-API references in `sources/`.

Implements NFR-002 AC-2.2: a CI grep guard, executed by the lint job
(or by ``tests/unit/sources/test_no_paid_apis.py`` as a subprocess
during ``pytest``), fails the build if any source file under
``src/investo/sources/`` matches a known-paid-API pattern.

The blocklist below is intentionally narrow: it catches paid-first market data
providers and provider-specific SDK/env-var references, but does not block broad
terms such as ``API_KEY`` because the repo intentionally uses free/public keys
for official providers.

Usage::

    python scripts/check_no_paid_apis.py

Exit codes:
    0 — no paid-API references found
    1 — at least one offender; details printed to stderr
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns are matched case-insensitively against every line of
# every ``.py`` file under ``SOURCES_ROOT``. Each entry should be a
# regex string (not a compiled pattern) so this list stays readable.
#
BLOCKLIST: list[str] = [
    r"\bblpapi\b",
    r"\bbloomberg(?:professional|terminal)?\.com\b",
    r"\bBLOOMBERG_[A-Z0-9_]*",
    r"\brefinitiv\b",
    r"\beikon\b",
    r"\bREFINITIV_[A-Z0-9_]*",
    r"\bEIKON_[A-Z0-9_]*",
    r"\bfactset\b",
    r"\bFACTSET_[A-Z0-9_]*",
    r"\bcapitaliq\b",
    r"\bcapital\s+iq\b",
    r"\bCAPITALIQ_[A-Z0-9_]*",
    r"\bmorningstar\s+direct\b",
    r"\bMORNINGSTAR_DIRECT_[A-Z0-9_]*",
    r"\bnasdaq\s+data\s+link\b",
    r"\bquandl\b",
    r"\bNASDAQ_DATA_LINK_[A-Z0-9_]*",
    r"\bQUANDL_[A-Z0-9_]*",
]

SOURCES_ROOT = Path(__file__).resolve().parent.parent / "src" / "investo" / "sources"


def find_offenders() -> list[tuple[Path, int, str, str]]:
    """Return ``(path, line_no, pattern, line_text)`` for every match.

    Returns an empty list when no source file matches.
    """
    compiled = [(re.compile(p, re.IGNORECASE), p) for p in BLOCKLIST]
    offenders: list[tuple[Path, int, str, str]] = []
    for path in sorted(SOURCES_ROOT.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for regex, pattern in compiled:
                if regex.search(line):
                    offenders.append((path, line_no, pattern, line.rstrip()))
    return offenders


def main() -> int:
    offenders = find_offenders()
    if not offenders:
        return 0
    repo_root = SOURCES_ROOT.parent.parent.parent
    print("Paid-API references detected (NFR-002 AC-2.2):", file=sys.stderr)
    for path, line_no, pattern, line in offenders:
        rel = path.relative_to(repo_root)
        print(f"  {rel}:{line_no}: matched {pattern!r}: {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
