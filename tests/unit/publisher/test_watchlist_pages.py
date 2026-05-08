"""Tests for u33 Step 3 — per-ticker accumulation pages."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from investo.briefing.watchlist import WatchlistMatch
from investo.models import NormalizedItem
from investo.publisher.watchlist_pages import update_watchlist_pages


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
