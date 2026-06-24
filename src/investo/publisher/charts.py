"""Chart placeholder rendering for u50 lightweight-charts-embed.

Pure helpers that turn a :class:`~investo.briefing.market_anchor.MarketAnchor`
+ its source ``OHLCRow`` history into the inline ``<div class="investo-chart"
...>`` block the public site picks up via
``site_docs/assets/investo-chart-init.js``.

The publisher emits the placeholder as a sibling of the static SVG
visual cards (u24 / u26): the SVG stays in place as the no-JS / mail
fallback; the chart placeholder upgrades the experience for browsers
with JavaScript enabled (progressive enhancement).

Pins
~~~~
* **Pure** — no I/O, no clock reads, no env reads. Same anchor + history
  → identical bytes (FD R9 / NFR-006 PBT contract).
* **HTML-attribute safe** — every value flowing into a ``data-*``
  attribute passes through :func:`html.escape` with ``quote=True``.
  Since u75 the heavy OHLC history no longer rides inline; the
  placeholder carries only a small ``data-history-src`` relative URL
  (also attribute-escaped) pointing at a sidecar JSON file the JS layer
  lazy-fetches on expand.
* **Module boundary** — imports only :mod:`investo.briefing.market_anchor`
  (which is itself a pure / dependency-free module). Does NOT import
  from ``orchestrator/`` / ``notifier/`` / ``sources/`` (project rule 2).
* **R13 hygiene** — chart data is OHLC + volume only. Anchor values are
  prices. Neither the rendered HTML nor the JSON payload includes
  source ``raw_metadata``; the entire surface is non-secret by
  construction.

Usage from the orchestrator publish stage::

    from investo.publisher.charts import build_chart_artifacts, inject_chart_block

    artifacts = build_chart_artifacts(
        anchors, history_by_ticker, segment=segment,
        markdown_stem=target_date.isoformat(), run_date=target_date,
    )
    if artifacts.block:
        new_md = inject_chart_block(briefing.rendered_markdown, artifacts.block)
        briefing = briefing.model_copy(update={"rendered_markdown": new_md})
        # write artifacts.sidecars next to the segment markdown / assets
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from investo.models.market_anchor import MarketAnchor, OHLCRow, anchor_label
from investo.publisher.chart_sidecar import (
    ChartSidecar,
    build_chart_sidecar,
    normalize_chart_id,
)

# Maximum chart placeholders embedded per segmented briefing. Since u75
# the heavy history lives in sidecar JSON, so each placeholder is now a
# sub-1 KB summary div; this cap still bounds the number of sidecar
# fetches the JS init layer can trigger on a single page.
MAX_CHARTS_PER_BRIEFING: Final[int] = 5

# Section header (NFC) to anchor injection on. Mirrors
# ``investo.briefing.prompts.STAGE2_SECTION_HEADERS[4]`` literally —
# a copy here avoids a briefing→publisher import cycle, and the unit
# test ``test_chart_placeholder.py::test_anchor_header_matches_prompts``
# pins both constants together so a future header rename fails loudly.
SECTION_FIVE_HEADER: Final[str] = "## ⑤ 주요 종목"

# HTML wrapper around the per-ticker chart placeholders. The
# ``<noscript>`` block leaves a Korean note for readers without JS so
# they understand why the area is empty (the SVG cards above remain
# their primary fallback).
_CHART_BLOCK_OPEN: Final[str] = (
    '\n<div class="investo-chart-block" markdown="0">\n'
    "<!-- u50 lightweight-charts-embed: placeholders consumed by "
    "site_docs/assets/investo-chart-init.js -->\n"
)
_CHART_BLOCK_CLOSE: Final[str] = (
    "<noscript><em>인터랙티브 차트는 JavaScript가 활성화된 환경에서 표시됩니다. "
    "위 정적 카드가 동일한 정보를 담고 있습니다.</em></noscript>\n"
    "</div>\n"
)


# Conservative slug pattern — ``^GSPC`` → ``GSPC``, ``BTC-USD`` →
# ``BTC-USD`` (already valid HTML id chars). The HTML ID grammar is
# permissive but we keep the slug to ASCII alphanumerics + hyphen so
# downstream CSS selectors / anchor links cannot trip on an unusual
# character.
def _slug_for_id(ticker: str) -> str:
    out_chars = []
    for char in ticker:
        if char.isascii() and (char.isalnum() or char == "-"):
            out_chars.append(char)
        else:
            out_chars.append("_")
    slug = "".join(out_chars).strip("_-")
    return slug or "ticker"


def _decimal_to_float_str(value: Decimal) -> str:
    """Render a :class:`Decimal` as a JSON-safe number literal.

    ``json.dumps(Decimal(...))`` raises ``TypeError`` by default; rather
    than register a custom encoder, we pre-format prices / volumes as
    a string-of-digits and emit them through ``json.dumps`` as a string
    field. The JS layer parses each field via ``parseFloat``, so
    floating-point precision concerns surface at the browser level
    only — server-side arithmetic remains :class:`Decimal`-exact.
    """
    return format(value, "f")


def _attr_escape(value: str) -> str:
    """Return ``value`` safe for embedding inside a double-quoted HTML attribute."""
    return html.escape(value, quote=True)


def render_chart_placeholder(
    anchor: MarketAnchor,
    history: Sequence[OHLCRow],
    *,
    sidecar: ChartSidecar,
) -> str:
    """Render a single ``<div class="investo-chart" ...>`` placeholder.

    Empty ``history`` → empty string (caller skips the ticker). The
    resulting div carries:

    * ``data-ticker`` — raw ticker (display value, attribute-escaped).
    * ``data-label`` — canonical Korean reader label for the symbol (u70).
      Sourced from the same :func:`anchor_label` registry the Telegram
      snapshot line uses, so the compact card never re-labels ``^IXIC``
      as Nasdaq 100.
    * ``data-close`` / ``data-pct`` — compact summary values used in the
      collapsed card before the full chart is opened. These come straight
      off the reconciled :class:`MarketAnchor` the orchestrator also feeds
      to the top table (u70 single-payload contract), so the card and the
      table never diverge on the same symbol's price/change.
    * ``data-history-src`` — u75: relative URL of the sidecar JSON file
      that holds the OHLCV bars. The JS layer lazy-fetches it only when
      the reader expands the chart, so the heavy payload never rides
      inline. (Replaces the old ``data-history`` attribute.)
    * ``data-ath`` — anchor close when ``is_ath`` else nothing (the JS
      side already redraws if absent).
    * ``data-52w-high`` / ``data-52w-low`` — derived from the trailing
      window high / low. We compute these from the supplied history
      rather than the anchor's percentage fields so the price labels
      land in the same units the candlestick series uses.
    * ``id`` — ``chart-<slug>`` where slug strips non-ASCII-alnum
      characters from the ticker. Stable across runs for the same
      ticker.
    """
    if not history:
        return ""
    slug = _slug_for_id(anchor.ticker)
    ticker_attr = _attr_escape(anchor.ticker)
    label_attr = _attr_escape(anchor_label(anchor.ticker).ko)
    close_attr = _attr_escape(_decimal_to_float_str(anchor.close))
    pct_attr = ""
    if anchor.pct is not None:
        pct_attr = f' data-pct="{_attr_escape(_decimal_to_float_str(anchor.pct))}"'

    window_high = max(row.high for row in history)
    window_low = min(row.low for row in history if row.low > 0) if history else None
    ath_attr = ""
    if anchor.is_ath:
        ath_attr = f' data-ath="{_attr_escape(_decimal_to_float_str(anchor.close))}"'

    high_attr = f' data-52w-high="{_attr_escape(_decimal_to_float_str(window_high))}"'
    low_attr = ""
    if window_low is not None:
        low_attr = f' data-52w-low="{_attr_escape(_decimal_to_float_str(window_low))}"'

    src_attr = _attr_escape(sidecar.relative_path)
    return (
        f'<div class="investo-chart" id="chart-{slug}" data-ticker="{ticker_attr}"'
        f' data-label="{label_attr}"'
        f' data-close="{close_attr}"{pct_attr}{ath_attr}{high_attr}{low_attr}'
        f' data-history-src="{src_attr}"></div>\n'
    )


@dataclass(frozen=True, slots=True)
class ChartArtifacts:
    """Result of :func:`build_chart_artifacts`.

    ``block`` is the markdown-embeddable HTML (empty when nothing to
    render). ``sidecars`` is the parallel list of externalised history
    payloads the caller must write next to the segment markdown.
    """

    block: str
    sidecars: tuple[ChartSidecar, ...]


def build_chart_artifacts(
    anchors: Sequence[MarketAnchor],
    history_by_ticker: Mapping[str, Sequence[OHLCRow]],
    *,
    segment: str,
    markdown_stem: str,
    run_date: date,
    max_charts: int = MAX_CHARTS_PER_BRIEFING,
) -> ChartArtifacts:
    """Render the chart block plus the externalised sidecar payloads (u75).

    Returns empty artifacts when no anchor has matching history rows, so
    the caller can simply skip injection (no orphan ``<div>`` opens, no
    sidecar files written).

    ``max_charts`` caps the number of placeholders / sidecars. Selection
    follows the input order of ``anchors``; the orchestrator routes
    per-segment, so the first 5 are the natural priority. ``chart_id`` is
    ``{segment}-{normalized_ticker}``; a duplicate slug in the same
    segment gets a ``-{ordinal}`` suffix in source order so two tickers
    that normalise to the same slug never collide on one sidecar file.
    """
    chunks: list[str] = []
    sidecars: list[ChartSidecar] = []
    seen_ids: dict[str, int] = {}
    for anchor in anchors:
        if len(chunks) >= max_charts:
            break
        history = history_by_ticker.get(anchor.ticker, ())
        if not history:
            continue
        base_id = normalize_chart_id(segment, anchor.ticker)
        ordinal = seen_ids.get(base_id, 0)
        seen_ids[base_id] = ordinal + 1
        chart_id = base_id if ordinal == 0 else f"{base_id}-{ordinal}"
        sidecar = build_chart_sidecar(
            anchor,
            history,
            markdown_stem=markdown_stem,
            chart_id=chart_id,
            run_date=run_date,
        )
        rendered = render_chart_placeholder(anchor, history, sidecar=sidecar)
        if rendered:
            chunks.append(rendered)
            sidecars.append(sidecar)
    if not chunks:
        return ChartArtifacts(block="", sidecars=())
    block = f"{_CHART_BLOCK_OPEN}{''.join(chunks)}{_CHART_BLOCK_CLOSE}"
    return ChartArtifacts(block=block, sidecars=tuple(sidecars))


def inject_chart_block(markdown: str, block: str) -> str:
    """Insert ``block`` immediately after the ⑤ 주요 종목 H2 in ``markdown``.

    No-op when:

    * ``block`` is empty (caller had nothing to render);
    * the section header is missing (defensive — Stage 2 prompt
      enforces all six headers; an upstream bug should not crash the
      publish path).

    Idempotency: if the markdown already carries an
    ``investo-chart-block`` div between the ⑤ header and the next H2,
    this function leaves the markdown unchanged. Same-day re-runs
    (FR-006) re-publish without duplicating the block.
    """
    if not block:
        return markdown
    header_idx = markdown.find(SECTION_FIVE_HEADER)
    if header_idx < 0:
        return markdown
    # Skip past the header line itself.
    line_end = markdown.find("\n", header_idx)
    if line_end < 0:
        # Header is the last line; append the block at the very end.
        return f"{markdown}\n{block}"
    insert_at = line_end + 1

    # Idempotency check — look between the header and the next H2 (or
    # end of document) for an existing block.
    next_header = markdown.find("\n## ", insert_at)
    region_end = next_header if next_header >= 0 else len(markdown)
    region = markdown[insert_at:region_end]
    if 'class="investo-chart-block"' in region:
        return markdown

    return f"{markdown[:insert_at]}{block}{markdown[insert_at:]}"


__all__ = [
    "MAX_CHARTS_PER_BRIEFING",
    "SECTION_FIVE_HEADER",
    "ChartArtifacts",
    "build_chart_artifacts",
    "inject_chart_block",
    "render_chart_placeholder",
]
