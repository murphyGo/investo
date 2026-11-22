"""Typed latest-list checks and bounded field projection; HTTP stays with its owner."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from investo._internal.event_context import resolve_context_ref
from investo.models.enrichment import DartEnrichmentTrace, DartParserVersion, EnrichmentReason
from investo.models.event_context import ContextRef, EventContextDocument
from investo.models.event_evidence import (
    evidence_clock_utc,
    make_event_context_document,
    make_evidence_document,
    normalize_evidence_text,
)
from investo.models.items import NormalizedItem
from investo.sources._dart_document import MAX_BYTES, DartDocumentError, DartDocumentEvidence
from investo.sources._dart_document import parse_dart_document as _parse
from investo.sources._dart_terms_document import PARSER_VERSION as TERMS_PARSER_VERSION
from investo.sources._dart_terms_document import parse_dart_terms_document
from investo.sources.dart_disclosure import DartDisclosureAdapter

DartRequestKind = Literal["listing", "document"]
_PARSERS = {
    "dart-cb-correction-6.4-v1": _parse,
    TERMS_PARSER_VERSION: parse_dart_terms_document,
}
DART_PARSER_VERSIONS = frozenset(_PARSERS)


class DartRequestError(ValueError):
    def __init__(
        self, reason: EnrichmentReason, *, request_spent: bool = False, target_missing: bool = False
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.request_spent = request_spent
        self.target_missing = target_missing


@dataclass(frozen=True, slots=True)
class DartResponse:
    data: bytes = field(repr=False)
    received_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "received_at", evidence_clock_utc(self.received_at))


DartRequest = Callable[[DartRequestKind, Mapping[str, str]], Awaitable[DartResponse]]


@dataclass(frozen=True, slots=True)
class DartRuntimeEvidence:
    item: NormalizedItem = field(repr=False)
    context: EventContextDocument = field(repr=False)
    field_refs: Mapping[str, tuple[ContextRef, ...]] = field(repr=False)


def dart_identity(item: NormalizedItem) -> tuple[str, str]:
    """Reject malformed request identities before any credential-bearing GET."""
    filing = item.raw_metadata.get("rcept_no")
    corp = item.raw_metadata.get("corp_code")
    report = item.raw_metadata.get("report_nm")
    if (
        item.source_name != "dart-disclosure"
        or item.category != "news"
        or not isinstance(filing, str)
        or re.fullmatch(r"[0-9]{14}", filing) is None
        or not isinstance(corp, str)
        or re.fullmatch(r"[0-9]{8}", corp) is None
        or item.raw_metadata.get("rcept_dt") != filing[:8]
        or str(item.url) != f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing}"
        or not isinstance(report, str)
        or re.sub(r"\s+", "", normalize_evidence_text(report))
        != "[기재정정]주요사항보고서(전환사채권발행결정)"
    ):
        raise DartRequestError("parser_unsupported")
    try:
        date.fromisoformat(f"{filing[:4]}-{filing[4:6]}-{filing[6:8]}")
    except ValueError:
        raise DartRequestError("evidence_invalid") from None
    return filing, corp


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DartRequestError("latest_unavailable")
        result[key] = value
    return result


def _latest_entry(
    response: DartResponse, item: NormalizedItem, filing: str, corp: str, token: bytes
) -> tuple[NormalizedItem, Literal["as_observed"]]:
    if not response.data or len(response.data) > MAX_BYTES:
        raise DartRequestError("latest_unavailable")
    payload = json.loads(response.data.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    if token and token.decode() in json.dumps(payload, ensure_ascii=False):
        raise DartRequestError("evidence_invalid")
    if isinstance(payload, dict) and payload.get("status") == "013":
        if payload.get("list") not in (None, []) or any(
            not (value is None or (type(value) is int and value == 0) or value == "0")
            for value in (payload.get("total_count"), payload.get("total_page"))
        ):
            raise DartRequestError("latest_unavailable")
        raise DartRequestError("latest_unavailable", target_missing=True)
    if not isinstance(payload, dict) or payload.get("status") != "000":
        raise DartRequestError("latest_unavailable")
    totals = DartDisclosureAdapter._pagination(payload, 1)
    entries = payload.get("list")
    if (
        totals is None
        or totals[1] != 1
        or not isinstance(entries, list)
        or not 1 <= len(entries) <= 100
        or len(entries) != totals[0]
    ):
        raise DartRequestError("latest_unavailable")
    if any(
        not DartDisclosureAdapter._well_formed_entry(entry)
        or entry["corp_code"] != corp
        or entry["rcept_dt"] != filing[:8]
        for entry in entries
    ) or len({entry["rcept_no"] for entry in entries}) != len(entries):
        raise DartRequestError("listing_changed")
    matches = [entry for entry in entries if entry["rcept_no"] == filing]
    if len(matches) != 1:
        raise DartRequestError("latest_unavailable", target_missing=True)
    remark = matches[0].get("rm")
    if not isinstance(remark, str) or len(remark) > 32:
        raise DartRequestError("latest_unavailable")
    if "철" in remark:
        raise DartRequestError("withdrawn")
    if "정" in remark:
        raise DartRequestError("superseded")
    if set(remark) - set("유코채넥공연"):
        raise DartRequestError("latest_unavailable")
    fresh = DartDisclosureAdapter()._normalize_entry(
        matches[0], date_precision=item.raw_metadata.get("published_at_precision") == "date"
    )
    if fresh is None or any(
        getattr(fresh, name) != getattr(item, name)
        for name in ("title", "summary", "url", "published_at", "raw_metadata")
    ):
        raise DartRequestError("listing_changed")
    return fresh, "as_observed"


def dart_runtime_evidence(parsed: DartDocumentEvidence) -> DartRuntimeEvidence:
    """Pack verified fields into one paragraph so native passages keep all slots."""
    previous = parsed.item.event_evidence
    if previous is None:
        raise DartRequestError("evidence_invalid")
    if parsed.parser_version == TERMS_PARSER_VERSION:
        context = make_event_context_document(
            previous, metadata=parsed.item.raw_metadata, item=parsed.item, article_passages=True
        )
        if context.model_dump_json() != parsed.context.model_dump_json():
            raise DartRequestError("evidence_invalid")
        for group in parsed.field_refs.values():
            for ref in group:
                resolve_context_ref(ref, (context,))
        return DartRuntimeEvidence(parsed.item, context, parsed.field_refs)
    projection = previous.detail_excerpt.replace("\n", " ")
    evidence = make_evidence_document(
        source_name=previous.source_name,
        title=previous.title,
        summary=previous.summary,
        detail_excerpt=projection,
        url=previous.url,
        published_at=previous.published_at,
        published_date=previous.published_date,
        received_at=previous.received_at,
        source_tier="official",
    ).model_copy(update={"evidence_budget_limited": True})
    item = parsed.item.model_copy(update={"event_evidence": evidence})
    context = make_event_context_document(
        evidence, metadata=item.raw_metadata, item=item, article_passages=True
    )
    chunks = [
        chunk for chunk in context.chunks if chunk.source_locator.startswith("detail_excerpt:")
    ]
    if len(chunks) != 1 or chunks[0].text != projection:
        raise DartRequestError("evidence_invalid")
    original_chunks = {chunk.chunk_id: chunk for chunk in parsed.context.chunks}
    native_chunks = {(chunk.role, chunk.source_locator): chunk for chunk in context.chunks}
    refs: dict[str, tuple[ContextRef, ...]] = {}
    for slot, values in parsed.field_refs.items():
        remapped = []
        for ref in values:
            original = original_chunks[ref.chunk_id]
            native = native_chunks[(original.role, original.source_locator)]
            expected = (
                original.text.replace("\n", " ")
                if original.source_locator.startswith("detail_excerpt:")
                else original.text
            )
            if len(expected) != len(original.text) or native.text != expected:
                raise DartRequestError("evidence_invalid")
            remapped.append(
                ContextRef(
                    document_id=context.document_id,
                    revision_id=context.revision_id,
                    chunk_id=native.chunk_id,
                    start=ref.start,
                    end=ref.end,
                )
            )
        refs[slot] = tuple(remapped)
    for slot, values in refs.items():
        for old, new in zip(parsed.field_refs[slot], values, strict=True):
            if resolve_context_ref(old, (parsed.context,)) != resolve_context_ref(new, (context,)):
                raise DartRequestError("evidence_invalid")
    return DartRuntimeEvidence(item, context, refs)


async def prepare_dart_item(
    item: NormalizedItem,
    request: DartRequest,
    *,
    forbidden_token: bytes,
    parser_version: DartParserVersion = "dart-cb-correction-6.4-v1",
) -> tuple[NormalizedItem, EnrichmentReason | None, DartEnrichmentTrace]:
    blocked = item.model_copy(update={"event_input_blocked": True})
    if parser_version not in _PARSERS:
        return blocked, "parser_unsupported", DartEnrichmentTrace()
    trace = DartEnrichmentTrace(parser_version=parser_version)

    async def get(kind: DartRequestKind, params: Mapping[str, str]) -> DartResponse:
        nonlocal trace
        try:
            response = await request(kind, params)
        except DartRequestError as exc:
            trace = trace.model_copy(update={"requests": trace.requests + int(exc.request_spent)})
            raise
        trace = trace.model_copy(update={"requests": trace.requests + 1})
        return response

    try:
        filing, corp = dart_identity(item)
        listing = await get(
            "listing",
            {
                "corp_code": corp,
                "bgn_de": filing[:8],
                "end_de": filing[:8],
                "last_reprt_at": "Y",
                "page_no": "1",
                "page_count": "100",
            },
        )
        trace = trace.model_copy(
            update={
                "listing_received_at": listing.received_at,
                "listing_sha256": hashlib.sha256(listing.data).hexdigest(),
            }
        )
        _latest_entry(listing, item, filing, corp, forbidden_token)
        trace = trace.model_copy(update={"latest_status": "as_observed"})
        document = await get("document", {"rcept_no": filing})
        response_sha = hashlib.sha256(document.data).hexdigest()
        trace = trace.model_copy(
            update={
                "document_received_at": document.received_at,
                "response_sha256": response_sha,
            }
        )
        if document.received_at < listing.received_at:
            raise DartRequestError("evidence_invalid")
        parsed = _PARSERS[parser_version](
            item,
            document.data,
            response_sha256=response_sha,
            received_at=document.received_at,
            forbidden_token=forbidden_token,
        )
        if parsed.parser_version != parser_version:
            raise DartRequestError("evidence_invalid")
        runtime = dart_runtime_evidence(parsed)
        trace = trace.model_copy(
            update={
                "document_received_at": document.received_at,
                "response_sha256": response_sha,
                "xml_sha256": parsed.xml_sha256,
                "native_context_sha256": hashlib.sha256(
                    runtime.context.model_dump_json().encode()
                ).hexdigest(),
            }
        )
        return runtime.item, None, trace
    except DartRequestError as exc:
        if exc.reason in {"superseded", "withdrawn"}:
            trace = trace.model_copy(update={"latest_status": exc.reason})
        elif exc.target_missing:
            trace = trace.model_copy(update={"latest_status": "missing"})
        return blocked, exc.reason, trace
    except DartDocumentError as exc:
        reason: EnrichmentReason = (
            "parser_unsupported" if str(exc) == "dart.schema_unsupported" else "evidence_invalid"
        )
        return blocked, reason, trace
    except (ValueError, TypeError, KeyError, RecursionError):
        return blocked, "evidence_invalid", trace
