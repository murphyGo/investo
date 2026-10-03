"""Offline recorded-response event replay; no collection, publication or LLM I/O.

The frozen expectations are authored synthetic annotations. This structural
checker does not award a human semantic score or measure worldwide news recall.
Markdown is imported only when this optional developer replay is executed.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from investo._internal.text import bound_at_sentence
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.fact_context import build_verified_fact_bundle
from investo.briefing.generation_contract import GenerationInput, GenerationResult
from investo.briefing.pipeline import GenerationPolicy, generate_briefing_from_input
from investo.briefing.segments import build_segment_coverage, segment_source_outcomes
from investo.briefing.watchlist import WatchlistConfig
from investo.models import Briefing, NormalizedItem, SourceOutcome
from investo.models.event_quality import EventCoverage, EventStageReceipt
from investo.models.events import EventIdentityReceipt
from investo.models.segments import MarketSegment
from investo.publisher.event_quality import evaluate_event_quality
from investo.publisher.public_document import (
    FinalizedPublicDocument,
    PublicDocumentContext,
    PublicDocumentFinalizationError,
    SegmentInputAbsence,
    finalize_public_bundle,
)

_MAX_FIXTURE_BYTES = 4 * 1024 * 1024
_SAFE_ID = r"^[a-z0-9][a-z0-9_-]{0,79}$"
CaseId = Annotated[str, Field(pattern=_SAFE_ID)]
EventId = Annotated[str, Field(pattern=r"^[0-9a-f]{24}$")]
Mutation = Literal[
    "none", "remove_fact", "remove_link", "marker_only", "url_only", "numeric", "forbidden"
]


class _FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReplayExpectation(_FixtureModel):
    expected_event_ids: tuple[EventId, ...]
    terminal_event_ids: tuple[EventId, ...]
    required_facts: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    allowed_uncertainty: tuple[str, ...]
    selected_expected: int | None
    candidate_visibility: int | None
    expected_public_status: Literal["finalized", "trust_blocked", "generation_absent"]
    qualified_expected: int | None
    expected_calls: int
    expected_exclusions: tuple[str, ...] = ()
    expected_issue_codes: tuple[str, ...] = ()
    expected_state: str | None = None
    expected_omitted: int | None = 0
    expected_reasons: tuple[str, ...] = ()
    expected_novelties: tuple[str, ...] = ()


class ReplayCase(_FixtureModel):
    case_id: CaseId
    scenario_id: CaseId
    expectations: dict[MarketSegment, ReplayExpectation]


class ReplaySegment(_FixtureModel):
    segment: MarketSegment
    items: tuple[NormalizedItem, ...]
    source_outcomes: tuple[SourceOutcome, ...] = ()
    baseline: tuple[EventIdentityReceipt, ...] = ()
    responses: tuple[str, ...]
    mutation: Mutation = "none"


class ReplayRecord(_FixtureModel):
    target_date: date
    observed_at: datetime
    segments: tuple[ReplaySegment, ...]


@dataclass(frozen=True)
class ReplaySegmentResult:
    segment: MarketSegment
    calls: int
    selected: int | None
    terminal: int | None
    qualified: int | None
    summary: int | None
    state: str | None
    codes: tuple[str, ...]


@dataclass(frozen=True)
class ReplayCaseResult:
    scenario_id: str
    case_id: str
    segments: tuple[ReplaySegmentResult, ...]
    codes: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.codes and all(not segment.codes for segment in self.segments)


class RecordedEventRunner:
    """The only runner accepted here returns frozen responses, never subprocesses."""

    def __init__(self, responses: tuple[str, ...]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        index = len(self.prompts)
        if input is None or index >= len(self.responses):
            raise ValueError("replay.response_count")
        self.prompts.append(input)
        return subprocess.CompletedProcess(args, 0, self.responses[index], "")


class _VisibleHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "li", "h1", "h2", "h3", "td", "tr", "br"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "h1", "h2", "h3", "td", "tr"}:
            self.parts.append(" ")


def rendered_html_text(markdown: str) -> str:
    """Use the site's Markdown engine, then read visible text (not comments)."""
    import markdown as markdown_module  # type: ignore[import-untyped]

    parser = _VisibleHTML()
    parser.feed(markdown_module.markdown(markdown, extensions=["tables", "fenced_code"]))
    parser.close()
    return " ".join("".join(parser.parts).split())


