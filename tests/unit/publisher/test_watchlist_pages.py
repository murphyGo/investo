"""Tests for u33 Step 3 — per-ticker accumulation pages."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.briefing.watchlist import WatchlistMatch
from investo.models import NormalizedItem
from investo.publisher import watchlist_pages as watchlist_pages_module
from investo.publisher.errors import PublisherIOError
from investo.publisher.watchlist_pages import (
    DAILY_IMPACT_PAGE,
    update_watchlist_pages,
    watchlist_index_path,
    watchlist_page_paths_for,
    watchlist_publish_paths_for,
)


def _match(
    *, term: str, title: str, source: str = "yfinance-price", weight: float = 0.0
) -> WatchlistMatch:
    item = NormalizedItem(
        source_name=source,
        category="news",
        title=title,
        published_at=datetime(2026, 5, 9, tzinfo=UTC),
        raw_metadata={},
    )
    return WatchlistMatch(term=term, kind="ticker", item=item, weight=weight)


def test_update_creates_per_term_page(tmp_path: Path) -> None:
    matches = [_match(term="NVDA", title="NVDA earnings")]
    written = update_watchlist_pages(date(2026, 5, 9), matches, pages_root=tmp_path)
    nvda = tmp_path / "NVDA.md"
    assert nvda.exists()
    body = nvda.read_text(encoding="utf-8")
    assert "NVDA 매칭 누적" in body
    assert "## 2026-05-09" in body
    assert "NVDA earnings" in body
    assert nvda in written


def test_watchlist_page_paths_predicts_per_term_and_index(tmp_path: Path) -> None:
    matches = [
        _match(term="NVDA", title="NVDA earnings"),
        _match(term="AAPL", title="AAPL earnings"),
    ]

    assert watchlist_page_paths_for(matches, pages_root=tmp_path) == (
        tmp_path / "AAPL.md",
        tmp_path / "NVDA.md",
        tmp_path / "index.md",
    )


def test_watchlist_page_paths_include_existing_index_rewrite(tmp_path: Path) -> None:
    (tmp_path / "NVDA.md").write_text("# old", encoding="utf-8")

    assert watchlist_page_paths_for([], pages_root=tmp_path) == (
        watchlist_index_path(pages_root=tmp_path),
    )


def test_watchlist_publish_paths_include_daily_page(tmp_path: Path) -> None:
    matches = [_match(term="NVDA", title="NVDA earnings")]

    assert watchlist_publish_paths_for(matches, pages_root=tmp_path) == (
        tmp_path / "NVDA.md",
        tmp_path / "index.md",
        tmp_path / DAILY_IMPACT_PAGE,
    )


def test_update_replaces_same_day_section_idempotent(tmp_path: Path) -> None:
    matches_a = [_match(term="NVDA", title="initial title")]
    update_watchlist_pages(date(2026, 5, 9), matches_a, pages_root=tmp_path)

    matches_b = [_match(term="NVDA", title="updated title")]
    update_watchlist_pages(date(2026, 5, 9), matches_b, pages_root=tmp_path)

    body = (tmp_path / "NVDA.md").read_text(encoding="utf-8")
    # Only one section for 2026-05-09 (idempotent replace).
    assert body.count("## 2026-05-09") == 1
    assert "updated title" in body
    assert "initial title" not in body


def test_update_preserves_prior_day_section(tmp_path: Path) -> None:
    update_watchlist_pages(
        date(2026, 5, 8),
        [_match(term="NVDA", title="day 1")],
        pages_root=tmp_path,
    )
    update_watchlist_pages(
        date(2026, 5, 9),
        [_match(term="NVDA", title="day 2")],
        pages_root=tmp_path,
    )
    body = (tmp_path / "NVDA.md").read_text(encoding="utf-8")
    assert "## 2026-05-08" in body
    assert "## 2026-05-09" in body
    assert "day 1" in body
    assert "day 2" in body


def test_update_writes_index_listing_each_term(tmp_path: Path) -> None:
    update_watchlist_pages(
        date(2026, 5, 9),
        [
            _match(term="NVDA", title="NVDA news"),
            _match(term="AAPL", title="AAPL news"),
        ],
        pages_root=tmp_path,
    )
    index = tmp_path / "index.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "NVDA" in text
    assert "AAPL" in text


def test_update_uses_shared_atomic_writer_for_pages_and_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def fake_write_atomic(path: Path, text: str) -> None:
        calls.append(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(watchlist_pages_module, "write_atomic", fake_write_atomic)

    update_watchlist_pages(
        date(2026, 5, 9),
        [_match(term="NVDA", title="NVDA news")],
        pages_root=tmp_path,
    )

    assert tmp_path / "NVDA.md" in calls
    assert tmp_path / "index.md" in calls


def test_update_maps_atomic_oserror_to_publisher_io_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write_atomic(path: Path, text: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(watchlist_pages_module, "write_atomic", fail_write_atomic)

    with pytest.raises(PublisherIOError) as exc_info:
        update_watchlist_pages(
            date(2026, 5, 9),
            [_match(term="NVDA", title="NVDA news")],
            pages_root=tmp_path,
        )

    assert exc_info.value.path == tmp_path / "NVDA.md"


def test_update_includes_weight_when_present(tmp_path: Path) -> None:
    update_watchlist_pages(
        date(2026, 5, 9),
        [_match(term="NVDA", title="NVDA news", weight=2.5)],
        pages_root=tmp_path,
    )
    body = (tmp_path / "NVDA.md").read_text(encoding="utf-8")
    assert "가중치 2.5" in body


def test_update_skips_weight_label_when_zero(tmp_path: Path) -> None:
    update_watchlist_pages(
        date(2026, 5, 9),
        [_match(term="NVDA", title="NVDA news")],
        pages_root=tmp_path,
    )
    body = (tmp_path / "NVDA.md").read_text(encoding="utf-8")
    assert "가중치" not in body


def test_update_handles_korean_term(tmp_path: Path) -> None:
    update_watchlist_pages(
        date(2026, 5, 9),
        [_match(term="엔비디아", title="엔비디아 실적")],
        pages_root=tmp_path,
    )
    page = tmp_path / "엔비디아.md"
    assert page.exists()
