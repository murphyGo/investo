"""Tests for ``investo.orchestrator.pipeline._stage_publish``.

Pins AC-003-4 (`PublisherDisclaimerError` / `PublisherIOError`
propagate), AC-003-5 (`PublisherGitError` propagates with
``last_stderr``), AC-005-5 (INFO logs), and TS-2 (sync u3 functions
bridged via ``asyncio.to_thread`` so the orchestrator stays async-
native).
"""

from __future__ import annotations

import logging
import subprocess
from datetime import date
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.orchestrator.pipeline import _stage_publish
from investo.publisher import (
    GitRunner,
    PublisherDisclaimerError,
    PublisherGitError,
    PublisherIOError,
)
from investo.publisher.paths import archive_path as compute_archive_path

_TARGET = date(2026, 4, 25)


def _briefing_with_disclaimer(*, include_disclaimer: bool = True) -> Briefing:
    """Build a Briefing whose rendered_markdown does/doesn't include
    the canonical disclaimer (NFR-004 hard block test).
    """
    body = (
        "## ① 요약\n요약 본문\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n"
    )
    rendered = body + (DISCLAIMER if include_disclaimer else "## ⑦ 면책조항\n없음")
    kwargs = {
        "target_date": _TARGET,
        "market_summary": "요약 본문",
        "key_issues": "핵심 이슈",
        "sector_flow": "섹터",
        "indicators_events": "지표",
        "notable_tickers": "종목",
        "today_watch": "관전",
        "disclaimer": DISCLAIMER if include_disclaimer else "없음",
        "rendered_markdown": rendered,
    }
    if not include_disclaimer:
        return Briefing.model_construct(**kwargs)
    return Briefing(**kwargs)


class _SuccessfulGitRunner:
    """``GitRunner`` Protocol fake — every git step succeeds (rc=0)."""

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


class _FailingGitPushRunner:
    """``GitRunner`` Protocol fake — ``git push`` always fails (rc=1).

    Used to drive ``commit_and_push`` to exhaustion → PublisherGitError.
    Add+commit succeed; push always returns non-zero rc with stderr.
    On retry attempts the local commit has already landed, so ``git
    commit`` returns the idempotent-noop signal (rc=1 + "nothing to
    commit") so the retry loop proceeds to push (which fails again).
    """

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
                args=args,
                returncode=1,
                stdout="",
                stderr="fatal: unable to access remote",
            )
        if args[1] == "commit" and len([c for c in self.calls if c[1] == "commit"]) >= 2:
            # On retries 2+ the working tree is clean (commit already
            # absorbed by attempt 1) → return the idempotent-noop
            # signal so commit_and_push proceeds to push.
            return subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout="nothing to commit, working tree clean\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_publish_writes_markdown_and_commits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end happy path: write_briefing produces a file at
    ``archive_path(target_date)`` and commit_and_push runs the 3-step
    git lifecycle without retries.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    runner = _SuccessfulGitRunner()
    briefing = _briefing_with_disclaimer()

    result = await _stage_publish(briefing, _TARGET, git_runner=runner)

    expected_path = compute_archive_path(_TARGET)
    assert result == expected_path
    assert expected_path.exists()
    # 3-step git lifecycle: add, commit, push.
    git_steps = [c[1] for c in runner.calls]
    assert git_steps == ["add", "commit", "push"]


@pytest.mark.asyncio
async def test_stage_publish_returns_archive_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returned path is the archive path the briefing was written to —
    used by ``run_pipeline`` to derive ``briefing_url``.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    briefing = _briefing_with_disclaimer()

    result = await _stage_publish(briefing, _TARGET, git_runner=_SuccessfulGitRunner())
    assert isinstance(result, Path)
    assert result.name == "2026-04-25.md"


@pytest.mark.asyncio
async def test_stage_publish_commit_message_includes_target_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The commit message format is ``"briefing: YYYY-MM-DD"`` so the
    git history is human-scannable. Pinned because u6 / cross-check
    may grep for this format.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    runner = _SuccessfulGitRunner()
    briefing = _briefing_with_disclaimer()

    await _stage_publish(briefing, _TARGET, git_runner=runner)

    commit_call = next(c for c in runner.calls if c[1] == "commit")
    # ``git commit -m "briefing: 2026-04-25" -- ...`` shape.
    assert "-m" in commit_call
    msg_idx = commit_call.index("-m") + 1
    assert commit_call[msg_idx] == "briefing: 2026-04-25"