def _mutate_generated(briefing: Briefing, mutation: Mutation) -> Briefing:
    if mutation == "none":
        return briefing
    markdown = briefing.rendered_markdown
    if mutation in {"remove_fact", "remove_link"}:
        label = "결정/실적/발표 내용" if mutation == "remove_fact" else "출처"
        markdown = re.sub(rf"(?m)^- {label}:.*\n", "", markdown, count=1)
    elif mutation in {"marker_only", "url_only"}:
        pattern = (
            r"(<!-- investo:block event:[0-9a-f]{24} -->\n)(.*?)"
            r"(<!-- /investo:block event:[0-9a-f]{24} -->)"
        )

        def retained(match: re.Match[str]) -> str:
            source = next(
                (line for line in match[2].splitlines() if line.startswith("- 출처:")), ""
            )
            return match[1] + (source + "\n" if mutation == "url_only" else "") + match[3]

        markdown = re.sub(pattern, retained, markdown, count=1, flags=re.S)
    elif mutation == "numeric":
        markdown = re.sub(
            r"(?m)^- 결정/실적/발표 내용:.*$",
            "- 결정/실적/발표 내용: [실제] 가상기업 매출 99999억 달러를 기록했습니다.",
            markdown,
            count=1,
        )
    elif mutation == "forbidden":
        markdown = markdown.replace(
            "## ① 요약\n", "## ① 요약\n\n수익을 보장합니다. 지금 매수하세요.\n", 1
        )
    return briefing.model_copy(update={"rendered_markdown": markdown})


def _check_document(
    document: FinalizedPublicDocument,
    expected: ReplayExpectation,
    generated: GenerationResult,
) -> set[str]:
    codes: set[str] = set()
    if document.surviving_event_ids != expected.terminal_event_ids:
        codes.add("replay.terminal_identity")
    summary = document.notification_summary
    if tuple(event.event_id for event in summary.events) != expected.terminal_event_ids[:3]:
        codes.add("replay.summary_identity")
    markdown = document.briefing.rendered_markdown
    visible = rendered_html_text(markdown)
    if any(" ".join(fact.split()) not in visible for fact in expected.required_facts):
        codes.add("replay.required_fact_missing")
    public_values = " ".join(
        [visible, summary.conclusion]
        + [f"{event.headline} {event.fact_summary}" for event in summary.events]
    )
    if any(claim in public_values for claim in expected.forbidden_claims):
        codes.add("replay.forbidden_claim")
    if any(value not in visible for value in expected.allowed_uncertainty):
        codes.add("replay.uncertainty_missing")
    if any(event_id in visible for event_id in expected.expected_event_ids):
        codes.add("replay.visible_identity")
    if (
        tuple(receipt.event_id for receipt in document.event_identity_receipts)
        != expected.terminal_event_ids
    ):
        codes.add("replay.sealed_identity")
    payload = generated.event_payload
    if payload is not None:
        by_id = {n.event_id: n for n in payload.narratives}
        for event in summary.events:
            if event.headline != by_id[event.event_id].headline:
                codes.add("replay.summary_value")
            if event.fact_summary != bound_at_sentence(
                by_id[event.event_id].what_happened, 180, require_complete=True
            ):
                codes.add("replay.summary_value")
        if summary.events and summary.conclusion not in visible:
            codes.add("replay.summary_value")
    return codes


