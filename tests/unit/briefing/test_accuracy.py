"""Tests for u44 forecast accuracy aggregation."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from investo.briefing.accuracy import PriceMove, compute_accuracy, render_accuracy_page
from investo.briefing.segments import MarketSegment


def _write_log(path: Path, day: date, segment: MarketSegment, tag: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "target_date": day.isoformat(),
                    "segment": segment,
                    "action_tag": tag,
                    "tickers": [],
                    "published_at": f"{day.isoformat()}T00:00:00+00:00",
                    "briefing_url": "",
                }
            )
            + "\n"
        )


def test_compute_accuracy_scores_directional_tags(tmp_path: Path) -> None:
    log = tmp_path / "forecast_log.jsonl"
    start = date(2026, 5, 1)
    tags = ["[강세]", "[약세]", "[혼조]", "[변동성↑]"]
    for idx in range(30):
        _write_log(log, start + timedelta(days=idx), "us-equity", tags[idx % len(tags)])

    def lookup(segment: MarketSegment, target_date: date, window_days: int) -> PriceMove:
        del segment, window_days
        if target_date.day % 4 == 1:
            return PriceMove(pct_change=1.0)
        if target_date.day % 4 == 2:
            return PriceMove(pct_change=-1.0)
        if target_date.day % 4 == 3:
            return PriceMove(pct_change=0.2)
        return PriceMove(pct_change=3.0, volatility_percentile=0.9)

    report = compute_accuracy(30, log_path=log, price_lookup=lookup, today=date(2026, 5, 30))
    body = render_accuracy_page((report,))

    assert "100.0%" in body
    assert "[강세]" in body
    assert "[변동성↑]" in body


def test_accuracy_marks_watch_and_data_limited_as_na(tmp_path: Path) -> None:
    log = tmp_path / "forecast_log.jsonl"
    _write_log(log, date(2026, 5, 1), "crypto", "[관망]")
    _write_log(log, date(2026, 5, 2), "crypto", "[데이터부족]")

    report = compute_accuracy(
        7,
        log_path=log,
        price_lookup=lambda _segment, _target, _window: PriceMove(pct_change=99.0),
        today=date(2026, 5, 7),
    )

    assert all(row.hit_rate is None for row in report.rows)
    assert {row.action_tag for row in report.rows} == {"[관망]", "[데이터부족]"}


def test_accuracy_empty_log_placeholder(tmp_path: Path) -> None:
    report = compute_accuracy(
        30,
        log_path=tmp_path / "missing.jsonl",
        price_lookup=lambda _segment, _target, _window: None,
    )

    assert "표본 누적 중" in render_accuracy_page((report,))
