"""Tests for the u18 + u28 watchlist relevance helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from investo.briefing.watchlist import (
    DEFAULT_BUNDLE_BADGE_LABEL,
    DEFAULT_CORE_ALIASES,
    WATCHLIST_CONFIG_ENV,
    WatchlistConfig,
    load_watchlist,
    match_watchlist_items,
    render_watchlist_impact,
    render_watchlist_prompt_context,
)
from investo.models import NormalizedItem


def _item(title: str, summary: str | None = None) -> NormalizedItem:
    return NormalizedItem(
        source_name="yahoo-finance-news",
        category="news",
        title=title,
        summary=summary,
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# u18 baseline regressions
# ---------------------------------------------------------------------------


def test_watchlist_config_normalizes_and_deduplicates_terms() -> None:
    config = WatchlistConfig(
        tickers=(" nvda ", "NVDA"),
        assets=("btc",),
        sectors=(" AI ",),
        keywords=("", "FOMC"),
    )

    assert config.tickers == ("NVDA",)
    assert config.assets == ("BTC",)
    assert config.sectors == ("AI",)
    assert config.keywords == ("FOMC",)
    assert config.is_configured
    assert not config.is_empty()


def test_match_watchlist_items_finds_ticker_asset_sector_and_keyword() -> None:
    config = WatchlistConfig(
        tickers=("NVDA",),
        assets=("BTC",),
        sectors=("semiconductor",),
        keywords=("FOMC",),
    )
    items = [
        _item("NVDA rallies after earnings", "semiconductor demand improves"),
        _item("Bitcoin ETF flow rises", "BTC liquidity improves"),
        _item("FOMC minutes published"),
    ]

    impact = match_watchlist_items(items, config)

    assert impact.configured
    assert impact.status == "matched"
    assert {match.term for match in impact.matches} == {"NVDA", "semiconductor", "BTC", "FOMC"}
    rendered = render_watchlist_impact(impact)
    assert "4건 확인" in rendered
    assert "NVDA" in rendered
    assert "BTC" in rendered
    assert "Watchlist relevance" in render_watchlist_prompt_context(impact)


def test_watchlist_no_match_does_not_invent_impact() -> None:
    impact = match_watchlist_items([_item("Local weather")], WatchlistConfig(tickers=("AAPL",)))

    assert impact.configured
    assert impact.status == "no_match"
    assert impact.matches == ()
    assert "직접 연결된 수집 항목 없음" in render_watchlist_impact(impact)
    assert "Do not invent personal impact" in render_watchlist_prompt_context(impact)


def test_empty_watchlist_is_explicitly_unconfigured() -> None:
    impact = match_watchlist_items([_item("NVDA rallies")], WatchlistConfig())

    assert not impact.configured
    assert impact.status == "unconfigured"
    assert impact.matches == ()
    assert "관심 목록 미설정" in render_watchlist_impact(impact)
    assert render_watchlist_prompt_context(impact) == ""


# ---------------------------------------------------------------------------
# u28 — Step 1: Onboarding nudge & site/telegram channel split
# ---------------------------------------------------------------------------


def test_unconfigured_site_channel_renders_onboarding_nudge() -> None:
    impact = match_watchlist_items([], WatchlistConfig())

    rendered = render_watchlist_impact(impact, channel="site")

    assert "관심 목록 미설정" in rendered
    assert "config/watchlist.json" in rendered
    assert "보유 종목 영향" in rendered


def test_unconfigured_telegram_channel_returns_empty_string() -> None:
    impact = match_watchlist_items([], WatchlistConfig())

    assert render_watchlist_impact(impact, channel="telegram") == ""


def test_is_empty_method_matches_unconfigured_impact() -> None:
    assert WatchlistConfig().is_empty()
    assert not WatchlistConfig(tickers=("AAPL",)).is_empty()


def test_load_watchlist_missing_path_activates_default_bundle(tmp_path: Path) -> None:
    config = load_watchlist(tmp_path / "missing-watchlist.json")

    assert config.is_default_bundle
    assert set(config.tickers) == set(DEFAULT_CORE_ALIASES)


def test_load_watchlist_empty_json_activates_default_bundle(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.json"
    path.write_text("{}", encoding="utf-8")

    assert load_watchlist(path).is_default_bundle


def test_load_watchlist_env_blank_uses_default_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(WATCHLIST_CONFIG_ENV, "   ")

    assert load_watchlist().is_default_bundle


def test_load_watchlist_existing_config_does_not_layer_default_bundle(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.json"
    path.write_text('{"tickers": ["KRW=X"]}', encoding="utf-8")

    config = load_watchlist(path)

    assert not config.is_default_bundle
    assert config.tickers == ("KRW=X",)
    assert "NVDA" not in config.tickers


def test_default_bundle_status_and_badge_label_are_pinned() -> None:
    impact = match_watchlist_items(
        [_item("NVIDIA and Bitcoin both rally")],
        WatchlistConfig.from_default_bundle(),
    )

    assert impact.status == "default_bundle"
    assert DEFAULT_BUNDLE_BADGE_LABEL == "기본 바스켓"
    rendered = render_watchlist_impact(impact)
    assert "(기본 바스켓)" in rendered


def test_default_bundle_without_matches_uses_unconfigured_branch() -> None:
    impact = match_watchlist_items(
        [_item("Local weather")],
        WatchlistConfig.from_default_bundle(),
    )

    assert not impact.configured
    assert impact.status == "unconfigured"
    assert impact.matches == ()


# ---------------------------------------------------------------------------
# u28 — Step 2: Alias mapping
# ---------------------------------------------------------------------------


def test_default_alias_bundle_covers_core_assets() -> None:
    # The persona-cited bundle: BTC↔Bitcoin↔비트코인, ETH↔Ethereum↔이더리움,
    # NVDA↔엔비디아 must all be present.
    assert "Bitcoin" in DEFAULT_CORE_ALIASES["BTC"]
    assert "비트코인" in DEFAULT_CORE_ALIASES["BTC"]
    assert "Ethereum" in DEFAULT_CORE_ALIASES["ETH"]
    assert "이더리움" in DEFAULT_CORE_ALIASES["ETH"]
    assert "엔비디아" in DEFAULT_CORE_ALIASES["NVDA"]
    assert "테슬라" in DEFAULT_CORE_ALIASES["TSLA"]


def test_alias_matches_korean_form_for_btc() -> None:
    config = WatchlistConfig(assets=("BTC",))
    items = [_item("비트코인 ETF 자금이 유입됐습니다")]

    impact = match_watchlist_items(items, config)

    assert impact.status == "matched"
    assert len(impact.matches) == 1
    match = impact.matches[0]
    # canonical term remains "BTC" so renderers stay deterministic.
    assert match.term == "BTC"
    assert match.matched_alias == "비트코인"


def test_alias_matches_english_long_name_for_nvda() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVIDIA reports record AI revenue")]

    impact = match_watchlist_items(items, config)

    assert len(impact.matches) == 1
    assert impact.matches[0].term == "NVDA"
    assert impact.matches[0].matched_alias == "NVIDIA"


def test_canonical_term_wins_over_alias() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA gains, NVIDIA upgrades guidance")]

    impact = match_watchlist_items(items, config)

    # The canonical "NVDA" should hit and the alias scan should NOT run for
    # the same term (matched_alias=None means canonical hit).
    assert len(impact.matches) == 1
    assert impact.matches[0].matched_alias is None


def test_user_alias_overrides_default_bundle_entry() -> None:
    config = WatchlistConfig(
        tickers=("BTC",),
        aliases={"BTC": ("DigitalGold",)},
    )
    items = [_item("DigitalGold flows resume")]

    impact = match_watchlist_items(items, config)

    assert len(impact.matches) == 1
    assert impact.matches[0].matched_alias == "DigitalGold"


def test_user_alias_override_drops_default_korean_alias() -> None:
    """User override replaces the entire bundle entry, not merge per-value."""
    config = WatchlistConfig(
        tickers=("BTC",),
        aliases={"BTC": ("DigitalGold",)},
    )
    items = [_item("비트코인 자금 유입")]

    impact = match_watchlist_items(items, config)

    # The default ("Bitcoin", "비트코인") entry was overridden by user, so
    # 비트코인 should no longer match.
    assert impact.status == "no_match"


# ---------------------------------------------------------------------------
# u28 — Step 3: Korean word boundary + short-ticker guard
# ---------------------------------------------------------------------------


def test_korean_term_does_not_partial_match_inside_compound() -> None:
    # "삼성" should NOT match "삼성전자" or "삼성생명" (Hangul-syllable
    # neighbour suppresses the hit).
    config = WatchlistConfig(keywords=("삼성",))
    items = [
        _item("삼성전자가 신제품을 발표했다"),
        _item("삼성생명 4월 실적 발표"),
    ]

    impact = match_watchlist_items(items, config)

    assert impact.status == "no_match"


def test_korean_term_matches_at_punctuation_or_whitespace_boundary() -> None:
    config = WatchlistConfig(keywords=("삼성",))
    items = [
        _item("삼성, 신규 투자 발표"),
        _item("오늘 삼성 그룹 회장 인터뷰"),
        _item("삼성·SDI 합병 루머"),
    ]

    impact = match_watchlist_items(items, config)

    assert impact.status == "matched"
    assert len(impact.matches) == 3


def test_short_ticker_requires_uppercase_boundary() -> None:
    # 1-character ticker "F" must NOT match "for" / "From" (lowercase or
    # mid-word). It MUST match "F " (boundary) and "(F)" (parens).
    config = WatchlistConfig(tickers=("F",))
    items = [
        _item("Ford up: a strong push for new EV"),  # has 'F' in 'Ford' / 'for'
        _item("F shares jump 5% on guidance lift"),
        _item("Earnings recap (F): strong quarter"),
    ]

    impact = match_watchlist_items(items, config)

    matched_titles = {m.item.title for m in impact.matches}
    assert any("F shares jump" in t for t in matched_titles)
    assert any("(F)" in t for t in matched_titles)
    # "Ford"/"for" must not produce a 1-char F match.
    assert not any("Ford up" in t for t in matched_titles)


def test_short_ticker_two_char_lowercase_does_not_match() -> None:
    # "BA" must NOT match "Bay" or "barrel" (any lowercase boundary).
    config = WatchlistConfig(tickers=("BA",))
    items = [
        _item("Boeing (BA) climbs on order book"),
        _item("Bay Area barrel demand softens"),
    ]

    impact = match_watchlist_items(items, config)

    matched_titles = {m.item.title for m in impact.matches}
    assert any("(BA)" in t for t in matched_titles)
    assert not any("Bay Area" in t for t in matched_titles)


def test_exact_match_terms_disable_alias_and_substring() -> None:
    config = WatchlistConfig(
        tickers=("BTC",),
        exact_match_terms=("BTC",),
    )
    # 비트코인 alias is suppressed under exact_match.
    impact_alias = match_watchlist_items([_item("비트코인 자금 유입")], config)
    assert impact_alias.status == "no_match"

    # Exact "BTC" still matches when standalone.
    impact_exact = match_watchlist_items([_item("BTC up 3% today")], config)
    assert impact_exact.status == "matched"


# ---------------------------------------------------------------------------
# u28 — Step 4: Coverage hold branch + cap split
# ---------------------------------------------------------------------------


def test_coverage_hold_branch_returns_pending_render() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA rallies after earnings")]

    impact = match_watchlist_items(items, config, coverage_status="insufficient")

    assert impact.status == "coverage_hold"
    # Even though the items would have matched, the matcher does not surface
    # them under insufficient coverage — the renderer must say "보류".
    assert impact.matches == ()
    rendered = render_watchlist_impact(impact)
    assert "데이터 수집 부족" in rendered
    assert "매칭 판단 보류" in rendered


def test_coverage_hold_telegram_channel_uses_same_hold_text() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    impact = match_watchlist_items([], config, coverage_status="insufficient")

    rendered = render_watchlist_impact(impact, channel="telegram")
    # Same body text — the per-channel filtering happens in notifier/summary
    # which strips the "/ 관심:" suffix when this prefix is present.
    assert "데이터 수집 부족" in rendered


def test_coverage_hold_prompt_context_warns_llm() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    impact = match_watchlist_items([], config, coverage_status="insufficient")

    context = render_watchlist_prompt_context(impact)
    assert "insufficient" in context
    assert "do not infer" in context.lower() or "Do not infer" in context


def test_partial_coverage_does_not_hold() -> None:
    config = WatchlistConfig(tickers=("NVDA",))
    items = [_item("NVDA rallies after earnings")]

    impact = match_watchlist_items(items, config, coverage_status="partial")

    assert impact.status == "matched"
    assert len(impact.matches) == 1


def test_site_channel_caps_at_five_telegram_at_three() -> None:
    config = WatchlistConfig(keywords=("AI",))
    items = [_item(f"AI item {i} mentions ai investment") for i in range(7)]

    impact = match_watchlist_items(items, config)
    site = render_watchlist_impact(impact, channel="site")
    telegram = render_watchlist_impact(impact, channel="telegram")

    # Site cap: 5 entries rendered, "외" suffix because total > cap.
    assert "7건 확인" in site
    assert site.count("AI item") == 5
    assert site.endswith(" 외")

    # Telegram cap: 3 entries.
    assert "7건 확인" in telegram
    assert telegram.count("AI item") == 3
    assert telegram.endswith(" 외")


# ---------------------------------------------------------------------------
# u28 — Cross-cutting: no secret leak, alias normalization
# ---------------------------------------------------------------------------


def test_aliases_normalize_canonical_key_to_uppercase_for_ascii() -> None:
    config = WatchlistConfig(
        tickers=("BTC",),
        aliases={"btc": ("Bitcoin",)},
    )
    items = [_item("Bitcoin price surges")]

    impact = match_watchlist_items(items, config)
    assert len(impact.matches) == 1


def test_alias_validator_drops_blank_entries_and_dedupes() -> None:
    config = WatchlistConfig(
        tickers=("BTC",),
        aliases={"BTC": ("Bitcoin", "", "Bitcoin", "비트코인")},
    )

    assert config.aliases["BTC"] == ("Bitcoin", "비트코인")


# ---------------------------------------------------------------------------
# u28 QA M3 — short keyword/sector are case-insensitive (false-negative fix)
# ---------------------------------------------------------------------------


def test_short_keyword_is_case_insensitive() -> None:
    # "EV" is a 2-char ASCII keyword (a semantic concept, not an exchange
    # ticker) — it must match lowercase "ev" inside a summary. Prior to the
    # M3 fix this fell through the short-ticker capitalize guard and produced
    # a false negative.
    config = WatchlistConfig(keywords=("EV",))
    items = [
        _item("Ford rolls out new ev launch this quarter"),
        _item("Steel prices steady today"),
    ]

    impact = match_watchlist_items(items, config)

    matched_titles = {m.item.title for m in impact.matches}
    assert any("new ev launch" in t for t in matched_titles)
    assert not any("Steel prices" in t for t in matched_titles)


def test_short_sector_is_case_insensitive() -> None:
    # Same fix path for ``sectors`` — "AI" must match lowercase "ai".
    config = WatchlistConfig(sectors=("AI",))
    items = [_item("New ai cluster opens in Texas")]

    impact = match_watchlist_items(items, config)

    assert impact.status == "matched"
    assert len(impact.matches) == 1


def test_short_ticker_remains_case_sensitive() -> None:
    # Regression pin for the prior behaviour: 1-char ticker "F" must still
    # require an uppercase boundary in the raw text, so "for" / "Ford" do not
    # produce false positives even after the M3 fix introduces kind-aware
    # branching.
    config = WatchlistConfig(tickers=("F",))
    items = [
        _item("Ford up: a strong push for new launch"),
        _item("F shares jump 5% on guidance lift"),
    ]

    impact = match_watchlist_items(items, config)

    matched_titles = {m.item.title for m in impact.matches}
    assert any("F shares jump" in t for t in matched_titles)
    assert not any("Ford up" in t for t in matched_titles)


# ---------------------------------------------------------------------------
# u28 QA M5 — defensive empty-term guard in _matches_korean_term
# ---------------------------------------------------------------------------


def test_matches_korean_term_empty_term_returns_false() -> None:
    # Internal helper: an empty ``term_cf`` must short-circuit to False even
    # though str.find("") returns 0. Pins the defensive guard so a future
    # caller change cannot silently reintroduce a "match every item" bug.
    from investo.briefing.watchlist import _matches_korean_term

    assert _matches_korean_term("", "본문 텍스트") is False
    assert _matches_korean_term("", "") is False
