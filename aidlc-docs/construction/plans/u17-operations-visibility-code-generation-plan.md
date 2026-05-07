# Code Generation Plan: `u17 operations-visibility`

**Date**: 2026-05-07
**Unit**: u17 operations-visibility
**Stage**: Code Generation

---

## Goal

Make partial-success and run diagnostics visible to the operator without requiring manual log archaeology.

---

## Definition of Done

- [ ] Public Telegram notification failure is surfaced even when archive publishing succeeds.
- [ ] Pipeline result includes actionable partial-failure context.
- [ ] GitHub Actions can show briefing URLs, stage timings, and notify errors in a concise summary.
- [ ] Diagnostics redact secrets and chat IDs.

---

## Steps

### Step 1 — Partial Result Metadata

- [ ] Extend pipeline result metadata for partial notify failures.
- [ ] Preserve current success/failed/partial semantics.
- [ ] Add tests for partial public-channel failure.

### Step 2 — Operator Surface

- [ ] Add GitHub Step Summary output or operator alert for partial failures.
- [ ] Include stage timings, segment URLs, and short error context.
- [ ] Redact token-like and chat-id-like values.

### Step 3 — Optional Doctor Command

- [ ] Evaluate whether a small diagnostics script is useful now.
- [ ] If added, test env preflight and latest archive checks.
