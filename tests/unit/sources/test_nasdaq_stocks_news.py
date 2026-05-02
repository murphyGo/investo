"""Tests for ``investo.sources.nasdaq_stocks_news.NasdaqStocksNewsAdapter``."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.nasdaq_stocks_news import NasdaqStocksNewsAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "nasdaq-stocks-news"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"
_EXPECTED_TICKERS = (
    "MSTR,ALK,AAPL,INTU,SNDK,DDOG,GLXY,VEEV,AMGN,COIN,CLX,MSFT,PSKY,STX,AMD,RBLX,"
    "SPY,DIA,TWLO,RDDT,SYK,ADSK,EL,MU,RMD,ORCL,WDAY,QQQ,INTC,NOW,ADBE,TEAM,MCHP,"
    "RIOT,CRM"
)


def _mock_client(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/xml;charset=utf-8"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_returns_items_within_window() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 2
    assert all(item.source_name == "nasdaq-stocks-news" for item in items)
    assert all(item.category == "news" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_url_is_http_or_https() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.url is not None
        assert str(item.url).startswith(("http://", "https://"))


async def test_real_fixture_maps_metadata_as_flat_strings() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    assert items[0].title == "S&P 500 and Nasdaq 100 Post Record Highs on Solid Earnings"
    assert items[0].raw_metadata == {
        "guid": "https://www.nasdaq.com/articles/sp-500-and-nasdaq-100-post-record-highs-solid-earnings?time=1777740418",
        "creator": "Barchart",
        "category": "Stocks",
        "tickers": _EXPECTED_TICKERS,
    }
    assert items[1].raw_metadata == {
        "guid": "https://www.nasdaq.com/articles/dollar-rebounds-trade-tensions-resurface?time=1777740417",
        "creator": "Barchart",
        "category": "Stocks",
    }
    for item in items:
        for value in item.raw_metadata.values():
            assert isinstance(value, str)
            assert value != ""


async def test_fetch_sends_compliance_user_agent() -> None:
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers["user-agent"])
        return httpx.Response(200, content=_REAL_FIXTURE.read_bytes())

    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await adapter.fetch(client, window)

    assert seen_headers == [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    ]


_SYNTH_HTML_IN_TITLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel><title>Synthetic</title>
    <item>
      <title><![CDATA[<b>Bold headline</b> &amp; more]]></title>
      <link>https://www.nasdaq.com/articles/html-title</link>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
      <description><![CDATA[<p>short body</p>]]></description>
    </item>
  </channel>
</rss>
"""


async def test_html_in_title_and_summary_is_stripped() -> None:
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(_SYNTH_HTML_IN_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Bold headline & more"
    assert items[0].summary == "short body"


def _long_description_xml() -> bytes:
    long_text = "x" * 400
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel><title>Synthetic</title>"
        "<item>"
        "<title>Long body</title>"
        "<link>https://www.nasdaq.com/articles/long-body</link>"
        "<pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>"
        f"<description>{long_text}</description>"
        "</item>"
        "</channel></rss>"
    )
    return body.encode("utf-8")


async def test_summary_is_truncated_to_280_chars() -> None:
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(_long_description_xml()) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    summary = items[0].summary
    assert summary is not None
    assert len(summary) == 280
    assert summary == "x" * 280


_SYNTH_BAD_URL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel><title>Synthetic</title>
    <item>
      <title>Good entry</title>
      <link>https://www.nasdaq.com/articles/good</link>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
    </item>
    <item>
      <title>file URL entry</title>
      <link>file:///etc/passwd</link>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
    </item>
    <item>
      <title>javascript URL entry</title>
      <link>javascript:alert(1)</link>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_non_http_https_urls_dropped() -> None:
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(_SYNTH_BAD_URL) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Good entry"


async def test_naive_or_garbage_pubdate_is_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Naive RFC-822</title>
      <link>https://www.nasdaq.com/articles/x</link>
      <pubDate>Sat, 02 May 2026 16:46:58</pubDate>
    </item>
    <item>
      <title>Garbage date</title>
      <link>https://www.nasdaq.com/articles/y</link>
      <pubDate>not a date</pubDate>
    </item>
  </channel>
</rss>
"""
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_missing_required_fields_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Has everything</title>
      <link>https://www.nasdaq.com/articles/x</link>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
    </item>
    <item>
      <title>Missing pubDate</title>
      <link>https://www.nasdaq.com/articles/y</link>
    </item>
    <item>
      <link>https://www.nasdaq.com/articles/z</link>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
    </item>
    <item>
      <title>Missing link</title>
      <pubDate>Sat, 02 May 2026 16:46:58 +0000</pubDate>
    </item>
  </channel>
</rss>
"""
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Has everything"


async def test_empty_channel_returns_empty_list() -> None:
    body = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rss version="2.0"><channel><title>Empty</title></channel></rss>'
    )
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = NasdaqStocksNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 3))

    async with _mock_client(b"<not xml") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


def test_adapter_class_attributes() -> None:
    assert NasdaqStocksNewsAdapter.name == "nasdaq-stocks-news"
    assert NasdaqStocksNewsAdapter.category == "news"
    assert (
        NasdaqStocksNewsAdapter._FEED_URL
        == "https://www.nasdaq.com/feed/rssoutbound?category=Stocks"
    )
