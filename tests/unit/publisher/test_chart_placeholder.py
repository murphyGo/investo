"""Regression tests for ``investo.publisher.charts`` (u50 + u75).

Pins:

* Placeholder div carries the expected attribute set (``data-ticker``,
  ``data-close``, optional ``data-pct``, ``data-history-src``,
  ``data-ath`` only when ATH, ``data-52w-high`` / ``data-52w-low``
  derived from the supplied history).
* u75 — the heavy OHLC history is NOT embedded inline; only a sidecar
  relative URL (``data-history-src``) rides in the placeholder.
* HTML id slug strips non-ASCII-alnum characters so ``^GSPC`` lands as
  ``chart-GSPC``.
* Attribute escaping defends against a malformed ticker closing the
  surrounding tag.
* ``inject_chart_block`` lands the block under the ⑤ 주요 종목 H2 and
  is idempotent on re-run.
* ``SECTION_FIVE_HEADER`` matches the briefing prompt's literal so a
  future header rename fails this test (chokepoint pin).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from investo.briefing.market_anchor import MarketAnchor, OHLCRow
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.publisher.chart_sidecar import build_chart_sidecar
from investo.publisher.charts import (
    MAX_CHARTS_PER_BRIEFING,
    SECTION_FIVE_HEADER,
    build_chart_artifacts,
    inject_chart_block,
    render_chart_placeholder,
)

_RUN_DATE = date(2026, 5, 24)


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


def _render(
    anchor: MarketAnchor,
    history: tuple[OHLCRow, ...],
    *,
    segment: str = "us-equity",
    chart_id: str = "us-equity-test",
) -> str:
    sidecar = build_chart_sidecar(
        anchor,
        history,
        markdown_stem=_RUN_DATE.isoformat(),
        chart_id=chart_id,
        run_date=_RUN_DATE,
    )
    return render_chart_placeholder(anchor, history, sidecar=sidecar)


# ---------------------------------------------------------------------------
# render_chart_placeholder
# ---------------------------------------------------------------------------


def test_render_emits_expected_attribute_set_for_ath() -> None:
    history = _history(100.0, 102.0, 105.0, 108.0)
    anchor = _anchor("AAPL", close=108.0, is_ath=True, pct=1.23)
    rendered = _render(anchor, history, chart_id="us-equity-aapl")
    assert rendered.startswith('<div class="investo-chart"')
    assert ' id="chart-AAPL"' in rendered
    assert ' data-ticker="AAPL"' in rendered
    assert ' data-label="애플"' in rendered
    assert ' data-close="108.0"' in rendered
    assert ' data-pct="1.23"' in rendered
    assert ' data-ath="108.0"' in rendered
    assert ' data-52w-high="109.0"' in rendered
    # u75 — sidecar reference, no inline history.
    assert ' data-history-src="2026-05-24.assets/charts/us-equity-aapl.json"' in rendered
    assert "data-history=" not in rendered
    assert rendered.endswith("></div>\n")


def test_render_omits_ath_attribute_when_not_at_ath() -> None:
    history = _history(100.0, 110.0, 90.0)
    anchor = _anchor("MSFT", close=90.0, is_ath=False)
    rendered = _render(anchor, history)
    assert "data-ath=" not in rendered
    assert "data-pct=" not in rendered
    assert " data-52w-high=" in rendered
    assert " data-52w-low=" in rendered


def test_render_returns_empty_for_empty_history() -> None:
    anchor = _anchor("NVDA", close=500.0, is_ath=True)
    assert (
        render_chart_placeholder(
            anchor,
            (),
            sidecar=build_chart_sidecar(
                anchor, (), markdown_stem="2026-05-24", chart_id="x", run_date=_RUN_DATE
            ),
        )
        == ""
    )


def test_id_slug_strips_caret() -> None:
    history = _history(100.0, 105.0)
    anchor = _anchor("^GSPC", close=105.0, is_ath=True)
    rendered = _render(anchor, history)
    assert ' id="chart-GSPC"' in rendered
    assert ' data-ticker="^GSPC"' in rendered
    ixic = _render(_anchor("^IXIC", close=26_274.13, is_ath=True), _history(25_000.0, 26_274.13))
    assert ' data-label="나스닥 종합"' in ixic
    assert "나스닥 100" not in ixic


def test_id_slug_preserves_hyphenated_btc() -> None:
    history = _history(50_000.0, 60_000.0)
    anchor = _anchor("BTC-USD", close=60_000.0, is_ath=True)
    rendered = _render(anchor, history)
    assert ' id="chart-BTC-USD"' in rendered


def test_no_inline_ohlc_history_in_placeholder() -> None:
    """u75 AC-75.1 — full OHLC rows never appear in the placeholder HTML."""
    history = _history(*(100.0 + i for i in range(28)))
    anchor = _anchor("AAPL", close=127.0, is_ath=True)
    rendered = _render(anchor, history, chart_id="us-equity-aapl")
    # No serialized OHLC row keys leak into the inline attribute surface.
    assert '"o":' not in rendered
    assert '"h":' not in rendered
    assert "data-history=" not in rendered
    # The inline placeholder stays small even for a long history.
    assert len(rendered.encode("utf-8")) < 512


def test_attribute_escapes_close_tag_attempt() -> None:
    history = _history(100.0, 110.0)
    anchor = MarketAnchor(
        ticker='AB"><script>',
        close=Decimal("110"),
        is_ath=True,
    )
    rendered = _render(anchor, history)
    assert "<script>" not in rendered.lower()
    assert "&quot;" in rendered or "&lt;" in rendered


# ---------------------------------------------------------------------------
# build_chart_artifacts + injection
# ---------------------------------------------------------------------------


def _artifacts(anchors: list[MarketAnchor], history_by_ticker: dict) -> object:
    return build_chart_artifacts(
        anchors,
        history_by_ticker,
        segment="us-equity",
        markdown_stem="2026-05-24",
        run_date=_RUN_DATE,
    )


def test_build_chart_artifacts_renders_open_and_close_wrappers() -> None:
    history = _history(100.0, 105.0, 110.0)
    anchor = _anchor("AAPL", close=110.0, is_ath=True)
    artifacts = _artifacts([anchor], {"AAPL": history})
    block = artifacts.block
    assert 'class="investo-chart-block"' in block
    assert "<noscript>" in block
    assert "JavaScript" in block
    assert block.count('<div class="investo-chart"') == 1
    assert len(artifacts.sidecars) == 1
    assert artifacts.sidecars[0].chart_id == "us-equity-aapl"
    assert artifacts.sidecars[0].relative_path == "2026-05-24.assets/charts/us-equity-aapl.json"


def test_build_chart_artifacts_caps_at_max() -> None:
    history = _history(*(100.0 + i for i in range(5)))
    anchors = [
        _anchor(f"T{i}", close=100.0 + i, is_ath=True) for i in range(MAX_CHARTS_PER_BRIEFING + 3)
    ]
    history_by_ticker = {anchor.ticker: history for anchor in anchors}
    artifacts = _artifacts(anchors, history_by_ticker)
    assert artifacts.block.count('<div class="investo-chart"') == MAX_CHARTS_PER_BRIEFING
    assert len(artifacts.sidecars) == MAX_CHARTS_PER_BRIEFING


def test_build_chart_artifacts_returns_empty_when_no_history_matches() -> None:
    anchor = _anchor("AAPL", close=100.0, is_ath=True)
    assert _artifacts([anchor], {}).block == ""
    assert _artifacts([anchor], {}).sidecars == ()
    assert _artifacts([anchor], {"AAPL": ()}).block == ""


def test_build_chart_artifacts_disambiguates_duplicate_chart_ids() -> None:
    history = _history(100.0, 110.0)
    # Two tickers that normalise to the same slug within one segment.
    a1 = _anchor("BTC.USD", close=110.0, is_ath=True)
    a2 = _anchor("BTC-USD", close=110.0, is_ath=True)
    artifacts = build_chart_artifacts(
        [a1, a2],
        {"BTC.USD": history, "BTC-USD": history},
        segment="crypto",
        markdown_stem="2026-05-24",
        run_date=_RUN_DATE,
    )
    ids = [sc.chart_id for sc in artifacts.sidecars]
    assert ids == ["crypto-btc-usd", "crypto-btc-usd-1"]
    # Paths are unique so the two sidecars never collide on disk.
    assert len({sc.relative_path for sc in artifacts.sidecars}) == 2


def test_build_chart_artifacts_is_deterministic() -> None:
    history = _history(100.0, 102.0, 105.0)
    anchor = _anchor("AAPL", close=105.0, is_ath=True)
    a = _artifacts([anchor], {"AAPL": history})
    b = _artifacts([anchor], {"AAPL": history})
    assert a.block == b.block
    assert a.sidecars[0].to_json_bytes() == b.sidecars[0].to_json_bytes()


def test_inject_chart_block_inserts_after_section_five_header() -> None:
    markdown = "## ① 요약\nblah\n## ⑤ 주요 종목\nbody bullets\n## ⑥ 오늘의 관전 포인트\nmore\n"
    block = '\n<div class="investo-chart-block"></div>\n'
    out = inject_chart_block(markdown, block)
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
