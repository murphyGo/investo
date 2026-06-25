# u123 Code Summary: body-evidence-attribution-reconciliation

## Overview

u123 reconciles rendered markdown evidence back into existing quality metadata. It adds a deterministic post-render evidence counter for public body links and verified u55 core facts, then uses that counter in publish, replay, and quality-consistency gates.

## Files Changed

- `src/investo/publisher/evidence_accounting.py` adds `RenderedEvidenceCounts`, public body extraction, known source link detection, verified-fact counting, and `본문 사용` marker repair.
- `src/investo/orchestrator/pipeline.py` computes rendered evidence during segmented publish and before quality snapshot persistence.
- `src/investo/publisher/quality_consistency.py` now detects `quality.body_evidence_untracked` when public body evidence exists but source-count metadata is zero or untracked.
- `src/investo/publisher/briefing_replay.py` now errors on archive markdown with known public evidence and `본문 사용 0/미집계`.
- Tests cover public-body extraction, diagnostics/navigation exclusion, source-name/domain matching, quality consistency, replay, and `figures_presence` / `figures_verified` separation.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Count rendered evidence after reader formatting | The defect was in published artifacts, not source collection. |
| Use known-source domains plus source-name labels | Archive replay often lacks live `SourceOutcome` objects, so domain matching must work offline. |
| Keep severity unchanged | Evidence accounting must not hide limited or failed core source health. |
| Preserve `figures_presence`, fill `figures_verified` from u55 facts | Keep the public dashboard's broad numeric-presence KPI separate from verified core-fact coverage. |

## Validation

- `uv run --extra dev pytest tests/unit/publisher/test_evidence_accounting.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_briefing_replay.py tests/unit/orchestrator/test_domestic_anchor_quarantine.py tests/unit/orchestrator/test_stage_protocol.py tests/unit/orchestrator/test_run_pipeline.py tests/unit/briefing/test_quality_history.py`
- `uv run --extra dev ruff check src/investo/publisher/evidence_accounting.py src/investo/publisher/quality_consistency.py src/investo/publisher/briefing_replay.py src/investo/orchestrator/pipeline.py tests/unit/publisher/test_evidence_accounting.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_briefing_replay.py tests/unit/orchestrator/test_domestic_anchor_quarantine.py`
- `uv run --extra dev ruff format --check src/investo/publisher/evidence_accounting.py src/investo/publisher/quality_consistency.py src/investo/publisher/briefing_replay.py src/investo/orchestrator/pipeline.py tests/unit/publisher/test_evidence_accounting.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_briefing_replay.py tests/unit/orchestrator/test_domestic_anchor_quarantine.py`
- `uv run --extra dev mypy src`

## TECH-DEBT

None.
