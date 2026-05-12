"""Shared-macro ``## ⓪`` block injection (u57 Step 5).

When :class:`BundleContext.shared_macro_block` is non-null the
publisher injects a ``## ⓪ 오늘의 매크로`` H2 block immediately *after*
the u51 TL;DR block (``## 한눈에 보기``) so the layout reads:

    > **오늘의 결론** : ...
    > **핵심 동인** : ...
    > **주의할 점** : ...

    ## 한눈에 보기
    ...

    ## ⓪ 오늘의 매크로
    - **국제 유가** — Brent 79$ 부근
    - **미 국채 수익률** — UST10Y 4.42%

    ## ① 요약
    ...

When TL;DR is absent the block is injected immediately before
``## ①``. When neither anchor exists the block is appended to the end
(degenerate input — caller's downstream verifier surfaces structural
problems).

Idempotent: re-running over text that already contains
``## ⓪ 오늘의 매크로`` returns it unchanged.

References
----------

* u57 plan Step 5 — shared macro dedupe block.
"""

from __future__ import annotations

import logging
from typing import Final

_logger = logging.getLogger(__name__)

SHARED_MACRO_HEADER: Final[str] = "## ⓪ 오늘의 매크로"
_TLDR_HEADER: Final[str] = "## 한눈에 보기"
_FIRST_SECTION_MARKER: Final[str] = "## ①"


def inject_shared_macro_block(
    text: str,
    block: str | None,
    *,
    segment: str | None = None,
) -> str:
    """Insert a ``## ⓪`` H2 + ``block`` body if absent.

    ``block`` is the rendered body (multi-line markdown — typically a
    bullet list); ``None`` short-circuits with the text unchanged.
    """
    if not block:
        return text
    if SHARED_MACRO_HEADER in text:
        return text

    rendered = f"{SHARED_MACRO_HEADER}\n\n{block.strip()}\n\n"

    # Prefer TL;DR-end as the insertion site.
    tldr_idx = text.find(_TLDR_HEADER)
    if tldr_idx != -1:
        # Find the end of the TL;DR block: the next ``## `` heading.
        scan_from = tldr_idx + len(_TLDR_HEADER)
        next_h2 = text.find("\n## ", scan_from)
        if next_h2 != -1:
            insertion = next_h2 + 1  # before the ``##`` itself
            _logger.info(
                "shared_macro.injected",
                extra={"segment": segment, "site": "after_tldr"},
            )
            return text[:insertion] + rendered + text[insertion:]

    # Fallback: just before ``## ①``.
    first_section = text.find(_FIRST_SECTION_MARKER)
    if first_section != -1:
        _logger.info(
            "shared_macro.injected",
            extra={"segment": segment, "site": "before_section_one"},
        )
        return text[:first_section] + rendered + text[first_section:]

    # Final fallback — append.
    _logger.warning(
        "shared_macro.injected",
        extra={"segment": segment, "site": "appended"},
    )
    return f"{text.rstrip()}\n\n{rendered}"


__all__ = ["SHARED_MACRO_HEADER", "inject_shared_macro_block"]
