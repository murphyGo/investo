from datetime import date, timedelta
from decimal import Decimal

import pytest

from investo.models.coverage import SourceOutcome
from investo.models.insights import (
    InsightTime,
    SourceInsightEnvelope,
    canonical_bytes,
)
from investo.models.insights_calendar import expected_observation
from investo.orchestrator.insights import InsightCapture, InsightsConfig
from investo.orchestrator.insights_projection import exact_change, freshness, update_history
from tests._helpers.insights import NOW, capture, metric, module, qualification


@pytest.mark.parametrize(
    "env",
    [
        {"INVESTO_INSIGHTS_MODE": "typo"},
        {"INVESTO_INSIGHTS_MODULES": "other"},
        {"INVESTO_INSIGHTS_MODULES": "macro,macro"},
        {"INVESTO_INSIGHTS_MODULES": ""},
    ],
)
def test_config_unknown_rejected(env):
    with pytest.raises(ValueError):
        InsightsConfig.from_env(env)


def test_config_default_off():
    assert InsightsConfig.from_env({}) == InsightsConfig()


def test_failed_current_preserves_qualified_last_good():
    prior = module()
    no_input = InsightCapture(
        (),
        (
            SourceOutcome.from_failure(
                "bybit-derivatives", "macro", message="SECRET", transient=True
            ),
        ),
    )
    result = module(previous=prior, captured=no_input, now=NOW + timedelta(hours=37))
    assert result.metrics[0].value == Decimal("2.5")
    assert result.metrics[0].last_good and result.metrics[0].freshness == "stale"
    assert result.metrics[0].latest_attempt == "failed"
    assert b"SECRET" not in canonical_bytes(result)


def test_revocation_removes_current_last_good_and_history():
    prior = module()
    history = update_history(prior, None, (qualification(),))
    denied = (qualification(revoked=True),)
    result = module(previous=prior, qualifications=denied)
    assert result.metrics == ()
    assert update_history(result, history, denied).rows == ()


def test_retention_denied_still_allows_current():
    qs = (qualification(retention_allowed=False),)
    result = module(qualifications=qs)
    assert result.metrics
    assert not update_history(result, None, qs).rows


def test_provider_change_breaks_chain_and_missing_exact_baseline():
    prior = module()
    history = update_history(prior, None, (qualification(),))
    changed = metric(provider="other")
    current = module(changed)
    history = update_history(current, history, (qualification(changed),))
    assert len(history.definitions) == 1
    assert history.definitions[0].metric.provider == "other"
    assert exact_change(current.metrics[0], history, baseline_observation_key="2026-10-02") is None


def test_same_day_revision_tracks_original_hash():
    prior = module()
    history = update_history(prior, None, (qualification(),))
    changed = module(metric(value="3"))
    revised = update_history(changed, history, (qualification(),))
    assert len(revised.rows) == 1
    assert revised.rows[0].revised_from == history.rows[0].record_hash


def test_conflicting_duplicate_suppressed():
    rows = (metric(), metric(value="7"))
    env = SourceInsightEnvelope(
        source_name=rows[0].source_name, origin_adapter_name=rows[0].source_name, metrics=rows
    )
    result = module(captured=InsightCapture((env,), capture().outcomes))
    assert not result.metrics and "definition_conflict" in result.reasons


def test_fallback_origin_is_not_overwritten_by_standalone_failure():
    row = metric(source_name="okx-derivatives")
    cap = capture(row, origin="bybit-derivatives")
    cap = InsightCapture(
        cap.envelopes, (*cap.outcomes, SourceOutcome.zero("okx-derivatives", "macro"))
    )
    assert module(row, captured=cap).metrics[0].latest_attempt == "ok"
    forged = capture(row, origin="other")
    assert not module(row, captured=forged).metrics


def test_unknown_source_time_suppressed():
    row = metric(time=InsightTime(basis="source_response", precision="unknown"))
    assert not module(row).metrics


def test_unsupported_year_unknown():
    row = metric(
        module="macro",
        cadence="daily",
        calendar_policy="treasury",
        time=InsightTime(
            basis="effective_date",
            precision="date",
            local_date=date(2027, 1, 4),
            source_timezone="America/New_York",
        ),
    )
    assert freshness(row, NOW.replace(year=2027)) == "unknown"


def test_july3_sofr_and_effr_publication_differ():
    at = NOW.replace(month=7, day=3, hour=15)
    assert expected_observation(at, "sofr") == date(2026, 7, 1)
    assert expected_observation(at, "effr") == date(2026, 7, 2)
    assert expected_observation(at.replace(day=6), "sofr") == date(2026, 7, 2)


def test_h10_daily_observations_follow_weekly_release():
    at = NOW.replace(hour=16, day=8)
    assert expected_observation(at, "h10") == date(2026, 10, 2)
    holiday = NOW.replace(day=12)
    assert expected_observation(holiday, "h10") == date(2026, 10, 2)
    assert expected_observation(holiday.replace(day=13), "h10") == date(2026, 10, 9)


def test_snapshot_window_is_not_run_clock():
    row = metric(
        time=InsightTime(
            basis="collection_window",
            precision="exact",
            window_start=NOW - timedelta(minutes=1),
            window_end=NOW,
        )
    )
    assert freshness(row, NOW + timedelta(hours=37)) == "stale"
    assert row.time.exact_at is None


@pytest.mark.parametrize("offset", [timedelta(hours=1), -timedelta(hours=37)])
def test_unconfirmed_unknown_or_stale_snapshot_is_not_new_public_number(offset):
    row = metric(
        time=InsightTime(basis="source_response", precision="exact", exact_at=NOW + offset)
    )
    result = module(row)
    assert result.metrics == ()
    assert result.availability == "unavailable"


def test_reviewed_semantics_must_match_not_only_definition_string():
    row = metric(unit="usd")
    result = module(row, qualifications=(qualification(),))
    assert not result.metrics and "definition_conflict" in result.reasons


def test_future_exact_clock_not_hidden_by_past_update_clock():
    clock = InsightTime(
        basis="source_response",
        precision="exact",
        exact_at=NOW + timedelta(hours=1),
        source_updated_at=NOW,
    )
    assert module(metric(time=clock)).metrics == ()


def test_items_only_has_no_invented_last_good_attempt():
    result = module(previous=module(), captured=InsightCapture((), ()))
    assert not result.metrics
    assert "missing_input" in result.reasons


def test_unsupported_monthly_year_does_not_claim_freshness():
    clock = InsightTime(basis="period", precision="month", period="2027-09")
    row = metric(
        module="macro",
        cadence="monthly",
        time=clock,
        next_release_at=NOW.replace(year=2027) + timedelta(days=30),
    )
    assert freshness(row, NOW.replace(year=2027)) == "unknown"
