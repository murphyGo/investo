"""Tests for the u74 channel-depth v2 native-anchor block.

Covers Steps 1-3 + 5: the deterministic per-segment anchor schema,
explicit missing-data rows (no invented values, no silent omission),
consumption of u67 domestic anchors / u66 crypto indicators, and the
``not_yet_available`` rendering when u66 has not supplied an indicator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from investo.briefing.market_anchor import MarketAnchor
from investo.models import NormalizedItem
from investo.publisher.channel_anchor_block import (
    CHANNEL_ANCHOR_HEADER,
    MissingReason,
    inject_channel_anchor_block,
    render_channel_anchor_block,
)


def _anchor(ticker: str, close: str, pct: str | None = None) -> MarketAnchor:
    return MarketAnchor(
        ticker=ticker,
        close=Decimal(close),
        pct=Decimal(pct) if pct is not None else None,
        is_ath=False,
    )


def _crypto_item(raw_metadata: dict[str, str]) -> NormalizedItem:
    return NormalizedItem(
        source_name="alternative-fng",
        category="macro",
        title="x",
        published_at=datetime(2026, 5, 23, tzinfo=UTC),
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# Schema / determinism
# ---------------------------------------------------------------------------


def test_header_present_when_any_value() -> None:
    # A block renders as soon as ≥ 1 native value is present.
    cases = {
        "domestic-equity": (_anchor("^KOSPI", "2710.55", "0.42"),),
        "us-equity": (_anchor("^GSPC", "5821.40", "0.37"),),
        "crypto": (_anchor("BTC-USD", "97250.00", "1.20"),),
    }
    for seg, anchors in cases.items():
        block = render_channel_anchor_block(seg, anchors=anchors)  # type: ignore[arg-type]
        assert CHANNEL_ANCHOR_HEADER in block


def test_all_missing_returns_empty_block() -> None:
    # No present native value anywhere → empty string (caller omits the
    # whole block); the all-missing grid would be noise.
    assert render_channel_anchor_block("crypto") == ""
    assert render_channel_anchor_block("domestic-equity") == ""
    assert render_channel_anchor_block("us-equity") == ""


def test_deterministic_same_inputs() -> None:
    anchors = (_anchor("^KOSPI", "2710.55", "0.42"),)
    first = render_channel_anchor_block("domestic-equity", anchors=anchors)
    second = render_channel_anchor_block("domestic-equity", anchors=anchors)
    assert first == second


# ---------------------------------------------------------------------------
# Domestic — consumes u67 anchors without changing precedence (AC-74.4)
# ---------------------------------------------------------------------------


def test_domestic_renders_present_and_missing_rows() -> None:
    anchors = (
        _anchor("^KOSPI", "2710.55", "0.42"),
        _anchor("KRW=X", "1372.10", "-0.15"),
    )
    block = render_channel_anchor_block("domestic-equity", anchors=anchors)
    # Present rows carry value + pct.
    assert "| 코스피 | 2,710.55 (+0.42%) |" in block
    assert "| 원/달러 | 1,372.10 (-0.15%) |" in block
    # KOSDAQ absent -> explicit missing reason, no invented value.
    assert "| 코스닥 | 미수집 |" in block


# ---------------------------------------------------------------------------
# US equity — index anchors + missing rows (AC-74.1/74.2)
# ---------------------------------------------------------------------------


def test_us_equity_rows() -> None:
    anchors = (_anchor("^GSPC", "5821.40", "0.37"),)
    block = render_channel_anchor_block("us-equity", anchors=anchors)
    # Labels route through the canonical u70 anchor_label registry (single
    # label authority) → Korean names, not the raw schema English strings.
    assert "| S&P 500 | 5,821.40 (+0.37%) |" in block
    assert "| 나스닥 종합 | 미수집 |" in block
    assert "| 다우존스 | 미수집 |" in block


# ---------------------------------------------------------------------------
# Crypto — consumes u66 indicators (AC-74.3) + not_yet_available
# ---------------------------------------------------------------------------


def test_crypto_full_consumes_u66_indicators() -> None:
    anchors = (
        _anchor("BTC-USD", "97250.00", "1.20"),
        _anchor("ETH-USD", "3420.50", "-0.80"),
    )
    items = [
        _crypto_item(
            {
                "indicator": "global_market",
                "btc_dominance_pct": "58.07",
            }
        ),
        _crypto_item({"indicator": "fear_greed", "value": "28", "classification": "Fear"}),
        _crypto_item({"indicator": "btc_funding", "btc_funding_rate": "0.00003545"}),
        _crypto_item({"indicator": "btc_oi", "btc_oi_usd": "4103494620"}),
    ]
    block = render_channel_anchor_block("crypto", anchors=anchors, crypto_items=items)
    assert "| 비트코인 | 97,250.00 (+1.20%) |" in block
    assert "| 이더리움 | 3,420.50 (-0.80%) |" in block
    assert "| BTC 도미넌스 | 58.07% |" in block
    # Value-only (no ``(Fear)`` gloss — ⓪-A owns the classification gloss
    # to keep the reader-format gloss-dedupe idempotent).
    assert "| 공포·탐욕 | 28 |" in block
    assert "| 펀딩/OI/청산 | 펀딩 0.00003545 · OI 수집됨 |" in block


def test_crypto_not_yet_available_when_u66_absent() -> None:
    # u49 supplies the BTC price anchor but u66 indicators have not landed:
    # the indicator rows must render not_yet_available, not fabricate a
    # value. The block renders because the price anchor is present.
    anchors = (_anchor("BTC-USD", "97250.00", "1.20"),)
    block = render_channel_anchor_block("crypto", anchors=anchors)
    assert "| 비트코인 | 97,250.00 (+1.20%) |" in block
    assert "| 이더리움 | 아직 미제공 |" in block
    assert "| BTC 도미넌스 | 아직 미제공 |" in block
    assert "| 공포·탐욕 | 아직 미제공 |" in block
    assert "| 펀딩/OI/청산 | 아직 미제공 |" in block


def test_missing_rows_carry_no_numeric_value() -> None:
    # A missing row's cell is a reason label from the bounded enum, never
    # a digit string — so it cannot be mistaken for a numeric fact.
    anchors = (_anchor("BTC-USD", "97250.00", "1.20"),)
    block = render_channel_anchor_block("crypto", anchors=anchors)
    reason_labels = {
        "데이터 없음",
        "휴장",
        "미수집",
        "항목 부족",
        "지연",
        "아직 미제공",
    }
    for line in block.splitlines():
        if line.startswith("| 공포·탐욕 |") or line.startswith("| 펀딩/OI/청산 |"):
            cell = line.split("|")[2].strip()
            assert cell in reason_labels
            assert not any(ch.isdigit() for ch in cell)


def test_missing_reason_enum_values() -> None:
    assert MissingReason.NOT_YET_AVAILABLE.value == "not_yet_available"
    assert MissingReason.NOT_COLLECTED.value == "not_collected"


# ---------------------------------------------------------------------------
# Injection idempotence
# ---------------------------------------------------------------------------


def test_inject_idempotent_and_before_first_section() -> None:
    block = render_channel_anchor_block("us-equity", anchors=(_anchor("^GSPC", "5821.40"),))
    text = "## 한눈에 보기\n\n요약.\n\n## ① 요약\n\n본문.\n"
    once = inject_channel_anchor_block(text, block)
    assert CHANNEL_ANCHOR_HEADER in once
    assert once.index(CHANNEL_ANCHOR_HEADER) < once.index("## ①")
    twice = inject_channel_anchor_block(once, block)
    assert twice == once


def test_inject_empty_block_noop() -> None:
    text = "## ① 요약\n"
    assert inject_channel_anchor_block(text, "") == text
