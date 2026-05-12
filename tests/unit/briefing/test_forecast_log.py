"""Tests for u44 forecast log persistence."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.forecast_log import append_forecast_entries
from investo.models import Briefing


def _briefing(conclusion: str) -> Briefing:
    return Briefing(
        target_date=date(2026, 5, 1),
        market_summary=conclusion,
        key_issues="k",
        sector_flow="s",
        indicators_events="i",
        notable_tickers="n",
        today_watch="t",
        disclaimer=DISCLAIMER,
        rendered_markdown=f"# test\n\n> **오늘의 결론**: {conclusion}\n\n{DISCLAIMER}\n",
    )


def _append(path: Path, target: date, conclusion: str = "NVDA 상승 관찰 [상승 관찰]") -> None:
    append_forecast_entries(
        target,
        segment_briefings={"us-equity": _briefing(conclusion)},
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        briefing_urls={"us-equity": "archive/us-equity/2026/05/2026-05-01.md"},
        log_path=path,
    )


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_first_publish_creates_forecast_log(tmp_path: Path) -> None:
    path = tmp_path / "forecast_log.jsonl"
    _append(path, date(2026, 5, 1))

    rows = _rows(path)
    assert len(rows) == 1
    # u56 — observation set replaces legacy stance tags.
    assert rows[0]["action_tag"] == "[상승 관찰]"
    assert rows[0]["tickers"] == ["NVDA"]


def test_second_day_appends_and_same_day_replaces(tmp_path: Path) -> None:
    path = tmp_path / "forecast_log.jsonl"
    _append(path, date(2026, 5, 1), "NVDA 상승 관찰 [상승 관찰]")
    _append(path, date(2026, 5, 2), "AAPL 하락 관찰 [하락 관찰]")
    _append(path, date(2026, 5, 2), "MSFT 혼재 [혼재]")

    rows = _rows(path)
    assert len(rows) == 2
    assert rows[-1]["target_date"] == "2026-05-02"
    assert rows[-1]["action_tag"] == "[혼재]"
    assert rows[-1]["tickers"] == ["MSFT"]


def test_corrupt_line_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "forecast_log.jsonl"
    path.write_text("{broken\n", encoding="utf-8")

    _append(path, date(2026, 5, 1))

    assert len(_rows(path)) == 1
    assert "skipping corrupt JSONL line" in caplog.text


def test_atomic_failure_preserves_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "forecast_log.jsonl"
    path.write_text('{"target_date":"2026-05-01"}\n', encoding="utf-8")
    original = path.read_text(encoding="utf-8")

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(RuntimeError, match="could not write forecast log"):
        _append(path, date(2026, 5, 2))
    assert path.read_text(encoding="utf-8") == original
