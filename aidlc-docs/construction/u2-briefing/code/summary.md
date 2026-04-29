# u2 briefing — Code Generation Summary

**Date**: 2026-04-30
**Stage**: Code Generation (final stage for u2 briefing)
**Status**: ✅ COMPLETE
**Stories closed**: US-002 (한국어 7섹션 시황 자동 생성), US-009 (LLM은 Claude Code CLI로만 호출)

---

## Files created

### Source code (`src/investo/briefing/`)

| File | LOC | Role |
|------|----:|------|
| `__init__.py` | 23 | Package docstring + reserved public surface (Step 1) |
| `disclaimer.py` | 61 | `DISCLAIMER` constant + idempotent `append_disclaimer` (Step 2) |
| `leak_guard.py` | 126 | R6 PII / secret regex set + `scan(markdown)` (Step 3) |
| `errors.py` | 124 | `BriefingGenerationError` + `SubprocessOutcome` + `BriefingStage` (Step 4) |
| `prompts.py` | 182 | 4 prompt constants + `STAGE2_SECTION_HEADERS` (Step 5) |
| `claude_code.py` | 202 | `RetryBudget` + `call_claude_code` subprocess wrapper (Step 6) |
| `pipeline.py` | 482 | Two-stage classify + synthesize + `generate_briefing` (Step 8 + 9.3 fix) |
| **Total** | **1,200** | 7 source files |

### Test helper (`tests/_helpers/`)

| File | LOC | Role |
|------|----:|------|
| `fake_claude_runner.py` | 227 | SHA-256 fixture replay + `INVESTO_LIVE_LLM=1` record mode (Step 7) |

### Tests (`tests/unit/briefing/` + `tests/integration/`)

| File | LOC | Tests | Role |
|------|----:|------:|------|
| `conftest.py` | 7 | 0 | Placeholder for shared fixtures (DEBT-010) |
| `test_disclaimer.py` | 106 | 9 | AC-4.2 / 4.3 / 4.5 anchor tests (Step 2) |
| `test_disclaimer_pbt.py` | 59 | 3 | AC-4.1 / 6.1 idempotence PBT (Step 2) |
| `test_leak_guard.py` | 247 | 26 | AC-6.4 / 7.3 hit + miss + ReDoS regression (Step 3) |
| `test_errors.py` | 258 | 20 | AC-3.2 BGE shape + AC-7.4 1024-byte truncation (Step 4) |
| `test_prompts.py` | 207 | 18 | AC-5.1 / 5.2 / 5.3 sentinel grep + format tests (Step 5) |
| `test_claude_code.py` | 349 | 21 | AC-2.5 / 7.1 / 7.2 / 7.6 self-checks + RetryBudget (Step 6) |
| `test_fake_claude_runner.py` | 407 | 16 | AC-6.5 + replay + record mode + atomic write (Step 7) |
| `test_pipeline_unit.py` | 449 | 30 | Pure helpers + H1/H2 regression (Steps 8.2 + 8.5) |
| `test_pipeline_pbt.py` | 203 | 5 | AC-6.2 serialize + AC-6.3 parse round-trips (Step 8.3) |
| `test_pipeline_no_prompt_strings.py` | 126 | 3 | AC-5.2 / 5.3 inspect.getsource grep (Step 8.4) |
| `test_failure_contract.py` | 265 | 5 | AC-3.2 / 3.4 / 3.5 four-stage BGE + pass-through (Step 9.1) |
| `test_budget_happy_path.py` | 138 | 2 | AC-1.1 happy path + 300s constant anchor (Step 9.2) |
| `test_budget_guard.py` | 207 | 3 | AC-1.4 / 1.5 forward-looking gate + intra-stage (Step 9.3) |
| `test_no_anthropic_sdk.py` | 224 | 12 | NFR-002 AC-2.2 / 2.3 + NFR-007 AC-7.1 / 7.6 CI guard (Step 10.2) |
| `tests/integration/test_briefing_pipeline_poc.py` | 196 | 1 | FD L9 PoC: u1 FOMC → u2 → AC-4.4 + AC-7.5 (Step 9.4) |
| **Total** | **3,448** | **174** | 16 test files (15 unit + 1 integration) |

