"""Tests for u32 Step 1 — source tier registry."""

from __future__ import annotations

import logging

import pytest

from investo.sources.tiers import ADAPTER_TIERS, DEFAULT_TIER, adapter_tier, tier_mix_label


def test_default_tier_is_b() -> None:
    assert DEFAULT_TIER == "B"


def test_unknown_adapter_falls_back_to_default() -> None:
    assert adapter_tier("definitely-not-registered-adapter") == "B"


def test_unknown_adapter_fallback_emits_diagnostic_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="investo.sources.tiers"):
        assert adapter_tier("non-production-stub") == DEFAULT_TIER

    assert "[tiers] non-production-stub missing from ADAPTER_TIERS" in caplog.text


def test_registry_covers_known_s_tier_sources() -> None:
    """Regulatory / exchange sources must be tier S."""
    s_tier = {name for name, tier in ADAPTER_TIERS.items() if tier == "S"}
    # SEC EDGAR + FOMC + KRX + Treasury + Korea policy RSS are non-negotiable.
    must_include = {
        "sec-edgar-8k",
        "fomc-rss",
        "fsc-krx-index-price",
        "fsc-krx-stock-price",
        "treasury-rates",
        "korea-policy-rss",
        "cftc-policy-rss",
    }
    missing = must_include - s_tier
    assert not missing, f"S-tier should include {missing}"


def test_known_first_party_sources_are_tier_a() -> None:
    a_tier = {name for name, tier in ADAPTER_TIERS.items() if tier == "A"}
    must_include = {"yfinance-price", "binance-crypto-market", "fred-macro"}
    assert must_include <= a_tier


def test_tier_mix_label_canonical_order() -> None:
    """Output is always S → A → B → C regardless of input order."""
    assert tier_mix_label(["B", "S", "A", "B", "S"]) == "S=2 / A=1 / B=2"


def test_tier_mix_label_empty_input_yields_empty_string() -> None:
    assert tier_mix_label([]) == ""


def test_tier_mix_label_omits_zero_count_buckets() -> None:
    assert tier_mix_label(["S", "S", "S"]) == "S=3"
