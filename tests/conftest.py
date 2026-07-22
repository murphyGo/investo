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
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
# Tracked generated surfaces the suite must never rewrite (DEBT-089).
_GUARDED_PATHS: tuple[str, ...] = ("archive/", "site_docs/")


def _dirty_generated_paths() -> frozenset[str]:
    """Return tracked-file porcelain entries under the guarded surfaces.

    Returns an empty set when git is unavailable / this is not a work
    tree, so the guard degrades to a no-op instead of failing the suite
    in a source-only checkout.
    """
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--", *_GUARDED_PATHS],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if completed.returncode != 0:
        return frozenset()
    return frozenset(line for line in completed.stdout.splitlines() if line.strip())


@pytest.fixture(scope="session", autouse=True)
def _assert_suite_leaves_generated_files_clean() -> Iterator[None]:
    """Fail the session if the suite dirtied a tracked generated file.

    DEBT-089 — closes DEBT-087 (untracked residue) and this entry
    (tracked modifications) against regression in one assertion.

    Compares the porcelain status BEFORE and AFTER the session rather
    than asserting absolute cleanliness, so a developer's unrelated
    local edits under ``archive/`` / ``site_docs/`` (e.g. a genuine
    pipeline run's output) never false-positive — only entries the
    session itself introduced are reported.
    """
    before = _dirty_generated_paths()
    yield
    introduced = _dirty_generated_paths() - before
    if introduced:
        offenders = "\n  ".join(sorted(introduced))
        pytest.fail(
            "the test session modified tracked generated files (DEBT-089).\n"
            "  These paths are committed renderings; a test must never write them.\n"
            "  Redirect the writer's path constant in tests/conftest.py "
            "(_SITE_PATH_CONSTANTS) or pass an explicit tmp_path root.\n"
            f"  Offending paths:\n  {offenders}",
            pytrace=False,
        )


# env var -> filename under the per-test temp dir.
_RUNTIME_PATH_ENVS: dict[str, str] = {
    "INVESTO_COVERAGE_LOG_PATH": "coverage.jsonl",
    "INVESTO_FORECAST_LOG_PATH": "forecast_log.jsonl",
    "INVESTO_QUALITY_HISTORY_PATH": "quality_history.jsonl",
}


# DEBT-089 — module-global page/asset path constants that production
# writers resolve at call time. Each entry is ``(module, attribute,
# relative destination under the per-test temp dir)``. Patched for every
# test so a suite run cannot rewrite the committed renderings; tests that
# patch these themselves run AFTER this autouse fixture and still win.
_SITE_PATH_CONSTANTS: tuple[tuple[str, str, str], ...] = (
    ("investo.publisher.site_index._constants", "SITE_INDEX_PATH", "site_docs/index.md"),
    ("investo.publisher.site_index._constants", "ARCHIVE_INDEX_PATH", "archive/index.md"),
    ("investo.publisher.site_index._constants", "QUALITY_PAGE_PATH", "site_docs/quality.md"),
    ("investo.publisher.site_index._constants", "ACCURACY_PAGE_PATH", "site_docs/accuracy.md"),
    ("investo.publisher.site_index", "SITE_INDEX_PATH", "site_docs/index.md"),
    ("investo.publisher.site_index", "ARCHIVE_INDEX_PATH", "archive/index.md"),
    ("investo.publisher.site_index", "QUALITY_PAGE_PATH", "site_docs/quality.md"),
    ("investo.publisher.site_index", "ACCURACY_PAGE_PATH", "site_docs/accuracy.md"),
    ("investo.publisher.watchlist_pages", "WATCHLIST_PAGES_ROOT", "site_docs/watchlist"),
    ("investo.visuals.og_card", "OG_CARD_RELATIVE_PATH", "site_docs/assets/og-card.svg"),
    ("investo.visuals.og_card", "OG_CARD_PNG_RELATIVE_PATH", "site_docs/assets/og-card.png"),
)


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


def _seed_from_repo(relative: str, target: Path) -> None:
    """Mirror the committed rendering into ``target`` when one exists.

    The index/quality writers are read-modify-write over marker blocks
    (``<!-- u29 hero begin -->`` etc.), so the redirected copy must start
    from the real committed content or those writers raise
    ``FileNotFoundError`` / lose their anchors. Directories (the
    watchlist root) are copied whole.
    """
    source = _REPO_ROOT / relative
    if not source.exists() or target.exists():
        return
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


@pytest.fixture(autouse=True)
def _isolate_site_page_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """Redirect committed site/index renderings to a temp dir (DEBT-089).

    ``archive/index.md`` and the ``site_docs/*`` pages are TRACKED
    generated files. Their writers resolve repo-relative module
    constants at call time, so any suite that drives a publish path
    without patching them rewrites the committed renderings — leaving
    every worktree dirty and putting a synthetic quality page one
    forgotten ``git checkout`` away from a commit.

    Patched per test against a temp mirror of the real layout. The
    mirror lives under its OWN ``tmp_path_factory`` dir — deliberately
    NOT the test's ``tmp_path`` — so a test that uses its own ``tmp_path``
    as a scan root (e.g. the curated-library loader) never discovers
    these seeded files. The ``SEGMENT_ARCHIVE_INDEX_PATHS`` mapping is
    redirected too, and both the defining ``_constants`` module and the
    package re-export are patched because different call sites read
    different namespaces.
    """
    site_root = tmp_path_factory.mktemp("site_surface")
    for module_name, attribute, relative in _SITE_PATH_CONSTANTS:
        target = site_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _seed_from_repo(relative, target)
        monkeypatch.setattr(f"{module_name}.{attribute}", target, raising=False)

    from investo.publisher.site_index import _constants as site_constants

    redirected_segment_indexes = {
        segment: site_root / "archive" / segment / "index.md"
        for segment in site_constants.SEGMENT_ARCHIVE_INDEX_PATHS
    }
    for segment, path in redirected_segment_indexes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        _seed_from_repo(f"archive/{segment}/index.md", path)
    monkeypatch.setattr(
        "investo.publisher.site_index._constants.SEGMENT_ARCHIVE_INDEX_PATHS",
        redirected_segment_indexes,
        raising=False,
    )
    monkeypatch.setattr(
        "investo.publisher.site_index.SEGMENT_ARCHIVE_INDEX_PATHS",
        redirected_segment_indexes,
        raising=False,
    )
    yield
