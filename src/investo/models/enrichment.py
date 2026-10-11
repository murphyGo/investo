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


SourceSlotId = Literal[
    "policy.monetary_decision",
    "policy.official_statement",
    "policy.regulatory_action",
    "policy.domestic_announcement",
    "earnings.reported_actual",
    "earnings.guidance",
    "domestic.disclosure_action",
    "earnings.schedule_context",
]
SlotReason = Literal[
    "access.denied",
    "access.unavailable",
    "access.not_verified",
    "rights.unknown",
    "rights.out_of_scope",
    "schema.unknown",
    "schema.mismatch",
    "slot.required_missing",
    "time.unknown",
    "locator.missing",
    "runtime.not_verified",
    "candidate.new_provider",
]
SLOT_REQUIRED_FIELDS: Mapping[SourceSlotId, tuple[str, ...]] = {
    "policy.monetary_decision": ("actor", "decision", "size_or_scope"),
    "policy.official_statement": ("speaker", "quoted_claim"),
    "policy.regulatory_action": ("authority", "action", "action_status", "target_scope"),
    "policy.domestic_announcement": ("authority", "action", "target_scope"),
    "earnings.reported_actual": (
        "issuer",
        "metric",
        "actual_value",
        "unit",
        "period",
        "filing_locator",
    ),
    "earnings.guidance": ("issuer", "guidance_claim", "guidance_period"),
    "domestic.disclosure_action": (
        "issuer",
        "action",
        "action_status",
        "action_terms",
        "filing_locator",
    ),
    "earnings.schedule_context": ("issuer", "scheduled_date", "report_bucket"),
}


class EndpointScope(EventModel):
    """Qualification evidence scope; never an HTTP runtime permission."""

    scheme: Literal["https"] = "https"
    host: Annotated[str, Field(strict=True, min_length=3, max_length=100)]
    path_prefix: Annotated[str, Field(strict=True, min_length=1, max_length=300)]
    query_keys: Annotated[tuple[str, ...], Field(max_length=16)] = ()

    @model_validator(mode="after")
    def literal_endpoint(self) -> Self:
        import ipaddress
        from urllib.parse import unquote

        if (
            self.host != self.host.lower()
            or re.fullmatch(r"[a-z0-9][a-z0-9.-]*", self.host) is None
            or "." not in self.host
            or self.host.endswith((".local", ".localhost", ".internal", "."))
            or not self.path_prefix.startswith("/")
            or any(token in unquote(self.path_prefix) for token in ("..", "//", "?", "#", "\\"))
        ):
            raise ValueError("slot.endpoint_invalid")
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            pass
        else:
            raise ValueError("slot.endpoint_invalid")
        if len(set(self.query_keys)) != len(self.query_keys) or any(
            re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key) is None for key in self.query_keys
        ):
            raise ValueError("slot.endpoint_invalid")
        return self


