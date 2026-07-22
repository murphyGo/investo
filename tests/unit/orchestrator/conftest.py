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
    """Redirect u31/u32 operator-state and quality-page paths to a per-test temp dir.

    Without this, ``run_pipeline`` writes ``archive/_meta/coverage.jsonl``,
    ``archive/_meta/operator_state/boot_alerts.json``, and
    ``site_docs/quality.md`` relative to the test's cwd (typically the
    repo root), polluting the working tree across test runs.

    DEBT-087 — the fixture also pre-patches ``ARCHIVE_ROOT`` to the same
    ``tmp_path / "archive"`` value the per-test ``archive_root`` fixture
    uses, so the handful of stage-level tests that drive the real
    generator WITHOUT that fixture (``_stage_generate_segments`` ones)
    no longer append into the repo's ``archive/_meta/fact_snapshots.jsonl``.
    Tests that do request ``archive_root`` simply re-patch the identical
    path, so the two compose without conflict.
    """
    from investo.publisher import site_index as site_index_mod

    monkeypatch.setenv("INVESTO_OPERATOR_STATE_DIR", str(tmp_path / "operator_state"))
    monkeypatch.setenv("INVESTO_COVERAGE_LOG_PATH", str(tmp_path / "coverage.jsonl"))
    monkeypatch.setenv("INVESTO_QUALITY_HISTORY_PATH", str(tmp_path / "quality_history.jsonl"))
    monkeypatch.setenv("INVESTO_FORECAST_LOG_PATH", str(tmp_path / "forecast_log.jsonl"))
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    monkeypatch.setattr(site_index_mod, "QUALITY_PAGE_PATH", tmp_path / "quality.md")
    monkeypatch.setattr(site_index_mod, "ACCURACY_PAGE_PATH", tmp_path / "accuracy.md")
    yield
