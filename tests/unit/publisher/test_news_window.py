"""News interval metadata and actual sealed reader output share one projection."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from investo._internal.event_rendering import render_event_blocks
from investo.briefing.event_evidence import evidence_document_from_item
from investo.briefing.quality_history import QualitySnapshot, append_quality_snapshot
from investo.models.coverage import SourceWindowCoverage
from investo.models.news_window import NewsWindowConfig
from investo.models.segments import US_EQUITY
from investo.orchestrator.news_window import make_news_window_consumptions, make_news_window_plan
from investo.publisher.news_window import news_observation_matches, news_observation_quality
from investo.publisher.public_document import finalize_public_bundle
from tests.integration.test_event_finalization import _briefing, _context
from tests.unit.briefing.test_event_evidence import item
from tests.unit.briefing.test_event_narrative import payload_for


def test_sealed_news_intervals_match_public_quality_without_private_identity(
    tmp_path: Path,
) -> None:
    payload = payload_for()
    context = _context({US_EQUITY: payload})
    source = payload.plan.evidence_documents[0].source_name
    plan = make_news_window_plan(
        NewsWindowConfig("active"),
        run_id="test-news",
        target_date=context.target_date,
        observed_at=context.entity_observed_at_utc,
        source_recipients={source: (US_EQUITY,)},
    )
    consumed = make_news_window_consumptions(
        plan, segment=US_EQUITY, items=(item(payload.plan.evidence_documents[0]),)
    )
    window = plan.windows[(source, US_EQUITY)]
    coverage = SourceWindowCoverage(
        source_name=source,
        requested_start=window.requested_start,
        end_utc=window.end_utc,
        completeness="full",
        basis="provider_pagination",
        pages=1,
    )
    context = replace(
        context,
        news_window_plan=plan,
        news_window_consumptions_by_segment={US_EQUITY: consumed},
        news_window_coverage=(coverage,),
    )
    document = finalize_public_bundle({US_EQUITY: _briefing(payload)}, context=context).documents[0]
    assert all(receipt.phase == "sealed" for receipt in document.news_window_consumptions)
    assert all(
        receipt.sealed_markdown_sha256 == document.markdown_sha256
        for receipt in document.news_window_consumptions
    )
    quality = news_observation_quality(
        plan, segment=US_EQUITY, consumed=document.news_window_consumptions, coverage=(coverage,)
    )
    assert quality is not None and quality.full_sources == 1
    assert quality.price_reference_date == document.target_date
    assert "소스 조회 상태: 완료 1개" in document.briefing.rendered_markdown
    assert "전체 뉴스의 완전 수집을 뜻하지 않습니다" in document.briefing.rendered_markdown
    path = tmp_path / "quality.jsonl"
    append_quality_snapshot(
        context.target_date,
        snapshot=QualitySnapshot(
            source_liveness=1,
            figures_presence=0,
            fallback_ratio=0,
            published_segments=1,
            total_items=1,
            total_failed_sources=0,
            news_observation={US_EQUITY: quality},
        ),
        history_path=path,
    )
    public = json.loads(path.read_text())["news_observation"][US_EQUITY]
    assert public == quality.model_dump(mode="json")
    assert "documents" not in public and "baseline_cursor_hash" not in public
    stale = replace(coverage, requested_start=coverage.requested_start - timedelta(hours=1))
    unknown = news_observation_quality(
        plan, segment=US_EQUITY, consumed=consumed, coverage=(stale,)
    )
    assert unknown is not None and unknown.full_sources == 0 and unknown.unknown_sources == 1


def test_hidden_or_duplicate_news_projection_cannot_supply_visible_evidence() -> None:
    expected = "**뉴스 관측기간**: source interval"
    assert news_observation_matches(expected, expected)
    assert not news_observation_matches(f"<!--{expected}-->", expected)
    assert not news_observation_matches(f"```text\n{expected}\n```\n", expected)
    assert not news_observation_matches(expected + "\n" + expected, expected)


@pytest.mark.parametrize(
    ("opening", "closing"),
    [
        (" ```text\n", "\n ```\n"),
        ("  ~~~text\n", "\n  ~~~~\n"),
        ("   ````text\n", "\n   `````\n"),
        (" ```text\n", ""),
        (" ````text\n", "\n ```\n"),
        (" ```text\n", "\n ~~~\n"),
        ("<!--", ""),
    ],
)
def test_unclosed_or_indented_hidden_projection_is_not_visible(opening: str, closing: str) -> None:
    expected = "**뉴스 관측기간**: source interval"
    assert not news_observation_matches(opening + expected + closing, expected)


@pytest.mark.parametrize("actual_event_date", [False, True])
def test_date_precision_evidence_does_not_invent_an_event_instant(actual_event_date: bool) -> None:
    payload = payload_for()
    document = payload.plan.evidence_documents[0]
    metadata = {
        "published_at_precision": "date",
        "published_date": "2026-09-21",
        "published_timezone": "Asia/Seoul",
    }
    if actual_event_date:
        metadata.update(event_date="2026-09-21", event_time_basis="source_date")
    source = item(document).model_copy(update={"event_evidence": None, "raw_metadata": metadata})
    evidence = evidence_document_from_item(source, received_at=document.received_at)
    assert evidence.published_date is not None
    assert evidence.event_time_basis == ("source_date" if actual_event_date else "unknown")
    if not actual_event_date:
        assert evidence.event_time is None
    dates = tuple(
        row.model_copy(update={"published_date": evidence.published_date})
        for row in payload.plan.evidence_documents
    )
    events = tuple(
        row.model_copy(update={"timing": "unknown", "effective_date": None})
        for row in payload.plan.selected
    )
    updated = payload.model_copy(
        update={
            "plan": payload.plan.model_copy(
                update={"evidence_documents": dates, "selected": events}
            )
        }
    )
    rendered = render_event_blocks(updated)
    assert "보도 기준 2026-09-21 (출처 날짜); 사건 시점 미확인" in rendered
    assert "보도 기준 2026-09-21 00:00" not in rendered
