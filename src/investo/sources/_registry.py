"""Module-level registry for Source Adapters.

Implements §E2 of
``aidlc-docs/construction/u1-sources/functional-design/domain-entities.md``
and L3 of ``business-logic-model.md``. Adapters apply :func:`register`
as a class decorator at definition time; the decorator instantiates
the adapter (singleton per process — adapters are stateless per FD R3)
and stores it keyed by ``cls.name``. Re-registering the same name
raises :class:`RuntimeError` per FD R2 ("fail loudly, never silently
overwrite").

This module is internal. Adapter modules import :func:`register`
directly; external consumers should use the public re-export from
:mod:`investo.sources` (Step 9 wires that up).
"""

from __future__ import annotations

from typing import TypeVar

from investo.sources.protocol import SourceAdapter

_AdapterT = TypeVar("_AdapterT", bound=SourceAdapter)

# Module-level singleton — populated at import time by adapter modules
# whose ``@register`` decorator runs as a side effect when
# ``investo.sources/__init__.py`` imports them. Stays stable for the
# life of the process; tests use :func:`_clear_for_test` to isolate.
_ADAPTERS: dict[str, SourceAdapter] = {}


def register(cls: type[_AdapterT]) -> type[_AdapterT]:
    """Class decorator: instantiate ``cls`` and add it to the registry.

    Returns ``cls`` unchanged so the decorator is transparent to type
    checkers and to anyone using the class directly.

    Raises:
        RuntimeError: when ``cls.name`` is already registered. Adapters
            collide on import order, so this surfaces at process start
            rather than mid-pipeline.
    """

    name = cls.name
    if name in _ADAPTERS:
        raise RuntimeError(f"duplicate source name: {name!r}")
    _ADAPTERS[name] = cls()
    return cls


def list_sources() -> list[SourceAdapter]:
    """Return a fresh list of registered adapters.

    The returned list is a *copy* — callers can sort, slice, or extend
    it without surprising side-effects on later calls. Insertion order
    is preserved (Python 3.7+ dict semantics) so adapters appear in
    the order their modules were imported.
    """

    return list(_ADAPTERS.values())


def _clear_for_test() -> None:
    """Reset the registry. **For test fixtures only.**

    Production code populates the registry at import time and never
    mutates it afterwards. Tests that register stub adapters or want
    to verify the empty state call this between cases.
    """

    _ADAPTERS.clear()
