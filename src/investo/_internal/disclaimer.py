"""Canonical disclaimer text and pure helpers.

The compatibility module ``investo.briefing.disclaimer`` re-exports this
contract, but publisher-side gates depend on this inward owner directly.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from investo.models.segments import MarketSegment

DISCLAIMER: Final[str] = (
    "## ⑦ 면책조항\n"
    "본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,\n"
    "특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다.\n"
    "투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,\n"
    "본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다."
)

DISCLAIMER_CRYPTO: Final[str] = (
    "## ⑦ 면책조항\n"
    "본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,\n"
    "특정 가상자산에 대한 매매 권유나 투자 자문이 아닙니다.\n"
    "가상자산은 가상자산이용자보호법(2024-07-19 시행) §10·§19의 적용 대상으로,\n"
    "24시간 거래되는 비제도권 자산이며 가격 변동성이 매우 크고 원금 전액 손실이 가능합니다.\n"
    "투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,\n"
    "본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다."
)

COMPLIANCE_CUTOFF_DATE: Final[date] = date(2026, 5, 13)
_ANCHOR: Final[str] = "## ⑦ 면책조항"


def _disclaimer_for(segment: MarketSegment | None) -> str:
    if segment == "crypto":
        return DISCLAIMER_CRYPTO
    return DISCLAIMER


def append_disclaimer(markdown: str, segment: MarketSegment | None = None) -> str:
    """Append the segment-appropriate disclaimer if the anchor is absent."""
    if _ANCHOR in markdown:
        return markdown
    return markdown + "\n\n" + _disclaimer_for(segment)


def ensure_canonical_disclaimer(markdown: str, segment: MarketSegment | None = None) -> str:
    """Return ``markdown`` with an anchor-present footer made canonical."""
    anchor_idx = markdown.find(_ANCHOR)
    if anchor_idx == -1:
        return markdown

    footer = _disclaimer_for(segment)
    if footer in markdown[anchor_idx:]:
        return markdown

    prefix = markdown[:anchor_idx].rstrip()
    suffix = "\n" if markdown.endswith("\n") else ""
    return f"{prefix}\n\n{footer}{suffix}"


__all__ = [
    "COMPLIANCE_CUTOFF_DATE",
    "DISCLAIMER",
    "DISCLAIMER_CRYPTO",
    "append_disclaimer",
    "ensure_canonical_disclaimer",
]
