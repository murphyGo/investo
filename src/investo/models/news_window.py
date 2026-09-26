"""Immutable observation intervals, hash-only cursors and consumption witnesses."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from investo.models.events import Digest, EventModel
from investo.models.items import NormalizedItem
from investo.models.segments import MarketSegment

NewsWindowMode = Literal["off", "shadow", "active"]
NewsWindowKey = tuple[str, MarketSegment]
NEWS_WINDOW_ACTIVE_READY = False
MAX_NEWS_SOURCES = 128
MAX_NEWS_WINDOWS = MAX_NEWS_SOURCES * 3
MAX_NEWS_REVISIONS = 5000
_SEGMENTS = frozenset({"domestic-equity", "us-equity", "crypto"})
SourceName = Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9_-]{1,80}$")]


def utc_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("news window timestamp must be timezone-aware")
    return value.astimezone(UTC)


def validate_news_source(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value) is None:
        raise ValueError("invalid news source name")


def _validate_run(value: str) -> None:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value) is None
    ):
        raise ValueError("invalid news run id")


def _validate_sha(value: str | None) -> None:
    if value is not None and (
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is None
    ):
        raise ValueError("news baseline must be a fixed commit id")


@dataclass(frozen=True, slots=True)
class NewsWindowConfig:
    mode: NewsWindowMode = "off"
    start_utc: datetime | None = None
    end_utc: datetime | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"off", "shadow", "active"}:
            raise ValueError("news window mode must be off, shadow or active")
        if (self.start_utc is None) != (self.end_utc is None):
            raise ValueError("news window overrides must be paired")
        if self.start_utc is not None and self.end_utc is not None:
            start, end = utc_datetime(self.start_utc), utc_datetime(self.end_utc)
            if not timedelta(0) < end - start <= timedelta(days=7):
                raise ValueError("news override must span at most seven days")
            object.__setattr__(self, "start_utc", start)
            object.__setattr__(self, "end_utc", end)

    @classmethod
    def from_env(cls, env: Mapping[str, str], target_date: date | None = None) -> NewsWindowConfig:
        mode = env.get("INVESTO_NEWS_WINDOW_MODE", "off").strip()
        bounds = [
            env.get(key, "").strip() for key in ("INVESTO_NEWS_START_UTC", "INVESTO_NEWS_END_UTC")
        ]
        if any(bounds) and (not all(bounds) or target_date is None):
            raise ValueError("paired news overrides require an explicit replay date")
        if mode not in {"off", "shadow", "active"}:
            raise ValueError("news window mode must be off, shadow or active")
        try:
            start, end = (datetime.fromisoformat(value) if value else None for value in bounds)
            return cls(mode=mode, start_utc=start, end_utc=end)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError("invalid news window configuration") from None

    def validate_publication(self, *, replay: bool, dry_run: bool) -> None:
        if self.start_utc is not None and not replay:
            raise ValueError("news override requires replay")
        if self.mode == "active" and not replay and not dry_run and not NEWS_WINDOW_ACTIVE_READY:
            raise ValueError("news window activation requires separate operational approval")


DEFAULT_NEWS_WINDOW_CONFIG = NewsWindowConfig()


@dataclass(frozen=True, slots=True)
class NewsObservationWindow:
    logical_start: datetime
    requested_start: datetime
    end_utc: datetime
    mode: Literal["scheduled", "replay", "shadow"]
    run_id: str
    baseline_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_run(self.run_id)
        _validate_sha(self.baseline_ref)
        if self.mode not in {"scheduled", "replay", "shadow"}:
            raise ValueError("invalid news observation mode")
        for name in ("logical_start", "requested_start", "end_utc"):
            object.__setattr__(self, name, utc_datetime(getattr(self, name)))
        span = self.end_utc - self.requested_start
        if not timedelta(0) <= span <= timedelta(days=7):
            raise ValueError("news observation interval exceeds seven days")
        if self.end_utc <= self.logical_start and self.requested_start != self.end_utc:
            raise ValueError("held news window must have an empty requested interval")
        if self.end_utc > self.logical_start and self.requested_start == self.end_utc:
            raise ValueError("active news window must have a nonempty requested interval")

    @property
    def start_utc(self) -> datetime:
        return self.requested_start

    @property
    def fetch_required(self) -> bool:
        return self.end_utc > self.logical_start

    @property
    def gap_seconds(self) -> float:
        return max(0.0, (self.requested_start - self.logical_start).total_seconds())

    def contains(self, value: datetime) -> bool:
        return self.fetch_required and self.requested_start <= utc_datetime(value) < self.end_utc


class NewsDocumentRevision(EventModel):
    document_id: Digest
    revision_id: Digest


class NewsSeenRevision(NewsDocumentRevision):
    source_name: SourceName
    segment: MarketSegment
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class NewsCursor(EventModel):
    source_name: SourceName
    segment: MarketSegment
    end_utc: datetime

    @field_validator("end_utc")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class NewsCursorLedger(EventModel):
    schema_version: Literal[1] = 1
    cursors: Annotated[tuple[NewsCursor, ...], Field(max_length=MAX_NEWS_WINDOWS)] = ()
    seen_revisions: Annotated[
        tuple[NewsSeenRevision, ...], Field(max_length=MAX_NEWS_REVISIONS)
    ] = ()

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        keys = [(cursor.source_name, cursor.segment) for cursor in self.cursors]
        seen = [
            (row.source_name, row.segment, row.document_id, row.revision_id)
            for row in self.seen_revisions
        ]
        if len(keys) != len(set(keys)) or len(seen) != len(set(seen)):
            raise ValueError("duplicate news ledger keys")
        if len({source for source, _ in keys}) > MAX_NEWS_SOURCES:
            raise ValueError("news ledger source limit exceeded")
        return self


@dataclass(frozen=True, slots=True)
class NewsCursorBaseline:
    baseline_sha: str
    cursor_hash: str
    ledger: NewsCursorLedger
    metadata_hash: str
    metadata_paths: tuple[Path, ...]
    run_id: str

    def __post_init__(self) -> None:
        _validate_sha(self.baseline_sha)
        if self.baseline_sha is None:
            raise ValueError("news baseline requires a fixed commit id")
        _validate_run(self.run_id)
        for value in (self.cursor_hash, self.metadata_hash):
            if re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError("invalid news baseline digest")
        paths = tuple(Path(path) for path in self.metadata_paths)
        if not paths or len(paths) > 32 or len(set(paths)) != len(paths):
            raise ValueError("invalid news metadata paths")
        if any(path.is_absolute() or ".." in path.parts or not path.parts for path in paths):
            raise ValueError("news metadata paths must be repository relative")
        object.__setattr__(self, "metadata_paths", paths)


@dataclass(frozen=True, slots=True)
class NewsWindowPlan:
    run_id: str
    mode: NewsWindowMode
    target_date: date
    observed_at: datetime
    replay: bool
    dry_run: bool
    baseline_ref: str | None
    baseline_cursor_hash: str | None
    windows: Mapping[NewsWindowKey, NewsObservationWindow]

    def __post_init__(self) -> None:
        _validate_run(self.run_id)
        _validate_sha(self.baseline_ref)
        if self.mode not in {"off", "shadow", "active"}:
            raise ValueError("invalid news plan mode")
        if type(self.replay) is not bool or type(self.dry_run) is not bool:
            raise ValueError("news replay/dry-run must be booleans")
        object.__setattr__(self, "observed_at", utc_datetime(self.observed_at))
        windows = dict(self.windows)
        if len(windows) > MAX_NEWS_WINDOWS:
            raise ValueError("news plan window limit exceeded")
        if (
            self.baseline_cursor_hash is not None
            and re.fullmatch(r"[0-9a-f]{64}", self.baseline_cursor_hash) is None
        ):
            raise ValueError("invalid news plan baseline digest")
        for (source, segment), window in windows.items():
            validate_news_source(source)
            if segment not in _SEGMENTS or window.run_id != self.run_id:
                raise ValueError("news window does not belong to plan")
            if window.baseline_ref != self.baseline_ref:
                raise ValueError("news window baseline differs from plan")
            if not self.replay and window.end_utc != self.observed_at:
                raise ValueError("scheduled news windows must share the observation clock")
        if len({source for source, _ in windows}) > MAX_NEWS_SOURCES:
            raise ValueError("news plan source limit exceeded")
        object.__setattr__(self, "windows", MappingProxyType(dict(sorted(windows.items()))))


@dataclass(frozen=True, slots=True)
class NewsWindowConsumption:
    run_id: str
    source_name: str
    segment: MarketSegment
    requested_start: datetime
    end_utc: datetime
    baseline_ref: str | None
    baseline_cursor_hash: str | None
    documents: tuple[NewsDocumentRevision, ...] = ()
    phase: Literal["generated", "sealed"] = "generated"
    sealed_markdown_sha256: str | None = None

    def __post_init__(self) -> None:
        _validate_run(self.run_id)
        validate_news_source(self.source_name)
        _validate_sha(self.baseline_ref)
        if self.segment not in _SEGMENTS or self.phase not in {"generated", "sealed"}:
            raise ValueError("invalid news consumption identity")
        start, end = utc_datetime(self.requested_start), utc_datetime(self.end_utc)
        if not timedelta(0) < end - start <= timedelta(days=7):
            raise ValueError("invalid consumed news interval")
        object.__setattr__(self, "requested_start", start)
        object.__setattr__(self, "end_utc", end)
        documents = tuple(self.documents)
        if (
            len(documents) > 1000
            or any(type(row) is not NewsDocumentRevision for row in documents)
            or len(set(documents)) != len(documents)
        ):
            raise ValueError("invalid news consumption document set")
        object.__setattr__(self, "documents", documents)
        if (
            self.baseline_cursor_hash is not None
            and re.fullmatch(r"[0-9a-f]{64}", self.baseline_cursor_hash) is None
        ):
            raise ValueError("invalid consumed baseline digest")
        if self.phase == "sealed":
            if (
                self.sealed_markdown_sha256 is None
                or re.fullmatch(r"[0-9a-f]{64}", self.sealed_markdown_sha256) is None
            ):
                raise ValueError("sealed consumption requires document digest")
        elif self.sealed_markdown_sha256 is not None:
            raise ValueError("generated consumption must not claim a seal")


class NewsManifestRow(EventModel):
    """Closed hash-only serialization of one recipient window and its disposition."""

    source_name: SourceName
    segment: MarketSegment
    window: NewsObservationWindow
    gap_seconds: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
    completeness: Literal["full", "partial", "unknown"]
    disposition: Literal["advanced", "clock_not_after_cursor", "not_sealed", "coverage_not_full"]
    consumption: NewsWindowConsumption | None

    @model_validator(mode="after")
    def coherent_receipt(self) -> Self:
        if self.gap_seconds != self.window.gap_seconds:
            raise ValueError("news manifest gap differs from window")
        if self.consumption is not None:
            receipt = self.consumption
            if (
                receipt.source_name,
                receipt.segment,
                receipt.run_id,
                receipt.requested_start,
                receipt.end_utc,
                receipt.baseline_ref,
            ) != (
                self.source_name,
                self.segment,
                self.window.run_id,
                self.window.requested_start,
                self.window.end_utc,
                self.window.baseline_ref,
            ):
                raise ValueError("news manifest consumption differs from window")
        if self.disposition == "advanced" and (
            self.completeness != "full"
            or self.consumption is None
            or self.consumption.phase != "sealed"
            or not self.window.fetch_required
        ):
            raise ValueError("advanced news manifest lacks sealed full coverage")
        if (self.disposition == "clock_not_after_cursor") != (not self.window.fetch_required):
            raise ValueError("news manifest hold differs from window")
        return self


class NewsWindowManifest(EventModel):
    schema_version: Literal[1]
    run_id: str
    baseline_cursor_hash: Digest
    windows: Annotated[tuple[NewsManifestRow, ...], Field(max_length=MAX_NEWS_WINDOWS)]

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("news manifest version must be an integer")
        return value

    @field_validator("run_id")
    @classmethod
    def valid_run_id(cls, value: str) -> str:
        _validate_run(value)
        return value

    @model_validator(mode="after")
    def consistent_rows(self) -> Self:
        keys = [(row.source_name, row.segment) for row in self.windows]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate news manifest recipients")
        if len({source for source, _ in keys}) > MAX_NEWS_SOURCES:
            raise ValueError("news manifest source limit exceeded")
        if len({row.window.baseline_ref for row in self.windows}) > 1:
            raise ValueError("news manifest has mixed baseline commits")
        for row in self.windows:
            if row.window.run_id != self.run_id or row.window.baseline_ref is None:
                raise ValueError("news manifest has inconsistent run identity")
            if row.consumption is not None and (
                row.consumption.baseline_cursor_hash != self.baseline_cursor_hash
            ):
                raise ValueError("news manifest consumption baseline differs")
        return self


def news_item_in_window(item: NormalizedItem, window: NewsObservationWindow) -> bool:
    """Date precision is interval overlap; a date anchor is never an event instant."""
    if not window.fetch_required:
        return False
    if item.raw_metadata.get("published_at_precision") != "date":
        return window.contains(item.published_at)
    raw_date = item.raw_metadata.get("published_date")
    raw_zone = item.raw_metadata.get("published_timezone")
    if not isinstance(raw_date, str) or not isinstance(raw_zone, str):
        return False
    try:
        day = date.fromisoformat(raw_date)
        zone = ZoneInfo(raw_zone)
        start = datetime.combine(day, time.min, zone).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    except (ValueError, OverflowError, ZoneInfoNotFoundError):
        return False
    return start < window.end_utc and end > window.requested_start
