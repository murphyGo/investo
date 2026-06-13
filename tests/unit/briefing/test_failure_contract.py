"""Failure-contract tests for ``briefing.pipeline.generate_briefing``.

Pins NFR ACs:

* AC-3.2 — every ``BriefingGenerationError`` carries one of the four
  declared ``stage`` values: ``"classification"``, ``"synthesis"``,
  ``"post_validation"``, ``"budget"``.
* AC-3.4 — programmer errors (e.g., ``KeyError`` from a bug, not from
  malformed LLM output) propagate as-is; they are NOT wrapped in BGE.
* AC-3.5 — ``pydantic.ValidationError`` raised by constructing
  ``Briefing`` likewise propagates as-is; the failure contract treats
  these as programmer-driven contract violations.

The 4-stage budget mode (``stage="budget"``) is exercised in
``test_budget_guard.py``; this file covers the other three plus the
two pass-through pin tests.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from investo.briefing import pipeline
from investo.briefing.errors import BriefingGenerationError
from investo.models import NormalizedItem
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TARGET_DATE = date(2026, 4, 25)


def _item(idx: int) -> NormalizedItem:
    """Build a minimal NormalizedItem at a fixed UTC timestamp."""
    return NormalizedItem(
        source_name=f"src-{idx}",
        category="news",
        title=f"item-{idx}",
        published_at=datetime(2026, 4, 25, 12, idx, tzinfo=UTC),
    )


def _items(n: int = 2) -> list[NormalizedItem]:
    return [_item(i) for i in range(1, n + 1)]


def _outcome(
    *, stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _runner_returning(
    outcomes: Sequence[subprocess.CompletedProcess[str]],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a runner that pops canned outcomes in order."""
    iterator = iter(outcomes)

    def runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return next(iterator)
        except StopIteration as exc:  # pragma: no cover - test-design guard
            raise AssertionError("runner ran out of canned outcomes — test setup mismatch") from exc

    return runner


# ---------------------------------------------------------------------------
# Classification BGE — AC-3.2 (stage="classification")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classification_bge_after_three_malformed_json_attempts() -> None:
    """Three Stage 1 attempts returning malformed JSON → BGE.

    Pins AC-3.2: ``stage="classification"``, ``attempt_count=3``,
    ``cause`` is a ``json.JSONDecodeError``.
    """
    runner = _runner_returning(
        [
            _outcome(stdout="not json at all"),
            _outcome(stdout="still { broken"),
            _outcome(stdout="}{{ invalid"),
        ]
    )

    with pytest.raises(BriefingGenerationError) as exc:
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), runner=runner)

    assert exc.value.stage == "classification"
    assert exc.value.attempt_count == 3
    assert isinstance(exc.value.cause, json.JSONDecodeError | ValueError)


# ---------------------------------------------------------------------------
# Synthesis BGE — AC-3.2 (stage="synthesis")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesis_bge_after_three_blank_attempts() -> None:
    """One classification success, then three Stage 2 attempts whose
    stdout is blank → BGE with ``stage="synthesis"``,
    ``attempt_count=3``.

    Stage 2 has a 200-char sanity floor; "" trips it on every attempt.
    """
    runner = _runner_returning(
        [
            _outcome(stdout=valid_classification_stdout(item_count=2)),
            _outcome(stdout=""),
            _outcome(stdout=""),
            _outcome(stdout=""),
        ]
    )

    with pytest.raises(BriefingGenerationError) as exc:
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), runner=runner)

    assert exc.value.stage == "synthesis"
    assert exc.value.attempt_count == 3


