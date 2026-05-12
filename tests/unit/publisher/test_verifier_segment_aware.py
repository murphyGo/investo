"""u56 — segment-aware ``verify_disclaimer`` + ``DISCLAIMER_CRYPTO``."""

from __future__ import annotations

import pytest

from investo.briefing.disclaimer import (
    COMPLIANCE_CUTOFF_DATE,
    DISCLAIMER,
    DISCLAIMER_CRYPTO,
    append_disclaimer,
)
from investo.publisher.verifier import verify_disclaimer


def test_default_call_uses_equity_byte_compat() -> None:
    """1-arg call preserves the historic equity-only byte-equal check."""
    assert verify_disclaimer(DISCLAIMER) is True
    assert verify_disclaimer(DISCLAIMER_CRYPTO) is False


def test_us_equity_segment_passes_with_equity_footer() -> None:
    assert verify_disclaimer(DISCLAIMER, segment="us-equity") is True


def test_domestic_equity_segment_passes_with_equity_footer() -> None:
    assert verify_disclaimer(DISCLAIMER, segment="domestic-equity") is True


def test_crypto_segment_passes_with_crypto_footer() -> None:
    assert verify_disclaimer(DISCLAIMER_CRYPTO, segment="crypto") is True


def test_crypto_segment_fails_with_us_equity_footer() -> None:
    """Cross-segment regression: crypto + equity footer = fail."""
    assert verify_disclaimer(DISCLAIMER, segment="crypto") is False


def test_legacy_flag_accepts_either_footer() -> None:
    assert verify_disclaimer(DISCLAIMER, segment="crypto", legacy=True) is True
    assert verify_disclaimer(DISCLAIMER_CRYPTO, segment="us-equity", legacy=True) is True


def test_missing_disclaimer_fails() -> None:
    assert verify_disclaimer("# Briefing\nno footer") is False
    assert verify_disclaimer("# Briefing\nno footer", segment="crypto") is False


def test_disclaimer_crypto_references_gasja_law() -> None:
    """``DISCLAIMER_CRYPTO`` carries the 가상자산이용자보호법 reference."""
    assert "가상자산이용자보호법" in DISCLAIMER_CRYPTO
    assert "§10" in DISCLAIMER_CRYPTO
    assert "§19" in DISCLAIMER_CRYPTO


def test_disclaimer_crypto_carries_volatility_warning() -> None:
    assert "변동성" in DISCLAIMER_CRYPTO
    assert "원금" in DISCLAIMER_CRYPTO


def test_append_disclaimer_crypto_uses_crypto_footer() -> None:
    out = append_disclaimer("# header", segment="crypto")
    assert DISCLAIMER_CRYPTO in out
    assert DISCLAIMER not in out  # equity footer must NOT be present


def test_append_disclaimer_us_equity_uses_equity_footer() -> None:
    out = append_disclaimer("# header", segment="us-equity")
    assert DISCLAIMER in out


def test_append_disclaimer_default_is_equity() -> None:
    """1-arg call retains historic equity-only behaviour."""
    out = append_disclaimer("# header")
    assert DISCLAIMER in out


def test_compliance_cutoff_date_constant() -> None:
    """Cutoff date is the u56 land-day (2026-05-13)."""
    assert COMPLIANCE_CUTOFF_DATE.isoformat() == "2026-05-13"


@pytest.mark.parametrize("seg", ["us-equity", "domestic-equity", "crypto"])
def test_idempotent_append(seg: str) -> None:
    once = append_disclaimer("# body", segment=seg)
    twice = append_disclaimer(once, segment=seg)
    assert once == twice
