"""Tests for ``investo.sources.korea_policy_rss``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.korea_policy_rss import KoreaPolicyRssAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "korea-policy-rss"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 7))
_PRESS_URL = "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"
_EXPLAIN_URL = "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0112"


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    failing_urls: set[str] | None = None,
) -> httpx.AsyncClient:
    failures = failing_urls or set()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in failures:
            return httpx.Response(503, text="temporary")
        body = fixtures.get(url)
        if body is None:
            return httpx.Response(404, text="missing fixture")
        return httpx.Response(200, content=body, headers={"content-type": "application/rss+xml"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_parses_official_fsc_rss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVESTO_KOREA_POLICY_RSS_URLS", raising=False)
    adapter = KoreaPolicyRssAdapter()
    fixtures = {_PRESS_URL: (_FIXTURE_DIR / "fsc-press.xml").read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "korea-policy-rss"
    assert item.category == "news"
    assert item.title == "자본시장 제도 개선 발표"
    assert item.summary == "금융위원회가 자본시장 제도 개선 방안을 발표했습니다."
    assert item.published_at == datetime(2026, 5, 7, 0, 30, tzinfo=UTC)
    assert item.raw_metadata["feed_url"] == _PRESS_URL
    assert item.raw_metadata["guid"] == "fsc-90001"


async def test_multiple_feeds_are_deduped_and_sorted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KOREA_POLICY_RSS_URLS", f"{_PRESS_URL},{_EXPLAIN_URL}")
    adapter = KoreaPolicyRssAdapter()
    fixtures = {
        _PRESS_URL: (_FIXTURE_DIR / "fsc-press.xml").read_bytes(),
        _EXPLAIN_URL: (_FIXTURE_DIR / "fsc-explain.xml").read_bytes(),
    }
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.title for item in items] == [
        "시장 안정 관련 보도 설명",
        "자본시장 제도 개선 발표",
    ]


async def test_one_failed_feed_does_not_drop_successful_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_KOREA_POLICY_RSS_URLS", f"{_PRESS_URL},{_EXPLAIN_URL}")
    adapter = KoreaPolicyRssAdapter()
    fixtures = {_PRESS_URL: (_FIXTURE_DIR / "fsc-press.xml").read_bytes()}
    async with _mock_client(fixtures, failing_urls={_EXPLAIN_URL}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.title for item in items] == ["자본시장 제도 개선 발표"]


async def test_all_failed_feeds_raise_source_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KOREA_POLICY_RSS_URLS", _PRESS_URL)
    adapter = KoreaPolicyRssAdapter()
    async with _mock_client({}, failing_urls={_PRESS_URL}) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, _WINDOW)


async def test_unsupported_feed_url_scheme_is_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KOREA_POLICY_RSS_URLS", "file:///tmp/feed.xml")
    adapter = KoreaPolicyRssAdapter()
    async with _mock_client({}) as client:
        with pytest.raises(SourceFetchError, match="unsupported feed URL scheme"):
            await adapter.fetch(client, _WINDOW)
