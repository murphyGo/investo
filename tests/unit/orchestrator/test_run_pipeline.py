"""Tests for ``investo.orchestrator.pipeline.run_pipeline``.

Pins the Q9=B Error Policy routing across AC-003-1 ~ AC-003-11 plus
AC-001-3 / AC-001-5 (no asyncio.wait_for / no stage-level
asyncio.gather) + AC-003-11 (no orchestrator-level retry) via AST-grep
deny tests on the source file.

Test architecture
-----------------
- Real ``write_briefing`` against ``tmp_path`` (atomic write to
  isolated archive root via ``ARCHIVE_ROOT`` monkeypatch).
- Fake ``GitRunner`` (always-success or always-fail variants).
- Fake ``BriefingPublisher`` and ``OperatorAlerter`` with recorded
  ``send`` / ``alert`` calls.
- Fake ``fetch`` callable (returns items or raises) and ``generate``
  callable (returns Briefing or raises).
"""

from __future__ import annotations

import ast
import asyncio
import importlib
import json
import logging
import subprocess
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.briefing.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
)
from investo.models import (
    Briefing,
    BriefingNotification,
    FailureContext,
    NormalizedItem,
    PipelineStatus,
    SendResult,
)
from investo.models.public_artifact import StagedArtifact
from investo.models.results import TRACEBACK_EXCERPT_MAX
from investo.orchestrator import pipeline as pipeline_module
from investo.orchestrator.pipeline import (
    _briefing_url_for,
    _build_failure_context,
    run_pipeline,
)
from investo.publisher import public_document as public_document_module
from investo.publisher.charts import ChartArtifacts
from investo.publisher.errors import PublisherIOError
from investo.visuals.assets import PreparedVisualAssets, VisualAssetError

_TARGET = date(2026, 4, 27)  # Mon
_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_PUBLIC_CHANNEL = "@example_channel"
_OPERATOR_CHAT = "12345678"
_SITE_BASE: HttpUrl = TypeAdapter(HttpUrl).validate_python("https://example.github.io/investo")


# ---------------------------------------------------------------------------
# Fixtures / fakes
# ---------------------------------------------------------------------------


def _item(title: str = "x") -> NormalizedItem:
    return NormalizedItem(
        source_name="fake-src",
        category="news",
        title=title,
        published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
    )


def _briefing(target_date: date = _TARGET, segment: MarketSegment | None = None) -> Briefing:
    # u56 — crypto segment carries DISCLAIMER_CRYPTO so the publish
    # gate's segment-aware verify_disclaimer(..., segment="crypto")
    # passes.
    footer = DISCLAIMER_CRYPTO if segment == "crypto" else DISCLAIMER
    body = (
        "오늘 시장 요약\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n"
        "<details><summary>수집/품질 진단</summary>\n"
        "진단 정보\n"
        "</details>\n\n" + footer
    )
    title = SEGMENT_LABELS[segment] if segment is not None else "테스트"
    return Briefing(
        target_date=target_date,
        market_summary="오늘 시장 요약",
        key_issues="핵심 이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=footer,
        rendered_markdown=(
            f"# {target_date.isoformat()} {title} 시황\n\n"
            "> **오늘의 결론**: 오늘 시장 요약\n"
            "> **핵심 동인**: 핵심 이슈\n"
            "> **주의할 점**: 관전\n\n"
            "## ① 요약\n" + body
        ),
    )


class _FakePublisher:
    """Records sends; replies with the configured ``SendResult``."""

    def __init__(
        self,
        *,
        result: SendResult | None = None,
        raise_exc: BaseException | None = None,
    ) -> None:
        self._result = result if result is not None else SendResult(ok=True, message_id=1)
        self._raise = raise_exc
        self.calls: list[BriefingNotification] = []

    async def send(self, payload: BriefingNotification) -> SendResult:
        self.calls.append(payload)
        if self._raise is not None:
            raise self._raise
        return self._result


class _FakeAlerter:
    """Records alerts; replies with the configured ``SendResult`` (default ok)."""

    def __init__(
        self,
        *,
        result: SendResult | None = None,
        results: list[SendResult] | None = None,
        raise_exc: BaseException | None = None,
    ) -> None:
        self._result = result if result is not None else SendResult(ok=True, message_id=2)
        self._results = list(results) if results is not None else None
        self._raise = raise_exc
        self.calls: list[FailureContext] = []

    async def alert(self, ctx: FailureContext) -> SendResult:
        self.calls.append(ctx)
        if self._raise is not None:
            raise self._raise
        if self._results is not None:
            return self._results.pop(0)
        return self._result


class _SuccessfulGitRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def _success_fetch(items: list[NormalizedItem]) -> object:
    async def _fake(target_date: date) -> list[NormalizedItem]:
        return items

    return _fake


def _failing_bge_generate(stage: str = "synthesis") -> object:
    async def _fake(
        target_date: date,
        items: object,
        runner: object,
    ) -> Briefing:
        raise BriefingGenerationError(
            stage=stage,  # type: ignore[arg-type]
            attempt_count=3,
            last_stderr="boom",
            cause=None,
        )

    return _fake


def test_curated_asset_runtime_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    """A staged u86 rollout must not make ``python -m investo`` import-fragile."""

    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None) -> object:
        if name == "investo.visuals.curated":
            raise ModuleNotFoundError("No module named 'investo.visuals.curated'", name=name)
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert pipeline_module._load_curated_runtime_safely() is None


def _success_generate() -> object:
    async def _fake(
        target_date: date,
        items: object,
        runner: object,
    ) -> Briefing:
        return _briefing(target_date)

    return _fake


