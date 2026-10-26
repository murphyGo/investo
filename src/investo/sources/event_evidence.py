"""Explicitly opted-in feed evidence; body access requires qualified source records."""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, cast
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

import httpx

from investo.models.enrichment import (
    EndpointScope,
    EnrichmentOutcome,
    EnrichmentPolicy,
    EnrichmentQualification,
    EnrichmentReason,
    EnrichmentResult,
    EnrichmentSource,
    SourceQualification,
    SourceSlotQualification,
    SourceSlotQualificationSet,
)
from investo.models.event_context import ContextRef, EventContextDocument
from investo.models.event_evidence import (
    canonical_evidence_url,
    event_digest,
    evidence_clock_utc,
    evidence_date_fields,
    make_evidence_document,
    normalize_evidence_text,
)
from investo.models.event_passages import passage_spans
from investo.models.items import NormalizedItem
from investo.sources._retry import RetryConfig, retry_get
from investo.sources.protocol import SourceFetchError

SourceTier = Literal["official", "primary", "secondary", "unknown"]
_BODY_SOURCES = frozenset({"fomc-rss", "fed-speech-rss", "sec-newsroom-rss", "cftc-policy-rss"})
_SELECTORS = frozenset({"fed-article-body-v1", "cftc-press-article-body-v1"})


def attach_feed_evidence(
    item: NormalizedItem,
    *,
    detail_excerpt: str,
    received_at: datetime | None,
    source_tier: SourceTier | None = None,
    excerpt_limit: int = 1200,
) -> NormalizedItem:
    """Attach source-owned pre-summary-cut text; None preserves the exact legacy item."""
    if received_at is None:
        return item
    if type(excerpt_limit) is not int or not 1 <= excerpt_limit <= 6000:
        raise ValueError("excerpt outside approved bounds")
    publication_day, event_day = evidence_date_fields(item.raw_metadata)
    tier = source_tier or (
        "official"
        if item.raw_metadata.get("official_source") == "true"
        else "primary"
        if item.raw_metadata.get("source_tier") == "primary"
        else "unknown"
    )
    evidence = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary or "",
        detail_excerpt=normalize_evidence_text(detail_excerpt)[:excerpt_limit],
        url=str(item.url) if item.url is not None else None,
        published_at=item.published_at,
        received_at=received_at,
        published_date=publication_day,
        event_time=event_day,
        event_time_basis="source_date" if event_day is not None else "unknown",
        source_tier=tier,
    )
    return item.model_copy(update={"event_evidence": evidence})


def load_enrichment_qualification(path: Path) -> EnrichmentQualification:
    """Read a small closed manifest without retaining rejected input in errors."""
    try:
        if not path.is_file():
            raise ValueError("qualification requires a regular file")
        with path.open("rb") as handle:
            data = handle.read(64 * 1024 + 1)
        if len(data) > 64 * 1024:
            raise ValueError("qualification exceeds byte budget")
        return EnrichmentQualification.model_validate_json(data)
    except (OSError, ValueError):
        raise ValueError("event source qualification unavailable") from None


def _allowed_url(url: str, qualification: SourceQualification) -> bool:
    """Only a literal directly-linked HTTPS locator within its qualified path."""
    try:
        parsed = urlsplit(url)
        return bool(
            qualification.status == "qualified"
            and qualification.allowed_host is not None
            and qualification.allowed_path is not None
            and parsed.scheme == "https"
            and parsed.hostname == qualification.allowed_host
            and parsed.netloc == qualification.allowed_host
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and parsed.path.startswith(qualification.allowed_path)
            and re.fullmatch(r"/[A-Za-z0-9_./-]+", parsed.path) is not None
            and ".." not in parsed.path
            and "//" not in parsed.path
        )
    except ValueError:
        return False


