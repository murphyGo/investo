"""u47 — personal-finance noise filter regression tests.

Pins ``YahooFinanceNewsAdapter._personal_finance_patterns_hit`` and the
batch-level INFO/WARNING canary log emitted by ``fetch()``. Triggered
by the 2026-05-09 cron US-equity quality retro: ~10 of 24 in-window
items were generic personal-finance product comparisons (CD rates /
HELOC / mortgage / savings / insurance / retirement) that diluted the
Stage 1 LLM token budget and the Stage 2 candidate pool.

Synthetic XML payloads are used for the filter regression because the
patterns themselves are headline / URL / source-text shaped — the
existing ``feed.xml`` real-recording fixture exercises the field-mapping
contract and is left unchanged (R10).
"""

from __future__ import annotations

import logging
from datetime import date

import pytest

from investo.sources._window import FetchWindow
from investo.sources.yahoo_finance_news import (
    _PERSONAL_FINANCE_DENY_PATTERNS,
    YahooFinanceNewsAdapter,
    _personal_finance_patterns_hit,
)
from tests.unit.sources._mock_transport import mock_client as _mock_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap(items_xml: str) -> bytes:
    """Wrap a sequence of <item>...</item> blocks in a minimal RSS 2.0 doc."""
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<rss version="2.0"><channel><title>Synthetic</title>\n'
        + items_xml.encode("utf-8")
        + b"</channel></rss>"
    )


def _item(
    title: str,
    *,
    link: str = "https://finance.yahoo.com/news/x.html",
    pubdate: str = "2026-04-29T14:00:00Z",
    guid: str = "g",
    source_text: str | None = None,
) -> str:
    src_block = f'<source url="https://example.com/">{source_text}</source>' if source_text else ""
    return (
        "<item>"
        f"<title>{title}</title>"
        f"<link>{link}</link>"
        f"<pubDate>{pubdate}</pubDate>"
        f"<guid>{guid}</guid>"
        f"{src_block}"
        "</item>\n"
    )


_WINDOW = FetchWindow.from_kst_date(date(2026, 4, 29))


# ---------------------------------------------------------------------------
# Pure helper — pattern matcher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Best CD rates today, May 8, 2026 (up to 4% APY return)",
        "HELOC and home equity loan rates today, May 8, 2026",
        "Home equity loan rates today: lock in before next Fed cut",
        "Mortgage and refinance interest rates today, May 8, 2026",
        "Mortgage and refi rates today: 30-year hits 6.5%",
        "Best high-yield savings interest rates today, May 8, 2026",
        "Best money market account rates today, May 8, 2026 (up to ...)",
        "Is $7,000 Per Year Too High for Long-Term Care Insurance?",
        "Hidden Retirement Costs You Should Plan For, According to ...",
    ],
)
def test_helper_matches_each_title_only_pattern(title: str) -> None:
    hits = _personal_finance_patterns_hit(title=title, url="", rss_source="")
    assert hits, f"expected at least one deny pattern hit for: {title}"


def test_helper_matches_personal_finance_via_url() -> None:
    # Yahoo flags product-comparison stories with the personal-finance
    # URL prefix; the headline itself rarely contains the literal phrase.
    hits = _personal_finance_patterns_hit(
        title="What is DeFi? A complete guide to decentralized finance.",
        url="https://finance.yahoo.com/personal-finance/investing/article/what-is-defi.html",
        rss_source="",
    )
    assert "personal finance" in hits


def test_helper_matches_personal_finance_via_source_text() -> None:
    hits = _personal_finance_patterns_hit(
        title="Does homeowners insurance cover water damage?",
        url="https://finance.yahoo.com/news/x.html",
        rss_source="Yahoo Personal Finance",
    )
    assert "personal finance" in hits


def test_helper_is_case_insensitive() -> None:
    assert _personal_finance_patterns_hit("BEST CD RATES TODAY", "", "") == ("cd rates",)
    assert _personal_finance_patterns_hit("HELOC EXPLAINED", "", "") == ("heloc",)


