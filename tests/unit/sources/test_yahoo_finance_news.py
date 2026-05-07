"""Tests for ``investo.sources.yahoo_finance_news.YahooFinanceNewsAdapter``.

Pins the algorithm from FD L6.5 (Extension #2 2026-05-01) against:

* The recorded real-feed fixture (`fixtures/api/yahoo-finance-news/feed.xml`)
  — field mapping, ISO 8601 `Z` → tz-aware UTC parsing, window filtering.
* Inline synthetic XML — AC-7.2 (HTML in title stripped), AC-7.3
  (non-http/https URLs dropped), edge cases (missing <source>,
  missing required fields, naive pubDate, malformed XML).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.yahoo_finance_news import YahooFinanceNewsAdapter
from tests.unit.sources._mock_transport import mock_client as _mock_client

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "yahoo-finance-news"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"


# ---------------------------------------------------------------------------
# Real fixture — happy path
# ---------------------------------------------------------------------------


async def test_fetch_returns_items_within_window() -> None:
    # KST 2026-04-29 → UTC [2026-04-28 15:00, 2026-04-29 15:00). The
    # fixture has many entries dated "2026-04-29T14:xx:xxZ" which fall
    # in this window. Older 2024 entries are out.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) >= 3
    assert all(item.source_name == "yahoo-finance-news" for item in items)
    assert all(item.category == "news" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = YahooFinanceNewsAdapter()
    # Far-future date; recorded fixture has no entries that recent.
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    # AC-7.4 — every returned item has tz-aware published_at, in UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_summary_always_none() -> None:
    # L6.5 specific: Yahoo's rssindex feed has no <description>; every
    # emitted item carries summary=None (not ""). The model
    # _normalize_optional_summary already collapses "" → None, but the
    # adapter sets None explicitly so the contract is intentional.
    body = _REAL_FIXTURE.read_bytes()
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    assert all(item.summary is None for item in items)


async def test_fetch_url_is_http_or_https() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.url is not None
        assert str(item.url).startswith(("http://", "https://"))


async def test_fetch_raw_metadata_keys_are_strings() -> None:
    # R8: raw_metadata values must be strings (DEBT-028 guardrail).
    body = _REAL_FIXTURE.read_bytes()
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert set(item.raw_metadata.keys()) == {"guid", "rss_source"}
        for value in item.raw_metadata.values():
            assert isinstance(value, str)


async def test_fetch_sends_browser_user_agent() -> None:
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers["user-agent"])
        return httpx.Response(
            200,
            content=_REAL_FIXTURE.read_bytes(),
            headers={"content-type": "application/xml"},
        )

    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await adapter.fetch(client, window)

    assert seen_headers == [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    ]


# ---------------------------------------------------------------------------
# Lead concern #2: <source> element may be missing on some items.
# Synthetic — must default rss_source="" rather than crash.
# ---------------------------------------------------------------------------


_SYNTH_NO_SOURCE_ELEM = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Synthetic</title>
  <item>
    <title>Yahoo-internal story without source element</title>
    <link>https://finance.yahoo.com/news/x.html</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
    <guid isPermaLink="false">x</guid>
  </item>
</channel></rss>
"""


async def test_missing_source_element_defaults_to_empty_string() -> None:
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(_SYNTH_NO_SOURCE_ELEM) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["rss_source"] == ""
    assert items[0].raw_metadata["guid"] == "x"


# ---------------------------------------------------------------------------
# AC-7.2 — HTML in <title> stripped
# ---------------------------------------------------------------------------


_SYNTH_HTML_IN_TITLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Synthetic</title>
  <item>
    <title>&lt;b&gt;Breaking&lt;/b&gt; news headline</title>
    <link>https://finance.yahoo.com/news/x.html</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
    <guid>g1</guid>
    <source url="https://example.com/">Example</source>
  </item>
</channel></rss>
"""


async def test_html_in_title_is_stripped() -> None:
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(_SYNTH_HTML_IN_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Breaking news headline"


# ---------------------------------------------------------------------------
# AC-7.3 — non-http/https schemes dropped
# ---------------------------------------------------------------------------


_SYNTH_BAD_URL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Synthetic</title>
  <item>
    <title>Good entry</title>
    <link>https://finance.yahoo.com/news/good.html</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
    <guid>g1</guid>
  </item>
  <item>
    <title>file:// URL entry</title>
    <link>file:///etc/passwd</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
    <guid>g2</guid>
  </item>
  <item>
    <title>javascript: URL entry</title>
    <link>javascript:alert(1)</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
    <guid>g3</guid>
  </item>
</channel></rss>
"""


async def test_non_http_https_urls_dropped() -> None:
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(_SYNTH_BAD_URL) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Good entry"


# ---------------------------------------------------------------------------
# Edge cases: naive pubDate, missing fields, empty feed, malformed XML
# ---------------------------------------------------------------------------


async def test_naive_or_garbage_pubdate_is_dropped() -> None:
    # Two failure modes: (a) ISO 8601 without offset parses successfully
    # but is naive (tzinfo is None) — must be dropped per R8 / AC-7.4;
    # (b) RFC 822 form (or any non-ISO input) raises ValueError out of
    # ``datetime.fromisoformat`` and is dropped.
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Naive ISO 8601</title>
    <link>https://finance.yahoo.com/news/x.html</link>
    <pubDate>2026-04-29T14:00:00</pubDate>
    <guid>g1</guid>
  </item>
  <item>
    <title>RFC 822 garbage to fromisoformat</title>
    <link>https://finance.yahoo.com/news/y.html</link>
    <pubDate>Wed, 29 Apr 2026 14:00:00 -0000</pubDate>
    <guid>g2</guid>
  </item>
  <item>
    <title>Wholly unparseable</title>
    <link>https://finance.yahoo.com/news/z.html</link>
    <pubDate>not a date at all</pubDate>
    <guid>g3</guid>
  </item>
</channel></rss>
"""
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_missing_required_fields_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Has everything</title>
    <link>https://finance.yahoo.com/news/x.html</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
  </item>
  <item>
    <title>Missing pubDate</title>
    <link>https://finance.yahoo.com/news/y.html</link>
  </item>
  <item>
    <link>https://finance.yahoo.com/news/z.html</link>
    <pubDate>2026-04-29T14:00:00Z</pubDate>
  </item>
</channel></rss>
"""
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Has everything"


async def test_empty_channel_returns_empty_list() -> None:
    body = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rss version="2.0"><channel><title>Empty</title></channel></rss>'
    )
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = YahooFinanceNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 29))

    async with _mock_client(b"<not xml") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Adapter identity (ClassVar attributes)
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert YahooFinanceNewsAdapter.name == "yahoo-finance-news"
    assert YahooFinanceNewsAdapter.category == "news"
    assert YahooFinanceNewsAdapter._FEED_URL == "https://finance.yahoo.com/news/rssindex"
