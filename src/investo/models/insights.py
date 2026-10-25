"""FR-026: private observations and immutable, bounded public insight contracts."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Literal, Self, cast
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    TypeAdapter,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.dataclasses import dataclass

from investo.models._validators import ensure_tz_aware
from investo.models.publication import PublishReceipt

ModuleId = Literal["macro", "calendar", "crypto"]
InsightUnit = Literal[
    "percent",
    "percentage_point",
    "basis_point",
    "usd",
    "krw_per_usd",
    "index",
    "contracts",
    "usd_notional",
    "fraction",
    "count",
]
Freshness = Literal["fresh", "delayed", "stale", "unknown"]
Attempt = Literal["ok", "zero", "failed", "skipped"]
Reason = Literal[
    "missing_input",
    "invalid_value",
    "definition_conflict",
    "time_unknown",
    "stale",
    "source_failed",
    "source_zero",
    "source_skipped",
    "rights_unverified",
    "rights_revoked",
    "history_insufficient",
    "history_incompatible",
    "publication_unconfirmed",
]
Cadence = Literal["daily", "monthly", "snapshot", "schedule"]
CalendarPolicy = Literal["treasury", "sofr", "effr", "h10", "federal", "none"]
MAX_CURRENT_BYTES = 256 * 1024
MAX_HISTORY_BYTES = 4 * 1024 * 1024
MAX_INPUT_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 12 * 1024 * 1024
MANIFEST_PATH = "site_docs/insights/_data/manifest.json"


def canonical_bytes(
    value: BaseModel | InsightHistoryRow | InsightHistoryTime | dict[str, object],
) -> bytes:
    if isinstance(value, InsightHistory):
        # Stream bounded rows: avoid a second whole-history dict/string graph.
        stream = BytesIO()
        stream.write(b'{"definitions":[')
        for index, definition in enumerate(value.definitions):
            if index:
                stream.write(b",")
            stream.write(canonical_bytes(definition))
        stream.write(b'],"module":')
        stream.write(json.dumps(value.module).encode("utf-8"))
        stream.write(b',"rows":[')
        for index, row in enumerate(value.rows):
            if index:
                stream.write(b",")
            stream.write(canonical_bytes(row))
        stream.write(b'],"schema_version":1}')
        return stream.getvalue()
    payload = (
        value.model_dump(mode="json")
        if isinstance(value, (BaseModel, InsightHistoryRow, InsightHistoryTime))
        else value
    )
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def public_href(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
        or any(ord(c) < 33 for c in value)
        or "\\" in value
    ):
        raise ValueError("public href requires a reviewed HTTPS URL without credentials or query")
    if len(value) > 1000:
        raise ValueError("public href too long")
    return value


class InsightModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InsightTime(InsightModel):
    basis: Literal["effective_date", "period", "source_response", "collection_window", "schedule"]
    precision: Literal["exact", "date", "month", "quarter", "unknown"]
    local_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    period: str | None = None
    source_timezone: str | None = None
    exact_at: datetime | None = None
    source_updated_at: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    applicable_start: datetime | None = None
    applicable_end: datetime | None = None

    @model_serializer(mode="wrap")
    def serialize_clock(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data = cast("dict[str, object]", handler(self))
        for name in ("applicable_start", "applicable_end"):
            if getattr(self, name) is None:
                data.pop(name, None)
        return data

    @field_validator(
        "exact_at",
        "source_updated_at",
        "window_start",
        "window_end",
        "applicable_start",
        "applicable_end",
    )
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return ensure_tz_aware(value) if value is not None else None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.applicable_start is not None or self.applicable_end is not None) and (
            self.applicable_start is None
            or self.applicable_end is None
            or self.basis != "source_response"
            or self.precision != "exact"
            or not timedelta(0) < self.applicable_end - self.applicable_start <= timedelta(days=7)
        ):
            raise ValueError("invalid applicable cycle interval")
        if self.source_timezone is not None:
            try:
                ZoneInfo(self.source_timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("unknown source timezone") from exc
        if (
            self.precision == "exact"
            and self.basis != "collection_window"
            and self.exact_at is None
        ):
            raise ValueError("exact precision requires exact_at")
        if self.precision != "exact" and self.exact_at is not None:
            raise ValueError("exact_at conflicts with precision")
        if self.precision == "date":
            if not self.source_timezone or (self.local_date is None and self.start_date is None):
                raise ValueError("date precision requires local date/range and IANA timezone")
            if self.local_date is not None and (self.start_date or self.end_date):
                raise ValueError("date and range are exclusive")
            if self.start_date is not None and (
                self.end_date is None or self.end_date < self.start_date
            ):
                raise ValueError("invalid date range")
        elif (
            self.local_date is not None or self.start_date is not None or self.end_date is not None
        ):
            raise ValueError("dates conflict with precision")
        if self.precision in {"month", "quarter"}:
            pattern = r"\d{4}-(0[1-9]|1[0-2])" if self.precision == "month" else r"\d{4}-Q[1-4]"
            if self.basis != "period" or not self.period or not re.fullmatch(pattern, self.period):
                raise ValueError("invalid period")
        elif self.period is not None:
            raise ValueError("period conflicts with precision")
        if self.basis == "collection_window":
            if (
                self.precision != "exact"
                or self.window_start is None
                or self.window_end is None
                or self.window_end <= self.window_start
                or self.exact_at is not None
            ):
                raise ValueError("collection window requires honest start/end interval")
        elif self.window_start is not None or self.window_end is not None:
            raise ValueError("window conflicts with basis")
        if self.basis == "effective_date" and self.precision not in {"date", "unknown"}:
            raise ValueError("effective date requires date precision")
        if self.basis == "source_response" and self.precision not in {"exact", "unknown"}:
            raise ValueError("source response requires exact precision")
        return self


class InsightIdentity(InsightModel):
    module: ModuleId
    metric_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,95}$")
    definition_id: str = Field(min_length=1, max_length=128)
    source_name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    scope_id: str = Field(min_length=1, max_length=128)
    methodology_id: str = Field(min_length=1, max_length=128)
    sample_policy: str = Field(min_length=1, max_length=100)
    unit: InsightUnit

    def comparison_key(self) -> str:
        return digest(
            canonical_bytes(
                {
                    name: getattr(self, name)
                    for name in (
                        "metric_id",
                        "definition_id",
                        "provider",
                        "scope_id",
                        "methodology_id",
                        "unit",
                        "sample_policy",
                    )
                }
            )
        )


class SourceInsightMetric(InsightIdentity):
    label: str = Field(min_length=1, max_length=160)
    value: Decimal
    time: InsightTime
    endpoint: str = Field(min_length=1, max_length=1000)
    field_scope: str = Field(min_length=1, max_length=128)
    source_href: str
    cadence: Cadence
    calendar_policy: CalendarPolicy = "none"
    next_release_at: datetime | None = None

    @field_validator("value", mode="before")
    @classmethod
    def finite_decimal(cls, value: object) -> Decimal:
        if (
            isinstance(value, bool)
            or not isinstance(value, (str, Decimal, int))
            or len(str(value)) > 64
        ):
            raise ValueError("value requires a bounded decimal string, Decimal or integer")
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid decimal") from exc
        if not result.is_finite() or len(str(result)) > 64 or abs(result.adjusted()) > 64:
            raise ValueError("non-finite or oversized decimal")
        return result

    @field_validator("next_release_at")
    @classmethod
    def release_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_tz_aware(value) if value is not None else None


EventCategory = Literal["economic_release", "central_bank", "treasury_auction"]
EventKind = Literal[
    "economic_release",
    "fomc_meeting",
    "fomc_statement",
    "fomc_press_conference",
    "fomc_minutes",
    "fed_speech",
    "beige_book",
    "fed_statistics",
    "fed_testimony",
    "fed_holiday",
    "treasury_auction",
]


class InsightEventDetails(InsightModel):
    """u182: source-owned occurrence semantics, separate from briefing macro keys."""

    category: EventCategory
    kind: EventKind
    official_id: str = Field(min_length=1, max_length=128)
    family: str = Field(min_length=1, max_length=80)
    target_period: str | None = Field(default=None, pattern=r"^\d{4}-(?:0[1-9]|1[0-2]|Q[1-4])$")
    instrument: str | None = Field(default=None, max_length=64)
    reopening: Literal["yes", "no", "unknown"] = "unknown"


class SourceScheduleCoverage(InsightModel):
    """Evidence for the adapter's existing query, never a whole-market calendar."""

    start_date: date
    end_date: date
    upstream_cap: int | None = Field(default=None, ge=1, le=10000)
    cap_reached: bool = False

    @model_validator(mode="after")
    def range_valid(self) -> Self:
        if not 0 <= (self.end_date - self.start_date).days <= 180:
            raise ValueError("invalid schedule coverage range")
        return self


