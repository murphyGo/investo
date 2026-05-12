"""u54 — Citation-cardinality WARN tests (Finding #4, AC-6).

The persona evidence (2026-05-11 domestic briefing) was 1 연합뉴스 URL
attributed to 5 distinct ticker/entity claims. The detector must flag
URLs at or above N=3 distinct claims and emit a structured WARN with
``url_hash`` only — never the raw URL — to honour R13 secret hygiene.
"""

from __future__ import annotations

import logging
import re

from investo.briefing.citation_cardinality import (
    CARDINALITY_THRESHOLD,
    count_claims_per_link,
    detect_cardinality_warnings,
    hash_url,
)


def test_single_url_with_five_tickers_emits_warning() -> None:
    text = (
        "삼성전자 [005930] 상승, SK하이닉스 [000660] 하락, NAVER [035420] 보합, "
        "카카오 [035720] 추세, 현대차 [005380] 약세 (출처: https://yna.invalid/x)"
    )
    warnings = detect_cardinality_warnings(
        text, ["https://yna.invalid/x"], segment="domestic-equity"
    )
    assert len(warnings) == 1
    assert warnings[0].claim_count == 5
    assert warnings[0].segment == "domestic-equity"


def test_url_with_two_tickers_below_threshold_no_warning() -> None:
    text = "삼성전자 [005930] 상승, SK하이닉스 [000660] 하락 (출처: https://x.invalid/a)"
    warnings = detect_cardinality_warnings(text, ["https://x.invalid/a"], segment="domestic-equity")
    assert warnings == ()


def test_warn_extra_payload_contains_url_hash_not_raw_url(
    caplog: logging.LogCaptureFixture,
) -> None:
    """R13 canary — the WARN log must never contain the raw URL.

    The structured extra carries ``url_hash`` (sha1[:12]); the raw URL
    is intentionally omitted so a leak guard scan of operator logs
    cannot surface a query-string token.
    """
    text = "AAPL up, MSFT flat, NVDA strong (cite https://leaky.invalid/?token=ABC123XYZ)"
    url = "https://leaky.invalid/?token=ABC123XYZ"
    caplog.set_level(logging.WARNING, logger="investo.briefing.citation_cardinality")
    warnings = detect_cardinality_warnings(text, [url], segment="us-equity")
    assert len(warnings) == 1
    assert warnings[0].url_hash == hash_url(url)
    # No record's message or extra carries the full URL.
    for record in caplog.records:
        assert url not in record.getMessage()
        # The structured extra is on the record's __dict__.
        assert record.__dict__.get("url_hash") == warnings[0].url_hash
        for value in record.__dict__.values():
            assert url not in str(value)


def test_url_hash_is_twelve_lowercase_hex_chars() -> None:
    h = hash_url("https://example.invalid/x")
    assert len(h) == 12
    assert re.fullmatch(r"[0-9a-f]{12}", h)


def test_us_and_crypto_tickers_count_as_entities() -> None:
    text = "AAPL, MSFT, BTC, ETH all featured in same headline (cite https://x.invalid/y)"
    counts = count_claims_per_link(text, ["https://x.invalid/y"])
    # 4 distinct tickers (AAPL, MSFT, BTC, ETH) — at or above threshold.
    assert counts["https://x.invalid/y"] == 4


def test_extra_terms_pick_up_watchlist_korean_entities() -> None:
    text = "삼성전자가 강세, 현대모비스도 상승, LG에너지솔루션 약세 (출처: https://x.invalid/y)"
    counts = count_claims_per_link(
        text,
        ["https://x.invalid/y"],
        extra_terms=("삼성전자", "현대모비스", "LG에너지솔루션"),
    )
    assert counts["https://x.invalid/y"] == 3


def test_threshold_constant_is_three() -> None:
    assert CARDINALITY_THRESHOLD == 3


def test_url_not_in_text_yields_zero_count() -> None:
    counts = count_claims_per_link("AAPL up, MSFT flat", ["https://nowhere.invalid/x"])
    assert counts["https://nowhere.invalid/x"] == 0


def test_duplicate_url_in_citations_dedup() -> None:
    text = "AAPL, MSFT, NVDA (cite https://x.invalid/y)"
    counts = count_claims_per_link(text, ["https://x.invalid/y", "https://x.invalid/y"])
    assert list(counts.keys()) == ["https://x.invalid/y"]
