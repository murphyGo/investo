"""U144 Step 4.3 single terminal entity-fact gate regressions."""

from __future__ import annotations

import inspect
import logging
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import HttpUrl

from investo._internal.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.models.facts import FactSnapshot, VerifiedFactBundle
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.orchestrator import pipeline
from investo.orchestrator.stages import PipelineContext
from investo.publisher import public_document
from investo.publisher.public_document import PublicDocumentContext

_TARGET_DATE = date(2026, 7, 21)
_OBSERVED_AT = datetime(2026, 7, 21, 1, tzinfo=UTC)


def _briefing(segment: MarketSegment, body: str) -> Briefing:
    markdown = "\n".join(
        (
            f"# {_TARGET_DATE.isoformat()} {SEGMENT_LABELS[segment]} 시황",
            "",
            "> **오늘의 결론**: 공개 근거를 요약합니다.",
            "> **핵심 동인**: 핵심 이슈를 확인합니다.",
            "> **주의할 점**: 확인할 조건을 살핍니다.",
            "> **데이터 상태**: 정상 — 핵심 근거를 확인했습니다.",
            "> **소스 카운트**: 수집 대상 1 / 성공 1 / 0건 0 / 실패 0 / 본문 사용 미집계",
            "",
            "## ① 요약",
            "",
            "요약 본문",
            "",
            "## ② 전일 핵심 이슈",
            "",
            body,
            "",
            "## ③ 섹터/수급 동향",
            "",
            "수급 본문",
            "",
            "## ④ 지표·이벤트",
            "",
            "지표 본문",
            "",
            "## ⑤ 주요 종목",
            "",
            "종목 본문",
            "",
            "## ⑥ 오늘의 관전 포인트",
            "",
            "- 확인할 조건",
            "",
            "<details><summary>수집/품질 진단</summary>",
            "진단 정보",
            "</details>",
            "",
            DISCLAIMER,
        )
    )
    return Briefing(
        target_date=_TARGET_DATE,
        market_summary="공개 근거를 요약합니다.",
        key_issues="핵심 이슈를 확인합니다.",
        sector_flow="수급 흐름을 확인합니다.",
        indicators_events="주요 지표를 확인합니다.",
        notable_tickers="주요 자산을 확인합니다.",
        today_watch="확인할 조건을 살핍니다.",
        disclaimer=DISCLAIMER,
        rendered_markdown=f"{markdown}\n",
    )


def _fact_bundle() -> VerifiedFactBundle:
    return VerifiedFactBundle(
        target_date=_TARGET_DATE,
        facts=(
            FactSnapshot(
                fact_id="fed.current_chair",
                value="Kevin Warsh",
                label_ko="케빈 워시",
                aliases=(),
                role="Chairman",
                source_name="fed-board-leadership",
                source_url=("https://www.federalreserve.gov/aboutthefed/bios/board/default.htm"),
                source_tier="S",
                observed_at=_OBSERVED_AT,
                expires_at=_OBSERVED_AT + timedelta(hours=24),
                status="fresh",
                raw_evidence_label="Kevin Warsh, Chairman",
            ),
        ),
    )


def test_legacy_generate_and_segment_publish_entity_scan_paths_are_absent() -> None:
    module_source = inspect.getsource(pipeline)
    generate_source = inspect.getsource(pipeline.GenerateStage.execute)
    assert "from investo.publisher.entity_fact_guard import" not in module_source
    assert "def _filter_entity_fact_violations" not in module_source
    assert "_scan_terminal_entity_fact_markdown" not in generate_source
    assert "_scan_terminal_entity_fact_markdown" not in inspect.getsource(
        pipeline._stage_publish_segments
    )
    publish_source = inspect.getsource(pipeline.PublishStage.execute)
    assert "_terminal_validate_entity_fact_segments" not in module_source
    assert "_apply_reader_format_to_segments" not in generate_source
    assert "SurfaceQualityError" not in generate_source
    assert "while True" not in generate_source
    assert publish_source.count("finalize_public_bundle(") == 1
    assert "_scan_terminal_entity_fact_markdown" not in module_source


