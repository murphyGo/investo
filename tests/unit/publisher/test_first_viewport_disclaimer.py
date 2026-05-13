"""u56 — first-viewport short disclaimer (segment-aware)."""

from __future__ import annotations

from investo.publisher.reader_format import (
    SHORT_DISCLAIMER_CRYPTO,
    SHORT_DISCLAIMER_EQUITY,
    emit_first_viewport_disclaimer,
)
from investo.publisher.verifier import verify_short_disclaimer_first_viewport


def test_equity_short_disclaimer_inserted_before_tldr() -> None:
    md = "# Header\n\n## 한눈에 보기\n\n- bullet 1\n\n## ① 요약\n본문.\n"
    out = emit_first_viewport_disclaimer(md, "us-equity")
    # short disclaimer present
    assert SHORT_DISCLAIMER_EQUITY in out
    # it lands BEFORE the TLDR header
    assert out.index(SHORT_DISCLAIMER_EQUITY) < out.index("## 한눈에 보기")


def test_crypto_short_disclaimer_text_differs() -> None:
    md = "## 한눈에 보기\n\n## ① 요약\nbody\n"
    out = emit_first_viewport_disclaimer(md, "crypto")
    assert SHORT_DISCLAIMER_CRYPTO in out
    assert "가상자산" in out


def test_fallback_to_first_section_when_no_tldr() -> None:
    md = "# Header\n\n## ① 요약\n본문.\n"
    out = emit_first_viewport_disclaimer(md, "us-equity")
    assert SHORT_DISCLAIMER_EQUITY in out
    assert out.index(SHORT_DISCLAIMER_EQUITY) < out.index("## ①")


def test_fallback_to_prepend_when_no_anchor() -> None:
    md = "본문만 있는 markdown.\n"
    out = emit_first_viewport_disclaimer(md, "us-equity")
    assert out.startswith(SHORT_DISCLAIMER_EQUITY)


def test_idempotent_equity() -> None:
    md = "## 한눈에 보기\n## ① 요약\nbody"
    once = emit_first_viewport_disclaimer(md, "us-equity")
    twice = emit_first_viewport_disclaimer(once, "us-equity")
    assert once == twice


def test_idempotent_crypto() -> None:
    md = "## 한눈에 보기\n## ① 요약\nbody"
    once = emit_first_viewport_disclaimer(md, "crypto")
    twice = emit_first_viewport_disclaimer(once, "crypto")
    assert once == twice


def test_equity_text_does_not_trigger_crypto_detector() -> None:
    """If only the equity disclaimer is present, the crypto detector
    still inserts (so a mistakenly-emitted equity-only crypto page
    gets the right text)."""
    md = "## 한눈에 보기\nbody"
    out_equity = emit_first_viewport_disclaimer(md, "us-equity")
    out_crypto = emit_first_viewport_disclaimer(out_equity, "crypto")
    # The crypto-specific detector substring is now present (because
    # the crypto pass inserted its text).
    assert "가상자산 매매 권유가 아닙니다" in out_crypto


def test_verify_first_viewport_equity_passes() -> None:
    md = f"{SHORT_DISCLAIMER_EQUITY}\n\n## 한눈에 보기\n- bullet\n\n## ① 요약\n"
    assert verify_short_disclaimer_first_viewport(md, "us-equity") is True


def test_verify_first_viewport_crypto_passes() -> None:
    md = f"{SHORT_DISCLAIMER_CRYPTO}\n\n## 한눈에 보기\n\n## ① 요약\n"
    assert verify_short_disclaimer_first_viewport(md, "crypto") is True


def test_verify_first_viewport_missing_fails() -> None:
    md = "## 한눈에 보기\n- bullet\n\n## ① 요약\n본문.\n"
    assert verify_short_disclaimer_first_viewport(md, "us-equity") is False


def test_verify_first_viewport_equity_text_fails_for_crypto_segment() -> None:
    """Cross-segment regression — equity short disclaimer does NOT
    satisfy the crypto first-viewport gate."""
    md = f"{SHORT_DISCLAIMER_EQUITY}\n\n## 한눈에 보기\n\n## ① 요약\n본문.\n"
    assert verify_short_disclaimer_first_viewport(md, "crypto") is False


def test_verify_first_viewport_only_considers_first_30_lines() -> None:
    """Short disclaimer buried below line 30 should fail the gate."""
    filler = "\n".join(f"line {i}" for i in range(50))
    md = filler + "\n" + SHORT_DISCLAIMER_EQUITY + "\n"
    assert verify_short_disclaimer_first_viewport(md, "us-equity") is False


def test_emit_moves_buried_short_disclaimer_back_to_first_viewport() -> None:
    filler = "\n".join(f"line {i}" for i in range(50))
    md = f"{filler}\n{SHORT_DISCLAIMER_EQUITY}\n\n## 한눈에 보기\n\n## ① 요약\n"

    out = emit_first_viewport_disclaimer(md, "us-equity")

    assert out.count(SHORT_DISCLAIMER_EQUITY) == 1
    assert verify_short_disclaimer_first_viewport(out, "us-equity") is True
    assert out.index(SHORT_DISCLAIMER_EQUITY) < out.index("## 한눈에 보기")
