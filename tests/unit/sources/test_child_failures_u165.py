"""All-child failures are distinct from valid empty and bounded partial data."""

import asyncio
import logging
from datetime import UTC, date, datetime

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo.models import NormalizedItem
from investo.sources import bea_macro_actuals as bea
from investo.sources._window import FetchWindow
from investo.sources.krx_foreign_flows import KrxForeignFlowsAdapter
from investo.sources.protocol import SourceFetchError

_WINDOW = FetchWindow.from_kst_date(date(2026, 10, 8))
_ITEM = NormalizedItem(
    source_name="bea-macro-actuals",
    category="macro",
    title="Synthetic actual",
    published_at=datetime(2026, 10, 8, tzinfo=UTC),
)


def _failure(transient=False):
    return SourceFetchError(
        source_name="bea-macro-actuals",
        message="synthetic secret-bearing error not for logs",
        transient=transient,
    )


@pytest.mark.parametrize("results", [(False, False), (False, True), (True, False), (True, True)])
async def test_naver_all_fail_vs_valid_empty(monkeypatch, results) -> None:
    async def fetch_market(self, client, *, market, **kwargs):
        if not results[0 if market == "KOSPI" else 1]:
            raise _failure()
        return []

    monkeypatch.setattr(KrxForeignFlowsAdapter, "_fetch_market", fetch_market)
    async with httpx.AsyncClient() as client:
        if not any(results):
            with pytest.raises(SourceFetchError, match="all investor-flow"):
                await KrxForeignFlowsAdapter().fetch(client, _WINDOW)
        else:
            assert await KrxForeignFlowsAdapter().fetch(client, _WINDOW) == []


async def test_naver_programmer_failure_propagates(monkeypatch) -> None:
    async def fetch_market(*args, **kwargs):
        raise TypeError("synthetic programmer error")

    monkeypatch.setattr(KrxForeignFlowsAdapter, "_fetch_market", fetch_market)
    async with httpx.AsyncClient() as client:
        with pytest.raises(TypeError):
            await KrxForeignFlowsAdapter().fetch(client, _WINDOW)


@pytest.mark.parametrize("kind", ["http", "api", "schema", "empty"])
async def test_bea_all_child_failure_vs_valid_empty(monkeypatch, caplog, kind) -> None:
    monkeypatch.setenv("BEA_API_KEY", "u165-synthetic-sentinel")
    payload = {
        "api": {"BEAAPI": {"Results": {"Error": {"text": "raw-private-error"}}}},
        "schema": {"BEAAPI": {"Results": {"Data": {}}}},
        "empty": {"BEAAPI": {"Results": {"Data": []}}},
    }

    async def retry_get(*args, **kwargs):
        if kind == "http":
            raise _failure(True)
        return httpx.Response(200, json=payload[kind])

    monkeypatch.setattr(bea, "retry_get", retry_get)
    with caplog.at_level(logging.INFO), pytest.MonkeyPatch.context():
        async with httpx.AsyncClient() as client:
            if kind == "empty":
                assert await bea.BeaMacroActualsAdapter().fetch(client, _WINDOW) == []
            else:
                with pytest.raises(SourceFetchError) as error:
                    await bea.BeaMacroActualsAdapter().fetch(client, _WINDOW)
                assert error.value.transient == (kind == "http")
    assert "raw-private-error" not in caplog.text
    assert "u165-synthetic-sentinel" not in caplog.text


async def test_bea_remaining_retry_budget_decreases(monkeypatch) -> None:
    monkeypatch.setenv("BEA_API_KEY", "synthetic")
    budgets = []

    async def retry_get(*args, **kwargs):
        budgets.append(kwargs["config"].total_budget_s)
        await asyncio.sleep(0.002)
        return httpx.Response(200, json={"BEAAPI": {"Results": {"Data": []}}})

    monkeypatch.setattr(bea, "retry_get", retry_get)
    async with httpx.AsyncClient() as client:
        assert await bea.BeaMacroActualsAdapter().fetch(client, _WINDOW) == []
    assert 0 < budgets[2] < budgets[1] < budgets[0] <= 60


@pytest.mark.parametrize("partial", [False, True])
async def test_bea_deadline_preserves_completed_items(monkeypatch, partial) -> None:
    monkeypatch.setenv("BEA_API_KEY", "synthetic")
    monkeypatch.setattr(bea, "_ADAPTER_BUDGET_S", 0.03)
    called = []

    async def fetch_one(self, client, series, *args, **kwargs):
        called.append(series.code)
        if partial and len(called) == 1:
            return _ITEM
        await asyncio.sleep(10)
        pytest.fail("outer deadline must cancel child")

    monkeypatch.setattr(bea.BeaMacroActualsAdapter, "_fetch_one", fetch_one)
    async with httpx.AsyncClient() as client:
        started = asyncio.get_running_loop().time()
        if partial:
            assert await bea.BeaMacroActualsAdapter().fetch(client, _WINDOW) == [_ITEM]
        else:
            with pytest.raises(SourceFetchError) as error:
                await bea.BeaMacroActualsAdapter().fetch(client, _WINDOW)
            assert error.value.transient
        assert asyncio.get_running_loop().time() - started < 1
    assert len(called) == (2 if partial else 1)


@pytest.mark.parametrize("error_type", [TypeError, TimeoutError, asyncio.CancelledError])
async def test_bea_non_source_failures_propagate(monkeypatch, error_type) -> None:
    monkeypatch.setenv("BEA_API_KEY", "synthetic")

    async def fetch_one(*args, **kwargs):
        raise error_type()

    monkeypatch.setattr(bea.BeaMacroActualsAdapter, "_fetch_one", fetch_one)
    async with httpx.AsyncClient() as client:
        with pytest.raises(error_type):
            await bea.BeaMacroActualsAdapter().fetch(client, _WINDOW)


@pytest.mark.parametrize("value", [None, True, False, "NaN", "inf", "--", "(D)", ""])
def test_bea_unknown_values_stay_unknown(value) -> None:
    assert bea._clean_value(value) == ""


@given(st.integers(min_value=-(10**9), max_value=10**9))
@settings(max_examples=50)
def test_bea_numeric_cleaner_preserves_true_zero_and_sign(value) -> None:
    assert bea._clean_value(value) == str(value)


def test_bea_invalid_latest_period_does_not_hide_valid_later_row() -> None:
    rows = [
        {"LineNumber": "1", "DataValue": "2", "TimePeriod": "invalid"},
        {"LineNumber": "1", "DataValue": "0", "TimePeriod": "2026Q3"},
    ]
    assert bea._first_matching_row(rows, bea._SERIES[0]) == (1, rows[1])
