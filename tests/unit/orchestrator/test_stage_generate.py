"""Tests for ``investo.orchestrator.pipeline._stage_generate``.

Pins AC-003-3 (`BriefingGenerationError` propagates unchanged so
``run_pipeline`` routes to ``OperatorAlerter.alert(stage="generate")``)
and AC-005-5 (INFO log on stage entry/exit).

Per Step 6 design reconciliation: ``generate_briefing`` is already
async-native (its sync subprocess call is bridged via
``asyncio.to_thread`` inside ``call_claude_code``), so
``_stage_generate`` ``await``s directly — the plan's ``asyncio
.to_thread(generate_briefing, ...)`` form would be a TypeError on
an async function.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime

import pytest

from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.errors import BriefingGenerationError
from investo.models import Briefing, NormalizedItem
from investo.orchestrator.pipeline import _stage_generate

_TARGET = date(2026, 4, 25)


def _item(title: str = "x") -> NormalizedItem:
    return NormalizedItem(
        source_name="fake-src",
        category="news",
        title=title,
        published_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
    )


def _briefing(target_date: date = _TARGET) -> Briefing:
    """Construct a minimal valid Briefing."""
    return Briefing(
        target_date=target_date,
        market_summary="요약 본문",
        key_issues="핵심 이슈 본문",
        sector_flow="섹터 동향",
        indicators_events="지표 이벤트",
        notable_tickers="종목",
        today_watch="관전 포인트",
        disclaimer="투자 자문이 아닙니다",
        rendered_markdown="## ① 요약\n요약 본문\n\n... 면책조항 ...",
    )


def _make_generate(
    briefing: Briefing,
) -> Callable[
    [date, Sequence[NormalizedItem], ClaudeRunner | None],
    Awaitable[Briefing],
]:
    """Build a fake generator returning ``briefing`` when awaited."""

    async def _fake(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        return briefing

    return _fake


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_generate_returns_briefing_from_u2() -> None:
    """Fake u2 returns a Briefing; ``_stage_generate`` forwards it."""
    expected = _briefing()
    items = [_item("a"), _item("b")]
    result = await _stage_generate(_TARGET, items, generate=_make_generate(expected))
    assert result is expected


@pytest.mark.asyncio
async def test_stage_generate_forwards_target_date_and_items() -> None:
    """The (target_date, items) pair is forwarded verbatim to u2."""
    captured: list[tuple[date, int]] = []

    async def _capturing(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        captured.append((target_date, len(items)))
        return _briefing(target_date)

    items = [_item(), _item(), _item()]
    await _stage_generate(_TARGET, items, generate=_capturing)
    assert captured == [(_TARGET, 3)]


@pytest.mark.asyncio
async def test_stage_generate_forwards_runner_seam_to_u2() -> None:
    """The injected ``ClaudeRunner`` arrives at u2 unchanged. Critical
    for the integration test (Step 11) where ``FakeClaudeRunner``
    replays recorded fixtures via the runner injection.
    """
    received_runners: list[ClaudeRunner | None] = []

    class _DummyRunner:
        """Smallest valid ClaudeRunner — never invoked in this test."""

        def __call__(
            self,
            args: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: float,
        ) -> object:  # CompletedProcess in real use
            raise NotImplementedError

    async def _capturing_generate(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        received_runners.append(runner)
        return _briefing(target_date)

    fake_runner = _DummyRunner()
    await _stage_generate(
        _TARGET,
        [_item()],
        runner=fake_runner,
        generate=_capturing_generate,
    )
    assert received_runners == [fake_runner]


@pytest.mark.asyncio
async def test_stage_generate_default_runner_is_none() -> None:
    """When the caller doesn't pass ``runner=``, ``None`` is forwarded
    so u2 uses its own production default (real subprocess runner).
    """
    received: list[ClaudeRunner | None] = []

    async def _capturing(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        received.append(runner)
        return _briefing(target_date)

    await _stage_generate(_TARGET, [_item()], generate=_capturing)
    assert received == [None]


# ---------------------------------------------------------------------------
# AC-003-3 — BriefingGenerationError propagates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", ["classification", "synthesis", "post_validation", "budget"])
@pytest.mark.asyncio
async def test_stage_generate_propagates_briefing_generation_error(
    stage: str,
) -> None:
    """All four BGE stages propagate unchanged. ``run_pipeline`` (Step
    9) catches and routes to OperatorAlerter per AC-003-3.
    """

    async def _failing_generate(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        raise BriefingGenerationError(
            stage=stage,  # type: ignore[arg-type]
            attempt_count=3,
            last_stderr="some stderr",
            cause=None,
        )

    with pytest.raises(BriefingGenerationError) as exc_info:
        await _stage_generate(_TARGET, [_item()], generate=_failing_generate)
    assert exc_info.value.stage == stage
    assert exc_info.value.attempt_count == 3


@pytest.mark.asyncio
async def test_stage_generate_does_not_swallow_or_wrap_bge() -> None:
    """The orchestrator MUST NOT wrap ``BriefingGenerationError`` in a
    different exception class — ``run_pipeline``'s ``except`` clause
    matches exactly on this type.
    """

    original = BriefingGenerationError(
        stage="synthesis",
        attempt_count=2,
        last_stderr=None,
        cause=ValueError("synthetic"),
    )

    async def _failing(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        raise original

    with pytest.raises(BriefingGenerationError) as exc_info:
        await _stage_generate(_TARGET, [_item()], generate=_failing)
    # Exact identity — not a wrap.
    assert exc_info.value is original


# ---------------------------------------------------------------------------
# Programmer-error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_generate_propagates_programmer_errors_unwrapped() -> None:
    """``KeyError`` / ``TypeError`` / ``ValidationError`` from u2 are
    programmer errors per the FD failure contract — orchestrator does
    not catch them; ``main()``'s top-level guard handles per
    AC-003-7.
    """

    async def _broken(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        raise KeyError("missing fixture key")

    with pytest.raises(KeyError, match="missing fixture key"):
        await _stage_generate(_TARGET, [_item()], generate=_broken)


# ---------------------------------------------------------------------------
# AC-005-5 — INFO logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_generate_logs_info_on_entry_and_exit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    items = [_item("one"), _item("two"), _item("three")]
    with caplog.at_level(logging.INFO, logger="investo.orchestrator.pipeline"):
        await _stage_generate(_TARGET, items, generate=_make_generate(_briefing()))

    info_msgs = [
        r.getMessage() for r in caplog.records if r.name == "investo.orchestrator.pipeline"
    ]
    # Entry message includes target_date + items count.
    assert any("[generate] starting" in m for m in info_msgs)
    assert any("items=3" in m for m in info_msgs)
    # Exit message confirms briefing was built.
    assert any("[generate] briefing built" in m for m in info_msgs)


@pytest.mark.asyncio
async def test_stage_generate_logs_starting_even_on_failure_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The starting log MUST be emitted before u2 is invoked — so the
    GHA log shows that generate was attempted even when u2 raises.
    """

    async def _failing(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        raise BriefingGenerationError(
            stage="classification",
            attempt_count=3,
            last_stderr=None,
            cause=None,
        )

    with (
        caplog.at_level(logging.INFO, logger="investo.orchestrator.pipeline"),
        pytest.raises(BriefingGenerationError),
    ):
        await _stage_generate(_TARGET, [_item()], generate=_failing)

    info_msgs = [
        r.getMessage() for r in caplog.records if r.name == "investo.orchestrator.pipeline"
    ]
    assert any("[generate] starting" in m for m in info_msgs)
    # No "briefing built" message because the call raised.
    assert not any("briefing built" in m for m in info_msgs)


# ---------------------------------------------------------------------------
# Default-generator wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_generate_default_callable_is_u2_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``generate=None`` (production), wires to the
    ``_default_generate_briefing`` adapter which forwards to u2's
    ``generate_briefing(..., runner=runner)``. Verify by monkeypatching
    the binding.
    """
    called_with: list[tuple[date, int, ClaudeRunner | None]] = []

    async def _spy(
        target_date: date,
        items: Sequence[NormalizedItem],
        runner: ClaudeRunner | None,
    ) -> Briefing:
        called_with.append((target_date, len(items), runner))
        return _briefing(target_date)

    monkeypatch.setattr(
        "investo.orchestrator.pipeline._default_generate_briefing",
        _spy,
        raising=True,
    )
    await _stage_generate(_TARGET, [_item("a")])
    assert called_with == [(_TARGET, 1, None)]
