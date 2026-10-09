"""Non-attempts survive orchestration serialization and cannot advance news cursors."""

from dataclasses import replace
from datetime import UTC, date, datetime

from investo import __main__ as main
from investo.models import PipelineResult, PipelineStatus, SourceOutcome
from investo.models.news_window import NewsCursorBaseline, NewsCursorLedger, NewsWindowConfig
from investo.orchestrator.news_window import (
    NEWS_CURSOR_PATH,
    make_news_window_consumptions,
    make_news_window_plan,
    news_manifest_path,
    prepare_news_window_publication,
)
from investo.orchestrator.pipeline import _build_quality_snapshot


def test_skipped_result_roundtrip_and_step_summary(tmp_path, monkeypatch) -> None:
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    skip = SourceOutcome.skipped("cnbc-top-news", "news", reason="access_denied")
    result = PipelineResult(
        target_date=date(2026, 10, 8),
        status=PipelineStatus.PARTIAL,
        stages={},
        stage_timings={},
        duration_seconds=1,
        source_outcomes=(skip,),
    )
    assert PipelineResult.model_validate_json(result.model_dump_json()) == result
    main._write_github_step_summary(result)
    summary = path.read_text()
    assert "Configured 1 / Attempted 0 / Skipped 1" in summary
    assert "skipped" in summary and "접근 제한" in summary
    assert summary.index("Configured 1") < summary.index("| Source | Tier")
    assert "Configured 1 / Attempted 0 / Skipped 1\n\n" in summary


def test_all_skipped_snapshot_does_not_report_liveness() -> None:
    snapshot = _build_quality_snapshot(
        briefings={},
        published_segments=(),
        items=(),
        source_outcomes=(
            SourceOutcome.skipped("coingecko-price", "price", reason="operator_disabled"),
        ),
    )
    assert snapshot.source_liveness is None
    assert snapshot.current_run_configured_sources == snapshot.current_run_skipped_sources == 1
    assert snapshot.current_run_attempted_sources == snapshot.total_failed_sources == 0


def test_skipped_news_absence_holds_actual_publication_cursor() -> None:
    run = "u165-cursor"
    baseline = NewsCursorBaseline(
        "a" * 40,
        "b" * 64,
        NewsCursorLedger(),
        "c" * 64,
        (NEWS_CURSOR_PATH, news_manifest_path(run)),
        run,
    )
    plan = make_news_window_plan(
        NewsWindowConfig("active"),
        run_id=run,
        target_date=date(2026, 10, 8),
        observed_at=datetime(2026, 10, 9, tzinfo=UTC),
        source_recipients={"yahoo-finance-news": ("us-equity",)},
        baseline=baseline,
    )
    (receipt,) = make_news_window_consumptions(plan, segment="us-equity", items=())
    receipt = replace(receipt, phase="sealed", sealed_markdown_sha256="d" * 64)
    prepared = prepare_news_window_publication(plan, baseline, coverage=(), consumed=(receipt,))
    assert prepared is not None
    _, metadata = prepared
    ledger = NewsCursorLedger.model_validate_json(metadata[NEWS_CURSOR_PATH])
    assert ledger.cursors == () and ledger.seen_revisions == ()