@pytest.mark.asyncio
async def test_synthesis_retry_prompt_includes_validation_feedback() -> None:
    """A malformed Stage 2 body should teach the next retry what failed."""
    prompts: list[str | None] = []
    outcomes = iter(
        [
            _outcome(stdout=valid_classification_stdout(item_count=2)),
            _outcome(stdout="### 헤더 없는 본문\n" + ("내용\n" * 80)),
            _outcome(stdout=valid_stage2_markdown()),
        ]
    )

    def runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del args, capture_output, text, timeout
        prompts.append(input)
        return next(outcomes)

    await pipeline.generate_briefing(_TARGET_DATE, _items(2), runner=runner)

    assert prompts[2] is not None
    assert "Previous Stage 2 output failed validation" in prompts[2]
    assert "missing section header" in prompts[2]
    assert "first non-empty line MUST be `## ① 요약`" in prompts[2]
    assert "do not begin mid-section" in prompts[2]


# ---------------------------------------------------------------------------
# Post-validation BGE — AC-3.2 (stage="post_validation")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_validation_bge_when_synthesis_leaks_github_pat() -> None:
    """Stage 2 returns valid markdown that embeds a GitHub PAT pattern
    inside a section body. After ``append_disclaimer``,
    ``leak_guard.scan`` matches the PAT and raises BGE with
    ``stage="post_validation"``, ``attempt_count=1`` (no retry per R6),
    ``cause`` is a ``ValueError`` naming the matched pattern.
    """
    leaky_markdown = valid_stage2_markdown().replace(
        "오늘 시장의 한 줄 요약 본문입니다",
        "오늘 시장의 요약 (debug token: ghp_" + "A" * 36 + ")",
    )
    runner = _runner_returning(
        [
            _outcome(stdout=valid_classification_stdout(item_count=2)),
            _outcome(stdout=leaky_markdown),
        ]
    )

    with pytest.raises(BriefingGenerationError) as exc:
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), runner=runner)

    assert exc.value.stage == "post_validation"
    assert exc.value.attempt_count == 1  # no retry on post-validation hit
    assert isinstance(exc.value.cause, ValueError)
    assert "github_pat" in str(exc.value.cause).lower()


# ---------------------------------------------------------------------------
# AC-3.4 — programmer KeyError must propagate, NOT wrap in BGE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_programmer_keyerror_propagates_unwrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``build_section_plan`` raises a synthetic ``KeyError`` (a
    programmer bug, not LLM-traceable), the failure contract says it
    propagates as-is. The caller can ``pytest.raises(KeyError)``;
    ``pytest.raises(BriefingGenerationError)`` would NOT catch it.
    """

    def boom(
        items: Sequence[NormalizedItem],
        classification: pipeline.ClassificationResult,
        target_date: date,
    ) -> pipeline.SectionPlan:
        raise KeyError("synthetic programmer error")

    monkeypatch.setattr(pipeline, "build_section_plan", boom)

    runner = _runner_returning([_outcome(stdout=valid_classification_stdout(item_count=2))])

    with pytest.raises(KeyError, match="synthetic programmer error"):
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), runner=runner)


# ---------------------------------------------------------------------------
# AC-3.5 — Briefing ValidationError must propagate, NOT wrap in BGE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_briefing_validation_error_propagates_unwrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``parse_six_sections`` returns a degenerate 6-tuple (e.g.,
    one empty body) such that the ``Briefing`` model construction fails
    via pydantic's ``min_length=1``, the resulting ``ValidationError``
    must propagate. The classifier + synthesizer cannot fabricate this
    state through normal channels (parse_six_sections rejects blank
    bodies before returning), so we monkeypatch to simulate a
    programmer error in the section-extraction logic.
    """

    def degenerate_parse(markdown: str) -> tuple[str, str, str, str, str, str]:
        return ("", "ok", "ok", "ok", "ok", "ok")

    monkeypatch.setattr(pipeline, "parse_six_sections", degenerate_parse)

    runner = _runner_returning(
        [
            _outcome(stdout=valid_classification_stdout(item_count=2)),
            _outcome(stdout=valid_stage2_markdown()),
        ]
    )

    with pytest.raises(ValidationError):
        await pipeline.generate_briefing(_TARGET_DATE, _items(2), runner=runner)
