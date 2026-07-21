"""Contract tests for ``investo.publisher.chart_sidecar`` (u75).

Pins:

* Deterministic ``chart_id`` normalisation and sidecar relative path.
* Deterministic, compact, stable-key-order JSON content with the fixed
  schema version and a wall-clock-free provenance block.
* Numeric fields serialise as Decimal-faithful strings; volume is
  ``null`` when the source omits it.
* ``write_chart_sidecar`` lands the file at the markdown-adjacent
  ``{stem}.assets/charts/<chart_id>.json`` location, is idempotent, and
  reachable via the relative ``data-history-src`` URL.
* R13 — no secret / raw-metadata surface in the payload.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from investo.briefing.market_anchor import MarketAnchor, OHLCRow
from investo.publisher.chart_sidecar import (
    SIDECAR_PROVENANCE_SOURCE,
    SIDECAR_SCHEMA_VERSION,
    build_chart_sidecar,
    normalize_chart_id,
    stage_chart_sidecar,
    write_chart_sidecar,
)

_RUN_DATE = date(2026, 5, 24)


def _history() -> tuple[OHLCRow, ...]:
    return (
        OHLCRow(
            trading_date=date(2026, 5, 2),
            open=Decimal("100.80"),
            high=Decimal("102.10"),
            low=Decimal("100.50"),
            close=Decimal("101.90"),
            volume=None,
        ),
        OHLCRow(
            trading_date=date(2026, 5, 1),
            open=Decimal("100.10"),
            high=Decimal("101.50"),
            low=Decimal("99.20"),
            close=Decimal("100.80"),
            volume=Decimal("12345"),
        ),
    )


def _anchor(ticker: str = "AAPL", *, is_ath: bool = True) -> MarketAnchor:
    return MarketAnchor(
        ticker=ticker,
        close=Decimal("101.90"),
        pct=Decimal("1.10"),
        is_ath=is_ath,
    )


@pytest.mark.parametrize(
    ("segment", "ticker", "expected"),
    [
        ("us-equity", "AAPL", "us-equity-aapl"),
        ("crypto", "BTC-USD", "crypto-btc-usd"),
        ("us-equity", "^GSPC", "us-equity-gspc"),
        ("us-equity", "BRK.B", "us-equity-brk-b"),
        ("domestic-equity", "005930.KS", "domestic-equity-005930-ks"),
    ],
)
def test_normalize_chart_id(segment: str, ticker: str, expected: str) -> None:
    assert normalize_chart_id(segment, ticker) == expected


def test_sidecar_relative_path_is_deterministic() -> None:
    sidecar = build_chart_sidecar(
        _anchor(),
        _history(),
        markdown_stem="2026-05-24",
        chart_id="us-equity-aapl",
        run_date=_RUN_DATE,
    )
    assert sidecar.relative_path == "2026-05-24.assets/charts/us-equity-aapl.json"


def test_sidecar_json_shape_and_sort() -> None:
    sidecar = build_chart_sidecar(
        _anchor(),
        _history(),
        markdown_stem="2026-05-24",
        chart_id="us-equity-aapl",
        run_date=_RUN_DATE,
    )
    payload = json.loads(sidecar.to_json_bytes())
    assert payload["schema_version"] == SIDECAR_SCHEMA_VERSION
    assert payload["chart_id"] == "us-equity-aapl"
    assert payload["ticker"] == "AAPL"
    assert payload["label"] == "애플"
    assert payload["summary"]["close"] == "101.90"
    assert payload["summary"]["pct"] == "1.10"
    assert payload["summary"]["ath"] == "101.90"
    assert payload["summary"]["high_52w"] == "102.10"
    assert payload["summary"]["low_52w"] == "99.20"
    # History sorted ascending by date regardless of input order.
    assert [row["t"] for row in payload["history"]] == ["2026-05-01", "2026-05-02"]
    assert payload["history"][0] == {
        "t": "2026-05-01",
        "o": "100.10",
        "h": "101.50",
        "l": "99.20",
        "c": "100.80",
        "v": "12345",
    }
    # Volume null preserved when the source omits it.
    assert payload["history"][1]["v"] is None
    # Deterministic provenance, no wall clock.
    assert payload["provenance"] == {
        "source": SIDECAR_PROVENANCE_SOURCE,
        "run_date": "2026-05-24",
    }


def test_sidecar_json_is_compact_and_deterministic() -> None:
    sidecar = build_chart_sidecar(
        _anchor(),
        _history(),
        markdown_stem="2026-05-24",
        chart_id="us-equity-aapl",
        run_date=_RUN_DATE,
    )
    raw = sidecar.to_json_bytes()
    # Compact separators (no spaces after , or :).
    assert b", " not in raw
    assert b": " not in raw
    # Byte-stable across calls.
    assert raw == sidecar.to_json_bytes()


def test_sidecar_omits_optional_summary_when_absent() -> None:
    anchor = MarketAnchor(ticker="^VIX", close=Decimal("18.5"), is_ath=False)
    history = (
        OHLCRow(
            trading_date=date(2026, 5, 1),
            open=Decimal("18.0"),
            high=Decimal("19.0"),
            low=Decimal("17.5"),
            close=Decimal("18.5"),
            volume=None,
        ),
    )
    payload = json.loads(
        build_chart_sidecar(
            anchor,
            history,
            markdown_stem="2026-05-24",
            chart_id="us-equity-vix",
            run_date=_RUN_DATE,
        ).to_json_bytes()
    )
    assert "pct" not in payload["summary"]
    assert "ath" not in payload["summary"]
    assert payload["summary"]["close"] == "18.5"


def test_write_chart_sidecar_lands_under_assets_dir(tmp_path: Path) -> None:
    markdown_path = tmp_path / "archive" / "us-equity" / "2026" / "05" / "2026-05-24.md"
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("# briefing", encoding="utf-8")
    sidecar = build_chart_sidecar(
        _anchor(),
        _history(),
        markdown_stem="2026-05-24",
        chart_id="us-equity-aapl",
        run_date=_RUN_DATE,
    )
    written = write_chart_sidecar(sidecar, markdown_path)
    assert written == markdown_path.parent / "2026-05-24.assets" / "charts" / "us-equity-aapl.json"
    assert written.is_file()
    # Reachable via the relative data-history-src URL from the markdown dir.
    assert (markdown_path.parent / sidecar.relative_path).resolve() == written.resolve()
    # Idempotent re-write → byte-equal.
    first = written.read_bytes()
    write_chart_sidecar(sidecar, markdown_path)
    assert written.read_bytes() == first


def test_stage_chart_sidecar_writes_only_below_run_root(tmp_path: Path) -> None:
    sidecar = build_chart_sidecar(
        _anchor(),
        _history(),
        markdown_stem="2026-05-24",
        chart_id="us-equity-aapl",
        run_date=_RUN_DATE,
    )
    staging_root = tmp_path / "stage"
    public_root = tmp_path / "archive"

    artifact = stage_chart_sidecar(
        sidecar,
        staging_root=staging_root,
        target_date=_RUN_DATE,
        segment="us-equity",
    )

    assert artifact.kind == "chart"
    assert artifact.staged_path.is_file()
    assert artifact.staged_path.is_relative_to(staging_root)
    assert artifact.relative_public_path.as_posix().endswith(
        "2026-05-24.assets/charts/us-equity-aapl.json"
    )
    assert not public_root.exists()


def test_write_leaves_no_tmp_artifact(tmp_path: Path) -> None:
    markdown_path = tmp_path / "2026-05-24.md"
    markdown_path.write_text("x", encoding="utf-8")
    sidecar = build_chart_sidecar(
        _anchor(), _history(), markdown_stem="2026-05-24", chart_id="c", run_date=_RUN_DATE
    )
    write_chart_sidecar(sidecar, markdown_path)
    leftovers = list((markdown_path.parent / "2026-05-24.assets" / "charts").glob("*.tmp"))
    assert leftovers == []


def test_sidecar_payload_carries_no_raw_metadata_or_secret() -> None:
    """R13 — payload is OHLCV + price + label only; no metadata/secret keys."""
    sidecar = build_chart_sidecar(
        _anchor(), _history(), markdown_stem="2026-05-24", chart_id="c", run_date=_RUN_DATE
    )
    text = sidecar.to_json_bytes().decode("utf-8").lower()
    for forbidden in ("raw_metadata", "token", "api_key", "apikey", "secret", "authorization"):
        assert forbidden not in text
