"""Exercise versioned event generation through the existing two-stage runner seam."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo._internal.codex_auth import write_auth
from investo._internal.llm_config import LlmExecutionConfig
from investo.briefing._core.orchestration import GenerationPolicy
from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.codex_cli import CodexRunner
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_evidence import (
    build_event_candidates,
    make_evidence_document,
    prepare_evidence_documents,
)
from investo.briefing.event_selection import select_events
from investo.briefing.generation_contract import GenerationInput, GenerationResult
from investo.briefing.pipeline import generate_briefing, generate_briefing_from_input
from investo.briefing.private_claude import PrivateClaudeRunner
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.briefing.watchlist import WatchlistConfig
from investo.models import NormalizedItem
from investo.models.event_config import EventMode
from investo.models.event_narratives import (
    EventMeaning,
    EventNarrative,
    EventReaction,
    Stage2OutputV2,
    Stage2Sections,
)
from investo.models.events import EventCandidateDraft, EventFactDraft, EvidenceDocument, EvidenceRef
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown

_TARGET = date(2026, 9, 21)
_OBSERVED = datetime(2026, 9, 22, 6, tzinfo=UTC)
_FACT = "매출 123.45억 달러를 기록했습니다."
_FIRST_SENTENCE = "Acme는 분기 매출 123.45억 달러를 발표했습니다."
_RAW_ERROR = "RAW_EVENT_RESPONSE_MUST_NOT_ESCAPE"


@dataclass(frozen=True)
class _Case:
    item: NormalizedItem
    document: EvidenceDocument
    classification: str
    synthesis: str
    event_id: str
    fact_id: str


def _reference(document: EvidenceDocument, text: str, field: str = "title") -> EvidenceRef:
    start = getattr(document, field).index(text)
    return EvidenceRef.model_validate(
        {
            "document_id": document.document_id,
            "revision_id": document.revision_id,
            "field": field,
            "start": start,
            "end": start + len(text),
        }
    )


def _case() -> _Case:
    original = make_evidence_document(
        source_name="fixture-official",
        title="Acme 분기 실적 발표",
        summary="분기 실적을 공식 발표했습니다. 발표 기준일은 2026-09-21입니다.",
        # The amount is deliberately beyond the legacy summary budget and
        # exists only in the separately transmitted evidence excerpt.
        detail_excerpt="공식 발표에 포함된 사업 설명입니다. " * 20 + _FACT,
        url="https://example.invalid/earnings-release",
        published_at=datetime(2026, 9, 21, 18, tzinfo=UTC),
        received_at=_OBSERVED,
        event_time=_TARGET,
        event_time_basis="source_date",
        source_tier="official",
    )
    item = NormalizedItem(
        source_name=original.source_name,
        category="news",
        title=original.title,
        summary=original.summary,
        url=original.url,
        published_at=original.published_at,
        event_evidence=original,
    )
    document = prepare_evidence_documents([item], received_at=_OBSERVED)[0]
    fact_ref = _reference(document, _FACT, "detail_excerpt")
    proposal = EventCandidateDraft(
        item_ids=(1,),
        event_kind="earnings_result",
        actor_refs=(_reference(document, "Acme"),),
        action_refs=(_reference(document, "실적 발표"),),
        relation_refs=(fact_ref,),
        impact_refs=(fact_ref,),
        timing="announced",
        relation="direct",
        impact="company",
        facts=(EventFactDraft(predicate="result", evidence_ref=fact_ref, unit="달러"),),
    )
    candidates = build_event_candidates([proposal], [item], [document], observed_at=_OBSERVED)
    plan = select_events(
        candidates,
        [document],
        segment="us-equity",
        window_start=datetime(2026, 9, 21, 4, tzinfo=UTC),
        window_end=datetime(2026, 9, 22, 4, tzinfo=UTC),
    )
    (event,) = plan.selected
    output = Stage2OutputV2(
        schema_version=2,
        sections=Stage2Sections(
            market_summary="공식 발표에서 확인한 사업 실적을 살펴봅니다.",
            sector_flow="섹터 전체의 수급 자료는 확인하지 못했습니다.",
            indicators_events="추가로 확정된 일정은 확인하지 못했습니다.",
            notable_tickers="Acme의 공식 실적 발표가 확인됐습니다.",
            today_watch="후속 공식 발표의 사업 설명을 확인할 필요가 있습니다.",
        ),
        events=(
            EventNarrative(
                event_id=event.event_id,
                headline="Acme 분기 실적 발표",
                what_happened=_FIRST_SENTENCE,
                fact_ids=event.required_fact_ids,
                source_refs=event.evidence_refs,
                meaning=EventMeaning(text=None, mode="unavailable"),
                reaction=EventReaction(text=None, status="unavailable"),
            ),
        ),
    )
    return _Case(
        item=item,
        document=document,
        classification=json.dumps(
            {
                "schema_version": 2,
                "assignments": {"1": 2},
                "unassigned": [],
                "events": [proposal.model_dump(mode="json")],
            },
            ensure_ascii=False,
        ),
        synthesis=output.model_dump_json(),
        event_id=event.event_id,
        fact_id=event.required_fact_ids[0],
    )


def _request(case: _Case, runner: ClaudeRunner, *, mode: EventMode = "preview") -> GenerationInput:
    return GenerationInput(
        target_date=_TARGET,
        items=[case.item],
        segment="us-equity",
        watchlist_config=WatchlistConfig(),
        runner=runner,
        generation_policy=GenerationPolicy(
            event_mode=mode, timeout_s=3, max_attempts=2, total_budget_s=30
        ),
        event_observed_at=_OBSERVED,
    )


class _ReplayRunner:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = iter(outputs)
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
        assert input is not None
        self.prompts.append(input)
        return subprocess.CompletedProcess(args, 0, next(self.outputs), _RAW_ERROR)


def _subprocess_runner(
    tmp_path: Path, provider: str, responses: list[str]
) -> PrivateClaudeRunner | CodexRunner:
    counter = tmp_path / "calls"
    body = (
        f"counter=Path({str(counter)!r})\n"
        "n=int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n+1))\n"
        f"Path({str(tmp_path)!r}, f'prompt-{{n}}.txt').write_text(prompt)\n"
        f"output={responses!r}[n]\n"
    )
    if provider == "codex":
        auth_home = tmp_path / "auth"
        auth_home.mkdir(mode=0o700)
        write_auth(
            auth_home / "auth.json",
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "OPENAI_API_KEY": None,
                    "tokens": {
                        key: f"synthetic-{key}"
                        for key in ("access_token", "refresh_token", "id_token", "account_id")
                    },
                }
            ).encode(),
        )
        binary = tmp_path / "codex"
        binary.write_text(
            f"#!{sys.executable}\nimport sys, json\nfrom pathlib import Path\n"
            "if '--version' in sys.argv:\n"
            " print('codex-cli 0.153.4'); sys.exit(0)\n"
            "prompt=sys.stdin.read()\n"
            + body
            + "Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(output)\n"
            "print(json.dumps({'type':'item.completed',"
            "'item':{'type':'agent_message','text':output}}))\n"
            "print(json.dumps({'type':'turn.completed'}))\n"
        )
        binary.chmod(0o700)
        return CodexRunner(
            LlmExecutionConfig("codex", "synthetic-model"),
            auth_home,
            deadline=time.monotonic() + 30,
            binary=str(binary),
        )
    binary = tmp_path / "claude"
    binary.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
        "prompt=sys.stdin.read()\n" + body + "print(output)\n"
    )
    binary.chmod(0o700)
    return PrivateClaudeRunner(str(binary), sys.executable, "synthetic-event-claude")


def _assert_event_result(result: GenerationResult, case: _Case) -> None:
    assert result.event_payload is not None
    assert result.event_plan == result.event_payload.plan
    assert [event.event_id for event in result.event_plan.selected] == [case.event_id]
    assert result.event_payload.narratives[0].fact_ids == (case.fact_id,)
    assert result.event_plan.evidence_documents[0].received_at == _OBSERVED
    markdown = result.briefing.rendered_markdown
    assert all(markdown.count(header) == 1 for header in STAGE2_SECTION_HEADERS)
    assert _FACT in result.briefing.key_issues
    assert "[fixture-official](https://example.invalid/earnings-release)" in markdown
    assert f"<!-- investo:block event:{case.event_id} -->" in result.briefing.key_issues
    assert "시장 반응은 확인하지 못했습니다." in result.briefing.key_issues
    header = markdown.split(STAGE2_SECTION_HEADERS[0], 1)[0]
    assert f"> **오늘의 결론**: {_FIRST_SENTENCE}\n" in header
    assert "investo:" not in header and case.event_id not in header
    assert "수치 검증 경고" not in header
    assert "123.45" not in case.item.title + (case.item.summary or "")
    assert case.document.detail_excerpt.index(_FACT) > 320


@pytest.mark.parametrize("provider", ["claude", "codex"])
async def test_v2_classification_and_json_synthesis_use_exactly_two_provider_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setattr("investo.models.event_config.EVENT_PREVIEW_READY", True)
    case = _case()
    runner = _subprocess_runner(tmp_path, provider, [case.classification, case.synthesis])
    try:
        result = await generate_briefing_from_input(_request(case, runner))
    finally:
        runner.close()
    assert (tmp_path / "calls").read_text() == "2"
    stage1 = (tmp_path / "prompt-0.txt").read_text()
    stage2 = (tmp_path / "prompt-1.txt").read_text()
    assert case.document.revision_id in stage1
    assert case.document.detail_excerpt in stage1
    assert case.event_id in stage2 and case.fact_id in stage2
    assert _FACT in stage2
    assert "schema_version" in stage2 and "JSON" in stage2
    _assert_event_result(result, case)


@pytest.mark.parametrize("provider", ["claude", "codex"])
async def test_invalid_stage2_retries_same_provider_with_only_closed_json_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    provider: str,
) -> None:
    monkeypatch.setattr("investo.models.event_config.EVENT_PREVIEW_READY", True)

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr("investo.briefing._core.orchestration.asyncio.sleep", no_sleep)
    case = _case()
    invalid = json.loads(case.synthesis)
    invalid["events"][0]["fact_ids"] = []
    invalid["events"][0]["what_happened"] = _RAW_ERROR + "."
    runner = _subprocess_runner(
        tmp_path, provider, [case.classification, json.dumps(invalid), case.synthesis]
    )
    try:
        result = await generate_briefing_from_input(_request(case, runner))
    finally:
        runner.close()
    assert (tmp_path / "calls").read_text() == "3"
    first = (tmp_path / "prompt-1.txt").read_text()
    retry = (tmp_path / "prompt-2.txt").read_text()
    assert retry.startswith(first)
    feedback = retry[len(first) :]
    assert "schema_version=2 JSON object" in feedback
    assert "selected events in order" in feedback
    assert "Markdown outside JSON" in feedback
    assert "Validation code: event.fact_unsupported" in feedback
    assert "first non-empty line MUST" not in feedback
    assert _RAW_ERROR not in retry + caplog.text
    _assert_event_result(result, case)


@pytest.mark.parametrize("invalid_kind", ["schema", "markdown", "semantic"])
async def test_exhausted_v2_retry_has_no_raw_output_or_v1_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    invalid_kind: str,
) -> None:
    monkeypatch.setattr("investo.models.event_config.EVENT_PREVIEW_READY", True)

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr("investo.briefing._core.orchestration.asyncio.sleep", no_sleep)
    case = _case()
    if invalid_kind == "schema":
        payload = json.loads(case.synthesis)
        payload["private_unexpected_field"] = _RAW_ERROR
        invalid = json.dumps(payload)
    elif invalid_kind == "markdown":
        invalid = valid_stage2_markdown() + _RAW_ERROR
    else:
        payload = json.loads(case.synthesis)
        payload["events"][0]["what_happened"] = (
            f"Acme는 매출 98765억 달러를 발표했습니다. {_RAW_ERROR}."
        )
        invalid = json.dumps(payload)
    runner = _ReplayRunner([case.classification, invalid, invalid])
    with pytest.raises(BriefingGenerationError) as raised:
        await generate_briefing_from_input(_request(case, runner))
    assert raised.value.stage == "synthesis"
    assert raised.value.attempt_count == 2
    assert len(runner.prompts) == 3
    assert raised.value.last_stdout is None and raised.value.last_stderr is None
    assert str(raised.value.cause).startswith("event.")
    assert _RAW_ERROR not in str(raised.value) + str(raised.value.cause) + caplog.text
    assert _RAW_ERROR not in runner.prompts[-1]
    assert "schema_version=2 JSON object" in runner.prompts[-1]


async def test_off_shadow_and_legacy_api_preserve_v1_prompts_and_output() -> None:
    case = _case()
    captures: list[list[str]] = []
    results: list[GenerationResult] = []
    modes: tuple[EventMode, ...] = ("off", "shadow")
    for mode in modes:
        runner = _ReplayRunner([valid_classification_stdout(1), valid_stage2_markdown()])
        results.append(await generate_briefing_from_input(_request(case, runner, mode=mode)))
        captures.append(runner.prompts)
    assert len(captures[0]) == len(captures[1]) == 2
    assert captures[0] == captures[1]
    assert results[0].briefing.model_dump() == results[1].briefing.model_dump()
    assert all(result.event_plan is None and result.event_payload is None for result in results)
    assert results[0].event_observation is None
    assert results[1].event_observation is not None
    assert results[1].event_observation.news_count == 1
    assert "investo:events" not in results[0].briefing.rendered_markdown

    legacy_runner = _ReplayRunner([valid_classification_stdout(1), valid_stage2_markdown()])
    legacy = await generate_briefing(
        _TARGET,
        [case.item],
        segment="us-equity",
        watchlist_config=WatchlistConfig(),
        runner=legacy_runner,
        generation_policy=replace(GenerationPolicy(), timeout_s=3, max_attempts=2),
    )
    assert legacy_runner.prompts == captures[0]
    assert legacy.model_dump() == results[0].briefing.model_dump()
