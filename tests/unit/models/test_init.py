"""Drift guard for the ``investo.models`` public API surface.

Whenever a new public type is added to a submodule, the developer must
also re-export it from ``investo/models/__init__.py`` and add it to
``__all__``. Mypy does not catch the omission; this test does.
"""

from __future__ import annotations

import investo.models as models

EXPECTED_PUBLIC_NAMES: frozenset[str] = frozenset(
    {
        # items.py
        "Category",
        "NormalizedItem",
        # segments.py
        "MarketSegment",
        "SEGMENT_MARKET_TZ",
        "SEGMENT_MARKET_TZ_LABEL",
        # briefing.py
        "TELEGRAM_MESSAGE_LIMIT",
        "Briefing",
        "BriefingNotification",
        # coverage.py (u22, u32)
        "SourceCollectionReport",
        "SourceOutcome",
        "SourceStatus",
        "SourceTier",
        "sanitize_source_error_message",
        # results.py
        "FailureContext",
        "FailureStage",
        "PipelineResult",
        "PipelineStatus",
        "SendResult",
        # carryover.py (u52)
        "BriefingCarryover",
        "CarryoverEventType",
        "CarryoverItem",
        "CarryoverStatus",
        "status_label_kr",
    }
)


def test_all_matches_expected_set() -> None:
    assert set(models.__all__) == EXPECTED_PUBLIC_NAMES


def test_each_name_resolves_in_module() -> None:
    for name in EXPECTED_PUBLIC_NAMES:
        assert hasattr(models, name), f"models.{name} missing"


def test_star_import_does_not_leak_internals() -> None:
    namespace: dict[str, object] = {}
    exec("from investo.models import *", namespace)
    leaked = set(namespace) - EXPECTED_PUBLIC_NAMES - {"__builtins__"}
    assert not leaked, f"star import leaked private names: {leaked}"


def test_internal_helpers_not_re_exported() -> None:
    # The leading-underscore submodule ``_validators`` *is* bound to the
    # package at import time (Python always binds submodules to their
    # parent), but its helper functions must never appear on the public
    # ``investo.models`` surface. ``__all__`` and star-import isolation
    # carry the actual contract; this test pins the helper-name check.
    for forbidden in ("reject_blank_strict", "reject_blank_preserve", "ensure_tz_aware"):
        assert not hasattr(models, forbidden), f"{forbidden} should be private"
    # The submodule is allowed to exist (Python implementation detail) but
    # must not appear in ``__all__``.
    assert "_validators" not in models.__all__
