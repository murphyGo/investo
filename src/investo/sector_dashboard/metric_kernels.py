"""Source-neutral mathematical kernels shared by sector dashboards.

The functions in this module know only ordered positive values and stable
identity keys.  Source-specific semantics stay in the public ``nav_*`` and
``iex_price_*`` wrappers owned by their respective products.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Hashable, Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from itertools import pairwise
from typing import Literal, TypeVar

KeyT = TypeVar("KeyT", bound=Hashable)
VolatilityReturnKind = Literal["simple", "log"]


def simple_return(start_value: Decimal, end_value: Decimal) -> Decimal:
    """Return ``end_value / start_value - 1`` in the fixed decimal context."""

    _validate_positive_values((start_value, end_value))
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = end_value / start_value - Decimal(1)
    return _finite_decimal(result)


def excess_return(
    subject_start_value: Decimal,
    subject_end_value: Decimal,
    benchmark_start_value: Decimal,
    benchmark_end_value: Decimal,
) -> Decimal:
    """Compute subject simple return minus benchmark simple return."""

    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = simple_return(subject_start_value, subject_end_value) - simple_return(
            benchmark_start_value,
            benchmark_end_value,
        )
    return _finite_decimal(result)


def relative_acceleration_5d(
    subject_t_minus_10: Decimal,
    subject_t_minus_5: Decimal,
    subject_t: Decimal,
    benchmark_t_minus_10: Decimal,
    benchmark_t_minus_5: Decimal,
    benchmark_t: Decimal,
) -> Decimal:
    """Subtract the preceding non-overlapping 5D excess from the current 5D excess."""

    current = excess_return(
        subject_t_minus_5,
        subject_t,
        benchmark_t_minus_5,
        benchmark_t,
    )
    previous = excess_return(
        subject_t_minus_10,
        subject_t_minus_5,
        benchmark_t_minus_10,
        benchmark_t_minus_5,
    )
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        result = current - previous
    return _finite_decimal(result)


def realized_volatility_20d(
    values: Sequence[Decimal],
    *,
    return_kind: VolatilityReturnKind,
) -> Decimal:
    """Annualize the sample deviation of twenty daily returns.

    ``log`` preserves the u139 private NAV contract.  ``simple`` is the u145
    public IEX close-to-close contract.  Keeping the choice explicit prevents
    either product from silently inheriting the other's statistical label.
    """

    if len(values) != 21:
        raise ValueError("20D realized volatility requires exactly 21 values")
    if return_kind not in {"simple", "log"}:
        raise ValueError("return_kind must be simple or log")
    _validate_positive_values(values)
    daily_returns: list[float] = []
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        for previous, current in pairwise(values):
            ratio = current / previous
            ratio_float = float(ratio)
            if not math.isfinite(ratio_float) or ratio_float <= 0:
                raise ValueError("daily value ratio must be finite and positive")
            daily_returns.append(
                math.log(ratio_float) if return_kind == "log" else ratio_float - 1.0
            )
    volatility = statistics.stdev(daily_returns) * math.sqrt(252.0)
    if not math.isfinite(volatility) or volatility < 0:
        raise ValueError("realized volatility must be finite and non-negative")
    return Decimal(repr(volatility))


def max_drawdown_20d(values: Sequence[Decimal]) -> Decimal:
    """Return the minimum value/running-peak drawdown over exactly 21 points."""

    if len(values) != 21:
        raise ValueError("20D max drawdown requires exactly 21 values")
    _validate_positive_values(values)
    peak = values[0]
    worst = Decimal(0)
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        for value in values:
            peak = max(peak, value)
            drawdown = value / peak - Decimal(1)
            worst = min(worst, drawdown)
    return _finite_decimal(worst)


def descending_midrank_percentiles(
    values: Mapping[KeyT, Decimal],
    *,
    identity_order: Sequence[KeyT],
) -> dict[KeyT, Decimal]:
    """Map values to descending tied midrank percentiles in ``[0, 1]``."""

    if len(values) < 2:
        raise ValueError("midrank percentiles require at least two values")
    if len(set(identity_order)) != len(identity_order):
        raise ValueError("identity order must contain unique keys")
    position_by_key = {key: position for position, key in enumerate(identity_order)}
    if any(key not in position_by_key for key in values):
        raise ValueError("midrank values must use keys from identity_order")
    if any(not value.is_finite() for value in values.values()):
        raise ValueError("midrank values must be finite")

    ordered = sorted(values.items(), key=lambda item: position_by_key[item[0]])
    ordered.sort(key=lambda item: item[1], reverse=True)
    count = len(ordered)
    percentiles: dict[KeyT, Decimal] = {}
    position = 0
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        while position < count:
            group_end = position + 1
            while group_end < count and ordered[group_end][1] == ordered[position][1]:
                group_end += 1
            first_rank = Decimal(position + 1)
            last_rank = Decimal(group_end)
            midrank = (first_rank + last_rank) / Decimal(2)
            percentile = (Decimal(count) - midrank) / Decimal(count - 1)
            for group_position in range(position, group_end):
                percentiles[ordered[group_position][0]] = percentile
            position = group_end
    return percentiles


def _validate_positive_values(values: Sequence[Decimal]) -> None:
    if any(not value.is_finite() or value <= 0 for value in values):
        raise ValueError("values must be finite and strictly positive")


def _finite_decimal(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("numeric result must be finite")
    return value


__all__ = [
    "VolatilityReturnKind",
    "descending_midrank_percentiles",
    "excess_return",
    "max_drawdown_20d",
    "realized_volatility_20d",
    "relative_acceleration_5d",
    "simple_return",
]
