"""Tests for u33 Steps 1 & 2 — watchlist weight sorting + lookahead D-N suffix."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.watchlist import (
    WatchlistConfig,
    match_watchlist_items,
    render_watchlist_impact,
)
from investo.models import NormalizedItem


def _item(*, source: str, title: str, scheduled_at: datetime | None = None) -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category="news",
        title=title,
        published_at=datetime(2026, 5, 9, tzinfo=UTC),
        scheduled_at=scheduled_at,
        raw_metadata={},
    )


# ---------------------------------------------------------------------------
# Step 1 — weight sorting
# ---------------------------------------------------------------------------


def test_matches_sorted_by_weight_desc() -> None:
    config = WatchlistConfig.model_validate(
        {
            "tickers": ["AAPL", "NVDA", "MSFT"],
            "weights": {"NVDA": 5.0, "AAPL": 1.0, "MSFT": 0.0},
        }
    )
    items = [
        _item(source="src", title="MSFT moves"),
        _item(source="src", title="AAPL moves"),
        _item(source="src", title="NVDA moves"),
    ]
    impact = match_watchlist_items(items, config)
    # Expect NVDA (5.0) → AAPL (1.0) → MSFT (0.0) ordering.
    assert [m.term for m in impact.matches] == ["NVDA", "AAPL", "MSFT"]


def test_unweighted_terms_break_alphabetically() -> None:
    config = WatchlistConfig.model_validate({"tickers": ["GOOGL", "AAPL"]})
    items = [
        _item(source="src", title="GOOGL moves"),
        _item(source="src", title="AAPL moves"),
    ]
    impact = match_watchlist_items(items, config)
    assert [m.term for m in impact.matches] == ["AAPL", "GOOGL"]


def test_negative_weights_rejected_at_validation() -> None:
    """Negative weights silently dropped — sorting falls back to alphabetical."""
    config = WatchlistConfig.model_validate({"tickers": ["NVDA"], "weights": {"NVDA": -1.0}})
    # Weight rejected; default 0.0 used.
    assert config.weights == {}


# ---------------------------------------------------------------------------
# Step 2 — lookahead D-N suffix
# ---------------------------------------------------------------------------


def test_render_appends_d_suffix_for_scheduled_match() -> None:
    config = WatchlistConfig.model_validate({"tickers": ["NVDA"]})
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    upcoming = _item(
        source="cal",
        title="NVDA earnings",
        scheduled_at=datetime(2026, 5, 12, 20, 0, tzinfo=UTC),  # +3d
    )
    impact = match_watchlist_items([upcoming], config)
    rendered = render_watchlist_impact(impact, now_utc=now)
    assert "NVDA D-3:" in rendered


def test_render_omits_d_suffix_when_now_utc_not_supplied() -> None:
    """Backward-compat: legacy callers without ``now_utc`` see the historic shape."""
    config = WatchlistConfig.model_validate({"tickers": ["NVDA"]})
    upcoming = _item(
        source="cal",
        title="NVDA earnings",
        scheduled_at=datetime(2026, 5, 12, tzinfo=UTC),
    )
    impact = match_watchlist_items([upcoming], config)
    rendered = render_watchlist_impact(impact)
    assert "D-" not in rendered


def test_render_skips_d_suffix_for_past_scheduled_at() -> None:
    """Items already past their scheduled time get no D- prefix."""
    config = WatchlistConfig.model_validate({"tickers": ["NVDA"]})
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    past = _item(
        source="cal",
        title="NVDA earnings (past)",
        scheduled_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    impact = match_watchlist_items([past], config)
    rendered = render_watchlist_impact(impact, now_utc=now)
    assert "D-" not in rendered


def test_render_skips_d_suffix_beyond_seven_days() -> None:
    """Far-future events fall outside the 7-day horizon."""
    config = WatchlistConfig.model_validate({"tickers": ["NVDA"]})
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    far = _item(
        source="cal",
        title="NVDA event (far)",
        scheduled_at=datetime(2026, 5, 30, tzinfo=UTC),
    )
    impact = match_watchlist_items([far], config)
    rendered = render_watchlist_impact(impact, now_utc=now)
    assert "D-" not in rendered


# ---------------------------------------------------------------------------
# Step 4 — multi-watchlist scopes
# ---------------------------------------------------------------------------


def test_for_segment_scope_returns_self_when_no_scopes() -> None:
    config = WatchlistConfig.model_validate({"tickers": ["NVDA"]})
    assert config.for_segment_scope("us-equity") is config


def test_for_segment_scope_merges_terms_for_matching_segment() -> None:
    config = WatchlistConfig.model_validate(
        {
            "tickers": ["NVDA"],
            "scopes": {
                "semis": {
                    "tickers": ["AMD", "AVGO"],
                    "segments": ["us-equity"],
                }
            },
        }
    )
    merged = config.for_segment_scope("us-equity")
    assert "NVDA" in merged.tickers
    assert "AMD" in merged.tickers
    assert "AVGO" in merged.tickers


def test_for_segment_scope_skips_scopes_bound_to_other_segments() -> None:
    config = WatchlistConfig.model_validate(
        {
            "tickers": ["NVDA"],
            "scopes": {
                "kr-only": {
                    "tickers": ["005930"],
                    "segments": ["domestic-equity"],
                }
            },
        }
    )
    merged = config.for_segment_scope("us-equity")
    assert "005930" not in merged.tickers
    # Unchanged tickers because no scope matches.
    assert merged.tickers == ("NVDA",)


def test_for_segment_scope_unbound_scope_applies_to_all_segments() -> None:
    config = WatchlistConfig.model_validate(
        {
            "tickers": ["NVDA"],
            "scopes": {
                "global": {"keywords": ["macro"]},
            },
        }
    )
    merged = config.for_segment_scope("crypto")
    assert "macro" in merged.keywords


def test_scope_weight_overrides_root_weight() -> None:
    config = WatchlistConfig.model_validate(
        {
            "tickers": ["NVDA"],
            "weights": {"NVDA": 1.0},
            "scopes": {
                "high-conviction": {
                    "weights": {"NVDA": 9.0},
                    "segments": ["us-equity"],
                }
            },
        }
    )
    merged = config.for_segment_scope("us-equity")
    assert merged.weights == {"NVDA": 9.0}
