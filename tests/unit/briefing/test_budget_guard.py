"""Budget-guard tests for ``briefing.pipeline.generate_briefing``.

Pins NFR AC-1.4 + AC-1.5 — once cumulative `elapsed_s` would push the
next attempt at or past the 300 s `total_budget_s`, the pipeline must
raise `BriefingGenerationError(stage="budget")` *before* dispatching
the next call. The budget is a single shared `RetryBudget` across
Stage 1 and Stage 2 (AC-1.5).

This is the FD R3 forward-looking gate (`would_exceed(timeout)`),
distinct from the post-hoc "already exhausted" check that
`RetryBudget.check_or_raise` exposes.

Happy-path counterpart lives in ``test_budget_happy_path.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from investo.briefing import pipeline
from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import BriefingGenerationError, SubprocessOutcome
from investo.models import NormalizedItem

_TARGET_DATE = date(2026, 4, 25)


def _item(idx: int) -> NormalizedItem:
    return NormalizedItem(
        source_name=f"src-{idx}",
        category="news",
        title=f"item-{idx}",
        published_at=datetime(2026, 4, 25, 12, idx, tzinfo=UTC),
    )


def _items(n: int = 2) -> list[NormalizedItem]:
    return [_item(i) for i in range(1, n + 1)]


def _valid_classification_stdout(item_count: int) -> str:
    assignments = {str(i): 4 for i in range(1, item_count + 1)}
    return json.dumps({"assignments": assignments, "unassigned": []})


@pytest.fixture(autouse=True)
def _zero_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip FD R3 backoff sleeps so failure-mode tests run instantly."""
    monkeypatch.setattr(pipeline, "_BACKOFF_SCHEDULE", (0.0, 0.0, 0.0))


# ---------------------------------------------------------------------------
# AC-1.4 — pre-dispatch budget gate fires after Stage 1 consumes ≥ 180 s
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_gate_fires_before_stage_2_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1.4 — Stage 1 attempt 1 reports `elapsed_s=200`. Cumulative
    elapsed becomes 200 s. Stage 2 enters its retry loop; the
    pre-dispatch gate evaluates `would_exceed(timeout=120)`:
    `200 + 120 = 320 ≥ 300` → True → raise BGE `stage="budget"`.

    Stage 2's runner must NOT be invoked. Total LLM dispatches: **1**
    (Stage 1 only). FD R3: "If the next attempt would exceed budget,
    raise immediately."
    """
    stdouts = [_valid_classification_stdout(item_count=2)]
    elapsed_per_call = [200.0]
    call_index = 0

    async def fake_call(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        nonlocal call_index
        outcome = SubprocessOutcome(
            stdout=stdouts[call_index],
            stderr="",
            returncode=0,
            elapsed_s=elapsed_per_call[call_index],
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call)

    budget = RetryBudget()
    with pytest.raises(BriefingGenerationError) as exc:
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), budget=budget)

    assert exc.value.stage == "budget"
    # Exactly one dispatch happened (Stage 1 attempt 1). Stage 2 was
    # blocked by the pre-dispatch gate before its first dispatch.
    assert call_index == 1
    # Cumulative elapsed reflects Stage 1's recorded duration.
    assert budget.elapsed_s == 200.0


# ---------------------------------------------------------------------------
# AC-1.5 — RetryBudget is shared across stages (passed by reference)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_is_shared_between_classify_and_synthesize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1.5 — the same `RetryBudget` instance is mutated by both
    Stage 1 and Stage 2. The cap is a SHARED counter, not per-stage.

    To prove sharing, construct a budget with a tight `total_budget_s`,
    let Stage 1 burn most of it, then assert the Stage 2 gate sees the
    Stage 1 elapsed (gate fires before Stage 2 dispatch). If the
    budget were re-instantiated between stages, Stage 2 would see a
    fresh 300 s and dispatch successfully.
    """
    stdouts = [_valid_classification_stdout(item_count=2)]
    call_index = 0

    async def fake_call(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        nonlocal call_index
        outcome = SubprocessOutcome(
            stdout=stdouts[call_index],
            stderr="",
            returncode=0,
            elapsed_s=200.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call)

    # Caller-supplied budget — pipeline must use THIS instance, not
    # construct its own per-stage replacement.
    shared_budget = RetryBudget()
    with pytest.raises(BriefingGenerationError) as exc:
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), budget=shared_budget)

    assert exc.value.stage == "budget"
    # The caller's budget object is the one that recorded Stage 1.
    assert shared_budget.elapsed_s == 200.0
    # Stage 2 was never dispatched — proves the SHARED budget gate
    # caught the over-cap projection before re-entry.
    assert call_index == 1


# ---------------------------------------------------------------------------
# Boundary — tight budget where Stage 1 alone exhausts the cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_gate_fires_on_classify_retry_when_first_attempt_overruns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boundary — Stage 1 attempt 1 dispatches and reports a 280 s
    elapsed (just under the cap). On Stage 1 attempt 2, the gate fires
    because 280 + 120 = 400 ≥ 300. Total dispatches: **1**, BGE stage
    is `"budget"`, attempt_count is 1 (one completed attempt).

    Pins that the gate works inside a single stage's retry loop, not
    only at the stage boundary.
    """
    # Stage 1 attempt 1 returns malformed JSON so the loop continues
    # to attempt 2 — but the budget gate fires first.
    stdouts = ["not valid json — malformed"]
    call_index = 0

    async def fake_call(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        nonlocal call_index
        outcome = SubprocessOutcome(
            stdout=stdouts[call_index],
            stderr="",
            returncode=0,
            elapsed_s=280.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call)

    budget = RetryBudget()
    with pytest.raises(BriefingGenerationError) as exc:
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), budget=budget)

    assert exc.value.stage == "budget"
    assert exc.value.attempt_count == 1
    assert call_index == 1
    assert budget.elapsed_s == 280.0
