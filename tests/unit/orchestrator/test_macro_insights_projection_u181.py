from datetime import timedelta
from decimal import Decimal

import pytest

from investo.models.insights import InsightTime
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.insights_projection import update_history
from tests._helpers.macro_insights import NOW, capture, module, qualifications


def test_thirteen_slots_and_decimal_spreads():
    current = module()
    rows = {r.metric_id: r for r in current.metrics}
    assert len(rows) == 13
    assert rows["ust_10y_2y_bp"].value == Decimal("20.00")
    assert rows["sofr_effr_bp"].value == Decimal("15.00")
    assert rows["cpi_sa_index"].unit == "index"
    assert rows["cpi_sa_index"].freshness == "unknown"
    assert rows["cpi_sa_index"].time.period == "2026-09"
    history = update_history(current, None, qualifications())
    monthly = {r.comparison_key() for r in rows.values() if r.cadence == "monthly"}
    assert not any(r.definition_key in monthly for r in history.rows)


@pytest.mark.parametrize(
    ("mid", "value"),
    [
        ("cpi_sa_index", "0"),
        ("core_cpi_sa_index", "-1"),
        ("unemployment_rate", "101"),
        ("unemployment_rate", "-0.1"),
        ("usd_krw_h10", "0"),
    ],
)
def test_invalid_domain_value_is_card_local(mid, value):
    rows = {r.metric_id for r in module(capture({mid: value})).metrics}
    assert mid not in rows and "ust_2y" in rows


def test_negative_rate_is_valid():
    rows = {r.metric_id: r for r in module(capture({"ust_2y": "-0.25"})).metrics}
    assert rows["ust_2y"].value == Decimal("-.25")


def test_mismatched_effective_date_never_derives_spread():
    data = capture()
    envelopes = []
    for e in data.envelopes:
        row = e.metrics[0]
        if row.metric_id == "effr":
            row = row.model_copy(
                update={
                    "time": InsightTime(
                        basis="effective_date",
                        precision="date",
                        local_date=row.time.local_date - timedelta(days=1),
                        source_timezone="America/New_York",
                    )
                }
            )
            e = e.model_copy(update={"metrics": (row,)})
        envelopes.append(e)
    current = module(InsightCapture(tuple(envelopes), data.outcomes))
    assert "sofr_effr_bp" not in {r.metric_id for r in current.metrics}


def test_parent_rights_withdrawal_blocks_derived_value():
    rights = tuple(
        q.model_copy(update={"revoked": True}) if q.field_scope == "BC_2YEAR" else q
        for q in qualifications()
    )
    rows = {r.metric_id for r in module(rights=rights).metrics}
    assert "ust_2y" not in rows and "ust_10y_2y_bp" not in rows
    assert "ust_10y" in rows


def test_next_release_unknown_does_not_allow_future_period_or_timestamp():
    data = capture()
    envelopes = []
    for e in data.envelopes:
        row = e.metrics[0]
        if row.metric_id == "cpi_sa_index":
            clock = InsightTime(
                basis="period",
                precision="month",
                period="2026-09",
                source_timezone="America/New_York",
                source_updated_at=NOW + timedelta(days=1),
            )
            e = e.model_copy(update={"metrics": (row.model_copy(update={"time": clock}),)})
        envelopes.append(e)
    assert "cpi_sa_index" not in {
        r.metric_id for r in module(InsightCapture(tuple(envelopes), data.outcomes)).metrics
    }


@pytest.mark.parametrize("value", ["1e999999999", "1e-999999999"])
def test_pathological_exponent_rejected_before_rendering(value):
    with pytest.raises(ValueError):
        capture({"ust_2y": value})


def test_parent_withdrawal_removes_last_good_spread_and_history():
    from investo.orchestrator.insights_projection import project_module

    previous = module()
    history = update_history(previous, None, qualifications())
    rights = tuple(
        q.model_copy(update={"display_allowed": False}) if q.field_scope == "BC_2YEAR" else q
        for q in qualifications()
    )
    current = project_module(
        "macro",
        InsightCapture((), capture().outcomes),
        rights,
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
        previous=previous,
    )
    assert "ust_10y_2y_bp" not in {r.metric_id for r in current.metrics}
    updated = update_history(current, history, rights)
    denied = {
        d.key for d in history.definitions if d.metric.metric_id in {"ust_2y", "ust_10y_2y_bp"}
    }
    assert not any(r.definition_key in denied for r in updated.rows)


def test_parent_retention_denied_removes_derived_history_only():
    rights = tuple(
        q.model_copy(update={"retention_allowed": False}) if q.field_scope == "BC_2YEAR" else q
        for q in qualifications()
    )
    current = module(rights=rights)
    assert "ust_10y_2y_bp" in {r.metric_id for r in current.metrics}
    history = update_history(current, None, rights)
    assert "ust_10y_2y_bp" not in {d.metric.metric_id for d in history.definitions}


def test_spread_range_failure_preserves_healthy_sibling():
    rows = {r.metric_id for r in module(capture({"ust_10y": "1e64"})).metrics}
    assert "ust_2y" in rows and "ust_10y_2y_bp" not in rows


def test_supported_long_decimal_spread_has_no_implicit_rounding():
    current = module(capture({"ust_10y": "4.12345678901234567890123456789123456789"}))
    value = next(r.value for r in current.metrics if r.metric_id == "ust_10y_2y_bp")
    assert value == Decimal("2.34567890123456789012345678912345678900")


def test_related_briefing_uses_only_confirmed_tree_and_valid_dates():
    from datetime import date

    from investo.orchestrator.insights_publication import verified_macro_briefing_date

    class Read:
        def run(self, *args):
            assert args[3] == "confirmed-sha"
            return "\n".join(
                [
                    "site_docs/archive/us-equity/2026/10/2026-10-08.md",
                    "site_docs/archive/us-equity/2026/10/2026-10-23.md",
                    "site_docs/archive/us-equity/2026/10/2026-10-30.md",
                    "site_docs/archive/us-equity/2026/09/2026-10-24.md",
                ]
            )

    assert verified_macro_briefing_date(Read(), "confirmed-sha", module()) == date(2026, 10, 23)


def test_default_qualification_keeps_conditional_sources_blocked():
    from investo.orchestrator.insights import load_qualifications

    rights = tuple(
        q for q in load_qualifications() if any(d.module == "macro" for d in q.definitions)
    )
    assert len(rights) == 13
    allowed = {
        q.definitions[0].public_id
        for q in rights
        if q.display_allowed and q.public_git_history_allowed
    }
    assert len(allowed) == 9
    assert not allowed & {"sofr", "effr", "sofr_effr_bp", "usd_krw_h10"}
    assert {r.metric_id for r in module(rights=rights).metrics} == allowed
