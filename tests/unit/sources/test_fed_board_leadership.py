from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fed_board_leadership import FedBoardLeadershipAdapter
from investo.sources.protocol import SourceFetchError


def _mock_client(body: str) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_emits_current_chair_fact_metadata() -> None:
    html = """
    <html><body><main>
      <ul><li><a href="/aboutthefed/bios/board/warsh.htm">Kevin Warsh, Chairman</a></li></ul>
    </main></body></html>
    """
    window = FetchWindow.from_local_date(date(2026, 6, 18), tz=UTC)

    async with _mock_client(html) as client:
        items = await FedBoardLeadershipAdapter().fetch(client, window)

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "fed-board-leadership"
    assert item.category == "macro"
    assert item.title == "Current Federal Reserve Chair: Kevin Warsh"
    assert item.summary == "Kevin Warsh, Chairman"
    assert item.published_at == datetime.combine(date(2026, 6, 18), time.min, tzinfo=UTC)
    assert item.raw_metadata["fact_id"] == "fed.current_chair"
    assert item.raw_metadata["fact_value"] == "Kevin Warsh"
    assert item.raw_metadata["fact_label_ko"] == "케빈 워시"
    assert item.raw_metadata["fact_source_tier"] == "S"
    assert (
        item.raw_metadata["fact_expires_at"]
        == (datetime(2026, 6, 18, tzinfo=UTC) + timedelta(hours=24)).isoformat()
    )
    assert "<a" not in item.raw_metadata["raw_evidence_label"]


async def test_fetch_without_chairman_returns_empty() -> None:
    html = "<html><body><a>Jane Doe, Governor</a></body></html>"
    window = FetchWindow.from_local_date(date(2026, 6, 18), tz=UTC)

    async with _mock_client(html) as client:
        assert await FedBoardLeadershipAdapter().fetch(client, window) == []


async def test_fetch_with_multiple_chairman_labels_raises() -> None:
    html = """
    <a>Kevin Warsh, Chairman</a>
    <a>Jerome Powell, Chairman</a>
    """
    window = FetchWindow.from_local_date(date(2026, 6, 18), tz=UTC)

    async with _mock_client(html) as client:
        with pytest.raises(SourceFetchError, match="ambiguous chairman labels"):
            await FedBoardLeadershipAdapter().fetch(client, window)
