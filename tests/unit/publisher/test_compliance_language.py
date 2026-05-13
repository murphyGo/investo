"""u56 — compliance-language P0/P1 gate."""

from __future__ import annotations

import logging

import pytest

from investo.publisher.compliance_language import (
    ComplianceLanguageError,
    repair_compliance_language,
    scan_compliance,
)

SEG = "us-equity"  # default segment for non-crypto tests


def _wrap(body: str) -> str:
    """Build a minimal scannable markdown shell — body wrapped between
    the section ① and the disclaimer footer so masking targets the
    disclaimer correctly.
    """
    return (
        "## ① 요약\n"
        f"{body}\n\n"
        "## ⑦ 면책조항\n"
        "본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,\n"
        "특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다.\n"
    )


# ---------------------------------------------------------------------------
# P0 — action verbs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "매수 검토",
        "매도 검토",
        "비중 축소",
        "비중 확대",
        "차익실현",
        "익절",
        "손절매",
        "리밸런싱",
        "평단가",
        "추격매수",
        "물타기",
    ],
)
def test_p0_action_phrase_blocks_publish(phrase: str) -> None:
    md = _wrap(f"AAPL에 대해 {phrase}가 가능하다.")
    with pytest.raises(ComplianceLanguageError) as info:
        scan_compliance(md, SEG)
    assert phrase in str(info.value)


def test_p0_certainty_phrase_blocks_publish() -> None:
    md = _wrap("이번 주는 반드시 상승한다고 보인다.")
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(md, SEG)


@pytest.mark.parametrize(
    "phrase",
    ["30% 이상 수익 예상", "2배 상승", "50% 수익 가능", "10배 수익"],
)
def test_p0_quantified_outcome_blocks_publish(phrase: str) -> None:
    md = _wrap(f"올해 안에 {phrase}이라는 전망이 나왔다.")
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(md, SEG)


def test_quantified_outcome_does_not_match_factual_report() -> None:
    """``12% 상승했다`` (factual past-tense) is NOT a quantified outcome
    promise — past indicative is allowed."""
    md = _wrap("어제 AAPL는 12% 상승했다.")
    report = scan_compliance(md, SEG)
    assert not report.p0_hits


# ---------------------------------------------------------------------------
# Crypto-only P0 segment isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    ["세력", "김프 진입", "상폐 임박", "에어드랍 확정", "펌핑"],
)
def test_crypto_only_p0_active_for_crypto_segment(phrase: str) -> None:
    md = _wrap(f"BTC 시장에서 {phrase}이라는 평가가 나왔다.")
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(md, "crypto")


@pytest.mark.parametrize(
    "phrase",
    ["상폐 임박", "에어드랍 확정", "펌핑"],
)
def test_crypto_only_p0_not_active_for_us_equity(phrase: str) -> None:
    md = _wrap(f"AAPL에 대해 {phrase}는 말이 나왔다.")
    report = scan_compliance(md, "us-equity")
    # phrase should NOT appear in p0_hits; the scan does not look for
    # crypto-only phrases on the equity segment.
    assert all(phrase not in h.phrase for h in report.p0_hits)


# ---------------------------------------------------------------------------
# Context-aware demote (Step 3)
# ---------------------------------------------------------------------------


def test_context_demote_jinip_in_field() -> None:
    md = _wrap("회사는 AI 분야 진입을 검토 중이다.")
    report = scan_compliance(md, SEG)
    # 진입 should be demoted to INFO (context: 분야).
    assert not report.p0_hits
    assert any(h.phrase == "진입" for h in report.info_hits)


def test_context_demote_cheongsan_in_bankruptcy() -> None:
    md = _wrap("해당 회사는 파산 청산 절차에 들어갔다.")
    report = scan_compliance(md, SEG)
    assert not any(h.phrase == "청산" for h in report.p0_hits)


def test_mokpyoga_with_brokerage_left_context_demoted() -> None:
    md = _wrap("삼성증권 보고서는 NVDA 목표가 1000달러로 제시했다.")
    report = scan_compliance(md, SEG)
    assert not any(h.phrase == "목표가" for h in report.p0_hits)


