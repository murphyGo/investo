"""Tests for ``investo.sources.sec_edgar_8k.SecEdgar8kAdapter``.

Pins the algorithm from FD L6.6 + R14 (Extension #2 2026-05-01) against:

* The recorded real-feed fixture (`fixtures/api/sec-edgar-8k/feed.xml`)
  — Atom 1.0 namespace handling, ISO-8859-1 encoding handshake, title
  regex parsing, Item-code extraction, ``<updated>`` parsing.
* The R14 UA-header pinning test — ``MockTransport`` captures the
  outbound request and asserts the UA is the project's compliance
  string.
* Inline synthetic Atom — ``<source>``-style edge cases, namespace
  handling, defensive drops on schema slips.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.sec_edgar_8k import SecEdgar8kAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "sec-edgar-8k"
_REAL_FIXTURE = _FIXTURE_DIR / "feed.xml"


def _mock_client(
    body: bytes,
    status: int = 200,
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/atom+xml"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Real fixture — happy path
# ---------------------------------------------------------------------------


async def test_fetch_returns_items_within_window() -> None:
    # KST 2026-05-01 → UTC [2026-04-30 15:00, 2026-05-01 15:00). The
    # fixture has 40 entries dated "2026-04-30T17:xx-04:00" =
    # "2026-04-30T21:xx UTC", all of which fall in the window.
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) >= 5
    assert all(item.source_name == "sec-edgar-8k" for item in items)
    assert all(item.category == "news" for item in items)


async def test_fetch_window_outside_returns_empty() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2027, 1, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_fetch_published_at_is_tz_aware_and_utc() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.published_at.tzinfo is not None
        assert item.published_at.tzinfo.utcoffset(item.published_at) == timedelta(0)


async def test_fetch_title_is_normalized() -> None:
    # Real fixture title shape: "8-K - DBV Technologies S.A.
    # (0001613780) (Filer)". Adapter emits "8-K: DBV Technologies S.A.
    # (CIK 0001613780)".
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.title.startswith("8-K: ")
        assert "(CIK " in item.title


async def test_fetch_raw_metadata_shape() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert set(item.raw_metadata.keys()) == {
            "accession_no",
            "filer_cik",
            "form_type",
            "items",
        }
        # R8: all values must be strings (DEBT-028 guardrail).
        for value in item.raw_metadata.values():
            assert isinstance(value, str)
        # form_type pinned, filer_cik must be a digit string.
        assert item.raw_metadata["form_type"] == "8-K"
        assert item.raw_metadata["filer_cik"].isdigit()


async def test_fetch_url_is_https_sec_gov() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        assert item.url is not None
        url_str = str(item.url)
        assert url_str.startswith("https://www.sec.gov/")


async def test_fetch_items_extraction_real_fixture() -> None:
    # The real fixture has DBV Technologies as the first entry with
    # two Item codes (Item 2.02, Item 9.01). Item-code extraction must
    # surface them as a comma-joined string in raw_metadata.items.
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    # At least one entry in the fixture must carry a multi-code items
    # field (DBV has two; the heavier filers have many).
    multi_code = [it for it in items if "," in it.raw_metadata["items"]]
    assert multi_code, "expected at least one entry with multiple Item codes"
    sample = multi_code[0]
    for code in sample.raw_metadata["items"].split(","):
        assert code.startswith("Item ")
        assert "." in code


async def test_fetch_accession_no_extracted() -> None:
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    for item in items:
        accno = item.raw_metadata["accession_no"]
        # SEC accession numbers: 18 digits with two hyphens at fixed
        # positions, e.g. "0001193125-26-197921". A non-empty value
        # with at least one hyphen is the relaxed shape we accept.
        assert accno
        assert "-" in accno


# ---------------------------------------------------------------------------
# R14 — UA header pinning + constant non-empty / contains '@'
# ---------------------------------------------------------------------------


async def test_request_carries_compliance_user_agent() -> None:
    # R14: every request to SEC must carry the compliance UA. We
    # capture the request via MockTransport and assert exact match.
    captured: list[httpx.Request] = []
    body = _REAL_FIXTURE.read_bytes()
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body, captured=captured) as client:
        await adapter.fetch(client, window)

    assert captured, "expected at least one request"
    # httpx headers are case-insensitive on lookup.
    assert captured[0].headers["user-agent"] == "investo investo@example.com"


def test_adapter_endpoint_config_shape() -> None:
    # Defensive: the R14 constant must identify the project + a
    # contact mailbox. A blank value would silently fall back to
    # httpx's default UA, which SEC 403's. A future regression that
    # wipes the constant must be caught here.
    assert SecEdgar8kAdapter._FEED_URL.startswith("https://www.sec.gov/")
    assert SecEdgar8kAdapter._USER_AGENT
    assert "@" in SecEdgar8kAdapter._USER_AGENT
    assert SecEdgar8kAdapter._USER_AGENT == "investo investo@example.com"


# ---------------------------------------------------------------------------
# Encoding: parser must take bytes (response.content), not text
# ---------------------------------------------------------------------------


async def test_iso_8859_1_encoded_body_parses_via_bytes() -> None:
    # SEC declares ISO-8859-1 in the XML preamble. We craft a synthetic
    # entry whose company name contains a Latin-1 character (the
    # Spanish 'ñ' — U+00F1, which encodes as 0xF1 in Latin-1) and feed
    # it as **raw Latin-1 bytes**. If the adapter passes ``response.text``
    # to the parser, httpx will pre-decode using a default charset
    # (utf-8 is the httpx default fallback) and the byte 0xF1 becomes
    # mojibake or a UnicodeDecodeError. The adapter passes
    # ``response.content`` (bytes), so the parser honours the
    # ISO-8859-1 declaration and the entry round-trips cleanly.
    iso_body = (
        '<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        "<title>Test</title>\n"
        "<entry>\n"
        "<title>8-K - ESPAÑA INC (0000123456) (Filer)</title>\n"
        '<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/x.htm"/>\n'
        '<summary type="html">'
        " &lt;b&gt;Filed:&lt;/b&gt; 2026-04-30 &lt;b&gt;AccNo:&lt;/b&gt; 0000123456-26-000001"
        " &lt;br&gt;Item 1.01: Entry into a Material Definitive Agreement"
        "</summary>\n"
        "<updated>2026-04-30T17:00:00-04:00</updated>\n"
        "<id>urn:tag:sec.gov,2008:accession-number=0000123456-26-000001</id>\n"
        "</entry>\n"
        "</feed>\n"
    ).encode("iso-8859-1")

    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(iso_body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    # The Latin-1 'Ñ' (U+00D1) must round-trip into the title.
    assert "ESPAÑA" in items[0].title


# ---------------------------------------------------------------------------
# Atom namespace handling — extension elements MUST NOT crash the parse
# ---------------------------------------------------------------------------


_SYNTH_NS_EXTENSION = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
<title>Synthetic</title>
<entry>
<title>8-K - SAMPLE CO (0000999999) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/y.htm"/>
<summary type="html">
 &lt;b&gt;AccNo:&lt;/b&gt; 0000999999-26-000001 &lt;br&gt;Item 8.01: Other Events
</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0000999999-26-000001</id>
<media:content url="https://example.com/x.png"/>
</entry>
</feed>
"""


