"""Pure event validation/rendering shared by generation and terminal publication.

This module verifies structured ownership, literal numeric/entity grounding and
bounded presentation. It does not prove semantic entailment of free prose;
annotated replay and the existing public hard gates remain independent checks.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

from investo._internal.summary_quality import is_unsafe_summary_value
from investo._internal.text import bound_at_sentence
from investo.models.event_narratives import EventGenerationPayload, EventNarrative
from investo.models.events import EventCandidate, EventFact, EvidenceDocument, EvidenceRef

EVENTS_MARKER = "<!-- investo:events version=2 -->"
NO_SELECTED_EVENTS = "수집된 근거에서 주요 사건을 선정하지 못했습니다."
COLLECTION_LIMITED_EVENTS = "뉴스 수집이 제한되어 중요 사건을 판단하기 어렵습니다."
NO_SURVIVING_EVENTS = "검증을 통과한 사건 설명을 제공하지 못했습니다."
REACTION_UNAVAILABLE = "시장 반응은 확인하지 못했습니다."
MEANING_UNAVAILABLE = "시장에 미치는 의미는 확인하지 못했습니다."

EventErrorCode = Literal[
    "event.narrative_invalid",
    "event.selection_mismatch",
    "event.fact_unsupported",
    "event.entity_unsupported",
    "event.evidence_invalid",
]


class EventNarrativeValidationError(ValueError):
    """A closed, source-free failure safe for retry feedback and hard findings."""

    def __init__(self, code: EventErrorCode) -> None:
        self.code = code
        super().__init__(code)


_NUMBER = re.compile(r"(?<![\d.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
_UNSAFE_TEXT = re.compile(r"https?://|www\.|<!--|[<>`\r\n]|\]\(", re.IGNORECASE)
_GENERIC = re.compile(
    r"(?:중요(?:한)?\s*(?:소식|사건|이슈)?입니다|관련\s*(?:소식|이슈)입니다|"
    r"확인이\s*필요합니다|지켜봐야\s*합니다|details?\s+(?:are\s+)?unavailable)[.!?。]?$",
    re.IGNORECASE,
)
_CONDITIONAL = re.compile(r"경우|라면|다면|수\s*있|가능성|조건|\b(?:if|could|may)\b", re.IGNORECASE)
_REACTION = re.compile(
    r"주가|시장|가격|수익률|거래량|반응|환율|수급|"
    r"\b(?:stocks?|shares?|price|market|yield|volume|reaction|response|gained|fell|rose)\b",
    re.IGNORECASE,
)
_NO_REACTION = re.compile(
    r"무반응|반응.{0,12}(?:없|미미)|변화.{0,12}없|"
    r"\b(?:no|little|muted)\b.{0,25}\b(?:reaction|response|change)\b|\bunchanged\b",
    re.IGNORECASE,
)
_FORECAST = re.compile(
    r"예상|전망|가이던스|추정|목표|\b(?:forecast|expected|guidance)\b", re.IGNORECASE
)
_EXPLICIT_ROLE_NUMBER = re.compile(
    r"(?P<role>실제|actual|예상|전망|forecast|expected|guidance)"
    r"[^0-9.!?。;\n]{0,32}(?P<value>[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?)",
    re.IGNORECASE,
)
_STATUS = {"actual": "실제", "forecast": "예상", "scheduled": "예정", "quoted_opinion": "인용 발언"}


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _plain(text: str) -> None:
    if not text.strip() or text != text.strip() or _UNSAFE_TEXT.search(text):
        raise EventNarrativeValidationError("event.narrative_invalid")


def _mentions(text: str, value: str) -> bool:
    # Latin product/actor identifiers cannot acquire an invented suffix. Hangul
    # particles may follow source names without whitespace in Korean prose.
    pattern = r"(?<![a-z0-9_])" + re.escape(_normal(value)) + r"(?![a-z0-9_])"
    return re.search(pattern, _normal(text)) is not None


def first_event_sentence(narrative: EventNarrative) -> str:
    """Return the first complete sentence verbatim; never truncate or summarize."""
    text = narrative.what_happened
    _plain(text)
    for end, char in enumerate(text[:80], 1):
        if char not in ".!?。":
            continue
        sentence = bound_at_sentence(text, end, require_complete=True)
        if sentence is not None:
            if is_unsafe_summary_value(sentence):
                break
            return sentence
    raise EventNarrativeValidationError("event.narrative_invalid")


def _lookup(payload: EventGenerationPayload) -> dict[tuple[str, str], EvidenceDocument]:
    return {(doc.document_id, doc.revision_id): doc for doc in payload.plan.evidence_documents}


def _resolve(ref: EvidenceRef, lookup: dict[tuple[str, str], EvidenceDocument]) -> str:
    doc = lookup.get((ref.document_id, ref.revision_id))
    if doc is None:
        raise EventNarrativeValidationError("event.evidence_invalid")
    buffer = getattr(doc, ref.field)
    if not isinstance(buffer, str) or not 0 <= ref.start < ref.end <= len(buffer):
        raise EventNarrativeValidationError("event.evidence_invalid")
    value = buffer[ref.start : ref.end]
    if not value.strip() or not 1 <= len(value) <= 240:
        raise EventNarrativeValidationError("event.evidence_invalid")
    return value


def _numbers(text: str) -> set[str]:
    return {match.group().replace(",", "").lstrip("+") for match in _NUMBER.finditer(text)}


def _check_numbers(text: str, source: str) -> None:
    if not _numbers(text) <= _numbers(source):
        raise EventNarrativeValidationError("event.fact_unsupported")


def _check_fact_roles(text: str, claims: Sequence[EventFact], context_numbers: set[str]) -> None:
    forecast = set().union(*(_numbers(f.value_text) for f in claims if f.status == "forecast"))
    actual = set().union(*(_numbers(f.value_text) for f in claims if f.status == "actual"))
    if _numbers(text) & (forecast - actual) and not _FORECAST.search(text):
        raise EventNarrativeValidationError("event.fact_unsupported")
    for match in _EXPLICIT_ROLE_NUMBER.finditer(text):
        values = _numbers(match["value"])
        permitted = actual if match["role"].casefold() in {"실제", "actual"} else forecast
        if values & (actual | forecast) and not values <= permitted | context_numbers:
            raise EventNarrativeValidationError("event.fact_unsupported")


def _covers(outer: EvidenceRef, inner: EvidenceRef) -> bool:
    return (outer.document_id, outer.revision_id, outer.field) == (
        inner.document_id,
        inner.revision_id,
        inner.field,
    ) and outer.start <= inner.start < inner.end <= outer.end


def _validate_narrative(
    narrative: EventNarrative,
    event: EventCandidate,
    lookup: dict[tuple[str, str], EvidenceDocument],
) -> None:
    for text in (narrative.headline, narrative.what_happened):
        _plain(text)
    first = first_event_sentence(narrative)
    if (
        _GENERIC.search(narrative.what_happened)
        or bound_at_sentence(narrative.what_happened, 240, require_complete=True)
        != narrative.what_happened
    ):
        raise EventNarrativeValidationError("event.narrative_invalid")
    allowed = set(event.evidence_refs)
    source_refs = set(narrative.source_refs)
    if len(source_refs) != len(narrative.source_refs) or not source_refs <= allowed:
        raise EventNarrativeValidationError("event.evidence_invalid")
    for ref in source_refs:
        _resolve(ref, lookup)
    facts = {fact.fact_id: fact for fact in event.change_facts}
    if (
        len(set(narrative.fact_ids)) != len(narrative.fact_ids)
        or not set(narrative.fact_ids) <= facts.keys()
        or not set(event.required_fact_ids) <= set(narrative.fact_ids)
    ):
        raise EventNarrativeValidationError("event.fact_unsupported")
    claims = [facts[fact_id] for fact_id in narrative.fact_ids]
    if (
        not {
            *event.actor_refs,
            *event.action_refs,
            *event.object_refs,
            *(fact.evidence_ref for fact in claims),
        }
        <= source_refs
    ):
        raise EventNarrativeValidationError("event.evidence_invalid")
    for fact in claims:
        if fact.value_text != _resolve(fact.evidence_ref, lookup):
            raise EventNarrativeValidationError("event.fact_unsupported")
        doc = lookup[(fact.evidence_ref.document_id, fact.evidence_ref.revision_id)]
        corpus = " ".join((doc.title, doc.summary, doc.detail_excerpt))
        if any(label is not None and label not in corpus for label in (fact.period, fact.unit)):
            raise EventNarrativeValidationError("event.fact_unsupported")
    actor_values = [_resolve(ref, lookup) for ref in event.actor_refs]
    object_values = [_resolve(ref, lookup) for ref in event.object_refs]
    for values in (actor_values, object_values):
        if values and not any(_mentions(first, value) for value in values):
            raise EventNarrativeValidationError("event.entity_unsupported")
    factual_source = " ".join(
        [*actor_values, *object_values]
        + [" ".join((fact.value_text, fact.period or "", fact.unit or "")) for fact in claims]
    )
    _check_numbers(narrative.headline + " " + narrative.what_happened, factual_source)
    context_numbers = _numbers(
        " ".join(
            [*actor_values, *object_values]
            + [" ".join((fact.period or "", fact.unit or "")) for fact in claims]
        )
    )
    for text in (narrative.headline, narrative.what_happened):
        _check_fact_roles(text, claims, context_numbers)
    identity_values = {
        _normal(_resolve(ref, lookup))
        for ref in (*event.actor_refs, *event.action_refs, *event.object_refs)
    }
    for field in (narrative.meaning, narrative.reaction):
        refs = set(field.evidence_refs)
        if len(refs) != len(field.evidence_refs) or not refs <= source_refs:
            raise EventNarrativeValidationError("event.evidence_invalid")
        if field.text is None:
            continue
        _plain(field.text)
        source = " ".join(_resolve(ref, lookup) for ref in field.evidence_refs)
        _check_numbers(field.text, source)
        field_claims = [
            fact for fact in claims if any(_covers(ref, fact.evidence_ref) for ref in refs)
        ]
        _check_fact_roles(
            field.text,
            field_claims,
            _numbers(" ".join((fact.period or "") for fact in field_claims)),
        )
        if not any(_normal(_resolve(ref, lookup)) not in identity_values for ref in refs):
            raise EventNarrativeValidationError("event.evidence_invalid")
    if narrative.meaning.mode == "conditional" and not _CONDITIONAL.search(
        narrative.meaning.text or ""
    ):
        raise EventNarrativeValidationError("event.narrative_invalid")
    reaction_source = " ".join(_resolve(ref, lookup) for ref in narrative.reaction.evidence_refs)
    if narrative.reaction.status == "observed" and not _REACTION.search(reaction_source):
        raise EventNarrativeValidationError("event.evidence_invalid")
    if narrative.reaction.status == "source_reported_no_reaction" and not (
        _NO_REACTION.search(reaction_source) and _NO_REACTION.search(narrative.reaction.text or "")
    ):
        raise EventNarrativeValidationError("event.evidence_invalid")


def validate_event_payload(payload: EventGenerationPayload) -> None:
    """Check exact ordered event membership and field-local source ownership."""
    try:
        # model_copy intentionally skips validation; never trust that shortcut
        # across a generation/publication boundary.
        raw = payload.model_dump(warnings="error")
        checked = EventGenerationPayload.model_validate(raw)
        if checked.model_dump(mode="json") != payload.model_dump(mode="json", warnings="error"):
            raise ValueError("noncanonical event payload")
    except (ValidationError, ValueError, TypeError):
        raise EventNarrativeValidationError("event.narrative_invalid") from None
    if tuple(n.event_id for n in checked.narratives) != tuple(
        event.event_id for event in checked.plan.selected
    ):
        raise EventNarrativeValidationError("event.selection_mismatch")
    lookup = _lookup(checked)
    for doc in checked.plan.evidence_documents:
        if doc.url is not None:
            try:
                parsed = urlsplit(doc.url)
            except ValueError:
                raise EventNarrativeValidationError("event.evidence_invalid") from None
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or re.search(r"[\s<>]", doc.url)
            ):
                raise EventNarrativeValidationError("event.evidence_invalid")
    for narrative, event in zip(checked.narratives, checked.plan.selected, strict=True):
        _validate_narrative(narrative, event, lookup)


def _escape(text: str) -> str:
    text = html.escape(" ".join(text.split()), quote=False)
    return re.sub(r"([\\`*_[\]])", r"\\\1", text)


def _render_event(
    narrative: EventNarrative,
    event: EventCandidate,
    lookup: dict[tuple[str, str], EvidenceDocument],
) -> str:
    actors = ", ".join(dict.fromkeys(_resolve(ref, lookup) for ref in event.actor_refs))
    objects = ", ".join(dict.fromkeys(_resolve(ref, lookup) for ref in event.object_refs))
    subject = _escape(actors) + (f"; 대상: {_escape(objects)}" if objects else "")
    docs = [
        lookup[key]
        for key in sorted({(r.document_id, r.revision_id) for r in narrative.source_refs})
    ]
    if event.effective_date is None or event.timing == "unknown":
        timing = f"보도 기준 {event.published_at:%Y-%m-%d %H:%M} UTC; 사건 시점 미확인"
    else:
        exact = [doc.event_time for doc in docs if isinstance(doc.event_time, datetime)]
        timing = (
            f"{min(exact):%Y-%m-%d %H:%M} UTC (출처 시각)"
            if exact
            else f"{event.effective_date.isoformat()} (출처 날짜)"
        )
    required = set(event.required_fact_ids)
    fact_values: list[str] = []
    for fact in event.change_facts:
        if fact.fact_id not in required:
            continue
        labels = [_STATUS[fact.status]]
        if fact.period:
            labels.append(f"기간 {fact.period}")
        if fact.unit:
            labels.append(f"단위 {fact.unit}")
        fact_values.append(f"[{_escape(', '.join(labels))}] {_escape(fact.value_text)}")
    links: list[str] = []
    for doc in docs:
        label = _escape(doc.source_name)
        if doc.url is None:
            links.append(f"{label} (URL 미제공)")
        else:
            locator = quote(doc.url, safe=":/?#[]@!$&'*,;=%+-._~")
            links.append(f"[{label}]({locator})")
    return "\n".join(
        (
            f"<!-- investo:block event:{event.event_id} -->",
            f"### {_escape(narrative.headline)}",
            f"- 시점: {timing}",
            f"- 주체: {subject}",
            f"- 무슨 일이 있었나: {_escape(narrative.what_happened)}",
            "- 결정/실적/발표 내용: "
            + ("; ".join(fact_values) or "세부설명은 원문 확인이 필요합니다."),
            f"- 의미: {_escape(narrative.meaning.text or MEANING_UNAVAILABLE)}",
            f"- 시장 반응: {_escape(narrative.reaction.text or REACTION_UNAVAILABLE)}",
            "- 출처: " + ", ".join(dict.fromkeys(links)),
            f"<!-- /investo:block event:{event.event_id} -->",
        )
    )


def render_event_blocks(
    payload: EventGenerationPayload,
    *,
    surviving_event_ids: Sequence[str] | None = None,
) -> str:
    """Render canonical owned children of section 2 in original selected order."""
    validate_event_payload(payload)
    ids = tuple(event.event_id for event in payload.plan.selected)
    surviving = ids if surviving_event_ids is None else tuple(surviving_event_ids)
    if surviving != tuple(event_id for event_id in ids if event_id in set(surviving)):
        raise EventNarrativeValidationError("event.selection_mismatch")
    if not surviving:
        note = (
            NO_SURVIVING_EVENTS
            if ids
            else COLLECTION_LIMITED_EVENTS
            if payload.collection_limited
            else NO_SELECTED_EVENTS
        )
        return f"{EVENTS_MARKER}\n\n{note}"
    lookup = _lookup(payload)
    blocks = [
        _render_event(narrative, event, lookup)
        for narrative, event in zip(payload.narratives, payload.plan.selected, strict=True)
        if event.event_id in surviving
    ]
    return EVENTS_MARKER + "\n\n" + "\n\n".join(blocks)


def event_summary_lines(
    payload: EventGenerationPayload,
    *,
    surviving_event_ids: Sequence[str] | None = None,
) -> tuple[str, str, str]:
    """One B6 content policy for the generation header and terminal summary."""
    validate_event_payload(payload)
    ids = tuple(event.event_id for event in payload.plan.selected)
    surviving = ids if surviving_event_ids is None else tuple(surviving_event_ids)
    if surviving != tuple(event_id for event_id in ids if event_id in set(surviving)):
        raise EventNarrativeValidationError("event.selection_mismatch")
    narratives = [narrative for narrative in payload.narratives if narrative.event_id in surviving]
    if not narratives:
        conclusion = (
            NO_SURVIVING_EVENTS
            if ids
            else COLLECTION_LIMITED_EVENTS
            if payload.collection_limited
            else NO_SELECTED_EVENTS
        )
        return conclusion, MEANING_UNAVAILABLE, "추가 발표 여부는 공식 자료에서 확인이 필요합니다."
    conclusion = first_event_sentence(narratives[0])
    if len(narratives) > 1:
        driver = first_event_sentence(narratives[1])
    elif narratives[0].reaction.text is not None:
        reaction = bound_at_sentence(narratives[0].reaction.text, 90, require_complete=True)
        driver = (
            reaction
            if reaction and not is_unsafe_summary_value(reaction)
            else "확인된 시장 반응은 사건 본문에서 확인할 수 있습니다."
        )
    else:
        driver = REACTION_UNAVAILABLE
    caution = (
        COLLECTION_LIMITED_EVENTS
        if payload.collection_limited
        else "일부 사건의 시장 반응은 확인하지 못했습니다."
        if any(narrative.reaction.status == "unavailable" for narrative in narratives)
        else "수집된 근거만으로 다음 확인 일정을 특정하기 어렵습니다."
    )
    return conclusion, driver, caution
