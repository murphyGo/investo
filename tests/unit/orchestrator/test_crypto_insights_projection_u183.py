"""Synthetic provider/definition/time/permission and daily history boundaries."""

from datetime import timedelta
from decimal import Decimal

import pytest

from investo.models.insights import (
    InsightTime,
    SourceInsightEnvelope,
    canonical_bytes,
    read_insight_history,
)
from investo.models.insights_crypto import CRYPTO_RECIPES, FNG, derivative_recipe
from investo.orchestrator.insights import InsightCapture, load_qualifications
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.crypto import seven_day_change
from tests._helpers.crypto_insights import NOW, capture, clock, module, qualifications, rows


def test_seven_slots_choose_bybit_without_summing_okx():
    current = module()
    assert len(current.metrics) == 7 and len(current.crypto_coverage.slots) == 7
    funding = next(r for r in current.metrics if r.metric_id == "btc_funding")
    oi = next(r for r in current.metrics if r.metric_id == "btc_oi_usd")
    assert funding.provider == oi.provider == "Bybit"
    assert funding.value == Decimal("0.0001") and oi.value == Decimal("5000000000.01")
    assert module(tuple(reversed(rows()))).snapshot_id == current.snapshot_id


def test_okx_fallback_origin_survives_failed_standalone_origin():
    values = rows()[6:8]
    captured = capture(
        values,
        statuses={"okx-derivatives": "failed"},
        origins={"okx-derivatives": "bybit-derivatives"},
    )
    result = module(captured=captured)
    assert len(result.metrics) == 2
    assert all(
        r.provider == "OKX" and r.origin_adapter_name == "bybit-derivatives" for r in result.metrics
    )


def test_identical_fallback_and_direct_sample_dedupe_but_newer_sample_is_selected():
    row = rows()[7]
    direct = capture((row,))
    fallback = SourceInsightEnvelope(
        source_name=row.source_name, origin_adapter_name="bybit-derivatives", metrics=(row,)
    )
    result = module(captured=InsightCapture((*direct.envelopes, fallback), direct.outcomes))
    assert len(result.metrics) == 1 and result.metrics[0].origin_adapter_name == "okx-derivatives"
    newer = row.model_copy(
        update={"time": clock(NOW + timedelta(seconds=1)), "value": Decimal("999")}
    )
    assert module((row, newer), now=NOW + timedelta(seconds=1)).metrics[0].value == 999


def test_conflicting_primary_sample_uses_healthy_fallback_and_never_revives_bad_primary():
    a = rows()[5]
    b = a.model_copy(update={"value": Decimal("1")})
    result = module((a, b, rows()[7]))
    assert result.metrics[0].provider == "OKX"
    result = module((a, b), previous=module((a,)))
    assert not result.metrics
    assert "definition_conflict" in result.crypto_coverage.slots[5].reasons


@pytest.mark.parametrize(
    "mid,value",
    [
        ("btc_dominance", "101"),
        ("btc_dominance", "-1"),
        ("market_cap_usd", "-1"),
        ("usd_stablecoin_supply", "-1"),
        ("chain_tvl_sum", "-1"),
        ("btc_oi_usd", "-1"),
        ("fear_greed_index", "1.5"),
        ("fear_greed_index", "101"),
    ],
)
def test_ranges_are_slot_local_and_fng_is_integer(mid, value):
    values = [
        r.model_copy(update={"value": Decimal(value)}) if r.metric_id == mid else r for r in rows()
    ]
    current = module(values)
    assert mid not in {r.metric_id for r in current.metrics}
    assert len(current.metrics) == 6
    assert (
        next(s for s in current.crypto_coverage.slots if s.metric_id == mid).availability
        == "unavailable"
    )


def test_wrong_instrument_unit_or_basis_is_rejected_before_public_values():
    a = rows()[5].model_copy(update={"scope_id": "ETHUSDT", "unit": "contracts"})
    b = rows()[4].model_copy(update={"methodology_id": "settled-annualized"})
    assert not module((a, b)).metrics


def test_known_source_clock_roles_cannot_be_relabelled_as_provider_updates():
    values = rows()
    llama = values[3].model_copy(update={"time": clock()})
    cg = values[0].model_copy(update={"time": clock()})
    bybit = values[5].model_copy(
        update={"time": clock().model_copy(update={"source_updated_at": NOW})}
    )
    result = module((llama, cg, bybit, values[-1]))
    assert {r.metric_id for r in result.metrics} == {"fear_greed_index"}


def test_unknown_collection_clock_is_unavailable_with_time_reason():
    row = rows()[3].model_copy(
        update={"time": InsightTime(basis="source_response", precision="unknown")}
    )
    result = module((row,))
    status = next(s for s in result.crypto_coverage.slots if s.metric_id == "chain_tvl_sum")
    assert status.availability == "unavailable" and "time_unknown" in status.reasons


