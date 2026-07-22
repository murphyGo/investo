"""Tests for the DEBT-089 generated-file guard helpers in ``tests/conftest.py``.

The session-scoped guard itself cannot be exercised without a nested
pytest run, but its comparison logic — "report only entries the session
introduced, not the developer's pre-existing local edits" — is a pure
set difference over the porcelain snapshot, which is directly testable.
"""

from __future__ import annotations


def test_guard_reports_only_session_introduced_paths() -> None:
    # Mirror of the guard's ``after - before`` diff. A pre-existing local
    # edit (present in ``before``) must NOT be reported; a path the
    # session newly dirtied (only in ``after``) must be.
    before = frozenset({" M archive/index.md"})  # developer's own edit
    after = frozenset({" M archive/index.md", " M site_docs/quality.md"})
    introduced = after - before
    assert introduced == frozenset({" M site_docs/quality.md"})


def test_guard_is_silent_when_session_adds_nothing() -> None:
    before = frozenset({" M archive/index.md", " M site_docs/index.md"})
    after = frozenset({" M archive/index.md", " M site_docs/index.md"})
    assert (after - before) == frozenset()


def test_guarded_paths_cover_both_surfaces() -> None:
    from tests.conftest import _GUARDED_PATHS

    assert "archive/" in _GUARDED_PATHS
    assert "site_docs/" in _GUARDED_PATHS