async def test_atom_extension_element_does_not_crash() -> None:
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_NS_EXTENSION) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["filer_cik"] == "0000999999"
    assert items[0].raw_metadata["items"] == "Item 8.01"


async def test_namespaceless_atom_drops_entries() -> None:
    # An "Atom-shaped" feed with NO xmlns declaration should match
    # zero entries via our namespace-aware iteration — defensive
    # against feed shape changes. Adapter returns []; no raise.
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed>
<title>No namespace</title>
<entry>
<title>8-K - SAMPLE CO (0000999999) (Filer)</title>
<link rel="alternate" href="https://www.sec.gov/x.htm"/>
<summary>AccNo: 0000999999-26-000001 Item 1.01</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
</entry>
</feed>
"""
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


# ---------------------------------------------------------------------------
# Title regex — drop on miss, do not raise
# ---------------------------------------------------------------------------


_SYNTH_BAD_TITLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>NOT THE EXPECTED 8-K SHAPE</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/x.htm"/>
<summary type="html"> &lt;b&gt;AccNo:&lt;/b&gt; 0000111111-26-000001 &lt;br&gt;Item 1.01</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
</entry>
<entry>
<title>8-K - GOOD CO (0000222222) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/y.htm"/>
<summary type="html"> &lt;b&gt;AccNo:&lt;/b&gt; 0000222222-26-000001 &lt;br&gt;Item 5.02</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
</entry>
</feed>
"""


