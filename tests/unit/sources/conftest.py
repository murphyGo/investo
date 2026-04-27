"""Shared pytest fixtures for ``tests/unit/sources/``.

The :func:`_isolate_registry` autouse fixture snapshots and restores
``investo.sources._registry._ADAPTERS`` around every test in this
directory. Tests that register stub adapters then automatically get
clean state without having to declare the fixture per-file.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from investo.sources._registry import _ADAPTERS, _clear_for_test


@pytest.fixture(autouse=True)
def _isolate_registry() -> Iterator[None]:
    snapshot = dict(_ADAPTERS)
    _clear_for_test()
    try:
        yield
    finally:
        _clear_for_test()
        _ADAPTERS.update(snapshot)
