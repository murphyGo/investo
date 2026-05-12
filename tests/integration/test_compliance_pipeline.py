"""u56 — end-to-end pipeline integration for the compliance-language
gate + first-viewport disclaimer.

Verifies that:
1. Clean briefings pass the chain.
2. Injected P0 phrases block publish via ComplianceLanguageError.
3. Missing canonical footer → verify_disclaimer fails.
4. Crypto segment + equity footer → verify_disclaimer fails.
5. Missing first-viewport short disclaimer in real markdown → gate
   inserts it (production path); after that, the additive gate passes.
"""

from __future__ import annotations

import pytest

from investo.briefing.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.publisher.compliance_language import (
    ComplianceLanguageError,
    scan_compliance,
)
from investo.publisher.reader_format import emit_first_viewport_disclaimer
from investo.publisher.verifier import (
    verify_disclaimer,
    verify_short_disclaimer_first_viewport,
)


def _clean_us_equity_md() -> str:
    return (
        "# 2026-05-13 미국 증시 시황\n\n"
        "## 한눈에 보기\n\n"
        "- S&P 500 1% 상승\n\n"
        "## ① 요약\n\n오늘은 흐름이 안정적이다. [상승 관찰]\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n"
        f"{DISCLAIMER}\n"
    )


def _clean_crypto_md() -> str:
    return (
        "# 2026-05-13 크립토 시황\n\n"
        "## 한눈에 보기\n\n"
        "- BTC 1% 상승\n\n"
        "## ① 요약\n\n오늘은 흐름이 안정적이다. [상승 관찰]\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n"
        f"{DISCLAIMER_CRYPTO}\n"
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_clean_us_equity_passes_full_chain() -> None:
    md = _clean_us_equity_md()
    # scan: clean.
    report = scan_compliance(md, "us-equity")
    assert not report.p0_hits
    # short-disclaimer insertion.
    md2 = emit_first_viewport_disclaimer(md, "us-equity")
    assert verify_short_disclaimer_first_viewport(md2, "us-equity") is True
    # canonical footer gate.
    assert verify_disclaimer(md2, "us-equity") is True


def test_clean_crypto_passes_full_chain() -> None:
    md = _clean_crypto_md()
    report = scan_compliance(md, "crypto")
    assert not report.p0_hits
    md2 = emit_first_viewport_disclaimer(md, "crypto")
    assert verify_short_disclaimer_first_viewport(md2, "crypto") is True
    assert verify_disclaimer(md2, "crypto") is True


# ---------------------------------------------------------------------------
# Negative pins — each surface, when removed, blocks publish.
# ---------------------------------------------------------------------------


def test_p0_phrase_injection_blocks_publish() -> None:
    md = _clean_us_equity_md().replace("오늘은 흐름이 안정적이다.", "오늘은 매수 검토가 적절하다.")
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(md, "us-equity")


def test_canonical_footer_removal_fails_verify_disclaimer() -> None:
    md = _clean_us_equity_md().replace(DISCLAIMER, "")
    assert verify_disclaimer(md, "us-equity") is False


def test_crypto_segment_with_equity_footer_fails_verify_disclaimer() -> None:
    # Take the us-equity markdown (carries equity footer) and check
    # under the crypto segment. Should fail.
    md = _clean_us_equity_md()
    assert verify_disclaimer(md, "crypto") is False


def test_short_disclaimer_removal_fails_first_viewport_gate() -> None:
    md = _clean_us_equity_md()  # no short disclaimer
    assert verify_short_disclaimer_first_viewport(md, "us-equity") is False


def test_crypto_p0_phrase_not_active_for_us_equity_segment() -> None:
    md = _clean_us_equity_md().replace("오늘은 흐름이 안정적이다.", "오늘은 펌핑이 진행 중이다.")
    # us-equity segment: not a P0 hit
    report = scan_compliance(md, "us-equity")
    assert not report.p0_hits


def test_crypto_p0_phrase_active_for_crypto_segment() -> None:
    md = _clean_crypto_md().replace("오늘은 흐름이 안정적이다.", "오늘은 펌핑이 진행 중이다.")
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(md, "crypto")
