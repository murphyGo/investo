# Independent code review: bounded event retry feedback

Date: 2026-11-23. Reviewer: separate `event_retry_review` agent, read-only source review under `code-review/SKILL.md`.

Base: `af3ca28920944880b19b86981f23826fa9b8541d`. Scope: three complete source files (`_core/classification.py`, `_core/orchestration.py`, `_assembly/markdown_render.py`), both complete retry test files, and `u157-u158-event-retry-feedback-code-generation-plan.md`. Supporting parser, evidence validator, narrative validator, runner, and error-contract code was inspected. This report is the reviewer's only authored file.

## Result and prioritized findings

**PASS for the bounded local change. No Critical, High, Medium, or Low defect identified.** This is code-review acceptance, not live operational acceptance or a deployment decision.

| Category | Pass | Warn | Fail | Evidence |
|---|---:|---:|---:|---|
| Correctness | 1 | 0 | 0 | Hints agree with ownership, span, required-fact, field-local evidence and forecast-role validators; validators remain unchanged. |
| Safety | 1 | 0 | 0 | Closed diagnostic/code allowlists at feedback/log boundaries; no failed response, source excerpt, URL or exception context added to logs. |
| Reliability | 1 | 0 | 0 | Latest-failure feedback, existing attempt/backoff/budget flow, repeated-invalid failures remain blocked. |
| Maintainability | 1 | 0 | 0 | Static hint mapping and shared Stage 2 allowlist helper; no new dependency, provider or stateful mechanism. |
| Test coverage | 1 | 0 | 0 | 159 related tests independently passed; static checks passed. Synthetic-fixture scope is explicit. |
| Total | 5 | 0 | 0 | No requested source correction. |

## Protocols applied

| Protocol | Trigger and analysis | Result |
|---|---|---|
| Security boundary | External model JSON enters strict parsers; validation causes flow into retry prompts and new warning logs. Traced both sinks, unknown-code handling, raw-output suppression and CLI input handoff. No authentication or authorization changes. | Stage 1 uses only exact known diagnostics; Stage 2 uses the five `EventErrorCode` members plus `event.output_invalid`. Raw strings and forged diagnostic paths cannot be emitted through these new channels. Prompt remains CLI stdin, not shell syntax. |
| Error contract | Typed classification/synthesis errors, wrapping, validation-step diagnostics, retries and terminal propagation. Inspected success, malformed output, exhausted attempts, budget rejection and unknown-code paths. | Known public failure strings remain; unknown `event.*` values intentionally collapse to `event.output_invalid`. Sanitized causal information survives. Per-attempt validation logging and final failure reporting serve different scopes; no swallowed terminal failure. |
| Memory | Diagnostic sets, hint lists, full prompt reconstruction and retained `last_cause`/`last_outcome`. Checked growth, lifetime, intermediate copies and streaming suitability. | At most eight diagnostics; fixed-size hints; each retry starts from `full_prompt`, so failed text does not accumulate. Existing output parsing caps and last-attempt lifetime remain. Streaming is unnecessary for the small added feedback. |
| Performance | Repeated CLI calls and prompt/log construction in retry loops; assessed iteration cost, data structures, batching and observability overhead. | New work is bounded by eight codes and static strings; set membership is appropriate. No extra CLI call, network request, per-item logging or unbounded metric dimension. |
| Resource lifecycle | Awaited CLI runner and timeout/retry ownership. Traced success, validation error, subprocess failure and budget exit; checked acquisitions/releases and ownership. | No new resource acquisition, pool or worker. Existing runner owns subprocess completion/timeout; budget checked before dispatch. No new cleanup or ownership gap. |
| Concurrency | Async retry loops and budget mutation around await points. Checked shared state, signal/action paths, invariants, queues and shutdown implications. | Added data is call-local or read-only module constants. No lock, split critical section, queue, spawned task or concurrent mutation introduced. Existing calls remain awaited and budget ownership unchanged. |
| Data integrity | No write, transaction or persistent-state signal in changed implementation. | Not triggered. No output persistence, deployment or publication action added. |

## Contract and verification evidence