def test_helper_returns_empty_for_market_signal_titles() -> None:
    # Five canonical positive cases per plan DoD.
    market_titles = [
        "S&P 500 reaches new high",
        "Tesla Q1 earnings beat estimates",
        "Federal Reserve holds rates steady",
        "Apple unveils new chip at WWDC",
        "TSMC sales decelerate amid AI pause",
    ]
    for title in market_titles:
        assert _personal_finance_patterns_hit(title, "", "") == (), (
            f"false positive on market title: {title}"
        )


def test_helper_returns_sorted_deduped_patterns() -> None:
    # Title contains both "cd rates" and "heloc" → deterministic sort.
    title = "Best CD rates and HELOC explainers for May 2026"
    hits = _personal_finance_patterns_hit(title, "", "")
    assert hits == ("cd rates", "heloc")


def test_deny_patterns_constant_shape() -> None:
    # Sanity: the constant covers the 9 plan-DoD patterns + is all
    # lowercase substring tokens (no regex metachars except hyphen).
    assert isinstance(_PERSONAL_FINANCE_DENY_PATTERNS, tuple)
    assert len(_PERSONAL_FINANCE_DENY_PATTERNS) == 10  # 9 base + 1 mortgage variant
    for pattern in _PERSONAL_FINANCE_DENY_PATTERNS:
        assert pattern == pattern.lower()
        assert pattern.strip() == pattern


# ---------------------------------------------------------------------------
# Adapter integration — filter is applied during fetch()
# ---------------------------------------------------------------------------


async def test_pure_deny_batch_yields_zero_items() -> None:
    body = _wrap(
        _item("Best CD rates today, May 8, 2026", guid="g1")
        + _item("HELOC and home equity loan rates today, May 8, 2026", guid="g2")
        + _item("Mortgage and refinance interest rates today", guid="g3")
        + _item("Best high-yield savings interest rates today", guid="g4")
        + _item("Best money market account rates today", guid="g5")
        + _item("Is $7,000 Per Year Too High for Long-Term Care Insurance?", guid="g6")
    )
    adapter = YahooFinanceNewsAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


async def test_pure_market_signal_batch_preserves_all_items() -> None:
    body = _wrap(
        _item("S&amp;P 500 reaches new high", guid="g1")
        + _item("Tesla Q1 earnings beat estimates", guid="g2")
        + _item("Federal Reserve holds rates steady", guid="g3")
        + _item("Apple unveils new chip at WWDC", guid="g4")
        + _item("TSMC sales decelerate amid AI pause", guid="g5")
    )
    adapter = YahooFinanceNewsAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 5
    titles = [item.title for item in items]
    # XML entity ``&amp;`` → ``&`` after parse.
    assert "S&P 500 reaches new high" in titles
    assert "Tesla Q1 earnings beat estimates" in titles


async def test_mixed_batch_filters_only_deny_items() -> None:
    body = _wrap(
        _item("Best CD rates today, May 8, 2026", guid="g1")
        + _item("HELOC and home equity loan rates today", guid="g2")
        + _item("Mortgage and refinance interest rates today", guid="g3")
        + _item("S&amp;P 500 reaches new high", guid="g4")
        + _item("Tesla Q1 earnings beat estimates", guid="g5")
    )
    adapter = YahooFinanceNewsAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 2
    titles = {item.title for item in items}
    assert titles == {"S&P 500 reaches new high", "Tesla Q1 earnings beat estimates"}


async def test_personal_finance_url_prefix_filters_neutral_title(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Yahoo's personal-finance URL category prefix should block items
    # whose headline alone would not match any pattern.
    body = _wrap(
        _item(
            "What is DeFi? A complete guide to decentralized finance.",
            link="https://finance.yahoo.com/personal-finance/investing/article/defi.html",
            guid="g1",
        )
        + _item("S&amp;P 500 reaches new high", guid="g2")
    )
    adapter = YahooFinanceNewsAdapter()
    with caplog.at_level(logging.INFO, logger="investo.sources.yahoo_finance_news"):
        async with _mock_client(body) as client:
            items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].title == "S&P 500 reaches new high"
    assert any("personal finance" in record.getMessage() for record in caplog.records), (
        "expected canary log to mention the personal-finance pattern"
    )