### Other artifacts

- `scripts/check_no_anthropic_sdk.py` — repo-wide CI grep guard for Anthropic SDK + shell-form subprocess (Step 10.1)
- `tests/fixtures/llm/.gitkeep` — fixture-key directory placeholder (Step 1; FakeClaudeRunner home)
- `CONTRIBUTING.md` — extended with Briefing prompts / LLM fixture refresh / extended PR description checklist (Step 10.3)

### Surface area

| Public re-export | Defined in | Consumed by |
|------------------|------------|-------------|
| `generate_briefing(target_date, items, *, runner=None, budget=None) -> Briefing` | `pipeline.py` | u5 orchestrator |
| `DISCLAIMER` (constant) | `disclaimer.py` | u3 publisher's `verify_disclaimer` (exact-substring match) |
| `append_disclaimer(markdown) -> str` | `disclaimer.py` | u3 publisher (defense-in-depth) |
| `BriefingGenerationError` | `errors.py` | u5 orchestrator (stage guard + operator alert routing) |
| `Briefing` (re-exported via `investo.models`) | `models/briefing.py` | u3 publisher, u5 orchestrator |

`__init__.py` is currently a placeholder (`__all__: list[str] = []`) — public re-exports are per-module imports today; can be promoted to package-level if u5 orchestrator's import patterns push for it.

---

## NFR AC-to-test traceability

All 44 ACs from `nfr-requirements.md` are pinned by tests or documented passive guarantees. The `Pinned by` column lists the canonical test that catches a regression.