| Contract | Evidence and conclusion |
|---|---|
| Useful Stage 1 feedback | `classification.py:147–220` covers closed document/revision, span, blank, ownership, missing relation/impact/object, date/timing, metadata, item and schema diagnostics. Compared with `event_evidence._build_candidate` and `parse_event_classification`. Repair guidance preserves original evidence and prohibits inventing evidence or substituting an empty-events fallback. The revision fault correctly yields `evidence.item_mismatch` because ownership is checked before span resolution. |
| Useful Stage 2 feedback | `markdown_render.py:197–247` matches `_internal/event_rendering.py`: unique owned facts including all required IDs; actor/action/object/claimed-fact refs; literal numeric grounding; exact supplied metadata; forecast roles; field-local meaning/reaction evidence. The unavailable form is limited to unsupported meaning/reaction while selected events and required facts remain. |
| Closed, bounded feedback | Independently derived the exact maximum over every possible number of schema diagnostics (0–8), choosing the longest allowed schema tokens and largest fixed code-plus-hint contributions. Stage 1 maximum is **2,069 ASCII characters/bytes** (seven fixed plus one schema diagnostic), below 4,096. Every Stage 2 allowlisted code was evaluated: maximum **809 characters/bytes** (`event.fact_unsupported`); entity 753, evidence 738, generic 253–257. Existing separate required-macro feedback remains unchanged. |
| No diagnostic/source leakage | `classification.py:121–137` filters exact tuple/string types and closed token components before either sink. `markdown_render.py:197–200` rejects arbitrary event-prefixed text. New logs at `orchestration.py:421` and `:741` contain stage, segment, attempt and sanitized tokens only; no `exc_info` or raw cause rendering. Forged diagnostics and private raw-error tests pass. |
| Failure and budget preservation | `orchestration.py` still gates before dispatch, records elapsed time, uses the same attempt limit/backoff and suppresses event stdout/stderr on final/budget errors. Invalid repeated responses still raise `BriefingGenerationError`; no automatic successful fallback. The latest Stage 1 failure replaces prior feedback. |
| Compatibility and gate integrity | First attempts receive no retry suffix. Off/shadow use unchanged v1 prompt/feedback paths. New tests and existing off/shadow replay tests pass. No changes to `event_evidence.py`, `event_narrative.py`, `_internal/event_rendering.py`, payload models, finalizer or publisher validators. |

Independent commands executed with the existing repository environments:

- Focused retry/classification/entity/pipeline-boundary suite: **50 passed**.
- Evidence/narrative validators, budget guard/happy path, internal retry budget/module boundaries, event generation and event prompt-budget suites: **109 passed**.
- Ruff check and Ruff format check across all five changed Python files: passed; all five already formatted.
- Mypy across all three changed source files: passed.
- `git diff --check`: passed.

The two pytest selections are disjoint (159 tests total). No repository-wide test/static run, live LLM invocation or production execution was performed by this reviewer.

## Project rules and self-review

| Rule / check | Status | Evidence |
|---|---|---|
| No Anthropic SDK / paid API addition | Pass | `rg` found no Anthropic SDK imports in `src`; changed files add no API/client/source dependency. |
| Approved CLI boundary | Pass | `orchestration.py` retains `llm.call_llm`; `llm.py` re-exports the approved runner boundary. Existing `claude_code.py` passes list args, stdin prompt and timeout to subprocess, checks its outcome, and uses `asyncio.to_thread`. |
| Disclaimer append / pre-publish verification | Unchanged | `briefing/pipeline.py:767,924` still append disclaimer; publisher writer and public-document verification remain outside the diff. |
| Module boundaries | Pass | Internal module dependency remains within the allowed shared validation layer; `test_module_boundary.py` passed. No cross-unit source/notifier/publisher import added. |
| Telegram channel separation | Unchanged | No config/notifier change; distinct operator/channel configuration and `__main__.py` equal-ID guard remain. |
| Plugin/source extensibility | Not applicable | No adapter or source-specific behavior added. |
| Resource and concurrency safety | Pass | No new handle/task, all provider calls awaited; protocol analysis above. |
| No hardcoded secrets / safe errors | Pass | Only static instructions/codes added. Context omission at event error boundary is intentional R13 protection, not accidental loss of arbitrary error text. |
| Failure scenarios and typing | Pass | Corrected-response recovery, repeated-invalid blocking, private sentinel, latest-only feedback, legacy/budget regressions and strict Mypy checks passed. |

## Limits and operational follow-up

The production evidence described in the plan establishes repeated classification `invalid_evidence` failures with unchanged prompt sizes and a separate `event.fact_unsupported` failure. Failed raw model outputs were intentionally not retained. Synthetic fixtures demonstrate the affected retry contracts, **not** byte-exact replay of those production incidents or a measured improvement in model success rate.

The separate Nov 19 post-generation `event.evidence_invalid` terminal failure is not repaired or explained by this diff. Its precise cause remains unproven without the rejected payload. Terminal gates must remain enforced during any later operational acceptance. Structural/literal validators also do not prove full semantic entailment of free prose; this change makes no such claim.

No new technical-debt candidate is required by this review. Retain the above live-acceptance limitations in the implementation handoff. No change to `TECH-DEBT.md`, source files, commit state, deployment or external service was made.