# ---------------------------------------------------------------------------
# AC-003-4 — PublisherDisclaimerError + PublisherIOError propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_publish_propagates_disclaimer_error_no_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Briefing without disclaimer → ``write_briefing`` raises
    ``PublisherDisclaimerError`` BEFORE writing. Verify (a) the error
    propagates and (b) no file lands on disk + (c) commit_and_push
    is NEVER called (the bad write is fail-fast).
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    runner = _SuccessfulGitRunner()
    bad_briefing = _briefing_with_disclaimer(include_disclaimer=False)

    with pytest.raises(PublisherDisclaimerError):
        await _stage_publish(bad_briefing, _TARGET, git_runner=runner)

    # No file written.
    expected_path = compute_archive_path(_TARGET)
    assert not expected_path.exists()
    # Git pipeline was never invoked.
    assert runner.calls == []


@pytest.mark.asyncio
async def test_stage_publish_propagates_io_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If write_briefing raises ``PublisherIOError`` (filesystem
    failure), it propagates and commit_and_push is never invoked.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    runner = _SuccessfulGitRunner()
    briefing = _briefing_with_disclaimer()

    def _bad_write(briefing: Briefing, target_date: date) -> Path:
        raise PublisherIOError(
            target_date=target_date, path=tmp_path / "x", cause=OSError("disk full")
        )

    monkeypatch.setattr("investo.orchestrator.pipeline.write_briefing", _bad_write)

    with pytest.raises(PublisherIOError):
        await _stage_publish(briefing, _TARGET, git_runner=runner)
    # Git phase skipped.
    assert runner.calls == []


# ---------------------------------------------------------------------------
# AC-003-5 — PublisherGitError after retry exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_publish_propagates_git_error_after_write_succeeded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File is written successfully, but commit_and_push exhausts
    retries (3 push failures with idempotent-commit handling between).
    PublisherGitError propagates with last_stderr populated.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    # Disable backoff sleeps so the test runs in milliseconds.
    monkeypatch.setattr("investo.publisher.git_ops.time.sleep", lambda _s: None)
    failing = _FailingGitPushRunner()
    briefing = _briefing_with_disclaimer()

    with pytest.raises(PublisherGitError) as exc_info:
        await _stage_publish(briefing, _TARGET, git_runner=failing)

    # last_stderr propagated from the failed push.
    assert exc_info.value.last_stderr is not None
    assert "unable to access remote" in exc_info.value.last_stderr
    # Write phase succeeded — file is on disk even though git failed.
    assert compute_archive_path(_TARGET).exists()


# ---------------------------------------------------------------------------
# Default git_runner — production wires to real subprocess
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_publish_default_git_runner_is_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the caller passes no ``git_runner=``, ``None`` is forwarded
    to ``commit_and_push`` so u3 uses its real subprocess runner.
    Verify by spying on the actual ``commit_and_push`` symbol that
    the orchestrator imported.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    captured: list[GitRunner | None] = []

    def _spy_commit_and_push(
        message: str,
        files: list[Path],
        *,
        retries: int = 2,
        runner: GitRunner | None = None,
    ) -> None:
        captured.append(runner)

    monkeypatch.setattr("investo.orchestrator.pipeline.commit_and_push", _spy_commit_and_push)

    briefing = _briefing_with_disclaimer()
    await _stage_publish(briefing, _TARGET)
    assert captured == [None]


# ---------------------------------------------------------------------------
# AC-005-5 — INFO logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_publish_logs_info_for_each_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Three INFO lines: starting → wrote → committed + pushed."""
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    runner = _SuccessfulGitRunner()
    briefing = _briefing_with_disclaimer()

    with caplog.at_level(logging.INFO, logger="investo.orchestrator.pipeline"):
        await _stage_publish(briefing, _TARGET, git_runner=runner)

    msgs = [r.getMessage() for r in caplog.records if r.name == "investo.orchestrator.pipeline"]
    assert any("[publish] starting" in m for m in msgs)
    assert any("[publish] wrote" in m for m in msgs)
    assert any("[publish] committed + pushed" in m for m in msgs)


@pytest.mark.asyncio
async def test_stage_publish_logs_starting_even_on_disclaimer_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The "starting" log MUST be emitted before any I/O — operators
    see the publish attempt in GHA logs even when it fails fast.
    """
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    runner = _SuccessfulGitRunner()
    bad_briefing = _briefing_with_disclaimer(include_disclaimer=False)

    with (
        caplog.at_level(logging.INFO, logger="investo.orchestrator.pipeline"),
        pytest.raises(PublisherDisclaimerError),
    ):
        await _stage_publish(bad_briefing, _TARGET, git_runner=runner)

    msgs = [r.getMessage() for r in caplog.records if r.name == "investo.orchestrator.pipeline"]
    assert any("[publish] starting" in m for m in msgs)
    # No "wrote" / "committed" because the failure was fail-fast.
    assert not any("[publish] wrote" in m for m in msgs)
    assert not any("[publish] committed" in m for m in msgs)
