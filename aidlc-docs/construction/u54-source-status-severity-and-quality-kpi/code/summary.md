# u54 Source-Status Severity & Quality KPI — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u54 source-status-severity-and-quality-kpi
**Status**: Complete (9/9 steps, 44/44 checkboxes)
**FR**: FR-010

## Goal

Prevent briefings from showing `데이터 상태: 정상` when core sources failed or returned 0 items. Make `site_docs/quality.md` report observed coverage truth instead of misleading 0% liveness.

## Quality Gate

| Gate | Result |
|------|--------|
| `ruff check .` | passed |
| `ruff format --check` | 287 files clean |
| `mypy --strict src/` | 112 files, 0 issues |
| `pytest -q` | **1977 passed** (1910 → +67, plan est. +34-42) |
| `mkdocs build --strict` | exit 0 |

## Key Deliverables

- **4-tier severity** (`normal/partial/limited/failed`) with `insufficient → failed` migration of legacy `CoverageStatus`.
- **`SEGMENT_CORE_SOURCES`** frozen constant (domestic 1 / us-equity 2 ≥1 / crypto 2 ≥1).
- **8-row severity decision tree** in `models/coverage.py`.
- **Staleness signal** — `SourceOutcome.latest_item_at` + per-segment `core_staleness_window` (30h/30h/6h).
- **Alert debouncing** — `notifier/severity_debounce.py` requires ≥2 consecutive bad runs on `coverage.jsonl` tail.
- **Same-day worst-wins** — `append_quality_snapshot(keep_worst=True)`.
- **Citation cardinality gate** (Finding #4) — `briefing/citation_cardinality.py` with N=3 threshold, R13-safe `sha1[:12]` url_hash, `claims_per_link` trace column.

## Files

**New (11)**:
- `src/investo/briefing/citation_cardinality.py`
- `src/investo/notifier/severity_debounce.py`
- 9 new test files under `tests/unit/{briefing,notifier}/`

**Modified (13)**:
- `src/investo/briefing/{segments,pipeline,quality_eval,quality_history,watchlist}.py`
- `src/investo/models/coverage.py`
- `src/investo/sources/aggregator.py`
- `src/investo/orchestrator/{pipeline,source_health}.py`
- `src/investo/notifier/summary.py`
- `docs/requirements.md` (FR-010)
- 5 legacy test fixtures (mechanical migration)

## TECH-DEBT candidates

- **D54-A** KRX index adapter `latest_item_at` source — verify FSC-KRX adapter populates `published_at` from response timestamp, not wall clock.
- **D54-B** Claim-entity dictionary drift — orchestrator should thread u53 watchlist via `extra_terms`.
- **D54-C** Promote debounce 2-run → 3-run if KST-cron 24h detection lag still produces spam.
- **D54-D** Cross-segment severity escalation (all-3-limited → page-level red banner).