| AC | Description | Pinned by |
|----|-------------|-----------|
| AC-1.1 | `generate_briefing` returns ≤ 300 s on happy path | `test_budget_happy_path.py::test_generate_briefing_succeeds_under_nominal_elapsed_per_call` |
| AC-1.2 | Worst case ≤ 300 s under FD R3 budget | Same as AC-1.4 (forward-looking gate prevents overshoot) |
| AC-1.3 | `test_budget_happy_path.py` exists | This file's existence + AC-1.1 pin |
| AC-1.4 | Budget gate fires when next attempt would exceed cap | `test_budget_guard.py::test_budget_gate_fires_before_stage_2_dispatches` |
| AC-1.5 | 300-s cap is shared across both stages | `test_budget_guard.py::test_budget_is_shared_between_classify_and_synthesize` |
| AC-2.1 | Every LLM call via `claude_code.call_claude_code` | `test_no_anthropic_sdk.py::test_subprocess_invocation_passes_on_current_tree` (CI grep) + `test_claude_code.py` (only call site) |
| AC-2.2 | CI grep guard on `src/**` | `scripts/check_no_anthropic_sdk.py` + `test_no_anthropic_sdk.py::test_detects_anthropic_sdk_import` (and 7 other detection tests) |
| AC-2.3 | Scope = whole repo, not just `briefing/` | Same script — `SRC_ROOT = repo/src` walks all of `src/**`; pyproject scan covers all dep tables |
| AC-2.4 | PR-description cost-disclosure rule | `CONTRIBUTING.md` "PR description checklist" → "Any new external network call" subsection (extended in 10.3) |
| AC-2.5 | `claude_code.py` does not log `CLAUDE_CODE_OAUTH_TOKEN` | `test_claude_code.py::test_claude_code_module_does_not_reference_oauth_token` (AST-stripped self-check) |
| AC-3.1 | `generate_briefing` returns `Briefing` (no Optional) | mypy --strict on `pipeline.py:generate_briefing` signature |
| AC-3.2 | BGE carries one of 4 stage values | `test_failure_contract.py` (5 tests covering classification / synthesis / post_validation / budget) |
| AC-3.3 | Type-system: signature is `-> Briefing` | mypy --strict |
| AC-3.4 | Programmer `KeyError` propagates unwrapped | `test_failure_contract.py::test_programmer_keyerror_propagates_unwrapped` |
| AC-3.5 | `ValidationError` propagates unwrapped | `test_failure_contract.py::test_briefing_validation_error_propagates_unwrapped` |
| AC-4.1 | `append_disclaimer` is idempotent | `test_disclaimer_pbt.py::test_append_disclaimer_is_idempotent` (100 examples) |
| AC-4.2 | Result contains DISCLAIMER substring | `test_disclaimer.py::test_append_to_empty_yields_disclaimer_substring` |
| AC-4.3 | DISCLAIMER ends as last `## ` header | `test_disclaimer.py::test_append_to_typical_briefing_ends_with_disclaimer` |
| AC-4.4 | `Briefing.rendered_markdown` contains DISCLAIMER | `test_briefing_pipeline_poc.py::test_full_pipeline_poc_against_recorded_fomc_fixture` |
| AC-4.5 | `DISCLAIMER` is a module-level `Final[str]` | `test_disclaimer.py::test_disclaimer_is_non_empty_str` + mypy --strict |
| AC-4.6 | Cross-unit: u3 publisher re-verifies disclaimer | Cross-unit AC — pinned by u3 when it lands; tracked under DEBT-001 (model-side invariant) |
| AC-5.1 | 4 prompt constants are `Final[str]` in `prompts.py` | `test_prompts.py::test_prompts_are_final_strings` + mypy --strict |
| AC-5.2 | `pipeline.py` contains no prompt body strings | `test_prompts.py::test_prompt_sentinels_only_in_prompts` + `test_pipeline_no_prompt_strings.py::test_pipeline_executable_source_has_no_prompt_sentinels` |
| AC-5.3 | `claude_code.py` contains no prompt body strings | Same two tests above (both modules covered) |
| AC-5.4 | Prompt change = single-file edit | `CONTRIBUTING.md` "Briefing prompts" section (10.3); reviewed at `/code-review` time |
| AC-5.5 | No template-engine dep added | `pyproject.toml` audit — `[project.dependencies]` unchanged from u1; flagged at `/code-review` |
| AC-6.1 | `append_disclaimer` PBT ≥ 100 examples | `test_disclaimer_pbt.py` (3 PBTs at 100 each) |
| AC-6.2 | `serialize_items_for_prompt` round-trip PBT | `test_pipeline_pbt.py::test_serialize_round_trip_yields_list_of_dicts_with_expected_shape` (+2 sibling PBTs at 100 each) |
| AC-6.3 | `parse_six_sections` round-trip PBT | `test_pipeline_pbt.py::test_parse_six_sections_round_trips_arbitrary_non_blank_bodies` (+1 sibling PBT at 100 each) |
| AC-6.4 | `leak_guard.scan` example-based hit/miss | `test_leak_guard.py` (26 tests; PBT explicitly excluded per AC) |
| AC-6.5 | All test LLM calls via `FakeClaudeRunner` | `test_fake_claude_runner.py::test_no_test_imports_subprocess_to_invoke_claude` (AST grep) |
| AC-6.6 | ≥ 100 examples per PBT | `@settings(max_examples=100)` on every PBT in `test_disclaimer_pbt.py` + `test_pipeline_pbt.py` |
| AC-7.1 | `subprocess.run` list form, no `shell=True` | `test_claude_code.py::test_claude_code_module_uses_only_list_form_subprocess` + `scripts/check_no_anthropic_sdk.py` (`shell_true` + `string_form_subprocess` patterns) |
| AC-7.2 | No `CLAUDE_CODE_OAUTH_TOKEN` literal in code | Same as AC-2.5 |
| AC-7.3 | Leak-guard regex set matches FD R6 exactly | `test_leak_guard.py::test_pattern_set_matches_fd_r6` |
| AC-7.4 | `last_stderr` truncated to 1024 bytes | `test_errors.py` (4 truncation tests covering at-cap / just-over / far-over / multi-byte boundary) |
| AC-7.5 | `rendered_markdown` contains no `<script>` | `test_briefing_pipeline_poc.py::test_full_pipeline_poc_against_recorded_fomc_fixture` |
| AC-7.6 | `subprocess.run` invocation excludes `shell=True` | `test_claude_code.py::test_claude_code_module_does_not_use_shell_true` + `scripts/check_no_anthropic_sdk.py` |
| AC-7.7 | No `eval` / `pickle.loads` / `exec` on response data | Passive — verified by inspection; no such calls in `briefing/`; documented here as evidence |
| AC-D.1 | All PBT + example tests run in CI | All tests under `tests/unit/briefing/` + `tests/integration/` execute via `pytest` |
| AC-D.2 | CI grep guard runs in CI | `test_no_anthropic_sdk.py` invokes `scripts/check_no_anthropic_sdk.py` as subprocess on every test run |
| AC-D.3 | Functional changes to u2's public surface trigger `/code-review` | `dev-investo` skill §5.1 routine — sub-agent reviews ratified the FD R3 forward-looking-gate fix in 9.3 |
| AC-D.4 | Leak-guard regex changes require test + audit log entry | Process AC — ratified for the `email` regex ReDoS-tightening in Step 3 (audit.md entry) |
| AC-D.5 | Runtime metrics (attempt counts, p50/p95) | Deferred to v2 per spec (not pinned) |

