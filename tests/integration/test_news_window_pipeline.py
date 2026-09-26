"""News windows through real collection/generation/finalization/publication stages.

Only source transport, recorded LLM responses, and unrelated presentation
sidecars are replaced. Cursor changes are observed in a real bare Git remote.
"""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Never, cast
from unittest.mock import AsyncMock

import pytest
from pydantic import HttpUrl

from investo.briefing.event_evidence import (
    build_event_candidates,
    make_evidence_document,
    prepare_evidence_documents,
)
from investo.models import NormalizedItem, SendResult, SourceCollectionReport, SourceOutcome
from investo.models.coverage import SourceWindowCoverage, WindowCompleteness
from investo.models.event_config import EventExecutionConfig
from investo.models.events import EventCandidateDraft, EventFactDraft
from investo.models.news_window import (
    NewsCursor,
    NewsCursorLedger,
    NewsWindowConfig,
    NewsWindowMode,
)
from investo.models.segments import MarketSegment
from investo.orchestrator import pipeline
from investo.orchestrator.stage_context import SEGMENT_ORDER
from investo.orchestrator.stages import PipelineContext, StageResult
from investo.publisher.public_document import finalize_public_bundle
from tests.integration import test_event_publication_boundary as boundary
from tests.integration.test_event_generation import _reference
from tests.integration.test_event_publication_boundary import (
    Repository,
    _checked,
    _git,
)

_base_repository = boundary.repository

_PRICE_DATE = date(2026, 9, 25)
_RUN_START = datetime(2026, 9, 27, 22, tzinfo=UTC)
_SOURCE_SEGMENTS: dict[str, MarketSegment] = {
    "yonhap-market": "domestic-equity",
    "cnbc-top-news": "us-equity",
    "theblock-crypto": "crypto",
}
_CURSOR_PATH = Path("archive/_meta/news_cursors.json")
_BODY = (
    "## ① 요약\n공식 자료에 담긴 서비스 출시 소식을 확인했습니다. "
    "가격 기준일과 뉴스 발생 시점은 별도로 확인해야 합니다.\n\n"
    "## ② 전일 핵심 이슈\n가상기업은 새로운 서비스를 공개했습니다. "
    "이번 발표는 이용 대상과 서비스 제공 범위를 확인하는 데 의미가 있습니다.\n\n"
    "## ③ 섹터/수급 동향\n섹터 전체의 수급 변화와 시장 반응을 확인할 자료는 없습니다.\n\n"
    "## ④ 지표·이벤트\n추가로 확정된 주요 경제지표 발표 일정은 확인하지 못했습니다.\n\n"
    "## ⑤ 주요 종목\n가상기업의 서비스 소식은 확인했지만 "
    "개별 종목의 가격 반응은 확인하지 못했습니다.\n\n"
    "## ⑥ 오늘의 관전 포인트\n후속 공식 발표에서 서비스 제공 범위가 "
    "변경되는지 확인할 필요가 있습니다.\n"
)


@dataclass
class NewsRepository:
    base: Repository
    other: Path

    @property
    def work(self) -> Path:
        return self.base.work

    @property
    def remote(self) -> Path:
        return self.base.remote

    def head(self) -> str:
        return self.base.head()

    def remote_head(self) -> str:
        return self.base.remote_head()

    def remote_bytes(self, path: Path) -> bytes | None:
        result = _git(self.remote, "show", f"refs/heads/main:{path}")
        return result.stdout.encode() if result.returncode == 0 else None

    def remote_ledger(self) -> NewsCursorLedger:
        raw = self.remote_bytes(_CURSOR_PATH)
        assert raw is not None
        return NewsCursorLedger.model_validate_json(raw)

    def advance_remote(self, *, cursor_bytes: bytes | None = None) -> str:
        _checked(self.other, "fetch", "origin")
        _checked(self.other, "merge", "--ff-only", "origin/main")
        path = _CURSOR_PATH if cursor_bytes is not None else Path("unrelated.md")
        destination = self.other / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(cursor_bytes if cursor_bytes is not None else b"other writer\n")
        _checked(self.other, "add", "--", str(path))
        _checked(self.other, "commit", "-m", "synthetic concurrent writer")
        _checked(self.other, "push", "origin", "HEAD:refs/heads/main")
        return self.remote_head()


