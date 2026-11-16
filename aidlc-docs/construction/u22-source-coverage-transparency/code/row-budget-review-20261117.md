# Independent code review: u22 data-confidence row budget

- Date: 2026-11-17
- Reviewer: separate `card_overflow_review` agent, per dev-investo Step 5.1.
- Base: `6d526e9b07641cf60f91de148f0217e3d9b22e48`.
- Scope: full reads of `src/investo/visuals/cards.py`, `src/investo/visuals/render.py`, `tests/unit/visuals/test_data_confidence_row_budget.py`, and the follow-up code-generation plan. Supporting reads covered `SourceOutcome`, `SegmentCoverage`, and the public-quality projection.
- Status: **PASS — no blocking or nonblocking findings in this change.**

## Summary

| Category | Result | Evidence |
|---|---|---|
| Correctness | Pass | Overflow compacts each present status, preserving healthy adapter count and original coverage; groups of one and cards of at most four rows keep existing detail/order. |
| Safety | Pass | Failure details reuse sanitized outcomes; SVG cleanup and escaping remain active. No new sensitive sink, IO, dependency, or credential. |
| Reliability | Pass | Observed 3 failed / 7 zero / 2 skipped / 16 ok and the variant without the three healthy new sources both produce four rows. Long derived details remain within 160 characters. |
| Maintainability | Pass | Shared visible-row constant; small pure compaction/bounding helpers; unchanged twelve-row direct-input contract. |
| Test coverage | Pass | 20 new regression/edge/integration cases plus existing card/render/asset tests; independent status-combination enumeration. |

## Protocols applied

| Protocol | Trigger and analysis | Result |
|---|---|---|
| Security boundary | Followed sanitized `SourceOutcome.from_failure` → card detail → existing text cleanup/public projection → HTML escaping. Count labels use readable source nouns and pass the existing forbidden-fragment check; projection rules are unchanged. No authentication, shell, path, or network change. | No issue |
| Memory | Inspected intermediate source rows/group lists and their lifetimes. Allocation is O(n) in already-collected adapter outcomes, local to one card build; output is bounded to four rows. No retained cache or accumulator. | No issue |
| Performance | Three fixed status scans plus healthy-row scan are O(n), not O(n²). Card construction is per-segment; no new repeated IO, regex compilation, or logging. | No issue |

Concurrency, resource-lifecycle, and data-integrity protocols are not triggered by the production diff: it changes only deterministic projections. Existing asset writing is exercised by the integration test, not modified here.

## Validation independently executed

| Check | Result |
|---|---|
| `ruff check` on the two source files and new test | Pass |
| `ruff format --check` on those three files | Pass |
| `mypy src/investo/visuals/cards.py src/investo/visuals/render.py` | Pass |
| Focused pytest: new row-budget tests + existing cards, render, assets | **76 passed in 1.21 s** |
| Enumeration of each status count from 0 through 5 | **1,296 combinations passed**: at most four rows, exact present-status set, healthy count preserved, item count unchanged |

The new tests exercise synthetic outcome inputs with the incident's observed counts. They do not claim provider-payload replay or full LLM/publication execution. Rendered PNG appearance, broader test selection, and shared-workspace integration remain the implementing agent's validation responsibilities.

## Project-rule and self-review checklist

- [x] No new SDK/API/LLM calls or paid integration; dependencies unchanged.
- [x] Module imports preserve the existing boundary; only a same-module-family constant is newly imported.
- [x] Existing SVG disclaimer and prepared briefing disclaimer are asserted by the integration test; publish/notify gates and channel separation are untouched.
- [x] Complete source outcomes, coverage status, item/source counts, reasons, and missing categories retain their original values.
- [x] Mixed skip reasons are not falsely merged into a single universal cause: aggregate detail is explicitly marked `대표`.
- [x] Empty, single-status, mixed-status, 4/5-row boundary, 12/13-row regression, 1,000-source stress, long detail, redaction, and XML escaping paths are covered.
- [x] Existing direct-input six-row renderer truncation test still passes, preserving compatibility.
- [x] No new failure-swallowing, resource ownership, concurrent mutation, or hardcoded secret.

## Findings and technical debt

Critical/High: none. Medium: none. Low: none. No new TECH-DEBT candidate.

The card remains a compact summary: aggregate rows intentionally show one representative source/reason, while the complete source outcomes remain available to existing detailed diagnostics. This is the accepted design, not a loss of collection truth. No deployment or remote state change was performed by this reviewer.
