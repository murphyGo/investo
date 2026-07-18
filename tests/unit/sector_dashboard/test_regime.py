from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo.models.sector import (
    AxisState,
    MetricMissingReason,
    SectorRegime,
    SectorTicker,
)
from investo.sector_dashboard.regime import (
    classify_regime_history,
    classify_sector_regime,
    neutral_band_ratio,
    regime_policy_for_band,
    resolve_axis_state,
)


@pytest.mark.parametrize(
    ("strength", "acceleration", "expected"),
    [
        ("0.002", "0.002", SectorRegime.LEADING),
        ("0.002", "-0.002", SectorRegime.WEAKENING),
        ("-0.002", "0.002", SectorRegime.RECOVERING),
        ("-0.002", "-0.002", SectorRegime.LAGGING),
    ],
)
def test_closed_regime_matrix(strength: str, acceleration: str, expected: SectorRegime) -> None:
    assert (
        classify_sector_regime(
            relative_strength_21d=Decimal(strength),
            acceleration_5d=Decimal(acceleration),
            neutral_band=Decimal("0.001"),
        )
        is expected
    )


def test_closed_band_retains_prior_state_and_initial_zero_is_negative() -> None:
    band = Decimal("0.001")
    assert (
        resolve_axis_state(
            Decimal("0.001"),
            neutral_band=band,
            previous_state=AxisState.NEGATIVE,
        )
        is AxisState.NEGATIVE
    )
    assert (
        resolve_axis_state(
            Decimal("-0.001"),
            neutral_band=band,
            previous_state=AxisState.POSITIVE,
        )
        is AxisState.POSITIVE
    )
    assert resolve_axis_state(Decimal(0), neutral_band=band) is AxisState.NEGATIVE
    assert resolve_axis_state(band, neutral_band=band) is AxisState.POSITIVE


def test_history_carries_axis_state_through_neutral_values() -> None:
    result = classify_regime_history(
        SectorTicker.XLC,
        (
            (Decimal("0.002"), Decimal("-0.002")),
            (Decimal("0.0002"), Decimal("-0.0002")),
            (Decimal("0.0001"), Decimal("0.003")),
        ),
    )
    assert result.regime is SectorRegime.LEADING
    assert result.strength_state is AxisState.POSITIVE
    assert result.acceleration_state is AxisState.POSITIVE


def test_missing_current_value_suppresses_history_and_all_policy_bands_are_versioned() -> None:
    result = classify_regime_history(
        SectorTicker.XLC,
        ((Decimal("0.01"), Decimal("0.01")),),
        current_missing_reason=MetricMissingReason.SECTOR_DATE_MISSING,
    )
    assert result.regime is SectorRegime.INSUFFICIENT
    assert result.missing_reason is MetricMissingReason.SECTOR_DATE_MISSING

    assert regime_policy_for_band(10).policy_id == "sector-regime-v1"
    for band in (0, 5, 15, 20):
        policy = regime_policy_for_band(band)
        assert policy.policy_id == f"sector-regime-v1-band-{band}"
        assert neutral_band_ratio(policy) == Decimal(band) / Decimal(10000)
    with pytest.raises(ValueError, match="0/5/10/15/20"):
        regime_policy_for_band(25)


@settings(max_examples=100, deadline=None)
@given(
    previous=st.sampled_from((AxisState.POSITIVE, AxisState.NEGATIVE)),
    band_bps=st.sampled_from((5, 10, 15, 20)),
    fraction=st.decimals(min_value="-1", max_value="1", places=6),
)
def test_neutral_band_hysteresis_property(
    previous: AxisState,
    band_bps: int,
    fraction: Decimal,
) -> None:
    band = Decimal(band_bps) / Decimal(10000)
    inside_value = band * fraction
    assert (
        resolve_axis_state(
            inside_value,
            neutral_band=band,
            previous_state=previous,
        )
        is previous
    )
