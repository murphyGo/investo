# Code Generation Plan: `u123 body-evidence-attribution-reconciliation`

**Date**: 2026-06-25
**Unit**: u123 body-evidence-attribution-reconciliation
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-23 generated-briefing review, focused on `archive/_meta/quality_history.jsonl` and the three 2026-06-23 segment markdown files.
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u54 source-status-severity-and-quality-kpi is complete; keep the existing severity and count model.
- u65 generated-briefing replay harness is complete; extend replay checks instead of adding a second replay entrypoint.
- u96 quality-current-run-snapshot-sync is complete; append new fields through the current `QualitySnapshot` path only when required.
- u108 reader-facing-quality-language-boundary is complete; keep public prose sanitized while fixing the underlying operator metric.

---

## Problem Statement

The latest reviewed bundle contains body evidence, links, and numeric claims, but the quality metadata still reports the body as untracked:

- `archive/domestic-equity/2026/06/2026-06-23.md` contains multiple linked source references and numeric rows, while the first viewport reports `본문 사용 미집계`.
- `archive/us-equity/2026/06/2026-06-23.md` includes links to Nasdaq, FRED, CFTC, Cboe, and other evidence, but the quality badge still says `본문 사용 미집계`.
- `archive/crypto/2026/06/2026-06-23.md` includes CoinGecko, The Block, CFTC, Treasury, Alternative.me, OKX, and DeFiLlama evidence, but the same body-used marker remains.
- `archive/_meta/quality_history.jsonl` for 2026-06-23 records `figures_presence=0.0` and `fallback_ratio=1.0` despite rendered figures and source links in all three segment files.

This weakens operator trust. The public language projection from u108 can hide raw counters from readers, but the operator still needs the metrics to reflect the rendered artifact.

## Goal

Reconcile rendered markdown evidence with existing quality metrics so the current-run quality snapshot can distinguish "body evidence present but limited core source health" from "body evidence absent or untracked".

## Existing Coverage / Deduplication

- u54 owns severity labels, source counts, and the `body_used_count` concept.
- u62/u69/u96 own quality history and public quality consistency.
- u65 owns replay checks for generated briefings.
- u108 owns public reader-safe wording and must remain unchanged.

This unit only fills the gap where rendered evidence is not reconciled back into `SegmentCoverage` and `QualitySnapshot`. It does not add a new KPI page, severity ladder, source adapter, or LLM prompt.

## Scope Boundary

In scope:
- Add a deterministic rendered-evidence counter for published markdown.
- Feed the counter into existing `SegmentCoverage.body_used_count` or a bounded sibling field used by `QualitySnapshot`.
- Treat verified core figures from u55 and rendered source links as separate evidence classes.
- Extend replay and quality-consistency checks to catch contradictory evidence/metadata pairs.

Out of scope:
- No severity upgrade solely because links appear in prose.
- No source collection or routing changes.
- No public prose wording change outside existing u108 projection.
- No rewrite of `figures_verified`; that remains u55's precision-first KPI.
- No archive backfill.

## Stage Decision

Functional Design: skip. This is an accounting refinement over existing quality entities.

NFR Requirements: skip. No new dependency, source, secret, network call, workflow, runtime budget, or deploy surface.

## Fixed Contracts

### Rendered Evidence Classifier

Create a pure helper with this default contract:

```python
@dataclass(frozen=True, slots=True)
class RenderedEvidenceCounts:
    markdown_links: int
    known_source_links: int
    verified_figure_mentions: int
    body_used_count: int
```

Rules:
- Count only the public body after the first viewport diagnostics are excluded.
- Exclude links inside `<details><summary>수집/품질 진단</summary>`.
- Exclude navigation links in the segment header.
- `known_source_links` counts links whose domain or source label can be mapped to collected `SourceOutcome.name` or known source domains already present in the repo.
- `verified_figure_mentions` counts u55 verified core figures, not arbitrary numbers.
- `body_used_count = max(known_source_links, verified_figure_mentions)` for the first implementation.

### Quality Snapshot Contract

- `SegmentCoverage.body_used_count` remains an integer.
- `QualitySnapshot.figures_presence` keeps its existing range and denominator.
- Limited severity remains limited when core source health is limited, even with `body_used_count > 0`.
- A published segment with `known_source_links > 0` must not render `본문 사용 미집계` in operator diagnostics.

## Implementation Steps

- [x] Add `src/investo/publisher/evidence_accounting.py` with `RenderedEvidenceCounts` and `count_rendered_evidence(markdown, segment, source_outcomes, verified_facts)`.
- [x] Add fixture snippets from the 2026-06-23 domestic, US, and crypto markdown files that include header navigation, collapsed diagnostics, public body links, and numeric facts.
- [x] Update the publish/generate quality assembly in `src/investo/orchestrator/pipeline.py` near `_build_quality_snapshot` and the `SegmentCoverage` map so rendered counts can populate `body_used_count` after reader formatting.
- [x] Keep `figures_presence` denominator behavior from `src/investo/briefing/quality_history.py`; only change the numerator when verified figures are present in rendered body.
- [x] Extend `src/investo/publisher/quality_consistency.py` to detect the contradiction "public body has known evidence but quality metadata says untracked/zero".
- [x] Extend `src/investo/publisher/briefing_replay.py` to report a replay issue when a segment body contains known source links but `body_used_count == 0`.
- [x] Add tests in `tests/unit/publisher/test_evidence_accounting.py`, `tests/unit/publisher/test_quality_consistency.py`, `tests/unit/publisher/test_briefing_replay.py`, and focused orchestrator quality snapshot tests.
- [x] Write `aidlc-docs/construction/u123-body-evidence-attribution-reconciliation/code/summary.md`.

## Acceptance Criteria

1. A segment markdown body with public known-source links records `body_used_count > 0` after publish formatting.
2. Collapsed diagnostics and segment navigation links do not inflate `body_used_count`.
3. A 2026-06-23 US-equity fixture with Nasdaq/FRED/CFTC links no longer produces an untracked body-used state.
4. A 2026-06-23 crypto fixture with CoinGecko/The Block/CFTC links no longer produces an untracked body-used state.
5. `figures_presence` remains `0.0` for a body with links but no verified core figures.
6. `figures_presence` becomes non-zero for a body with verified u55 core figures rendered in public prose or tables.
7. Severity stays `limited` when core source health is limited; evidence accounting does not mask source failure.
8. Replay fails on a fixture where markdown evidence and quality metadata disagree.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_evidence_accounting.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_briefing_replay.py tests/unit/orchestrator/test_run_pipeline.py tests/unit/briefing/test_quality_history.py
uv run --extra dev ruff check src/investo/publisher/evidence_accounting.py src/investo/orchestrator/pipeline.py tests/unit/publisher/test_evidence_accounting.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_briefing_replay.py
uv run --extra dev ruff format --check src/investo/publisher/evidence_accounting.py src/investo/orchestrator/pipeline.py tests/unit/publisher/test_evidence_accounting.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_briefing_replay.py
uv run --extra dev mypy src
```

## Non-Goals

- No new source severity model.
- No quality dashboard redesign.
- No public wording change beyond existing u108 projection.
- No archive backfill.
- No LLM prompt change.
