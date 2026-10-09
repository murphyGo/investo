"""Synthetic schema/count receipts; no restricted provider response fixtures."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from investo.sources import fsc_krx_index_price as source
from investo.sources._window import FetchWindow

_WINDOW = FetchWindow.from_kst_date(date(2026, 10, 7))
_ROOT = Path(__file__).resolve().parents[3]


def _row(name: str = "코스피", basis: str = "20261007", **changes: Any) -> dict[str, Any]:
    return {
        "idxNm": name,
        "basDt": basis,
        "clpr": 10,
        "vs": 0,
        "fltRt": 0,
        "mkp": 10,
        "hipr": 11,
        "lopr": 9,
        "trqu": 0,
        "trPrc": 0,
        "lstgMrktTotAmt": 100,
        **changes,
    }


def _payload(rows: Any, *, total: int | None = None, page: int = 1) -> dict[str, Any]:
    return {
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "pageNo": page,
                "numOfRows": 100,
                "totalCount": len(rows) if total is None else total,
                "items": {"item": rows},
            },
        }
    }


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "PRIVATE_KEY_SENTINEL")
    monkeypatch.delenv("INVESTO_KRX_INDEX_NAMES", raising=False)


async def test_v2_second_page_finds_main_indices_and_preserves_numeric_zero() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        page = int(request.url.params["pageNo"])
        rows = [_row("other")] * 100 if page == 1 else [_row(), _row("코스닥"), _row("코스피 200")]
        return httpx.Response(200, json=_payload(rows, total=103, page=page))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert len(calls) == 2 and all(
        "GetMarketIndexInfoService_V2/getStockMarketIndex_V2" in r.url.path for r in calls
    )
    assert len(report.items) == 3
    assert report.items[0].raw_metadata["pct_change"] == "0.000000"
    assert report.items[0].raw_metadata["volume"] == "0"
    assert report.diagnostics[0].exclusions == (("name_mismatch", 100),)
    assert report.diagnostics[1].selected_date == "2026-10-07"
    assert not vars(source.FscKrxIndexPriceAdapter())


async def test_empty_is_zero_but_nonempty_mismatch_is_observable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        rows = [_row("unwanted")] if request.url.params["basDt"] == "20261007" else []
        return httpx.Response(200, json=_payload(rows))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert not report.items and len(report.diagnostics) == 8
    assert report.diagnostics[0].reason == "name_mismatch"
    assert all(r.reason == "provider_no_rows" for r in report.diagnostics[1:])


@pytest.mark.parametrize("rows", [None, "", [], {}])
def test_valid_empty_envelope_shapes(rows: Any) -> None:
    # A singleton {} is a malformed non-empty row, not a successful empty envelope.
    if rows == {}:
        with pytest.raises(source.IndexDiagnosticError):
            source._extract_rows(_payload(rows, total=0), source_name="fsc-krx-index-price")
    else:
        assert (
            source._extract_rows(_payload(rows, total=0), source_name="fsc-krx-index-price") == []
        )


@pytest.mark.parametrize(
    "payload",
    [{}, {"response": {}}, _payload([], total=1), _payload([1]), _payload([_row()], page=2)],
)
def test_bad_envelopes_are_failed_not_zero(payload: Any) -> None:
    with pytest.raises(source.IndexDiagnosticError) as caught:
        source._extract_rows(payload, source_name="fsc-krx-index-price")
    assert caught.value.diagnostics[-1].reason == "schema_error"


@pytest.mark.parametrize("xml", [False, True])
async def test_auth_receipts_never_include_provider_message_or_key(xml: bool) -> None:
    raw = (
        b"<error><returnReasonCode>PRIVATE_KEY_SENTINEL</returnReasonCode>"
        b"<errMsg>PRIVATE_PRICE_SENTINEL</errMsg></error>"
    )
    payload = {
        "response": {
            "header": {"resultCode": "PRIVATE_KEY_SENTINEL", "resultMsg": "PRIVATE_PRICE_SENTINEL"}
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=raw) if xml else httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(source.IndexDiagnosticError) as caught:
            await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    text = str(caught.value) + json.dumps([asdict(r) for r in caught.value.diagnostics])
    assert "PRIVATE" not in text and "unknown" in text
    assert caught.value.cause is None


async def test_transport_status_is_fixed_and_redacted() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(403))
    ) as client:
        with pytest.raises(source.IndexDiagnosticError) as caught:
            await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert caught.value.diagnostics[-1].http_status == 403
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize(
    "body", [b'{"huge":' + b"1" * 4400 + b"}", b"[" * 2000 + b"0" + b"]" * 2000]
)
async def test_untrusted_json_resource_errors_are_isolated_and_redacted(body: bytes) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    ) as client:
        with pytest.raises(source.IndexDiagnosticError) as caught:
            await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert caught.value.diagnostics[-1].reason == "schema_error"
    assert caught.value.cause is None and len(str(caught.value)) < 200


async def test_page_limit_without_usable_rows_is_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_payload([_row("other")] * 100, total=300, page=int(request.url.params["pageNo"])),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(source.IndexDiagnosticError) as caught:
            await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert len(caught.value.diagnostics) == 2
    assert caught.value.diagnostics[-1].reason == "page_incomplete"


async def test_successful_first_page_survives_second_page_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["pageNo"] == "2":
            return httpx.Response(403)
        return httpx.Response(200, json=_payload([_row()] + [_row("other")] * 99, total=101))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert len(report.items) == 1 and report.diagnostics[-1].reason == "transport_error"


@pytest.mark.parametrize("second_total", [168, 101])
async def test_truncated_or_inconsistent_second_page_cannot_be_zero(second_total: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pageNo"])
        rows = [_row("other")] * (100 if page == 1 else 1)
        return httpx.Response(
            200, json=_payload(rows, total=168 if page == 1 else second_total, page=page)
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(source.IndexDiagnosticError) as caught:
            await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert caught.value.diagnostics[-1].reason == "page_incomplete"
    assert len(caught.value.diagnostics) == 2


async def test_truncated_success_page_preserves_rows_and_discloses_incomplete() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=_payload([_row()], total=168))
        )
    ) as client:
        report = await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert len(report.items) == 1
    assert report.diagnostics[-1].reason == "page_incomplete"


async def test_adapter_deadline_and_remaining_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source, "_TOTAL_BUDGET_S", 0.03)
    budgets: list[float] = []

    async def slow(*args: Any, **kwargs: Any) -> httpx.Response:
        budgets.append(kwargs["config"].total_budget_s)
        await asyncio.sleep(1)
        raise AssertionError("deadline must cancel")

    monkeypatch.setattr(source, "retry_get", slow)
    async with httpx.AsyncClient() as client:
        with pytest.raises(source.IndexDiagnosticError) as caught:
            await source.FscKrxIndexPriceAdapter().fetch_with_diagnostics(client, _WINDOW)
    assert budgets[0] <= 0.03 and caught.value.diagnostics[-1].reason == "deadline"


@pytest.mark.parametrize("error", [TypeError, TimeoutError, asyncio.CancelledError])
async def test_programmer_and_cancellation_errors_propagate(
    monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    async def bad(*args: Any, **kwargs: Any) -> httpx.Response:
        raise error()

    monkeypatch.setattr(source, "retry_get", bad)
    async with httpx.AsyncClient() as client:
        with pytest.raises(error):
            await source.FscKrxIndexPriceAdapter().fetch(client, _WINDOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"basDt": "20261008"},
        {"clpr": "NaN"},
        {"vs": True},
        {"trqu": -1},
        {"trqu": "1.5"},
        {"hipr": 5},
    ],
)
def test_invalid_future_nonfinite_boolean_fractional_or_negative_rows_filtered(
    changes: dict[str, Any],
) -> None:
    assert (
        source.FscKrxIndexPriceAdapter()._rows_to_items(
            [_row(**changes)],
            wanted={"코스피"},
            index_order=("코스피",),
            target_date=_WINDOW.target_date,
        )
        == []
    )


@given(st.integers(min_value=0, max_value=10**25))
def test_integer_parser_preserves_large_exact_values(value: int) -> None:
    assert source._integer(str(value)) == value


@pytest.mark.parametrize(
    "value",
    ["1e1000000", "-1e1000000", "1e-1000000", "-1e-1000000", str(10**30 + 1), str(-(10**30 + 1))],
)
def test_extreme_decimal_values_are_closed_row_errors(value: str) -> None:
    with pytest.raises(ValueError):
        source._integer(value)
    assert (
        source.FscKrxIndexPriceAdapter()._rows_to_items(
            [_row(trqu=value)],
            wanted={"코스피"},
            index_order=("코스피",),
            target_date=_WINDOW.target_date,
        )
        == []
    )


@pytest.mark.parametrize("value", [10**28 + 1, 10**30, -(10**28 + 1)])
def test_decimal_magnitude_checks_preserve_exact_large_values(value: int) -> None:
    assert source._integer(str(value)) == value


async def test_probe_cli_outputs_only_allowlisted_receipts() -> None:
    spec = importlib.util.spec_from_file_location(
        "index_probe", _ROOT / "scripts/probe_domestic_index_source.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json=_payload([_row(clpr=10, arbitrary="PRIVATE_PRICE_SENTINEL")])
            )
        )
    ) as client:
        result, exit_code = await module.probe(_WINDOW.target_date, client)
    text = json.dumps(result)
    assert exit_code == 0 and result["usable_items"] == 1
    assert "PRIVATE" not in text and "idxNm" not in text and "clpr" not in text


def test_manual_workflow_has_no_runtime_or_publication_side_effects() -> None:
    path = _ROOT / ".github/workflows/domestic-index-source-probe.yml"
    text = path.read_text()
    config = yaml.safe_load(text)
    assert config["permissions"] == {"contents": "read"}
    assert config["jobs"]["probe"]["timeout-minutes"] == 5
    assert "schedule:" not in text and "upload-artifact" not in text
    assert "TELEGRAM" not in text and "OPENAI" not in text and "CLAUDE" not in text
    assert "persist-credentials: false" in text and '"$TARGET_DATE"' in text
