"""Repo-wide pytest fixtures.

DEBT-087 — working-tree isolation safety net. Several runtime artifacts
under ``archive/_meta/`` are written by production code paths that tests
exercise end-to-end (per-source coverage log, forecast log, quality
history). Their production defaults are repo-relative, so any suite that
drives ``run_pipeline`` (or a stage that touches them) without redirecting
the path appends into the REAL working tree — the leak that left
``archive/_meta/coverage.jsonl`` + ``fact_snapshots.jsonl`` untracked after
a local ``pytest`` run, and that DEBT-088 would have turned into committed
synthetic rows once the coverage log joined the publish staging list.

``tests/unit/orchestrator/conftest.py`` already redirects these three env
vars for its own directory; this module generalizes that protection to
every suite (integration, publisher, briefing, …) *without* changing
production behaviour:

* the redirect is env-var based — exactly the documented operator
  override seam each writer already consults;
* it is applied only when the variable is not already set, so any test
  that sets its own path (or the orchestrator conftest, which runs
  after this one) still wins;
* ``ARCHIVE_ROOT`` itself is deliberately NOT patched here — a global
  patch would break the tests that legitimately read committed archive
  content (site-index / heatmap / discovery scans). Suites that write
  archive files keep using their own ``archive_root`` fixture.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# env var -> filename under the per-test temp dir.
_RUNTIME_PATH_ENVS: dict[str, str] = {
    "INVESTO_COVERAGE_LOG_PATH": "coverage.jsonl",
    "INVESTO_FORECAST_LOG_PATH": "forecast_log.jsonl",
    "INVESTO_QUALITY_HISTORY_PATH": "quality_history.jsonl",
}


@pytest.fixture(autouse=True)
def _isolate_archive_runtime_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[None]:
    """Redirect append-only ``archive/_meta`` runtime logs to ``tmp_path``."""
    logs_dir = tmp_path / "_archive_runtime_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    for env_name, filename in _RUNTIME_PATH_ENVS.items():
        if not os.environ.get(env_name, "").strip():
            monkeypatch.setenv(env_name, str(logs_dir / filename))
    yield
