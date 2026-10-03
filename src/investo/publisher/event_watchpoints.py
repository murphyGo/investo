"""Pure source-fact watchpoints; numeric rows retain their existing resolver."""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Literal, cast
from urllib.parse import quote

from investo._internal.event_rendering import (
    EventNarrativeValidationError,
    validate_event_payload,
)
from investo.models.event_narratives import EventGenerationPayload, EventNarrative
from investo.models.events import (
    EventCandidate,
    EventFact,
    EventKind,
    EventWatchpoint,
    EventWatchpointNextCheck,
    EvidenceDocument,
    EvidenceRef,
)
from investo.publisher.reader_format.emphasis import wrap_numbers_bold

EVENT_WATCHPOINT_BLOCK_RE = re.compile(
    r"^<!-- investo:watch event:(?P<event_id>[0-9a-f]{24}) -->\n(?P<body>.*?)"
    r"^<!-- /investo:watch event:(?P=event_id) -->$",
    re.DOTALL | re.MULTILINE,
)
_MARKER_START = re.compile(r"<!--\s*/?investo:watch\b")
_SECTION = re.compile(r"(?ms)^## ⑥[^\n]*\n(.*?)(?=^## |\Z)")
_STATUS = {"actual": "실제", "quoted_opinion": "인용 발언", "scheduled": "예정"}
_NEXT_CHECK: dict[EventKind, str] = {
    "geopolitical": "관련 당국의 공식 결정과 후속 발표를 확인합니다.",
    "monetary_policy": "정책 당국의 공식 결정과 후속 발언을 확인합니다.",
    "macro_release": "후속 공식 지표 공개 내용을 확인합니다.",
    "earnings_result": "후속 실적 공개 내용을 확인합니다.",
    "product_service": "공식 서비스 제공 상태와 후속 공지를 확인합니다.",
    "public_statement": "발언 주체의 후속 공식 발언을 확인합니다.",
    "corporate_action": "기업의 후속 공식 결정과 공시를 확인합니다.",
    "regulation": "관할 기관의 공식 결정과 후속 공지를 확인합니다.",
    "market_structure": "시장 운영 기관의 공식 결정과 후속 공지를 확인합니다.",
}
_UNKNOWN_SOURCE = frozenset({"unknown", "미상", "출처 미상", "알 수 없음"})
_URL_SAFE = ":/?#[]@!$&'*,;=%+-._~"


@dataclass(frozen=True, slots=True)
class EventWatchpointBuildResult:
    watchpoints: tuple[EventWatchpoint, ...]
    attempted_count: int
    exclusions: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "watchpoints", tuple(self.watchpoints))
        object.__setattr__(self, "exclusions", tuple(self.exclusions))
        ids = tuple(card.event_id for card in self.watchpoints) + tuple(
            event_id for event_id, _ in self.exclusions
        )
        if type(self.attempted_count) is not int or self.attempted_count != len(ids):
            raise ValueError("event watchpoint attempts must equal cards plus exclusions")
        if len(set(ids)) != len(ids) or any(not reason.strip() for _, reason in self.exclusions):
            raise ValueError("event watchpoint outcomes must be distinct with nonblank reasons")


def _usable_source(doc: EvidenceDocument) -> bool:
    # Full URL syntax validation belongs to validate_event_payload above.
    return (
        doc.url is not None
        and doc.source_tier != "unknown"
        and doc.source_status in {"ok", "partial"}
        and doc.source_name.strip().casefold() not in _UNKNOWN_SOURCE
    )


def _observed_time(
    doc: EvidenceDocument,
) -> tuple[
    datetime | date,
    Literal["source_exact", "source_date", "publication_exact", "publication_date"],
]:
    if doc.event_time_basis != "unknown" and doc.event_time is not None:
        return doc.event_time, doc.event_time_basis
    if doc.published_date is not None:
        return doc.published_date, "publication_date"
    return doc.published_at, "publication_exact"


