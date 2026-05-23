# Code Generation Plan: `u69 quality-public-consistency-gate`

**Date**: 2026-05-24
**Unit**: u69 quality-public-consistency-gate
**Stage**: Code Generation
**Status**: Complete (5/5) — closed 2026-05-24
**Source**: 2026-05-24 ten-subagent user-quality review of the latest generated segmented briefings
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u54 source-status-severity-and-quality-kpi
- u62 quality-status-publish-reconciliation
- u63 partial-bundle-navigation-and-absence-state (non-overlap: u69 checks quality-status labels only, not generated/missing/fallback navigation semantics)
- u65 generated-briefing-quality-replay-harness

---

## Problem Statement

The public quality surfaces can contradict the generated briefing artifacts. In the reviewed latest bundle, segment markdown contained partial/limited conditions, source failures, zero-item/core-source gaps, and `[데이터부족]` language, while `site_docs/quality.md` and quality-history summaries could present failed/zero/limited counts as `0`, `0.0%`, or denominator-unknown in ways that implied the run was healthier than the actual archive.

This is a reader-trust defect. A non-operator reader should not have to reconcile:
- Per-segment status blocks in `archive/{segment}/YYYY/MM/YYYY-MM-DD.md`
- `archive/_meta/quality_history.jsonl`
- `site_docs/quality.md`
- Latest/archive index cards
- Offline replay findings

If these surfaces disagree for the same `(date, segment)`, the safest behavior is a deterministic validation failure before publication, or a replay failure for already-generated artifacts.

---

## Goal

Make the public quality state canonical: one snapshot for a run/date drives quality-history rows, rendered quality dashboard rows, index summaries, segment status labels, and replay validation. The user-facing result is that failed/zero/limited/partial states are impossible to hide behind contradictory public dashboard numbers.

Canonical field source contract:

| Field | Canonical source | Consumers checked by u69 |
|-------|------------------|--------------------------|
| Date-level worst status | `src/investo/briefing/quality_history.py` / `archive/_meta/quality_history.jsonl` | `site_docs/quality.md`, latest/archive index status labels |
| Segment status tier | segment markdown status block plus `SegmentCoverage.status` when available | segment markdown, index labels, replay findings |
| failed/zero source counts | `SegmentCoverage` / `archive/_meta/coverage.jsonl` when present; otherwise quality-history aggregate may mark unknown | `quality.md`, segment status block, replay |
| body-used count | `SegmentCoverage.body_used` when present; unknown is rendered as `미집계`, never as `0` if evidence exists | `quality.md`, segment status block |
| generated/missing segment state | u63 bundle metadata | u69 may compare quality label only; u63 owns navigation/fallback semantics |

---

## Existing Coverage / Deduplication

This unit is not a new quality KPI implementation.

- u54 already defined source-status severity, denominator correctness, and same-day worst-wins behavior.
- u62 already reconciled quality status publication and fixed known `본문 사용 0` misleading output cases.
- u65 already added an offline generated-briefing replay harness.

u69 only closes the remaining contradiction class: **all public surfaces for one generated bundle must agree**. If implementation needs a new helper, it should wrap/reuse u54/u62/u65 data models rather than creating another status enum or KPI schema.

---

## Scope Boundary

In scope:
- Canonical quality snapshot load/build path for `(date, segment)`.
- Consistency checks across `quality_history.jsonl`, segment markdown status, `site_docs/quality.md`, index cards, and replay output.
- Regression fixture that models a contradictory latest bundle.
- Publish-time or replay-time failure when contradictions are detected.

Out of scope:
- Redefining severity tiers (`normal`, `partial`, `limited`, `failed`).
- Adding new source adapters.
- Rewriting coverage collection.
- Replacing the u65 replay CLI.
- Backfilling historical archive content unless a test fixture needs a minimal sample.

---

## Stage Decision

- **Functional Design — SKIP**. No new domain entity is required if existing quality snapshot/coverage models are reused. The design decision is a rendering/validation contract over existing artifacts.
- **NFR Requirements — SKIP**. No new external source, network call, dependency, secret, or runtime budget is introduced. The consistency check is local file/metadata validation.

---

## Implementation Steps

### Step 1 — Inventory canonical quality fields `[x]`
- [x] Identify the existing canonical source for status tier, failed-source count, zero-item-source count, body-used count, and limited/failed segment count.
- [x] Document which field feeds each public surface today.
- [x] Add a small internal adapter only if the fields currently require multiple model shapes.
- **Acceptance**: one table in the implementation notes maps field → canonical producer → rendered consumers. *(see Implementation Notes below)*

### Step 2 — Add cross-surface consistency validator `[x]`
- [x] Implement a pure validator that accepts generated artifact text/metadata for one date and returns deterministic findings. → `src/investo/publisher/quality_consistency.py`
- [x] Compare segment markdown status blocks against `quality_history.jsonl` rows.
- [x] Compare rendered `site_docs/quality.md` totals against canonical per-segment aggregates.
- [x] Compare latest/archive index labels against the same canonical worst status. *(worst-status comparison covers index labels, which render the same history worst-status; no independent index recompute exists)*
- **Acceptance**: validator reports stable error codes `quality.status_mismatch`, `quality.failed_count_mismatch`, `quality.denominator_unknown_but_evidence_present`, `quality.quality_page_missing` (skipped).

