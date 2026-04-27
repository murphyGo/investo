"""Tests for ``investo.sources.fomc_rss.FomcRssAdapter``.

Pins the algorithm from FD L6 against:

* The recorded real-feed fixture (`fixtures/api/fomc-rss/feed.xml`) —
  field mapping, RFC 822 → tz-aware UTC parsing, window filtering
* Inline synthetic XML — AC-7.2 (HTML in title stripped), AC-7.3
  (non-http/https URLs dropped), edge cases (missing fields,
  malformed XML, oversized summary)
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fomc_rss import FomcRssAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fomc-rss"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"


def _mock_client(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "text/xml"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Real fixture — happy path
# ---------------------------------------------------------------------------


async def test_fetch_returns_items_within_window() -> None:
    # KST 2026-04-25 → UTC [2026-04-24 15:00, 2026-04-25 15:00). The
    # recorded fixture has 2 entries dated "Fri, 24 Apr 2026 20:00:00
    # GMT" — both fall inside this window. Older entries are out.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 2
    assert all(item.source_name == "fomc-rss" for item in items)
    assert all(item.category == "calendar" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcRssAdapter()
    # Far-future date; recorded fixture has no entries that recent.
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    # AC-7.4 — every returned item has tz-aware published_at, in UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_returns_normalized_items_with_full_fields() -> None:
    # Spot-check on a known fixture entry: title, summary, url,
    # raw_metadata (guid + rss_category) all populated as expected.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    item = items[0]
    assert item.title  # non-empty after strip_html
    assert item.url is not None
    assert "guid" in item.raw_metadata
    assert "rss_category" in item.raw_metadata


# ---------------------------------------------------------------------------
# AC-7.2 — HTML in <title> / <description> stripped
# ---------------------------------------------------------------------------


_SYNTH_HTML_IN_TITLE = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Synthetic test feed</title>
    <item>
      <title>&lt;b&gt;Stress test&lt;/b&gt; results</title>
      <link>https://example.com/a</link>
      <guid>https://example.com/a</guid>
      <pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>
      <description>&lt;i&gt;Italic&lt;/i&gt; description</description>
    </item>
  </channel>
</rss>
"""


async def test_html_in_title_is_stripped() -> None:
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(_SYNTH_HTML_IN_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Stress test results"
    assert items[0].summary == "Italic description"


# ---------------------------------------------------------------------------
# AC-7.3 — non-http/https schemes dropped
# ---------------------------------------------------------------------------


_SYNTH_BAD_URL = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Synthetic test feed</title>
    <item>
      <title>Good entry</title>
      <link>https://example.com/good</link>
      <guid>g1</guid>
      <pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>
    </item>
    <item>
      <title>file:// URL entry</title>
      <link>file:///etc/passwd</link>
      <guid>g2</guid>
      <pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>
    </item>
    <item>
      <title>javascript: URL entry</title>
      <link>javascript:alert(1)</link>
      <guid>g3</guid>
      <pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_non_http_https_urls_dropped() -> None:
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(_SYNTH_BAD_URL) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Good entry"


# ---------------------------------------------------------------------------
# Edge cases: malformed XML, missing fields, oversized summary
# ---------------------------------------------------------------------------


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(b"<not xml") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


_SYNTH_MISSING_FIELDS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Has everything</title>
    <link>https://example.com/a</link>
    <pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Missing pubDate</title>
    <link>https://example.com/b</link>
  </item>
  <item>
    <link>https://example.com/c</link>
    <pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


async def test_missing_required_fields_dropped() -> None:
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(_SYNTH_MISSING_FIELDS) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Has everything"


def _build_body_with_summary(text: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<rss version="2.0"><channel>'
        "<item>"
        "<title>Summary boundary entry</title>"
        "<link>https://example.com/x</link>"
        "<pubDate>Fri, 24 Apr 2026 20:00:00 GMT</pubDate>"
        f"<description>{text}</description>"
        "</item>"
        "</channel></rss>"
    ).encode()


async def test_summary_oversized_truncated_to_280_chars() -> None:
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(_build_body_with_summary("x" * 500)) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].summary is not None
    assert len(items[0].summary) == 280


async def test_summary_at_boundary_passes_through_untouched() -> None:
    # 280 chars exactly — must not be touched.
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    text = "y" * 280
    async with _mock_client(_build_body_with_summary(text)) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].summary == text


async def test_summary_one_over_boundary_truncated() -> None:
    # 281 chars — must trim to 280.
    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(_build_body_with_summary("z" * 281)) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].summary is not None
    assert len(items[0].summary) == 280


async def test_naive_or_garbage_pubdate_is_dropped() -> None:
    # RFC 5322 "-0000" means "explicitly unknown TZ" — Python's
    # parsedate_to_datetime returns a naive datetime, which the
    # adapter MUST drop (AC-7.4 requires tz-aware). "not a date at
    # all" raises a parse error and is unconditionally dropped.
    body = (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<rss version="2.0"><channel>'
        b"<item>"
        b"<title>Naive date</title>"
        b"<link>https://example.com/x</link>"
        b"<pubDate>Fri, 24 Apr 2026 20:00:00 -0000</pubDate>"
        b"</item>"
        b"<item>"
        b"<title>Garbage date</title>"
        b"<link>https://example.com/y</link>"
        b"<pubDate>not a date at all</pubDate>"
        b"</item>"
        b"</channel></rss>"
    )

    adapter = FomcRssAdapter()
    window = FetchWindow.from_kst_date(date(2026, 4, 25))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    # Both entries dropped — naive timestamp + unparseable string.
    assert items == []


# ---------------------------------------------------------------------------
# Adapter identity (ClassVar attributes)
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert FomcRssAdapter.name == "fomc-rss"
    assert FomcRssAdapter.category == "calendar"
    assert FomcRssAdapter._FEED_URL.startswith("https://www.federalreserve.gov/")
