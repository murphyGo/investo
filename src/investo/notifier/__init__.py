"""Notifier (u4) — Telegram dispatcher (BriefingPublisher + OperatorAlerter).

US-004 (공개 채널) + US-007 (운영자 1:1 chat).

Two clearly-separated dispatcher classes — each takes its own
``chat_id`` at construction time — so the public-channel briefing
and the operator-only failure alert NEVER cross-contaminate (CLAUDE
.md project rule #5). The orchestrator (u5) wires the two from
disjoint environment variables and is responsible for asserting
disjointness.

Both classes follow a non-raising contract: HTTP failures, Telegram
API errors, and timeouts are encoded in :class:`SendResult.ok=False`
with a sanitized error message (bot tokens redacted from any URL
leakage). Programmer errors propagate as-is.

The package's public surface is finalized in Step 6 of the Code
Generation plan; this docstring is the bootstrap placeholder.

Reference:
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
    aidlc-docs/inception/application-design/component-methods.md (C4)
    docs/requirements.md FR-004 + FR-007 + NFR-003
"""

__all__: list[str] = []
