"""Synthetic crypto observations and permissions; never market or licensing evidence."""

from datetime import UTC, datetime, timedelta

from investo.models.coverage import SourceOutcome
from investo.models.insights import InsightSourceQualification, InsightTime, SourceInsightEnvelope
from investo.models.insights_crypto import (
    CG_DOMINANCE,
    CG_MARKET_CAP,
    CRYPTO_RECIPES,
    CRYPTO_SOURCES,
    FNG,
    LLAMA_SUPPLY,
    LLAMA_TVL,
    derivative_recipe,
)
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.insights_projection import project_module

NOW = datetime(2026, 10, 25, 4, tzinfo=UTC)


def clock(now=NOW, *, funding=False, seconds=28800):
    extra = (
        dict(
            applicable_start=now - timedelta(seconds=seconds / 2),
            applicable_end=now + timedelta(seconds=seconds / 2),
        )
        if funding
        else {}
    )
    return InsightTime(basis="source_response", precision="exact", exact_at=now, **extra)


def rows(now=NOW):
    collection = InsightTime(
        basis="collection_window",
        precision="exact",
        window_start=now - timedelta(seconds=2),
        window_end=now,
    )
    return (
        CG_DOMINANCE.metric("58.33", clock(now).model_copy(update={"source_updated_at": now})),
        CG_MARKET_CAP.metric(
            "2500000000000.12345", clock(now).model_copy(update={"source_updated_at": now})
        ),
        LLAMA_SUPPLY.metric("280000000000.555", collection),
        LLAMA_TVL.metric("120000000000.2222", collection),
        derivative_recipe("btc_funding", "Bybit", interval_seconds=28800).metric(
            "0.0001", clock(now, funding=True)
        ),
        derivative_recipe("btc_oi_usd", "Bybit").metric("5000000000.01", clock(now)),
        derivative_recipe("btc_funding", "OKX", interval_seconds=28800).metric(
            "-0.0002", clock(now, funding=True)
        ),
        derivative_recipe("btc_oi_usd", "OKX").metric("600000000.001", clock(now)),
        FNG.metric("51", clock(now)),
    )


def qualifications(recipes=CRYPTO_RECIPES):
    return tuple(
        InsightSourceQualification(
            source_name=r.source_name,
            endpoint=r.endpoint,
            field_scope=r.field_scope,
            definition_ids=(r.definition_id,),
            definitions=(r.definition(),),
            display_allowed=True,
            public_git_history_allowed=True,
            retention_allowed=True,
            evidence_hrefs=("https://example.invalid/synthetic-permission",),
            checked_on=NOW.date(),
            attribution="Synthetic permission fixture only",
            allowed_hrefs=(r.endpoint, r.href),
        )
        for r in recipes
    )


def capture(values=None, *, statuses=None, origins=None):
    values = rows() if values is None else values
    statuses = statuses or {}
    origins = origins or {}
    bundles = tuple(
        SourceInsightEnvelope(
            source_name=r.source_name,
            origin_adapter_name=origins.get(r.source_name, r.source_name),
            metrics=(r,),
        )
        for r in values
    )
    outcomes = tuple(
        SourceOutcome(
            source_name=name,
            category="macro",
            status=statuses.get(name, "ok"),
            item_count=max(1, sum(r.source_name == name for r in values))
            if statuses.get(name, "ok") == "ok"
            else 0,
            failure_reason="Synthetic failure" if statuses.get(name) == "failed" else None,
            transient=True if statuses.get(name) == "failed" else None,
            skip_reason="operator_disabled" if statuses.get(name) == "skipped" else None,
        )
        for name in CRYPTO_SOURCES
    )
    return InsightCapture(bundles, outcomes)


def module(values=None, *, now=NOW, previous=None, rights=None, captured=None, statuses=None):
    return project_module(
        "crypto",
        captured or capture(values, statuses=statuses),
        qualifications() if rights is None else rights,
        run_started_at=now,
        collection_completed_at=now,
        evaluated_at=now,
        previous=previous,
    )
