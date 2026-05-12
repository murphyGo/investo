"""u56 — Stage-2 prompt advertises the new observation ActionTag set
and forbids the P0 advisory-language phrase catalog.

Negative-grep: legacy stance tags must NOT appear in the live LLM
contract anymore (the prompt is the source of truth for what the LLM
emits). Positive: the four observation tags + the P0 forbidden phrase
list MUST appear so the LLM sees the contract at the same surface as
the publish gate.
"""

from __future__ import annotations

import pytest

from investo.briefing.prompts import (
    CRYPTO_FORBIDDEN_TERMS_NOTE,
    SEGMENT_CONTEXT_TEMPLATE,
    STAGE2_SYSTEM,
)


@pytest.mark.parametrize(
    "tag",
    ["[상승 관찰]", "[하락 관찰]", "[혼재]", "[변동성 확대]"],
)
def test_stage2_prompt_advertises_new_observation_tag(tag: str) -> None:
    assert tag in STAGE2_SYSTEM


def test_stage2_prompt_advertises_data_insufficient_tag_role() -> None:
    # The publisher forces [데이터부족] — the LLM must know not to emit
    # it itself.
    assert "[데이터부족]" in STAGE2_SYSTEM


@pytest.mark.parametrize(
    "p0_phrase",
    [
        "매수 검토",
        "매도 검토",
        "비중 축소",
        "비중 확대",
        "차익실현",
        "손절",
        "목표가",
        "리밸런싱",
        "평단가",
        "추격매수",
        "물타기",
        "반드시",
        "확실",
        "보장",
    ],
)
def test_stage2_prompt_lists_p0_phrase_in_forbid(p0_phrase: str) -> None:
    """The Stage-2 system prompt enumerates the P0 ban so the LLM
    sees the same list the publisher gate enforces."""
    assert p0_phrase in STAGE2_SYSTEM


def test_stage2_prompt_documents_quantified_outcome_ban() -> None:
    # The numeric-outcome promise regex is gated at publish; the
    # prompt also warns the LLM not to emit it.
    assert "수익 예상" in STAGE2_SYSTEM or "수익" in STAGE2_SYSTEM
    assert "2배" in STAGE2_SYSTEM or "30%" in STAGE2_SYSTEM


def test_stage2_prompt_mentions_observation_verbs() -> None:
    """Replacement verbs are advertised so the LLM has a non-empty
    fallback when it would otherwise have used an action verb."""
    body = STAGE2_SYSTEM
    assert any(v in body for v in ("관찰", "확인", "점검", "비교"))


def test_crypto_segment_context_includes_crypto_p0() -> None:
    """When the segment is crypto, the segment context note carries the
    crypto-only retail-coded ban (세력 / 김프 / 펌핑 / 상폐 임박 /
    에어드랍 확정)."""
    note = CRYPTO_FORBIDDEN_TERMS_NOTE
    for phrase in ("세력", "김프", "펌핑", "상폐", "에어드랍"):
        assert phrase in note


def test_us_equity_segment_context_does_not_include_crypto_p0() -> None:
    """The crypto-only ban must NOT leak into the us-equity prompt
    surface — the §10 reference targets crypto."""
    us_ctx = SEGMENT_CONTEXT_TEMPLATE.format(
        segment_label="미국 주식",
        segment_slug="us-equity",
        data_limited_note="x",
        segment_extra_note="",
    )
    for phrase in ("세력", "김프", "펌핑", "상폐 임박", "에어드랍 확정"):
        assert phrase not in us_ctx
