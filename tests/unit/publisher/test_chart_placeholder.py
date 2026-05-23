"""Regression tests for ``investo.publisher.charts`` (u50).

Pins:

* Placeholder div carries the expected attribute set (``data-ticker``,
  ``data-close``, optional ``data-pct``, ``data-history``,
  ``data-ath`` only when ATH, ``data-52w-high`` / ``data-52w-low``
  derived from the supplied history).
* ``data-history`` JSON shape — list of dicts with ``t/o/h/l/c[/v]``.
* HTML id slug strips non-ASCII-alnum characters so ``^GSPC`` lands as
  ``chart-GSPC`` (a leading ``^`` would parse but breaks `getElementById`
  in some legacy paths).
* Attribute escaping defends against a malformed ticker / history value
  closing the surrounding tag.
* ``inject_chart_block`` lands the block under the ⑤ 주요 종목 H2 and
  is idempotent on re-run.
* ``SECTION_FIVE_HEADER`` matches the briefing prompt's literal so a
  future header rename fails this test (chokepoint pin).
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from investo.briefing.market_anchor import MarketAnchor, OHLCRow
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.publisher.charts import (
    MAX_CHARTS_PER_BRIEFING,
    SECTION_FIVE_HEADER,
    build_chart_block,
    inject_chart_block,
    render_chart_placeholder,
)


def _row(day: int, close: float, volume: float | None = 100.0) -> OHLCRow:
    return OHLCRow(
        trading_date=date(2026, 5, day),
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)) if volume is not None else None,
    )


def _history(*closes: float) -> tuple[OHLCRow, ...]:
    return tuple(_row(idx + 1, value) for idx, value in enumerate(closes))


def _anchor(
    ticker: str,
    *,
    close: float,
    is_ath: bool,
    pct: float | None = None,
) -> MarketAnchor:
    return MarketAnchor(
        ticker=ticker,
        close=Decimal(str(close)),
        pct=Decimal(str(pct)) if pct is not None else None,
        is_ath=is_ath,
    )


# ---------------------------------------------------------------------------
# render_chart_placeholder
# ---------------------------------------------------------------------------


def test_render_emits_expected_attribute_set_for_ath() -> None:
    history = _history(100.0, 102.0, 105.0, 108.0)
    anchor = _anchor("AAPL", close=108.0, is_ath=True, pct=1.23)
    rendered = render_chart_placeholder(anchor, history)
    assert rendered.startswith('<div class="investo-chart"')
    assert ' id="chart-AAPL"' in rendered
    assert ' data-ticker="AAPL"' in rendered
    assert ' data-close="108.0"' in rendered
    assert ' data-pct="1.23"' in rendered
    assert ' data-ath="108.0"' in rendered
    # data-52w-high reflects the max(history.high), not anchor.close
    assert ' data-52w-high="109.0"' in rendered
    assert " data-history='" in rendered
    assert rendered.endswith("</div>\n")


def test_render_omits_ath_attribute_when_not_at_ath() -> None:
    history = _history(100.0, 110.0, 90.0)
    anchor = _anchor("MSFT", close=90.0, is_ath=False)
    rendered = render_chart_placeholder(anchor, history)
    assert "data-ath=" not in rendered
    assert "data-pct=" not in rendered
    assert " data-52w-high=" in rendered
    assert " data-52w-low=" in rendered


def test_render_returns_empty_for_empty_history() -> None:
    anchor = _anchor("NVDA", close=500.0, is_ath=True)
    assert render_chart_placeholder(anchor, ()) == ""


def test_id_slug_strips_caret() -> None:
    history = _history(100.0, 105.0)
    anchor = _anchor("^GSPC", close=105.0, is_ath=True)
    rendered = render_chart_placeholder(anchor, history)
    assert ' id="chart-GSPC"' in rendered
    # data-ticker preserves the original ticker (HTML-escaped).
    assert ' data-ticker="^GSPC"' in rendered


def test_id_slug_preserves_hyphenated_btc() -> None:
    history = _history(50_000.0, 60_000.0)
    anchor = _anchor("BTC-USD", close=60_000.0, is_ath=True)
    rendered = render_chart_placeholder(anchor, history)
    assert ' id="chart-BTC-USD"' in rendered


def test_data_history_json_shape() -> None:
    history = (
        OHLCRow(
            trading_date=date(2026, 5, 1),
            open=Decimal("100.10"),
            high=Decimal("101.50"),
            low=Decimal("99.20"),
            close=Decimal("100.80"),
            volume=Decimal("12345"),
        ),
        OHLCRow(
            trading_date=date(2026, 5, 2),
            open=Decimal("100.80"),
            high=Decimal("102.10"),
            low=Decimal("100.50"),
            close=Decimal("101.90"),
            volume=None,
        ),
    )
    anchor = _anchor("AAPL", close=101.9, is_ath=True)
    rendered = render_chart_placeholder(anchor, history)
    start = rendered.index("data-history='") + len("data-history='")
    end = rendered.index("'></div>")
    payload = rendered[start:end]
    parsed = json.loads(payload)
    assert parsed == [
        {
            "t": "2026-05-01",
            "o": "100.10",
            "h": "101.50",
            "l": "99.20",
            "c": "100.80",
            "v": "12345",
        },
        {"t": "2026-05-02", "o": "100.80", "h": "102.10", "l": "100.50", "c": "101.90"},
    ]


def test_attribute_escapes_close_tag_attempt() -> None:
    # Defensive — even though tickers are validated upstream, an
    # adversarial ticker carrying ``"></div><script>`` must not break
    # out of the attribute. The attribute escape turns ``"`` into
    # ``&quot;``.
    history = _history(100.0, 110.0)
    anchor = MarketAnchor(
        ticker='AB"><script>',
        close=Decimal("110"),
        is_ath=True,
    )
    rendered = render_chart_placeholder(anchor, history)
    assert "<script>" not in rendered.lower()
    assert "&quot;" in rendered or "&lt;" in rendered


# ---------------------------------------------------------------------------
# build_chart_block + injection
# ---------------------------------------------------------------------------


def test_build_chart_block_renders_open_and_close_wrappers() -> None:
    history = _history(100.0, 105.0, 110.0)
    anchor = _anchor("AAPL", close=110.0, is_ath=True)
    block = build_chart_block([anchor], {"AAPL": history})
    assert 'class="investo-chart-block"' in block
    assert "<noscript>" in block
    assert "JavaScript" in block
    assert block.count('<div class="investo-chart"') == 1


def test_build_chart_block_caps_at_max() -> None:
    history = _history(*(100.0 + i for i in range(5)))
    anchors = [
        _anchor(f"T{i}", close=100.0 + i, is_ath=True) for i in range(MAX_CHARTS_PER_BRIEFING + 3)
    ]
    history_by_ticker = {anchor.ticker: history for anchor in anchors}
    block = build_chart_block(anchors, history_by_ticker)
    assert block.count('<div class="investo-chart"') == MAX_CHARTS_PER_BRIEFING


def test_build_chart_block_returns_empty_when_no_history_matches() -> None:
    anchor = _anchor("AAPL", close=100.0, is_ath=True)
    assert build_chart_block([anchor], {}) == ""
    assert build_chart_block([anchor], {"AAPL": ()}) == ""


def test_inject_chart_block_inserts_after_section_five_header() -> None:
    markdown = "## ① 요약\nblah\n## ⑤ 주요 종목\nbody bullets\n## ⑥ 오늘의 관전 포인트\nmore\n"
    block = '\n<div class="investo-chart-block"></div>\n'
    out = inject_chart_block(markdown, block)
    # Block lands AFTER the ⑤ header line and BEFORE the ⑤ body content.
    five = out.index("## ⑤ 주요 종목")
    six = out.index("## ⑥ 오늘의 관전 포인트")
    block_start = out.index('<div class="investo-chart-block"')
    assert five < block_start < six
    body_start = out.index("body bullets")
    assert block_start < body_start


def test_inject_chart_block_idempotent() -> None:
    markdown = "## ⑤ 주요 종목\nbody\n## ⑥ 오늘의 관전 포인트\nmore\n"
    block = '\n<div class="investo-chart-block">x</div>\n'
    once = inject_chart_block(markdown, block)
    twice = inject_chart_block(once, block)
    assert once == twice


def test_inject_chart_block_no_op_for_empty_block() -> None:
    markdown = "## ⑤ 주요 종목\nbody\n"
    assert inject_chart_block(markdown, "") == markdown


def test_inject_chart_block_no_op_when_header_missing() -> None:
    markdown = "no headers here at all"
    block = '\n<div class="investo-chart-block">x</div>\n'
    assert inject_chart_block(markdown, block) == markdown


def test_section_header_constant_matches_prompts() -> None:
    """Chokepoint pin — a future Stage 2 header rename must update both."""
    assert STAGE2_SECTION_HEADERS[4] == SECTION_FIVE_HEADER


def test_render_is_deterministic() -> None:
    history = _history(100.0, 102.0, 105.0)
    anchor = _anchor("AAPL", close=105.0, is_ath=True)
    a = render_chart_placeholder(anchor, history)
    b = render_chart_placeholder(anchor, history)
    assert a == b
