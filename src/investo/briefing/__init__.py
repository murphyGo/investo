"""Briefing Generator (u2) — two-stage Claude Code CLI flow (US-002, US-009).

This package consumes ``list[NormalizedItem]`` from ``investo.sources``
and produces a ``Briefing`` (defined in ``investo.models``) by:

1. Stage 1 — classification: a Claude Code CLI prompt that assigns each
   item to one of sections {2, 3, 4, 5} or to ``unassigned``.
2. Stage 2 — synthesis: a second Claude Code CLI prompt that writes
   six markdown sections of Korean prose.
3. Disclaimer auto-insert (NFR-004) — section ⑦ is appended
   programmatically, never authored by the LLM.
4. PII / secret leak guard — markdown is scanned before the
   ``Briefing`` model is constructed.

The package's public surface is finalized in Step 10 of the
Code Generation plan; this docstring is the bootstrap placeholder.

Reference:
    aidlc-docs/construction/u2-briefing/functional-design/
    aidlc-docs/construction/u2-briefing/nfr-requirements/
"""

from investo.briefing.quality_eval import QualityHistoryRow, compute_quality_history
from investo.briefing.quality_history import (
    QualitySnapshot,
    append_quality_snapshot,
    resolve_quality_history_path,
)

__all__ = [
    "QualityHistoryRow",
    "QualitySnapshot",
    "append_quality_snapshot",
    "compute_quality_history",
    "resolve_quality_history_path",
]
