# u22 follow-up: data-confidence visible row budget (2026-11-17)

## Scope and authorization

User request `진행시켜` follows the diagnosed source-row overflow and recommendation to fix it. This authorizes the bounded repair, tests, review, and cross-check. No publish dispatch or release is part of this implementation step. Existing u22 coverage transparency contracts are reused; no new unit ID is allocated.

## Stage Decision

- Functional Design: Skipped — narrow correction to the existing u22 card, without new workflow, cross-module contract, or coverage semantics.
- NFR Requirements: Skipped — reuse reliability, rendering, testing, and sanitized diagnostic contracts; no new IO, dependency, secret, cost, or failure policy.
- NFR Design / Infrastructure Design: Skipped — unchanged.
- Source of requirements: FR-002/003 source coverage; FR-017 quality transparency; FR-018 visual cards; NFR-003/004/005/006 and R13. Existing `u22-source-coverage-transparency/code/summary.md`; runtime finding documented in `docs/cross-checks/2026-11-16-macro-sources-runtime.md` (local follow-up evidence).

## Design and acceptance criteria

1. The builder fits the actual four visible SVG rows. Up to four existing rows keep their exact order/content. The public input model's twelve-row compatibility limit remains unchanged.
2. When overflowing, group into failed → zero → skipped → ok, omitting absent statuses. Non-ok groups use reader-facing labels (`수집 실패 소스 N개`, `0건 반환 소스 N개`, `비활성 소스 N개`) and show exact adapter counts and a clearly marked representative source/reason; singleton groups retain their original row. Preserve the existing healthy summary and count.
3. Derived details fit the 160-character model limit with an ellipsis for truncation. Failure details come only from sanitized SourceOutcome values. SVG escaping and disclaimers remain in force.
4. Do not mutate source outcomes, coverage status, counts, reasons, markdown detail, or publication quality gates. No classification or upstream source fixes.
5. Observed 3 failed / 7 zero / 2 skipped / 16 ok must produce four rows and complete `prepare_segment_visual_assets`, including light/dark variants and provenance. Evidence is an outcome-level replay, not a full LLM/publish replay.

## Steps

- [x] 1. Isolate latest public main, record shared workspace hashes, inspect u22 builder/renderer and incident evidence.
- [x] 2. Update `src/investo/visuals/cards.py` and `render.py` with a shared visible budget and deterministic status compaction.
- [x] 3. Add `tests/unit/visuals/test_data_confidence_row_budget.py`: regression, boundary/large inputs, unchanged small cards, sanitized details, light/dark and asset-path integration.
- [x] 4. Run related tests/static checks, inspect rendered artifacts, obtain independent code review and resolve findings.
- [x] 5. Record scoped build/test and requirements cross-check; integrate only unchanged owned files into the shared workspace, preserving its HEAD/index and unrelated changes.

## Validation strategy

Use the existing Python 3.11 environment with `PYTHONPATH=src`, Node 22 and Cairo when required. Run all visual tests and related coverage/orchestrator tests, scoped ruff/mypy, and appropriate repository checks. Regression fixtures model source outcomes and must never be presented as raw provider payloads. Render both themes for visual inspection. Keep private job logs out of repository artifacts. Independent review is required by dev-investo Step 5.1.