class SourceInsightEvent(InsightModel):
    module: Literal["calendar"] = "calendar"
    event_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
    definition_id: str = Field(min_length=1, max_length=128)
    source_name: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=160)
    time: InsightTime
    endpoint: str = Field(min_length=1, max_length=1000)
    field_scope: str = Field(min_length=1, max_length=128)
    source_href: str
    details: InsightEventDetails | None = None

    @model_serializer(mode="wrap")
    def serialize_event(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data = cast("dict[str, object]", handler(self))
        if self.details is None:
            data.pop("details", None)
        if not data.get("references"):
            data.pop("references", None)
        return data


class SourceInsightEnvelope(InsightModel):
    schema_version: Literal[1] = 1
    source_name: str = Field(min_length=1, max_length=100)
    origin_adapter_name: str | None = Field(default=None, max_length=100)
    metrics: tuple[SourceInsightMetric, ...] = Field(default=(), max_length=16)
    events: tuple[SourceInsightEvent, ...] = Field(default=(), max_length=128)
    schedule_coverage: SourceScheduleCoverage | None = None

    @model_serializer(mode="wrap")
    def serialize_envelope(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data = cast("dict[str, object]", handler(self))
        if self.schedule_coverage is None:
            data.pop("schedule_coverage", None)
        return data

    @model_validator(mode="after")
    def same_owner(self) -> Self:
        if any(row.source_name != self.source_name for row in self.metrics) or any(
            row.source_name != self.source_name for row in self.events
        ):
            raise ValueError("envelope producer mismatch")
        return self


class InsightDefinitionQualification(InsightModel):
    definition_id: str = Field(min_length=1, max_length=128)
    module: ModuleId
    public_id: str = Field(min_length=1, max_length=128)
    unit: InsightUnit | None = None
    provider: str | None = Field(default=None, max_length=100)
    scope_id: str | None = Field(default=None, max_length=128)
    methodology_id: str | None = Field(default=None, max_length=128)
    sample_policy: str | None = Field(default=None, max_length=100)
    cadence: Cadence = "schedule"
    calendar_policy: CalendarPolicy = "none"

    @model_validator(mode="after")
    def metric_identity(self) -> Self:
        numeric = self.module != "calendar"
        identity = (
            self.unit,
            self.provider,
            self.scope_id,
            self.methodology_id,
            self.sample_policy,
        )
        if numeric and (not all(identity) or self.cadence == "schedule"):
            raise ValueError("qualified metric requires complete semantic identity")
        if not numeric and (any(identity) or self.public_id != self.definition_id):
            raise ValueError("calendar definition cannot claim numeric semantics")
        return self


class InsightSourceQualification(InsightModel):
    source_name: str = Field(min_length=1, max_length=100)
    endpoint: str
    field_scope: str
    definition_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    definitions: tuple[InsightDefinitionQualification, ...] = Field(default=(), max_length=32)
    display_allowed: StrictBool = False
    public_git_history_allowed: StrictBool = False
    retention_allowed: StrictBool = False
    revoked: StrictBool = False
    evidence_hrefs: tuple[str, ...] = Field(default=(), max_length=16)
    checked_on: date | None = None
    attribution: str = Field(default="", max_length=1000)
    required_env_names: tuple[str, ...] = Field(default=(), max_length=16)
    runtime_probe_state: Literal["unverified", "ok", "failed"] = "unverified"
    allowed_hrefs: tuple[str, ...] = Field(default=(), max_length=32)

    @field_validator("allowed_hrefs", "evidence_hrefs")
    @classmethod
    def safe_links(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(public_href(href) for href in value)

    @model_validator(mode="after")
    def evidenced_rights(self) -> Self:
        if (self.display_allowed or self.public_git_history_allowed or self.retention_allowed) and (
            not self.evidence_hrefs
            or self.checked_on is None
            or not self.attribution
            or not self.allowed_hrefs
        ):
            raise ValueError("allowed rights require precise evidence and attribution")
        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", name) for name in self.required_env_names):
            raise ValueError("invalid environment variable name")
        return self


class ValidatedInsightMetric(SourceInsightMetric):
    origin_adapter_name: str
    availability: Literal["available", "limited"] = "available"
    freshness: Freshness
    latest_attempt: Attempt
    reasons: tuple[Reason, ...] = ()
    attribution: str = Field(max_length=1000)
    last_good: bool = False

    @field_validator("source_href", "endpoint")
    @classmethod
    def safe_href(cls, value: str) -> str:
        return public_href(value)


class InsightEventReference(InsightModel):
    event: SourceInsightEvent
    origin_adapter_name: str
    collection_completed_at: datetime
    latest_attempt: Attempt
    last_good: bool = False
    attribution: str = Field(max_length=1000)

    @model_validator(mode="after")
    def safe_reference(self) -> Self:
        public_href(self.event.source_href)
        public_href(self.event.endpoint)
        ensure_tz_aware(self.collection_completed_at)
        return self


class ValidatedInsightEvent(SourceInsightEvent):
    collection_completed_at: datetime

    @field_validator("collection_completed_at")
    @classmethod
    def collected_aware(cls, value: datetime) -> datetime:
        return ensure_tz_aware(value)

    origin_adapter_name: str
    freshness: Freshness
    latest_attempt: Attempt
    attribution: str = Field(max_length=1000)
    last_good: bool = False
    references: tuple[InsightEventReference, ...] = Field(default=(), max_length=3)

    @field_validator("source_href", "endpoint")
    @classmethod
    def safe_href(cls, value: str) -> str:
        return public_href(value)


class CalendarSourceStatus(InsightModel):
    source_name: str
    latest_attempt: Literal["ok", "zero", "failed", "skipped", "missing"]
    rights: Literal["allowed", "blocked", "mixed", "unverified"]
    query: SourceScheduleCoverage | None = None


class CalendarModuleCoverage(InsightModel):
    sources: tuple[CalendarSourceStatus, ...] = Field(max_length=4)
    selected_count: int = Field(ge=0, le=128)
    excluded_count: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)
    invalid_count: int = Field(default=0, ge=0)


class CryptoSlotStatus(InsightModel):
    metric_id: str
    availability: Literal["available", "limited", "unavailable"]
    selected_source: str | None = None
    reasons: tuple[Reason, ...] = ()


class CryptoSourceStatus(InsightModel):
    source_name: str
    latest_attempt: Literal["ok", "zero", "failed", "skipped", "missing"]
    rights: Literal["allowed", "blocked", "mixed", "unverified"]


class CryptoModuleCoverage(InsightModel):
    slots: tuple[CryptoSlotStatus, ...] = Field(max_length=7)
    sources: tuple[CryptoSourceStatus, ...] = Field(max_length=5)


class ValidatedInsightModule(InsightModel):
    schema_version: Literal[1] = 1
    module: ModuleId
    snapshot_id: str = ""
    run_started_at: datetime
    collection_completed_at: datetime
    evaluated_at: datetime
    availability: Literal["available", "limited", "unavailable"]
    reasons: tuple[Reason, ...] = ()
    metrics: tuple[ValidatedInsightMetric, ...] = Field(default=(), max_length=32)
    events: tuple[ValidatedInsightEvent, ...] = Field(default=(), max_length=128)
    calendar_coverage: CalendarModuleCoverage | None = None
    crypto_coverage: CryptoModuleCoverage | None = None

    @model_serializer(mode="wrap")
    def serialize_module(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        # Preserve existing schema-v1 numeric snapshots and their hashes.
        data = cast("dict[str, object]", handler(self))
        if self.calendar_coverage is None:
            data.pop("calendar_coverage", None)
        if self.crypto_coverage is None:
            data.pop("crypto_coverage", None)
        return data

    @field_validator("run_started_at", "collection_completed_at", "evaluated_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return ensure_tz_aware(value)

    @model_validator(mode="after")
    def identity(self) -> Self:
        if (
            self.collection_completed_at < self.run_started_at
            or self.evaluated_at < self.collection_completed_at
        ):
            raise ValueError("invalid operational clocks")
        if any(row.module != self.module for row in self.metrics) or any(
            row.module != self.module for row in self.events
        ):
            raise ValueError("module mismatch")
        if (self.module == "calendar" and self.metrics) or (
            self.module != "calendar" and self.events
        ):
            raise ValueError("module payload kind mismatch")
        if self.calendar_coverage is not None and (
            self.module != "calendar" or self.calendar_coverage.selected_count != len(self.events)
        ):
            raise ValueError("calendar coverage mismatch")
        if self.crypto_coverage is not None and self.module != "crypto":
            raise ValueError("crypto coverage mismatch")
        if len({m.metric_id for m in self.metrics}) != len(self.metrics) or len(
            {e.event_id for e in self.events}
        ) != len(self.events):
            raise ValueError("duplicate public identity")
        if self.availability == "unavailable" and (self.metrics or self.events):
            raise ValueError("unavailable module cannot contain public values")
        if self.availability != "unavailable" and not (self.metrics or self.events):
            raise ValueError("available module requires public values")
        expected = self.computed_id()
        if self.snapshot_id and self.snapshot_id != expected:
            raise ValueError("snapshot identity mismatch")
        object.__setattr__(self, "snapshot_id", expected)
        if len(canonical_bytes(self)) > MAX_CURRENT_BYTES:
            raise ValueError("current payload cap exceeded")
        return self

    def computed_id(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("snapshot_id")
        return digest(canonical_bytes(payload))


class HistoryDefinition(InsightModel):
    key: str
    metric: SourceInsightMetric
    attribution: str = Field(max_length=1000)


@dataclass(frozen=True, slots=True, config=ConfigDict(extra="forbid"))
class InsightHistoryTime:
    """Compact immutable history clock; reuse the source clock validator."""

    basis: Literal["effective_date", "period", "source_response", "collection_window", "schedule"]
    precision: Literal["exact", "date", "month", "quarter", "unknown"]
    local_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    period: str | None = None
    source_timezone: str | None = None
    exact_at: datetime | None = None
    source_updated_at: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    applicable_start: datetime | None = None
    applicable_end: datetime | None = None

    @model_serializer(mode="wrap")
    def serialize_clock(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data = cast("dict[str, object]", handler(self))
        for name in ("applicable_start", "applicable_end"):
            if getattr(self, name) is None:
                data.pop(name, None)
        return data

    @model_validator(mode="after")
    def validate_source_clock(self) -> Self:
        InsightTime.model_validate(self.model_dump())
        return self

    @classmethod
    def from_source(cls, value: InsightTime) -> InsightHistoryTime:
        return _HISTORY_TIME_ADAPTER.validate_python(value.model_dump())

    def model_dump(self, *, mode: Literal["json", "python"] = "python") -> dict[str, object]:
        return cast("dict[str, object]", _HISTORY_TIME_ADAPTER.dump_python(self, mode=mode))


_HISTORY_TIME_ADAPTER = TypeAdapter(InsightHistoryTime)


@dataclass(frozen=True, slots=True, config=ConfigDict(extra="forbid"))
class InsightHistoryRow:
    """Slots avoid retaining two BaseModel dictionaries/field sets per sample."""

    definition_key: str
    observation_key: str
    value: Decimal
    time: InsightHistoryTime
    record_hash: str
    revised_from: str | None = None
    superseded_from: str | None = None

    @model_serializer(mode="wrap")
    def serialize_row(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        data = cast("dict[str, object]", handler(self))
        if self.superseded_from is None:
            data.pop("superseded_from", None)
        return data

    @field_validator("value", mode="before")
    @classmethod
    def finite_decimal(cls, value: object) -> Decimal:
        return SourceInsightMetric.finite_decimal(value)

    @field_validator("time", mode="before")
    @classmethod
    def source_clock(cls, value: object) -> object:
        return value.model_dump() if isinstance(value, InsightTime) else value

    def model_dump(self, *, mode: Literal["json", "python"] = "python") -> dict[str, object]:
        return cast("dict[str, object]", _HISTORY_ROW_ADAPTER.dump_python(self, mode=mode))

    @classmethod
    def model_validate(cls, value: object) -> InsightHistoryRow:
        return _HISTORY_ROW_ADAPTER.validate_python(value)


_HISTORY_ROW_ADAPTER = TypeAdapter(InsightHistoryRow)


class InsightHistory(InsightModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    schema_version: Literal[1] = 1
    module: Literal["macro", "crypto"]
    definitions: tuple[HistoryDefinition, ...] = ()
    rows: tuple[InsightHistoryRow, ...] = Field(default=(), max_length=32 * 366)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if any(
            d.key != d.metric.comparison_key() or d.metric.module != self.module
            for d in self.definitions
        ):
            raise ValueError("history definition identity mismatch")
        for definition in self.definitions:
            limit = 24 if definition.metric.cadence == "monthly" else 366
            if sum(row.definition_key == definition.key for row in self.rows) > limit:
                raise ValueError("history observation retention cap exceeded")
        for definition in self.definitions:
            SourceInsightMetric.model_validate_json(canonical_bytes(definition.metric))
        for row in self.rows:
            SourceInsightMetric.finite_decimal(row.value)
            InsightTime.model_validate_json(canonical_bytes(row.time))
        keys = {d.key for d in self.definitions}
        if (
            len(keys) != len(self.definitions)
            or len(keys) > 32
            or any(r.definition_key not in keys for r in self.rows)
        ):
            raise ValueError("invalid history definition references")
        if len({(r.definition_key, r.observation_key) for r in self.rows}) != len(self.rows):
            raise ValueError("duplicate history observation")
        if any(
            not r.value.is_finite()
            or digest(
                canonical_bytes({"value": str(r.value), "time": r.time.model_dump(mode="json")})
            )
            != r.record_hash
            for r in self.rows
        ):
            raise ValueError("invalid history row")
        if len(canonical_bytes(self)) > MAX_HISTORY_BYTES:
            raise ValueError("history payload cap exceeded")
        return self


class ManifestEntry(InsightModel):
    module: ModuleId
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    current_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    index_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    history_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class PublicInsightsManifest(InsightModel):
    schema_version: Literal[1] = 1
    modules: tuple[ManifestEntry, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({row.module for row in self.modules}) != len(self.modules):
            raise ValueError("duplicate manifest module")
        return self


class InsightRunOutcome(InsightModel):
    mode: Literal["shadow", "active"]
    modules: tuple[ModuleId, ...]
    status: Literal["shadow", "skipped", "remote_confirmed", "failed", "outcome_unknown"]
    projected_modules: tuple[ValidatedInsightModule, ...] = Field(
        default=(), repr=False, exclude=True
    )
    receipt: PublishReceipt | None = None

    @model_validator(mode="after")
    def confirmed(self) -> Self:
        if self.status == "remote_confirmed" and (
            self.mode != "active"
            or self.receipt is None
            or self.receipt.status != "remote_confirmed"
        ):
            raise ValueError("success requires remote confirmation")
        return self


def read_insight_history(data: bytes) -> InsightHistory:
    """Read canonical history one row at a time, avoiding a duplicate JSON tree.

    Retain only typed rows. Caps and exact re-encoding reject noncanonical or
    malformed remote data, including duplicate keys and unexpected suffixes.
    """
    if len(data) > MAX_HISTORY_BYTES:
        raise ValueError("history payload cap exceeded")
    marker = b',"rows":['
    offset = data.find(marker)
    if offset < 0 or not data.endswith(b'],"schema_version":1}'):
        raise ValueError("history is not canonical")
    header = data[:offset] + b',"rows":[],"schema_version":1}'
    empty = InsightHistory.model_validate_json(header)
    # Numeric rows contain only decimal/hash/date/IANA-clock tokens (ASCII).
    # Keep Unicode attribution in the small header, without widening all rows.
    content = data[offset + len(marker) :].decode("ascii")
    position = 0

    def intern_keys(value: dict[str, object]) -> dict[str, object]:
        return {sys.intern(key): item for key, item in value.items()}

    decoder = json.JSONDecoder(object_hook=intern_keys)
    definition_keys = {definition.key: definition.key for definition in empty.definitions}
    observation_keys: dict[str, str] = {}
    rows: list[InsightHistoryRow] = []
    while position < len(content) and content[position] != "]":
        try:
            raw, position = decoder.raw_decode(content, position)
        except RecursionError as exc:
            raise ValueError("history JSON nesting rejected") from exc
        if isinstance(raw, dict):
            key = raw.get("definition_key")
            if isinstance(key, str) and key in definition_keys:
                raw["definition_key"] = definition_keys[key]
            observed = raw.get("observation_key")
            if isinstance(observed, str) and len(observed) <= 16:
                raw["observation_key"] = observation_keys.setdefault(observed, observed)
        if position >= len(content):
            raise ValueError("history JSON truncated")
        rows.append(InsightHistoryRow.model_validate(raw))
        if len(rows) > 32 * 366:
            raise ValueError("history row cap exceeded")
        if content[position] == ",":
            position += 1
        elif content[position] != "]":
            raise ValueError("invalid history separator")
    result = InsightHistory(module=empty.module, definitions=empty.definitions, rows=tuple(rows))
    if canonical_bytes(result) != data:
        raise ValueError("history is not canonical")
    return result
