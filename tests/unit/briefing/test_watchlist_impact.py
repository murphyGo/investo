"""Tests for the u73 watchlist impact center (grouping layer over u64)."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.watchlist import (
    WatchlistConfig,
    match_watchlist_items,
)
from investo.briefing.watchlist_impact import (
    RejectedCandidate,
    WatchlistImpactCenter,
    build_impact_center,
    public_impact,
)
from investo.models import NormalizedItem


def _item(
    title: str,
    summary: str | None = None,
    *,
    source_name: str = "yahoo-finance-news",
    raw_metadata: dict[str, str] | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="news",
        title=title,
        summary=summary,
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata=raw_metadata or {},
    )


# ---------------------------------------------------------------------------
# AC-73.1 — four-group classification
# ---------------------------------------------------------------------------


def test_structured_symbol_hit_is_direct() -> None:
    config = WatchlistConfig(tickers=("BTC",))
    items = [_item("Daily crypto roundup", raw_metadata={"symbol": "BTC-USD"})]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.direct) == 1
    assert center.direct[0].confidence == "structured"
    assert not center.related
    assert not center.uncertain


def test_strict_ticker_boundary_hit_is_direct() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA rallies after earnings beat")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.direct) == 1
    assert center.direct[0].confidence == "strict"


def test_alias_ticker_hit_is_direct() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVIDIA unveils new GPU lineup")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.direct) == 1
    assert center.direct[0].confidence == "alias"


def test_sector_keyword_text_hit_is_related() -> None:
    config = WatchlistConfig(sectors=("semiconductor",))
    items = [_item("The semiconductor cycle shows signs of recovery")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert not center.direct
    assert len(center.related) == 1
    assert center.related[0].kind == "sector"


def test_short_keyword_text_hit_is_uncertain() -> None:
    config = WatchlistConfig(keywords=("EV",))
    items = [_item("A new ev launch was announced today")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert not center.direct
    assert not center.related
    assert len(center.uncertain) == 1


def test_classification_table_maps_reasons_to_groups() -> None:
    """AC-73.1 — common match shapes land in the documented groups."""
    cases = [
        (WatchlistConfig(tickers=("BTC",)), {"symbol": "BTC-USD"}, "Crypto roundup", "direct"),
        (WatchlistConfig(tickers=("NVDA",)), {}, "NVDA earnings beat", "direct"),
        (WatchlistConfig(assets=("Bitcoin",)), {}, "Bitcoin rally continues", "direct"),
        (WatchlistConfig(sectors=("semiconductor",)), {}, "semiconductor demand", "related"),
        (WatchlistConfig(keywords=("EV",)), {}, "new ev model", "uncertain"),
    ]
    for config, meta, title, expected_group in cases:
        items = [_item(title, raw_metadata=meta)]
        center = build_impact_center(
            match_watchlist_items(items, config), items=items, config=config
        )
        bucket = {
            "direct": center.direct,
            "related": center.related,
            "uncertain": center.uncertain,
        }[expected_group]
        assert len(bucket) == 1, f"{title!r} expected in {expected_group}"


# ---------------------------------------------------------------------------
# AC-73.2 — short-ticker false-positive rejection (SOL / BTC families)
# ---------------------------------------------------------------------------


def test_btc_btm_near_miss_is_rejected_not_matched() -> None:
    config = WatchlistConfig(tickers=("BTC",))
    items = [_item("BTM Corp announces acquisition")]
    impact = match_watchlist_items(items, config)
    # u64 correctly does not match BTC against BTM.
    assert impact.status == "no_match"
    center = build_impact_center(impact, items=items, config=config)
    assert not center.direct
    assert len(center.rejected) == 1
    assert center.rejected[0].term == "BTC"
    assert center.rejected[0].token == "BTM"
    assert center.rejected[0].reason == "short-ticker-boundary"


def test_btc_btcs_near_miss_is_rejected() -> None:
    config = WatchlistConfig(tickers=("BTC",))
    items = [_item("BTCS Inc shares jump on crypto custody news")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert not center.direct
    assert any(r.token == "BTCS" for r in center.rejected)


def test_sol_slgl_near_miss_is_rejected() -> None:
    config = WatchlistConfig(tickers=("SOL",))
    items = [_item("SLGL biotech reports trial data")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert not center.direct
    assert any(r.token == "SLGL" for r in center.rejected)


def test_sol_solana_company_without_alias_is_not_direct() -> None:
    """Generic Solana-company text without configured alias must not be Direct."""
    config = WatchlistConfig(tickers=("SOL",), exact_match_terms=("sol",))
    items = [_item("Solana Inc, an unrelated company, files paperwork")]
    impact = match_watchlist_items(items, config)
    center = build_impact_center(impact, items=items, config=config)
    assert not center.direct


def test_valid_btc_alias_still_matches_direct() -> None:
    """AC-73.2 — valid alias preserved while near-miss tokens reject."""
    config = WatchlistConfig(tickers=("BTC",))
    items = [
        _item("Bitcoin surges past resistance"),
        _item("BTM Corp unrelated news"),
    ]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.direct) == 1
    assert center.direct[0].matched_alias == "Bitcoin"
    assert any(r.token == "BTM" for r in center.rejected)


def test_structured_sol_usd_still_matches_direct() -> None:
    config = WatchlistConfig(tickers=("SOL",))
    items = [_item("Crypto prices update", raw_metadata={"symbol": "SOL-USD"})]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.direct) == 1
    assert not center.rejected


def test_accepted_term_is_never_also_rejected() -> None:
    """An item that legitimately matched must not appear in rejected too."""
    config = WatchlistConfig(tickers=("BTC",))
    items = [_item("BTC and BTM both mentioned here")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.direct) == 1
    # BTM still flagged as a near-miss; BTC itself not rejected.
    assert all(r.term == "BTC" and r.token != "BTC" for r in center.rejected)


def test_rejected_records_are_bounded() -> None:
    config = WatchlistConfig(tickers=("BTC",))
    items = [_item(f"BTM{i} report number {i}") for i in range(60)]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert len(center.rejected) <= 25


# ---------------------------------------------------------------------------
# Redaction safety
# ---------------------------------------------------------------------------


def test_rejected_redacted_line_omits_title() -> None:
    candidate = RejectedCandidate(
        term="BTC",
        kind="ticker",
        token="BTM",
        source_name="yahoo-finance-news",
        reason="short-ticker-boundary",
        title_hash="ab12cd",
    )
    line = candidate.redacted_line()
    assert "BTC" in line
    assert "BTM" in line
    assert "short-ticker-boundary" in line
    assert "yahoo-finance-news" in line
    assert "#ab12cd" in line


def test_rejected_scan_skipped_without_items() -> None:
    config = WatchlistConfig(tickers=("BTC",))
    items = [_item("BTM Corp news")]
    center = build_impact_center(match_watchlist_items(items, config))
    assert center.rejected == ()


# ---------------------------------------------------------------------------
# AC-73.4 — public projection drops diagnostics
# ---------------------------------------------------------------------------


def test_public_impact_contains_only_direct_and_related() -> None:
    config = WatchlistConfig(tickers=("NVDA",), keywords=("EV",))
    items = [
        _item("NVDA earnings beat"),
        _item("new ev model launch"),
    ]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert center.direct  # NVDA
    assert center.uncertain  # EV
    pub = public_impact(center)
    # Public impact carries only direct+related — the EV uncertain match is gone.
    assert all(m.term != "EV" for m in pub.matches)
    assert any(m.term == "NVDA" for m in pub.matches)


def test_public_impact_no_public_eligible_is_no_match() -> None:
    config = WatchlistConfig(keywords=("EV",))
    items = [_item("a new ev launch")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert center.uncertain
    pub = public_impact(center)
    assert pub.matches == ()
    assert pub.status == "no_match"


def test_public_impact_carries_through_unconfigured() -> None:
    config = WatchlistConfig()
    center = build_impact_center(match_watchlist_items([_item("x")], config))
    assert not center.configured
    pub = public_impact(center)
    assert pub.status == "unconfigured"
    assert not pub.configured


def test_public_impact_carries_through_coverage_hold() -> None:
    config = WatchlistConfig(tickers=("BTC",))
    impact = match_watchlist_items([_item("x")], config, coverage_status="failed")
    center = build_impact_center(impact)
    pub = public_impact(center)
    assert pub.status == "coverage_hold"
    assert pub.matches == ()


def test_telegram_render_has_no_diagnostic_leak() -> None:
    """AC-73.4 — diagnostics never reach the public render surface.

    The public projection feeds the same ``render_watchlist_impact``
    path the briefing body + Telegram one-liner use. A center holding
    only uncertain + rejected records must render an empty / no-match
    Telegram surface with no reason codes or offending tokens leaked.
    """
    from investo.briefing.watchlist import render_watchlist_impact

    config = WatchlistConfig(keywords=("EV",), tickers=("BTC",))
    items = [_item("a new ev launch and BTM Corp news")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    # Sanity: this day produced only diagnostics.
    assert center.uncertain
    assert center.rejected
    assert not center.has_public_impacts

    pub = public_impact(center)
    telegram = render_watchlist_impact(pub, channel="telegram")
    site = render_watchlist_impact(pub, channel="site")
    for surface in (telegram, site):
        assert "short-ticker-boundary" not in surface
        assert "BTM" not in surface
        assert "⊘" not in surface
        assert "진단" not in surface


def test_center_helpers() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA up")]
    center = build_impact_center(match_watchlist_items(items, config), items=items, config=config)
    assert isinstance(center, WatchlistImpactCenter)
    assert center.has_public_impacts
    assert center.public_matches()[0].term == "NVDA"
