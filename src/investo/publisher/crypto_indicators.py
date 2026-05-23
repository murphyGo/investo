"""Crypto-native indicator block injection (u66 Step 5, publisher side).

The pure deterministic renderer lives in
:mod:`investo.briefing.crypto_indicators` so both the Stage 2 prompt
grounding (u66 Step 7) and this publisher injection consume the same
table without inverting the publisher→briefing import direction. This
module re-exports the renderer and adds the markdown injection helper.

Placement: after the shared-macro ``## ⓪`` block (or the TL;DR block when
macro is absent) and before ``## ①``. Injection is idempotent.

Module boundary: imports only from :mod:`investo.briefing.crypto_indicators`.
Does NOT import from ``orchestrator`` / ``sources`` / ``notifier``.
"""

from __future__ import annotations

from typing import Final

from investo.briefing.crypto_indicators import (
    CRYPTO_INDICATOR_HEADER,
    render_crypto_indicator_block,
)

_TLDR_HEADER: Final[str] = "## 한눈에 보기"
_SHARED_MACRO_HEADER: Final[str] = "## ⓪ 오늘의 매크로"
_FIRST_SECTION_MARKER: Final[str] = "## ①"


def inject_crypto_indicator_block(text: str, block: str | None) -> str:
    """Insert the crypto indicator block (idempotent).

    Placed after the shared-macro ``## ⓪`` block (or the TL;DR block when
    macro is absent) and before ``## ①``. Re-injection is a no-op.
    """
    if not block:
        return text
    if CRYPTO_INDICATOR_HEADER in text:
        return text

    rendered = f"{block.strip()}\n\n"

    for anchor in (_SHARED_MACRO_HEADER, _TLDR_HEADER):
        idx = text.find(anchor)
        if idx != -1:
            scan_from = idx + len(anchor)
            next_h2 = text.find("\n## ", scan_from)
            if next_h2 != -1:
                insertion = next_h2 + 1
                return text[:insertion] + rendered + text[insertion:]

    first_section = text.find(_FIRST_SECTION_MARKER)
    if first_section != -1:
        return text[:first_section] + rendered + text[first_section:]

    return f"{text.rstrip()}\n\n{rendered}"


__all__ = [
    "CRYPTO_INDICATOR_HEADER",
    "inject_crypto_indicator_block",
    "render_crypto_indicator_block",
]