class _BodyParser(HTMLParser):
    """Two qualified selectors, no script execution or generic page fallback."""

    _VOID = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )
    _HIDDEN = frozenset(
        {
            "script",
            "style",
            "noscript",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "svg",
            "template",
        }
    )

    def __init__(self, selector: str, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.selector, self.limit = selector, limit
        self.stack: list[tuple[str, str | None, bool]] = []
        self.selected_depth: int | None = None
        self.matches = 0
        self.complete = False
        self.text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len(self.stack) >= 256:
            raise ValueError("official body nesting exceeds parser bound")
        attributes = dict(attrs)
        classes = frozenset((attributes.get("class") or "").split())
        selected = (
            self.selector == "fed-article-body-v1"
            and tag == "div"
            and bool(self.stack)
            and self.stack[-1][1] == "article"
            and {"col-xs-12", "col-sm-8", "col-md-8"} <= classes
            and "heading" not in classes
        ) or (
            self.selector == "cftc-press-article-body-v1"
            and "field--name-body" in classes
            and any(parent[0] == "article" for parent in self.stack)
        )
        hidden = (
            tag in self._HIDDEN
            or "hidden" in attributes
            or attributes.get("aria-hidden") == "true"
            or re.search(
                r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
                attributes.get("style") or "",
                re.IGNORECASE,
            )
            is not None
        )
        if selected:
            self.matches += 1
            if self.matches == 1:
                self.selected_depth = len(self.stack)
        if tag not in self._VOID:
            self.stack.append((tag, attributes.get("id"), hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.limit > 1200 and tag in {"p", "li", "h2", "h3"} and self.selected_depth is not None:
            self.text = self.text.rstrip() + "\n"
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                if self.selected_depth is not None and index <= self.selected_depth:
                    self.complete = True
                    self.selected_depth = None
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if self.selected_depth is None or any(row[2] for row in self.stack):
            return
        if len(self.text) < self.limit:
            text = re.sub(r"\s+", " ", normalize_evidence_text(data)).strip()
            if text:
                self.text = (self.text + ("" if self.text.endswith("\n") else " ") + text).lstrip()[
                    : self.limit
                ]


def _body_excerpt(
    response: httpx.Response, qualification: SourceQualification, limit: int
) -> tuple[str | None, EnrichmentReason | None, bool]:
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != qualification.content_type:
        return None, "content_type", False
    parser = _BodyParser(
        qualification.extraction_selector_version or "", 500 * 1024 if limit > 1200 else limit
    )
    try:
        parser.feed(response.text)
        parser.close()
    except (ValueError, RecursionError, AssertionError):
        return None, "selector_unavailable", False
    if parser.matches != 1 or not parser.complete:
        return None, "selector_unavailable", False
    limited = False
    text = parser.text
    if limit > 1200:
        spans = passage_spans(text, limit=limit)
        text = "\n".join(text[start:end] for start, end in spans)
        # Separators are also part of the bounded retained buffer.
        while len(text) > limit and spans:
            spans = spans[:-1]
            text = "\n".join(parser.text[start:end] for start, end in spans)
        cursor = 0
        for start, end in spans:
            limited |= bool(parser.text[cursor:start].strip())
            cursor = end
        limited |= bool(parser.text[cursor:].strip())
    return (text, None, limited) if text else (None, "empty_excerpt", limited)


@dataclass(frozen=True, slots=True)
class _Candidate:
    index: int
    item: NormalizedItem
    source: EnrichmentSource
    document_id: str


def _candidates(
    items: Sequence[NormalizedItem], cap: int, records: Mapping[str, SourceQualification]
) -> tuple[_Candidate, ...]:
    # A newer testimony or other non-qualified URL cannot spend the body quota
    # of an older, directly linked qualified release from the same RSS feed.
    grouped: dict[str, tuple[list[_Candidate], list[_Candidate]]] = {}
    seen: set[tuple[str, str, bool]] = set()
    for index, item in sorted(
        enumerate(items),
        key=lambda row: (
            -row[1].published_at.timestamp(),
            row[1].source_name,
            str(row[1].url),
            row[1].title,
        ),
    ):
        if item.source_name not in _BODY_SOURCES or item.scheduled_at is not None:
            continue
        url = str(item.url) if item.url else None
        try:
            identity = canonical_evidence_url(url) or (item.title, item.published_at.isoformat())
        except ValueError:
            identity = (item.title, item.published_at.isoformat())
        document_id = event_digest(item.source_name, identity)
        record = records.get(item.source_name)
        eligible = bool(
            record is not None
            and record.extraction_selector_version in _SELECTORS
            and _allowed_url(url or "", record)
        )
        key = item.source_name, document_id, eligible
        if key in seen:
            continue
        seen.add(key)
        lanes = grouped.setdefault(item.source_name, ([], []))
        lanes[0 if eligible else 1].append(
            _Candidate(index, item, cast("EnrichmentSource", item.source_name), document_id)
        )
    selected: dict[str, list[_Candidate]] = {}
    for source, (eligible_items, rejected_items) in grouped.items():
        selected[source] = eligible_items[:cap]
        eligible_ids = {item.document_id for item in eligible_items}
        rejected = [item for item in rejected_items if item.document_id not in eligible_ids]
        selected[source].extend(rejected[: cap - len(selected[source])])
    return tuple(
        bucket[offset]
        for offset in range(cap)
        for _source, bucket in sorted(selected.items())
        if offset < len(bucket)
    )


async def enrich_event_evidence(
    items: Sequence[NormalizedItem],
    *,
    client: httpx.AsyncClient,
    policy: EnrichmentPolicy,
    qualification: EnrichmentQualification,
    received_at: datetime,
    deadline: float | None = None,
) -> EnrichmentResult:
    """Bounded official body reads; each failure retains the original feed item."""
    if policy.mode not in {"active", "preview"}:
        return EnrichmentResult(items=tuple(items))
    policy.validate_activation()
    if policy.mode == "preview" and policy.qualification_sha256 != qualification.policy_hash:
        raise ValueError("event preview qualification hash mismatch")
    received_at = evidence_clock_utc(received_at)
    if client.follow_redirects:
        raise ValueError("event enrichment requires automatic redirects disabled")
    if deadline is not None and (type(deadline) not in {float, int} or not math.isfinite(deadline)):
        raise ValueError("event enrichment deadline must be finite monotonic time")
    stop_at = min(
        time.monotonic() + policy.total_budget_s, deadline if deadline is not None else math.inf
    )
    records: dict[str, SourceQualification] = {
        record.source_name: record for record in qualification.sources
    }
    candidates = tuple(
        candidate
        for candidate in _candidates(items, policy.max_items_per_source, records)
        if policy.mode != "preview" or candidate.source in policy.preview_sources
    )
    results: dict[int, tuple[NormalizedItem, EnrichmentReason | None]] = {}
    semaphore = asyncio.Semaphore(policy.concurrency)
    request_count = 0

    async def enrich(candidate: _Candidate) -> None:
        nonlocal request_count
        item, record = candidate.item, records.get(candidate.source)
        reason: EnrichmentReason | None = "unqualified"
        if (
            record is None
            or record.status != "qualified"
            or record.max_excerpt_chars < policy.max_excerpt_chars
        ):
            results[candidate.index] = item, reason
            return
        if record.extraction_selector_version not in _SELECTORS:
            results[candidate.index] = item, "selector_unavailable"
            return
        url = str(item.url) if item.url else ""
        if not _allowed_url(url, record):
            results[candidate.index] = item, "url_rejected"
            return
        async with semaphore:
            for hop in range(policy.max_redirects + 1):
                remaining = stop_at - time.monotonic()
                if request_count >= policy.max_requests or remaining <= 0:
                    reason = "budget_exhausted"
                    break
                request_count += 1
                try:
                    response = await retry_get(
                        client,
                        url,
                        source_name=candidate.source,
                        config=RetryConfig(
                            timeout_s=min(policy.request_timeout_s, remaining),
                            retries=0,
                            backoffs=(),
                            total_budget_s=min(policy.request_timeout_s, remaining),
                            max_response_bytes=policy.max_response_bytes,
                        ),
                    )
                except SourceFetchError as exc:
                    reason = (
                        "timed_out"
                        if isinstance(exc.cause, (TimeoutError, httpx.TimeoutException))
                        else "request_failed"
                    )
                    break
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    redirected = urljoin(url, location) if location else ""
                    if hop >= policy.max_redirects or not _allowed_url(redirected, record):
                        reason = "redirect_rejected"
                        break
                    url = redirected
                    continue
                if response.status_code != 200:
                    reason = "request_failed"
                    break
                excerpt, reason, excerpt_limited = _body_excerpt(
                    response, record, policy.max_excerpt_chars
                )
                if excerpt is not None:
                    try:
                        enriched = attach_feed_evidence(
                            item,
                            detail_excerpt=excerpt,
                            received_at=received_at,
                            source_tier="official",
                            excerpt_limit=policy.max_excerpt_chars,
                        )
                    except ValueError:
                        reason = "evidence_invalid"
                        break
                    if (
                        enriched.event_evidence is None
                        or enriched.event_evidence.document_id != candidate.document_id
                    ):
                        reason = "evidence_invalid"
                        break
                    if excerpt_limited:
                        enriched = enriched.model_copy(
                            update={
                                "event_evidence": enriched.event_evidence.model_copy(
                                    update={"evidence_budget_limited": True}
                                )
                            }
                        )
                    results[candidate.index] = enriched, None
                    return
                break
            results[candidate.index] = item, reason

    tasks = [asyncio.create_task(enrich(candidate)) for candidate in candidates]
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=max(0, stop_at - time.monotonic()))
    except TimeoutError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    enriched_items = list(items)
    outcomes: list[EnrichmentOutcome] = []
    for candidate in candidates:
        item, reason = results.get(candidate.index, (candidate.item, "timed_out"))
        enriched_items[candidate.index] = item
        outcomes.append(
            EnrichmentOutcome(
                source_name=candidate.source,
                document_id=candidate.document_id,
                status="enriched" if reason is None else "enrichment_unavailable",
                reason=reason,
            )
        )
    return EnrichmentResult(
        items=tuple(enriched_items), outcomes=tuple(outcomes), request_count=request_count
    )


# A qualification matrix is evidence about slots, not another source registry.
_SLOT_EXISTING_SOURCES: Mapping[str, frozenset[str]] = {
    "policy.monetary_decision": frozenset({"fomc-rss"}),
    "policy.official_statement": frozenset({"fed-speech-rss"}),
    "policy.regulatory_action": frozenset({"cftc-policy-rss", "sec-newsroom-rss"}),
    "policy.domestic_announcement": frozenset({"korea-policy-rss"}),
    "earnings.reported_actual": frozenset({"sec-company-facts", "sec-edgar-8k"}),
    "earnings.guidance": frozenset({"sec-company-facts", "sec-edgar-8k"}),
    "domestic.disclosure_action": frozenset({"dart-disclosure"}),
    "earnings.schedule_context": frozenset({"nasdaq-earnings-calendar"}),
}


def _slot_locator_allowed(url: str, scope: EndpointScope) -> bool:
    """A verified endpoint includes its authority and decoded path boundary."""
    try:
        locator = urlsplit(url)
        path = locator.path
        for _ in range(4):
            decoded = unquote(path)
            if decoded == path:
                break
            path = decoded
        return (
            locator.scheme == "https"
            and locator.hostname == scope.host
            and locator.username is None
            and locator.password is None
            and locator.port in {None, 443}
            and not locator.fragment
            and "\\" not in path
            and "%" not in path
            and not any(part in {".", ".."} for part in path.split("/"))
            and path.startswith(scope.path_prefix)
            and not (set(key for key, _ in parse_qsl(locator.query)) - set(scope.query_keys))
        )
    except ValueError:
        return False


def load_source_slot_qualification(path: Path) -> SourceSlotQualificationSet:
    """Read a bounded offline matrix; this grants no collection capabilities."""
    from investo._internal.source_specs import SOURCE_SPECS_BY_NAME

    try:
        if not path.is_file():
            raise ValueError("slot.manifest_invalid")
        with path.open("rb") as handle:
            data = handle.read(64 * 1024 + 1)
        if len(data) > 64 * 1024:
            raise ValueError("slot.manifest_budget_exhausted")
        matrix = SourceSlotQualificationSet.model_validate_json(data)
        for row in matrix.records:
            if row.source_name is None:
                continue
            spec = SOURCE_SPECS_BY_NAME.get(row.source_name)
            if spec is None or row.source_name not in _SLOT_EXISTING_SOURCES[row.slot_id]:
                raise ValueError("slot.source_invalid")
            if row.endpoint_scope is not None and not any(
                row.endpoint_scope.host == domain or row.endpoint_scope.host.endswith("." + domain)
                for domain in spec.evidence_domains
            ):
                raise ValueError("slot.endpoint_invalid")
            if row.status == "verified":
                assert row.endpoint_scope is not None and row.official_discovery_url is not None
                if not _slot_locator_allowed(row.official_discovery_url, row.endpoint_scope):
                    raise ValueError("slot.endpoint_invalid")
        return matrix
    except (OSError, ValueError):
        raise ValueError("event source slot qualification unavailable") from None


def map_source_slot_context(
    item: NormalizedItem,
    qualification: SourceSlotQualification,
    *,
    received_at: datetime,
    field_refs: Mapping[str, tuple[ContextRef, ...]] | None = None,
) -> EventContextDocument:
    """Reuse the real u167 factory. Missing roles and unknown times stay missing."""
    from investo.models.event_evidence import (
        evidence_document_from_item,
        make_event_context_document,
    )

    qualification = SourceSlotQualification.model_validate(qualification.model_dump())
    if qualification.source_name != item.source_name:
        raise ValueError("slot.source_invalid")
    if qualification.status != "verified":
        raise ValueError("slot.required_missing")
    assert qualification.endpoint_scope is not None
    if not item.url or not _slot_locator_allowed(str(item.url), qualification.endpoint_scope):
        raise ValueError("slot.endpoint_invalid")
    document = make_event_context_document(
        evidence_document_from_item(item, received_at=received_at),
        metadata=item.raw_metadata,
        item=item,
    )
    from investo._internal.event_context import (
        context_lookup,
        metadata_ref_field,
        resolve_context_ref,
    )

    refs_by_field = dict(field_refs or {})
    if set(refs_by_field) != set(qualification.required_slots):
        raise ValueError("slot.required_missing")
    if any(not 1 <= len(refs) <= 16 for refs in refs_by_field.values()):
        raise ValueError("slot.required_missing")
    for refs in refs_by_field.values():
        for ref in refs:
            resolve_context_ref(ref, (document,))
    lookup = context_lookup((document,))
    values = {
        field: " ".join(resolve_context_ref(ref, lookup) for ref in refs)
        for field, refs in refs_by_field.items()
    }
    if len({ref for refs in refs_by_field.values() for ref in refs}) < min(3, len(refs_by_field)):
        raise ValueError("slot.required_missing")
    for field in {
        "actual_value",
        "scheduled_date",
        "unit",
        "period",
        "filing_locator",
    } & values.keys():
        value = values[field].strip()
        if (
            field == "actual_value"
            and re.fullmatch(r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?", value) is None
        ):
            raise ValueError("slot.required_missing")
        if (
            field == "unit"
            and re.fullmatch(r"%|USD|KRW|EUR|JPY|CNY|GBP|원|달러|유로|건|명|bp|bps", value) is None
        ):
            raise ValueError("slot.required_missing")
        if field in {"period", "scheduled_date"} and not re.search(
            r"\b(?:FY)?20\d{2}\b|Q[1-4]|[1-4]분기", value
        ):
            raise ValueError("slot.required_missing")
        if field == "filing_locator" and not (
            re.fullmatch(r"\d{10}-\d{2}-\d{6}|\d{14}", value)
            or (
                urlsplit(value).scheme == "https"
                and urlsplit(value).hostname == qualification.endpoint_scope.host
            )
        ):
            raise ValueError("slot.required_missing")
    if qualification.slot_id == "earnings.reported_actual":
        from investo._internal.event_context import (
            validate_context_fact,
            validate_fact_associations,
        )
        from investo.models.event_context import ContextFactDraft, ContextRef

        status_refs = []
        for chunk in document.chunks:
            for match in re.finditer(r"\bactual\b|실제|발표치", chunk.text, re.I):
                candidate = ContextRef(
                    document_id=document.document_id,
                    revision_id=document.revision_id,
                    chunk_id=chunk.chunk_id,
                    start=match.start(),
                    end=match.end(),
                )
                if chunk.source_locator != "source_metadata" or metadata_ref_field(
                    candidate, lookup
                ) in {"fact_status", "macro_status", "macro_actual_status", "macro_event_status"}:
                    status_refs.append(candidate)
        if not status_refs:
            raise ValueError("slot.required_missing")
        actual = ContextFactDraft(
            predicate="result",
            status="actual",
            value_kind="numeric",
            subject_refs=refs_by_field["issuer"],
            metric_refs=refs_by_field["metric"],
            value_refs=refs_by_field["actual_value"],
            unit_refs=refs_by_field["unit"],
            period_refs=refs_by_field["period"],
            status_refs=tuple(status_refs[:16]),
        )
        validate_context_fact(actual, lookup)
        validate_fact_associations((actual,), lookup)
    if not set(qualification.chunk_roles) <= {chunk.role for chunk in document.chunks}:
        raise ValueError("slot.required_missing")
    return document
