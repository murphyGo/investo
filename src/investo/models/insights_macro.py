"""FR-027 closed presentation recipes, not an adapter registry or fetch service."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import cast

from investo.models.insights import (
    Cadence,
    CalendarPolicy,
    InsightDefinitionQualification,
    InsightTime,
    InsightUnit,
    SourceInsightMetric,
)

TREASURY_ENDPOINT = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
)
TREASURY_HREF = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"
NYFED_ENDPOINT = "https://markets.newyorkfed.org/api/rates"
NYFED_HREF = "https://www.newyorkfed.org/markets/reference-rates"
BLS_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data"
BLS_HREF = "https://www.bls.gov/data/"
FRED_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"
FRED_HREF = "https://fred.stlouisfed.org/series/DEXKOUS"


@dataclass(frozen=True, slots=True)
class MacroRecipe:
    metric_id: str
    label: str
    source_name: str
    provider: str
    field_scope: str
    unit: InsightUnit
    cadence: Cadence
    calendar_policy: CalendarPolicy
    endpoint: str
    href: str
    methodology: str

    def metric(self, value: str | Decimal | int, clock: InsightTime) -> SourceInsightMetric:
        return SourceInsightMetric(
            module="macro",
            metric_id=self.metric_id,
            definition_id=self.metric_id + ".v1",
            source_name=self.source_name,
            provider=self.provider,
            scope_id=self.field_scope,
            methodology_id=self.methodology,
            sample_policy="source-period-revisions" if self.cadence == "monthly" else "source-day",
            unit=self.unit,
            label=self.label,
            value=value,
            time=clock,
            endpoint=self.endpoint,
            field_scope=self.field_scope,
            source_href=self.href,
            cadence=self.cadence,
            calendar_policy=self.calendar_policy,
        )

    def definition(self) -> InsightDefinitionQualification:
        return InsightDefinitionQualification(
            definition_id=self.metric_id + ".v1",
            module="macro",
            public_id=self.metric_id,
            unit=self.unit,
            provider=self.provider,
            scope_id=self.field_scope,
            methodology_id=self.methodology,
            sample_policy="source-period-revisions" if self.cadence == "monthly" else "source-day",
            cadence=self.cadence,
            calendar_policy=self.calendar_policy,
        )


MACRO_RECIPES = (
    *(
        MacroRecipe(
            mid,
            label,
            "treasury-rates",
            "US Treasury",
            field,
            "percent",
            "daily",
            "treasury",
            TREASURY_ENDPOINT,
            TREASURY_HREF,
            "daily-par-yield-v1",
        )
        for mid, label, field in (
            ("ust_3m", "미 국채 3개월", "BC_3MONTH"),
            ("ust_2y", "미 국채 2년", "BC_2YEAR"),
            ("ust_10y", "미 국채 10년", "BC_10YEAR"),
            ("ust_30y", "미 국채 30년", "BC_30YEAR"),
        )
    ),
    *(
        MacroRecipe(
            mid,
            label,
            "treasury-rates",
            "US Treasury",
            field,
            "basis_point",
            "daily",
            "treasury",
            TREASURY_ENDPOINT,
            TREASURY_HREF,
            "same-day-percent-difference-times-100-v1",
        )
        for mid, label, field in (
            ("ust_10y_2y_bp", "10년 - 2년", "BC_10YEAR-BC_2YEAR"),
            ("ust_10y_3m_bp", "10년 - 3개월", "BC_10YEAR-BC_3MONTH"),
        )
    ),
    *(
        MacroRecipe(
            mid,
            label,
            "nyfed-reference-rates",
            "Federal Reserve Bank of New York",
            field,
            "percent",
            "daily",
            cast("CalendarPolicy", policy),
            NYFED_ENDPOINT + suffix,
            NYFED_HREF,
            "official-effective-date-v1",
        )
        for mid, label, field, policy, suffix in (
            ("sofr", "SOFR", "SOFR", "sofr", "/secured/sofr/last/1.json"),
            ("effr", "EFFR", "EFFR", "effr", "/unsecured/effr/last/1.json"),
        )
    ),
    MacroRecipe(
        "sofr_effr_bp",
        "SOFR - EFFR",
        "nyfed-reference-rates",
        "Federal Reserve Bank of New York",
        "SOFR-EFFR",
        "basis_point",
        "daily",
        "sofr",
        NYFED_ENDPOINT,
        NYFED_HREF,
        "same-effective-day-percent-difference-times-100-v1",
    ),
    MacroRecipe(
        "usd_krw_h10",
        "원/달러 H.10",
        "fred-fx-close",
        "Federal Reserve Board via FRED",
        "DEXKOUS",
        "krw_per_usd",
        "daily",
        "h10",
        FRED_ENDPOINT,
        FRED_HREF,
        "h10-noon-buying-rate-not-exchange-close-v1",
    ),
    *(
        MacroRecipe(
            mid,
            label,
            "bls-macro-actuals",
            "US Bureau of Labor Statistics",
            series,
            cast("InsightUnit", unit),
            "monthly",
            "federal",
            BLS_ENDPOINT + "/" + series,
            BLS_HREF,
            method,
        )
        for mid, label, series, unit, method in (
            (
                "cpi_sa_index",
                "소비자물가 CPI",
                "CUSR0000SA0",
                "index",
                "SA-1982-84=100-revisable-v1",
            ),
            (
                "core_cpi_sa_index",
                "근원 소비자물가 CPI",
                "CUSR0000SA0L1E",
                "index",
                "SA-1982-84=100-revisable-v1",
            ),
            (
                "unemployment_rate",
                "실업률",
                "LNS14000000",
                "percent",
                "SA-civilian-16plus-revisable-v1",
            ),
        )
    ),
)
MACRO_BY_ID = {recipe.metric_id: recipe for recipe in MACRO_RECIPES}
SPREAD_RECIPES = (
    ("ust_10y_2y_bp", "ust_10y", "ust_2y"),
    ("ust_10y_3m_bp", "ust_10y", "ust_3m"),
    ("sofr_effr_bp", "sofr", "effr"),
)


def difference_exact(left: Decimal, right: Decimal, *, scale: int = 1) -> Decimal:
    """Preserve every supported 64-character input digit, including exponent gaps."""
    with localcontext() as context:
        context.prec = 256
        return (left - right) * scale


def valid_macro_metric(row: SourceInsightMetric) -> bool:
    recipe = MACRO_BY_ID.get(row.metric_id)
    if recipe is None:
        return True  # Foundation accepts other reviewed definitions; this view has 13 slots.
    expected = recipe.metric(row.value, row.time)
    if any(
        getattr(row, k) != getattr(expected, k)
        for k in (
            "definition_id",
            "source_name",
            "provider",
            "scope_id",
            "methodology_id",
            "sample_policy",
            "unit",
            "endpoint",
            "field_scope",
            "source_href",
            "cadence",
            "calendar_policy",
        )
    ):
        return False
    if row.metric_id in {"cpi_sa_index", "core_cpi_sa_index", "usd_krw_h10"} and row.value <= 0:
        return False
    return row.metric_id != "unemployment_rate" or 0 <= row.value <= 100
