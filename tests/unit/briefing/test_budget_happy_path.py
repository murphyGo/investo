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

from datetime import UTC, date, datetime

import pytest

from investo.briefing import pipeline
from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import SubprocessOutcome
from investo.briefing.segments import US_EQUITY
from investo.briefing.watchlist import WatchlistConfig
from investo.models import Briefing, NormalizedItem
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown

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

    The 300 s budget gate must NOT fire on this path: each pre-dispatch
    ``would_exceed(DEFAULT_TIMEOUT_S)`` check sees `elapsed + 120 < 300`
    and lets the call through. After both stages, cumulative is 120 s.
    The pin protects against accidentally moving the gate to a position
    where it would mis-fire on the happy path.
    """
    stdouts = [
        valid_classification_stdout(item_count=2),
        valid_stage2_markdown(),
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
async def test_generate_briefing_passes_segment_context_to_both_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """u7 Step 2 — segment scope is visible to classification and synthesis
    without calling live Claude.
    """
    stdouts = [
        valid_classification_stdout(item_count=2),
        valid_stage2_markdown(),
    ]
    captured_prompts: list[str] = []

    async def fake_call_claude_code(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        captured_prompts.append(prompt)
        return SubprocessOutcome(
            stdout=stdouts[len(captured_prompts) - 1],
            stderr="",
            returncode=0,
            elapsed_s=1.0,
        )

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call_claude_code)

    result = await pipeline.generate_briefing(
        _TARGET_DATE,
        _items(2),
        segment=US_EQUITY,
        data_limited=True,
    )

    assert len(captured_prompts) == 2
    for prompt in captured_prompts:
        assert "미국 증시" in prompt
        assert "us-equity" in prompt
        assert "데이터 부족" in prompt
    assert result.rendered_markdown.startswith("# 2026-04-25 미국 증시 시황")
    assert "**세그먼트**:" in result.rendered_markdown
    assert "> **데이터 상태**: 부분" in result.rendered_markdown
    assert "누락: 가격" in result.rendered_markdown
    assert "> **오늘의 결론**:" in result.rendered_markdown


@pytest.mark.asyncio
async def test_segment_header_sanitizes_markdown_and_numbered_watchpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """u14 — first-viewport header fields must not expose raw markdown fragments."""
    stage2_markdown = (
        "## ① 요약\n[미국 증시](https://example.com)는 **실적 일정**을 앞두고 "
        "방향성 확인이 필요합니다. 추가 패딩 텍스트입니다.\n\n"
        "## ② 전일 핵심 이슈\n**입법 가속화 vs. 정치적 마찰**\n"
        "[White House](https://example.com)가 세부 일정을 제시했습니다.\n\n"
        "## ③ 섹터/수급 동향\n섹터별 수급 근거는 제한적입니다.\n\n"
        "## ④ 지표·이벤트\n지표 일정은 추가 확인이 필요합니다.\n\n"
        "## ⑤ 주요 종목\n주요 종목 근거는 제한적입니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n"
        "1. **ARM 가이던스** — 실제 EPS보다 차기 분기 전망이 중요합니다.\n"
    )
    stdouts = [
        valid_classification_stdout(item_count=2),
        stage2_markdown,
    ]
    captured_prompts: list[str] = []

    async def fake_call_claude_code(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        captured_prompts.append(prompt)
        return SubprocessOutcome(
            stdout=stdouts[len(captured_prompts) - 1],
            stderr="",
            returncode=0,
            elapsed_s=1.0,
        )

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call_claude_code)

    result = await pipeline.generate_briefing(
        _TARGET_DATE,
        _items(2),
        segment=US_EQUITY,
        watchlist_config=WatchlistConfig(tickers=("ITEM-1",), keywords=("item-2",)),
    )

    header = result.rendered_markdown.split("## ① 요약", maxsplit=1)[0]
    assert "> **데이터 상태**: 부분" in header
    assert "> **내 관심 자산 영향**: 2건 확인" in header
    assert "> **오늘의 결론**: 미국 증시는 실적 일정을 앞두고 방향성 확인이 필요합니다." in header
    assert "> **핵심 동인**: 입법 가속화 vs. 정치적 마찰" in header
    assert "> **주의할 점**: ARM 가이던스" in header
    assert "주의할 점**: 1." not in header
    summary_lines = "\n".join(line for line in header.splitlines() if line.startswith("> "))
    assert "[미국 증시]" not in summary_lines
    assert "**실적 일정**" not in summary_lines
    assert "**입법 가속화" not in summary_lines
    assert "Watchlist relevance" in captured_prompts[0]
    assert "ITEM-1" in captured_prompts[1]


@pytest.mark.asyncio
async def test_generate_briefing_zero_item_segment_uses_concise_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """u9 — empty segment output should be useful and should not burn LLM calls."""

    async def fail_if_called(*args: object, **kwargs: object) -> SubprocessOutcome:
        raise AssertionError("Claude should not be called for a zero-item segment fallback")

    monkeypatch.setattr(pipeline, "call_claude_code", fail_if_called)

    result = await pipeline.generate_briefing(
        _TARGET_DATE,
        (),
        segment=US_EQUITY,
        data_limited=True,
    )

    assert result.rendered_markdown.startswith("# 2026-04-25 미국 증시 시황")
    assert "정식 시황을 만들 만큼 검증된 입력 데이터가 수집되지 않았습니다" in (
        result.rendered_markdown
    )
    assert "충분한 가격/뉴스 근거 없이 티커를 나열하지 않습니다" in result.rendered_markdown
    assert result.rendered_markdown.count("데이터 부족") == 0
    header = result.rendered_markdown.split("## ① 요약", maxsplit=1)[0]
    assert "> **데이터 상태**: 부족" in header
    assert "누락: 뉴스, 가격" in header
    assert "주의할 점**: 1." not in header
    assert "> **주의할 점**: 데이터 수집 로그에서 실패한 소스" in header


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