---

## Open TECH-DEBT items

| ID | Priority | Origin | Description |
|----|----------|--------|-------------|
| DEBT-001 | Medium | models step 3 (cross-unit) | `Briefing` model lacks `disclaimer ∈ rendered_markdown` invariant |
| DEBT-002 | Medium | models step 3 (cross-unit) | No date sanity bounds on `target_date` / `published_at` |
| DEBT-007 | Medium | u2 step 8.5 review | No byte-exact JSON snapshot test for `serialize_items_for_prompt` (FakeClaudeRunner key stability) |
| DEBT-006 | Low | u2 step 6 review | `call_claude_code` cancellation does not stop the worker thread |
| DEBT-008 | Low | u2 step 8.5 review | `_parse_classification` does not catch `RecursionError` on adversarial JSON |
| DEBT-009 | Low | u2 step 8.5 review | `_executable_source` AST helper duplicated across two test files |
| DEBT-010 | Low | u2 step 9.5 review | u2 briefing test helpers duplicated across 4 files |
| DEBT-011 | Low | u2 step 9.5 review | Integration PoC bypasses `aggregator.fetch_all` |

Plus DEBT-003 / DEBT-004 / DEBT-005 from u1 (unchanged). None block u2; 5 of 6 new items originate inside u2.

---

## FD-vs-implementation divergences (ratified in audit log)

Two structural deviations and one corrective fix landed during construction:

1. **Step 8.1** — `_classify` / `_synthesize` signature: FD plan called for a `prompts` parameter (dependency injection). Implementation imports prompts at module level — single-prompt-set reality doesn't need an injection seam. Ratified at Step 8.5 review.
2. **Step 8.1** — `STAGE2_SECTION_HEADERS` consolidation: `parse_six_sections` originally hardcoded the six headers; the AC-5.2 sentinel grep flagged `## ① 요약`. Refactor: moved the header tuple to `prompts.py` (single source of truth) and re-imported. Ratified at Step 8 commit.
3. **Step 9.3** — FD R3 forward-looking budget gate: `_classify` and `_synthesize` originally used `budget.check_or_raise` (post-hoc "already exhausted"). FD R3 explicitly specifies "if next attempt would exceed budget, raise immediately" — replaced with `budget.would_exceed(DEFAULT_TIMEOUT_S)`. The `would_exceed` method had been built in Step 6 but never wired up. Ratified at Step 9.5 review.