def _build_one(
    event: EventCandidate,
    narrative: EventNarrative,
    documents: dict[tuple[str, str], EvidenceDocument],
) -> tuple[EventWatchpoint | None, str]:
    if event.timing not in {"occurred", "announced"}:
        return None, "unsupported_timing"
    if event.evidence_state not in {"supported", "detail_limited"}:
        return None, "evidence_conflict"
    if narrative.meaning.text is None:
        return None, "meaning_unavailable"
    facts = tuple(fact for fact in event.change_facts if fact.fact_id in narrative.fact_ids)
    observed = next((fact for fact in facts if fact.status == "actual"), None)
    if observed is None:
        observed = next((fact for fact in facts if fact.status == "quoted_opinion"), None)
    if observed is None and event.timing == "announced" and len(facts) > 1:
        observed = next((fact for fact in facts if fact.status == "scheduled"), None)
    if observed is None:
        return None, "observed_state_unavailable"

    def document(ref: EvidenceRef) -> EvidenceDocument:
        return documents[(ref.document_id, ref.revision_id)]

    scheduled: EventFact | None = next(
        (
            fact
            for fact in facts
            if fact.status == "scheduled"
            and fact.fact_id != observed.fact_id
            and _usable_source(document(fact.evidence_ref))
        ),
        None,
    )
    next_check = (
        EventWatchpointNextCheck(
            kind="scheduled_fact",
            text=scheduled.value_text,
            fact_id=scheduled.fact_id,
            source_refs=(scheduled.evidence_ref,),
        )
        if scheduled is not None
        else EventWatchpointNextCheck(
            kind="observation_template", text=_NEXT_CHECK[event.event_kind]
        )
    )
    refs = tuple(
        dict.fromkeys(
            (
                *event.actor_refs,
                *event.action_refs,
                *event.object_refs,
                observed.evidence_ref,
                *narrative.meaning.evidence_refs,
                *next_check.source_refs,
            )
        )
    )
    docs = tuple(documents[key] for key in sorted({(r.document_id, r.revision_id) for r in refs}))
    if not all(_usable_source(doc) for doc in docs):
        return None, "source_unavailable"
    observed_at, time_basis = _observed_time(document(observed.evidence_ref))
    return EventWatchpoint(
        event_id=event.event_id,
        event_kind=event.event_kind,
        fact_id=observed.fact_id,
        fact_status=cast(Literal["actual", "quoted_opinion", "scheduled"], observed.status),
        headline=narrative.headline,
        observed_state=observed.value_text,
        observed_at=observed_at,
        time_basis=time_basis,
        source_refs=refs,
        source_labels=tuple(doc.source_name for doc in docs),
        source_urls=tuple(cast(str, doc.url) for doc in docs),
        next_check=next_check,
        implication=narrative.meaning.text,
    ), ""


def build_event_watchpoints(
    payload: EventGenerationPayload,
    *,
    surviving_event_ids: Sequence[str],
    source_limited_event_ids: Sequence[str] = (),
) -> EventWatchpointBuildResult:
    """Build from validated selected facts, never from generated today_watch.

    Payload trust errors propagate to the existing hard-gate owner. Ordinary
    absence of a usable current/meaning/source is an explicit card exclusion.
    """
    validate_event_payload(payload)
    selected = tuple(event.event_id for event in payload.plan.selected)
    surviving = tuple(surviving_event_ids)
    if surviving != tuple(event_id for event_id in selected if event_id in set(surviving)):
        raise EventNarrativeValidationError("event.selection_mismatch")
    source_limited = tuple(source_limited_event_ids)
    if len(set(source_limited)) != len(source_limited) or not set(source_limited) <= set(surviving):
        raise EventNarrativeValidationError("event.selection_mismatch")
    documents = {(doc.document_id, doc.revision_id): doc for doc in payload.plan.evidence_documents}
    cards: list[EventWatchpoint] = []
    exclusions: list[tuple[str, str]] = []
    for event, narrative in zip(payload.plan.selected, payload.narratives, strict=True):
        if event.event_id not in surviving:
            exclusions.append((event.event_id, "finalization_removed"))
            continue
        if event.event_id in source_limited:
            exclusions.append((event.event_id, "source_locator_missing"))
            continue
        card, reason = _build_one(event, narrative, documents)
        if card is None:
            exclusions.append((event.event_id, reason))
        else:
            cards.append(card)
    return EventWatchpointBuildResult(tuple(cards), len(selected), tuple(exclusions))


def _escape(text: str) -> str:
    return re.sub(r"([\\`*_[\]])", r"\\\1", html.escape(" ".join(text.split()), quote=False))


def _time_label(card: EventWatchpoint) -> str:
    prefix = "사건" if card.time_basis.startswith("source_") else "보도"
    if isinstance(card.observed_at, datetime):
        value = f"{card.observed_at:%Y-%m-%d %H:%M} UTC (출처 시각)"
    else:
        value = f"{card.observed_at.isoformat()} (출처 날짜)"
    suffix = "; 사건 시점 미확인" if prefix == "보도" else ""
    return f"{prefix} 기준 {value}{suffix}"


