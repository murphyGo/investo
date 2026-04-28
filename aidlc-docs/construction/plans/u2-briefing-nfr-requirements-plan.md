# NFR Requirements Plan: `u2 briefing`

**Date**: 2026-04-28
**Unit**: u2 briefing — Briefing Generator
**Stage**: NFR Requirements
**Source artifacts**:
- `aidlc-docs/construction/u2-briefing/functional-design/` — domain-entities, business-rules (R1-R12), business-logic-model (L1-L9)
- `docs/requirements.md` — NFR-001, NFR-002, NFR-003, NFR-004, NFR-005, NFR-006, NFR-007 acceptance criteria
- `aidlc-docs/construction/u1-sources/nfr-requirements/` — reference format for parallel concerns

---

## Unit Context

NFRs that touch this unit:

- **NFR-001 (share)** Performance — u2's slice of the 10-min orchestrator budget
- **NFR-002** Cost (Claude Code CLI only; Anthropic SDK ban; $0/월)
- **NFR-003** Reliability (retry policy + failure contract)
- **NFR-004** Compliance / Disclaimer (auto-insert + defense-in-depth)
- **NFR-005** Maintainability (prompt templating; module separation)
- **NFR-006** Testing (PBT partial; LLM record/replay fixtures)
- **NFR-007** Security baseline (subprocess hygiene; PII leak guard; secret-handling)

NFR-005's "plugin extensibility" sub-requirement is u1's territory; not relevant here.

---

## Execution Checklist

### Part 1 — Planning (you are here)
- [x] Q1~Q9 모두 [Answer]: 채움 (2026-04-28, all A)
- [x] Ambiguity 분석: 없음 (Q1의 rationale은 옵션 A 본문과 일치)
- [ ] Plan 명시적 승인

### Part 2 — Generation (after approval)
- [x] `aidlc-docs/construction/u2-briefing/nfr-requirements/nfr-requirements.md` (49 ACs)
- [x] `aidlc-docs/construction/u2-briefing/nfr-requirements/tech-stack-decisions.md` (10 TS entries, zero new deps)
- [x] aidlc-state.md / audit.md 업데이트
- [x] NFR Requirements 명시적 승인 (2026-04-28, "approve" / Continue to Next Stage)

---

## Embedded Questions

### Q1: Performance — u2's share of NFR-001 (10-min total budget)

`u2` uses an internal 5-min `RetryBudget` (FD R3). The orchestrator's
total budget is 10 min (NFR-001). `u1` claimed ≤ 4 min for collect.
That leaves ≤ 6 min for `briefing + publisher + notifier` combined.
What's the testable AC for u2?

A) **권장**:
   - AC: `generate_briefing(target_date, items)` returns within
     **300 s** wall-clock on the **happy path** (Stage 1 + Stage 2
     each succeed on first attempt, no retries). Worst case under
     the R3 retry budget is also 300 s (the budget is the cap).
   - Test: `tests/unit/briefing/test_budget.py` pins this with a
     `FakeClaudeRunner` that injects a 60-s sleep per stage —
     `generate_briefing` must return ≤ 300 s.
   - Test: separate test pins the budget guard fires —
     `FakeClaudeRunner` simulates each call taking 200 s; second
     stage's first attempt must raise `BriefingGenerationError(stage="budget")`
     without sleeping out the third attempt.
B) Stricter: 180 s happy path. Pads less for slow LLM days; risks
   spurious budget errors when Claude is briefly slow.
C) Looser: 420 s. Eats into the ≤ 6-min downstream margin (publisher
   + notifier need their share).

[Answer]: A, with the rationale that 5 min per stage is a reasonable upper bound for v1, and the retry budget is already capped at 5 min, so there's no need to pad further for slow days. The tests ensure that the happy path meets the 5-min target and that the retry budget is enforced correctly.

---

### Q2: Cost — Anthropic SDK ban as a CI regression guard (NFR-002)

FD R2 forbids `from anthropic ...`, `import anthropic`, and the
`anthropic` package in dependencies. u1 has a parallel CI grep
(`scripts/check_no_paid_apis.py`). What's the AC for u2?

A) **권장**: Two-layer guard, scope = **whole repo, not just u2**:
   1. CI grep: `scripts/check_no_anthropic_sdk.py` (added in u2 Code
      Generation) fails the build if ANY file under `src/` matches
      `^(from anthropic|import anthropic)` or if `pyproject.toml`
      `[project.dependencies]` lists `anthropic`.
   2. Extension: the same grep also flags `subprocess.run(shell=True)`
      and bare `subprocess.run("claude ...", shell=True)` patterns
      anywhere in `src/` — paranoia about future contributors taking
      shortcuts.
   3. The `/code-review` skill rule (already in `dev-investo` §5.1)
      catches it earlier in PR review.