async def replay_event_case(case: ReplayCase, record: ReplayRecord) -> ReplayCaseResult:
    """Run real generation/finalization; all external effects are absent by construction."""
    if set(case.expectations) != {entry.segment for entry in record.segments}:
        raise ValueError("replay.segment_identity")
    generated: dict[MarketSegment, GenerationResult] = {}
    inputs = {entry.segment: entry for entry in record.segments}
    runners: dict[MarketSegment, RecordedEventRunner] = {}
    receipts: dict[MarketSegment, tuple[EventStageReceipt, ...]] = {}
    briefings: dict[MarketSegment, Briefing] = {}
    absences: dict[MarketSegment, SegmentInputAbsence] = {}
    for entry in record.segments:
        runner = RecordedEventRunner(entry.responses)
        runners[entry.segment] = runner
        try:
            result = await generate_briefing_from_input(
                GenerationInput(
                    target_date=record.target_date,
                    items=entry.items,
                    source_outcomes=entry.source_outcomes,
                    watchlist_config=WatchlistConfig(),
                    segment=entry.segment,
                    runner=runner,
                    generation_policy=GenerationPolicy(
                        event_mode="preview", timeout_s=1, max_attempts=1, total_budget_s=10
                    ),
                    event_observed_at=record.observed_at,
                    event_baseline=entry.baseline,
                )
            )
        except BriefingGenerationError as exc:
            receipts[entry.segment] = exc.event_stage_receipts
            absences[entry.segment] = "generation_failed"
            continue
        receipts[entry.segment] = result.event_stage_receipts
        generated[entry.segment] = result
        briefings[entry.segment] = _mutate_generated(result.briefing, entry.mutation)
    documents: dict[MarketSegment, FinalizedPublicDocument] = {}
    hard: dict[MarketSegment, tuple[str, ...]] = {}
    if briefings:
        all_items = tuple(item for entry in record.segments for item in entry.items)
        context = PublicDocumentContext(
            target_date=record.target_date,
            expected_segments=tuple(inputs),
            input_absences=absences,
            items_by_segment={segment: inputs[segment].items for segment in briefings},
            anchors_by_segment={},
            coverage_by_segment={
                segment: build_segment_coverage(
                    segment,
                    inputs[segment].items,
                    source_outcomes=segment_source_outcomes(
                        segment, inputs[segment].source_outcomes
                    ),
                )
                for segment in briefings
            },
            source_outcomes=tuple(
                outcome for entry in record.segments for outcome in entry.source_outcomes
            ),
            bundle_context=None,
            fact_bundle=build_verified_fact_bundle(
                all_items, record.target_date, record.observed_at
            ),
            entity_observed_at_utc=record.observed_at,
            event_payloads_by_segment={
                segment: result.event_payload
                for segment, result in generated.items()
                if result.event_payload is not None
            },
        )
        try:
            bundle = finalize_public_bundle(briefings, context=context)
        except PublicDocumentFinalizationError as exc:
            if len(briefings) != 1:
                raise ValueError("replay.bundle_failed") from None
            hard[next(iter(briefings))] = exc.issue_codes
        else:
            documents = {document.segment: document for document in bundle.documents}
            hard = {
                outcome.segment: outcome.issue_codes
                for outcome in bundle.segment_outcomes
                if outcome.state == "trust_blocked"
            }
    results: list[ReplaySegmentResult] = []
    for segment, expected in case.expectations.items():
        codes: set[str] = set()
        generation = generated.get(segment)
        payload = generation.event_payload if generation is not None else None
        document = documents.get(segment)
        quality: EventCoverage = evaluate_event_quality(
            document,
            payload=payload,
            receipts=receipts[segment],
            hard_issue_codes=hard.get(segment, ()),
        )
        status = (
            "finalized" if document else "trust_blocked" if segment in hard else "generation_absent"
        )
        if status != expected.expected_public_status:
            codes.add("replay.public_status")
        if len(runners[segment].prompts) != expected.expected_calls:
            codes.add("replay.call_count")
        if quality.selected_count != expected.selected_expected:
            codes.add("replay.selected_count")
        if quality.collected_candidate_count != expected.candidate_visibility:
            codes.add("replay.candidate_visibility")
        if quality.qualified_event_count != expected.qualified_expected:
            codes.add("replay.qualified_count")
        terminal_expected = len(expected.terminal_event_ids) if document else None
        if quality.terminal_event_count != terminal_expected:
            codes.add("replay.terminal_count")
        summary_expected = min(terminal_expected, 3) if terminal_expected is not None else None
        if quality.summary_event_count != summary_expected:
            codes.add("replay.summary_count")
        if quality.omitted_count != expected.expected_omitted:
            codes.add("replay.omitted_count")
        if not set(expected.expected_reasons) <= set(quality.reasons):
            codes.add("replay.coverage_reason")
        if expected.expected_state is not None and quality.state != expected.expected_state:
            codes.add("replay.coverage_state")
        if expected.selected_expected in (0, None) and (
            quality.selection_coverage is not None or quality.qualified_coverage is not None
        ):
            codes.add("replay.false_zero_ratio")
        observed = tuple(event.event_id for event in payload.plan.selected) if payload else ()
        if observed != expected.expected_event_ids:
            codes.add("replay.selected_identity")
        if payload is not None:
            if (
                expected.expected_novelties
                and tuple(event.novelty for event in payload.plan.selected)
                != expected.expected_novelties
            ):
                codes.add("replay.novelty")
            exclusions = {entry.reason for entry in payload.plan.excluded}
            if not set(expected.expected_exclusions) <= exclusions:
                codes.add("replay.exclusion_reason")
            prompts = runners[segment].prompts
            if observed and (
                len(prompts) < 2 or any(event_id not in prompts[1] for event_id in observed)
            ):
                codes.add("replay.protected_input")
        if not set(expected.expected_issue_codes) <= set(hard.get(segment, ())):
            codes.add("replay.hard_finding")
        if document is not None and generation is not None:
            codes.update(_check_document(document, expected, generation))
        results.append(
            ReplaySegmentResult(
                segment,
                len(runners[segment].prompts),
                quality.selected_count,
                quality.terminal_event_count,
                quality.qualified_event_count,
                quality.summary_event_count,
                quality.state,
                tuple(sorted(codes)),
            )
        )
    return ReplayCaseResult(case.scenario_id, case.case_id, tuple(results), ())


