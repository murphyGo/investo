"""FR-029: closed crypto semantics, exact decimal handling and cycle identity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DecimalException, localcontext

from pydantic import ValidationError

from investo.models.insights import (
    InsightDefinitionQualification,
    InsightTime,
    InsightUnit,
    SourceInsightEnvelope,
    SourceInsightMetric,
)

SAMPLE_POLICY = "utc-collection-day-last-confirmed"
CRYPTO_SOURCES = (
    "coingecko-global-market",
    "defillama-market-structure",
    "bybit-derivatives",
    "okx-derivatives",
    "alternative-fng",
)
CRYPTO_SLOTS = (
    "btc_dominance",
    "market_cap_usd",
    "usd_stablecoin_supply",
    "chain_tvl_sum",
    "btc_funding",
    "btc_oi_usd",
    "fear_greed_index",
)


def decimal_value(value: object) -> Decimal | None:
    try:
        return SourceInsightMetric.finite_decimal(value)
    except (ValueError, DecimalException):
        return None


def exact_scale(value: Decimal, scale: int) -> Decimal:
    with localcontext() as context:
        context.prec = 256
        return value * scale


def exact_difference(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 256
        return left - right


def safe_metric(
    recipe: CryptoRecipe, value: object, clock: InsightTime
) -> SourceInsightMetric | None:
    parsed = decimal_value(value)
    if parsed is None:
        return None
    try:
        return recipe.metric(parsed, clock)
    except ValidationError:
        return None


def envelope(
    source_name: str, metrics: list[SourceInsightMetric | None]
) -> SourceInsightEnvelope | None:
    accepted = tuple(row for row in metrics if row is not None)
    return SourceInsightEnvelope(source_name=source_name, metrics=accepted) if accepted else None


def epoch(value: object, *, milliseconds: bool = False) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).isdigit():
        return None
    try:
        numeric = int(value)
        if not 0 < numeric < (10**14 if milliseconds else 10**11):
            return None
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
            milliseconds=numeric if milliseconds else 0, seconds=0 if milliseconds else numeric
        )
    except (ValueError, OverflowError):
        return None


@dataclass(frozen=True, slots=True)
class CryptoRecipe:
    metric_id: str
    label: str
    source_name: str
    provider: str
    scope_id: str
    methodology_id: str
    unit: InsightUnit
    endpoint: str
    field_scope: str
    href: str
    interval_seconds: int | None = None

    @property
    def definition_id(self) -> str:
        suffix = f".indicative.{self.interval_seconds}s" if self.interval_seconds else ""
        return f"crypto.{self.metric_id}.{self.provider.lower()}{suffix}.v1"

    def metric(self, value: str | Decimal | int, clock: InsightTime) -> SourceInsightMetric:
        return SourceInsightMetric(
            module="crypto",
            metric_id=self.metric_id,
            definition_id=self.definition_id,
            source_name=self.source_name,
            provider=self.provider,
            scope_id=self.scope_id,
            methodology_id=self.methodology_id,
            sample_policy=SAMPLE_POLICY,
            unit=self.unit,
            label=self.label,
            value=value,
            time=clock,
            endpoint=self.endpoint,
            field_scope=self.field_scope,
            source_href=self.href,
            cadence="snapshot",
        )

    def definition(self) -> InsightDefinitionQualification:
        return InsightDefinitionQualification(
            definition_id=self.definition_id,
            module="crypto",
            public_id=self.metric_id,
            unit=self.unit,
            provider=self.provider,
            scope_id=self.scope_id,
            methodology_id=self.methodology_id,
            sample_policy=SAMPLE_POLICY,
            cadence="snapshot",
        )


CG_DOMINANCE = CryptoRecipe(
    "btc_dominance",
    "BTC 도미넌스",
    "coingecko-global-market",
    "CoinGecko",
    "global.tracked.market_cap",
    "btc-market-cap-share-v1",
    "percent",
    "https://api.coingecko.com/api/v3/global",
    "data.market_cap_percentage.btc",
    "https://www.coingecko.com/en/global-charts",
)
CG_MARKET_CAP = CryptoRecipe(
    "market_cap_usd",
    "전체 시가총액",
    "coingecko-global-market",
    "CoinGecko",
    "global.tracked.market_cap",
    "tracked-market-cap-usd-v1",
    "usd",
    CG_DOMINANCE.endpoint,
    "data.total_market_cap.usd",
    CG_DOMINANCE.href,
)
LLAMA_SUPPLY = CryptoRecipe(
    "usd_stablecoin_supply",
    "USD 연동 공급",
    "defillama-market-structure",
    "DeFiLlama",
    "named-positive.peggedUSD",
    "circulating-peggedUSD-nominal-sum-v1",
    "usd",
    "https://stablecoins.llama.fi/stablecoins",
    "peggedAssets.circulating.peggedUSD",
    "https://defillama.com/stablecoins",
)
LLAMA_TVL = CryptoRecipe(
    "chain_tvl_sum",
    "체인 TVL 합계",
    "defillama-market-structure",
    "DeFiLlama",
    "named-positive.chain-tvl",
    "chain-tvl-usd-sum-not-netflow-v1",
    "usd",
    "https://api.llama.fi/v2/chains",
    "chains.tvl",
    "https://defillama.com/chains",
)
FNG = CryptoRecipe(
    "fear_greed_index",
    "Fear & Greed 지수",
    "alternative-fng",
    "Alternative.me",
    "provider.bitcoin.index",
    "provider-index-0-100-v1",
    "index",
    "https://api.alternative.me/fng/",
    "data[0].value",
    "https://alternative.me/crypto/fear-and-greed-index/",
)


def derivative_recipe(
    metric_id: str, provider: str, *, interval_seconds: int | None = None
) -> CryptoRecipe:
    if metric_id not in {"btc_funding", "btc_oi_usd"} or provider not in {"Bybit", "OKX"}:
        raise ValueError("unsupported crypto derivative definition")
    funding = metric_id == "btc_funding"
    if funding and (interval_seconds is None or not 0 < interval_seconds <= 7 * 86400):
        raise ValueError("funding requires an explicit bounded cycle interval")
    bybit = provider == "Bybit"
    instrument = "BTCUSDT.linear.perpetual" if bybit else "BTC-USD-SWAP.inverse.perpetual"
    method = (
        f"indicative-for-cycle-{interval_seconds}s-v1"
        if funding
        else "venue-open-interest-usd-notional-v1"
    )
    endpoint = (
        "https://api.bybit.com/v5/market/tickers"
        if bybit
        else "https://www.okx.com/api/v5/public/" + ("funding-rate" if funding else "open-interest")
    )
    return CryptoRecipe(
        metric_id,
        "BTC 펀딩비" if funding else "BTC 미결제약정",
        "bybit-derivatives" if bybit else "okx-derivatives",
        provider,
        instrument,
        method,
        "fraction" if funding else "usd_notional",
        endpoint,
        ("BTCUSDT.fundingRate" if funding else "BTCUSDT.openInterestValue")
        if bybit
        else ("BTC-USD-SWAP.fundingRate" if funding else "BTC-USD-SWAP.oiUsd"),
        "https://www.bybit.com/trade/usdt/BTCUSDT"
        if bybit
        else "https://www.okx.com/trade-swap/btc-usd-swap",
        interval_seconds if funding else None,
    )


CRYPTO_RECIPES = (
    CG_DOMINANCE,
    CG_MARKET_CAP,
    LLAMA_SUPPLY,
    LLAMA_TVL,
    derivative_recipe("btc_funding", "Bybit", interval_seconds=28800),
    derivative_recipe("btc_oi_usd", "Bybit"),
    derivative_recipe("btc_funding", "OKX", interval_seconds=28800),
    derivative_recipe("btc_oi_usd", "OKX"),
    FNG,
)
CRYPTO_BY_ID = {r.metric_id: r for r in CRYPTO_RECIPES}


def recipe_for(row: SourceInsightMetric) -> CryptoRecipe | None:
    if row.metric_id not in CRYPTO_SLOTS:
        return None
    if row.metric_id not in {"btc_funding", "btc_oi_usd"}:
        return CRYPTO_BY_ID[row.metric_id]
    interval = None
    if row.metric_id == "btc_funding":
        if row.time.applicable_start is None or row.time.applicable_end is None:
            return None
        duration = (row.time.applicable_end - row.time.applicable_start).total_seconds()
        if duration != int(duration):
            return None
        interval = int(duration)
    try:
        return derivative_recipe(row.metric_id, row.provider, interval_seconds=interval)
    except ValueError:
        return None


def valid_crypto_metric(row: SourceInsightMetric) -> bool:
    if row.metric_id not in CRYPTO_SLOTS:
        return not row.definition_id.startswith("crypto.")  # u180 synthetic generic contract
    recipe = recipe_for(row)
    if recipe is None:
        return False
    try:
        expected = recipe.metric(row.value, row.time)
    except ValidationError:
        return False
    if any(
        getattr(row, k) != getattr(expected, k)
        for k in (
            "definition_id",
            "source_name",
            "provider",
            "scope_id",
            "methodology_id",
            "unit",
            "sample_policy",
            "endpoint",
            "field_scope",
            "source_href",
            "cadence",
            "calendar_policy",
        )
    ):
        return False
    clock = row.time
    if row.metric_id in {"usd_stablecoin_supply", "chain_tvl_sum"}:
        if clock.precision == "unknown":
            if clock.basis != "source_response" or clock.source_updated_at is not None:
                return False
        elif clock.basis != "collection_window" or clock.source_updated_at is not None:
            return False
    elif (
        clock.basis != "source_response"
        or clock.precision not in {"exact", "unknown"}
        or (row.provider == "CoinGecko" and clock.source_updated_at != clock.exact_at)
        or (row.provider in {"Bybit", "OKX"} and clock.source_updated_at is not None)
        or (
            row.provider == "Alternative.me"
            and clock.source_updated_at not in {None, clock.exact_at}
        )
    ):
        return False
    if row.metric_id in {"btc_dominance", "fear_greed_index"} and not 0 <= row.value <= 100:
        return False
    if row.metric_id == "fear_greed_index" and row.value != row.value.to_integral_value():
        return False
    if row.metric_id not in {"btc_funding", "btc_dominance", "fear_greed_index"} and row.value < 0:
        return False
    if row.metric_id == "btc_funding":
        return bool(
            row.time.exact_at
            and row.time.applicable_start
            and row.time.applicable_end
            and row.time.applicable_start <= row.time.exact_at < row.time.applicable_end
        )
    return row.time.applicable_start is None and row.time.applicable_end is None