B) Code review only — no CI guard. Lighter; relies on humans.
C) A plus a test that imports `briefing.claude_code` and asserts the
   module has no `anthropic` symbol. Redundant with the CI grep,
   adds maintenance noise.

[Answer]: A

---

### Q3: Reliability — failure contract (NFR-003)

FD R4 says `generate_briefing` returns `Briefing` on success and
raises `BriefingGenerationError` on failure (no `Briefing | None`,
no partial `Briefing`). What's the testable AC?

A) **권장**: Three pinning tests:
   1. `tests/unit/briefing/test_failure_contract.py`:
      - Stage 1 LLM returns malformed JSON × 3 → raises
        `BriefingGenerationError(stage="classification", attempt_count=3, ...)`.
      - Stage 2 LLM returns blank stdout × 3 → raises
        `BriefingGenerationError(stage="synthesis", attempt_count=3, ...)`.
      - Leak guard hits → raises
        `BriefingGenerationError(stage="post_validation", attempt_count=1, ...)`
        with **no retry** (R6 + L5).
      - Total budget exceeded mid-stage → raises
        `BriefingGenerationError(stage="budget", ...)` immediately
        on next-attempt check (no further subprocess call).
   2. Type-system AC: `generate_briefing` signature is
      `async def generate_briefing(...) -> Briefing`. mypy strict
      mode would reject `Briefing | None`. Pinned by code review,
      not by a test.
   3. Programmer-error AC: a `KeyError` simulated inside
      `build_section_plan` propagates out as `KeyError` (NOT wrapped
      in `BriefingGenerationError`). Pinned by a test that monkeypatches
      a builder helper to raise `KeyError`.
B) Just one combined "all failure modes raise BGE" test. Cheaper,
   misses the post-validation no-retry distinction and the
   programmer-error pass-through.
C) A plus a test that drives the real `claude` CLI offline (no
   network), expecting `BriefingGenerationError(stage="...")` —
   adds CI flakiness from a real subprocess; rejected.

[Answer]: A

---

### Q4: Compliance — disclaimer defense-in-depth (NFR-004)

FD R5 specifies `append_disclaimer` is idempotent (anchored on
`## ⑦ 면책조항`) and that `u3 publisher.verify_disclaimer` does an
exact-substring match of the full `DISCLAIMER` constant. The cross-
unit guarantee is "publish is blocked if disclaimer text drifts."
What's the AC at u2's level?

A) **권장**:
   - AC: `append_disclaimer(markdown)` is **idempotent** —
     `append_disclaimer(append_disclaimer(x)) == append_disclaimer(x)`
     for all strings `x`. Property test (PBT, hypothesis).
   - AC: `append_disclaimer(x)` always returns a string containing
     the exact `DISCLAIMER` constant. Example-based test.
   - AC: `append_disclaimer(x)` adds the disclaimer at the **end**
     (after section ⑥), never at the top, never embedded mid-string.
     Pinned by a test that confirms the disclaimer is the last
     section header in the rendered markdown.
   - AC: `Briefing.rendered_markdown` always contains
     `briefing.disclaimer.DISCLAIMER` as a substring. This is the
     u2-side guarantee that u3's `verify_disclaimer` will succeed
     under non-adversarial conditions. (DEBT-001 tracks moving
     this into the model itself; out of scope here.)
   - Cross-unit AC: u3's `verify_disclaimer` is its own NFR scope;
     u2 only commits to producing markdown where the disclaimer is
     present and exactly matches the constant.
B) Just the idempotence property test. Skips the "always at end"
   anchor — risks regressions where the disclaimer ends up mid-
   markdown without anyone noticing.
C) A plus a test that mutates `DISCLAIMER` and asserts u3's
   `verify_disclaimer` rejects the resulting briefing. That's u3's
   AC; cross-cutting tests live in integration tests, not the u2
   unit-test plan.

[Answer]: A

---

### Q5: Maintainability — prompt templating (NFR-005)

`docs/requirements.md` NFR-005 says "섹션 정의·프롬프트가 코드와 분리
(예: `templates/briefing.md.j2` 또는 yaml)". FD L2 / L3 show prompt
*skeletons* but doesn't pin where the strings live in code. This is
the only real ambiguity the FD didn't resolve. Three concrete shapes:

