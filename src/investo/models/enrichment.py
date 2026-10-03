"""Closed qualification records and immutable bounds for optional official HTTP."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Self, cast
from urllib.parse import urlsplit

from pydantic import Field, StrictInt, field_validator, model_validator

from investo.models.event_evidence import evidence_clock_utc
from investo.models.events import Digest, EventModel
from investo.models.items import NormalizedItem

EnrichmentMode = Literal["off", "shadow", "active"]
EnrichmentSource = Literal["fomc-rss", "fed-speech-rss", "sec-newsroom-rss", "cftc-policy-rss"]
ENRICHMENT_MODE_ENV = "INVESTO_EVENT_ENRICHMENT_MODE"
EVENT_ENRICHMENT_ACTIVE_READY = False


@dataclass(frozen=True, slots=True)
class EnrichmentPolicy:
    mode: EnrichmentMode = "off"
    max_requests: int = 6
    concurrency: int = 2
    request_timeout_s: float = 8.0
    total_budget_s: float = 20.0
    max_response_bytes: int = 500 * 1024
    max_items_per_source: int = 2
    max_excerpt_chars: int = 1200
    max_redirects: int = 1

    def __post_init__(self) -> None:
        if self.mode not in {"off", "shadow", "active"}:
            raise ValueError("event enrichment mode must be off, shadow or active")
        for value, maximum, minimum in (
            (self.max_requests, 6, 1),
            (self.concurrency, 2, 1),
            (self.max_response_bytes, 500 * 1024, 1),
            (self.max_items_per_source, 2, 1),
            (self.max_excerpt_chars, 1200, 1),
            (self.max_redirects, 1, 0),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("event enrichment limit is outside approved bounds")
        for duration, maximum in ((self.request_timeout_s, 8), (self.total_budget_s, 20)):
            if (
                type(duration) not in {int, float}
                or not math.isfinite(duration)
                or not 0 < duration <= maximum
            ):
                raise ValueError("event enrichment duration is outside approved bounds")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> EnrichmentPolicy:
        raw = env.get(ENRICHMENT_MODE_ENV, "off").strip()
        if raw not in {"off", "shadow", "active"}:
            raise ValueError("event enrichment mode must be off, shadow or active")
        return cls(mode=cast("EnrichmentMode", raw))

    def validate_activation(self) -> None:
        if self.mode == "active" and not EVENT_ENRICHMENT_ACTIVE_READY:
            raise ValueError("event body enrichment requires separate operational approval")


DEFAULT_ENRICHMENT_POLICY = EnrichmentPolicy()


class SourceQualification(EventModel):
    source_name: EnrichmentSource
    checked_at: datetime
    official_discovery_url: Annotated[str, Field(strict=True, max_length=500)]
    allowed_host: Annotated[str, Field(strict=True, max_length=100)] | None
    allowed_path: Annotated[str, Field(strict=True, max_length=200)] | None
    content_type: Literal["text/html"] | None
    public_rights_basis: Annotated[str, Field(strict=True, max_length=2000)] | None
    extraction_selector_version: (
        Annotated[str, Field(strict=True, pattern=r"^[a-z0-9-]{1,80}$")] | None
    )
    fixture_sha256: Digest | None
    status: Literal["qualified", "blocked", "rejected"]
    reason: Annotated[str, Field(strict=True, min_length=1, max_length=500)]

    @field_validator("checked_at")
    @classmethod
    def checked_clock(cls, value: datetime) -> datetime:
        return evidence_clock_utc(value)

    @model_validator(mode="after")
    def qualified_evidence(self) -> Self:
        hosts = {
            "fomc-rss": "www.federalreserve.gov",
            "fed-speech-rss": "www.federalreserve.gov",
            "sec-newsroom-rss": "www.sec.gov",
            "cftc-policy-rss": "www.cftc.gov",
        }
        discovery = urlsplit(self.official_discovery_url)
        if (
            discovery.scheme != "https"
            or discovery.hostname != hosts[self.source_name]
            or (
                discovery.username is not None
                or discovery.password is not None
                or discovery.port is not None
            )
        ):
            raise ValueError("qualification discovery must belong to its official source")
        if self.allowed_host is not None and self.allowed_host != hosts[self.source_name]:
            raise ValueError("qualification host must belong to its official source")
        if self.allowed_path is not None and (
            re.fullmatch(r"/[A-Za-z0-9_./-]+/", self.allowed_path) is None
            or ".." in self.allowed_path
            or "//" in self.allowed_path
        ):
            raise ValueError("qualification path must be a literal scoped directory")
        if self.status == "qualified" and not all(
            (
                self.allowed_host,
                self.allowed_path,
                self.content_type,
                self.public_rights_basis,
                self.extraction_selector_version,
                self.fixture_sha256,
            )
        ):
            raise ValueError("qualified source requires rights, parser and live fixture evidence")
        return self


class EnrichmentQualification(EventModel):
    schema_version: Literal[1] = 1
    sources: Annotated[tuple[SourceQualification, ...], Field(max_length=4)] = ()

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        if len({row.source_name for row in self.sources}) != len(self.sources):
            raise ValueError("duplicate enrichment qualification source")
        return self


EnrichmentReason = Literal[
    "unqualified",
    "url_rejected",
    "budget_exhausted",
    "request_failed",
    "timed_out",
    "content_type",
    "selector_unavailable",
    "empty_excerpt",
    "redirect_rejected",
    "evidence_invalid",
]


class EnrichmentOutcome(EventModel):
    source_name: EnrichmentSource
    document_id: Digest
    status: Literal["enriched", "enrichment_unavailable"]
    reason: EnrichmentReason | None = None

    @model_validator(mode="after")
    def coherent_status(self) -> Self:
        if (self.status == "enriched") != (self.reason is None):
            raise ValueError("enrichment outcome reason must match status")
        return self


class EnrichmentResult(EventModel):
    items: tuple[NormalizedItem, ...]
    outcomes: Annotated[tuple[EnrichmentOutcome, ...], Field(max_length=8)] = ()
    request_count: Annotated[StrictInt, Field(ge=0, le=6)] = 0
