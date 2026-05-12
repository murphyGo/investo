"""u56 — single source of truth for the compliance-language phrase
catalogue.

Located under ``models/`` so both the briefing prompt and the publisher
gate can import the same data without violating the
``orchestrator-only-cross-imports`` module-boundary rule (Rule 3): a
``models/`` import is allowed from every unit because models is a pure
data layer.

Three P0 categories, one P1 category:

1. ``BANNED_P0_ACTION`` — symmetric buy/sell action verbs (``매수 검토 /
   매도 검토 / 비중 축소 / 비중 확대 / 편입 / 차익실현 / 익절 / 손절 /
   손절매 / 리밸런싱 / 진입 / 청산 / 목표가 / 평단가 / 추격매수 /
   물타기``). Korean capital-markets law (자본시장법 §17) treats
   directional buy/sell instructions as implicit investment
   recommendation language.
2. ``BANNED_P0_CERTAINTY`` — language asserting outcome certainty
   (``반드시 / 확실 / 보장 / 급등 예상 / 급락 임박 / 불가피 / 필연``).
3. ``BANNED_P0_QUANTIFIED_OUTCOME`` — regex catalogue for
   numeric-outcome promises (``\\d+% (이상 )?수익 예상`` style,
   ``\\d+배 수익`` style).
4. ``BANNED_P0_CRYPTO_ONLY`` — retail-coded crypto terms
   (``세력 / 김프 진입 / 상폐 임박 / 에어드랍 확정 / 펌핑``). Triggered
   only when ``segment == "crypto"`` per 가상자산이용자보호법 §10
   disorderly-market reference.
5. ``WARN_P1`` — closed-causation phrases that read as deterministic
   forecasting (``직접 반영된다`` / ``작용할 전망``) plus a small regex
   catalog for "주가/지수/가격이 X 때문에 Y했다" style closed-loop
   prose. WARN-only (non-blocking).

The lists are tuples — frozen at import time. New additions are
audit-logged events (cf. u56 plan §3, NFR drift AC-D.4).
"""

from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# P0 — block at publish boundary
# ---------------------------------------------------------------------------

BANNED_P0_ACTION: Final[tuple[str, ...]] = (
    "매수 검토",
    "매도 검토",
    "비중 축소",
    "비중 확대",
    "편입",
    "차익실현",
    "익절",
    "손절",
    "손절매",
    "리밸런싱",
    "진입",
    "청산",
    "목표가",
    "평단가",
    "추격매수",
    "물타기",
)

BANNED_P0_CERTAINTY: Final[tuple[str, ...]] = (
    "반드시",
    "확실",
    "보장",
    "급등 예상",
    "급락 임박",
    "불가피",
    "필연",
)

BANNED_P0_QUANTIFIED_OUTCOME: Final[tuple[re.Pattern[str], ...]] = (
    # "30% 이상 수익 예상 / 가능 / 보장 / 기대" style
    re.compile(
        r"\d+\s*%\s*(이상\s*)?\s*(수익|상승|하락|손실)\s*"
        r"(예상|가능|기대|보장|확실|불가피)"
    ),
    # "2배 수익 / 상승" style
    re.compile(r"\d+\s*배\s*(수익|상승)"),
)

BANNED_P0_CRYPTO_ONLY: Final[tuple[str, ...]] = (
    "세력",
    "김프 진입",
    "상폐 임박",
    "에어드랍 확정",
    "펌핑",
)

# ---------------------------------------------------------------------------
# P1 — WARN at publish boundary (non-blocking)
# ---------------------------------------------------------------------------

WARN_P1: Final[tuple[str, ...]] = (
    "직접 반영된다",
    "작용할 전망",
)

WARN_P1_CLOSED_CAUSATION: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(주가|지수|가격)[가-힣\s]{0,4}(때문에|로 인해)[가-힣\s]{0,8}(했다|한다)"),
)

# ---------------------------------------------------------------------------
# Context-aware demote markers (Step 3 — false-positive filter)
# ---------------------------------------------------------------------------

# 좌/우 6-token window 분기. Each entry maps a P0 token to the set of
# context markers that demote it from P0 → INFO.
CONTEXT_DEMOTE_NEIGHBORS: Final[dict[str, frozenset[str]]] = {
    "진입": frozenset({"분야", "시장", "사업"}),
    "청산": frozenset({"회사", "기업", "법인", "파산", "합병"}),
    # 목표가 — only the quotative-source markers demote. Bare ``목표가``
    # stays P0. The scan classifier (compliance_language._classify_hit)
    # encodes this asymmetry: left-side markers only.
    "목표가": frozenset({"증권사", "애널리스트", "보고서", "IR", "분기"}),
    # 편입 — "ETF 편입" (index inclusion event) is news fact, not advice;
    # "포트폴리오에 편입" is advice → stays P0.
    "편입": frozenset({"ETF", "지수", "코스피200", "MSCI"}),
}


__all__ = [
    "BANNED_P0_ACTION",
    "BANNED_P0_CERTAINTY",
    "BANNED_P0_CRYPTO_ONLY",
    "BANNED_P0_QUANTIFIED_OUTCOME",
    "CONTEXT_DEMOTE_NEIGHBORS",
    "WARN_P1",
    "WARN_P1_CLOSED_CAUSATION",
]
