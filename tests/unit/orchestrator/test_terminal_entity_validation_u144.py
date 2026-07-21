"""U144 Step 4.3 single terminal entity-fact gate regressions."""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import HttpUrl

from investo._internal.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.models.facts import FactSnapshot, VerifiedFactBundle
from investo.models.segments import DOMESTIC_EQUITY, US_EQUITY, MarketSegment
from investo.orchestrator import pipeline
from investo.orchestrator.stages import PipelineContext

_TARGET_DATE = date(2026, 7, 21)
_OBSERVED_AT = datetime(2026, 7, 21, 1, tzinfo=UTC)


def _briefing(segment: MarketSegment, body: str) -> Briefing:
    return Briefing(
        target_date=_TARGET_DATE,
        market_summary="공개 근거를 요약합니다.",
        key_issues="핵심 이슈를 확인합니다.",
        sector_flow="수급 흐름을 확인합니다.",
        indicators_events="주요 지표를 확인합니다.",
        notable_tickers="주요 자산을 확인합니다.",
        today_watch="확인할 조건을 살핍니다.",
        disclaimer=DISCLAIMER,
        rendered_markdown=f"{body}\n\n{DISCLAIMER}",
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
    assert "from investo.publisher.entity_fact_guard import" not in module_source
    assert "def _filter_entity_fact_violations" not in module_source
    assert "_scan_terminal_entity_fact_markdown" not in inspect.getsource(
        pipeline.GenerateStage.execute
    )
    assert "_scan_terminal_entity_fact_markdown" not in inspect.getsource(
        pipeline._stage_publish_segments
    )
    assert "_terminal_validate_entity_fact_segments" in inspect.getsource(
        pipeline.PublishStage.execute
    )
    terminal_source = inspect.getsource(pipeline._terminal_validate_entity_fact_segments)
    assert terminal_source.count("_scan_terminal_entity_fact_markdown(") == 1


@pytest.mark.asyncio
async def test_publish_terminal_gate_scans_each_segment_once_with_e1_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    briefings = {
        DOMESTIC_EQUITY: _briefing(DOMESTIC_EQUITY, "국내 시장의 일반 근거입니다."),
        US_EQUITY: _briefing(US_EQUITY, "파월 의장 기자회견이 예정돼 있습니다."),
    }
    calls: list[tuple[MarketSegment, datetime]] = []
    real_scan = pipeline._scan_terminal_entity_fact_markdown

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

    monkeypatch.setattr(pipeline, "_scan_terminal_entity_fact_markdown", observe_scan)
    monkeypatch.setattr(pipeline, "_stage_publish_segments", fake_publish_segments)
    context = PipelineContext(
        target_date=_TARGET_DATE,
        site_url_base=HttpUrl("https://example.com/investo"),
    )
    accumulated: dict[str, object] = {
        "segmented_mode": True,
        "items": [],
        "source_outcomes": (),
        "segment_briefings": briefings,
        "briefing": briefings[DOMESTIC_EQUITY],
        "macro_lineage_by_segment": {},
        "fact_bundle": _fact_bundle(),
        "entity_observed_at_utc": _OBSERVED_AT,
        "visual_asset_paths": (),
        "image_candidate_paths": (),
    }

    result = await pipeline.PublishStage().execute(context, accumulated)

    assert result.status == "partial"
    assert result.error is None
    assert result.data is not None
    assert result.data["entity_fact_blocked_segments"] == (US_EQUITY,)
    assert tuple(published[0]) == (DOMESTIC_EQUITY,)
    assert calls == ([(DOMESTIC_EQUITY, _OBSERVED_AT), (US_EQUITY, _OBSERVED_AT)])
    assert result.stage_notes[f"publish:{US_EQUITY}"] == "failed: EntityFactGuard"
