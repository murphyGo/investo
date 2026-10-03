"""Strict temporal boundaries and immutable news-window witnesses."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from investo.models.items import NormalizedItem
from investo.models.news_window import (
    NewsCursor,
    NewsCursorLedger,
    NewsDocumentRevision,
    NewsObservationWindow,
    NewsWindowConfig,
    NewsWindowConsumption,
    NewsWindowPlan,
    news_item_in_window,
)
from investo.models.segments import US_EQUITY

END = datetime(2026, 9, 28, 0, tzinfo=UTC)


def _window(**changes: object) -> NewsObservationWindow:
    value = NewsObservationWindow(
        END - timedelta(days=1), END - timedelta(days=1), END, "scheduled", "run-1"
    )
    return replace(value, **changes)


@pytest.mark.parametrize(
    "env",
    [
        {"INVESTO_NEWS_WINDOW_MODE": "unknown"},
        {"INVESTO_NEWS_START_UTC": "2026-09-26T00:00:00Z"},
        {
            "INVESTO_NEWS_START_UTC": "2026-09-26T00:00:00Z",
            "INVESTO_NEWS_END_UTC": "2026-09-27T00:00:00Z",
        },
    ],
)
def test_config_rejects_unknown_modes_unpaired_or_nonreplay_override(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        NewsWindowConfig.from_env(env)


def test_config_defaults_off_and_gate_keeps_actual_active_publication_blocked() -> None:
    assert NewsWindowConfig.from_env({}).mode == "off"
    active = NewsWindowConfig("active")
    with pytest.raises(ValueError, match="operational approval"):
        active.validate_publication(replay=False, dry_run=False)
    active.validate_publication(replay=True, dry_run=False)
    active.validate_publication(replay=False, dry_run=True)
    override = NewsWindowConfig.from_env(
        {
            "INVESTO_NEWS_START_UTC": "2026-09-26T09:00:00+09:00",
            "INVESTO_NEWS_END_UTC": "2026-09-27T09:00:00+09:00",
        },
        target_date=date(2026, 9, 26),
    )
    assert override.start_utc == datetime(2026, 9, 26, tzinfo=UTC)
    with pytest.raises(ValueError, match="requires replay"):
        override.validate_publication(replay=False, dry_run=True)


@pytest.mark.parametrize(
    "changes",
    [
        {"requested_start": END - timedelta(days=8)},
        {"requested_start": END + timedelta(seconds=1)},
        {"logical_start": END, "requested_start": END - timedelta(hours=1)},
        {"requested_start": END},
        {"end_utc": END.replace(tzinfo=None)},
        {"baseline_ref": "origin/main"},
        {"run_id": "../secret"},
    ],
)
def test_invalid_or_ambiguous_window_fails_closed(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _window(**changes)


def test_interval_is_half_open_and_future_cursor_is_empty_hold() -> None:
    window = _window()
    assert window.contains(window.requested_start)
    assert not window.contains(window.end_utc)
    hold = _window(logical_start=END + timedelta(hours=1), requested_start=END)
    assert not hold.fetch_required and not hold.contains(END)
    assert hold.gap_seconds == 0


def test_plan_copies_mapping_and_requires_shared_clock() -> None:
    windows = {("rss", US_EQUITY): _window()}
    plan = NewsWindowPlan("run-1", "active", END.date(), END, False, False, None, None, windows)
    windows.clear()
    assert len(plan.windows) == 1
    with pytest.raises(TypeError):
        plan.windows[("other", US_EQUITY)] = _window()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        plan.mode = "off"  # type: ignore[misc]
    with pytest.raises(ValueError, match="share the observation clock"):
        replace(plan, observed_at=END + timedelta(seconds=1))


def test_sealed_consumption_requires_hash_and_distinct_hash_only_documents() -> None:
    receipt = NewsWindowConsumption(
        "run-1", "rss", US_EQUITY, END - timedelta(days=1), END, None, None
    )
    with pytest.raises(ValueError, match="requires document digest"):
        replace(receipt, phase="sealed")
    sealed = replace(receipt, phase="sealed", sealed_markdown_sha256="a" * 64)
    assert sealed.phase == "sealed"
    with pytest.raises(ValueError, match="must not claim a seal"):
        replace(receipt, sealed_markdown_sha256="a" * 64)
    revision = NewsDocumentRevision(document_id="b" * 64, revision_id="c" * 64)
    with pytest.raises(ValueError, match="document set"):
        replace(receipt, documents=(revision, revision))
    with pytest.raises(ValidationError):
        NewsDocumentRevision(document_id="raw title", revision_id="c" * 64)


def test_ledger_rejects_duplicate_keys_and_unknown_prose() -> None:
    cursor = NewsCursor(source_name="rss", segment=US_EQUITY, end_utc=END)
    with pytest.raises(ValidationError, match="duplicate news ledger"):
        NewsCursorLedger(cursors=(cursor, cursor))
    with pytest.raises(ValidationError):
        NewsCursorLedger.model_validate({"raw_article": "private prose"})


def test_date_precision_is_day_overlap_not_midnight_event_time() -> None:
    # KST day overlaps a UTC interval even though its midnight anchor is outside it.
    item = NormalizedItem(
        source_name="dart",
        category="news",
        title="Disclosure",
        published_at=datetime(2026, 9, 26, 15, tzinfo=UTC),
        raw_metadata={
            "published_at_precision": "date",
            "published_date": "2026-09-27",
            "published_timezone": "Asia/Seoul",
        },
    )
    window = NewsObservationWindow(
        END - timedelta(hours=24),
        END - timedelta(hours=24),
        END - timedelta(hours=12),
        "scheduled",
        "run-1",
    )
    assert not window.contains(item.published_at)
    assert news_item_in_window(item, window)
    assert not news_item_in_window(
        item.model_copy(
            update={
                "raw_metadata": {
                    "published_at_precision": "date",
                    "published_date": "2026-09-27",
                    "published_timezone": "not-a-zone",
                }
            }
        ),
        window,
    )
