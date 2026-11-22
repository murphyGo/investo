# u157/u158 follow-up: bounded event validation feedback (2026-11-23)

## Authorization and evidence

User `진행시켜` follows the report of remaining intermittent classification/fact-grounding failures. Proceed with a bounded local repair, tests, independent review and cross-check. Commit/deployment and live publication are outside this implementation step.

Production code `3ce35148947db7f5ec8c4011578e078d03ee19b7` failed domestic classification on Nov 17/18 (`invalid_evidence`) and synthesis on Nov 20 (`event.fact_unsupported`). The three classification attempts had identical prompt byte counts. Code inspection confirms only the fact-metadata subtype currently receives a repair hint; other closed evidence/schema diagnostics are discarded from retry instructions. Stage 2 fact failures receive only a generic envelope hint. Nov 19 instead hit the terminal `event.evidence_invalid` gate after successful generation. Nov 21 succeeded.

Failed raw LLM responses were intentionally not retained (`last_stdout=None`). These logs establish failure stages and a retry-feedback gap, not a byte-exact reconstruction of the rejected output or proof of a particular false-positive validator. Keep private logs outside tracked files. No validator relaxation or fabricated evidence.

## Stage Decision

- Functional Design: Skipped — bounded follow-up to existing u157/u158 strict two-stage retry contract; no new source/data schema, generation stage, publication policy or workflow.
- NFR Requirements: Skipped — reuse FR-023, NFR-002/003/004/005/006, existing u157/u158 NF3/NF6/NF7/NF9/NF10 and R13 source-free diagnostics. No new network call, timeout, attempt count, cost, raw output persistence or secret surface.
- NFR Design / Infrastructure Design: Skipped — existing CLI runner, retry budget and terminal gate unchanged.
- Existing extension scope: Security Baseline declined; Partial PBT applies to pure serialization/normalization functions only. Existing round-trip and boundary regressions remain selected.

## Design and acceptance criteria

1. Stage 1 event retries receive only sanitized closed diagnostics and fixed repair instructions for document/revision ownership, Unicode codepoint span bounds, blank spans, required relation/impact/object evidence, date/timing consistency, exact period/unit metadata, schema and item-ID errors. First-attempt and legacy off/shadow prompts remain unchanged.
2. Stage 2 fact/evidence failures receive concrete fixed instructions about required fact IDs, source refs, literal numbers/units and actual/forecast roles. Selected event membership and required facts must be preserved. Unknown `event.*` text is mapped to `event.output_invalid`, never echoed as arbitrary model text.
3. Reuse existing attempts/backoff/time budget and rebuild feedback from the latest failure without accumulating prior failed text. Invalid repeated outputs remain blocked with no stdout/stderr leak or automatic zero-event success.
4. Log bounded closed codes at each rejected event attempt using existing logging; no source excerpts, URLs, item values, malformed response or raw exception text. Preserve the existing public error strings.
5. Exercise corrected second responses through actual `_classify`/`_synthesize` validators, repeated rejection, privacy, bounds, legacy compatibility and module-boundary checks. Synthetic fixtures must not be described as actual failed production payloads.
6. Terminal validation remains unchanged. Without the failed Nov 19 payload, its precise cause is not proven; record this operational acceptance limit rather than weakening or claiming to repair the gate.

## Steps

- [x] 1. Inspect sanitized incident evidence and production/public code differences; isolate latest public base `af3ca28920944880b19b86981f23826fa9b8541d`; record shared workspace hashes.
- [x] 2. Implement bounded feedback in `briefing/_core/classification.py`, `_assembly/markdown_render.py`, and `_core/orchestration.py`.
- [x] 3. Add `tests/unit/briefing/test_event_retry_feedback.py` and update the existing entity-feedback compatibility assertion; prove recovery and fail-closed behavior with synthetic inputs.
- [x] 4. Run scoped static/related regression checks and obtain independent review; resolve findings. Public base: 2,088 related tests; production base: 111 tests; Ruff/format/Mypy and independent review passed.
- [x] 5. Record scoped verification, acceptance limits, session/audit/state; integrate only before-hash-matching owned files into the shared workspace. Completed with owned-file hashes checked and shared HEAD/index preserved.
