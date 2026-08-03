"""Rendered regression for the u133 2026-06-30 registry-only incident."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from investo.briefing.watchlist import (
    WatchlistConfig,
    match_watchlist_items,
    render_watchlist_impact,
)
from investo.briefing.watchlist_impact import build_impact_center, public_impact
from investo.models import NormalizedItem
from investo.publisher.watchlist_pages import render_daily_impact_page

_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "u133" / "watchlist-registry-2026-06-30.json"
)


def test_registry_only_production_match_set_is_diagnostics_only() -> None:
    payload: dict[str, Any] = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    target_date = date.fromisoformat(payload["target_date"])
    config = WatchlistConfig.model_validate(payload["watchlist"])
    items = tuple(NormalizedItem.model_validate(item) for item in payload["items"])
    expected = payload["expected"]

    raw_impact = match_watchlist_items(items, config)
    assert len(raw_impact.matches) == expected["raw_match_count"] >= 5

    center = build_impact_center(raw_impact, items=items, config=config)
    assert center.public_matches() == ()
    assert len(center.uncertain) == expected["raw_match_count"]
    assert {match.reason for match in center.uncertain} == {expected["diagnostic_reason"]}

    site_callout = render_watchlist_impact(public_impact(center), channel="site")
    assert (
        site_callout == "관심 목록과 직접 연결된 수집 항목 없음 — 영향은 별도로 단정하지 않습니다."
    )

    daily_page = render_daily_impact_page(target_date, center)
    assert "직접 0 · 관련 0 · 보류 6 · 제외 0" in daily_page
    details_start = daily_page.index("<details>")
    details_end = daily_page.index("</details>")
    details_close_end = details_end + len("</details>")
    public_daily = daily_page[:details_start] + daily_page[details_close_end:]
    diagnostics = daily_page[details_start:details_close_end]

    for ticker in config.tickers:
        for source_name in ("nasdaq-symbol-directory", "sec-company-facts"):
            redacted_row = f"{ticker} · {source_name} [reference-registry]"
            assert redacted_row in diagnostics
            assert redacted_row not in public_daily
            assert redacted_row not in site_callout
            assert daily_page.count(redacted_row) == 1

    for item in items:
        assert item.title not in site_callout
        assert item.title not in daily_page
