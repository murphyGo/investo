"""Shared pytest fixtures for u5 orchestrator unit tests.

Per-stage fixtures (fake ``Aggregator`` / ``GitRunner`` / mocked
``BriefingPublisher`` / ``OperatorAlerter`` / record-replay
``ClaudeCodeRunner``) land alongside the stage tests in Steps 4-9
of ``aidlc-docs/construction/plans/u5-orchestrator-code-generation-plan.md``.

This file is the canonical destination for any helper that more
than one orchestrator test needs (e.g., the eventual
``_dummy_briefing`` factory or the integration-test ``MockTransport``
constructor) — preventing the per-test-file duplication that
DEBT-010 / DEBT-013 / DEBT-016 already track for the other units.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_operator_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Redirect u31 operator-state paths to a per-test temp dir.

    Without this, ``run_pipeline`` writes ``archive/_meta/coverage.jsonl``
    and ``archive/_meta/operator_state/boot_alerts.json`` relative to
    the test's cwd (typically the repo root), polluting the working
    tree across test runs. This autouse fixture pins both paths to
    ``tmp_path`` for every test in this directory.
    """
    monkeypatch.setenv("INVESTO_OPERATOR_STATE_DIR", str(tmp_path / "operator_state"))
    monkeypatch.setenv("INVESTO_COVERAGE_LOG_PATH", str(tmp_path / "coverage.jsonl"))
    yield
