"""Tests for ``investo.sources.cnbc_top_news.CnbcTopNewsAdapter``.

Pins the algorithm from FD L6.9 (Extension #3 2026-05-01) against:

* The recorded real-feed fixture (``fixtures/api/cnbc-top-news/feed.xml``)
  — field mapping, RFC-822 ``GMT`` → tz-aware UTC parsing, KST window
  filtering, missing ``<creator>`` (always-case for CNBC).
* Inline synthetic XML — AC-7.2 (HTML in title stripped), AC-7.3
  (non-http/https URLs dropped), edge cases (missing required fields,
  naive pubDate, summary truncation at 280 chars, malformed XML), and
  the ``metadata:*`` / ``media:*`` / ``cn:*`` namespace-ignore guarantee
  (per FD L6.9: NO namespace-prefixed key leaks into ``raw_metadata``).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from investo.sources._window import FetchWindow
from investo.sources.cnbc_top_news import CnbcTopNewsAdapter
from investo.sources.protocol import SourceFetchError
from tests.unit.sources._mock_transport import mock_client as _mock_client

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "cnbc-top-news"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"


# ---------------------------------------------------------------------------
# Real fixture — happy path
# ---------------------------------------------------------------------------


async def test_fetch_returns_items_within_window() -> None:
    # KST 2026-05-01 → UTC [2026-04-30 15:00, 2026-05-01 15:00). The
    # fixture has many entries dated "Fri, 01 May 2026 HH:MM:SS GMT" and
    # a handful from "Thu, 30 Apr 2026 ..." — most should fall in this
    # window once converted to UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) >= 5
    assert all(item.source_name == "cnbc-top-news" for item in items)
    assert all(item.category == "news" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = CnbcTopNewsAdapter()
    # Far-future date; recorded fixture has no entries that recent.
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    # AC-7.4 — every returned item has tz-aware published_at, in UTC.
    body = _REAL_FIXTURE.read_bytes()
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_url_is_http_or_https() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.url is not None
        assert str(item.url).startswith(("http://", "https://"))


async def test_real_fixture_no_creator_key_anywhere() -> None:
    # The CNBC feed has NO <creator> / <dc:creator> element on any item.
    # Per FD L6.9 missing-creator is the always-case for this source —
    # no item ever yields raw_metadata.creator.
    body = _REAL_FIXTURE.read_bytes()
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert "creator" not in item.raw_metadata


async def test_real_fixture_raw_metadata_is_only_guid() -> None:
    # Per FD L6.9 raw_metadata carries {"guid": str} only.
    body = _REAL_FIXTURE.read_bytes()
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        # All keys are exactly {"guid"} — guid is present on every
        # item in the recorded feed.
        assert set(item.raw_metadata.keys()) == {"guid"}
        for value in item.raw_metadata.values():
            assert isinstance(value, str)
            assert value != ""


# ---------------------------------------------------------------------------
# Namespace-ignore guarantee (FD L6.9)
# ---------------------------------------------------------------------------


_SYNTH_NAMESPACED_SIBLINGS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:metadata="http://search.cnbc.com/rss/2.0/modules/siteContentMetadata"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:cn="http://nbcnews.com/rss/namespace">
  <channel><title>Synthetic</title>
    <item>
      <link>https://www.cnbc.com/2026/05/01/article-x.html</link>
      <guid isPermaLink="false">108300xxx</guid>
      <metadata:type>cnbcnewsstory</metadata:type>
      <metadata:id>108300xxx</metadata:id>
      <metadata:sponsored>false</metadata:sponsored>
      <media:thumbnail url="https://image.cnbcfm.com/api/v1/image/x.jpg"/>
      <cn:source>cnbc</cn:source>
      <cn:type>article</cn:type>
      <title>Article with namespaced siblings</title>
      <description><![CDATA[Body text.]]></description>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_namespaced_siblings_are_ignored_in_raw_metadata() -> None:
    # Per FD L6.9: NO key starts with 'metadata:' / 'media:' / 'cn:' /
    # contains a colon. raw_metadata must contain ONLY {"guid": "..."}.
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_NAMESPACED_SIBLINGS) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    item = items[0]
    assert set(item.raw_metadata.keys()) == {"guid"}
    assert item.raw_metadata["guid"] == "108300xxx"
    # Defense-in-depth: no key contains a colon.
    for key in item.raw_metadata:
        assert ":" not in key
    # No namespace-prefixed key, regardless of which prefix.
    for prefix in ("metadata:", "media:", "cn:", "atom:", "content:"):
        assert not any(k.startswith(prefix) for k in item.raw_metadata)


# ---------------------------------------------------------------------------
# AC-7.2 — HTML in title is stripped
# ---------------------------------------------------------------------------


_SYNTH_HTML_IN_TITLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel><title>Synthetic</title>
    <item>
      <title><![CDATA[<b>Bold headline</b> &amp; more]]></title>
      <link>https://www.cnbc.com/2026/05/01/x.html</link>
      <guid isPermaLink="false">g1</guid>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
      <description><![CDATA[short body]]></description>
    </item>
  </channel>
</rss>
"""


