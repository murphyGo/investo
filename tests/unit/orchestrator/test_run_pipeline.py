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
import logging
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.errors import BriefingGenerationError
from investo.models import (
    Briefing,
    BriefingNotification,
    FailureContext,
    NormalizedItem,
    PipelineStatus,
    SendResult,
)
from investo.models.results import TRACEBACK_EXCERPT_MAX
from investo.orchestrator.pipeline import (
    _briefing_url_for,
    _build_failure_context,
    run_pipeline,
)

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


def _briefing(target_date: date = _TARGET) -> Briefing:
    body = (
        "오늘 시장 요약\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n" + DISCLAIMER
    )
    return Briefing(
        target_date=target_date,
        market_summary="오늘 시장 요약",
        key_issues="핵심 이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown="## ① 요약\n" + body,
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


def _success_generate() -> object:
    async def _fake(
        target_date: date,
        items: object,
        runner: object,
    ) -> Briefing:
        return _briefing(target_date)

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
    assert "2026/04/2026-04-27" in str(result.briefing_url)
    # No operator alert on the happy path.
    assert alerter.calls == []
    # Publisher was called exactly once with the per-day URL.
    assert len(publisher.calls) == 1
    assert str(publisher.calls[0].site_url) == str(result.briefing_url)


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
# AC-003-6 + AC-003-8 — notify fail → PARTIAL with NO operator alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_notify_failure_yields_partial_no_alert(
    archive_root: Path,
) -> None:
    """Publish succeeds, notify_briefing fails → PARTIAL.
    NO operator alert (per AC-003-6 — PARTIAL is the visibility signal).
    briefing_url IS set (publish succeeded).
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
    # NO operator alert on PARTIAL.
    assert alerter.calls == []


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
    assert "investo/2026/04/2026-04-25/" in s
    # No double slash.
    assert "//" not in s.replace("https://", "")


def test_briefing_url_for_pads_month_to_2_digits() -> None:
    url = _briefing_url_for(date(2026, 1, 5), _SITE_BASE)
    assert "/2026/01/2026-01-05/" in str(url)


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
