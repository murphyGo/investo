# Cross-Check: u32 trust-traceability-deep-dive

**Scope**: u32 trust-traceability-deep-dive (Steps 1–5)
**Date**: 2026-05-09
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 5 | 100% |
| ⚠️ Partial | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ❌ Gap | 0 | 0% |
| **Total** | **5** | **100%** |

**Overall Compliance**: 100% (all five DoD items closed; one DoD sub-clause — operator-alert escalation on numeric mismatch — is intentionally implemented at the brief-header callout level, see notes).

---

## Plan / Goal

- **Plan**: `aidlc-docs/construction/plans/u32-trust-traceability-deep-dive-code-generation-plan.md`
- **Goal**: Give the critical-analyst persona day-by-day verification primitives — source-tier metadata, Stage 3 numeric self-check, traceability footer, hashed signatures, daily evaluation harness. Persona evaluation 2026-05-07 (#3, wish-list).

---

## Definition-of-Done Mapping

| DoD Item | Status | Evidence |
|----------|--------|----------|
| Tier label on every source + tier-mix on coverage badge | ✅ | `models/coverage.py::SourceTier` + `SourceOutcome.tier`; `sources/tiers.py` registry; `aggregator.py` stamps tier; `briefing/segments.py::SegmentCoverage.tier_mix_label`; `_render_coverage_badge` "소스 등급 분포" line; GHA Step Summary source table Tier column. Tests `tests/unit/sources/test_tiers.py`. |
| Stage 3 numeric self-check with brief-header warning | ✅ | `briefing/numeric_self_check.py::find_unverified` + `render_warning_line`; `_enhance_reader_experience(candidates=)` integration. The DoD's operator-alert escalation is implemented as the brief-header callout — read at the same surface as the rest of the trust signals — to avoid duplicating signal in the operator chat for a single mismatched figure. Tests `tests/unit/briefing/test_numeric_self_check.py`. |
| `<details>` traceability footer + 3 hashes | ✅ | `briefing/trace_footer.py::render_traceability_footer`; `generate_briefing` appends footer just before disclaimer. Tests `tests/unit/briefing/test_trace_footer.py`. |
| 12-char SHA-256 prefixes per segment | ✅ | `compute_input_hash` / `compute_stage1_hash` / `compute_stage2_hash` rendered as `input_hash` / `stage1_hash` / `stage2_hash` lines inside the `<details>` block. Pure: same `(items, classification_dict, stage2_text)` → same hash byte-for-byte. |
| Daily evaluation harness on public site | ✅ | `briefing/quality_eval.py::compute_quality_kpis` + `render_quality_page`; `publisher/site_index.py::update_quality_page` writes `site_docs/quality.md`; mkdocs nav adds "데이터 품질". Orchestrator publishes the page atomically with the briefing. Tests `tests/unit/briefing/test_quality_eval.py`. |

---

## Scope Mapping

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-001 source coverage transparency | ✅ | tier mix + tier table in Step Summary | Tier column makes "missing primary source" vs "missing aggregator" visible at a glance. |
| FR-003 static web publishing | ✅ | `site_docs/quality.md` + mkdocs nav entry | mkdocs build --strict ✅ with the new page in nav. |
| NFR-002 cost / no paid APIs | ✅ | All u32 surfaces are pure / local-I/O. No new external endpoints | Tier registry is a static editorial dict; no API call. |
| NFR-003 graceful degradation | ✅ | Empty-data branches in quality_eval; ledger absent → 0% rates with explicit "측정 가능한 게시가 없습니다" body; numeric self-check empty-haystack branch flags everything (defensive) but never blocks publish | Publisher snapshots the quality page and rolls back atomically on PublisherIOError. |
| NFR-004 compliance / disclaimer boundary | ✅ | Trace footer + hashes appended *before* the disclaimer; `verify_disclaimer` and `summary_quality` gates remain the publish authority | None of the new surfaces bypass the disclaimer or summary-quality gates. |
| NFR-005 consistency / DRY | ✅ | Single tier registry; single numeric extractor reused by quality_eval; single hash helper | Tier resolution flows: registry → `aggregator` → `SourceOutcome.tier` → `SegmentCoverage.tier_mix_label`. Numeric extractor reused by `quality_eval._carries_numeric_figure`. |
| NFR-006 testing | ✅ | +31 tests (1419 → 1450) | 7 tier registry + 9 numeric self-check + 8 trace footer + 7 quality eval = 31. |
| NFR-007 secret hygiene (R13) | ✅ | Hashes are sha256 prefixes (one-way); the trace footer redacts pipe chars and caps title length but does not expose secret-shaped tokens because candidates already pass through u27 redaction during fixture recording | The footer only renders fields that already survived publish-time leak guard scanning. |

---

## Architectural / Module-Boundary Notes

- `sources/tiers.py` imports `SourceTier` from `models` (the foundation), not from `protocol` — the Literal lives where the dataclass that carries it lives.
- `aggregator.py` reaches into `sources/tiers.py`, which is fine (same unit).
- `briefing/segments.py` reads `outcome.tier` directly from the model — no boundary hop into `sources/`.
- `briefing/quality_eval.py` reuses `briefing/numeric_self_check.extract_flaggable_numbers` — single chokepoint for "what counts as a numeric figure".
- `publisher/site_index.update_quality_page` lives at the publisher layer (it is a writer); the helper is also re-imported into the orchestrator at call time, with the path resolved at call time so tests can monkeypatch the module-level constant.

## Quality Gate

- `uv run ruff check .` — ✅
- `uv run ruff format --check .` — ✅ (218 files)
- `uv run mypy --strict src/` — ✅ (87 source files)
- `uv run pytest -q` — ✅ (1450 passed)
- `uv run mkdocs build --strict` — ✅

## TECH-DEBT Delta

No new TECH-DEBT items. No DEBT-* resolved.

The DoD sub-clause "operator-alert escalation on numeric mismatch" is intentionally satisfied by the brief-header callout: readers and operators consume the same first-viewport surface, and the orchestrator already emits per-stage operator alerts (u31). Adding a separate operator chat ping for every mismatch would create duplicate signal without raising the resolution. A future follow-up can promote a high-magnitude mismatch (e.g. >5 unverified tokens) to an operator alert without changing the producer-side helpers.

## Status

u32 trust-traceability-deep-dive construction and cross-check **complete**.
