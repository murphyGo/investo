"""Deterministic chart-history sidecar files for u75.

u50 embedded the full OHLC history inline in each chart placeholder as a
``data-history='[...]'`` attribute. On a multi-card segment page that is
several tens of KB of JSON the reader downloads before touching a single
chart — a mobile-payload regression even though the visual surface was
already made compact by the later compact-card change.

This module externalises that heavy history into an **archive-local
sidecar JSON file** staged next to the segment markdown / visual assets
and lazy-fetched by ``site_docs/assets/investo-chart-init.js`` only when
the reader expands the chart. The placeholder keeps only the small
summary attributes (``data-ticker`` / ``data-label`` / ``data-close`` /
``data-pct`` / ``data-ath`` / ``data-52w-*``) plus a ``data-history-src``
relative URL.

Pins
~~~~
* **Deterministic** — ``chart_id`` and the sidecar path/content are a
  pure function of ``(segment, ticker, anchor, history)`` plus the
  source-order ordinal for duplicate tickers. No clock, no env, no I/O.
  Same inputs → byte-equal JSON (FD R9 / NFR-006 PBT contract). The
  ``provenance`` block carries the briefing ``run_date`` (the target
  date), never a wall-clock timestamp.
* **GitHub-Pages compatible** — the sidecar is a plain static file under
  ``{stem}.assets/charts/<chart_id>.json`` reachable by a relative URL
  from the rendered HTML. No server endpoint, no CDN, no paid API.
* **R13 hygiene** — the JSON carries OHLCV bars + reconciled prices +
  display label only. No source ``raw_metadata``, no secrets; the whole
  surface is non-secret by construction (same guarantee as the inline
  payload it replaces).
* **Module boundary** — imports only :mod:`investo.briefing.market_anchor`
  (pure) and :mod:`investo.briefing.segments` (the segment-string type).
  Does NOT import from ``orchestrator`` / ``notifier`` / ``sources``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from investo._internal._io import write_atomic_bytes
from investo.models.market_anchor import MarketAnchor, OHLCRow, anchor_label

# Fixed sidecar schema version. Bump only on a breaking shape change; the
# JS loader reads it to refuse incompatible future payloads.
SIDECAR_SCHEMA_VERSION: Final[int] = 1

# Deterministic provenance source tag. Pure constant — no host / key /
# wall-clock value ever lands here (R13).
SIDECAR_PROVENANCE_SOURCE: Final[str] = "investo-chart-history"

# Sub-directory under the markdown-adjacent ``*.assets`` directory that
# holds chart sidecars. Kept separate from the SVG visual cards so a
# directory listing stays legible.
SIDECAR_SUBDIR: Final[str] = "charts"

# Lowercase ``chart_id`` slug: collapse any run of characters outside
# ``[a-z0-9]`` to a single hyphen, then strip leading/trailing hyphens.
_SLUG_RUN_RE: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


def normalize_chart_id(segment: str, ticker: str) -> str:
    """Return the base ``chart_id`` for ``(segment, ticker)``.

    ``{segment}-{normalized_ticker}`` lowercased, every run of non
    ``[a-z0-9]`` characters replaced with a single hyphen, ends trimmed.
    Examples: ``("us-equity", "AAPL")`` → ``us-equity-aapl``;
    ``("crypto", "BTC-USD")`` → ``crypto-btc-usd``;
    ``("us-equity", "^GSPC")`` → ``us-equity-gspc``.

    Duplicate-disambiguation (``-{ordinal}``) is applied by the caller
    that owns source order, not here.
    """
    raw = f"{segment}-{ticker}".lower()
    slug = _SLUG_RUN_RE.sub("-", raw).strip("-")
    return slug or "chart"


def _decimal_str(value: Decimal) -> str:
    """Render a :class:`Decimal` as a plain fixed-point string.

    Mirrors ``investo.publisher.charts._decimal_to_float_str`` so the
    sidecar history and any residual inline summary stay byte-identical
    on the same value.
    """
    return format(value, "f")


@dataclass(frozen=True, slots=True)
class ChartSidecar:
    """A single chart's externalised history payload.

    ``relative_path`` is POSIX, relative to the segment markdown file's
    parent directory (e.g. ``2026-05-24.assets/charts/us-equity-aapl.json``),
    so it doubles as the ``data-history-src`` attribute value AND the
    on-disk location under the archive asset directory.
    """

    chart_id: str
    relative_path: str
    ticker: str
    label: str
    run_date: date
    close: Decimal
    pct: Decimal | None
    ath: Decimal | None
    high_52w: Decimal | None
    low_52w: Decimal | None
    history: tuple[OHLCRow, ...]

    def to_json_bytes(self) -> bytes:
        """Serialise to deterministic, compact UTF-8 JSON bytes.

        Stable key order, compact separators, ``ensure_ascii`` so the
        bytes are platform-independent. Numbers are strings (Decimal
        precision survives the round-trip; the JS loader ``parseFloat``s
        them, identical to the old inline contract).
        """
        summary: dict[str, str] = {"close": _decimal_str(self.close)}
        if self.pct is not None:
            summary["pct"] = _decimal_str(self.pct)
        if self.ath is not None:
            summary["ath"] = _decimal_str(self.ath)
        if self.high_52w is not None:
            summary["high_52w"] = _decimal_str(self.high_52w)
        if self.low_52w is not None:
            summary["low_52w"] = _decimal_str(self.low_52w)

        rows: list[dict[str, str | None]] = []
        for row in sorted(self.history, key=lambda r: r.trading_date):
            entry: dict[str, str | None] = {
                "t": row.trading_date.isoformat(),
                "o": _decimal_str(row.open),
                "h": _decimal_str(row.high),
                "l": _decimal_str(row.low),
                "c": _decimal_str(row.close),
                "v": _decimal_str(row.volume) if row.volume is not None else None,
            }
            rows.append(entry)

        payload: dict[str, object] = {
            "schema_version": SIDECAR_SCHEMA_VERSION,
            "chart_id": self.chart_id,
            "ticker": self.ticker,
            "label": self.label,
            "summary": summary,
            "history": rows,
            "provenance": {
                "source": SIDECAR_PROVENANCE_SOURCE,
                "run_date": self.run_date.isoformat(),
            },
        }
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        return text.encode("utf-8")


def build_chart_sidecar(
    anchor: MarketAnchor,
    history: Sequence[OHLCRow],
    *,
    markdown_stem: str,
    chart_id: str,
    run_date: date,
) -> ChartSidecar:
    """Build the :class:`ChartSidecar` for one anchor + its history.

    ``markdown_stem`` is the segment markdown filename without suffix
    (e.g. ``2026-05-24``); the sidecar lands at
    ``{markdown_stem}.assets/charts/{chart_id}.json`` relative to the
    markdown file. ``chart_id`` is supplied by the caller (already
    duplicate-disambiguated in source order). ``run_date`` is the
    briefing target date (deterministic provenance, no wall clock).

    The 52-week high/low are derived from the supplied history rows (max
    high / min positive low), matching the inline placeholder's price
    labels so the candlestick axis stays history-faithful.
    """
    window_high = max((row.high for row in history), default=None)
    positive_lows = [row.low for row in history if row.low > 0]
    window_low = min(positive_lows) if positive_lows else None
    ath = anchor.close if anchor.is_ath else None
    relative_path = f"{markdown_stem}.assets/{SIDECAR_SUBDIR}/{chart_id}.json"
    return ChartSidecar(
        chart_id=chart_id,
        relative_path=relative_path,
        ticker=anchor.ticker,
        label=anchor_label(anchor.ticker).ko,
        run_date=run_date,
        close=anchor.close,
        pct=anchor.pct,
        ath=ath,
        high_52w=window_high,
        low_52w=window_low,
        history=tuple(history),
    )


def write_chart_sidecar(sidecar: ChartSidecar, markdown_path: Path) -> Path:
    """Write ``sidecar`` next to ``markdown_path`` and return its absolute path.

    The on-disk location is ``markdown_path.parent / sidecar.relative_path``
    — i.e. ``{stem}.assets/charts/<chart_id>.json`` resolved against the
    segment markdown's directory, exactly the location the rendered
    ``data-history-src`` relative URL resolves to on GitHub Pages.

    Atomic write (tmp + ``os.replace``) so a crashed run never leaves a
    truncated sidecar. Idempotent: the bytes are a pure function of the
    inputs, so a same-day re-run overwrites with byte-equal content.
    """
    target = markdown_path.parent / sidecar.relative_path
    write_atomic_bytes(target, sidecar.to_json_bytes())
    return target


__all__ = [
    "SIDECAR_PROVENANCE_SOURCE",
    "SIDECAR_SCHEMA_VERSION",
    "SIDECAR_SUBDIR",
    "ChartSidecar",
    "build_chart_sidecar",
    "normalize_chart_id",
    "write_chart_sidecar",
]
