"""Pins NFR-007 AC-7.6 — XML parsing must use ``defusedxml``.

This is a static guard: a regex sweep over every Python file under
``src/investo/sources/`` rejects direct imports of stdlib
``xml.etree.ElementTree`` or related stdlib XML parsers. Adapters that
parse XML must import from ``defusedxml`` instead (which transparently
re-uses stdlib types like :class:`Element` but routes parsing through
the safe entry points).
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SOURCES_ROOT = _REPO_ROOT / "src" / "investo" / "sources"

# Match top-of-line `import xml.…` / `from xml.… import` for every
# stdlib XML parser surface that bypasses defusedxml's safe entry
# points: `xml.etree.{ElementTree,cElementTree}`, `xml.dom.*`,
# `xml.sax.*`, `xml.parsers.expat`. `defusedxml.…` legitimately
# wraps these and does NOT match (different top-level prefix).
_FORBIDDEN = re.compile(
    r"^\s*(?:from|import)\s+xml\.(?:etree|dom|sax|parsers)\b",
    re.MULTILINE,
)
_DEFUSEDXML_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+defusedxml\b",
    re.MULTILINE,
)


def test_no_stdlib_xml_imports_in_sources() -> None:
    offenders: list[Path] = []
    for path in _SOURCES_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _FORBIDDEN.search(text):
            offenders.append(path.relative_to(_REPO_ROOT))
    assert not offenders, (
        f"forbidden stdlib XML imports in: {offenders}. "
        "Use defusedxml.ElementTree per NFR-007 AC-7.6."
    )


def test_fomc_rss_uses_defusedxml() -> None:
    # Sanity-check the inverse: the FOMC adapter (Step 8) DOES import
    # from defusedxml as a top-level statement (not just as a string
    # in a comment). If a future refactor accidentally drops the
    # import, this fails loudly.
    fomc_rss = _SOURCES_ROOT / "fomc_rss.py"
    text = fomc_rss.read_text(encoding="utf-8")
    assert _DEFUSEDXML_IMPORT.search(text), (
        "fomc_rss.py must import defusedxml as a top-level import statement (NFR-007 AC-7.6)."
    )
