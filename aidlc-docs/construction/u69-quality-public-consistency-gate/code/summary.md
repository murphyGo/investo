# u69 quality-public-consistency-gate — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u69 quality-public-consistency-gate
**Status**: Complete (5/5 steps)

## Goal

Make the public quality state canonical: one snapshot per `(date)` drives quality-history rows, the rendered quality dashboard, index summaries, segment status labels, and replay validation, so failed/zero/limited/partial states are impossible to hide behind contradictory public dashboard numbers (plan Problem Statement / Goal). No new severity enum or KPI family is introduced — u69 wraps the existing u54/u62/u65 data models (AC-69.5).

## Scope

In scope: canonical snapshot build/load per date; cross-surface consistency checks over `quality_history.jsonl`, segment markdown status blocks, `site_docs/quality.md`, index labels, and replay output; deterministic publish-time and replay-time failure on contradiction; rendering-path fix so an empty/lagging `coverage.jsonl` cannot under-render the failed-source floor.
Out of scope: redefining severity tiers (`normal`/`partial`/`limited`/`failed`), new source adapters, rewriting coverage collection, replacing the u65 replay CLI, backfilling historical archive content.

## Stage Decision

- **Functional Design — SKIP**. No new domain entity; the design is a rendering/validation contract over existing quality snapshot/coverage models (`SegmentCoverage`, `QualityKPIs`, `quality_history.jsonl`). Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP**. No new external source, network call, dependency, secret, or runtime budget. The consistency check is local file/metadata validation.

## Key Deliverables

- `src/investo/publisher/quality_consistency.py`: new canonical validator. Public surface:
  - `build_canonical_snapshot` — one `CanonicalQualitySnapshot` per date.
  - `check_quality_consistency` — pure validator returning deterministic findings.
  - `validate_date_quality_consistency` — date-scoped convenience wrapper.
  - `reconcile_kpis_with_history` — floors dashboard KPI counters up to `quality_history.jsonl` evidence.
- Stable error codes: `quality.status_mismatch`, `quality.failed_count_mismatch`, `quality.denominator_unknown_but_evidence_present`, and `quality.quality_page_missing` (recorded as **skip**, never as pass/fail).
- Wiring (read/validate only — no new collection):
  - `src/investo/publisher/briefing_replay.py` (u65 harness): validator runs offline (no network/LLM); replay context extended with `quality_page_path: Path | None`; `quality_page_missing` -> warn, contradiction -> error; archive read-only (no mutation).
  - `src/investo/publisher/site_index.py`: `update_quality_page` calls `reconcile_kpis_with_history` so an empty/lagging `coverage.jsonl` cannot render `실패한 소스 누적 = 0` when history holds failure evidence.
  - `src/investo/orchestrator/pipeline.py`: `_enforce_quality_consistency_gate` + `QualityConsistencyError`; invoked at the publish boundary after quality/index pages render and before commit; added to the rollback `except` path so a contradiction aborts publish cleanly.
- Tests: `tests/unit/publisher/test_quality_consistency.py` (per mismatch class), `tests/unit/publisher/test_briefing_replay.py` (2026-05-22-style contradiction replay), `tests/unit/publisher/test_quality_page.py` (dashboard reconciliation).

## Canonical Snapshot Contract

`CanonicalQualitySnapshot` — exactly one per date.

| Field | Canonical source | Validated consumers |
|-------|------------------|---------------------|
| worst-status | segment markdown `**데이터 상태**` (+) `quality_history.jsonl.worst_severity` (u54 worst-wins; **no severity re-definition**) | `quality.md`, history row, segment block, index label, replay |
| has-failed-evidence | segment markdown `실패 N>0` OR history `total_failed_sources>0` | `quality.md` `실패한 소스 누적`, segment block, replay |
| dashboard failed/zero counters | `coverage.jsonl` via `compute_quality_kpis`, **reconciled up to** history evidence by `reconcile_kpis_with_history` | `quality.md` |
| body-used count | `SegmentCoverage.body_used_count`, `미집계` when unknown (pre-existing u62 behavior, unchanged) | segment status block |

The worst-status comparison covers index labels because they render the same history worst-status; no independent index recompute exists.

## Module Boundary

`quality_consistency.py` imports only `briefing.segments` (`MarketSegment` / `CoverageStatus` / labels) — same precedent as the existing `site_index` / `briefing_replay` consumers; `QualityKPIs` is referenced under a `TYPE_CHECKING` guard. Not a boundary violation (orchestrator-only cross-unit import rule upheld; the validator is publisher-internal).

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-69.1 | For one `(date, segment)`, `quality.md` / `quality_history.jsonl` / segment markdown status / index status cannot disagree silently | MET | `check_quality_consistency` codes `status_mismatch` / `failed_count_mismatch`; publish gate + replay; `test_quality_consistency.py` |
| AC-69.2 | Same-day aggregate status uses the worst segment status already defined by u54/u62 | MET | worst-status = segment markdown (+) history `worst_severity`; no severity re-definition |
| AC-69.3 | Denominator-zero / unknown rendered only when canonical snapshot genuinely lacks evidence | MET | `quality.denominator_unknown_but_evidence_present`; `reconcile_kpis_with_history`; `test_quality_page.py` |
| AC-69.4 | u65 replay reports deterministic findings for contradiction fixtures | MET | `briefing_replay.py` validator (skip->warn / contradiction->error); `test_briefing_replay.py` |
| AC-69.5 | No new severity enum / KPI family / external source / dependency / paid service | MET | reuses u54/u62/u65 models; `quality_consistency.py` adds only a snapshot dataclass + validator |

## FD Divergences Ratified

None. FD was SKIP (no entity). No code-vs-spec divergence to ratify.

## 2026-05-22 Live Finding (measured; unmodified — out of scope)

Running the new replay against the live archive flags 2026-05-22 with `quality.denominator_unknown_but_evidence_present`: the committed `site_docs/quality.md` renders failed count `0` / `n/a` while the bundle holds failure evidence. The render-path fix (`reconcile_kpis_with_history` in `update_quality_page`) corrects **future** publishes, but the already-committed stale `site_docs/quality.md` is **not** backfilled (historical archive repair is a plan Non-Goal). Registered as **DEBT-073**.

## TECH-DEBT Registered

- **DEBT-073** — backfill/repair past stale `site_docs/quality.md` (2026-05-22 `denominator_unknown_but_evidence_present`) and empty/lagging `archive/_meta/coverage.jsonl` (`outcomes:[]`) rows that pre-date the render-path fix; plus an optional operator runbook section explaining dashboard interpretation. Low.

## Potential Risks

- The publish-boundary gate is now **blocking**: a genuine contradiction aborts publish before commit (intended). Operators must watch for `QualityConsistencyError` in pipeline logs. False-aborts are avoided because a missing `quality.md` is recorded as **skip**, not a contradiction.

## Verification Gate

- ruff check: clean
- ruff format: clean
- mypy --strict: 138 files clean
- pytest: 2504 passed
- mkdocs build --strict: pass
