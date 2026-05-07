# Code Generation Plan: `u23 notification-actionability`

**Date**: 2026-05-07
**Unit**: u23 notification-actionability
**Stage**: Code Generation

---

## Goal

Make segmented public alerts more actionable and make notification failures visible to the operator when publish succeeds.

---

## Definition of Done

- [x] Each segment alert block includes a compact status tag and inline detail link.
- [x] The footer/link structure remains readable within Telegram limits.
- [x] Markdown parse fallback does not expose raw formatting artifacts.
- [x] Notification failure in an otherwise successful publish is operator-visible.

---

## Steps

### Step 1 — Segment Alert Layout

- [x] Add compact status tags to each segment block.
- [x] Move each segment detail link into the corresponding block.
- [x] Keep message length accounting and URL preservation tests green.

### Step 2 — Plain Fallback Quality

- [x] Ensure Markdown parse fallback uses a clean plain-text message.
- [x] Add tests that raw markdown markers are not exposed after fallback.

### Step 3 — Partial Notify Visibility

- [x] Make notify failure in otherwise successful segmented publish operator-visible.
- [x] Preserve existing SUCCESS/PARTIAL/FAILED exit-code semantics.

### Step 4 — Verification

- [x] Run notifier and orchestrator targeted tests.
- [x] Run full quality gate.
