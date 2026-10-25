"""FR-028: closed event definitions and display semantics; not a source registry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from investo.models.insights import (
    EventCategory,
    EventKind,
    InsightDefinitionQualification,
    InsightEventDetails,
    InsightTime,
    SourceInsightEnvelope,
    SourceInsightEvent,
    SourceScheduleCoverage,
    canonical_bytes,
    digest,
)

KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
FED_ENDPOINT = "https://www.federalreserve.gov/json/calendar.json"
FED_HREF = "https://www.federalreserve.gov/newsevents/calendar.htm"
BEA_ENDPOINT = "https://www.bea.gov/news/schedule"
FRED_ENDPOINT = "https://api.stlouisfed.org/fred/release/dates"
FRED_HREF = "https://fred.stlouisfed.org/releases/calendar"
AUCTION_ENDPOINT = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v1/accounting/od/upcoming_auctions"
)
AUCTION_HREF = "https://fiscaldata.treasury.gov/datasets/upcoming-auctions/upcoming-auctions"
CALENDAR_SOURCES = (
    "fomc-calendar",
    "us-economic-calendar",
    "fred-economic-calendar",
    "treasury-auctions",
)


@dataclass(frozen=True, slots=True)
class EventRecipe:
    key: str
    source_name: str
    endpoint: str
    href: str
    category: EventCategory
    kind: EventKind
    family: str
    label: str

    @property
    def definition_id(self) -> str:
        return f"calendar.{self.key}.v1"

    @property
    def field_scope(self) -> str:
        return f"schedule.{self.key}"

    def definition(self) -> InsightDefinitionQualification:
        return InsightDefinitionQualification(
            definition_id=self.definition_id, module="calendar", public_id=self.definition_id
        )

    def event(
        self,
        clock: InsightTime,
        official_id: str,
        *,
        target_period: str | None = None,
        instrument: str | None = None,
        reopening: str = "unknown",
    ) -> SourceInsightEvent:
        details = InsightEventDetails.model_validate(
            dict(
                category=self.category,
                kind=self.kind,
                family=self.family,
                official_id=official_id,
                target_period=target_period,
                instrument=instrument,
                reopening=reopening,
            )
        )
        return SourceInsightEvent(
            event_id=occurrence_id(details, clock),
            definition_id=self.definition_id,
            source_name=self.source_name,
            label=self.label,
            time=clock,
            endpoint=self.endpoint,
            field_scope=self.field_scope,
            source_href=self.href,
            details=details,
        )

    def envelope(
        self, event: SourceInsightEvent, coverage: SourceScheduleCoverage
    ) -> SourceInsightEnvelope:
        return SourceInsightEnvelope(
            source_name=self.source_name, events=(event,), schedule_coverage=coverage
        )


def _fed(key: str, kind: EventKind, label: str) -> EventRecipe:
    return EventRecipe(
        key, "fomc-calendar", FED_ENDPOINT, FED_HREF, "central_bank", kind, f"fed.{kind}", label
    )


FED_RECIPES = {
    "meeting": _fed("fed.meeting", "fomc_meeting", "FOMC 회의"),
    "statement": _fed("fed.statement", "fomc_statement", "FOMC 성명 발표 일정"),
    "press_conference": _fed("fed.press_conference", "fomc_press_conference", "FOMC 기자회견"),
    "minutes": _fed("fed.minutes", "fomc_minutes", "FOMC 의사록 공개 일정"),
    "speech": _fed("fed.speech", "fed_speech", "연준 연설·대담"),
    "beige": _fed("fed.beige", "beige_book", "연준 베이지북"),
    "statistics": _fed("fed.statistics", "fed_statistics", "연준 통계 발표 일정"),
    "testimony": _fed("fed.testimony", "fed_testimony", "연준 의회 증언"),
    "holiday": _fed("fed.holiday", "fed_holiday", "연준 휴일 일정"),
}


def _economic(key: str, source: str, family: str, label: str) -> EventRecipe:
    bea = source == "us-economic-calendar"
    return EventRecipe(
        key,
        source,
        BEA_ENDPOINT if bea else FRED_ENDPOINT,
        BEA_ENDPOINT if bea else FRED_HREF,
        "economic_release",
        "economic_release",
        family,
        label,
    )


BEA_RECIPES = {
    "gdp": _economic("bea.gdp", "us-economic-calendar", "us.gdp", "미국 GDP 발표 일정"),
    "pce": _economic(
        "bea.pce",
        "us-economic-calendar",
        "us.personal_income_outlays",
        "미국 개인소득·지출 발표 일정",
    ),
    "trade": _economic(
        "bea.trade", "us-economic-calendar", "us.trade", "미국 상품·서비스 무역 발표 일정"
    ),
    "other": _economic("bea.other", "us-economic-calendar", "bea.other", "BEA 경제통계 발표 일정"),
}
FRED_RELEASES = {
    "10": ("us.cpi", "미국 소비자물가 발표 일정"),
    "46": ("us.ppi", "미국 생산자물가 발표 일정"),
    "50": ("us.employment", "미국 고용보고서 발표 일정"),
    "53": ("us.gdp", "미국 GDP 발표 일정"),
    "54": ("us.personal_income_outlays", "미국 개인소득·지출 발표 일정"),
    "13": ("us.industrial_production", "미국 산업생산 발표 일정"),
    "9": ("us.retail_sales", "미국 소매판매 발표 일정"),
    "192": ("us.jolts", "미국 구인·이직 발표 일정"),
    "27": ("us.housing_starts", "미국 주택착공 발표 일정"),
    "291": ("us.existing_home_sales", "미국 기존주택판매 발표 일정"),
}
FRED_RECIPES = {
    rid: _economic(f"fred.{rid}", "fred-economic-calendar", family, label)
    for rid, (family, label) in FRED_RELEASES.items()
}
AUCTION_RECIPE = EventRecipe(
    "treasury.auction",
    "treasury-auctions",
    AUCTION_ENDPOINT,
    AUCTION_HREF,
    "treasury_auction",
    "treasury_auction",
    "treasury.auction",
    "미 국채 입찰 일정",
)
EVENT_RECIPES = (
    *FED_RECIPES.values(),
    *BEA_RECIPES.values(),
    *FRED_RECIPES.values(),
    AUCTION_RECIPE,
)
EVENT_BY_DEFINITION = {r.definition_id: r for r in EVENT_RECIPES}


def occurrence_id(details: InsightEventDetails, clock: InsightTime) -> str:
    """Source occurrence key; no title similarity or briefing macro_event_key."""
    start, end = local_dates(clock)
    identity: dict[str, object] = dict(
        kind=details.kind,
        official_id=details.official_id,
        start=str(start),
        end=str(end),
        period=details.target_period,
        reopening=details.reopening,
    )
    return "event:" + digest(canonical_bytes(identity))


def local_dates(clock: InsightTime) -> tuple[date | None, date | None]:
    if clock.precision == "exact" and clock.exact_at is not None and clock.source_timezone:
        day = clock.exact_at.astimezone(ZoneInfo(clock.source_timezone)).date()
        return day, day
    return clock.local_date or clock.start_date, clock.local_date or clock.end_date


def valid_event(row: SourceInsightEvent) -> bool:
    recipe = EVENT_BY_DEFINITION.get(row.definition_id)
    if recipe is None:
        # u180's generic validated contract remains usable by synthetic resource fixtures.
        return row.details is None and not row.definition_id.startswith("calendar.")
    details = row.details
    start, end = local_dates(row.time)
    return bool(
        details is not None
        and start is not None
        and end is not None
        and timedelta(0) <= end - start <= timedelta(days=7)
        and row.time.basis == "schedule"
        and row.time.precision in {"date", "exact"}
        and row.time.source_timezone == "America/New_York"
        and row.source_name == recipe.source_name
        and row.endpoint == recipe.endpoint
        and row.field_scope == recipe.field_scope
        and row.source_href == recipe.href
        and row.label == recipe.label
        and details.category == recipe.category
        and details.kind == recipe.kind
        and details.family == recipe.family
        and row.event_id == occurrence_id(details, row.time)
        and (recipe.source_name != "fred-economic-calendar" or details.target_period is None)
        and (
            recipe.source_name != "fred-economic-calendar"
            or details.official_id == "fred:" + recipe.key.split(".")[-1]
        )
        and (recipe.source_name == "us-economic-calendar" or details.target_period is None)
        and (
            recipe.category == "treasury_auction"
            or (details.instrument is None and details.reopening == "unknown")
        )
    )


def display_dates(row: SourceInsightEvent) -> tuple[date | None, date | None]:
    if row.time.precision == "exact" and row.time.exact_at is not None:
        day = row.time.exact_at.astimezone(KST).date()
        return day, day
    return local_dates(row.time)


def in_range(row: SourceInsightEvent, today: date, days: int) -> bool:
    start, end = display_dates(row)
    return bool(start and end and end >= today and start < today + timedelta(days=days))


def range_anchor(row: SourceInsightEvent, now: datetime) -> date:
    """Exact instants use KST; date-only windows use their declared local calendar."""
    zone = (
        KST
        if row.time.precision == "exact"
        else ZoneInfo(row.time.source_timezone or "America/New_York")
    )
    return now.astimezone(zone).date()
