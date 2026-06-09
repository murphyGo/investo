"""u70 — body-assertion gating on canonical anchor availability.

Regression for the reviewed failure: a domestic status block reporting
core price source missing/empty while the body asserts a precise KOSPI
move. The gate rewrites isolated offending sentences to a deterministic
data-limited callout and raises on un-rewritable contradictions.
"""

from __future__ import annotations

import pytest

from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.publisher.anchor_assertion_gate import (
    NumericAnchorReconciliationError,
    enforce_anchor_assertions,
    gate_body_assertions,
)


def test_isolated_kospi_claim_without_anchor_is_rewritten() -> None:
    md = "코스피는 1.8% 급락 마감했다.\n"
    result = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())
    assert "급락" not in result.markdown
    assert "데이터 미수집" in result.markdown
    assert result.findings
    assert result.findings[0].isolated is True
    assert result.findings[0].symbol == "^KOSPI"
    assert not result.has_blocking_finding


def test_rewrite_is_idempotent() -> None:
    md = "코스피는 1.8% 급락 마감했다.\n"
    once = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=()).markdown
    twice = gate_body_assertions(once, segment=DOMESTIC_EQUITY, available_symbols=()).markdown
    assert once == twice


def test_claim_passes_when_anchor_available() -> None:
    md = "코스피는 1.8% 급락 마감했다.\n"
    result = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=("^KOSPI",))
    assert result.markdown == md
    assert result.findings == ()


def test_vague_mention_without_magnitude_is_not_gated() -> None:
    md = "코스피는 약세 흐름을 이어갔다.\n"
    result = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())
    # No explicit magnitude → not a precise move claim → untouched.
    assert result.markdown == md
    assert result.findings == ()


def test_multi_sentence_line_rewrites_only_offending_sentence() -> None:
    md = "코스피는 1.8% 급락했다. 외국인 수급은 안정적이었다.\n"
    result = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())
    assert not result.has_blocking_finding
    assert "코스피 관련 정밀 수치는" in result.markdown
    assert "외국인 수급은 안정적이었다" in result.markdown


def test_enforce_raises_on_blocking_finding() -> None:
    md = "| ^KOSPI | 2,500.00 | -1.8% | 급락 |\n"
    with pytest.raises(NumericAnchorReconciliationError):
        enforce_anchor_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())


def test_enforce_returns_rewritten_for_isolated() -> None:
    md = "코스피는 1.8% 급락 마감했다.\n"
    out = enforce_anchor_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())
    assert "데이터 미수집" in out


def test_bullet_line_is_rewritten_preserving_marker() -> None:
    md = "- 코스피는 1.8% 급락 마감했다.\n"
    result = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())
    assert result.markdown.startswith("- ")
    assert "데이터 미수집" in result.markdown
    assert "급락" not in result.markdown


def test_table_row_is_never_rewritten() -> None:
    # The anchor table itself is structural; even a "급락 1.8%" cell must
    # not be rewritten (the gate guards prose, not the table it protects).
    md = "| ^KOSPI | 2,500.00 | -1.8% | 급락 |\n"
    result = gate_body_assertions(md, segment=DOMESTIC_EQUITY, available_symbols=())
    # Structural ⇒ recorded as a blocking finding, markdown unchanged.
    assert result.markdown == md
    assert result.has_blocking_finding


def test_mixed_domestic_paragraph_rewrites_missing_fx_sentence_only() -> None:
    md = (
        "KOSPI(코스피)가 전일 대비 **5%대** 급락한 **8,160**대로 마감했다. "
        "원/달러 환율은 1,600원을 향해 가파르게 치솟았다. "
        "외국인 순매도도 부담이었다.\n"
    )
    out = enforce_anchor_assertions(
        md,
        segment=DOMESTIC_EQUITY,
        available_symbols=("^KOSPI", "^KOSDAQ"),
    )

    assert "KOSPI(코스피)가 전일 대비 **5%대** 급락" in out
    assert "원/달러 환율은 1,600원을 향해" not in out
    assert "원/달러 관련 정밀 수치는" in out
    assert "외국인 순매도도 부담이었다" in out


def test_other_sentence_magnitude_does_not_make_fx_mention_precise() -> None:
    md = (
        "KOSPI(코스피)가 전일 대비 **5%대** 급락한 **8,160**대로 마감했다. "
        "원/달러 환율 급등과 美 고용 호조발 채권금리 급등이 낙폭을 키웠다.\n"
    )
    out = enforce_anchor_assertions(
        md,
        segment=DOMESTIC_EQUITY,
        available_symbols=("^KOSPI", "^KOSDAQ"),
    )

    assert out == md


def test_us_segment_ixic_claim_gated_when_absent() -> None:
    md = "나스닥 종합은 0.5% 상승 마감했다.\n"
    result = gate_body_assertions(md, segment=US_EQUITY, available_symbols=("^GSPC",))
    # ^GSPC present but ^IXIC absent → IXIC claim gated.
    assert result.findings
    assert result.findings[0].symbol == "^IXIC"


def test_crypto_btc_claim_passes_when_present() -> None:
    md = "비트코인은 3.2% 급등했다.\n"
    result = gate_body_assertions(md, segment=CRYPTO, available_symbols=("BTC-USD",))
    assert result.markdown == md
    assert result.findings == ()
