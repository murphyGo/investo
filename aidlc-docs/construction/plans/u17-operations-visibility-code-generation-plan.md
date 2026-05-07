# Code Generation Plan: `u17 operations-visibility`

**Date**: 2026-05-07
**Unit**: u17 operations-visibility
**Stage**: Code Generation

---

## Goal

Make partial-success and run diagnostics visible to the operator without requiring manual log archaeology.

---

## Definition of Done

- [x] Public Telegram notification failure is surfaced even when archive publishing succeeds.
- [x] Pipeline result includes actionable partial-failure context.
- [x] GitHub Actions can show briefing URLs, stage timings, and notify errors in a concise summary.
- [x] Diagnostics redact secrets and chat IDs.

---

## Steps

### Step 1 — Partial Result Metadata

- [x] Extend pipeline result metadata for partial notify failures.
- [x] Preserve current success/failed/partial semantics.
- [x] Add tests for partial public-channel failure.

### Step 2 — Operator Surface

- [x] Add GitHub Step Summary output or operator alert for partial failures.
- [x] Include stage timings, segment URLs, and short error context.
- [x] Redact token-like and chat-id-like values.

### Step 3 — Optional Doctor Command

- [x] Evaluate whether a small diagnostics script is useful now.
- [x] If added, test env preflight and latest archive checks.
