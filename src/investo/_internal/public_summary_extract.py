"""Pure cleanup shared by public-document sealing and notifier adapters."""

from __future__ import annotations

import re
from typing import Final

from investo._internal.public_quality_language import project_public_quality_language

_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`~]+")
_LEADING_MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:>\s*)?(?:#{1,6}\s*)?(?:(?:[-*+])|\d+[.)])\s*"
)
_MEANINGFUL_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")


def clean_public_summary_text(text: str) -> str:
    """Return one public-safe meaningful line extracted from Markdown."""

    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = _LEADING_MARKDOWN_RE.sub("", cleaned).strip()
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _MARKDOWN_TOKEN_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    cleaned = project_public_quality_language(cleaned)
    if not _MEANINGFUL_TEXT_RE.search(cleaned):
        return ""
    return cleaned


__all__ = ["clean_public_summary_text"]
