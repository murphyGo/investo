"""Tests for the u73 daily-first watchlist impact center page."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from investo.briefing.watchlist import WatchlistConfig, match_watchlist_items
from investo.briefing.watchlist_impact import build_impact_center
from investo.models import NormalizedItem
from investo.publisher.watchlist_pages import (
    DAILY_IMPACT_PAGE,
    render_daily_impact_page,
    write_daily_impact_page,
)


def _item(
    title: str,
    summary: str | None = None,
    *,
    raw_metadata: dict[str, str] | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name="yahoo-finance-news",
        category="news",
        title=title,
        summary=summary,
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata=raw_metadata or {},
    )


def _center(config: WatchlistConfig, items: list[NormalizedItem]) -> object:
    return build_impact_center(match_watchlist_items(items, config), items=items, config=config)


def test_daily_page_starts_with_today_impacts_not_config_prose() -> None:
    """AC-73.3 — first content block is today's impacts, not config text."""
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA earnings beat")]
    center = _center(config, items)
    body = render_daily_impact_page(date(2026, 5, 7), center)  # type: ignore[arg-type]
    lines = [line for line in body.splitlines() if line.strip()]
    assert lines[0] == "# 오늘의 관심 자산 영향 — 2026-05-07"
    # The summary counts line precedes any prose about configuration.
    assert "직접 1" in body
    assert "config/watchlist.json" not in body


def test_daily_page_groups_direct_related_uncertain_rejected() -> None:
    config = WatchlistConfig(tickers=("BTC",), sectors=("semiconductor",), keywords=("EV",))
    items = [
        _item("Bitcoin rallies", raw_metadata={"symbol": "BTC-USD"}),
        _item("semiconductor cycle recovery"),
        _item("a new ev launch"),
        _item("BTM Corp unrelated news"),
    ]
    center = _center(config, items)
    body = render_daily_impact_page(date(2026, 5, 7), center)  # type: ignore[arg-type]
    assert "직접 영향 (Direct)" in body
    assert "관련·매크로 맥락 (Related)" in body
    # Uncertain + Rejected only inside the collapsed diagnostics block.
    assert "<details>" in body
    assert "진단: 보류/제외된 후보" in body
    assert "제외 (Rejected)" in body


def test_daily_page_diagnostics_redact_titles() -> None:
    """Uncertain/Rejected rows must not leak the full source title."""
    config = WatchlistConfig(tickers=("BTC",), keywords=("EV",))
    secret_title = "SECRETHEADLINE about a new ev model and BTM Corp"
    items = [_item(secret_title)]
    center = _center(config, items)
    body = render_daily_impact_page(date(2026, 5, 7), center)  # type: ignore[arg-type]
    assert "SECRETHEADLINE" not in body
    # The diagnostics block still references the source + reason codes.
    assert "yahoo-finance-news" in body


def test_daily_page_public_groups_show_titles() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA rallies after earnings beat")]
    center = _center(config, items)
    body = render_daily_impact_page(date(2026, 5, 7), center)  # type: ignore[arg-type]
    # Public Direct group renders the headline.
    assert "NVDA rallies after earnings beat" in body


def test_daily_page_segment_backlinks() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA up")]
    center = _center(config, items)
    body = render_daily_impact_page(
        date(2026, 5, 7),
        center,  # type: ignore[arg-type]
        segment_links=[("미국 주식", "archive/us-equity/2026/05/2026-05-07.md")],
    )
    assert "## 관련 시황" in body
    assert "archive/us-equity/2026/05/2026-05-07.md" in body


def test_write_daily_page_prefixes_segment_backlinks_for_mkdocs(tmp_path: object) -> None:
    root = Path(tmp_path) / "site_docs" / "watchlist"  # type: ignore[arg-type]
    config = WatchlistConfig(tickers=("NVDA",))
    center = _center(config, [_item("NVDA up")])

    path = write_daily_impact_page(
        date(2026, 5, 7),
        center,  # type: ignore[arg-type]
        pages_root=root,
        segment_links=[("미국 주식", "archive/us-equity/2026/05/2026-05-07.md")],
    )

    assert "../archive/us-equity/2026/05/2026-05-07.md" in path.read_text(encoding="utf-8")


def test_daily_page_unconfigured_branch() -> None:
    config = WatchlistConfig()
    center = build_impact_center(match_watchlist_items([_item("x")], config))
    body = render_daily_impact_page(date(2026, 5, 7), center)  # type: ignore[arg-type]
    assert "관심 목록 미설정" in body
    assert "<details>" not in body


def test_index_includes_group_guide_and_excludes_daily(tmp_path: object) -> None:
    """The per-term index documents group semantics + omits daily.md as a term."""
    from datetime import date as _date

    from investo.briefing.watchlist import WatchlistMatch
    from investo.publisher.watchlist_pages import update_watchlist_pages, write_daily_impact_page

    root = tmp_path  # type: ignore[assignment]
    match = WatchlistMatch(term="NVDA", kind="ticker", item=_item("NVDA up"))
    update_watchlist_pages(_date(2026, 5, 7), [match], pages_root=root)  # type: ignore[arg-type]
    config = WatchlistConfig(tickers=("NVDA",))
    center = _center(config, [_item("NVDA up")])
    write_daily_impact_page(_date(2026, 5, 7), center, pages_root=root)  # type: ignore[arg-type]
    # Regenerate the index now that daily.md exists.
    update_watchlist_pages(_date(2026, 5, 7), [match], pages_root=root)  # type: ignore[arg-type]
    index_text = (root / "index.md").read_text(encoding="utf-8")  # type: ignore[operator]
    assert "영향 그룹 안내" in index_text
    assert "직접 (Direct)" in index_text
    assert "제외 (Rejected)" in index_text
    assert "매매 권유가 아닙니다" in index_text
    # daily.md is not a per-term row.
    assert "| daily " not in index_text
    assert "오늘의 관심 자산 영향" in index_text


def test_daily_page_is_idempotent(tmp_path: object) -> None:
    config = WatchlistConfig(tickers=("NVDA",), keywords=("EV",))
    items = [_item("NVDA up"), _item("BTM news")]
    center = _center(config, items)
    root = tmp_path  # type: ignore[assignment]
    p1 = write_daily_impact_page(date(2026, 5, 7), center, pages_root=root)  # type: ignore[arg-type]
    first = p1.read_text(encoding="utf-8")
    p2 = write_daily_impact_page(date(2026, 5, 7), center, pages_root=root)  # type: ignore[arg-type]
    assert p1 == p2
    assert p1.name == DAILY_IMPACT_PAGE
    assert p2.read_text(encoding="utf-8") == first
