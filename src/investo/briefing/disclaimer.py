"""Disclaimer constants + idempotent appender (NFR-004, FR-002 compliance).

Per FD R5 (`u2-briefing/functional-design/business-rules.md`), the
canonical us-equity / domestic-equity disclaimer text is fixed as the
module-level ``DISCLAIMER`` constant. ``append_disclaimer`` is
idempotent — anchored on the literal section header ``## ⑦ 면책조항``.
The complementary check lives in u3 publisher:
``publisher.verify_disclaimer`` does an exact-substring match on the
full segment-appropriate disclaimer constant immediately before publish
(NFR-004 defense-in-depth).

u56 — crypto segment now carries its own disclaimer
(``DISCLAIMER_CRYPTO``) with a 가상자산이용자보호법 (2024-07-19 시행) §10
/ §19 reference: "24시간 거래 / 비제도권 자산 / 가격 변동성 매우 큼 /
원금 전액 손실 가능" 명시. ``append_disclaimer(markdown, segment)``
selects between the two; the equity variant remains byte-identical to
its pre-u56 text so existing archive files do not need rewriting.

Why anchor on the header (not the full body): FD R5 deliberately allows
the body wording to drift via future ADR while keeping the section
header as the canonical idempotence detect. The pathological case
(input already contains the anchor but with wrong body text — e.g. a
hallucinated LLM section ⑦) is caught by u3's stricter
``verify_disclaimer`` check, which blocks publish on drift.

Archive backward-compat (legacy=True flag on ``verify_disclaimer``):
files written before 2026-05-13 carry the equity disclaimer regardless
of segment. The weekly-digest / monthly-index re-readers pass
``legacy=True`` so cutoff-old crypto archives still verify against the
equity text. DEBT-001 tracks moving the substring guarantee one layer
earlier into the ``Briefing`` model itself.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from investo.briefing.segments import MarketSegment

# Exact text per FD R5. This MUST stay byte-identical with what u3's
# ``verify_disclaimer`` substring-checks for non-crypto segments. Any
# wording change is an audit-logged event (per NFR drift AC-D.4).
DISCLAIMER: Final[str] = (
    "## ⑦ 면책조항\n"
    "본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,\n"
    "특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다.\n"
    "투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,\n"
    "본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다."
)

# u56 — crypto-segment disclaimer with the 가상자산이용자보호법 reference.
# The text deliberately repeats the equity footer's risk-warning shape
# (자료 성격 + 매매 권유 부정 + 본인 책임 + 작성자 면책) so the legal
# scaffolding is identical; the differentiation is the §10 / §19
# reference plus the asset-class-specific risk callout (24시간 거래 /
# 가격 변동성 매우 큼 / 원금 전액 손실).
DISCLAIMER_CRYPTO: Final[str] = (
    "## ⑦ 면책조항\n"
    "본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,\n"
    "특정 가상자산에 대한 매매 권유나 투자 자문이 아닙니다.\n"
    "가상자산은 가상자산이용자보호법(2024-07-19 시행) §10·§19의 적용 대상으로,\n"
    "24시간 거래되는 비제도권 자산이며 가격 변동성이 매우 크고 원금 전액 손실이 가능합니다.\n"
    "투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,\n"
    "본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다."
)

# u56 — date the segment-aware disclaimer pipeline went live. Archive
# files with a date earlier than this cutoff carry the equity footer
# even for crypto segments; ``verify_disclaimer(..., legacy=True)``
# accepts that historical shape.
COMPLIANCE_CUTOFF_DATE: Final[date] = date(2026, 5, 13)

# The idempotence anchor. Body wording inside the disclaimer constants
# may drift via future ADR; this header is the canonical detect.
_ANCHOR: Final[str] = "## ⑦ 면책조항"


def _disclaimer_for(segment: MarketSegment | None) -> str:
    if segment == "crypto":
        return DISCLAIMER_CRYPTO
    return DISCLAIMER


def append_disclaimer(markdown: str, segment: MarketSegment | None = None) -> str:
    """Append the segment-appropriate disclaimer to ``markdown`` if not
    already present.

    Idempotence is anchored on the literal substring ``## ⑦ 면책조항``.
    When the anchor is present, the input is returned unchanged. When
    absent, ``\\n\\n`` plus the full segment-appropriate disclaimer
    block is appended.

    ``segment=None`` defaults to the equity footer — the historic
    behaviour for non-segmented unit tests.

    The two-newline separator guarantees the disclaimer header is
    rendered as a top-level markdown section even when the input ends
    without a trailing newline.

    The function is pure: same input → same output, no mutation, no
    timestamp, no per-call variation.
    """
    if _ANCHOR in markdown:
        return markdown
    return markdown + "\n\n" + _disclaimer_for(segment)


__all__ = [
    "COMPLIANCE_CUTOFF_DATE",
    "DISCLAIMER",
    "DISCLAIMER_CRYPTO",
    "append_disclaimer",
]
