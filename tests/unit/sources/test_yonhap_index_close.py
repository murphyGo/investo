"""Contract tests for the Yonhap Korean index-close adapter."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.models.core_fact import core_fact_metadata_key
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError
from investo.sources.yonhap_index_close import YonhapIndexCloseAdapter

_FIXTURE = Path(__file__).parent / "fixtures" / "api" / "yonhap-index-close" / "yonhap_index.xml"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 22))


async def _fetch(body: bytes) -> tuple[list, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await YonhapIndexCloseAdapter().fetch(client, _WINDOW)
    return items, requests


def test_class_attributes() -> None:
    assert YonhapIndexCloseAdapter.name == "yonhap-index-close"
    assert YonhapIndexCloseAdapter.category == "price"


async def test_recorded_feed_emits_two_indices_from_one_request() -> None:
    items, requests = await _fetch(_FIXTURE.read_bytes())

    assert len(requests) == 1
    assert str(requests[0].url) == "https://www.yna.co.kr/rss/market.xml"
    assert [item.raw_metadata["ticker"] for item in items] == ["^KOSPI", "^KOSDAQ"]

    kospi, kosdaq = items
    assert kospi.raw_metadata == {
        "ticker": "^KOSPI",
        "display_name": "코스피",
        "close": "2650.500000",
        "provenance": "yonhap-rss",
        "source_date": "2026-05-22",
        "source_headline": "코스피, 외국인 매수에 강보합 마감…2,650.50 마감",
        core_fact_metadata_key("kospi_close"): "2650.500000",
    }
    assert str(kospi.url) == "https://www.yna.co.kr/view/AKR20260522000100001"
    assert kospi.published_at == datetime(2026, 5, 22, 6, 30, tzinfo=UTC)
    assert kosdaq.raw_metadata[core_fact_metadata_key("kosdaq_close")] == "870.250000"
    assert all(item.raw_metadata["ticker"] != "KRW=X" for item in items)


async def test_one_index_match_emits_only_that_index() -> None:
    body = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item><title><![CDATA[코스닥 870.25 마감]]></title>
    <link>https://www.yna.co.kr/view/AKR1</link></item></channel></rss>""".encode()

    items, _ = await _fetch(body)

    assert [item.raw_metadata["ticker"] for item in items] == ["^KOSDAQ"]


async def test_no_numeric_index_match_returns_zero_items() -> None:
    body = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel><item><title>국내 증시 마감</title></item></channel></rss>""".encode()

    items, _ = await _fetch(body)

    assert items == []


async def test_malformed_xml_is_terminal_source_error() -> None:
    with pytest.raises(SourceFetchError) as exc_info:
        await _fetch(b"<rss><channel>")

    assert exc_info.value.source_name == "yonhap-index-close"
    assert exc_info.value.transient is False
    assert "malformed Yonhap XML" in str(exc_info.value)
