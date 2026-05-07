# Code Generation Plan: `u23 notification-actionability`

**Date**: 2026-05-07
**Unit**: u23 notification-actionability
**Stage**: Code Generation

---

## Goal

Make segmented public alerts more actionable and make notification failures visible to the operator when publish succeeds.

---

## Definition of Done

- [ ] Each segment alert block includes a compact status tag and inline detail link.
- [ ] The footer/link structure remains readable within Telegram limits.
- [ ] Markdown parse fallback does not expose raw formatting artifacts.
- [ ] Notification failure in an otherwise successful publish is operator-visible.

---

## Steps

### Step 1 — Segment Alert Layout

- [ ] Add compact status tags to each segment block.
- [ ] Move each segment detail link into the corresponding block.
- [ ] Keep message length accounting and URL preservation tests green.

### Step 2 — Plain Fallback Quality

- [ ] Ensure Markdown parse fallback uses a clean plain-text message.
- [ ] Add tests that raw markdown markers are not exposed after fallback.

### Step 3 — Partial Notify Visibility

- [ ] Make notify failure in otherwise successful segmented publish operator-visible.
- [ ] Preserve existing SUCCESS/PARTIAL/FAILED exit-code semantics.

### Step 4 — Verification

- [ ] Run notifier and orchestrator targeted tests.
- [ ] Run full quality gate.

