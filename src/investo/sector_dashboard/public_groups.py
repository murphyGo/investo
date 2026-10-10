"""Fourteen bounded observation groups with explicit ETF/basket semantics."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException, localcontext
from typing import TypedDict

from investo.models.market_groups import (
    GROUP_DEFINITIONS,
    MARKET_GROUP_IDS,
    GroupCategory,
    GroupKind,
    MarketGroupDefinition,
    MarketGroupId,
    PublicAssetTicker,
)
from investo.models.sector import (
    MetricMissingReason,
    SectorCoverageStatus,
    SectorRegime,
    SectorTicker,
)
from investo.models.sector_public import (
    AdditionalParsedSet,
    PublicGroupRank,
    PublicGroupRegime,
    PublicMarketGroupBundle,
    PublicMarketGroupRecord,
    PublicPriceMetrics,
    PublicSectorDashboardSnapshot,
    PublicSectorSeriesBundle,
    SectorAvailability,
    ValuePoint,
)
from investo.sector_dashboard.metric_kernels import descending_midrank_percentiles
from investo.sector_dashboard.public_metrics import (
    PUBLIC_RANK_WEIGHTS,
    compute_public_price_metrics,
    identify_public_snapshot,
    missing_public_price_metrics,
    public_price_regime_observations,
)
from investo.sector_dashboard.regime import classify_price_regime_history


class _GroupMetadata(TypedDict):
    group_id: MarketGroupId
    name: str
    category: GroupCategory
    kind: GroupKind
    members: tuple[PublicAssetTicker, ...]
    scope: str


def representative_price_index(
    members: Sequence[Sequence[ValuePoint]], benchmark_dates: Sequence[date]
) -> tuple[ValuePoint, ...]:
    """Daily equal-weight simple returns, with every member/date required."""
    if not members or len(benchmark_dates) != 64:
        raise ValueError("basket requires members and all64 benchmark sessions")
    if any(
        tuple(point.trading_date for point in member) != tuple(benchmark_dates)
        for member in members
    ):
        raise ValueError("basket cannot fill or omit a member/date")
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        level = Decimal(100)
        result = [ValuePoint(trading_date=benchmark_dates[0], value=level)]
        for index in range(1, len(benchmark_dates)):
            ratio = sum(
                (member[index].value / member[index - 1].value for member in members), Decimal(0)
            ) / Decimal(len(members))
            level *= ratio
            result.append(ValuePoint(trading_date=benchmark_dates[index], value=level))
    return tuple(result)


def _additional_points(
    definition: MarketGroupDefinition, parsed: AdditionalParsedSet, dates: tuple[date, ...]
) -> tuple[ValuePoint, ...] | None:
    members = []
    for ticker in definition.members:
        series = parsed.assets.get(ticker) if not isinstance(ticker, SectorTicker) else None
        if series is None or tuple(point.trading_date for point in series.points) != dates:
            return None
        members.append(
            tuple(
                ValuePoint(trading_date=point.trading_date, value=point.close)
                for point in series.points
            )
        )
    if definition.kind is GroupKind.REPRESENTATIVE:
        return representative_price_index(members, dates)
    return members[0]


def _extra_record(
    definition: MarketGroupDefinition,
    parsed: AdditionalParsedSet,
    benchmark: tuple[ValuePoint, ...],
    target_date: date,
) -> PublicMarketGroupRecord:
    reason = MetricMissingReason.SECTOR_DATE_MISSING
    calculated: tuple[PublicPriceMetrics, PublicGroupRegime] | None = None
    try:
        points = _additional_points(
            definition, parsed, tuple(point.trading_date for point in benchmark)
        )
        if points is not None:
            metrics = compute_public_price_metrics(
                points,
                benchmark,
                coverage_status=SectorCoverageStatus.NORMAL,
                target_date=target_date,
            )
            regime, strength, acceleration, missing = classify_price_regime_history(
                public_price_regime_observations(points, benchmark, target_date=target_date)
            )
            if (
                all(metric.value is not None for _, metric in metrics)
                and regime is not SectorRegime.INSUFFICIENT
            ):
                calculated = (
                    metrics,
                    PublicGroupRegime(
                        regime=regime,
                        strength_state=strength,
                        acceleration_state=acceleration,
                        missing_reason=missing,
                    ),
                )
            reason = MetricMissingReason.NUMERIC_INVALID
    except (DecimalException, OverflowError, ValueError):
        reason = MetricMissingReason.NUMERIC_INVALID
    if calculated is not None:
        return PublicMarketGroupRecord(
            **_metadata(definition),
            availability=SectorAvailability.AVAILABLE,
            metrics=calculated[0],
            primary_regime=calculated[1],
            relative_rank=PublicGroupRank(
                comparable_group_count=0, missing_reason="insufficient_comparables"
            ),
        )
    return PublicMarketGroupRecord(
        **_metadata(definition),
        availability=SectorAvailability.TEMPORARILY_UNAVAILABLE,
        metrics=missing_public_price_metrics(reason),
        primary_regime=PublicGroupRegime(regime=SectorRegime.INSUFFICIENT, missing_reason=reason),
        relative_rank=PublicGroupRank(comparable_group_count=0, missing_reason="unavailable"),
    )


def _metadata(definition: MarketGroupDefinition) -> _GroupMetadata:
    return {
        "group_id": definition.group_id,
        "name": definition.name,
        "category": definition.category,
        "kind": definition.kind,
        "members": definition.members,
        "scope": definition.scope,
    }


def _rank_groups(records: Sequence[PublicMarketGroupRecord]) -> tuple[PublicMarketGroupRecord, ...]:
    available = [
        record for record in records if record.availability is SectorAvailability.AVAILABLE
    ]
    count = len(available)
    scores: dict[MarketGroupId, Decimal] = {}
    if count >= 8:
        with localcontext() as context:
            context.prec = 34
            context.rounding = ROUND_HALF_EVEN
            for horizon, weight in PUBLIC_RANK_WEIGHTS.items():
                values: dict[MarketGroupId, Decimal] = {}
                for record in available:
                    value = getattr(record.metrics, f"price_excess_{horizon}d").value
                    assert value is not None
                    values[record.group_id] = value
                percentiles = descending_midrank_percentiles(
                    values, identity_order=MARKET_GROUP_IDS
                )
                for group_id, percentile in percentiles.items():
                    scores[group_id] = scores.get(group_id, Decimal(0)) + percentile * weight
        # Compare the same normalized score that is stored and checked by the DTO.
        scores = {
            key: PublicGroupRank._normalize_score(value) or Decimal(0)
            for key, value in scores.items()
        }
    ordered = [key for key in MARKET_GROUP_IDS if key in scores]
    ordered.sort(key=lambda key: -scores[key])
    ordinals = {key: index for index, key in enumerate(ordered, 1)}
    result = []
    for record in records:
        rank = (
            PublicGroupRank(
                score=scores[record.group_id],
                ordinal=ordinals[record.group_id],
                comparable_group_count=count,
                used_horizons=(5, 21, 63),
            )
            if record.group_id in scores
            else PublicGroupRank(
                comparable_group_count=count,
                missing_reason="insufficient_comparables"
                if record.availability is SectorAvailability.AVAILABLE
                else "unavailable",
            )
        )
        result.append(record.model_copy(update={"relative_rank": rank}))
    return tuple(result)


def attach_public_market_groups(
    snapshot: PublicSectorDashboardSnapshot,
    bundle: PublicSectorSeriesBundle,
    additional: AdditionalParsedSet,
) -> PublicSectorDashboardSnapshot:
    """Attach same-date derived groups; preserve the original eleven-sector view."""
    if bundle.benchmark is None or snapshot.as_of_date is None:
        raise ValueError("groups require a valid benchmark and date")
    overview = {record.ticker: record for record in snapshot.records}
    records = []
    for definition in GROUP_DEFINITIONS:
        if len(definition.members) == 1 and isinstance(definition.members[0], SectorTicker):
            original = overview[definition.members[0]]
            records.append(
                PublicMarketGroupRecord(
                    **_metadata(definition),
                    availability=original.availability,
                    metrics=PublicPriceMetrics.model_validate(
                        original.metrics.model_dump(exclude={"ticker"})
                    ),
                    primary_regime=PublicGroupRegime.model_validate(
                        original.primary_regime.model_dump(exclude={"ticker"})
                    ),
                    relative_rank=PublicGroupRank(
                        comparable_group_count=0,
                        missing_reason="insufficient_comparables"
                        if original.availability is SectorAvailability.AVAILABLE
                        else "unavailable",
                    ),
                )
            )
        else:
            records.append(
                _extra_record(definition, additional, bundle.benchmark.points, snapshot.as_of_date)
            )
    records = list(_rank_groups(records))
    count = sum(record.availability is SectorAvailability.AVAILABLE for record in records)
    groups = PublicMarketGroupBundle(
        as_of_date=snapshot.as_of_date,
        available_group_count=count,
        comparable_group_count=count,
        records=tuple(records),
    )
    amended = PublicSectorDashboardSnapshot.model_validate(
        {
            **snapshot.model_dump(exclude={"snapshot_id"}),
            "schema_version": 3,
            "market_groups": groups,
        }
    )
    return identify_public_snapshot(amended)