### Step 3 — Wire validator into replay and publish surfaces `[x]`
- [x] Reuse u65 replay harness to run the validator for a generated bundle without network/LLM calls.
- [x] Extend replay context with `quality_page_path: Path | None`.
- [x] Add a mandatory publish-boundary consistency gate after quality/index pages are rendered and before commit (`_enforce_quality_consistency_gate` in orchestrator; raises `QualityConsistencyError`, rolled back). `quality_page_missing` recorded as skipped, not passed.
- [x] Already-generated archive replay runs read-only (no archive mutation).
- **Acceptance**: contradictory fixture fails replay; consistent fixture passes.

### Step 4 — Fix rendering paths that drift from canonical snapshot `[x]`
- [x] `update_quality_page` now reconciles the failed-source floor up to the canonical `quality_history.jsonl` evidence (`reconcile_kpis_with_history`) so an empty/lagging `coverage.jsonl` cannot render `실패한 소스 누적 = 0`.
- [x] Index labels already render the canonical history worst-status (no independent recompute) — validated by the worst-status check.
- [x] Denominator-zero renders `n/a`/`0` only when genuinely unknown, not when history evidence exists.
- **Acceptance**: rendered quality dashboard matches the canonical snapshot in tests.

### Step 5 — Tests and docs `[x]`
- [x] Unit tests per mismatch class — `tests/unit/publisher/test_quality_consistency.py`.
- [x] Replay test for the 2026-05-22-style contradiction pattern — `tests/unit/publisher/test_briefing_replay.py`.
- [x] Dashboard reconciliation test — `tests/unit/publisher/test_quality_page.py`.
- [x] Update any runbook/docs that describe quality dashboard interpretation. *(no operator runbook section exists describing dashboard interpretation; no code-owned doc change required. Runbook authoring handed to ops and tracked under DEBT-073 as an optional Low add — see TECH-DEBT.)*
- [x] Ran targeted publisher/replay tests, ruff/format/mypy on changed files, full suite, and `mkdocs build --strict`.

---

## Implementation Notes — canonical field → producer → consumer (Step 1)

| Field | Canonical producer | Rendered consumers (validated by u69) |
|-------|--------------------|----------------------------------------|
| Date-level worst status | `quality_history.jsonl.worst_severity` (u54 keep-worst) reconciled with worst per-segment markdown status block | `site_docs/quality.md`, latest/archive index status labels |
| Segment status tier | segment markdown `**데이터 상태**: {label}` block (reverse-mapped via `COVERAGE_STATUS_LABELS`) | segment markdown, replay findings |
| failed-source count | `quality_history.jsonl.total_failed_sources`; segment markdown `소스 카운트 ... 실패 N` block | `quality.md` `실패한 소스 누적`, segment status block, replay |
| body-used count | `SegmentCoverage.body_used_count` rendered as `미집계` when unknown (pre-existing u62 behavior, unchanged) | segment status block |
| dashboard failed/zero counters | `coverage.jsonl` via `compute_quality_kpis`, **reconciled up to** `quality_history.jsonl` evidence by `reconcile_kpis_with_history` | `quality.md` |

Canonical snapshot type: `CanonicalQualitySnapshot` in `quality_consistency.py`. No new severity enum / KPI family introduced (AC-69.5).

---

## Acceptance Criteria

- **AC-69.1** — For one `(date, segment)`, `quality.md`, `quality_history.jsonl`, segment markdown status, and index status cannot disagree silently.
- **AC-69.2** — Same-day aggregate status uses the worst segment status already defined by u54/u62.
- **AC-69.3** — Denominator-zero / unknown states are rendered only when the canonical snapshot is genuinely missing the evidence.
- **AC-69.4** — u65 replay reports deterministic findings for contradiction fixtures.
- **AC-69.5** — No new severity enum, KPI family, external source, dependency, or paid service is introduced.

---

## Tests / Validation

Expected test areas:
- `tests/unit/briefing/test_quality_history.py`
- `tests/unit/briefing/test_quality_history_keep_worst.py`
- `tests/unit/publisher/test_site_index.py`
- `tests/unit/publisher/test_briefing_replay.py`
- New compact fixture under `tests/fixtures/` if the current replay fixtures do not cover contradictory public surfaces.

Minimum local gate:
- Targeted pytest for publisher/replay quality tests.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if source signatures change.
- `uv run mkdocs build --strict` if rendered docs/site pages are touched.

---

## Non-Goals

- Historical archive repair.
- A new visual quality dashboard.
- Any change to market data collection.
- Any change to Telegram notification semantics except if an existing quality label is reused from the canonical snapshot.
