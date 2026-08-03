# Cross-Check: u133 watchlist-registry-source-impact-suppression

**Scope**: u133 watchlist-registry-source-impact-suppression
**Date**: 2026-08-03
**Checked by**: Codex
**Baseline**: `a475dd2`
**Implementation head**: `6a5e227`

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Complete | 7 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **7** | **100%** |

**Overall Compliance**: 100%

## Scope Mapping

The unit definition maps u133 to FR-002, FR-004, FR-008, FR-009, NFR-003,
NFR-006, and R13
(`aidlc-docs/inception/application-design/unit-of-work.md:1905`). This report
checks the bounded u133 contribution to those project requirements.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 AI briefing | Complete | `src/investo/briefing/prompts.py:258`, `tests/unit/briefing/test_prompts.py:185` | Stage 2 treats registry rows as entity evidence only and forbids a registry-only §⑤ subsection. |
| FR-004 Telegram notification | Complete | `tests/unit/notifier/test_summary.py:395`, `tests/unit/briefing/test_watchlist_impact.py:327` | Terminal typed Telegram formatting receives only public projection text; registry count/reason/source/title do not leak. |
| FR-008 segmented briefing | Complete | `src/investo/orchestrator/pipeline.py:2149`, `tests/unit/orchestrator/test_run_pipeline.py:1348` | Each segment's visual watchlist input is independently projected before finalization. |
| FR-009 reader-facing format | Complete | `src/investo/orchestrator/pipeline.py:1553`, `tests/unit/publisher/test_watchlist_registry_regression.py:24` | Site, visual, per-term, daily, and Telegram public rows/counts use Direct+Related only; daily diagnostics stay collapsed and redacted. |
| NFR-003 reliability | Complete | `src/investo/briefing/watchlist_impact.py:137`, `tests/unit/briefing/test_watchlist_impact.py:99` | Unknown/non-registry sources keep the established path; registry-only input uses the existing no-public state without failure. |
| NFR-006 testing | Complete | `tests/unit/sources/test_source_specs.py:87`, `aidlc-docs/construction/u133-watchlist-registry-source-impact-suppression/code/step-7-quality-gate.md:5` | Exact-set, mixed-input, cross-surface, fixture, rollback, concurrency, and terminal DTO regressions pass in the 3,138-test planned gate. |
| R13 secret/public diagnostics hygiene | Complete | `tests/unit/publisher/test_watchlist_daily_page.py:120`, `tests/unit/publisher/test_watchlist_registry_regression.py:24` | Diagnostics expose only term/source/reason inside `<details>`; full title/summary/URL and private metadata remain absent. |

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-133.1: The reconstructed 2026-06-30 public callout excludes registry rows and exposes no registry title. | Complete | Six accepted MSFT/NVDA/TSLA rows project to zero public rows; exact no-public state and title absence are pinned in `tests/unit/publisher/test_watchlist_registry_regression.py:24`. |
| AC-133.2: Registry matches appear only in collapsed diagnostics with R13-safe `reference-registry` wording. | Complete | Routing is pre-classification at `src/investo/briefing/watchlist_impact.py:293`; exact single-occurrence containment is tested in the rendered regression. |
| AC-133.3: Site, Telegram, visual, and daily counts agree on public rows. | Complete | Visual uses `public_impact()` at `src/investo/orchestrator/pipeline.py:2157`; per-term snapshot/write share `public_matches()` at line 1559; Telegram terminal DTO and daily public counts are covered by dedicated tests. |
| AC-133.4: u64 matching and u73 grouping semantics remain unchanged. | Complete | Matcher code is untouched; registry rows remain accepted before source-class routing, and a same-ticker non-registry row stays Direct in `tests/unit/briefing/test_watchlist_impact.py:99`. |
| AC-133.5: Stage 2 pins entity-only, same-run, same-ticker non-registry corroboration and registry-only suppression. | Complete | All clauses are present at `src/investo/briefing/prompts.py:258` and independently asserted in `tests/unit/briefing/test_prompts.py:185`; prompt size is 20,271 bytes under 20,300. |
| AC-133.6: u101 entity verification continues unchanged. | Complete | Registry items remain collected and raw matcher output remains available; no u101 source/model/guard file changed, and the full publisher scope including terminal entity-guard regressions passed. |