async def test_canary_info_log_emitted_on_partial_filter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = _wrap(
        _item("Best CD rates today, May 8, 2026", guid="g1")
        + _item("HELOC explainer", guid="g2")
        + _item("Mortgage and refinance interest rates today", guid="g3")
        + _item("S&amp;P 500 reaches new high", guid="g4")
        + _item("Tesla Q1 earnings beat estimates", guid="g5")
    )
    adapter = YahooFinanceNewsAdapter()
    with caplog.at_level(logging.INFO, logger="investo.sources.yahoo_finance_news"):
        async with _mock_client(body) as client:
            await adapter.fetch(client, _WINDOW)
    canaries = [
        record
        for record in caplog.records
        if record.name == "investo.sources.yahoo_finance_news" and "filtered" in record.getMessage()
    ]
    assert len(canaries) == 1
    canary = canaries[0]
    assert canary.levelno == logging.INFO
    assert "filtered 3/5 items" in canary.getMessage()
    # Structured ``extra`` preserved for downstream log processors. The
    # logging module sets these as instance attributes on ``LogRecord``,
    # so direct access is the supported public surface.
    assert canary.filtered == 3  # type: ignore[attr-defined]
    assert canary.total == 5  # type: ignore[attr-defined]
    assert set(canary.patterns_hit) == {  # type: ignore[attr-defined]
        "cd rates",
        "heloc",
        "mortgage and refinance",
    }


async def test_canary_warning_log_emitted_on_full_filter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = _wrap(
        _item("Best CD rates today, May 8, 2026", guid="g1") + _item("HELOC explainer", guid="g2")
    )
    adapter = YahooFinanceNewsAdapter()
    with caplog.at_level(logging.INFO, logger="investo.sources.yahoo_finance_news"):
        async with _mock_client(body) as client:
            items = await adapter.fetch(client, _WINDOW)
    assert items == []
    canaries = [
        record
        for record in caplog.records
        if record.name == "investo.sources.yahoo_finance_news" and "filtered" in record.getMessage()
    ]
    assert len(canaries) == 1
    assert canaries[0].levelno == logging.WARNING
    assert "filtered 2/2 items" in canaries[0].getMessage()


async def test_no_log_when_nothing_filtered(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = _wrap(
        _item("S&amp;P 500 reaches new high", guid="g1")
        + _item("Tesla Q1 earnings beat estimates", guid="g2")
    )
    adapter = YahooFinanceNewsAdapter()
    with caplog.at_level(logging.INFO, logger="investo.sources.yahoo_finance_news"):
        async with _mock_client(body) as client:
            items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 2
    canaries = [
        record
        for record in caplog.records
        if record.name == "investo.sources.yahoo_finance_news" and "filtered" in record.getMessage()
    ]
    assert canaries == []


async def test_no_log_when_no_in_window_items(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # All items outside the KST 2026-04-29 window. Filter should not
    # emit (zero-item collection is the aggregator's domain).
    body = _wrap(
        _item("Best CD rates today", guid="g1", pubdate="2027-05-01T00:00:00Z")
        + _item("S&amp;P 500 reaches new high", guid="g2", pubdate="2027-05-01T00:00:00Z")
    )
    adapter = YahooFinanceNewsAdapter()
    with caplog.at_level(logging.INFO, logger="investo.sources.yahoo_finance_news"):
        async with _mock_client(body) as client:
            items = await adapter.fetch(client, _WINDOW)
    assert items == []
    canaries = [
        record
        for record in caplog.records
        if record.name == "investo.sources.yahoo_finance_news" and "filtered" in record.getMessage()
    ]
    assert canaries == []