def test_bare_mokpyoga_stays_p0() -> None:
    md = _wrap("NVDA 목표가 1000달러를 노릴 만하다.")
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(md, SEG)


def test_etf_pyeonip_demoted() -> None:
    md = _wrap("KODEX 200 ETF 편입 비중 변경이 공시되었다.")
    report = scan_compliance(md, SEG)
    assert not any(h.phrase == "편입" for h in report.p0_hits)


# ---------------------------------------------------------------------------
# P1 — WARN only (non-blocking)
# ---------------------------------------------------------------------------


def test_p1_phrase_warns_but_does_not_block(caplog: pytest.LogCaptureFixture) -> None:
    md = _wrap("이번 발표가 다음 분기 실적에 직접 반영된다는 기대가 나왔다.")
    with caplog.at_level(logging.WARNING):
        report = scan_compliance(md, SEG)
    assert any("compliance_language.p1_hit" in r.message for r in caplog.records)
    assert any(h.phrase == "직접 반영된다" for h in report.p1_hits)
    assert not report.p0_hits


# ---------------------------------------------------------------------------
# Masking guardrails
# ---------------------------------------------------------------------------


def test_code_block_p0_phrase_is_ignored() -> None:
    md = (
        "## ① 요약\n"
        "정상 문장입니다.\n\n"
        "```\n"
        "익절 손절 비중 축소 매수 검토\n"
        "```\n\n"
        "## ⑦ 면책조항\n"
        "본 시황은 매매 권유가 아닙니다.\n"
    )
    report = scan_compliance(md, SEG)
    assert not report.p0_hits


def test_table_row_p0_phrase_is_ignored() -> None:
    md = (
        "## ① 요약\n"
        "정상 문장입니다.\n\n"
        "| 종목 | 비고 |\n"
        "| --- | --- |\n"
        "| AAPL | 익절 |\n\n"
        "## ⑦ 면책조항\n"
        "본 시황은 매매 권유가 아닙니다.\n"
    )
    report = scan_compliance(md, SEG)
    assert not report.p0_hits


def test_disclaimer_footer_phrase_is_ignored() -> None:
    """``매매 권유`` in the canonical footer must not trigger a P0 hit."""
    md = _wrap("정상 문장입니다.")
    # The disclaimer footer in _wrap contains "매매 권유" — which is not
    # itself in our P0 list, but masking the footer keeps any nearby
    # phrases from contaminating the scan.
    report = scan_compliance(md, SEG)
    assert not report.p0_hits


def test_clean_body_returns_empty_report() -> None:
    md = _wrap("S&P 500 지수가 0.5% 상승 마감했다는 사실이 확인되었다.")
    report = scan_compliance(md, SEG)
    assert not report.p0_hits
    assert not report.p1_hits


def test_segment_field_propagated_to_report() -> None:
    md = _wrap("정상 문장입니다.")
    report = scan_compliance(md, "crypto")
    assert report.segment == "crypto"


# ---------------------------------------------------------------------------
# Repair pass
# ---------------------------------------------------------------------------


def test_repair_compliance_language_neutralizes_p0_phrases() -> None:
    md = _wrap("BTC는 30% 이상 수익 예상이 아니라 변동성 확인이 필요하고 펌핑 표현은 피한다.")
    repaired = repair_compliance_language(md, "crypto")
    report = scan_compliance(repaired, "crypto")
    assert not report.p0_hits
    assert "수익률 변동 가능성" in repaired
    assert "단기 급등" in repaired


def test_repair_compliance_language_preserves_masked_regions() -> None:
    md = (
        "## ① 요약\n"
        "| 종목 | 비고 |\n"
        "| --- | --- |\n"
        "| AAPL | 매수 검토 |\n\n"
        "```\n"
        "익절\n"
        "```\n\n"
        "본문에는 손절 문구가 있다.\n\n"
        "## ⑦ 면책조항\n"
        "매수 검토 손절\n"
    )
    repaired = repair_compliance_language(md, SEG)
    assert "| AAPL | 매수 검토 |" in repaired
    assert "```\n익절\n```" in repaired
    assert "## ⑦ 면책조항\n매수 검토 손절" in repaired
    assert "본문에는 거래 리스크 관리 문구가 있다." in repaired
