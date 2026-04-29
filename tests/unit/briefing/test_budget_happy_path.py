"""Budget happy-path test for ``briefing.pipeline.generate_briefing``.

Pins NFR AC-1.1 — when each stage call's wall-clock elapsed is well
under the 300 s budget, ``generate_briefing`` returns a valid
``Briefing`` without raising a budget-stage BGE. Locks the
non-pathological path through the ``RetryBudget.check_or_raise`` /
``record`` plumbing.

The 300 s budget is enforced via ``RetryBudget.elapsed_s`` (sum of
per-call ``SubprocessOutcome.elapsed_s``). To control elapsed
deterministically, this test stubs ``pipeline.call_claude_code`` with
a function that returns a fixed-shape ``SubprocessOutcome`` per call.
That keeps the budget logic on the real code path while bypassing the
real subprocess + clock plumbing (those are exercised in
``test_claude_code.py``).

Budget-exhaustion (the failure-mode counterpart) lives in
``test_budget_guard.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from investo.briefing import pipeline
from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import SubprocessOutcome
from investo.models import Briefing, NormalizedItem

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _valid_stage2_markdown() -> str:
    """A Stage 2 stdout that parses cleanly + clears the 200-char floor."""
    return (
        "## ① 요약\n오늘 시장의 한 줄 요약 본문입니다 추가 패딩 텍스트도 함께\n\n"
        "## ② 전일 핵심 이슈\n전일의 핵심 이슈를 상세히 설명하는 본문 텍스트입니다\n\n"
        "## ③ 섹터/수급 동향\n섹터별 수급 동향을 정리한 본문 텍스트입니다\n\n"
        "## ④ 지표·이벤트\n주요 거시 지표와 일정 이벤트를 정리한 본문입니다\n\n"
        "## ⑤ 주요 종목\n관심 종목 흐름을 정리한 본문 텍스트입니다\n\n"
        "## ⑥ 오늘의 관전 포인트\n오늘 살펴볼 포인트를 정리한 본문 텍스트입니다\n"
    )


# ---------------------------------------------------------------------------
# AC-1.1 — happy path under nominal elapsed_s per call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_briefing_succeeds_under_nominal_elapsed_per_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1.1 — with ``elapsed_s=60.0`` per call (Stage 1 + Stage 2 ⇒
    cumulative 120 s, well under 300 s budget), ``generate_briefing``
    returns a valid ``Briefing`` and ``RetryBudget.elapsed_s`` records
    the cumulative time.

    The 300 s budget gate must NOT fire on this path: each
    ``check_or_raise`` precedes the call, and after both calls the
    budget is at 120 s. The pin protects against accidentally moving
    the gate to a position where it would mis-fire.
    """
    monkeypatch.setattr(pipeline, "_BACKOFF_SCHEDULE", (0.0, 0.0, 0.0))

    stdouts = [
        _valid_classification_stdout(item_count=2),
        _valid_stage2_markdown(),
    ]
    call_index = 0

    async def fake_call_claude_code(
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
            elapsed_s=60.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call_claude_code)

    budget = RetryBudget()
    result = await pipeline.generate_briefing(_TARGET_DATE, _items(2), budget=budget)

    assert isinstance(result, Briefing)
    assert result.target_date == _TARGET_DATE
    # Cumulative elapsed = 60 (Stage 1) + 60 (Stage 2) = 120 s. Under 300 s.
    assert budget.elapsed_s == 120.0
    assert budget.elapsed_s < budget.total_budget_s
    # Confirm exactly two LLM calls were dispatched (no retries).
    assert call_index == 2


@pytest.mark.asyncio
async def test_default_total_budget_is_300_seconds() -> None:
    """AC-1.1 anchor — the default budget cap is 300 s per FD R3.

    A regression that lowered the cap (or wired the wrong constant)
    would still pass the happy-path test above as long as cumulative
    elapsed stayed under the wrong cap. This anchor pins the constant
    explicitly.
    """
    budget = RetryBudget()
    assert budget.total_budget_s == 300.0