class SourceSlotQualification(EventModel):
    source_name: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,80}$")] | None = None
    proposed_source_name: Annotated[str, Field(pattern=r"^[a-z0-9-]{1,80}$")] | None = None
    slot_id: SourceSlotId
    access_kind: Literal["feed", "structured_api", "official_body"]
    endpoint_scope: EndpointScope | None = None
    official_discovery_url: Annotated[str, Field(max_length=1000)] | None = None
    checked_at: datetime
    source_code_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    status: Literal["verified", "blocked"]
    reason_codes: Annotated[tuple[SlotReason, ...], Field(max_length=12)] = ()
    access_evidence_hash: Digest | None = None
    rights_evidence_url: Annotated[str, Field(max_length=1000)] | None = None
    rights_scope: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    schema_fixture_sha256: Digest | None = None
    parser_version: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,79}$")] | None = None
    required_slots: Annotated[tuple[str, ...], Field(max_length=16)]
    verified_slots: Annotated[tuple[str, ...], Field(max_length=16)] = ()
    missing_slots: Annotated[tuple[str, ...], Field(max_length=16)]
    chunk_roles: Annotated[
        tuple[
            Literal[
                "identity", "fact", "comparison", "background", "meaning", "reaction", "follow_up"
            ],
            ...,
        ],
        Field(max_length=7),
    ] = ()
    time_precision: Literal["exact", "date", "unknown"] = "unknown"
    public_locator_basis: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    runtime_probe_status: Literal["verified", "blocked", "not_run"] = "not_run"
    runtime_evidence_ref: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    activation_ready: Literal[False] = False

    @field_validator("checked_at")
    @classmethod
    def checked_slot_clock(cls, value: datetime) -> datetime:
        return evidence_clock_utc(value)

    @model_validator(mode="after")
    def source_slot_evidence(self) -> Self:
        if (self.source_name is None) == (self.proposed_source_name is None):
            raise ValueError("slot.source_invalid")
        for field in (
            self.required_slots,
            self.verified_slots,
            self.missing_slots,
            self.chunk_roles,
            self.reason_codes,
        ):
            if len(set(field)) != len(field):
                raise ValueError("slot.duplicate")
        required = set(SLOT_REQUIRED_FIELDS[self.slot_id])
        if (
            set(self.required_slots) != required
            or not set(self.verified_slots) <= required
            or set(self.missing_slots) != required - set(self.verified_slots)
        ):
            raise ValueError("slot.required_missing")
        for href in (self.official_discovery_url, self.rights_evidence_url):
            if href is not None:
                url = urlsplit(href)
                if (
                    url.scheme != "https"
                    or not url.hostname
                    or url.username is not None
                    or url.password is not None
                    or url.port not in {None, 443}
                    or url.fragment
                    or url.query
                ):
                    raise ValueError("slot.evidence_url_invalid")
                EndpointScope(host=url.hostname, path_prefix=url.path or "/")
        if (
            self.access_kind == "official_body"
            and self.endpoint_scope is not None
            and self.endpoint_scope.query_keys
        ):
            raise ValueError("slot.endpoint_invalid")
        if self.runtime_probe_status == "verified" and self.runtime_evidence_ref is None:
            raise ValueError("slot.runtime_unbound")
        if self.status == "blocked" and not self.reason_codes:
            raise ValueError("slot.blocked_reason_missing")
        if self.proposed_source_name is not None and (
            self.status == "verified" or "candidate.new_provider" not in self.reason_codes
        ):
            raise ValueError("slot.new_provider_requires_separate_plan")
        if self.status == "verified":
            if (
                any(
                    value is None
                    for value in (
                        self.endpoint_scope,
                        self.official_discovery_url,
                        self.access_evidence_hash,
                        self.rights_evidence_url,
                        self.rights_scope,
                        self.schema_fixture_sha256,
                        self.parser_version,
                        self.public_locator_basis,
                    )
                )
                or self.missing_slots
                or "identity" not in self.chunk_roles
                or any(
                    reason not in {"time.unknown", "runtime.not_verified"}
                    for reason in self.reason_codes
                )
            ):
                raise ValueError("slot.verified_evidence_missing")
            if self.time_precision == "unknown" and "time.unknown" not in self.reason_codes:
                raise ValueError("slot.time_unbound")
        return self


class SourceSlotQualificationSet(EventModel):
    schema_version: Literal[1] = 1
    records: Annotated[tuple[SourceSlotQualification, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def unique_slots(self) -> Self:
        keys = [
            (
                row.source_name or row.proposed_source_name,
                row.slot_id,
                row.access_kind,
                row.endpoint_scope.model_dump_json() if row.endpoint_scope else None,
            )
            for row in self.records
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("slot.duplicate")
        if len(self.model_dump_json().encode("utf-8")) > 64 * 1024:
            raise ValueError("slot.manifest_budget_exhausted")
        return self
