"""Compatibility exports for the shared core market-fact verification gate."""

from investo._internal.numeric_verify import (
    WINDOW,
    ConflictDetail,
    CoreFactVerificationReport,
    NumericGateAction,
    aggregate_source_facts,
    find_body_value,
    render_downgrade_callout,
    verify_core_facts,
)

__all__ = [
    "WINDOW",
    "ConflictDetail",
    "CoreFactVerificationReport",
    "NumericGateAction",
    "aggregate_source_facts",
    "find_body_value",
    "render_downgrade_callout",
    "verify_core_facts",
]
