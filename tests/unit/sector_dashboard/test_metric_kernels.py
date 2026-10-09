"""Source-neutral kernel and u139 compatibility tests (TS-2)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo.models.sector import SECTOR_TICKERS, SectorTicker
from investo.sector_dashboard.metric_kernels import (
    descending_midrank_percentiles,
    excess_return,
    max_drawdown_20d,
    realized_volatility_20d,
    relative_acceleration_5d,
    simple_return,
)
from investo.sector_dashboard.metrics import (
    descending_midrank_percentiles as nav_descending_midrank_percentiles,
)
from investo.sector_dashboard.metrics import (
    nav_excess_return,
    nav_max_drawdown_20d,
    nav_realized_volatility_20d,
    nav_relative_acceleration_5d,
    nav_return,
)

PBT_SETTINGS = settings(max_examples=100, deadline=None)
POSITIVE_DECIMAL = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)


def test_u139_nav_wrappers_have_fixed_golden_digest() -> None:
    values = tuple(
        Decimal(str(value))
        for value in (
            100,
            101,
            99,
            102,
            103,
            101,
            104,
            106,
            105,
            107,
            108,
            106,
            109,
            111,
            110,
            112,
            115,
            114,
            116,
            118,
            117,
        )
    )
    payload = {
        "return": str(nav_return(Decimal("100"), Decimal("110"))),
        "excess": str(
            nav_excess_return(Decimal("100"), Decimal("110"), Decimal("100"), Decimal("105"))
        ),
        "acceleration": str(
            nav_relative_acceleration_5d(
                Decimal("100"),
                Decimal("102"),
                Decimal("108"),
                Decimal("100"),
                Decimal("101"),
                Decimal("104"),
            )
        ),
        "volatility": str(nav_realized_volatility_20d(values)),
        "drawdown": str(nav_max_drawdown_20d(values)),
        "midrank": {
            ticker.value: str(value)
            for ticker, value in nav_descending_midrank_percentiles(
                {
                    SectorTicker.XLC: Decimal("3"),
                    SectorTicker.XLY: Decimal("3"),
                    SectorTicker.XLP: Decimal("2"),
                    SectorTicker.XLE: Decimal("1"),
                }
            ).items()
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert hashlib.sha256(canonical).hexdigest() == (
        "1edbea4830774b00938d1660d54c1be1140c2ff312e93e6c8b8e65f8222d5b73"
    )


def test_u139_nav_wrapper_validation_messages_remain_compatible() -> None:
    with pytest.raises(ValueError, match="NAV values must be finite and strictly positive"):
        nav_return(Decimal("0"), Decimal("1"))
    with pytest.raises(ValueError, match="20D realized volatility requires exactly 21 NAV points"):
        nav_realized_volatility_20d((Decimal("1"),) * 20)
    with pytest.raises(ValueError, match="midrank values must use sector tickers"):
        nav_descending_midrank_percentiles(  # type: ignore[arg-type]
            {SectorTicker.XLC: Decimal("1"), SectorTicker.SPY: Decimal("0")}
        )


@given(start=POSITIVE_DECIMAL, end=POSITIVE_DECIMAL)
@PBT_SETTINGS
def test_nav_return_and_excess_wrappers_equal_neutral_kernels(
    start: Decimal,
    end: Decimal,
) -> None:
    assert nav_return(start, end) == simple_return(start, end)
    assert nav_excess_return(start, end, end, start) == excess_return(start, end, end, start)


@given(values=st.lists(POSITIVE_DECIMAL, min_size=21, max_size=21))
@PBT_SETTINGS
def test_nav_window_wrappers_equal_log_kernel_and_preserve_bounds(
    values: list[Decimal],
) -> None:
    assert nav_realized_volatility_20d(values) == realized_volatility_20d(values, return_kind="log")
    assert nav_max_drawdown_20d(values) == max_drawdown_20d(values)
    assert nav_realized_volatility_20d(values) >= 0
    assert Decimal("-1") < nav_max_drawdown_20d(values) <= 0


@given(
    subject=st.lists(POSITIVE_DECIMAL, min_size=3, max_size=3),
    benchmark=st.lists(POSITIVE_DECIMAL, min_size=3, max_size=3),
)
@PBT_SETTINGS
def test_acceleration_wrapper_equals_neutral_kernel(
    subject: list[Decimal],
    benchmark: list[Decimal],
) -> None:
    arguments = (*subject, *benchmark)
    assert nav_relative_acceleration_5d(*arguments) == relative_acceleration_5d(*arguments)


@given(
    values=st.lists(
        st.decimals(
            min_value=Decimal("-1000"),
            max_value=Decimal("1000"),
            allow_nan=False,
            allow_infinity=False,
            places=4,
        ),
        min_size=2,
        max_size=11,
        unique=True,
    )
)
@PBT_SETTINGS
def test_midrank_wrapper_equals_neutral_kernel_and_best_is_one(
    values: list[Decimal],
) -> None:
    mapping = dict(zip(SECTOR_TICKERS, values, strict=False))
    neutral = descending_midrank_percentiles(mapping, identity_order=SECTOR_TICKERS)

    assert nav_descending_midrank_percentiles(mapping) == neutral
    assert max(neutral.values()) == Decimal(1)
    assert min(neutral.values()) == Decimal(0)


@given(value=POSITIVE_DECIMAL)
@PBT_SETTINGS
def test_zero_return_and_excess_invariants(value: Decimal) -> None:
    assert simple_return(value, value) == 0
    assert excess_return(value, value, value, value) == 0
