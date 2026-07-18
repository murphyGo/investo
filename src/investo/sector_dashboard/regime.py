"""Deterministic neutral-band regime classification for the private sector radar.

The classifier is intentionally side-effect free.  It consumes already-computed
relative-strength and acceleration observations, carries the two axis states through
eligible history, and returns the closed u139 regime contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final, Literal, cast

from investo.models.sector import (
    PRIMARY_REGIME_POLICY,
    REGIME_BANDS_BPS,
    AxisState,
    MetricMissingReason,
    RegimePolicy,
    RegimeResult,
    SectorRegime,
    SectorTicker,
)

_BPS_DENOMINATOR: Final[Decimal] = Decimal("10000")
_REGIME_BY_AXES: Final[dict[tuple[AxisState, AxisState], SectorRegime]] = {
    (AxisState.POSITIVE, AxisState.POSITIVE): SectorRegime.LEADING,
    (AxisState.POSITIVE, AxisState.NEGATIVE): SectorRegime.WEAKENING,
    (AxisState.NEGATIVE, AxisState.POSITIVE): SectorRegime.RECOVERING,
    (AxisState.NEGATIVE, AxisState.NEGATIVE): SectorRegime.LAGGING,
}
RegimeBand = Literal[0, 5, 10, 15, 20]


def regime_policy_for_band(neutral_band_bps: int) -> RegimePolicy:
    """Return the fixed primary or sensitivity policy for an approved band."""

    if neutral_band_bps not in REGIME_BANDS_BPS:
        raise ValueError("neutral band must be one of 0/5/10/15/20 bps")
    if neutral_band_bps == PRIMARY_REGIME_POLICY.neutral_band_bps:
        return PRIMARY_REGIME_POLICY
    return RegimePolicy(
        policy_id=f"sector-regime-v1-band-{neutral_band_bps}",
        neutral_band_bps=cast(RegimeBand, neutral_band_bps),
    )


def neutral_band_ratio(policy: RegimePolicy) -> Decimal:
    """Convert a policy's basis-point band to its exact ratio boundary."""

    return Decimal(policy.neutral_band_bps) / _BPS_DENOMINATOR


def resolve_axis_state(
    value: Decimal,
    *,
    neutral_band: Decimal,
    previous_state: AxisState | None = None,
) -> AxisState:
    """Apply the closed neutral band and hysteresis rule to one axis value.

    Values strictly outside the band select their sign.  Values inside the closed
    band retain the previous state.  The first eligible value uses its raw sign, with
    exactly zero initialized as negative.
    """

    if not value.is_finite() or not neutral_band.is_finite() or neutral_band < 0:
        raise ValueError("axis value and neutral band must be finite and band non-negative")
    if value > neutral_band:
        return AxisState.POSITIVE
    if value < -neutral_band:
        return AxisState.NEGATIVE
    if previous_state is not None:
        return previous_state
    return AxisState.POSITIVE if value > 0 else AxisState.NEGATIVE


def classify_sector_regime(
    *,
    relative_strength_21d: Decimal,
    acceleration_5d: Decimal,
    neutral_band: Decimal,
    previous_strength_state: AxisState | None = None,
    previous_acceleration_state: AxisState | None = None,
) -> SectorRegime:
    """Classify one eligible observation using optional prior axis states."""

    strength_state = resolve_axis_state(
        relative_strength_21d,
        neutral_band=neutral_band,
        previous_state=previous_strength_state,
    )
    acceleration_state = resolve_axis_state(
        acceleration_5d,
        neutral_band=neutral_band,
        previous_state=previous_acceleration_state,
    )
    return _REGIME_BY_AXES[(strength_state, acceleration_state)]


def classify_regime_history(
    ticker: SectorTicker,
    observations: Sequence[tuple[Decimal, Decimal]],
    *,
    policy: RegimePolicy = PRIMARY_REGIME_POLICY,
    current_missing_reason: MetricMissingReason | None = None,
) -> RegimeResult:
    """Carry axis states through eligible observations and classify the latest one.

    The caller supplies observations in chronological order.  Discontinuous dates
    are omitted by the metric layer rather than interpolated; a missing current value
    is passed explicitly and always suppresses the final regime.
    """

    if current_missing_reason is not None:
        return _insufficient_result(ticker, policy, current_missing_reason)
    if not observations:
        return _insufficient_result(
            ticker,
            policy,
            MetricMissingReason.INSUFFICIENT_HISTORY,
        )

    band = neutral_band_ratio(policy)
    strength_state: AxisState | None = None
    acceleration_state: AxisState | None = None
    for relative_strength, acceleration in observations:
        try:
            strength_state = resolve_axis_state(
                relative_strength,
                neutral_band=band,
                previous_state=strength_state,
            )
            acceleration_state = resolve_axis_state(
                acceleration,
                neutral_band=band,
                previous_state=acceleration_state,
            )
        except ValueError:
            return _insufficient_result(
                ticker,
                policy,
                MetricMissingReason.NUMERIC_INVALID,
            )

    assert strength_state is not None
    assert acceleration_state is not None
    return RegimeResult(
        ticker=ticker,
        regime=_REGIME_BY_AXES[(strength_state, acceleration_state)],
        strength_state=strength_state,
        acceleration_state=acceleration_state,
        policy_id=policy.policy_id,
    )


def _insufficient_result(
    ticker: SectorTicker,
    policy: RegimePolicy,
    reason: MetricMissingReason,
) -> RegimeResult:
    return RegimeResult(
        ticker=ticker,
        regime=SectorRegime.INSUFFICIENT,
        policy_id=policy.policy_id,
        missing_reason=reason,
    )


__all__ = [
    "classify_regime_history",
    "classify_sector_regime",
    "neutral_band_ratio",
    "regime_policy_for_band",
    "resolve_axis_state",
]