def _success_segment_generate(calls: list[tuple[MarketSegment, int, bool]]) -> object:
    async def _fake(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del source_outcomes  # u22 transparency hook — not asserted by these tests
        del recent_context  # u34 — asserted in dedicated test below
        del market_anchors  # u49 — asserted in dedicated test below
        del carryover  # u52 — asserted in dedicated test below
        del bundle_context  # u57 — asserted in dedicated test below
        calls.append((segment, len(items), data_limited))
        return _briefing(target_date, segment=segment)

    return _fake


def _failing_segment_generate(fail_segment: MarketSegment) -> object:
    async def _fake(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del source_outcomes
        del recent_context
        del market_anchors
        del carryover
        del bundle_context
        if segment == fail_segment:
            raise BriefingGenerationError(
                stage="synthesis",
                attempt_count=3,
                last_stderr=f"{segment} failed",
                cause=None,
            )
        return _briefing(target_date, segment=segment)

    return _fake


def _surface_blocking_segment_generate(block_segment: MarketSegment) -> object:
    async def _fake(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del items, runner, data_limited, source_outcomes, recent_context, market_anchors
        del carryover, bundle_context
        briefing = _briefing(target_date, segment=segment)
        if segment != block_segment:
            return briefing
        return briefing.model_copy(
            update={
                "rendered_markdown": briefing.rendered_markdown.replace(
                    "> **오늘의 결론**: 오늘 시장 요약",
                    "> **오늘의 결론**: [broken link",
                )
            }
        )

    return _fake


@pytest.fixture
def archive_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ARCHIVE_ROOT to per-test tmp dir so writes don't pollute repo."""
    root = tmp_path / "archive"
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", root)
    # Disable backoff sleeps so retry-exhaustion tests run in ms.
    monkeypatch.setattr("investo.publisher.git_ops.time.sleep", lambda _s: None)
    return root


# ---------------------------------------------------------------------------
# Happy path → SUCCESS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_happy_path_success(archive_root: Path) -> None:
    """All 4 stages succeed → SUCCESS, briefing_url set, NO operator alert."""
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("a"), _item("b")]),
        git_runner=git,
        generate=_success_generate(),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.content_completeness == "complete"
    assert result.segment_outcomes == ()
    assert result.publication_committed is True
    assert result.target_date == _TARGET
    assert result.stages == {
        "collect": "ok",
        "generate": "ok",
        "publish": "ok",
        "notify_briefing": "ok",
    }
    assert set(result.stage_timings) == {
        "collect",
        "generate",
        "publish",
        "notify_briefing",
    }
    assert all(t >= 0 for t in result.stage_timings.values())
    # Per-day URL is what flows to publisher AND PipelineResult.
    assert result.briefing_url is not None
    assert "archive/2026/04/2026-04-27" in str(result.briefing_url)
    # No operator alert on the happy path.
    assert alerter.calls == []
    # Publisher was called exactly once with the per-day URL.
    assert len(publisher.calls) == 1
    assert str(publisher.calls[0].site_url) == str(result.briefing_url)


@pytest.mark.asyncio
async def test_run_pipeline_default_generates_and_publishes_three_segments(
    archive_root: Path,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    segment_calls: list[tuple[MarketSegment, int, bool]] = []
    items = [
        NormalizedItem(
            source_name="yonhap-market",
            category="news",
            title="코스피 상승 [005930]",
            published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="AAPL closes higher",
            published_at=datetime(2026, 4, 27, 12, 1, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="coingecko-price",
            category="price",
            title="Bitcoin rises",
            published_at=datetime(2026, 4, 27, 12, 2, tzinfo=UTC),
        ),
    ]

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch(items),
        git_runner=git,
        generate_segment=_success_segment_generate(segment_calls),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.content_completeness == "complete"
    assert tuple(outcome.state for outcome in result.segment_outcomes) == (
        "finalized",
        "finalized",
        "finalized",
    )
    assert result.publication_committed is True
    assert [call[0] for call in segment_calls] == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert [call[1] for call in segment_calls] == [1, 1, 1]
    assert [call[2] for call in segment_calls] == [True, True, True]
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        assert (archive_root / segment / "2026" / "04" / "2026-04-27.md").exists()


def _ppi_actual_item() -> NormalizedItem:
    return NormalizedItem(
        source_name="fred-macro",
        category="macro",
        title="Producer Price Index by Commodity: Final Demand",
        published_at=datetime(2026, 4, 27, 13, 0, tzinfo=UTC),
        raw_metadata={
            "series_id": "PPIFID",
            "release_date": "2026-04-27",
            "macro_event_label": "Producer Price Index",
            "value": "144.2",
        },
    )


@pytest.mark.asyncio
async def test_run_pipeline_persists_macro_carryover_snapshot(
    archive_root: Path,
) -> None:
    items = [_item("AAPL closes higher"), _ppi_actual_item()]

    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch(items),
        git_runner=_SuccessfulGitRunner(),
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.SUCCESS
    carryover = archive_root / "_meta" / "macro_event_carryover.jsonl"
    assert carryover.exists()
    rows = [line for line in carryover.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any('"status": "confirmed"' in row and "PPIFID" in row for row in rows)


@pytest.mark.asyncio
async def test_run_pipeline_survives_macro_carryover_persist_failure(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.briefing.macro_carryover import MacroCarryoverError

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise MacroCarryoverError("disk full")

    monkeypatch.setattr(pipeline_module, "upsert_macro_lifecycle_snapshot", _boom)

    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL"), _ppi_actual_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate_segment=_success_segment_generate([]),
    )

    # Carryover persistence failure must not crash or fail the pipeline.
    assert result.status == PipelineStatus.SUCCESS


@pytest.mark.asyncio
async def test_run_pipeline_success_appends_quality_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", Path("archive"))
    monkeypatch.setattr(
        pipeline_module,
        "update_latest_index_pages",
        lambda *args, **kwargs: (Path("site_docs/index.md"),),
    )
    monkeypatch.setattr(pipeline_module, "_build_publish_heatmap_svg", lambda _date: "<svg/>")
    monkeypatch.setattr(
        pipeline_module,
        "write_og_card",
        lambda *args, **kwargs: Path("site_docs/assets/og-card.svg"),
    )
    git = _SuccessfulGitRunner()
    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    history = tmp_path / "quality_history.jsonl"
    rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
    forecast_rows = [
        json.loads(line)
        for line in (tmp_path / "forecast_log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert result.status == PipelineStatus.SUCCESS
    assert len(rows) == 1
    assert rows[0]["date"] == _TARGET.isoformat()
    assert rows[0]["published_segments"] == 3
    assert rows[0]["total_items"] == 1
    assert rows[0]["total_failed_sources"] == 0
    assert rows[0]["current_run_briefings_observed"] == 3
    assert rows[0]["current_run_zero_item_sources"] == 0
    assert rows[0]["current_run_core_missing_segments"] == 2
    assert rows[0]["current_run_segments_limited_or_worse"] == 2
    assert len(forecast_rows) == 3
    assert (tmp_path / "site_docs" / "accuracy.md").exists()


@pytest.mark.asyncio
async def test_run_pipeline_dry_run_skips_quality_history_append(
    archive_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_DRY_RUN", "1")

    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=_SuccessfulGitRunner(),
        generate_segment=_success_segment_generate([]),
    )

    assert not (tmp_path / "quality_history.jsonl").exists()
    assert not (tmp_path / "forecast_log.jsonl").exists()
    assert not (tmp_path / "accuracy.md").exists()
    assert result.publication_committed is False


@pytest.mark.asyncio
async def test_run_pipeline_threads_recent_context_to_segment_generate(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """u34 — orchestrator loads trailing-N-day archive context and threads
    it into the segment generate callable. Pin: when an archived briefing
    exists for ``target_date - 1`` (a weekday), the loader populates the
    ``RecentBriefingsContext`` and the fake generator observes it.
    """
    from investo.briefing.context import RecentBriefingsContext

    # Seed an archive entry one weekday before the target so the loader
    # has something to pick up.
    yesterday = date(2026, 4, 24)  # Fri (target Mon 4/27 → look back to Fri)
    seed_dir = archive_root / US_EQUITY / "2026" / "04"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "2026-04-24.md").write_text(
        "# 2026-04-24 미국 증시 시황\n\n"
        "**기준 시각**: 2026-04-24 NY · "
        "수집창 2026-04-24T04:00Z ~ 2026-04-25T04:00Z (종료 미포함)\n\n"
        "> **오늘의 결론**: 어제는 반도체 주도\n"
        "> **핵심 동인**: AI 투자 사이클\n"
        "> **주의할 점**: 변동성\n\n"
        "## ① 요약\n\n본문\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("INVESTO_RECENT_CONTEXT_DAYS", "5")

    seen: list[RecentBriefingsContext | None] = []

    async def _capturing_segment_generate(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: RecentBriefingsContext | None = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del (
            items,
            runner,
            source_outcomes,
            data_limited,
            market_anchors,
            carryover,
            bundle_context,
        )
        if segment == US_EQUITY:
            seen.append(recent_context)
        return _briefing(target_date, segment=segment)

    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="AAPL closes higher",
            published_at=datetime(2026, 4, 27, 12, 1, tzinfo=UTC),
        ),
    ]

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch(items),
        git_runner=git,
        generate_segment=_capturing_segment_generate,
    )

    assert result.status == PipelineStatus.SUCCESS
    assert len(seen) == 1
    captured = seen[0]
    assert captured is not None
    us_entries = captured.for_segment(US_EQUITY)
    assert len(us_entries) == 1
    assert us_entries[0].publish_date == yesterday
    assert "반도체" in us_entries[0].conclusion


@pytest.mark.asyncio
async def test_run_pipeline_recent_context_disabled_when_env_zero(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """u34 — ``INVESTO_RECENT_CONTEXT_DAYS=0`` disables the feature
    cleanly: the orchestrator threads ``None`` to the segment generator
    and the recent-briefings loader is never invoked.
    """
    monkeypatch.setenv("INVESTO_RECENT_CONTEXT_DAYS", "0")

    seen_recent: list[object] = []

    async def _capturing_segment_generate(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del (
            items,
            runner,
            source_outcomes,
            data_limited,
            market_anchors,
            carryover,
            bundle_context,
        )
        if segment == US_EQUITY:
            seen_recent.append(recent_context)
        return _briefing(target_date)

    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="AAPL closes higher",
            published_at=datetime(2026, 4, 27, 12, 1, tzinfo=UTC),
        ),
    ]

    await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch(items),
        git_runner=git,
        generate_segment=_capturing_segment_generate,
    )

    assert seen_recent == [None]


@pytest.mark.asyncio
async def test_run_pipeline_segmented_publish_inserts_visual_links_and_stages_svgs(
    archive_root: Path,
) -> None:
    """u26 Step 1 — pin the segmented publish path's visual delivery contract.

    Persona #2 (2026-05-07): u24 closed but the 2026-05-06 archive carried
    no SVGs and no ``![](...)`` references. This test exercises the real
    segmented pipeline (no monkeypatched visuals) and pins:

    1. ``insert_visual_links`` ran — every segment markdown contains at
       least one ``![label](2026-MM-DD.assets/...)`` reference.
    2. SVG cards landed beside the markdown — ``data-confidence.svg`` /
       ``market-snapshot.svg`` / ``watchlist-relevance.svg`` exist with
       their JSON manifests.
    3. The publish stage forwarded the staged asset paths to git so the
       commit picks them up alongside the markdown.

    A regression that drops any of (1)/(2)/(3) — e.g., an early-return in
    ``_stage_prepare_segment_visual_assets`` or a refactor that keeps the
    files but forgets ``insert_visual_links`` — fails this test.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    items = [
        NormalizedItem(
            source_name="yonhap-market",
            category="news",
            title="코스피 상승 [005930]",
            published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="AAPL closes higher",
            published_at=datetime(2026, 4, 27, 12, 1, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="coingecko-price",
            category="price",
            title="Bitcoin rises",
            published_at=datetime(2026, 4, 27, 12, 2, tzinfo=UTC),
        ),
    ]

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch(items),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.stages.get("visual_assets", "").startswith("ok:")
    iso = _TARGET.isoformat()
    rel_prefix = f"{iso}.assets/"
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        markdown_path = archive_root / segment / "2026" / "04" / f"{iso}.md"
        assert markdown_path.exists()
        body = markdown_path.read_text(encoding="utf-8")
        # (1) Markdown image references for every staged SVG card.
        assert f"![데이터 신뢰도]({rel_prefix}data-confidence.svg)" in body
        assert f"![시장 스냅샷]({rel_prefix}market-snapshot.svg)" in body
        assert f"![관심 자산 관련성]({rel_prefix}watchlist-relevance.svg)" in body
        for kind in ("data-confidence", "market-snapshot", "watchlist-relevance"):
            marker_id = f"{segment}.visual.{kind}"
            assert f"<!-- investo:block visual:{marker_id} -->" in body
            assert f"<!-- /investo:block visual:{marker_id} -->" in body
        # (2) SVG assets + manifests land beside the markdown.
        assets_dir = markdown_path.with_suffix(".assets")
        for kind in ("data-confidence", "market-snapshot", "watchlist-relevance"):
            asset = assets_dir / f"{kind}.svg"
            manifest = assets_dir / f"{kind}.svg.json"
            assert asset.exists(), f"missing asset: {asset}"
            assert manifest.exists(), f"missing manifest: {manifest}"
    # (3) git ``add`` picks up SVGs and their provenance manifests so
    # the commit publishes the cards alongside the markdown.
    add_call = next(call for call in git.calls if call[1] == "add")
    assert any(arg.endswith(".svg") for arg in add_call), (
        f"expected at least one SVG in git add; got {add_call!r}"
    )
    assert any(arg.endswith(".svg.json") for arg in add_call), (
        f"expected at least one SVG manifest in git add; got {add_call!r}"
    )


def test_chart_injection_routes_through_typed_pre_finalization_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    block = '\n<div class="investo-chart-block">chart</div>\n'
    monkeypatch.setattr(
        pipeline_module,
        "build_chart_artifacts",
        lambda *args, **kwargs: ChartArtifacts(block=block, sidecars=()),
    )
    briefings = {US_EQUITY: _briefing(segment=US_EQUITY)}

    rewritten, sidecars = pipeline_module._inject_chart_blocks_into_segments(
        briefings,
        target_date=_TARGET,
        anchors_by_segment={US_EQUITY: (object(),)},  # type: ignore[dict-item]
        history_by_ticker={"AAPL": (object(),)},  # type: ignore[dict-item]
    )

    marker_id = f"{US_EQUITY}.chart.market"
    markdown = rewritten[US_EQUITY].rendered_markdown
    assert f"<!-- investo:block chart:{marker_id} -->" in markdown
    assert f"<!-- /investo:block chart:{marker_id} -->" in markdown
    assert sidecars == ()


def test_chart_staging_links_descriptor_to_typed_supplement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    block = '\n<div class="investo-chart-block">chart</div>\n'
    sidecar = object()
    monkeypatch.setattr(
        pipeline_module,
        "build_chart_artifacts",
        lambda *args, **kwargs: ChartArtifacts(block=block, sidecars=(sidecar,)),
    )
    staging_root = tmp_path / "stage"
    staged_path = staging_root / "us-equity/chart.json"
    staged_path.parent.mkdir(parents=True)
    staged_path.write_bytes(b"chart")
    descriptor = StagedArtifact(
        artifact_id="us-equity.chart.market",
        segment=US_EQUITY,
        kind="chart",
        relative_public_path=PurePosixPath("us-equity/chart.json"),
        staged_path=staged_path,
        sha256="0" * 64,
    )
    monkeypatch.setattr(
        pipeline_module,
        "stage_chart_sidecar",
        lambda *args, **kwargs: descriptor,
    )
    real_apply = pipeline_module._apply_pre_finalization_supplements
    captured = []

    def _capture(*args: object, **kwargs: object) -> Briefing:
        captured.extend(kwargs["supplements"])  # type: ignore[arg-type, index]
        return real_apply(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pipeline_module, "_apply_pre_finalization_supplements", _capture)

    rewritten, descriptors = pipeline_module._inject_chart_blocks_into_segments(
        {US_EQUITY: _briefing(segment=US_EQUITY)},
        target_date=_TARGET,
        anchors_by_segment={US_EQUITY: (object(),)},  # type: ignore[dict-item]
        history_by_ticker={"AAPL": (object(),)},  # type: ignore[dict-item]
        staging_root=staging_root,
    )

    marker_id = f"{US_EQUITY}.chart.market"
    markdown = rewritten[US_EQUITY].rendered_markdown
    assert markdown.count(f"<!-- investo:block chart:{marker_id} -->") == 1
    assert markdown.count(f"<!-- /investo:block chart:{marker_id} -->") == 1
    assert descriptors == (descriptor,)
    assert captured[0].artifact_ids == (descriptor.artifact_id,)


@pytest.mark.asyncio
async def test_run_pipeline_visual_asset_failure_publishes_text_only_partial(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="AAPL closes higher",
            published_at=datetime(2026, 4, 27, 12, 1, tzinfo=UTC),
        )
    ]

    def _fail_visual_assets(*args: object, **kwargs: object) -> object:
        raise VisualAssetError("renderer unavailable")

    monkeypatch.setattr(pipeline_module, "prepare_segment_visual_assets", _fail_visual_assets)

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch(items),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.PARTIAL
    assert result.content_completeness == "complete"
    assert tuple(outcome.state for outcome in result.segment_outcomes) == (
        "finalized",
        "finalized",
        "finalized",
    )
    assert result.stages["visual_assets"] == "failed: VisualAssetError"
    assert result.stages["publish"] == "ok"
    assert result.stages["notify_briefing"] == "ok"
    assert len(publisher.calls) == 1
    assert alerter.calls == []
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        markdown = archive_root / segment / "2026" / "04" / "2026-04-27.md"
        assert markdown.exists()
        text = markdown.read_text(encoding="utf-8")
        # Text-only publishing emits no visual SVG/image asset links. (u75
        # chart-history sidecars referenced by ``data-history-src`` are a
        # separate, history-driven artifact and may still appear.) Assert no
        # markdown image link points at an asset dir, and every residual
        # ``.assets/`` reference is a chart sidecar attribute.
        for line in text.splitlines():
            if line.lstrip().startswith("!["):
                assert ".assets/" not in line
            elif ".assets/" in line:
                assert "data-history-src=" in line


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 1),
        ("1", 1),
        ("2", 2),
        ("3", 3),
        ("0", 1),
        ("4", 1),
        ("abc", 1),
    ],
)
def test_visual_prep_concurrency_env_parser(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    raw: str | None,
    expected: int,
) -> None:
    if raw is None:
        monkeypatch.delenv("INVESTO_VISUAL_PREP_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("INVESTO_VISUAL_PREP_CONCURRENCY", raw)

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        value = pipeline_module._visual_prep_concurrency_from_env()

    assert value == expected
    if raw not in {None, "1", "2", "3"}:
        assert "INVESTO_VISUAL_PREP_CONCURRENCY" in caplog.text


@pytest.mark.asyncio
async def test_stage_prepare_visual_assets_concurrency_two_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("INVESTO_VISUAL_PREP_CONCURRENCY", "2")
    monkeypatch.setattr(pipeline_module, "load_watchlist", lambda: object())
    monkeypatch.setattr(pipeline_module, "match_watchlist_items", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_module, "_load_curated_runtime_safely", lambda: None)
    started: list[MarketSegment] = []
    active = 0
    max_active = 0
    lock = threading.Lock()
    second_started = threading.Event()
    release = threading.Event()
    staging_root = tmp_path / "stage"

    def _fake_prepare(briefing: Briefing, **kwargs: object) -> PreparedVisualAssets:
        nonlocal active, max_active
        segment = kwargs["segment"]
        assert segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
        assert kwargs["staging_root"] == staging_root
        with lock:
            active += 1
            max_active = max(max_active, active)
            started.append(segment)
            if len(started) == 2:
                second_started.set()
        release.wait(timeout=1)
        with lock:
            active -= 1
        path = staging_root / segment / f"{segment}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(segment.encode())
        artifact = StagedArtifact(
            artifact_id=f"{segment}.visual.test",
            segment=segment,
            kind="visual",
            relative_public_path=PurePosixPath(f"{segment}/{segment}.svg"),
            staged_path=path,
            sha256="0" * 64,
        )
        return PreparedVisualAssets(
            briefing=briefing,
            asset_paths=(path,),
            staged_artifacts=(artifact,),
        )

    monkeypatch.setattr(pipeline_module, "prepare_segment_visual_assets", _fake_prepare)
    briefings = {
        DOMESTIC_EQUITY: _briefing(segment=DOMESTIC_EQUITY),
        US_EQUITY: _briefing(segment=US_EQUITY),
        CRYPTO: _briefing(segment=CRYPTO),
    }
    task = asyncio.create_task(
        pipeline_module._stage_prepare_segment_visual_assets(
            briefings,
            _three_segment_items(),
            _TARGET,
            staging_root=staging_root,
        )
    )
    await asyncio.wait_for(asyncio.to_thread(second_started.wait, 1), timeout=2)

    assert started == [DOMESTIC_EQUITY, US_EQUITY]
    assert max_active == 2

    release.set()
    prepared, staged_artifacts, supplements_by_segment = await task

    assert list(prepared) == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert [artifact.segment for artifact in staged_artifacts] == [
        DOMESTIC_EQUITY,
        US_EQUITY,
        CRYPTO,
    ]
    assert supplements_by_segment == {}


@pytest.mark.asyncio
async def test_stage_visual_cancellation_drains_worker_before_staging_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()
    staging_roots: list[Path] = []
    real_staging = pipeline_module.temporary_artifact_staging_root

    def blocking_prepare(briefing: Briefing, **kwargs: object) -> PreparedVisualAssets:
        staging_root = kwargs["staging_root"]
        assert isinstance(staging_root, Path)
        started.set()
        release.wait(timeout=10)
        late_path = staging_root / "late" / "worker-finished.svg"
        late_path.parent.mkdir(parents=True, exist_ok=True)
        late_path.write_bytes(b"done")
        return PreparedVisualAssets(briefing=briefing, asset_paths=(late_path,))

    monkeypatch.setattr(pipeline_module, "prepare_segment_visual_assets", blocking_prepare)

    async def prepare_in_run_owned_staging() -> None:
        with real_staging() as staging_root:
            staging_roots.append(staging_root)
            await pipeline_module._stage_prepare_segment_visual_assets(
                _segment_briefings_dict(),
                _three_segment_items(),
                _TARGET,
                staging_root=staging_root,
            )

    task = asyncio.create_task(prepare_in_run_owned_staging())
    try:
        assert await asyncio.to_thread(started.wait, 5)

        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert staging_roots and all(not root.exists() for root in staging_roots)


@pytest.mark.asyncio
async def test_run_pipeline_segment_generation_failure_publishes_remaining_segments_partial(
    archive_root: Path,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("Bitcoin"), _item("AAPL")]),
        git_runner=git,
        generate_segment=_failing_segment_generate(CRYPTO),
    )

    assert result.status == PipelineStatus.PARTIAL
    assert result.content_completeness == "partial"
    assert tuple(outcome.state for outcome in result.segment_outcomes) == (
        "finalized",
        "finalized",
        "generation_absent",
    )
    assert result.stages["generate"] == "partial: failed crypto"
    assert result.stages["generate:crypto"] == "failed: synthesis"
    assert result.stage_timings["generate:crypto"] >= 0
    assert result.stage_timings["generate:domestic-equity"] >= 0
    assert result.stage_timings["generate:us-equity"] >= 0
    assert result.stage_timings["publish:finalize"] >= 0
    assert result.stages["publish"] == "ok"
    assert result.stages["notify_briefing"] == "ok"
    assert len(publisher.calls) == 1
    assert len(alerter.calls) == 1
    assert (archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert (archive_root / US_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert not (archive_root / CRYPTO / "2026" / "04" / "2026-04-27.md").exists()
    assert "⚠️ 부분 발행: 크립토 생성 실패" in publisher.calls[0].summary_text
    assert "/archive/crypto/2026/04/2026-04-27/" not in publisher.calls[0].summary_text
    assert "push" in [call[1] for call in git.calls]


@pytest.mark.asyncio
async def test_run_pipeline_surface_quality_defect_is_contained_without_segment_drop(
    archive_root: Path,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("Bitcoin"), _item("AAPL")]),
        git_runner=git,
        generate_segment=_surface_blocking_segment_generate(CRYPTO),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.stages["publish"] == "ok"
    assert "publish:crypto" not in result.stages
    assert result.stages["notify_briefing"] == "ok"
    assert len(publisher.calls) == 1
    assert (archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert (archive_root / US_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert (archive_root / CRYPTO / "2026" / "04" / "2026-04-27.md").exists()
    assert "/archive/crypto/2026/04/2026-04-27/" in publisher.calls[0].summary_text
    assert "push" in [call[1] for call in git.calls]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 1),
        ("1", 1),
        ("2", 2),
        ("3", 3),
        ("0", 1),
        ("-1", 1),
        ("4", 1),
        ("abc", 1),
    ],
)
def test_segment_generation_concurrency_env_parser(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    raw: str | None,
    expected: int,
) -> None:
    if raw is None:
        monkeypatch.delenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", raw)

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        value = pipeline_module._segment_generation_concurrency_from_env()

    assert value == expected
    if raw not in {None, "1", "2", "3"}:
        assert "INVESTO_SEGMENT_GENERATION_CONCURRENCY" in caplog.text


def _three_segment_items() -> list[NormalizedItem]:
    return [
        _item("삼성전자[005930] 상승"),
        _item("AAPL closes higher"),
        _item("Bitcoin rises"),
    ]


def _fed_chair_fact_item() -> NormalizedItem:
    return NormalizedItem(
        source_name="fed-board-leadership",
        category="macro",
        title="Current Federal Reserve Chair: Kevin Warsh",
        summary="Kevin Warsh, Chairman",
        url="https://www.federalreserve.gov/aboutthefed/bios/board/default.htm",
        published_at=datetime(2026, 4, 27, 0, 0, tzinfo=UTC),
        raw_metadata={
            "fact_id": "fed.current_chair",
            "fact_value": "Kevin Warsh",
            "fact_label_ko": "케빈 워시",
            "fact_role": "Chairman",
            "fact_status": "fresh",
            "fact_source_tier": "S",
            "fact_expires_at": "2099-01-01T00:00:00+00:00",
            "raw_evidence_label": "Kevin Warsh, Chairman",
        },
    )


@pytest.mark.asyncio
async def test_stage_generate_segments_passes_fact_context_to_default_generator(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[MarketSegment, str]] = []

    async def _fake_default_generate_segment(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object,
        recent_context: object,
        market_anchors: object,
        carryover: object,
        bundle_context: object,
        fact_context_block: str = "",
        **_: object,
    ) -> pipeline_module.GenerationResult:
        del items, runner, data_limited, source_outcomes, recent_context
        del market_anchors, carryover, bundle_context
        captured.append((segment, fact_context_block))
        return pipeline_module.GenerationResult(briefing=_briefing(target_date, segment=segment))

    monkeypatch.setattr(
        pipeline_module,
        "_default_generate_segment_briefing",
        _fake_default_generate_segment,
    )

    briefings, failures, _, fact_bundle, _, _, _ = await pipeline_module._stage_generate_segments(
        _TARGET,
        [*_three_segment_items(), _fed_chair_fact_item()],
    )

    assert failures == {}
    assert list(briefings) == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert fact_bundle.get("fed.current_chair") is not None
    assert [segment for segment, _ in captured] == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert all("fed.current_chair: Kevin Warsh" in block for _, block in captured)
    assert (archive_root / "_meta" / "fact_snapshots.jsonl").exists()


@pytest.mark.asyncio
async def test_stage_generate_segments_passes_explicit_watchlist_to_default_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.briefing.watchlist import WatchlistConfig

    expected_watchlist = WatchlistConfig(tickers=("NVDA",))
    captured: list[object] = []

    monkeypatch.setattr(pipeline_module, "load_watchlist", lambda: expected_watchlist)

    async def _fake_default_generate_segment(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object,
        recent_context: object,
        market_anchors: object,
        carryover: object,
        bundle_context: object,
        fact_context_block: str = "",
        **kwargs: object,
    ) -> pipeline_module.GenerationResult:
        del items, runner, data_limited, source_outcomes, recent_context
        del market_anchors, carryover, bundle_context, fact_context_block
        captured.append(kwargs["watchlist_config"])
        return pipeline_module.GenerationResult(briefing=_briefing(target_date, segment=segment))

    monkeypatch.setattr(
        pipeline_module,
        "_default_generate_segment_briefing",
        _fake_default_generate_segment,
    )

    briefings, failures, _, _, _, _, _ = await pipeline_module._stage_generate_segments(
        _TARGET,
        _three_segment_items(),
    )

    assert failures == {}
    assert list(briefings) == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert captured == [expected_watchlist, expected_watchlist, expected_watchlist]


@pytest.mark.asyncio
async def test_stage_generate_segments_default_concurrency_is_serial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", raising=False)
    active = 0
    max_active = 0
    started: list[MarketSegment] = []

    async def _serial_probe(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del items, runner, data_limited, source_outcomes, recent_context, market_anchors
        del carryover, bundle_context
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        started.append(segment)
        await asyncio.sleep(0)
        active -= 1
        return _briefing(target_date, segment=segment)

    briefings, failures, _, _, _, _, timings = await pipeline_module._stage_generate_segments(
        _TARGET,
        _three_segment_items(),
        generate_segment=_serial_probe,
    )

    assert started == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert max_active == 1
    assert list(briefings) == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert failures == {}
    assert all(timings[f"generate:{segment}"] >= 0 for segment in pipeline_module.SEGMENT_ORDER)


@pytest.mark.asyncio
async def test_stage_generate_segments_concurrency_two_starts_two_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", "2")
    started: list[MarketSegment] = []
    release = asyncio.Event()
    second_started = asyncio.Event()
    active = 0
    max_active = 0

    async def _blocking_probe(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del items, runner, data_limited, source_outcomes, recent_context, market_anchors
        del carryover, bundle_context
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        started.append(segment)
        if len(started) == 2:
            second_started.set()
        await release.wait()
        active -= 1
        return _briefing(target_date, segment=segment)

    task = asyncio.create_task(
        pipeline_module._stage_generate_segments(
            _TARGET,
            _three_segment_items(),
            generate_segment=_blocking_probe,
        )
    )
    await asyncio.wait_for(second_started.wait(), timeout=1.0)

    assert started == [DOMESTIC_EQUITY, US_EQUITY]
    assert max_active == 2

    release.set()
    briefings, failures, _, _, _, _, timings = await task

    assert started == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert list(briefings) == [DOMESTIC_EQUITY, US_EQUITY, CRYPTO]
    assert failures == {}
    assert all(timings[f"generate:{segment}"] >= 0 for segment in pipeline_module.SEGMENT_ORDER)


@pytest.mark.asyncio
async def test_stage_generate_segments_programmer_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", "3")

    async def _broken(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del target_date, items, runner, data_limited, source_outcomes, recent_context
        del market_anchors, carryover, bundle_context
        if segment == US_EQUITY:
            raise RuntimeError("programmer bug")
        return _briefing(_TARGET, segment=segment)

    with pytest.raises(RuntimeError, match="programmer bug"):
        await pipeline_module._stage_generate_segments(
            _TARGET,
            _three_segment_items(),
            generate_segment=_broken,
        )


@pytest.mark.asyncio
async def test_stage_generate_segments_all_failures_raise_first_segment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_SEGMENT_GENERATION_CONCURRENCY", "3")

    async def _always_fails(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del target_date, items, runner, data_limited, source_outcomes, recent_context
        del market_anchors, carryover, bundle_context
        raise BriefingGenerationError(
            stage="synthesis",
            attempt_count=2,
            last_stderr=f"{segment} failed",
            cause=None,
        )

    with pytest.raises(BriefingGenerationError) as exc_info:
        await pipeline_module._stage_generate_segments(
            _TARGET,
            _three_segment_items(),
            generate_segment=_always_fails,
        )

    assert exc_info.value.last_stderr == f"{DOMESTIC_EQUITY} failed"


def test_rewrite_segment_nav_for_partial_publish_labels_missing_segments() -> None:
    briefing = _briefing().model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-27 크립토 시황\n\n"
                "**세그먼트**: [국내 증시](../../../domestic-equity/2026/04/2026-04-27.md) "
                "| [미국 증시](../../../us-equity/2026/04/2026-04-27.md) "
                "| [크립토](2026-04-27.md)\n\n"
                "## ① 요약\n본문\n\n"
                f"{DISCLAIMER}"
            )
        }
    )

    rewritten = pipeline_module._assemble_phase_one_presentation_briefings(
        {CRYPTO: briefing},
        target_date=_TARGET,
        active_segments=(CRYPTO,),
    )

    markdown = rewritten[CRYPTO].rendered_markdown
    assert (
        "**세그먼트**: 국내 증시(미발행) | 미국 증시(미발행) | [크립토](2026-04-27.md)"
    ) in markdown
    assert "domestic-equity/2026/04/2026-04-27.md" not in markdown
    assert "us-equity/2026/04/2026-04-27.md" not in markdown


@pytest.mark.asyncio
async def test_run_pipeline_segment_disclaimer_failure_withholds_only_failed_segment(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    def fake_verify_disclaimer(
        markdown: str,
        segment: MarketSegment | None = None,
        *,
        legacy: bool = False,
    ) -> bool:
        del markdown, legacy
        return segment != US_EQUITY

    monkeypatch.setattr(
        public_document_module,
        "verify_disclaimer",
        fake_verify_disclaimer,
    )

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.PARTIAL
    assert result.content_completeness == "partial"
    assert tuple(outcome.state for outcome in result.segment_outcomes) == (
        "finalized",
        "trust_blocked",
        "finalized",
    )
    assert result.stages["publish:us-equity"] == "failed: PublicDocumentTrustGate"
    assert result.stages["publish"] == "ok"
    assert result.stages["notify_briefing"] == "ok"
    assert len(publisher.calls) == 1
    assert git.calls
    assert (archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert not (archive_root / US_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert (archive_root / CRYPTO / "2026" / "04" / "2026-04-27.md").exists()


@pytest.mark.asyncio
async def test_run_pipeline_segment_summary_quality_failure_withholds_only_failed_segment(
    archive_root: Path,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    async def broken_segment_generate(
        target_date: date,
        items: list[NormalizedItem],
        runner: object,
        segment: MarketSegment,
        data_limited: bool,
        source_outcomes: object = (),
        recent_context: object = None,
        market_anchors: object = (),
        carryover: object = None,
        bundle_context: object = None,
    ) -> Briefing:
        del source_outcomes
        del recent_context
        del market_anchors
        del carryover
        del bundle_context
        briefing = _briefing(target_date, segment=segment)
        if segment == US_EQUITY:
            return briefing.model_copy(
                update={
                    "rendered_markdown": briefing.rendered_markdown.replace(
                        "> **주의할 점**: 관전\n",
                        "",
                    )
                }
            )
        return briefing

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=broken_segment_generate,
    )

    assert result.status == PipelineStatus.PARTIAL
    assert result.stages["publish:us-equity"] == "failed: PublicDocumentTrustGate"
    assert result.stages["publish"] == "ok"
    assert result.stages["notify_briefing"] == "ok"
    assert alerter.calls == []
    assert len(publisher.calls) == 1
    assert git.calls
    assert (archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert not (archive_root / US_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert (archive_root / CRYPTO / "2026" / "04" / "2026-04-27.md").exists()


@pytest.mark.asyncio
async def test_run_pipeline_segment_publish_io_failure_rolls_back_written_files(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    domestic_path = archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md"
    domestic_path.parent.mkdir(parents=True)
    domestic_path.write_text("previous domestic", encoding="utf-8")
    prior_asset = domestic_path.with_suffix(".assets") / "data-confidence.svg"
    prior_asset.parent.mkdir(parents=True)
    prior_asset.write_bytes(b"previous visual")
    staging_roots: list[Path] = []
    real_staging = pipeline_module.temporary_artifact_staging_root

    @contextmanager
    def observe_staging() -> Iterator[Path]:
        with real_staging() as root:
            staging_roots.append(root)
            yield root

    monkeypatch.setattr(
        pipeline_module,
        "temporary_artifact_staging_root",
        observe_staging,
    )

    def fake_write_finalized_document(
        document: public_document_module.FinalizedPublicDocument,
    ) -> Path:
        segment = document.segment
        target_date = document.target_date
        path = archive_root / segment / "2026" / "04" / "2026-04-27.md"
        if segment == US_EQUITY:
            raise PublisherIOError(target_date=target_date, path=path, cause=OSError("boom"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"new {segment}", encoding="utf-8")
        return path

    monkeypatch.setattr(
        pipeline_module,
        "write_finalized_document",
        fake_write_finalized_document,
    )

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"] == "failed: PublisherIOError"
    assert result.publication_committed is False
    assert result.stages["notify_briefing"] == "skipped"
    assert domestic_path.read_text(encoding="utf-8") == "previous domestic"
    assert prior_asset.read_bytes() == b"previous visual"
    assert {
        path
        for path in archive_root.rglob("*")
        if path.is_file() and not path.is_relative_to(archive_root / "_meta")
    } == {
        domestic_path,
        prior_asset,
    }
    assert staging_roots and all(not root.exists() for root in staging_roots)
    assert not (archive_root / US_EQUITY / "2026" / "04" / "2026-04-27.md").exists()
    assert not (archive_root / CRYPTO / "2026" / "04" / "2026-04-27.md").exists()
    assert publisher.calls == []
    assert git.calls == []


@pytest.mark.asyncio
async def test_run_pipeline_finalization_e8_changes_no_public_destination(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    prior_asset = (
        archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.assets" / "data-confidence.svg"
    )
    prior_asset.parent.mkdir(parents=True)
    prior_asset.write_bytes(b"previous visual")
    staging_roots: list[Path] = []
    real_staging = pipeline_module.temporary_artifact_staging_root

    @contextmanager
    def observe_staging() -> Iterator[Path]:
        with real_staging() as root:
            staging_roots.append(root)
            yield root

    def fail_finalization(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise pipeline_module.PublicDocumentFinalizationError(
            target_date=_TARGET,
            segment=None,
            phase="bundle",
            issue_codes=("bundle.zero_survivors",),
        )

    monkeypatch.setattr(
        pipeline_module,
        "temporary_artifact_staging_root",
        observe_staging,
    )
    monkeypatch.setattr(pipeline_module, "finalize_public_bundle", fail_finalization)

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"] == "failed: PublicDocumentFinalizationError"
    assert result.stages["notify_briefing"] == "skipped"
    assert prior_asset.read_bytes() == b"previous visual"
    assert sorted(
        path
        for path in archive_root.rglob("*")
        if path.is_file() and not path.is_relative_to(archive_root / "_meta")
    ) == [prior_asset]
    assert staging_roots and all(not root.exists() for root in staging_roots)
    assert publisher.calls == []
    assert git.calls == []


@pytest.mark.asyncio
async def test_run_pipeline_promotion_failure_rolls_back_every_public_destination(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.publisher import staged_artifacts as staged_artifacts_module

    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()
    prior_asset = (
        archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.assets" / "data-confidence.svg"
    )
    prior_asset.parent.mkdir(parents=True)
    prior_asset.write_bytes(b"previous visual")
    unrelated = archive_root / "operator-note.txt"
    unrelated.write_bytes(b"untouched")

    def public_bytes() -> dict[Path, bytes]:
        return {
            path.relative_to(archive_root): path.read_bytes()
            for path in archive_root.rglob("*")
            if path.is_file() and not path.is_relative_to(archive_root / "_meta")
        }

    before = public_bytes()
    attempts: list[Path] = []
    real_write = staged_artifacts_module.write_atomic_bytes

    def fail_second_promotion(path: Path, payload: bytes) -> None:
        attempts.append(path)
        if len(attempts) == 2:
            raise OSError("injected second promotion failure")
        real_write(path, payload)

    staging_roots: list[Path] = []
    real_staging = pipeline_module.temporary_artifact_staging_root

    @contextmanager
    def observe_staging() -> Iterator[Path]:
        with real_staging() as root:
            staging_roots.append(root)
            yield root

    monkeypatch.setattr(
        staged_artifacts_module,
        "write_atomic_bytes",
        fail_second_promotion,
    )
    monkeypatch.setattr(
        pipeline_module,
        "temporary_artifact_staging_root",
        observe_staging,
    )

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"] == "failed: PublisherIOError"
    assert result.publication_committed is False
    assert len(attempts) == 2
    assert public_bytes() == before
    assert staging_roots and all(not root.exists() for root in staging_roots)
    assert publisher.calls == []
    assert git.calls == []


@pytest.mark.asyncio
async def test_publish_cancellation_after_promotion_drains_writer_then_rolls_back(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = _SuccessfulGitRunner()
    prior_asset = (
        archive_root / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.assets" / "data-confidence.svg"
    )
    prior_asset.parent.mkdir(parents=True)
    prior_asset.write_bytes(b"previous visual")
    writer_started = threading.Event()
    release_writer = threading.Event()
    staging_roots: list[Path] = []
    real_staging = pipeline_module.temporary_artifact_staging_root

    def fake_promote(
        bundle: object,
        *,
        staging_root: Path,
        archive_root: Path,
        snapshots: dict[Path, bytes | None],
    ) -> tuple[Path, ...]:
        del bundle
        assert staging_root.exists()
        assert prior_asset.is_relative_to(archive_root)
        snapshots[prior_asset] = prior_asset.read_bytes()
        prior_asset.write_bytes(b"promoted visual")
        return (prior_asset,)

    document = SimpleNamespace(
        segment=DOMESTIC_EQUITY,
        briefing=_briefing(segment=DOMESTIC_EQUITY),
    )

    def blocking_write(value: object) -> Path:
        assert value is document
        writer_started.set()
        release_writer.wait(timeout=10)
        path = archive_root / DOMESTIC_EQUITY / "2026" / "04" / f"{_TARGET.isoformat()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document.briefing.rendered_markdown, encoding="utf-8")
        return path

    monkeypatch.setattr(pipeline_module, "promote_finalized_bundle_artifacts", fake_promote)
    monkeypatch.setattr(pipeline_module, "write_finalized_document", blocking_write)

    async def publish_from_run_owned_staging() -> None:
        with real_staging() as staging_root:
            staging_roots.append(staging_root)
            await pipeline_module._stage_publish_segments(
                {DOMESTIC_EQUITY: _briefing(segment=DOMESTIC_EQUITY)},
                _TARGET,
                git_runner=git,
                phase_one_complete=True,
                finalized_bundle=SimpleNamespace(
                    documents=(document,),
                    promotion_manifest=(object(),),
                ),
                staging_root=staging_root,
            )

    task = asyncio.create_task(publish_from_run_owned_staging())
    try:
        assert await asyncio.to_thread(writer_started.wait, 5)
        assert prior_asset.read_bytes() == b"promoted visual"

        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release_writer.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert prior_asset.read_bytes() == b"previous visual"
    assert sorted(
        path
        for path in archive_root.rglob("*")
        if path.is_file() and not path.is_relative_to(archive_root / "_meta")
    ) == [prior_asset]
    assert staging_roots and all(not root.exists() for root in staging_roots)
    assert git.calls == []


@pytest.mark.asyncio
async def test_run_pipeline_publish_rollback_never_touches_image_ledger(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEBT-085 regression pin — u137 Step 4 rollback exclusion.

    Image-stage outputs join the publish git-add list but are EXCLUDED
    from the rollback snapshots (u137 R3 never-drop / R9). If a future
    edit registers ``extra_commit_paths`` into ``snapshots`` with
    ``previous_bytes=None`` (the ``asset_paths`` idiom), a publish-gate
    rollback would DELETE the merge-rewrite ledger — this test goes red
    in exactly that case: it pre-seeds a prior-run ledger row, lets the
    run merge a NEW candidate into the same date file, forces a
    ``PublisherIOError`` rollback, and asserts the ledger (both rows)
    and ``index.json`` survive byte-intact while the segment markdown
    writes ARE rolled back.
    """
    from investo.visuals.image_library import (
        ImageCandidateRecord,
        append_candidates,
        candidate_id_for_url,
    )

    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    # Pre-seed the date ledger with a prior-run candidate (a DIFFERENT
    # image URL), via the real merge-rewrite writer under the isolated
    # archive root the pipeline's _image_candidates_root() resolves to.
    ledger_root = archive_root / "_meta" / "image_candidates"
    preseeded_url = "https://img.yna.co.kr/photo/reuters/OLD001.jpg"
    preseeded_item = NormalizedItem(
        source_name="yonhap-market",
        category="news",
        title="전일 이미지 기사",
        url="https://www.yna.co.kr/view/OLD001",
        published_at=datetime(2026, 4, 27, 9, 0, tzinfo=UTC),
        raw_metadata={"image_url": preseeded_url},
    )
    append_candidates(_TARGET, {"domestic-equity": [preseeded_item]}, ledger_root=ledger_root)
    ledger_path = ledger_root / "2026" / "2026-04-27.jsonl"
    preseeded_line = ledger_path.read_text(encoding="utf-8").splitlines()[0]

    # This run carries one NEW image-bearing item (different candidate).
    new_url = "https://img.yna.co.kr/photo/reuters/NEW001.jpg"
    image_item = NormalizedItem(
        source_name="yonhap-market",
        category="news",
        title="오늘 이미지 기사",
        url="https://www.yna.co.kr/view/NEW001",
        published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
        raw_metadata={"image_url": new_url},
    )

    def fake_write_finalized_document(
        document: public_document_module.FinalizedPublicDocument,
    ) -> Path:
        segment = document.segment
        target_date = document.target_date
        path = archive_root / segment / "2026" / "04" / "2026-04-27.md"
        if segment == US_EQUITY:
            raise PublisherIOError(target_date=target_date, path=path, cause=OSError("boom"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"new {segment}", encoding="utf-8")
        return path

    monkeypatch.setattr(
        pipeline_module,
        "write_finalized_document",
        fake_write_finalized_document,
    )

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL"), image_item]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    # The publish failure fired and the rollback provably ran (the
    # markdown writes were reversed) …
    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"] == "failed: PublisherIOError"
    assert not list(archive_root.rglob("*.md"))
    # … the image stage itself had succeeded before publish: 1 new
    # candidate merged, 2 total indexed (preseeded + new).
    assert result.stages["image_candidates"] == "ok: candidates=1 indexed=2 stored=0"

    # DEBT-085 core: rollback must not touch the ledger at all.
    assert ledger_path.exists()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert preseeded_line in lines  # pre-seeded row byte-preserved (R3)
    rows = [ImageCandidateRecord.model_validate_json(line) for line in lines]
    candidate_ids = {row.candidate_id for row in rows}
    assert candidate_id_for_url(preseeded_url) in candidate_ids
    assert candidate_id_for_url(new_url) in candidate_ids  # merged row survives too
    assert (ledger_root / "index.json").exists()


@pytest.mark.asyncio
async def test_run_pipeline_stages_coverage_log_for_commit(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DEBT-088 — this run's coverage line is appended BEFORE publish and
    its path joins the ``git add`` argv (mirrors the ``*.svg.json``
    staging assertion), so the diagnostics log is actually committed.
    """
    # No env override — the path derives from the (tmp) ARCHIVE_ROOT,
    # which is the in-repo shape production uses.
    monkeypatch.delenv("INVESTO_COVERAGE_LOG_PATH", raising=False)
    coverage_path = archive_root / "_meta" / "coverage.jsonl"

    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.SUCCESS
    # The line for THIS run exists (hoisted ahead of publish) …
    assert coverage_path.exists()
    assert _TARGET.isoformat() in coverage_path.read_text(encoding="utf-8")
    # … and its path was staged in the same commit.
    add_call = next(c for c in git.calls if c[1] == "add")
    assert any("coverage.jsonl" in arg for arg in add_call)


@pytest.mark.asyncio
async def test_publish_rollback_never_touches_coverage_log(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DEBT-088 + DEBT-085 shape — the append-only coverage log rides
    ``extra_commit_paths``, so a publish-gate rollback must NOT delete
    it (registering it in the rollback snapshots with
    ``previous_bytes=None`` would wipe committed diagnostics history).
    """
    monkeypatch.delenv("INVESTO_COVERAGE_LOG_PATH", raising=False)
    coverage_path = archive_root / "_meta" / "coverage.jsonl"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    preseeded = '{"target_date": "2026-04-20", "outcomes": []}\n'
    coverage_path.write_text(preseeded, encoding="utf-8")

    def fake_write_finalized_document(
        document: public_document_module.FinalizedPublicDocument,
    ) -> Path:
        segment = document.segment
        target_date = document.target_date
        path = archive_root / segment / "2026" / "04" / "2026-04-27.md"
        if segment == US_EQUITY:
            raise PublisherIOError(target_date=target_date, path=path, cause=OSError("boom"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"new {segment}", encoding="utf-8")
        return path

    monkeypatch.setattr(
        pipeline_module,
        "write_finalized_document",
        fake_write_finalized_document,
    )

    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=_SuccessfulGitRunner(),
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"] == "failed: PublisherIOError"
    assert not list(archive_root.rglob("*.md"))  # rollback provably ran
    # Coverage log survives with the pre-seeded row AND this run's row.
    assert coverage_path.exists()
    content = coverage_path.read_text(encoding="utf-8")
    assert preseeded.strip() in content
    assert _TARGET.isoformat() in content


@pytest.mark.asyncio
async def test_coverage_log_outside_repo_is_not_staged(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DEBT-088 — an operator-local ``INVESTO_COVERAGE_LOG_PATH`` outside
    the repo must never enter the ``git add`` list."""
    outside = tmp_path / "operator_local" / "coverage.jsonl"
    monkeypatch.setenv("INVESTO_COVERAGE_LOG_PATH", str(outside))

    git = _SuccessfulGitRunner()
    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert outside.exists()  # still written — only staging is skipped
    add_call = next(c for c in git.calls if c[1] == "add")
    assert not any("coverage.jsonl" in arg for arg in add_call)


@pytest.mark.asyncio
async def test_stage_publish_segments_stages_latest_index_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = _SuccessfulGitRunner()
    index_paths = (Path("site_docs/index.md"), Path("archive/index.md"))

    def fake_archive_path(target_date: date, *, segment: MarketSegment | None = None) -> Path:
        assert segment is not None
        return Path("archive") / segment / "2026" / "04" / "2026-04-27.md"

    def fake_write_briefing(
        briefing: Briefing,
        target_date: date,
        *,
        segment: MarketSegment | None = None,
    ) -> Path:
        assert segment is not None
        return fake_archive_path(target_date, segment=segment)

    def fake_update_latest_index_pages(
        target_date: date,
        *,
        segment_briefings: dict[MarketSegment, Briefing] | None = None,
        heatmap_svg: str | None = None,
    ) -> tuple[Path, ...]:
        assert target_date == _TARGET
        # u29 site-discovery-v2 — orchestrator now threads the segmented
        # briefings AND a precomputed heatmap SVG into the index update so
        # the hero block + Archive heatmap both refresh atomically with
        # the segmented archive write.
        assert segment_briefings is not None
        assert set(segment_briefings.keys()) == {DOMESTIC_EQUITY, US_EQUITY, CRYPTO}
        assert heatmap_svg is not None and heatmap_svg.startswith("<svg")
        return index_paths

    def fake_build_heatmap(target_date: date) -> str:
        assert target_date == _TARGET
        return "<svg/>"

    def fake_write_og_card(
        target_date: date,
        briefings: dict[MarketSegment, Briefing],
    ) -> Path:
        assert target_date == _TARGET
        assert set(briefings.keys()) == {DOMESTIC_EQUITY, US_EQUITY, CRYPTO}
        return Path("site_docs/assets/og-card.svg")

    monkeypatch.setattr(pipeline_module, "compute_archive_path", fake_archive_path)
    monkeypatch.setattr(pipeline_module, "write_briefing", fake_write_briefing)
    monkeypatch.setattr(
        pipeline_module,
        "update_latest_index_pages",
        fake_update_latest_index_pages,
    )
    monkeypatch.setattr(pipeline_module, "_build_publish_heatmap_svg", fake_build_heatmap)
    monkeypatch.setattr(pipeline_module, "write_og_card", fake_write_og_card)
    monkeypatch.setattr(pipeline_module, "_read_existing_bytes", lambda path: b"previous")

    await pipeline_module._stage_publish_segments(
        {
            DOMESTIC_EQUITY: _briefing(segment=DOMESTIC_EQUITY),
            US_EQUITY: _briefing(segment=US_EQUITY),
            CRYPTO: _briefing(segment=CRYPTO),
        },
        _TARGET,
        git_runner=git,
    )

    assert any("site_docs/index.md" in call for call in git.calls)
    assert any("archive/index.md" in call for call in git.calls)
    # u29 OG card path is staged with the same commit.
    assert any("site_docs/assets/og-card.svg" in call for call in git.calls)


@pytest.mark.asyncio
async def test_run_pipeline_segmented_summary_build_failure_yields_partial(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()
    git = _SuccessfulGitRunner()

    def broken_summary(*args: object, **kwargs: object) -> str:
        raise ValueError("footer too long")

    monkeypatch.setattr(pipeline_module, "build_segmented_summary", broken_summary)

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("AAPL")]),
        git_runner=git,
        generate_segment=_success_segment_generate([]),
    )

    assert result.status == PipelineStatus.PARTIAL
    assert result.stages["publish"] == "ok"
    assert result.stages["notify_briefing"].startswith("failed: segmented summary build failed")
    assert publisher.calls == []
    assert len(alerter.calls) == 1
    assert alerter.calls[0].stage == "notify_briefing"
    assert alerter.calls[0].error_type == "NotifyDeliveryError"
    assert "push" in [call[1] for call in git.calls]


@pytest.mark.asyncio
async def test_run_pipeline_resolves_target_date_when_omitted(archive_root: Path) -> None:
    """target_date=None → ``resolve_target_date(now_utc)`` is consulted."""
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    result = await run_pipeline(
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    # The resolved date should be a weekday within the last few days
    # of "today" KST.
    assert result.target_date.weekday() < 5


# ---------------------------------------------------------------------------
# AC-003-1 — per-source partial collect → SUCCESS (not PARTIAL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_per_source_partial_collect_yields_success(
    archive_root: Path,
) -> None:
    """Per-source failure already swallowed inside u1's aggregator;
    orchestrator sees a non-empty list → SUCCESS, NO downgrade to
    PARTIAL.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    # Simulate "3 sources registered, only 1 succeeded" — orchestrator
    # sees 1 item and proceeds normally.
    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item("survivor")]),
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert alerter.calls == []


# ---------------------------------------------------------------------------
# AC-003-2 — empty collect → FAILED + alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_empty_collect_fails_with_alert(
    archive_root: Path,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([]),  # empty
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.briefing_url is None
    assert result.stages["collect"] == "failed: empty"
    # Generate / publish / notify all skipped.
    assert result.stages["generate"] == "skipped"
    assert result.stages["publish"] == "skipped"
    assert result.stages["notify_briefing"] == "skipped"
    # Exactly 1 alert with stage="collect".
    assert len(alerter.calls) == 1
    assert alerter.calls[0].stage == "collect"
    assert alerter.calls[0].error_type == "EmptyCollectError"
    # Publisher NEVER called.
    assert publisher.calls == []


# ---------------------------------------------------------------------------
# AC-003-3 — generate fail → FAILED + alert
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", ["classification", "synthesis", "post_validation", "budget"])
@pytest.mark.asyncio
async def test_run_pipeline_generate_failure_fails_with_alert(
    archive_root: Path, stage: str
) -> None:
    """All 4 BGE stages → FAILED + alert(stage='generate')."""
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_failing_bge_generate(stage),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.briefing_url is None
    assert result.stages["generate"] == f"failed: {stage}"
    assert result.stages["publish"] == "skipped"
    assert result.stages["notify_briefing"] == "skipped"
    # Alert with stage="generate" and BGE error_type.
    assert len(alerter.calls) == 1
    assert alerter.calls[0].stage == "generate"
    assert alerter.calls[0].error_type == "BriefingGenerationError"
    assert publisher.calls == []


@pytest.mark.asyncio
async def test_run_pipeline_generate_failure_logs_failure_details(
    archive_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Actions logs should expose the real u2 stage/cause/stderr."""
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    async def _failing_generate(
        target_date: date,
        items: object,
        runner: object,
    ) -> Briefing:
        raise BriefingGenerationError(
            stage="classification",
            attempt_count=2,
            last_stderr="claude stderr",
            last_stdout="not json",
            cause=ValueError("bad claude output"),
        )

    with caplog.at_level(logging.ERROR, logger="investo.orchestrator.pipeline"):
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_success_fetch([_item()]),
            git_runner=_SuccessfulGitRunner(),
            generate=_failing_generate,
        )

    assert result.status == PipelineStatus.FAILED
    record = next(
        record for record in caplog.records if record.getMessage().startswith("[generate] failed")
    )
    assert "stage=classification" in record.getMessage()
    assert "attempts=2" in record.getMessage()
    assert "cause_type=ValueError" in record.getMessage()
    assert "last_stderr=claude stderr" in record.getMessage()
    assert "last_stdout=not json" in record.getMessage()
    assert record.briefing_stage == "classification"
    assert record.attempt_count == 2
    assert record.cause_type == "ValueError"
    assert record.last_stderr == "claude stderr"
    assert record.last_stdout == "not json"


# ---------------------------------------------------------------------------
# AC-003-4 — disclaimer fail → FAILED + alert (no notify)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_publisher_disclaimer_error_fails_with_alert(
    archive_root: Path,
) -> None:
    """Generate produces a Briefing whose rendered_markdown lacks the
    disclaimer → write_briefing raises PublisherDisclaimerError →
    FAILED + alert(stage='publish').
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    async def _bad_briefing_generate(
        target_date: date,
        items: object,
        runner: object,
    ) -> Briefing:
        # Construct a Briefing with rendered_markdown that does NOT
        # include the canonical DISCLAIMER substring.
        return Briefing.model_construct(
            target_date=target_date,
            market_summary="x",
            key_issues="x",
            sector_flow="x",
            indicators_events="x",
            notable_tickers="x",
            today_watch="x",
            disclaimer="not the canonical disclaimer",
            rendered_markdown="## ① 요약\n\n본문\n\n## ⑦ 면책조항\n없음",
        )

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_bad_briefing_generate,
    )

    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"].startswith("failed: PublisherDisclaimerError")
    assert result.stages["notify_briefing"] == "skipped"
    assert len(alerter.calls) == 1
    assert alerter.calls[0].stage == "publish"
    assert alerter.calls[0].error_type == "PublisherDisclaimerError"
    assert publisher.calls == []


# ---------------------------------------------------------------------------
# AC-003-5 — git push fail → FAILED + alert with last_stderr in message
# ---------------------------------------------------------------------------


class _PushFailingGitRunner:
    """add+commit succeed; push always fails (rc=1, stderr populated)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[1] == "push":
            return subprocess.CompletedProcess(
                args=args, returncode=1, stdout="", stderr="fatal: unable to access remote"
            )
        # On retry attempts, commit returns idempotent-noop signal.
        if args[1] == "commit" and len([c for c in self.calls if c[1] == "commit"]) >= 2:
            return subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout="nothing to commit, working tree clean\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


@pytest.mark.asyncio
async def test_run_pipeline_git_push_failure_fails_with_alert(
    archive_root: Path,
) -> None:
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_PushFailingGitRunner(),
        generate=_success_generate(),
    )

    assert result.status == PipelineStatus.FAILED
    assert result.stages["publish"].startswith("failed: PublisherGitError")
    assert result.stages["notify_briefing"] == "skipped"
    assert len(alerter.calls) == 1
    assert alerter.calls[0].stage == "publish"
    assert alerter.calls[0].error_type == "PublisherGitError"
    assert publisher.calls == []


# ---------------------------------------------------------------------------
# AC-003-6 + AC-003-8 — notify fail → PARTIAL with operator visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_notify_failure_yields_partial_and_alerts_operator(
    archive_root: Path,
) -> None:
    """Publish succeeds, notify_briefing fails → PARTIAL and operator alert.

    The exit-code contract still treats PARTIAL as non-fatal, but the
    operator must see that the public channel did not receive the briefing.
    """
    publisher = _FakePublisher(result=SendResult(ok=False, error="rate limited"))
    alerter = _FakeAlerter()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    assert result.status == PipelineStatus.PARTIAL
    assert result.briefing_url is not None
    assert result.stages["publish"] == "ok"
    assert result.stages["notify_briefing"].startswith("failed: rate limited")
    assert len(alerter.calls) == 1
    assert alerter.calls[0].stage == "notify_briefing"
    assert alerter.calls[0].error_type == "NotifyDeliveryError"
    assert "rate limited" in alerter.calls[0].error_message


# ---------------------------------------------------------------------------
# AC-003-9 — per-source partial does NOT yield PARTIAL
# (already covered above, but pin the explicit invariant)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_per_source_partial_is_success_not_partial(
    archive_root: Path,
) -> None:
    """Pin the AC-003-9 invariant explicitly — partial collect with
    successful subsequent stages MUST NOT downgrade to PARTIAL.
    PARTIAL is reserved for the publish-ok + notify-fail case.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter()

    result = await run_pipeline(
        _TARGET,
        publisher=publisher,
        alerter=alerter,
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),  # only 1 of 3 sources, hypothetically
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    assert result.status == PipelineStatus.SUCCESS
    assert result.status != PipelineStatus.PARTIAL


# ---------------------------------------------------------------------------
# AC-003-10 — alerter delivery failure during FAILED run does NOT change status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_alert_failure_during_failed_run_keeps_failed(
    archive_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty collect → FAILED. Alerter returns ``ok=False`` → status
    STAYS FAILED (not changed); WARNING logged.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter(result=SendResult(ok=False, error="alerter down"))

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_success_fetch([]),  # empty
            git_runner=_SuccessfulGitRunner(),
            generate=_success_generate(),
        )

    assert result.status == PipelineStatus.FAILED
    # Alert was retried but still failed.
    assert len(alerter.calls) == 2
    # WARNING log records the alert delivery failure.
    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.name == "investo.orchestrator.pipeline" and r.levelno == logging.WARNING
    ]
    assert any("alert delivery failed" in m for m in warnings)


@pytest.mark.asyncio
async def test_run_pipeline_alert_delivery_retries_then_succeeds(
    archive_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-007 retry slice: transient operator-alert send failure is
    retried without changing the underlying FAILED pipeline status.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter(
        results=[
            SendResult(ok=False, error="temporary telegram failure"),
            SendResult(ok=True, message_id=99),
        ]
    )

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_success_fetch([]),
            git_runner=_SuccessfulGitRunner(),
            generate=_success_generate(),
        )

    assert result.status == PipelineStatus.FAILED
    assert len(alerter.calls) == 2
    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.name == "investo.orchestrator.pipeline" and r.levelno == logging.WARNING
    ]
    assert not any("alert delivery failed" in m for m in warnings)


@pytest.mark.asyncio
async def test_run_pipeline_alert_raise_during_failed_run_keeps_failed(
    archive_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If the alerter itself RAISES (programmer error in the stub),
    the underlying stage failure is not masked — pipeline still
    returns FAILED with WARNING logged.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter(raise_exc=RuntimeError("alerter bug"))

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_success_fetch([]),
            git_runner=_SuccessfulGitRunner(),
            generate=_success_generate(),
        )

    assert result.status == PipelineStatus.FAILED
    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.name == "investo.orchestrator.pipeline" and r.levelno == logging.WARNING
    ]
    assert any("alert raised unexpected" in m for m in warnings)


@pytest.mark.parametrize(
    "alert_exc",
    [
        # H1 regression — broaden _safe_alert exception list. Each of
        # these used to slip through the narrow (OSError, RuntimeError,
        # ValueError) tuple and propagate from run_pipeline, masking
        # the underlying stage failure. The fix catches Exception so
        # all of these are absorbed.
        OSError("transport down"),  # already caught pre-fix.
        RuntimeError("publisher bug"),  # already caught pre-fix.
        ValueError("pydantic validation in send"),  # already caught pre-fix.
        # The new coverage — these used to LEAK:
        TypeError("u4 contract bug"),
        AttributeError("attr"),
        ZeroDivisionError("synth"),
    ],
)
@pytest.mark.asyncio
async def test_run_pipeline_safe_alert_swallows_arbitrary_exceptions(
    archive_root: Path,
    alert_exc: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """H1 regression — ``_safe_alert`` catches ``Exception`` per the
    documented intent, so the underlying stage failure is never
    masked by an alerter bug. ``BaseException`` (KeyboardInterrupt,
    SystemExit, asyncio.CancelledError) still propagates.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter(raise_exc=alert_exc)

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.pipeline"):
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_success_fetch([]),
            git_runner=_SuccessfulGitRunner(),
            generate=_success_generate(),
        )

    # Underlying stage failure preserved — pipeline returned FAILED,
    # not raised the alert exception.
    assert result.status == PipelineStatus.FAILED
    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.name == "investo.orchestrator.pipeline" and r.levelno == logging.WARNING
    ]
    assert any("alert raised unexpected" in m for m in warnings)


@pytest.mark.asyncio
async def test_run_pipeline_safe_alert_lets_base_exception_propagate(
    archive_root: Path,
) -> None:
    """H1 sanity — ``BaseException`` (operator Ctrl-C, asyncio
    cancellation, system exit) MUST still propagate so the runtime
    can shut the process down. We catch ``Exception`` not
    ``BaseException`` precisely to preserve this behavior.
    """
    publisher = _FakePublisher()
    alerter = _FakeAlerter(raise_exc=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_success_fetch([]),
            git_runner=_SuccessfulGitRunner(),
            generate=_success_generate(),
        )


# ---------------------------------------------------------------------------
# AC-001-1 — stage_timings populated on every exit (success + failure)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_records_stage_timings_on_success(
    archive_root: Path,
) -> None:
    """All 4 stage timings present + non-negative on the happy path."""
    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    assert set(result.stage_timings) == {
        "collect",
        "generate",
        "publish",
        "notify_briefing",
    }
    for stage, seconds in result.stage_timings.items():
        assert seconds >= 0, f"{stage} timing negative"


@pytest.mark.asyncio
async def test_run_pipeline_records_failed_stage_timing_even_on_abort(
    archive_root: Path,
) -> None:
    """When generate raises, generate's timing IS recorded; downstream
    stages are not (they didn't run). Operators can see post-mortem
    where time was spent before the failure.
    """
    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_failing_bge_generate(),
    )

    assert "collect" in result.stage_timings
    assert "generate" in result.stage_timings
    # downstream were skipped → no timing recorded.
    assert "publish" not in result.stage_timings
    assert "notify_briefing" not in result.stage_timings


# ---------------------------------------------------------------------------
# Programmer error propagation (AC-003-7 surfaces at main; orchestrator
# does not swallow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_propagates_programmer_error(archive_root: Path) -> None:
    """Aggregator raises a non-source RuntimeError (programmer error)
    → propagates from run_pipeline so main() can route per AC-003-7.
    Orchestrator does not catch arbitrary Exception.
    """

    async def _broken_fetch(target_date: date) -> list[NormalizedItem]:
        raise RuntimeError("aggregator blew up")

    with pytest.raises(RuntimeError, match="aggregator blew up"):
        await run_pipeline(
            _TARGET,
            publisher=_FakePublisher(),
            alerter=_FakeAlerter(),
            site_url_base=_SITE_BASE,
            fetch=_broken_fetch,
            git_runner=_SuccessfulGitRunner(),
            generate=_success_generate(),
        )


# ---------------------------------------------------------------------------
# Briefing URL composition
# ---------------------------------------------------------------------------


def test_briefing_url_for_strips_trailing_slash_in_base() -> None:
    base_with_slash = TypeAdapter(HttpUrl).validate_python("https://example.github.io/investo/")
    url = _briefing_url_for(date(2026, 4, 25), base_with_slash)
    s = str(url)
    assert "investo/archive/2026/04/2026-04-25/" in s
    # No double slash.
    assert "//" not in s.replace("https://", "")


def test_briefing_url_for_pads_month_to_2_digits() -> None:
    url = _briefing_url_for(date(2026, 1, 5), _SITE_BASE)
    assert "/archive/2026/01/2026-01-05/" in str(url)


def test_briefing_url_for_supports_segment_prefix_for_new_runs() -> None:
    url = _briefing_url_for(date(2026, 1, 5), _SITE_BASE, segment=US_EQUITY)
    assert "/archive/us-equity/2026/01/2026-01-05/" in str(url)


def test_briefing_url_for_keeps_unsegmented_history_readable() -> None:
    url = _briefing_url_for(date(2026, 1, 5), _SITE_BASE, segment=None)
    assert "/archive/2026/01/2026-01-05/" in str(url)
    assert "/archive/crypto/" not in str(url)


def test_briefing_url_for_segment_strips_trailing_slash_in_base() -> None:
    base_with_slash = TypeAdapter(HttpUrl).validate_python("https://example.github.io/investo/")
    url = _briefing_url_for(date(2026, 4, 25), base_with_slash, segment=CRYPTO)
    s = str(url)
    assert "investo/archive/crypto/2026/04/2026-04-25/" in s
    assert "//" not in s.replace("https://", "")


# ---------------------------------------------------------------------------
# AC-001-3 / AC-001-5 / AC-003-11 — AST-grep deny tests
# ---------------------------------------------------------------------------


def _pipeline_source() -> str:
    """Read the orchestrator pipeline source for static checks."""
    from investo.orchestrator import pipeline as pipe_mod

    return Path(pipe_mod.__file__).read_text(encoding="utf-8")


_STAGE_CALL_NAMES = frozenset(
    {
        "_stage_collect",
        "_stage_generate",
        "_stage_publish",
        "_stage_notify_briefing",
    }
)


def _is_stage_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _STAGE_CALL_NAMES
    )


def _is_asyncio_call(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
        and node.func.attr == name
    )


def test_pipeline_source_has_no_asyncio_wait_for_on_stages() -> None:
    """AC-001-3: per Q1=A, the orchestrator MUST NOT wrap stage calls
    in ``asyncio.wait_for`` — unit-level timeouts are the contract.
    """
    src = _pipeline_source()
    tree = ast.parse(src)
    offending = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if _is_asyncio_call(node, "wait_for") and node.args and _is_stage_call(node.args[0])
    ]
    assert offending == [], (
        f"pipeline.py contains asyncio.wait_for(stage_call) which violates AC-001-3: {offending}"
    )


def test_pipeline_source_has_no_stage_level_asyncio_gather() -> None:
    """AC-001-5: stages are sequential per Q5; ``asyncio.gather`` of
    multiple ``_stage_*`` calls would parallelize and is forbidden.
    """
    src = _pipeline_source()
    # Find every ``asyncio.gather(...)`` call site and assert none of
    # its arguments name a ``_stage_*`` callable.
    tree = ast.parse(src)
    offending: list[str] = []
    for node in ast.walk(tree):
        if _is_asyncio_call(node, "gather"):
            offending.extend(ast.unparse(arg) for arg in node.args if _is_stage_call(arg))
    assert offending == [], (
        f"pipeline.py asyncio.gather wraps stage calls (AC-001-5 violation): {offending}"
    )


def test_pipeline_source_has_no_orchestrator_level_retry_loops() -> None:
    """AC-003-11: per Q4=A, orchestrator does not wrap stage calls in
    retry loops. Reject any ``for ... in range(...)`` or ``while ...``
    loop whose body contains an ``await _stage_*`` call.
    """
    src = _pipeline_source()
    tree = ast.parse(src)
    offending: list[str] = []

    def _body_calls_stage(body: list[ast.stmt]) -> bool:
        for stmt in body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Await) and _is_stage_call(sub.value):
                    return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.For | ast.While) and _body_calls_stage(node.body):
            offending.append(ast.unparse(node))
    assert offending == [], "pipeline.py wraps a stage await in a retry loop (AC-003-11 violation)"


# ---------------------------------------------------------------------------
# _build_failure_context — traceback truncation safety
# ---------------------------------------------------------------------------


def test_build_failure_context_truncates_traceback_at_2000_chars() -> None:
    """A pathologically deep traceback must not violate
    FailureContext's 2000-char limit (would otherwise raise
    ValidationError at construction).
    """
    # Synthesize an exception with a long traceback by raising and
    # padding the message itself.
    long_message = "x" * 5000
    try:
        raise RuntimeError(long_message)
    except RuntimeError as exc:
        ctx = _build_failure_context(stage="collect", exc=exc)

    assert ctx.traceback_excerpt is not None
    assert len(ctx.traceback_excerpt) <= TRACEBACK_EXCERPT_MAX


def test_build_failure_context_uses_error_class_name_when_message_empty() -> None:
    """If exc has no string form, error_message falls back to the
    class name so the FailureContext min_length=1 invariant holds.
    """

    class _SilentError(RuntimeError):
        def __str__(self) -> str:
            return ""

    try:
        raise _SilentError()
    except _SilentError as exc:
        ctx = _build_failure_context(stage="generate", exc=exc)

    assert ctx.error_message == "_SilentError"


# ---------------------------------------------------------------------------
# Total duration sanity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_duration_seconds_set_on_success(archive_root: Path) -> None:
    """``duration_seconds`` is set on PipelineResult and ≥ sum of stage timings."""
    result = await run_pipeline(
        _TARGET,
        publisher=_FakePublisher(),
        alerter=_FakeAlerter(),
        site_url_base=_SITE_BASE,
        fetch=_success_fetch([_item()]),
        git_runner=_SuccessfulGitRunner(),
        generate=_success_generate(),
    )

    assert result.duration_seconds >= 0
    # Duration is at least the sum of per-stage timings (loose bound;
    # bookkeeping overhead may add a tiny gap).
    assert result.duration_seconds >= sum(result.stage_timings.values()) - 0.1


# ---------------------------------------------------------------------------
# u29 QA M3 — weekly digest opt-in is the only switch that flips the
# orchestrator into Saturday-cron mode. These tests pin the contract so a
# refactor that changes the env-var name or drops the gate is caught.
# ---------------------------------------------------------------------------


def _segment_briefings_dict() -> dict[MarketSegment, Briefing]:
    return {
        DOMESTIC_EQUITY: _briefing(segment=DOMESTIC_EQUITY),
        US_EQUITY: _briefing(segment=US_EQUITY),
        CRYPTO: _briefing(segment=CRYPTO),
    }


def _patch_publish_segments_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    weekly_calls: list[date] | None = None,
    weekly_index_calls: list[None] | None = None,
    weekly_raises: BaseException | None = None,
) -> None:
    """Patch publish side effects while preserving absolute archive returns.

    ``_stage_publish_segments`` normalizes absolute paths returned from
    ``write_briefing`` before running index/heatmap/OG/quality/weekly
    side effects. This helper returns absolute archive paths under
    ``tmp_path`` so those tests exercise the normalization path while
    stubbing the expensive side-effect writers.

    ``tmp_path`` is required because ``_rollback_paths`` calls
    ``Path.unlink(missing_ok=True)`` on every snapshot path. With
    ``_read_existing_bytes`` stubbed to ``None``, those unlinks resolve
    against the test process cwd — historically the repo root, where
    they would silently delete the real ``site_docs/index.md`` and
    ``archive/**/index.md`` files. Chdir-ing into ``tmp_path`` keeps
    the rollback's filesystem effects scoped to the per-test scratch
    directory.
    """
    monkeypatch.chdir(tmp_path)
    archive_root = tmp_path / "archive"
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", archive_root)

    def fake_archive_path(target_date: date, *, segment: MarketSegment | None = None) -> Path:
        assert segment is not None
        return archive_root / segment / "2026" / "04" / f"{target_date.isoformat()}.md"

    def fake_write_briefing(
        briefing: Briefing,
        target_date: date,
        *,
        segment: MarketSegment | None = None,
    ) -> Path:
        assert segment is not None
        return fake_archive_path(target_date, segment=segment)

    monkeypatch.setattr(pipeline_module, "compute_archive_path", fake_archive_path)
    monkeypatch.setattr(pipeline_module, "write_briefing", fake_write_briefing)
    monkeypatch.setattr(
        pipeline_module,
        "update_latest_index_pages",
        lambda *args, **kwargs: (Path("site_docs/index.md"),),
    )
    monkeypatch.setattr(pipeline_module, "_build_publish_heatmap_svg", lambda _date: "<svg/>")
    monkeypatch.setattr(
        pipeline_module,
        "write_og_card",
        lambda *args, **kwargs: Path("site_docs/assets/og-card.svg"),
    )
    monkeypatch.setattr(pipeline_module, "_read_existing_bytes", lambda path: None)

    def fake_publish_weekly_digest(target_date: date) -> Path:
        if weekly_raises is not None:
            raise weekly_raises
        if weekly_calls is not None:
            weekly_calls.append(target_date)
        return Path("archive/weekly/fake.md")

    def fake_update_weekly_index() -> Path:
        if weekly_index_calls is not None:
            weekly_index_calls.append(None)
        return Path("archive/weekly/index.md")

    monkeypatch.setattr(pipeline_module, "publish_weekly_digest", fake_publish_weekly_digest)
    monkeypatch.setattr(pipeline_module, "update_weekly_index", fake_update_weekly_index)


@pytest.mark.asyncio
async def test_stage_publish_segments_identity_failure_removes_staged_asset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path)
    asset_path = tmp_path / "archive" / DOMESTIC_EQUITY / "staged.assets" / "chart.svg"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text("<svg/>", encoding="utf-8")
    mismatched = _briefing(date(2026, 4, 26), segment=DOMESTIC_EQUITY)

    with pytest.raises(ValueError, match="briefing target_date must match"):
        await pipeline_module._stage_publish_segments(
            {DOMESTIC_EQUITY: mismatched},
            _TARGET,
            asset_paths=(asset_path,),
            git_runner=_SuccessfulGitRunner(),
        )

    assert not asset_path.exists()


@pytest.mark.asyncio
async def test_stage_publish_segments_sealed_path_preserves_exact_markdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path)
    sealed = _briefing(segment=DOMESTIC_EQUITY).model_copy(
        update={"rendered_markdown": "sealed bytes -- do not mutate\n"}
    )
    written: list[Briefing] = []

    def fail_phase_one(*args: object, **kwargs: object) -> object:
        raise AssertionError("sealed path must not re-run phase-one producers")

    def capture_write(
        briefing: Briefing,
        target_date: date,
        *,
        segment: MarketSegment | None = None,
    ) -> Path:
        assert target_date == _TARGET
        assert segment == DOMESTIC_EQUITY
        written.append(briefing)
        return tmp_path / "archive" / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md"

    monkeypatch.setattr(
        pipeline_module,
        "_assemble_phase_one_presentation_briefings",
        fail_phase_one,
    )
    monkeypatch.setattr(
        pipeline_module,
        "_assemble_phase_one_body_evidence",
        fail_phase_one,
    )
    monkeypatch.setattr(pipeline_module, "write_briefing", capture_write)

    await pipeline_module._stage_publish_segments(
        {DOMESTIC_EQUITY: sealed},
        _TARGET,
        git_runner=_SuccessfulGitRunner(),
        phase_one_complete=True,
    )

    assert written == [sealed]
    assert written[0].rendered_markdown == "sealed bytes -- do not mutate\n"


@pytest.mark.asyncio
async def test_stage_publish_segments_finalized_bundle_uses_sealed_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path)
    sealed = _briefing(segment=DOMESTIC_EQUITY)
    unsealed = sealed.model_copy(
        update={"rendered_markdown": sealed.rendered_markdown.replace("오늘 시장 요약", "unsealed")}
    )
    document = SimpleNamespace(segment=DOMESTIC_EQUITY, briefing=sealed)
    bundle = SimpleNamespace(documents=(document,), promotion_manifest=())
    written: list[object] = []
    indexed: list[dict[MarketSegment, Briefing]] = []
    og_inputs: list[dict[MarketSegment, Briefing]] = []

    def fail_legacy_writer(*args: object, **kwargs: object) -> Path:
        del args, kwargs
        raise AssertionError("finalized bundle must not use write_briefing")

    def capture_sealed_writer(value: object) -> Path:
        written.append(value)
        return tmp_path / "archive" / DOMESTIC_EQUITY / "2026" / "04" / "2026-04-27.md"

    def capture_index(
        target_date: date,
        *,
        segment_briefings: dict[MarketSegment, Briefing],
        heatmap_svg: str,
    ) -> tuple[Path, ...]:
        assert target_date == _TARGET
        assert heatmap_svg == "<svg/>"
        indexed.append(segment_briefings)
        return (Path("site_docs/index.md"),)

    def capture_og(
        target_date: date,
        segment_briefings: dict[MarketSegment, Briefing],
    ) -> Path:
        assert target_date == _TARGET
        og_inputs.append(segment_briefings)
        return Path("site_docs/assets/og-card.svg")

    monkeypatch.setattr(pipeline_module, "write_briefing", fail_legacy_writer)
    monkeypatch.setattr(pipeline_module, "write_finalized_document", capture_sealed_writer)
    monkeypatch.setattr(pipeline_module, "update_latest_index_pages", capture_index)
    monkeypatch.setattr(pipeline_module, "write_og_card", capture_og)

    await pipeline_module._stage_publish_segments(
        {DOMESTIC_EQUITY: unsealed},
        _TARGET,
        git_runner=_SuccessfulGitRunner(),
        phase_one_complete=True,
        finalized_bundle=bundle,
        staging_root=tmp_path / "staging",
    )

    assert written == [document]
    assert indexed == [{DOMESTIC_EQUITY: sealed}]
    assert og_inputs == [{DOMESTIC_EQUITY: sealed}]


def _patch_watchlist_publish_inputs(
    monkeypatch: pytest.MonkeyPatch,
    items: Sequence[NormalizedItem],
) -> None:
    from investo.briefing import watchlist as watchlist_module
    from investo.briefing.watchlist import WatchlistConfig

    class _SegmentedItems:
        def for_segment(self, segment: MarketSegment) -> tuple[NormalizedItem, ...]:
            return tuple(items)

        def coverage_for_segment(
            self,
            segment: MarketSegment,
            *,
            source_outcomes: object = (),
        ) -> object:
            return SimpleNamespace(status="normal")

    monkeypatch.setattr(
        watchlist_module,
        "load_watchlist",
        lambda: WatchlistConfig(tickers=("NVDA",)),
    )
    monkeypatch.setattr(pipeline_module, "segment_items", lambda _items: _SegmentedItems())


@pytest.mark.asyncio
async def test_stage_publish_segments_rolls_back_quality_history_append(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path)
    history = tmp_path / "quality_history.jsonl"
    monkeypatch.setenv("INVESTO_QUALITY_HISTORY_PATH", str(history))
    original = '{"date":"2026-04-26","source_liveness":1.0}\n'
    history.write_text(original, encoding="utf-8")

    def fake_read_existing(path: Path) -> bytes | None:
        if path == history:
            return original.encode("utf-8")
        return None

    def fail_quality_page(*args: object, **kwargs: object) -> Path:
        raise pipeline_module.QualityHistoryError("quality page failed after append")

    monkeypatch.setattr(pipeline_module, "_read_existing_bytes", fake_read_existing)
    monkeypatch.setattr(pipeline_module, "update_quality_page", fail_quality_page)

    with pytest.raises(pipeline_module.QualityHistoryError):
        await pipeline_module._stage_publish_segments(
            _segment_briefings_dict(),
            _TARGET,
            git_runner=_SuccessfulGitRunner(),
        )

    assert history.read_text(encoding="utf-8") == original


def test_maybe_publish_monthly_retrospective_on_month_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", archive)
    for day in range(1, 8):
        path = archive / US_EQUITY / "2026" / "04" / f"2026-04-{day:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# t\n\n> **오늘의 결론**: AAPL 강세 {day} [강세]\n", encoding="utf-8")

    snapshots: dict[Path, bytes | None] = {}
    paths = pipeline_module._maybe_publish_monthly_retrospective(date(2026, 5, 1), snapshots)

    assert archive / "monthly" / "2026-04.md" in paths
    assert (archive / "monthly" / "index.md") in paths
    assert "2026년 04월 회고" in (archive / "monthly" / "2026-04.md").read_text(encoding="utf-8")


def test_maybe_publish_monthly_retrospective_skips_non_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")

    assert pipeline_module._maybe_publish_monthly_retrospective(date(2026, 5, 2), {}) == ()


@pytest.mark.asyncio
async def test_stage_publish_segments_invokes_weekly_digest_when_opt_in_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``INVESTO_PUBLISH_WEEKLY=1`` → ``publish_weekly_digest`` invoked
    once + ``update_weekly_index`` invoked once for the segmented run.

    Pins the Saturday cron contract: the orchestrator only calls the
    weekly retrospective publisher when the GHA workflow has set the
    opt-in flag (mirrors ``aidlc-docs/.../u29`` design).
    """
    monkeypatch.setenv("INVESTO_PUBLISH_WEEKLY", "1")
    weekly_calls: list[date] = []
    weekly_index_calls: list[None] = []
    _patch_publish_segments_side_effects(
        monkeypatch,
        tmp_path=tmp_path,
        weekly_calls=weekly_calls,
        weekly_index_calls=weekly_index_calls,
    )

    git = _SuccessfulGitRunner()
    await pipeline_module._stage_publish_segments(
        _segment_briefings_dict(),
        _TARGET,
        git_runner=git,
    )

    assert weekly_calls == [_TARGET]
    assert len(weekly_index_calls) == 1
    # The weekly markdown + index path should be staged in the same
    # ``git add`` call as the segmented archive.
    add_call = next(call for call in git.calls if len(call) > 1 and call[1] == "add")
    assert any("weekly/fake.md" in arg for arg in add_call)
    assert any("weekly/index.md" in arg for arg in add_call)


@pytest.mark.asyncio
async def test_stage_publish_segments_skips_weekly_digest_when_opt_in_unset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No ``INVESTO_PUBLISH_WEEKLY`` env-var → weekly digest NOT invoked
    on a Mon-Fri cron path. Confirms the segmented happy-path does not
    accidentally double-publish when the opt-in is absent.
    """
    monkeypatch.delenv("INVESTO_PUBLISH_WEEKLY", raising=False)
    weekly_calls: list[date] = []
    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path, weekly_calls=weekly_calls)

    await pipeline_module._stage_publish_segments(
        _segment_briefings_dict(),
        _TARGET,
        git_runner=_SuccessfulGitRunner(),
    )

    assert weekly_calls == []


@pytest.mark.asyncio
async def test_stage_publish_segments_skips_weekly_digest_when_opt_in_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``INVESTO_PUBLISH_WEEKLY=0`` is treated as opt-out (only ``1`` opts in)."""
    monkeypatch.setenv("INVESTO_PUBLISH_WEEKLY", "0")
    weekly_calls: list[date] = []
    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path, weekly_calls=weekly_calls)

    await pipeline_module._stage_publish_segments(
        _segment_briefings_dict(),
        _TARGET,
        git_runner=_SuccessfulGitRunner(),
    )

    assert weekly_calls == []


@pytest.mark.asyncio
async def test_run_pipeline_weekly_digest_failure_rolls_back_and_fails(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ``INVESTO_PUBLISH_WEEKLY=1`` and the weekly publisher raises
    a ``PublisherDisclaimerError`` (NFR-004), the orchestrator's
    publish-stage catch routes to FAILED + alert. The publish-stage
    try-block already covers the weekly call, so the segmented publish
    that succeeded is NOT promoted — confirms failure isolation per the
    M3 brief. Routes the failure through ``_stage_publish_segments``
    directly so the weekly call's normalized publish path executes.
    """
    from investo.publisher.errors import PublisherDisclaimerError

    monkeypatch.setenv("INVESTO_PUBLISH_WEEKLY", "1")
    _patch_publish_segments_side_effects(
        monkeypatch,
        tmp_path=tmp_path,
        weekly_raises=PublisherDisclaimerError(target_date=_TARGET),
    )

    git = _SuccessfulGitRunner()
    with pytest.raises(PublisherDisclaimerError):
        await pipeline_module._stage_publish_segments(
            _segment_briefings_dict(),
            _TARGET,
            git_runner=git,
        )

    # No git commit happened — the failure short-circuited before
    # ``commit_and_push`` was reached.
    assert git.calls == []


@pytest.mark.asyncio
async def test_stage_publish_segments_weekly_failure_restores_existing_watchlist_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from investo.publisher.errors import PublisherDisclaimerError

    monkeypatch.setenv("INVESTO_PUBLISH_WEEKLY", "1")
    _patch_publish_segments_side_effects(
        monkeypatch,
        tmp_path=tmp_path,
        weekly_raises=PublisherDisclaimerError(target_date=_TARGET),
    )
    item = NormalizedItem(
        source_name="yfinance-price",
        category="news",
        title="NVDA earnings surprise",
        published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
    )
    _patch_watchlist_publish_inputs(monkeypatch, (item,))

    watchlist_page = tmp_path / "site_docs" / "watchlist" / "NVDA.md"
    watchlist_page.parent.mkdir(parents=True)
    original = "# previous watchlist page\n"
    watchlist_page.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        pipeline_module,
        "_read_existing_bytes",
        lambda path: path.read_bytes() if path.exists() else None,
    )

    with pytest.raises(PublisherDisclaimerError):
        await pipeline_module._stage_publish_segments(
            _segment_briefings_dict(),
            _TARGET,
            git_runner=_SuccessfulGitRunner(),
            items=(item,),
        )

    assert watchlist_page.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_stage_publish_segments_weekly_failure_removes_new_watchlist_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from investo.publisher.errors import PublisherDisclaimerError

    monkeypatch.setenv("INVESTO_PUBLISH_WEEKLY", "1")
    _patch_publish_segments_side_effects(
        monkeypatch,
        tmp_path=tmp_path,
        weekly_raises=PublisherDisclaimerError(target_date=_TARGET),
    )
    item = NormalizedItem(
        source_name="yfinance-price",
        category="news",
        title="NVDA earnings surprise",
        published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
    )
    _patch_watchlist_publish_inputs(monkeypatch, (item,))
    watchlist_page = tmp_path / "site_docs" / "watchlist" / "NVDA.md"
    monkeypatch.setattr(
        pipeline_module,
        "_read_existing_bytes",
        lambda path: path.read_bytes() if path.exists() else None,
    )

    with pytest.raises(PublisherDisclaimerError):
        await pipeline_module._stage_publish_segments(
            _segment_briefings_dict(),
            _TARGET,
            git_runner=_SuccessfulGitRunner(),
            items=(item,),
        )

    assert not watchlist_page.exists()


@pytest.mark.asyncio
async def test_stage_publish_segments_watchlist_atomic_failure_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from investo.publisher import watchlist_pages as watchlist_pages_module

    _patch_publish_segments_side_effects(monkeypatch, tmp_path=tmp_path)
    item = NormalizedItem(
        source_name="yfinance-price",
        category="news",
        title="NVDA earnings surprise",
        published_at=datetime(2026, 4, 27, 12, 0, tzinfo=UTC),
    )
    _patch_watchlist_publish_inputs(monkeypatch, (item,))

    watchlist_page = tmp_path / "site_docs" / "watchlist" / "NVDA.md"
    watchlist_page.parent.mkdir(parents=True)
    original = "# previous watchlist page\n"
    watchlist_page.write_text(original, encoding="utf-8")

    def fake_write_atomic(path: Path, text: str) -> None:
        if path.name == "index.md":
            raise OSError("index write failed")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(watchlist_pages_module, "write_atomic", fake_write_atomic)
    monkeypatch.setattr(
        pipeline_module,
        "_read_existing_bytes",
        lambda path: path.read_bytes() if path.exists() else None,
    )

    with pytest.raises(PublisherIOError):
        await pipeline_module._stage_publish_segments(
            _segment_briefings_dict(),
            _TARGET,
            git_runner=_SuccessfulGitRunner(),
            items=(item,),
        )

    assert watchlist_page.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_stage_publish_segments_rejects_absolute_archive_path_outside_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_root = tmp_path / "archive"
    outside_root = tmp_path / "outside"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", archive_root)

    def fake_archive_path(target_date: date, *, segment: MarketSegment | None = None) -> Path:
        assert segment is not None
        return archive_root / segment / "2026" / "04" / f"{target_date.isoformat()}.md"

    def fake_write_briefing(
        briefing: Briefing,
        target_date: date,
        *,
        segment: MarketSegment | None = None,
    ) -> Path:
        assert segment is not None
        return outside_root / segment / "2026" / "04" / f"{target_date.isoformat()}.md"

    monkeypatch.setattr(pipeline_module, "compute_archive_path", fake_archive_path)
    monkeypatch.setattr(pipeline_module, "write_briefing", fake_write_briefing)

    with pytest.raises(PublisherIOError) as exc_info:
        await pipeline_module._stage_publish_segments(
            _segment_briefings_dict(),
            _TARGET,
            git_runner=_SuccessfulGitRunner(),
        )
    assert exc_info.value.cause is not None
    assert "outside archive root" in str(exc_info.value.cause)


# ---------------------------------------------------------------------------
# 2026-05-09 GHA postmortem — segment generation timeout policy regression
# ---------------------------------------------------------------------------


def test_segment_generation_policy_carries_postmortem_timeouts_and_cron_budget() -> None:
    """Pin the live GHA timeout policy.

    2026-05-09 bumped the per-call timeout after Crypto Stage 2 hit the
    180s ceiling. 2026-05-12/13 then showed that slow repeated segment
    synthesis can burn through the old 60-minute workflow ceiling. The
    workflow now has a 240-minute ceiling. 2026-06-13 kept a third crypto
    attempt because two long attempts both returned mid-section markdown.
    2026-06-29 applied the same guard to domestic-equity after the same
    missing-first-header failure pattern.
    """
    domestic = pipeline_module.SEGMENT_GENERATION_POLICIES[DOMESTIC_EQUITY]
    us = pipeline_module.SEGMENT_GENERATION_POLICIES[US_EQUITY]
    crypto = pipeline_module.SEGMENT_GENERATION_POLICIES[CRYPTO]

    assert domestic.timeout_s == 1800.0
    assert us.timeout_s == 1800.0
    assert crypto.timeout_s == 1800.0

    assert domestic.max_attempts == 3
    assert us.max_attempts == 2
    assert crypto.max_attempts == 3

    # Worst-case repeated synthesis time remains within the 240-minute job
    # timeout. Fast collect/publish stages still leave enough headroom for
    # normal runner overhead.
    assert (
        sum(policy.timeout_s * policy.max_attempts for policy in (domestic, us, crypto)) <= 240 * 60
    )

    # Total budget covers the retry attempts plus headroom for the fast
    # classification stage and output validation.
    for policy in (domestic, us, crypto):
        assert policy.total_budget_s >= policy.timeout_s * policy.max_attempts