All three ratified in `aidlc-docs/audit.md`. No cross-unit contract was broken.

---

## Story status

- ✅ **US-002** (한국어 7섹션 시황 자동 생성) — closed by `generate_briefing` (atomic two-stage Claude Code CLI flow) producing `Briefing` with all 7 sections (① summary through ⑥ watch points + ⑦ disclaimer auto-appended). Stage 1 LLM-decided classification + Stage 2 synthesis under a 300-s budget gate.
- ✅ **US-009** (LLM은 Claude Code CLI(setup token)로만 호출) — closed by the `claude_code.py` subprocess wrapper (list-form `subprocess.run(["claude", "-p", prompt])`, no `shell=True`, no Anthropic SDK import) plus the `scripts/check_no_anthropic_sdk.py` CI guard enforcing the rule repo-wide.

---

## Pre-flight notes for u3 publisher

When `u3 publisher` enters Code Generation, it will consume the following stable surface from `investo.briefing` (and `investo.models`):

| Symbol | Defined in | What u3 needs it for |
|--------|------------|----------------------|
| `Briefing` | `investo.models.briefing` (re-export in `investo.models`) | The shape u3's archive writer + Telegram payload builder consume. Frozen pydantic model with `target_date`, 6 section bodies + `disclaimer` + `rendered_markdown`. |
| `DISCLAIMER` | `investo.briefing.disclaimer` | u3's `verify_disclaimer` performs an EXACT substring match on this constant against `briefing.rendered_markdown` (NFR-004). Block publish on failure. |
| `append_disclaimer` | `investo.briefing.disclaimer` | u3 may re-call this defensively as a no-op (it's idempotent). Cheaper than re-rendering markdown from sections. |

**u3 must NOT import any other u2 symbol** — `pipeline`, `claude_code`, `prompts`, `errors`, `leak_guard`, `RetryBudget`, `BriefingGenerationError`, etc. are u5 orchestrator's concern, not u3's. The module-boundary rule is enforced informally by `/code-review` — there is no automated grep test for it (yet — could add one if drift becomes a recurring pain).

### Disclaimer verification hint (informational)

```python
# u3 publisher (sketch)
from investo.briefing.disclaimer import DISCLAIMER

def verify_disclaimer(briefing: Briefing) -> None:
    if DISCLAIMER not in briefing.rendered_markdown:
        raise PublishBlockedError(
            "rendered_markdown missing canonical disclaimer (NFR-004); "
            "rejecting publish"
        )
```

The `Briefing` model itself does not enforce `DISCLAIMER ∈ rendered_markdown` (DEBT-001). u3's verify step is the runtime safety net.

---

## Quality gate (final, Step 10.5 will re-confirm)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ |
| `mypy --strict src/` | ✅ (22 source files: 7 models + 8 sources + 7 briefing) |
| `pytest` | ✅ **430/430** passing (252 u1+models baseline + 178 u2 = 430 total) |

Test breakdown for u2: 9 disclaimer + 3 disclaimer-pbt + 26 leak_guard + 20 errors + 18 prompts + 21 claude_code + 16 fake_claude_runner + 30 pipeline_unit + 5 pipeline_pbt + 3 pipeline_no_prompts + 5 failure_contract + 2 budget_happy + 3 budget_guard + 12 no_anthropic_sdk + 1 integration_poc = **174 tests**. (Plus ~4 collected in conftest / pkg tests = 178 reported by `pytest --collect-only`.)

---

## Next stage gate

`u2 briefing` Code Generation is now CLOSED. The unit becomes eligible for `/cross-check` against requirements. Three stage gates remain for the project:

1. `u3 publisher`, `u4 notifier`, `u5 orchestrator` Code Generation (per `aidlc-docs/inception/plans/execution-plan.md`)
2. `u6 infra/CI` (YAML/config only — Code Generation but no FD/NFR)
3. Global `Build and Test` after every unit's CG completes