@pytest.fixture
def news_repository(
    _base_repository: Repository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> NewsRepository:
    other = tmp_path / "other"
    other.mkdir()
    _checked(other, "clone", "--branch", "main", str(_base_repository.remote), ".")
    _checked(other, "config", "user.name", "News Cursor Test")
    _checked(other, "config", "user.email", "news@example.invalid")
    _CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CURSOR_PATH.write_text(
        NewsCursorLedger(
            cursors=tuple(
                NewsCursor(
                    source_name=source, segment=segment, end_utc=_RUN_START - timedelta(days=3)
                )
                for source, segment in _SOURCE_SEGMENTS.items()
            )
        ).model_dump_json()
        + "\n"
    )
    _checked(_base_repository.work, "add", "--", str(_CURSOR_PATH))
    _checked(_base_repository.work, "commit", "-m", "synthetic prior confirmed news cursor")
    _checked(_base_repository.work, "push", "origin", "main")
    monkeypatch.setattr("investo.models.news_window.NEWS_WINDOW_ACTIVE_READY", True)
    monkeypatch.setattr(socket.socket, "connect", _forbid_baseline)
    monkeypatch.setenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", "1")
    monkeypatch.setattr(pipeline, "_load_recent_context_for_run", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_load_market_anchors_for_run", AsyncMock(return_value=({}, {})))
    monkeypatch.setattr(pipeline, "_load_carryover_for_run", lambda *_a, **_k: {})
    monkeypatch.setattr(pipeline, "_advance_and_persist_macro_carryover", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_persist_fact_snapshot_safely", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_append_daily_coverage_line", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_run_image_candidate_stage", lambda *_a, **_k: ((), "ok: empty"))
    monkeypatch.setattr(
        pipeline, "_inject_chart_blocks_into_segments", lambda briefings, **_k: (briefings, ())
    )

    async def no_visual_sidecars(
        briefings: dict[MarketSegment, object], *_args: object, **_kwargs: object
    ) -> tuple[dict[MarketSegment, object], tuple[()], dict[str, object]]:
        return briefings, (), {}

    monkeypatch.setattr(pipeline, "_stage_prepare_segment_visual_assets", no_visual_sidecars)
    return NewsRepository(_base_repository, other)


def news_items(*, published_at: datetime | None = None) -> tuple[NormalizedItem, ...]:
    return tuple(
        NormalizedItem(
            source_name=source,
            category="news",
            title="가상기업 신규 서비스 공개",
            summary="가상기업이 합성 서비스를 공개했습니다. 이용 대상과 제공 범위를 발표했습니다.",
            url=HttpUrl(f"https://example.invalid/{source}/synthetic-release"),
            published_at=published_at
            or datetime(2026, 9, 27 if segment == "us-equity" else 26, 12, tzinfo=UTC),
        )
        for source, segment in _SOURCE_SEGMENTS.items()
    )


class NewsRunner:
    """Six deterministic responses; source news, never a provider subprocess."""

    def __init__(self, *, blocked_segment: MarketSegment | None = None, v2: bool = False) -> None:
        self.prompts: list[str] = []
        self.blocked_segment = blocked_segment
        self.v2 = v2

    def __call__(self, args: list[str], *, input: str | None = None, **_kwargs: object) -> Any:
        assert input is not None
        index = len(self.prompts)
        self.prompts.append(input)
        if index % 2 == 0:
            value: dict[str, object] = {"assignments": {"1": 2}, "unassigned": []}
            if self.v2:
                value.update(schema_version=2, events=[])
            stdout = json.dumps(value)
        else:
            stdout = _BODY
            if self.v2:
                stdout = json.dumps(
                    {
                        "schema_version": 2,
                        "sections": {
                            "market_summary": "공식 자료에 담긴 서비스 소식을 확인했습니다.",
                            "sector_flow": "섹터 전체의 수급 자료는 확인하지 못했습니다.",
                            "indicators_events": "추가로 확정된 일정은 확인하지 못했습니다.",
                            "notable_tickers": "가상기업의 서비스 소식을 확인했습니다.",
                            "today_watch": "후속 공식 발표에서 제공 범위를 확인할 필요가 있습니다.",
                        },
                        "events": [],
                    },
                    ensure_ascii=False,
                )
            if SEGMENT_ORDER[index // 2] == self.blocked_segment:
                stdout = stdout.replace(
                    "## ① 요약\n", "## ① 요약\n수익을 보장합니다. 지금 매수하세요.\n"
                )
        return subprocess.CompletedProcess(args, 0, stdout, "")


class ObserveStage:
    """Delegates unchanged production stages and retains their typed boundary output."""

    def __init__(self, delegate: Any, observed: dict[str, Any]) -> None:
        self.delegate = delegate
        self.name = delegate.name
        self.observed = observed

    async def execute(
        self, ctx: PipelineContext, accumulated: dict[str, object]
    ) -> StageResult[dict[str, object]]:
        self.observed["context"] = ctx
        result = await self.delegate.execute(ctx, accumulated)
        self.observed[self.name] = result
        return cast(StageResult[dict[str, object]], result)


def source_outcomes(items: tuple[NormalizedItem, ...]) -> tuple[SourceOutcome, ...]:
    return tuple(SourceOutcome.ok(item.source_name, "news", 1) for item in items)


def notifier_pair(*, fail_notification: bool = False) -> tuple[Any, Any]:
    publisher = AsyncMock()
    publisher.send.return_value = SendResult(
        ok=not fail_notification,
        message_id=None if fail_notification else 1,
        error="synthetic delivery failure" if fail_notification else None,
    )
    return publisher, AsyncMock()


async def run_news_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: NewsWindowMode = "active",
    target_date: date | None = None,
    run_started_at: datetime = _RUN_START,
    items: tuple[NormalizedItem, ...] | None = None,
    completeness: dict[str, WindowCompleteness] | None = None,
    failed_sources: frozenset[str] = frozenset(),
    runner: NewsRunner | None = None,
    git_runner: Any = None,
    fail_notification: bool = False,
    stop_after_generate: bool = False,
    **options: Any,
) -> tuple[Any, dict[str, Any]]:
    """Keep all four production stages; replace only external collection transport."""
    observed: dict[str, Any] = {}
    fixture_items = news_items() if items is None else items

    async def collect(target: date, **kwargs: Any) -> SourceCollectionReport:
        observed["collection_target"] = target
        observed["collection_kwargs"] = kwargs
        windows = kwargs.get("news_windows") or {}
        selected = tuple(
            item
            for item in fixture_items
            if item.source_name not in failed_sources
            and (
                item.source_name not in windows
                or windows[item.source_name].contains(item.published_at)
            )
        )
        coverages = tuple(
            SourceWindowCoverage(
                source_name=source,
                requested_start=window.requested_start,
                end_utc=window.end_utc,
                pages=1,
                completeness="unknown"
                if source in failed_sources
                else (completeness or {}).get(source, "full"),
                basis="provider_pagination"
                if source not in failed_sources
                and (completeness or {}).get(source, "full") == "full"
                else "none",
            )
            for source, window in windows.items()
            if source in _SOURCE_SEGMENTS
        )
        failures = tuple(
            SourceOutcome.from_failure(
                source, "news", message="synthetic source failure", transient=True
            )
            for source in sorted(failed_sources)
        )
        return SourceCollectionReport(selected, (*source_outcomes(selected), *failures), coverages)

    monkeypatch.setattr(pipeline, "_default_collect_sources", collect)
    recorded = runner or NewsRunner()
    publisher, alerter = notifier_pair(fail_notification=fail_notification)
    observed["runner"] = recorded
    observed["publisher"] = publisher
    observed["alerter"] = alerter
    delegates: tuple[Any, ...] = (pipeline.CollectStage(), pipeline.GenerateStage())
    if not stop_after_generate:
        delegates += (pipeline.PublishStage(), pipeline.NotifyStage())
    stages = tuple(ObserveStage(stage, observed) for stage in delegates)
    result = await pipeline.run_pipeline(
        target_date,
        publisher=publisher,
        alerter=alerter,
        site_url_base=HttpUrl("https://example.invalid/investo"),
        runner=recorded,
        git_runner=git_runner,
        news_window_config=NewsWindowConfig(mode=mode),
        run_started_at=run_started_at,
        stages=stages,
        **options,
    )
    return result, observed


async def test_monday_news_consumption_is_generated_sealed_and_remotely_committed(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = news_repository.remote_bytes(_CURSOR_PATH)
    result, observed = await run_news_pipeline(monkeypatch)
    assert result.target_date == observed["collection_target"] == _PRICE_DATE
    assert result.publication_committed is True
    assert len(observed["runner"].prompts) == 6
    assert {item.published_at.date() for item in observed["collect"].data["items"]} == {
        date(2026, 9, 26),
        date(2026, 9, 27),
    }
    assert len(result.segment_outcomes) == 3
    assert all(row.state != "trust_blocked" for row in result.segment_outcomes), (
        result.segment_outcomes
    )
    assert news_repository.remote_bytes(_CURSOR_PATH) != before
    ledger = news_repository.remote_ledger()
    assert {(row.source_name, row.segment, row.end_utc) for row in ledger.cursors} == {
        (source, segment, _RUN_START) for source, segment in _SOURCE_SEGMENTS.items()
    }
    bundle = observed["publish"].data["finalized_bundle"]
    for document in bundle.documents:
        assert document.briefing.target_date == _PRICE_DATE
        generated = observed["generate"].data["event_results"][document.segment]
        assert generated.news_window_consumptions
        assert all(
            row.phase == "generated" and row.sealed_markdown_sha256 is None
            for row in generated.news_window_consumptions
        )
        nonempty = [row for row in document.news_window_consumptions if row.documents]
        assert len(nonempty) == 1
        receipt = nonempty[0]
        assert receipt.phase == "sealed" and receipt.documents
        assert receipt.end_utc == _RUN_START
        assert receipt.requested_start == _RUN_START - timedelta(days=4)
        assert receipt.documents == next(
            row.documents
            for row in generated.news_window_consumptions
            if row.source_name == receipt.source_name
        )
        assert (
            receipt.sealed_markdown_sha256
            == hashlib.sha256(document.briefing.rendered_markdown.encode()).hexdigest()
        )
        assert "가격 기준일 2026-09-25" in document.briefing.rendered_markdown
        assert "전체 뉴스의 완전 수집을 뜻하지 않습니다" in document.briefing.rendered_markdown
        assert (
            news_repository.remote_bytes(Path(f"archive/{document.segment}/2026/09/2026-09-25.md"))
            == document.briefing.rendered_markdown.encode()
        )


async def test_shadow_publishes_all_three_segments_with_legacy_bytes_and_unchanged_cursors(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = news_repository.remote_bytes(_CURSOR_PATH)
    legacy_items = news_items(published_at=datetime(2026, 9, 25, 12, tzinfo=UTC))
    off, off_observed = await run_news_pipeline(monkeypatch, mode="off", items=legacy_items)
    shadow, shadow_observed = await run_news_pipeline(
        monkeypatch, mode="shadow", items=legacy_items
    )
    assert off.publication_committed and shadow.publication_committed
    assert len(shadow.segment_outcomes) == 3
    assert all(
        outcome.state in {"finalized", "finalized_degraded"} for outcome in shadow.segment_outcomes
    )
    assert off_observed["runner"].prompts == shadow_observed["runner"].prompts
    assert off_observed["collection_kwargs"] == shadow_observed["collection_kwargs"] == {}
    off_docs = off_observed["publish"].data["finalized_bundle"].documents
    shadow_docs = shadow_observed["publish"].data["finalized_bundle"].documents
    assert [doc.briefing.rendered_markdown for doc in off_docs] == [
        doc.briefing.rendered_markdown for doc in shadow_docs
    ]
    assert news_repository.remote_bytes(_CURSOR_PATH) == before == _CURSOR_PATH.read_bytes()
    assert not Path("archive/_meta/news_windows").exists()


async def test_explicit_replay_v2_uses_frozen_windows_without_any_live_git_read(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _CURSOR_PATH.read_bytes()
    monkeypatch.setattr("investo.models.event_config.EVENT_ACTIVE_READY", True)
    replay_items = news_items(published_at=datetime(2026, 9, 25, 12, tzinfo=UTC))
    with monkeypatch.context() as isolated:
        isolated.setattr(subprocess, "run", _forbid_baseline)
        _, first = await run_news_pipeline(
            isolated,
            target_date=_PRICE_DATE,
            items=replay_items,
            runner=NewsRunner(v2=True),
            git_runner=_forbid_baseline,
            event_config=EventExecutionConfig("active"),
            stop_after_generate=True,
        )
        frozen = first["collect"].data["news_window_plan"].windows
        _, repeated = await run_news_pipeline(
            isolated,
            target_date=_PRICE_DATE,
            items=replay_items,
            run_started_at=_RUN_START + timedelta(days=30),
            news_replay_windows=frozen,
            runner=NewsRunner(v2=True),
            git_runner=_forbid_baseline,
            event_config=EventExecutionConfig("active"),
            stop_after_generate=True,
        )
    for observed in (first, repeated):
        assert observed["context"].news_replay is True
        assert observed["collect"].data["news_cursor_baseline"] is None
        assert observed["generate"].data["event_baseline"] is None
        assert observed["generate"].status == "ok"
        assert len(observed["runner"].prompts) == 6
    first_windows = first["collection_kwargs"]["news_windows"]
    repeated_windows = repeated["collection_kwargs"]["news_windows"]
    assert {key: (row.requested_start, row.end_utc) for key, row in first_windows.items()} == {
        key: (row.requested_start, row.end_utc) for key, row in repeated_windows.items()
    }
    assert first["runner"].prompts == repeated["runner"].prompts
    assert _CURSOR_PATH.read_bytes() == before == news_repository.remote_bytes(_CURSOR_PATH)
    assert not Path("archive/_meta/news_windows").exists()


async def test_hard_blocked_recipient_cannot_advance_its_consumed_cursor(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = finalize_public_bundle

    def finalizer(briefings: Any, **kwargs: Any) -> Any:
        changed = dict(briefings)
        domestic = changed["domestic-equity"]
        changed["domestic-equity"] = domestic.model_copy(
            update={
                "rendered_markdown": domestic.rendered_markdown.replace(
                    "## ① 요약\n", "## ① 요약\n\n## ① 요약\n", 1
                )
            }
        )
        return original(changed, **kwargs)

    monkeypatch.setattr(pipeline, "finalize_public_bundle", finalizer)
    result, observed = await run_news_pipeline(monkeypatch)
    assert result.publication_committed
    bundle = observed["publish"].data["finalized_bundle"]
    assert tuple(document.segment for document in bundle.documents) == ("us-equity", "crypto")
    assert result.segment_outcomes[0].state == "trust_blocked"
    assert observed["generate"].data["event_results"]["domestic-equity"].news_window_consumptions
    ledger = news_repository.remote_ledger()
    for cursor in ledger.cursors:
        expected = (
            _RUN_START - timedelta(days=3) if cursor.segment == "domestic-equity" else _RUN_START
        )
        assert cursor.end_utc == expected


@pytest.mark.parametrize("completeness", ["unknown", "partial"])
async def test_unproven_source_holds_only_its_cursor_despite_successful_publication(
    news_repository: NewsRepository,
    monkeypatch: pytest.MonkeyPatch,
    completeness: WindowCompleteness,
) -> None:
    result, observed = await run_news_pipeline(
        monkeypatch, completeness={"cnbc-top-news": completeness}
    )
    assert result.publication_committed and len(result.segment_outcomes) == 3
    ledger = news_repository.remote_ledger()
    for cursor in ledger.cursors:
        expected = (
            _RUN_START - timedelta(days=3) if cursor.source_name == "cnbc-top-news" else _RUN_START
        )
        assert cursor.end_utc == expected
    us_document = next(
        doc
        for doc in observed["publish"].data["finalized_bundle"].documents
        if doc.segment == "us-equity"
    )
    assert us_document.news_window_consumptions


def _forbid_baseline(*args: object, **kwargs: object) -> Never:
    pytest.fail("replay or dry-run attempted live Git/provider I/O")


async def test_scheduled_dry_run_never_reads_live_baseline_or_changes_cursor(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _CURSOR_PATH.read_bytes()
    monkeypatch.setenv("INVESTO_DRY_RUN", "1")
    with monkeypatch.context() as isolated:
        isolated.setattr(subprocess, "run", _forbid_baseline)
        result, observed = await run_news_pipeline(isolated, git_runner=_forbid_baseline)
    assert not result.publication_committed
    assert observed["collect"].data["news_cursor_baseline"] is None
    assert len(observed["publish"].data["finalized_bundle"].documents) == 3
    assert _CURSOR_PATH.read_bytes() == before == news_repository.remote_bytes(_CURSOR_PATH)
    assert not Path("archive/_meta/news_windows").exists()


async def test_weekend_v2_event_survives_selection_with_friday_price_reference(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("investo.models.event_config.EVENT_ACTIVE_READY", True)
    publication = datetime(2026, 9, 26, 12, tzinfo=UTC)
    fact = "서비스 가를 정식 출시했습니다."
    evidence = make_evidence_document(
        source_name="cnbc-top-news",
        title="가상사 출시 서비스 가",
        summary="가상사가 서비스 가를 정식 출시했습니다.",
        detail_excerpt=fact,
        url="https://example.invalid/weekend-launch",
        published_at=publication,
        received_at=_RUN_START,
        event_time=publication,
        event_time_basis="source_exact",
        source_tier="secondary",
    )
    item = NormalizedItem(
        source_name=evidence.source_name,
        category="news",
        title=evidence.title,
        summary=evidence.summary,
        url=HttpUrl(str(evidence.url)),
        published_at=publication,
        event_evidence=evidence,
    )
    document = prepare_evidence_documents((item,), received_at=_RUN_START)[0]
    fact_ref = _reference(document, fact, "detail_excerpt")
    proposal = EventCandidateDraft(
        item_ids=(1,),
        event_kind="product_service",
        actor_refs=(_reference(document, "가상사"),),
        action_refs=(_reference(document, "출시"),),
        object_refs=(_reference(document, "서비스 가"),),
        relation_refs=(fact_ref,),
        impact_refs=(fact_ref,),
        timing="announced",
        relation="direct",
        impact="company",
        facts=(EventFactDraft(predicate="launch", evidence_ref=fact_ref),),
    )
    candidate = build_event_candidates((proposal,), (item,), (document,), observed_at=_RUN_START)[0]
    classification = json.dumps(
        {
            "schema_version": 2,
            "assignments": {"1": 2},
            "unassigned": [],
            "events": [proposal.model_dump(mode="json")],
        },
        ensure_ascii=False,
    )
    synthesis = json.dumps(
        {
            "schema_version": 2,
            "sections": {
                "market_summary": "주말에 서비스 출시가 발표됐습니다.",
                "sector_flow": "섹터 전체의 수급 자료는 확인하지 못했습니다.",
                "indicators_events": "추가로 확정된 일정은 확인하지 못했습니다.",
                "notable_tickers": "가상사의 서비스 소식을 확인했습니다.",
                "today_watch": "후속 공식 발표에서 제공 범위를 확인할 필요가 있습니다.",
            },
            "events": [
                {
                    "event_id": candidate.event_id,
                    "headline": evidence.title,
                    "what_happened": "가상사는 서비스 가를 정식 출시했습니다.",
                    "fact_ids": candidate.required_fact_ids,
                    "source_refs": [ref.model_dump(mode="json") for ref in candidate.evidence_refs],
                    "meaning": {"text": None, "mode": "unavailable"},
                    "reaction": {"text": None, "status": "unavailable"},
                }
            ],
        },
        ensure_ascii=False,
    )

    class WeekendRunner(NewsRunner):
        def __call__(self, args: list[str], *, input: str | None = None, **kwargs: object) -> Any:
            assert input is not None
            response = (classification, synthesis)[len(self.prompts)]
            self.prompts.append(input)
            return subprocess.CompletedProcess(args, 0, response, "")

    result, observed = await run_news_pipeline(
        monkeypatch,
        items=(item,),
        runner=WeekendRunner(),
        event_config=EventExecutionConfig("active"),
    )
    assert result.publication_committed and result.target_date == _PRICE_DATE
    generated = observed["generate"].data["event_results"]["us-equity"]
    assert len(generated.event_plan.selected) == 1
    assert generated.event_plan.selected[0].published_at == publication
    sealed = next(
        doc
        for doc in observed["publish"].data["finalized_bundle"].documents
        if doc.segment == "us-equity"
    )
    assert sealed.surviving_event_ids == (candidate.event_id,)
    assert (
        sealed.notification_summary.events[0].fact_summary
        == "가상사는 서비스 가를 정식 출시했습니다."
    )
    assert "가격 기준일 2026-09-25" in sealed.briefing.rendered_markdown
    assert "2026-09-26" in sealed.briefing.rendered_markdown
    assert len(observed["runner"].prompts) == 2
    assert (
        observed["collect"].data["event_baseline"].baseline_sha
        == observed["collect"].data["news_cursor_baseline"].baseline_sha
    )


@pytest.mark.parametrize(("day", "hours"), [(date(2025, 3, 9), 23), (date(2025, 11, 2), 25)])
async def test_dst_replay_keeps_calendar_day_window_in_published_reader_output(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch, day: date, hours: int
) -> None:
    before = news_repository.remote_bytes(_CURSOR_PATH)
    timestamp = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    result, observed = await run_news_pipeline(
        monkeypatch,
        target_date=day,
        run_started_at=timestamp + timedelta(days=1),
        items=news_items(published_at=timestamp),
    )
    assert result.publication_committed and result.target_date == day
    window = observed["collect"].data["news_window_plan"].windows[("cnbc-top-news", "us-equity")]
    assert window.end_utc - window.requested_start == timedelta(hours=hours)
    us = next(
        doc
        for doc in observed["publish"].data["finalized_bundle"].documents
        if doc.segment == "us-equity"
    )
    assert window.requested_start.isoformat(timespec="seconds") in us.briefing.rendered_markdown
    assert window.end_utc.isoformat(timespec="seconds") in us.briefing.rendered_markdown
    assert news_repository.remote_bytes(_CURSOR_PATH) == before
    assert not Path("archive/_meta/news_windows").exists()


async def test_failed_source_keeps_cursor_while_successful_siblings_advance(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, observed = await run_news_pipeline(
        monkeypatch, failed_sources=frozenset({"cnbc-top-news"})
    )
    assert result.publication_committed
    assert len(observed["runner"].prompts) == 4
    ledger = news_repository.remote_ledger()
    for cursor in ledger.cursors:
        expected = (
            _RUN_START - timedelta(days=3) if cursor.source_name == "cnbc-top-news" else _RUN_START
        )
        assert cursor.end_utc == expected


async def test_total_source_failure_does_not_reach_generation_or_cursor_write(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = news_repository.remote_bytes(_CURSOR_PATH)
    initial_head = news_repository.remote_head()
    result, observed = await run_news_pipeline(
        monkeypatch, failed_sources=frozenset(_SOURCE_SEGMENTS)
    )
    assert not result.publication_committed
    assert observed["runner"].prompts == []
    assert "generate" not in observed and "publish" not in observed
    assert news_repository.remote_head() == initial_head
    assert news_repository.remote_bytes(_CURSOR_PATH) == before == _CURSOR_PATH.read_bytes()
    assert not Path("archive/_meta/news_windows").exists()


async def test_custom_generator_cannot_claim_plan_windows_as_consumed(
    news_repository: NewsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, prepared = await run_news_pipeline(
        monkeypatch,
        mode="off",
        stop_after_generate=True,
        items=news_items(published_at=datetime(2026, 9, 25, 12, tzinfo=UTC)),
    )
    legacy_briefings = prepared["generate"].data["segment_briefings"]

    async def custom_generator(
        target: date, items: object, runner: object, segment: MarketSegment, *args: object
    ) -> Any:
        return legacy_briefings[segment]

    result, observed = await run_news_pipeline(monkeypatch, generate_segment=custom_generator)
    assert result.publication_committed
    assert observed["runner"].prompts == []
    assert observed["generate"].data["event_results"] == {}
    bundle = observed["publish"].data["finalized_bundle"]
    assert len(bundle.documents) == 3
    assert all(document.news_window_consumptions == () for document in bundle.documents)
    assert all(
        cursor.end_utc == _RUN_START - timedelta(days=3)
        for cursor in news_repository.remote_ledger().cursors
    )
    manifest = next(Path("archive/_meta/news_windows").glob("*.json"))
    assert all(
        row["disposition"] == "not_sealed" for row in json.loads(manifest.read_bytes())["windows"]
    )