A) **권장 — Module-level constants (no template engine)**:
   - Prompts live in `src/investo/briefing/prompts.py` as
     `STAGE1_SYSTEM`, `STAGE1_USER_TEMPLATE`, `STAGE2_SYSTEM`,
     `STAGE2_USER_TEMPLATE` — plain Python triple-quoted strings.
   - Variable substitution uses `str.format(**kwargs)` (the only
     placeholders are `{items_json}`, `{grouped_json}`, `{target_date}` —
     trivially shaped, no nested logic).
   - "Separated from code" is satisfied because prompts live in
     their own module, not in `pipeline.py` or `claude_code.py`.
     Code review can audit the file in isolation. PR diff for a
     prompt change is local.
   - AC: `briefing.pipeline` does NOT contain prompt body strings —
     only imports them from `briefing.prompts`. Pinned by a test
     that greps `briefing/pipeline.py` for sentinel substrings of
     the prompts.
   - AC: `briefing.claude_code` does NOT contain prompt body strings —
     it only knows about `subprocess.run` semantics.
B) **Jinja2 templates in `src/investo/briefing/templates/*.j2`**:
   - Adds `jinja2` dep. Heavier syntax. Marginal benefit for prompts
     with 2-3 placeholders. Useful if prompts grow to have loops
     (e.g. iterating sections) — but FD R7 already serializes items
     to JSON and lets the LLM do the rendering, so the prompt body
     itself stays simple.
C) **YAML files (`prompts/stage1.yaml`)**:
   - Adds `pyyaml` or `ruamel.yaml` dep. Multi-line strings in YAML
     are fiddly (`|` vs `>`, indentation). Same expressive power as
     A with worse ergonomics.

[Answer]: A

---

### Q6: Testing — PBT scope for u2 (NFR-006, partial)

Per project policy, PBT applies to "pure functions and serialization
round-trips" only. Which u2 pure functions qualify?

A) **권장**:
   - `append_disclaimer(s)` — idempotence property: `f(f(x)) == f(x)`
     for any string `x`. Hypothesis: `text()` strategy.
   - `serialize_items_for_prompt(items)` (R7) — round-trip property:
     given any list of `NormalizedItem`, the serialized JSON parses
     back to a structurally equivalent list (excluding `raw_metadata`,
     which is deliberately stripped per R7). Uses the same
     `NormalizedItem` strategy already defined in
     `tests/unit/models/`.
   - `parse_six_sections(markdown)` — round-trip property: for any
     synthetic markdown built by joining six valid `## ① ... ## ⑥`
     sections, `parse_six_sections` returns those exact six bodies
     (whitespace-normalized). Uses a `text()` × 6 strategy with the
     fixed headers prepended.
   - `leak_guard.scan(markdown)` — DOES NOT get a PBT (regex
     correctness is example-based; PBT would mostly find regex
     edge cases unrelated to project intent). Example-based tests
     cover known-bad strings + a curated "should not match"
     allowlist.
B) Just `append_disclaimer` idempotence. Cheapest; misses the JSON
   round-trip which is the more bug-prone path.
C) A plus PBT for `build_section_plan` (E3 builder). The function is
   pure, but the property to test is essentially "input items split
   into the right buckets" — an example-based test is clearer.

[Answer]: A

---

### Q7: Security — subprocess hygiene + PII leak guard (NFR-007)

FD R2 forbids `shell=True`; FD R6 specifies the leak-guard regex
set. The trust boundary is "LLM output is untrusted bytes that go
into a public archive + Telegram channel." How strict is the AC?

A) **권장**:
   - **Subprocess form**: `subprocess.run` is invoked with the list
     form `["claude", "-p", prompt]`, never the string form. AC: a
     CI grep test rejects `subprocess.run(shell=True)` and
     `subprocess.Popen(shell=True)` anywhere under `src/investo/`.
     (Same grep as Q2 — one tool, two checks.)
   - **Token handling**: `CLAUDE_CODE_OAUTH_TOKEN` is read from the
     environment by the `claude` CLI itself, NOT by Python code.
     `briefing.claude_code` does **not** read, log, or pass the
     token explicitly. AC: a test asserts
     `briefing.claude_code` source has no `CLAUDE_CODE_OAUTH_TOKEN`
     literal.
   - **Leak-guard regex set** (the R6 list): pinned as AC. Test
     `tests/unit/briefing/test_leak_guard.py` asserts:
     - Each known-bad pattern (GitHub PAT, AWS access key, JWT,
       generic long base64, email, KR phone) gets matched by a
       canonical example.
     - A curated allowlist of strings that LOOK like patterns but
       are intentionally fine (e.g. a markdown URL with a long
       slug) does NOT match. Calibrates false-positive rate.
   - **Stderr handling**: when `BriefingGenerationError` carries
     `last_stderr`, the field is **truncated to 1024 bytes** before
     being attached to the exception (FD E4). AC: test pins the
     truncation.
   - **No raw HTML in the briefing**: u1 already strips HTML from
     titles/summaries (NFR-007 AC-7.2 in u1). u2 doesn't re-strip;
     the LLM is just told (Stage 2 prompt) not to invent HTML.
     Belt-and-braces verification: `Briefing.rendered_markdown`
     must not contain `<script>` substring. Pinned in a test.