async def test_title_regex_miss_drops_entry() -> None:
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_BAD_TITLE) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["filer_cik"] == "0000222222"


# ---------------------------------------------------------------------------
# Defensive drops: missing fields, non-http link, naive updated, empty items
# ---------------------------------------------------------------------------


_SYNTH_MISSING_LINK_REL = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>8-K - NO ALT LINK CO (0000333333) (Filer)</title>
<link rel="self" href="https://www.sec.gov/self.htm"/>
<summary type="html"> &lt;b&gt;AccNo:&lt;/b&gt; 0000333333-26-000001 &lt;br&gt;Item 1.01</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
</entry>
</feed>
"""


async def test_missing_alternate_link_drops_entry() -> None:
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_MISSING_LINK_REL) as client:
        items = await adapter.fetch(client, window)

    assert items == []


_SYNTH_NON_HTTP_LINK = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>8-K - FILE URL CO (0000444444) (Filer)</title>
<link rel="alternate" type="text/html" href="file:///etc/passwd"/>
<summary type="html"> &lt;b&gt;AccNo:&lt;/b&gt; 0000444444-26-000001 &lt;br&gt;Item 1.01</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
</entry>
</feed>
"""


async def test_non_http_https_link_dropped() -> None:
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_NON_HTTP_LINK) as client:
        items = await adapter.fetch(client, window)

    assert items == []


_SYNTH_NAIVE_UPDATED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>8-K - NAIVE TIME CO (0000555555) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/n.htm"/>
<summary type="html"> &lt;b&gt;AccNo:&lt;/b&gt; 0000555555-26-000001 &lt;br&gt;Item 1.01</summary>
<updated>2026-04-30T17:00:00</updated>
</entry>
</feed>
"""


async def test_naive_updated_dropped() -> None:
    # Defensive — SEC always emits an offset on <updated>, but a future
    # format slip without offset would parse naive and must be dropped.
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_NAIVE_UPDATED) as client:
        items = await adapter.fetch(client, window)

    assert items == []


_SYNTH_NO_ITEM_CODES = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>8-K - NO ITEMS CO (0000666666) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/no_items.htm"/>
<summary type="html"> &lt;b&gt;AccNo:&lt;/b&gt; 0000666666-26-000001 &lt;br&gt;Narrative.</summary>
<updated>2026-04-30T17:00:00-04:00</updated>
</entry>
</feed>
"""


async def test_no_item_codes_emits_entry_with_empty_items() -> None:
    # L6.6 edge case: zero matches → entry STILL emitted with
    # raw_metadata.items="". The title + URL alone carry signal.
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(_SYNTH_NO_ITEM_CODES) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["items"] == ""
    assert items[0].raw_metadata["accession_no"] == "0000666666-26-000001"


# ---------------------------------------------------------------------------
# Transport-level failures
# ---------------------------------------------------------------------------


async def test_403_response_raises_terminal_source_fetch_error() -> None:
    # Synthetic 403 simulates SEC's missing/wrong-UA response. Per the
    # retry contract this is a terminal 4xx-not-429 → SourceFetchError
    # with transient=False.
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(b"forbidden", status=403) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False


async def test_malformed_xml_raises_terminal_source_fetch_error() -> None:
    adapter = SecEdgar8kAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 1))

    async with _mock_client(b"<not xml") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed XML" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Adapter identity
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert SecEdgar8kAdapter.name == "sec-edgar-8k"
    assert SecEdgar8kAdapter.category == "news"
