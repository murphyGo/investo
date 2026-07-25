"""Byte and scenario contracts for the u138 endpoint-lifecycle fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

from investo.sources.protocol import SourceFetchError
from investo.sources.yfinance_history import fetch_price_history, parse_chart_payload

_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "api"
_YAHOO_DIR = _FIXTURE_ROOT / "yfinance-history"
_FRED_DIR = _FIXTURE_ROOT / "fred-fx-close"
_STOOQ_DIR = _FIXTURE_ROOT / "stooq-retirement"

_CRITICAL_FIXTURES = {
    "^GSPC": "GSPC.json",
    "^IXIC": "IXIC.json",
    "^DJI": "DJI.json",
    "^VIX": "VIX.json",
    "AAPL": "AAPL.json",
    "MSFT": "MSFT.json",
    "GOOGL": "GOOGL.json",
    "AMZN": "AMZN.json",
    "NVDA": "NVDA.json",
    "META": "META.json",
    "TSLA": "TSLA.json",
    "BZ=F": "BZ_F.json",
    "^RUT": "RUT.json",
}


def _load_json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_bytes())
    assert isinstance(loaded, dict)
    return loaded


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(("ticker", "filename"), _CRITICAL_FIXTURES.items())
def test_query2_critical_basket_has_replayable_success_fixture(
    ticker: str,
    filename: str,
) -> None:
    rows = parse_chart_payload(_load_json(_YAHOO_DIR / filename), ticker=ticker)
    assert rows, f"missing replay rows for {ticker}"


def test_query2_error_and_misaligned_array_fixtures_are_replayable() -> None:
    with pytest.raises(SourceFetchError, match="Not Found"):
        parse_chart_payload(
            _load_json(_YAHOO_DIR / "chart-error.json"),
            ticker="INVESTO-U138-NOT-A-TICKER",
        )

    rows = parse_chart_payload(
        _load_json(_YAHOO_DIR / "malformed-arrays.json"),
        ticker="AAPL",
    )
    assert len(rows) == 1


def test_yahoo_replay_manifest_pins_rate_limit_and_partial_basket() -> None:
    metadata = _load_json(_YAHOO_DIR / "_meta.json")
    replay_cases = metadata["replay_cases"]
    assert isinstance(replay_cases, dict)
    rate_limited = replay_cases["rate_limited"]
    partial = replay_cases["partial_basket"]
    assert rate_limited == {
        "status": 429,
        "body_sha256": hashlib.sha256(b"").hexdigest(),
        "evidence": "GitHub Actions run 29541149434",
    }
    assert partial["AAPL"] == 200
    assert partial["BZ=F"] == 429
    assert partial["INVESTO-U138-NOT-A-TICKER"] == 404


@pytest.mark.asyncio
async def test_partial_basket_replays_success_rate_limit_and_chart_error() -> None:
    request_counts: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = unquote(request.url.path.rsplit("/", 1)[-1])
        request_counts[ticker] = request_counts.get(ticker, 0) + 1
        assert request.url.params["interval"] == "1d"
        assert request.url.params["range"] == "1y"
        if ticker == "AAPL":
            return httpx.Response(200, content=(_YAHOO_DIR / "AAPL.json").read_bytes())
        if ticker == "BZ=F":
            return httpx.Response(429, content=b"")
        return httpx.Response(
            404,
            content=(_YAHOO_DIR / "chart-error.json").read_bytes(),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        history = await fetch_price_history(
            client,
            tickers=("AAPL", "BZ=F", "INVESTO-U138-NOT-A-TICKER"),
        )

    assert set(history) == {"AAPL"}
    assert request_counts == {
        "AAPL": 1,
        "BZ=F": 3,
        "INVESTO-U138-NOT-A-TICKER": 1,
    }


def test_new_yahoo_fixture_hashes_match_recording_sidecar() -> None:
    metadata = _load_json(_YAHOO_DIR / "_meta.json")
    responses = metadata["responses"]
    assert isinstance(responses, dict)
    for filename in ("BZ_F.json", "RUT.json", "chart-error.json", "malformed-arrays.json"):
        response = responses[filename]
        assert _sha256(_YAHOO_DIR / filename) == response["sha256"]


def test_fred_dexkous_fixture_is_live_shaped_secret_free_and_byte_pinned() -> None:
    metadata = _load_json(_FRED_DIR / "meta.json")
    assert metadata["url_template"] == (
        "https://api.stlouisfed.org/fred/series/observations?"
        "series_id=DEXKOUS&api_key=***&file_type=json&sort_order=desc&limit=16"
    )
    fixture_path = _FRED_DIR / str(metadata["fixture"])
    assert _sha256(fixture_path) == metadata["sha256"]

    body = fixture_path.read_text()
    assert "FRED_API_KEY" not in body
    assert "api_key" not in body
    payload = _load_json(fixture_path)
    observations = payload["observations"]
    assert isinstance(observations, list)
    assert observations[0]["date"] == "2026-07-10"
    assert observations[0]["value"] == "1501.06"
    assert any(row["value"] == "." for row in observations)


def test_stooq_retirement_responses_are_byte_pinned() -> None:
    metadata = _load_json(_STOOQ_DIR / "meta.json")
    responses = metadata["responses"]
    assert isinstance(responses, dict)
    for filename, response in responses.items():
        assert _sha256(_STOOQ_DIR / filename) == response["sha256"]

    assert "does not exist" in (_STOOQ_DIR / "quote-404.html").read_text()
    assert "requires JavaScript" in (_STOOQ_DIR / "history-challenge.html").read_text()
