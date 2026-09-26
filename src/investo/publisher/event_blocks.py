"""Event identities and content reconciliation inside the existing section ②.

There is no second layout/finalizer here. The caller owns phase ordering,
hard-gate snapshots and reindexing; these helpers only inspect or reduce text.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from investo._internal.briefing_extract import CAUTION_PREFIX, CONCLUSION_PREFIX, DRIVER_PREFIX
from investo._internal.event_rendering import (
    COLLECTION_LIMITED_EVENTS,
    MEANING_UNAVAILABLE,
    NO_SELECTED_EVENTS,
    NO_SURVIVING_EVENTS,
    REACTION_UNAVAILABLE,
    render_event_blocks,
    validate_event_payload,
)
from investo._internal.text import bound_at_sentence
from investo.models.event_narratives import EventGenerationPayload
from investo.models.public_notification import PublicEventSummary

_BLOCK = re.compile(
    r"<!-- investo:block event:([0-9a-f]{24}) -->\n(.*?)"
    r"<!-- /investo:block event:\1 -->",
    re.DOTALL,
)
_MARKER = re.compile(r"<!-- /?investo:block event:([^>]*?) -->")
_SECTION = re.compile(r"(?m)^## ② 전일 핵심 이슈[ \t]*\n(.*?)(?=^## |\Z)", re.DOTALL)
_URL = re.compile(r"\]\((https?://[^\s<>]+?)\)")
_SOURCE_LINK = re.compile(r"\[([^\]\n]*)\]\((https?://[^\s<>]+?)\)")
_TLDR = re.compile(r"(?m)(^## 한눈에 보기[ \t]*\n)(.*?)(?=^## |\Z)", re.DOTALL)
_FACT_PREFIX = "결정/실적/발표 내용:"
_WHAT_PREFIX = "무슨 일이 있었나:"
_SOURCE_PREFIX = "출처:"
_EVENT_HARD_CODES = frozenset(
    {"event.fact_unsupported", "event.entity_unsupported", "event.evidence_invalid"}
)


@dataclass(frozen=True, slots=True)
class TerminalEvent:
    event_id: str
    headline: str
    what_happened: str
    first_sentence: str
    reaction: str
    coverage: Literal["supported", "detail_limited"]

    def notification_summary(self) -> PublicEventSummary:
        return PublicEventSummary(
            event_id=self.event_id,
            headline=self.headline,
            fact_summary=bound_at_sentence(self.what_happened, 180, require_complete=True)
            or self.first_sentence,
            coverage=self.coverage,
        )


def _section(markdown: str) -> str:
    match = _SECTION.search(markdown)
    return match.group(1) if match else ""


def _lines(body: str) -> tuple[str, ...]:
    return tuple(event_plain_text(line) for line in body.splitlines() if line.strip())


def event_plain_text(text: str) -> str:
    """Decode the canonical event renderer without erasing literal name tokens."""
    text = re.sub(r"^(?:- |### )", "", text.strip())
    text = re.sub(r"(?<!\\)\*\*(.*?)(?<!\\)\*\*", r"\1", text)
    return html.unescape(re.sub(r"\\([\\`*_\[\]])", r"\1", text))


def _summary_markdown(text: str) -> str:
    return re.sub(r"([\\`*_\[\]])", r"\\\1", html.escape(text, quote=False))


def _same_or_truncated_link(actual: tuple[str, str], expected: tuple[str, str]) -> bool:
    if actual == expected:
        return True
    label, locator = actual
    expected_label, expected_locator = expected
    if label != expected_label:
        return False
    suffix = "..." if locator.endswith("...") else "…" if locator.endswith("…") else ""
    if not suffix:
        return False
    prefix = locator[: -len(suffix)]
    try:
        same_host = urlsplit(locator).netloc == urlsplit(expected_locator).netloc
    except ValueError:
        return False
    return same_host and expected_locator.startswith(prefix) and prefix != expected_locator


def _field(lines: Sequence[str], prefix: str) -> str:
    return next(
        (line.removeprefix(prefix).strip() for line in lines if line.startswith(prefix)), ""
    )


def _first_sentence(text: str) -> str:
    for end, char in enumerate(text[:80], 1):
        if char in ".!?。":
            sentence = bound_at_sentence(text, end, require_complete=True)
            if sentence is not None:
                return sentence
    return ""


def _expected_blocks(payload: EventGenerationPayload) -> dict[str, str]:
    return {
        match.group(1): match.group(2) for match in _BLOCK.finditer(render_event_blocks(payload))
    }


def event_hard_issue_codes(markdown: str, payload: EventGenerationPayload) -> tuple[str, ...]:
    """Preserve unsupported structured claims before any editorial deletion."""
    try:
        validate_event_payload(payload)
        expected = _expected_blocks(payload)
    except ValueError as exc:
        code = next((code for code in sorted(_EVENT_HARD_CODES) if code in str(exc)), None)
        return (code or "event.narrative_invalid",)
    codes: set[str] = set()
    section = _section(markdown)
    blocks = tuple(_BLOCK.finditer(section))
    ids = tuple(match.group(1) for match in blocks)
    if len(set(ids)) != len(ids) or not set(ids) <= set(expected):
        codes.add("event.evidence_invalid")
    if ids != tuple(event_id for event_id in expected if event_id in ids):
        codes.add("event.evidence_invalid")
    # A marker outside ②, malformed marker, or duplicate identity is never
    # accepted as another independently owned mutation region.
    if len(_MARKER.findall(markdown)) != 2 * len(blocks):
        codes.add("event.evidence_invalid")
    for match in blocks:
        original = expected.get(match.group(1))
        if original is None:
            continue
        actual_lines, expected_lines = _lines(match.group(2)), _lines(original)
        for prefix, code in (
            ("주체:", "event.entity_unsupported"),
            (_FACT_PREFIX, "event.fact_unsupported"),
            ("시점:", "event.evidence_invalid"),
            (_WHAT_PREFIX, "event.fact_unsupported"),
            ("의미:", "event.evidence_invalid"),
            ("시장 반응:", "event.evidence_invalid"),
        ):
            allowed = {line for line in expected_lines if line.startswith(prefix)}
            if any(line not in allowed for line in actual_lines if line.startswith(prefix)):
                codes.add(code)
        expected_titles = {
            event_plain_text(line) for line in original.splitlines() if line.startswith("### ")
        }
        if any(
            event_plain_text(line) not in expected_titles
            for line in match.group(2).splitlines()
            if line.startswith("### ")
        ):
            codes.add("event.entity_unsupported")
        allowed_links = set(_SOURCE_LINK.findall(original))
        if any(
            not any(_same_or_truncated_link(link, original_link) for original_link in allowed_links)
            for link in _SOURCE_LINK.findall(match.group(2))
        ):
            codes.add("event.evidence_invalid")
        # A removed link may leave its original label. New labels or prose
        # cannot acquire a source's authority merely by retaining its URL.
        labels = {event_plain_text(label) for label, _ in allowed_links}
        for line in match.group(2).splitlines():
            if not line.startswith("- 출처:"):
                continue
            residue = _SOURCE_LINK.sub(lambda found: found.group(1), line.removeprefix("- 출처:"))
            if (
                any(
                    event_plain_text(part) not in labels
                    for part in residue.split(",")
                    if part.strip()
                )
                and event_plain_text(line) not in expected_lines
            ):
                codes.add("event.evidence_invalid")
    return tuple(sorted(codes))


def terminal_events(
    markdown: str,
    payload: EventGenerationPayload,
    *,
    surviving_event_ids: Sequence[str] | None = None,
) -> tuple[TerminalEvent, ...]:
    """Read complete surviving slots from terminal bytes in selected order.

    Missing source locators downgrade an otherwise intact block. Missing
    what/time/actor/required facts/meaning/reaction removes its eligibility;
    a marker or source link alone cannot count as a surviving event.
    """
    expected = _expected_blocks(payload)
    actual = {match.group(1): match.group(2) for match in _BLOCK.finditer(_section(markdown))}
    allowed = set(expected if surviving_event_ids is None else surviving_event_ids)
    events: list[TerminalEvent] = []
    for candidate in payload.plan.selected:
        event_id = candidate.event_id
        if event_id not in allowed or event_id not in actual:
            continue
        original_lines, actual_lines = _lines(expected[event_id]), _lines(actual[event_id])
        required = tuple(line for line in original_lines if not line.startswith(_SOURCE_PREFIX))
        if not all(line in actual_lines for line in required):
            continue
        what = _field(actual_lines, _WHAT_PREFIX)
        first = _first_sentence(what)
        headline = next(
            (
                event_plain_text(line.removeprefix("### "))
                for line in actual[event_id].splitlines()
                if line.startswith("### ")
            ),
            "",
        )
        if not first or not headline or len(headline) > 80:
            continue
        source_urls = set(_URL.findall(actual[event_id]))
        expected_urls = set(_URL.findall(expected[event_id]))
        coverage: Literal["supported", "detail_limited"] = (
            "supported"
            if candidate.evidence_state == "supported"
            and expected_urls
            and expected_urls <= source_urls
            else "detail_limited"
        )
        events.append(
            TerminalEvent(
                event_id, headline, what, first, _field(actual_lines, "시장 반응:"), coverage
            )
        )
    return tuple(events)


def event_empty_message(payload: EventGenerationPayload) -> str:
    if payload.plan.selected:
        return NO_SURVIVING_EVENTS
    if payload.collection_limited:
        return COLLECTION_LIMITED_EVENTS
    return NO_SELECTED_EVENTS


def reconcile_event_summaries(
    markdown: str,
    payload: EventGenerationPayload,
    events: Sequence[TerminalEvent],
) -> str:
    """Replace summary content in place; preserve the existing layout order."""
    conclusion = events[0].first_sentence if events else event_empty_message(payload)
    driver = (
        events[1].first_sentence
        if len(events) > 1
        else bound_at_sentence(events[0].reaction, 90, require_complete=True)
        if events
        else MEANING_UNAVAILABLE
    ) or "확인된 시장 반응은 사건 본문에서 확인할 수 있습니다."
    caution = (
        "추가 발표 여부는 공식 자료에서 확인이 필요합니다."
        if not events
        else COLLECTION_LIMITED_EVENTS
        if payload.collection_limited
        else "일부 사건의 시장 반응은 확인하지 못했습니다."
        if any(event.reaction == REACTION_UNAVAILABLE for event in events)
        else "수집된 근거만으로 다음 확인 일정을 특정하기 어렵습니다."
    )
    values = (conclusion, driver, caution)
    for prefix, value in zip(
        (CONCLUSION_PREFIX, DRIVER_PREFIX, CAUTION_PREFIX), values, strict=True
    ):
        pattern = re.compile(rf"(?m)^{re.escape(prefix)}[^\n]*$")
        replacement = f"{prefix} {_summary_markdown(value)}"
        markdown, count = pattern.subn(replacement.replace("\\", r"\\"), markdown)
        if not count:
            insertion = markdown.find("## 한눈에 보기")
            if insertion < 0:
                insertion = markdown.find("## ① 요약")
            if insertion >= 0:
                markdown = markdown[:insertion] + replacement + "\n" + markdown[insertion:]
    bullets = "\n".join(f"- {_summary_markdown(value)}" for value in values)

    def replace_tldr(match: re.Match[str]) -> str:
        # Callouts/hero may follow the three items before the next H2 (u154's
        # proposed order). Replace only the leading summary paragraph, never
        # consume separately owned preamble blocks with the H2 section body.
        lines = match.group(2).splitlines(keepends=True)
        start = 0
        while start < len(lines) and not lines[start].strip():
            start += 1
        end = start
        while end < len(lines):
            line = lines[end].strip()
            if not line or line.startswith((">", "#", "<", "![", "**기준 시각**")):
                break
            end += 1
        tail = "".join(lines[end:]).lstrip("\n")
        return f"{match.group(1)}\n{bullets}\n\n{tail}"

    markdown, count = _TLDR.subn(replace_tldr, markdown)
    if not count:
        insertion = markdown.find("## ① 요약")
        if insertion >= 0:
            markdown = (
                markdown[:insertion] + f"## 한눈에 보기\n\n{bullets}\n\n" + markdown[insertion:]
            )
    return markdown


def reconcile_event_blocks(
    markdown: str,
    payload: EventGenerationPayload,
    *,
    surviving_event_ids: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    """One monotone repair step: remove incomplete blocks, then dependents."""
    events = terminal_events(markdown, payload, surviving_event_ids=surviving_event_ids)
    ids = tuple(event.event_id for event in events)
    kept = set(ids)
    section = _SECTION.search(markdown)
    if section is not None:
        body = _BLOCK.sub(
            lambda match: match.group(0) if match.group(1) in kept else "", section.group(1)
        )
        if not events:
            body = f"\n<!-- investo:events version=2 -->\n{event_empty_message(payload)}\n\n"
        markdown = markdown[: section.start(1)] + body + markdown[section.end(1) :]
    # Event watchpoint cards are reserved for u162. Honor their explicit
    # identity if present without touching ordinary numeric watchpoint rows.
    for event_id in set(surviving_event_ids) - kept:
        markdown = re.sub(
            rf"<!-- investo:event-watchpoint {event_id} -->.*?"
            rf"<!-- /investo:event-watchpoint {event_id} -->",
            "",
            markdown,
            flags=re.DOTALL,
        )
    return reconcile_event_summaries(markdown, payload, events), ids


__all__ = [
    "TerminalEvent",
    "event_empty_message",
    "event_hard_issue_codes",
    "event_plain_text",
    "reconcile_event_blocks",
    "reconcile_event_summaries",
    "terminal_events",
]