def test_fresh_fallback_wins_over_stale_primary_and_future_clock_is_not_now():
    stale = rows()[5].model_copy(update={"time": clock(NOW - timedelta(hours=37))})
    future = rows()[0].model_copy(update={"time": clock(NOW + timedelta(seconds=1))})
    current = module((stale, rows()[7], future))
    assert len(current.metrics) == 1 and current.metrics[0].provider == "OKX"


def test_failed_last_good_preserves_source_clock_and_does_not_advance_history():
    old = module()
    prior = update_history(old, None, qualifications())
    current = module(
        (),
        now=NOW + timedelta(hours=40),
        previous=old,
        statuses={
            s: "failed"
            for s in (
                "bybit-derivatives",
                "okx-derivatives",
                "coingecko-global-market",
                "defillama-market-structure",
                "alternative-fng",
            )
        },
    )
    assert len(current.metrics) == 7 and all(
        r.last_good and r.freshness == "stale" for r in current.metrics
    )
    assert {r.metric_id: r.time for r in current.metrics} == {
        r.metric_id: r.time for r in old.metrics
    }
    assert update_history(current, prior, qualifications()).rows == prior.rows


def test_collection_utc_day_is_sample_key_even_if_source_clock_is_yesterday():
    now = NOW.replace(hour=0, minute=1)
    value = FNG.metric("51", clock(now - timedelta(minutes=2)))
    current = module((value,), now=now)
    history = update_history(current, None, qualifications())
    assert history.rows[0].observation_key == now.date().isoformat()
    assert history.rows[0].time.exact_at.date() != now.date()


def test_intraday_replacement_is_distinct_from_same_clock_revision():
    a = FNG.metric("50", clock())
    prior = update_history(module((a,)), None, qualifications())
    b = FNG.metric("51", clock(NOW + timedelta(minutes=1)))
    updated = update_history(module((b,), now=NOW + timedelta(minutes=1)), prior, qualifications())
    assert updated.rows[0].superseded_from == prior.rows[0].record_hash
    assert updated.rows[0].revised_from is None
    c = b.model_copy(update={"value": Decimal("52")})
    revised = update_history(
        module((c,), now=NOW + timedelta(minutes=1)), updated, qualifications()
    )
    assert revised.rows[0].revised_from == updated.rows[0].record_hash
    assert read_insight_history(canonical_bytes(revised)) == revised


def test_exact_seven_collection_days_with_compatible_contract_only():
    old_now = NOW - timedelta(days=7)
    old = module((FNG.metric("40", clock(old_now)),), now=old_now)
    prior = update_history(old, None, qualifications())
    current = module((FNG.metric("51", clock()),))
    history = update_history(current, prior, qualifications())
    assert seven_day_change(current.metrics[0], current, history) == 11
    no_baseline = update_history(current, None, qualifications())
    assert seven_day_change(current.metrics[0], current, no_baseline) is None


def test_provider_and_interval_switch_break_history_chains():
    old = module((rows()[5],))
    history = update_history(old, None, qualifications())
    new = module((rows()[7],))
    switched = update_history(new, history, qualifications())
    assert {d.metric.provider for d in switched.definitions} == {"OKX"}
    assert seven_day_change(new.metrics[0], new, switched) is None
    changed = derivative_recipe("btc_funding", "Bybit", interval_seconds=14400)
    rights = qualifications((*CRYPTO_RECIPES, changed))
    first = module((rows()[4],), rights=rights)
    prior = update_history(first, None, rights)
    new = module((changed.metric("0.0001", clock(funding=True, seconds=14400)),), rights=rights)
    updated = update_history(new, prior, rights)
    assert len(updated.definitions) == 1 and updated.definitions[0].key != prior.definitions[0].key


def test_production_permissions_allow_only_attributed_fng_and_no_blocked_history():
    rights = load_qualifications()
    current = module(rights=rights)
    assert {r.metric_id for r in current.metrics} == {"fear_greed_index"}
    history = update_history(current, None, rights)
    assert {d.metric.metric_id for d in history.definitions} == {"fear_greed_index"}
    revoked = [
        q.model_copy(update={"revoked": True}) if q.source_name == "alternative-fng" else q
        for q in rights
    ]
    after = module((), previous=current, rights=revoked, statuses={"alternative-fng": "failed"})
    assert not after.metrics and not update_history(after, history, revoked).rows


def test_private_cap_does_not_get_bypassed_by_dedupe_or_previous_values():
    current = capture((rows()[0],))
    too_large = InsightCapture(current.envelopes * 1000, current.outcomes)
    assert not module(captured=too_large, previous=module()).metrics