@pytest.mark.asyncio
async def test_publish_terminal_gate_scans_each_active_attempt_with_e1_clock(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="investo.orchestrator.pipeline")
    briefings = {
        DOMESTIC_EQUITY: _briefing(DOMESTIC_EQUITY, "국내 시장의 일반 근거입니다."),
        US_EQUITY: _briefing(US_EQUITY, "파월 의장 기자회견이 예정돼 있습니다."),
    }
    calls: list[tuple[MarketSegment, datetime]] = []
    real_scan = public_document._scan_terminal_entity_fact_markdown

    def observe_scan(
        markdown: str,
        *,
        segment: MarketSegment,
        fact_bundle: VerifiedFactBundle,
        target_date: date,
        entity_observed_at_utc: datetime,
    ):
        calls.append((segment, entity_observed_at_utc))
        return real_scan(
            markdown,
            segment=segment,
            fact_bundle=fact_bundle,
            target_date=target_date,
            entity_observed_at_utc=entity_observed_at_utc,
        )

    published: list[dict[MarketSegment, Briefing]] = []

    async def fake_publish_segments(
        active: dict[MarketSegment, Briefing],
        target_date: date,
        **_: object,
    ) -> dict[MarketSegment, object]:
        assert target_date == _TARGET_DATE
        published.append(dict(active))
        return {}

    monkeypatch.setattr(
        public_document,
        "_scan_terminal_entity_fact_markdown",
        observe_scan,
    )
    monkeypatch.setattr(pipeline, "_stage_publish_segments", fake_publish_segments)
    context = PipelineContext(
        target_date=_TARGET_DATE,
        site_url_base=HttpUrl("https://example.com/investo"),
    )
    fact_bundle = _fact_bundle()
    public_context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY, US_EQUITY, CRYPTO),
        input_absences={CRYPTO: "generation_failed"},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=0,
                source_count=0,
                categories=(),
                missing_categories=(),
            )
            for segment in briefings
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=fact_bundle,
        entity_observed_at_utc=_OBSERVED_AT,
    )
    accumulated: dict[str, object] = {
        "segmented_mode": True,
        "items": [],
        "source_outcomes": (),
        "segment_briefings": briefings,
        "briefing": briefings[DOMESTIC_EQUITY],
        "macro_lineage_by_segment": {},
        "public_document_context": public_context,
        "visual_asset_paths": (),
        "image_candidate_paths": (),
    }

    result = await pipeline.PublishStage().execute(context, accumulated)

    assert result.status == "partial"
    assert result.error is None
    assert result.data is not None
    assert result.data["finalization_blocked_segments"] == (US_EQUITY,)
    bundle = result.data["finalized_bundle"]
    assert bundle.documents[0].notification_summary.conclusion == "공개 근거를 요약합니다."
    assert result.data["segment_briefings"] == {DOMESTIC_EQUITY: bundle.documents[0].briefing}
    assert tuple(published[0]) == (DOMESTIC_EQUITY,)
    assert calls == [
        (DOMESTIC_EQUITY, _OBSERVED_AT),
        (US_EQUITY, _OBSERVED_AT),
        (DOMESTIC_EQUITY, _OBSERVED_AT),
    ]
    assert result.stage_notes[f"publish:{US_EQUITY}"] == ("failed: PublicDocumentTrustGate")
    assert (
        "[finalize] target_date=2026-07-21 segment=domestic-equity state=finalized codes=none"
    ) in caplog.messages
    assert (
        "[finalize] target_date=2026-07-21 segment=us-equity "
        "state=trust_blocked codes=entity.fact_contradiction"
    ) in caplog.messages
    assert (
        "[finalize] target_date=2026-07-21 segment=crypto "
        "state=generation_absent codes=generation.failed"
    ) in caplog.messages


@pytest.mark.asyncio
async def test_publish_stage_converts_finalizer_e8_to_failed_result_and_skips_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    briefing = _briefing(DOMESTIC_EQUITY, "국내 시장의 일반 근거입니다.")
    error = pipeline.PublicDocumentFinalizationError(
        target_date=_TARGET_DATE,
        segment=None,
        phase="bundle",
        issue_codes=("bundle.zero_survivors",),
    )
    publish_called = False

    def fail_finalization(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    async def forbidden_publish(*args: object, **kwargs: object) -> None:
        del args, kwargs
        nonlocal publish_called
        publish_called = True

    monkeypatch.setattr(pipeline, "finalize_public_bundle", fail_finalization)
    monkeypatch.setattr(pipeline, "_stage_publish_segments", forbidden_publish)
    context = PipelineContext(
        target_date=_TARGET_DATE,
        site_url_base=HttpUrl("https://example.com/investo"),
    )
    accumulated: dict[str, object] = {
        "segmented_mode": True,
        "items": [],
        "source_outcomes": (),
        "segment_briefings": {DOMESTIC_EQUITY: briefing},
        "briefing": briefing,
        "macro_lineage_by_segment": {},
        "public_document_context": object(),
        "visual_asset_paths": (),
        "image_candidate_paths": (),
    }

    result = await pipeline.PublishStage().execute(context, accumulated)

    assert result.status == "failed"
    assert result.error is error
    assert result.stage_notes == {
        "publish": "failed: PublicDocumentFinalizationError",
        "notify_briefing": "skipped",
    }
    assert result.timings["publish:finalize"] >= 0
    assert publish_called is False