def load_event_replay(path: Path) -> tuple[tuple[ReplayCase, ReplayRecord], ...]:
    """Read only one pinned sibling recording; no arbitrary fixture path traversal."""
    with path.open("rb") as stream:
        raw = stream.read(_MAX_FIXTURE_BYTES + 1)
    if len(raw) > _MAX_FIXTURE_BYTES:
        raise ValueError("replay.manifest_size")
    manifest = json.loads(raw)
    if (
        manifest.get("schema_version") != 1
        or manifest.get("fixture_author") != "AI-authored synthetic"
        or manifest.get("human_review") != "pending"
        or manifest.get("input_recording") != "records.json"
        or len(manifest.get("scenarios", ())) != 12
        or len(manifest.get("output_inventory", ())) != 18
    ):
        raise ValueError("replay.manifest_contract")
    with (path.parent / "records.json").open("rb") as stream:
        recording = stream.read(_MAX_FIXTURE_BYTES + 1)
    if len(recording) > _MAX_FIXTURE_BYTES or hashlib.sha256(recording).hexdigest() != manifest.get(
        "input_recording_sha256"
    ):
        raise ValueError("replay.recording_identity")
    records = json.loads(recording)
    cases = tuple(ReplayCase.model_validate(case) for case in manifest["cases"])
    if len({case.case_id for case in cases}) != len(cases) or {
        case.case_id for case in cases
    } != set(records):
        raise ValueError("replay.case_identity")
    if {case.scenario_id for case in cases} != {
        scenario["scenario_id"] for scenario in manifest["scenarios"]
    }:
        raise ValueError("replay.scenario_identity")
    return tuple((case, ReplayRecord.model_validate(records[case.case_id])) for case in cases)


async def replay_event_manifest(path: Path) -> tuple[ReplayCaseResult, ...]:
    results: list[ReplayCaseResult] = []
    for case, record in load_event_replay(path):
        try:
            results.append(await replay_event_case(case, record))
        except Exception:
            # Never expose Pydantic input values, source spans, prompts or model
            # responses through the CLI result channel, including failing cases.
            results.append(
                ReplayCaseResult(case.scenario_id, case.case_id, (), ("replay.execution_failed",))
            )
    return tuple(results)