## Fixed Contracts

| Contract | Status | Evidence |
|----------|--------|----------|
| 1. `reference_registry=False` by default; exact active set is Nasdaq directory + SEC company facts. | Complete | `src/investo/_internal/source_specs.py:34`, exact-set test at `tests/unit/sources/test_source_specs.py:87`. |
| 2. Accepted registry matches route to diagnostics, never Direct/Related/public count. | Complete | Immutable `replace` copy at `src/investo/briefing/watchlist_impact.py:137`; routing test at `tests/unit/briefing/test_watchlist_impact.py:68`. |
| 3. Every public surface counts non-registry public rows and preserves the existing zero-row state. | Complete | Behavior-level orchestrator tests at `tests/unit/orchestrator/test_run_pipeline.py:1348` and `:4015`; exact site/Telegram state tests pass. |
| 4. Stage-2 §⑤ registry narration rule is present. | Complete | `src/investo/briefing/prompts.py:258`; prompt tests at `tests/unit/briefing/test_prompts.py:185`. |
| 5. Impact-center routing is the deterministic backstop; no new scanner. | Complete | Only source spec, prompt, impact-center, and pre-seal routing changed; matcher/scanner/public gate families are untouched. |

## Definition of Done

| Unit DoD | Status | Evidence |
|----------|--------|----------|
| Public impact count excludes the production registry shape. | Complete | Six-row production regression yields zero public rows and no `N건 확인` string. |
| Registry matches appear only in collapsed R13-safe diagnostics. | Complete | Six unique term/source/reason rows occur once each inside `<details>` and nowhere in public regions. |
| §⑤ does not narrate a registry-only listing update. | Complete | Same-run, same-ticker non-registry corroboration is mandatory in the Stage-2 prompt; deterministic public projection remains authoritative. |
| Telegram and visual counts agree with site; matcher grouping is unchanged. | Complete | Renderer, terminal DTO, visual-stage, per-term publish, and same-ticker mixed-input regressions pass. |

## Verification

- Ruff and format passed all 11 changed Python files.
- `mypy src` passed 248 source files.
- Briefing, notifier, publisher, visuals, and sources suites passed 3,138 tests.
- `uv lock --check`, u133 fixture JSON parse, and `git diff --check` passed.
- Cumulative fresh-eyes review approved AC-133.1-6 and Fixed Contracts 1-5
  with no Critical, High, Medium, or Low findings; 23 independent targeted
  tests passed.
- Property-Based Testing remains Partial and Security Baseline remains declined;
  no new dependency, source, credential, network, external-I/O, or cost surface
  was introduced.

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Existing ownership | Complete | Source class is single-homed in `SourceSpec`; public enforcement reuses u73's impact center. |
| Segment/finalization isolation | Complete | Visual projection occurs pre-seal; terminal notifier consumes only validated `PublicNotificationSummary` DTOs. |
| Graceful degradation | Complete | Unknown/non-registry/unconfigured/coverage-hold branches preserve existing behavior and wording. |
| Zero-cost / free API | Complete | No dependency, source, HTTP call, credential, or paid service was added. |
| Secret hygiene | Complete | The fixture contains no raw payload, URL, credential, private destination, or private metadata. |
| No archive backfill | Complete | The production shape is reconstructed in tests; committed archive/site history is unchanged. |

## QA Verdict

**APPROVE**

No Critical, High, Medium, or Low finding remains. The implementation matches
the unit definition, Fixed Contracts 1-5, Definition of Done, six acceptance
criteria, and all bounded project requirement mappings.

## Gaps Analysis

No u133 gap found.

## Proposed Actions

- No development-plan additions.
- No TECH-DEBT items.
- u133 has no remaining construction work.