B) Just the leak-guard pattern set. Skips the subprocess hygiene
   AC and the stderr truncation AC; risks a future contributor
   adding `shell=True` or letting a 10-MB stderr land in the alert.
C) A plus a runtime metric counting leak-guard hits per run. Useful
   eventually but not at v1; defer per the same DEBT-005 rationale.

[Answer]: A

---

### Q8: Tech stack additions for u2

Anything new beyond stdlib + project core (`pydantic`, `pytest`,
`hypothesis`)?

| Component | Locked / Suggested | Decision |
|-----------|---------------------|----------|
| Subprocess | stdlib `subprocess` | A |
| Hashing (fixture key) | stdlib `hashlib.sha256` | A |
| JSON | stdlib `json` (R7 serialization, Stage 1 parsing) | A |
| Time | stdlib `time.monotonic` (RetryBudget tracking) | A |
| Date | stdlib `datetime` (target_date, ts) | A |
| Logging | stdlib `logging` (parallel to u1 TS-5) | A |
| Prompt templating | depends on Q5 — stdlib `str.format` if Q5=A; `jinja2>=3` if Q5=B | A (depends) |
| LLM fixture format | JSON files in `tests/fixtures/llm/<sha256>.json` (R9) | A |
| Test-side runner | `FakeClaudeRunner` in-house (no `pytest-subprocess` etc.) | A |

A) **All recommended above** (권장). NEW deps added to
   `[project.dependencies]`: **none** if Q5=A; only `jinja2>=3` if
   Q5=B; `pyyaml` or `ruamel.yaml` if Q5=C.
B) Override one or more (specify which and why).

[Answer]: A

---

### Q9: NFR drift / monitoring

What stops u2's NFRs from drifting after it ships?

A) **권장** — same shape as u1's drift plan:
   - PBT round-trips (Q6) live forever in CI.
   - Failure-contract tests (Q3) live forever in CI.
   - Disclaimer idempotence + presence tests (Q4) live forever in CI.
   - Anthropic SDK CI grep (Q2) runs on every PR.
   - Leak-guard regex set (Q7) tests live forever; adding/removing
     a pattern requires a test update, which forces conscious
     review.
   - Functional changes that touch u2's public surface
     (`generate_briefing` signature, `BriefingGenerationError`
     attributes) trigger a fresh `/code-review git`.
B) A plus a per-quarter manual review of leak-guard hit rates.
   Adds a calendar ritual; useful when this becomes a real
   operational concern, but for v1 (1-person tool, no users) it's
   ceremony without payoff.
C) A plus runtime metrics (per-stage attempt counts, p50/p95 LLM
   latency, leak-guard hit count). Defer to a future operations
   ADR; u1 made the same call (AC-D.4).

[Answer]: A

---

## Plan Summary Reference

| Aspect | Recommendation |
|--------|----------------|
| Q1 Performance | A — `generate_briefing` ≤ 300 s wall-clock; budget guard fires before extra attempts |
| Q2 Cost / SDK ban | A — repo-wide CI grep + shell=True ban + code-review rule |
| Q3 Reliability / failure contract | A — three pinning tests (failure modes + signature + programmer-error pass-through) |
| Q4 Disclaimer | A — idempotence PBT + presence + last-section anchor |
| Q5 Prompt templating | A — `briefing/prompts.py` constants + `str.format` (no template engine) |
| Q6 PBT scope | A — `append_disclaimer` + `serialize_items` round-trip + `parse_six_sections` round-trip |
| Q7 Security | A — subprocess list-form + token-not-in-code + leak-guard pattern AC + stderr cap + `<script>` belt-and-braces |
| Q8 Tech stack | A — stdlib only (or `jinja2` only if Q5=B) |
| Q9 Drift | A — CI tests + grep + standard code-review |

---

## How to Fill Answers

Each Q1~Q9 `[Answer]:` accepts a letter (A/B/C/...) or free text.
**"all recommended"** = every option marked A above. If a question
depends on another (Q8 depends on Q5), answering "all recommended"
takes the A→A path.