def render_event_watchpoint(watchpoint: EventWatchpoint) -> str:
    """Render an owned canonical card with no numeric-direction requirement."""
    card = EventWatchpoint.model_validate(watchpoint.model_dump(warnings="error"))
    links = ", ".join(
        f"[{_escape(label)}]({quote(url, safe=_URL_SAFE)})"
        for label, url in zip(card.source_labels, card.source_urls, strict=True)
    )
    next_label = "예정" if card.next_check.kind == "scheduled_fact" else "관찰 항목"
    markdown = "\n".join(
        (
            f"<!-- investo:watch event:{card.event_id} -->",
            f"#### 관찰 신호: {_escape(card.headline)}",
            "",
            f"- 출처: {links}",
            f"- 현재 상태: [{_STATUS[card.fact_status]}] {_escape(card.observed_state)}",
            f"- 기준 시점: {_time_label(card)}",
            f"- 다음 확인: [{next_label}] {_escape(card.next_check.text)}",
            f"- 관심 영향: {_escape(card.implication)}",
            f"<!-- /investo:watch event:{card.event_id} -->",
        )
    )
    return wrap_numbers_bold(markdown)


def event_watchpoint_ids(markdown: str) -> tuple[str, ...]:
    return tuple(match["event_id"] for match in EVENT_WATCHPOINT_BLOCK_RE.finditer(markdown))


class _CardContainerContext(HTMLParser):
    """Track only open containers around a card, without rewriting HTML."""

    _VOID_TAGS = frozenset(
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

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.containers: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Colon/address-shaped Markdown autolinks are not HTML containers.
        if tag not in self._VOID_TAGS and re.fullmatch(r"[a-z][a-z0-9-]*", tag):
            self.containers.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.containers:
            index = len(self.containers) - 1 - self.containers[::-1].index(tag)
            del self.containers[index:]

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # HTML non-void tags do not become closed merely by adding '/>'.
        self.handle_starttag(tag, attrs)


def _inside_literal_context(markdown: str, position: int) -> bool:
    """A canonical card must stand outside Markdown fences and raw HTML."""
    fence: tuple[str, int] | None = None
    html_context = _CardContainerContext()
    for line in markdown[:position].splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match is None:
            if fence is None:
                html_context.feed(line)
            continue
        marker, suffix = match.groups()
        if fence is None:
            if marker[0] != "`" or "`" not in suffix:
                fence = marker[0], len(marker)
        elif marker[0] == fence[0] and len(marker) >= fence[1] and not suffix.strip():
            fence = None
    return fence is not None or bool(html_context.containers)


def event_watchpoint_issue_codes(
    markdown: str,
    payload: EventGenerationPayload,
    *,
    surviving_event_ids: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Read-only check before repair and again against terminal survivors."""
    try:
        built = build_event_watchpoints(
            payload,
            surviving_event_ids=(
                tuple(event.event_id for event in payload.plan.selected)
                if surviving_event_ids is None
                else surviving_event_ids
            ),
        )
    except EventNarrativeValidationError as exc:
        return (exc.code,)
    expected = {card.event_id: render_event_watchpoint(card) for card in built.watchpoints}
    blocks = tuple(EVENT_WATCHPOINT_BLOCK_RE.finditer(markdown))
    sections = tuple(_SECTION.finditer(markdown))
    ids = tuple(block["event_id"] for block in blocks)
    codes: set[str] = set()
    if (
        len(_MARKER_START.findall(markdown)) != 2 * len(blocks)
        or len(set(ids)) != len(ids)
        or not set(ids) <= set(expected)
        or ids != tuple(event_id for event_id in expected if event_id in ids)
    ):
        codes.add("event.evidence_invalid")
    for block in blocks:
        placed = len(sections) == 1 and (
            sections[0].start(1) <= block.start() < block.end() <= sections[0].end(1)
        )
        if not placed or _inside_literal_context(markdown, block.start()):
            codes.add("event.evidence_invalid")
        original = expected.get(block["event_id"])
        if original is None or original == block.group(0):
            continue
        actual_lines, expected_lines = block.group(0).splitlines(), original.splitlines()
        for prefix, code in (
            ("#### 관찰 신호:", "event.entity_unsupported"),
            ("- 현재 상태:", "event.fact_unsupported"),
        ):
            if tuple(line for line in actual_lines if line.startswith(prefix)) != tuple(
                line for line in expected_lines if line.startswith(prefix)
            ):
                codes.add(code)
        codes.add("event.evidence_invalid")
    return tuple(sorted(codes))


__all__ = [
    "EVENT_WATCHPOINT_BLOCK_RE",
    "EventWatchpointBuildResult",
    "build_event_watchpoints",
    "event_watchpoint_ids",
    "event_watchpoint_issue_codes",
    "render_event_watchpoint",
]
