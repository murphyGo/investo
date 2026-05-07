# Code Generation Plan: `u31 operations-resilience`

**Date**: 2026-05-08
**Unit**: u31 operations-resilience
**Stage**: Code Generation

---

## Goal

Strengthen the 1-person operator's 5-minute triage surface and reduce noise via retry/dedup/dry-run primitives.

---

## Definition of Done

- [ ] GHA Step Summary includes a `source_outcomes` table so a failed adapter is visible at a glance.
- [ ] Telegram retry path applies 1-2s backoff and honors the `Retry-After` header.
- [ ] Boot-alert dedup suppresses identical `ConfigError` notifications within a 14-day window.
- [ ] `INVESTO_DRY_RUN=1` mode skips git push and Telegram send while still writing local archive files.
- [ ] Per-source health time series appended to `archive/_meta/coverage.jsonl` (one line per day, append-only).
- [ ] Sunday weekly digest cron sends an operator-chat summary covering 7-day success rate, failed sources, and GHA minutes used.
- [ ] N-consecutive-day FAILED source is auto-detected and surfaced to the operator chat.
- [ ] Retry budget caps total retries per cron run.

---

## Steps

### Step 1 — Step Summary Source Table and Telegram Backoff

- [ ] Extend GHA Step Summary writer with the `source_outcomes` table.
- [ ] Add 1-2s backoff + `Retry-After` handling to the Telegram client.

### Step 2 — Boot-Alert Dedup and Dry-Run

- [ ] Persist boot-alert fingerprints with a 14-day TTL.
- [ ] Wire `INVESTO_DRY_RUN=1` through publisher / notifier.

### Step 3 — Source Health Time Series and Auto-Detect

- [ ] Append daily coverage line to `archive/_meta/coverage.jsonl`.
- [ ] Detect N-day-consecutive FAILED source and emit operator alert.

### Step 4 — Weekly Digest Cron

- [ ] Add Sunday cron + digest renderer to operator chat.

### Step 5 — Retry Budget and Verification

- [ ] Enforce a per-run retry budget across HTTP retry sites.
- [ ] Run targeted ops tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #5 (P1 + wish-list).