async def test_html_in_title_is_stripped() -> None:
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_HTML_IN_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    # bleach strips <b> tags and decodes &amp; entities; the resulting
    # title is plain text.
    assert items[0].title == "Bold headline & more"


# ---------------------------------------------------------------------------
# Summary truncation at 280 chars
# ---------------------------------------------------------------------------


def _long_description_xml() -> bytes:
    long_text = "x" * 400  # 400-char ASCII description
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel><title>Synthetic</title>"
        "<item>"
        "<title>Long body</title>"
        "<link>https://www.cnbc.com/2026/05/01/long.html</link>"
        "<guid>g1</guid>"
        "<pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>"
        f"<description><![CDATA[{long_text}]]></description>"
        "</item>"
        "</channel></rss>"
    )
    return body.encode("utf-8")


async def test_summary_is_truncated_to_280_chars() -> None:
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_long_description_xml()) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    summary = items[0].summary
    assert summary is not None
    assert len(summary) == 280
    assert summary == "x" * 280


# ---------------------------------------------------------------------------
# AC-7.3 — non-http/https schemes dropped
# ---------------------------------------------------------------------------


_SYNTH_BAD_URL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel><title>Synthetic</title>
    <item>
      <title>Good entry</title>
      <link>https://www.cnbc.com/2026/05/01/good.html</link>
      <guid>g1</guid>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>file URL entry</title>
      <link>file:///etc/passwd</link>
      <guid>g2</guid>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>javascript URL entry</title>
      <link>javascript:alert(1)</link>
      <guid>g3</guid>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


async def test_non_http_https_urls_dropped() -> None:
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_BAD_URL) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Good entry"


# ---------------------------------------------------------------------------
# Edge cases: naive pubDate, missing fields, empty channel, malformed XML
# ---------------------------------------------------------------------------


async def test_naive_or_garbage_pubdate_is_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Naive RFC-822 (no offset)</title>
      <link>https://www.cnbc.com/2026/05/01/x.html</link>
      <pubDate>Fri, 01 May 2026 12:00:00</pubDate>
      <guid>g1</guid>
    </item>
    <item>
      <title>Wholly unparseable pubDate</title>
      <link>https://www.cnbc.com/2026/05/01/y.html</link>
      <pubDate>not a date at all</pubDate>
      <guid>g2</guid>
    </item>
  </channel>
</rss>
"""
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_missing_required_fields_dropped() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Has everything</title>
      <link>https://www.cnbc.com/2026/05/01/x.html</link>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Missing pubDate</title>
      <link>https://www.cnbc.com/2026/05/01/y.html</link>
    </item>
    <item>
      <link>https://www.cnbc.com/2026/05/01/z.html</link>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Missing link</title>
      <pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].title == "Has everything"


async def test_empty_channel_returns_empty_list() -> None:
    body = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rss version="2.0"><channel><title>Empty</title></channel></rss>'
    )
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = CnbcTopNewsAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(b"<not xml") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Adapter identity (ClassVar attributes)
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert CnbcTopNewsAdapter.name == "cnbc-top-news"
    assert CnbcTopNewsAdapter.category == "news"
    assert CnbcTopNewsAdapter._FEED_URL == "https://www.cnbc.com/id/100003114/device/rss/rss.html"
