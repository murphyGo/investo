# NFR Requirements — `u2 briefing`

**Date**: 2026-04-28
**Source**: u2-briefing-nfr-requirements-plan.md (all recommended)

This document fixes measurable, testable acceptance criteria for the
NFRs that touch this unit. Anything not listed here is OUT of scope
for `u2` (typically owned by orchestrator, publisher, or notifier).

The Functional Design (R1-R12) already pins many concrete decisions
(retry counts, leak-guard regex set, fixture mechanism). This NFR
document **does not duplicate** those — it adds the testable AC layer
on top of them and pins what is otherwise ambiguous (e.g. prompt
templating, performance bound).

---

## NFR-001 (share): Performance — u2's slice of the 10-min budget

**Owner of overall budget**: u5 orchestrator (≤ 10 min total run)
**`u2` share**: ≤ 5 min (matches FD R3 RetryBudget)

### Acceptance criteria
- AC-1.1 — `generate_briefing(target_date, items)` returns within
  **300 s** wall-clock on the **happy path** (Stage 1 + Stage 2
  succeed on first attempt, no retries triggered).
- AC-1.2 — Worst case under FD R3's RetryBudget is also **≤ 300 s**.
  The budget is the cap; Stage 2 retries don't get a fresh budget if
  Stage 1 already consumed most of it.
- AC-1.3 — A test (`tests/unit/briefing/test_budget_happy_path.py`)
  pins AC-1.1: `FakeClaudeRunner` injects a 60-s sleep per stage
  (one call per stage) → `generate_briefing` returns ≤ 300 s.
- AC-1.4 — A test (`tests/unit/briefing/test_budget_guard.py`)
  pins AC-1.2: `FakeClaudeRunner` simulates each call taking 200 s.
  Stage 1 attempt 1 succeeds (200 s consumed). Stage 2 attempt 1
  succeeds (400 s total) — but the budget check fires *before*
  Stage 2 dispatches because elapsed_s ≥ total_budget_s. Result:
  `BriefingGenerationError(stage="budget")` with no further
  subprocess call. Test verifies the call count matches expectation.
- AC-1.5 — The 300-s cap is a **shared** counter across both stages.
  If Stage 1 consumes 280 s, Stage 2 has only 20 s before the budget
  guard fires. Pinned by a test that verifies the RetryBudget is
  passed by reference into both stages, not constructed twice.

---

## NFR-002: Cost — Anthropic SDK ban + free-only LLM path

### Acceptance criteria
- AC-2.1 — Every LLM call goes through
  `briefing.claude_code.call_claude_code` (FD R2). No other module
  invokes the `claude` CLI directly. Pinned by a test that greps
  `src/investo/` for `subprocess.run(["claude"...]` and asserts the
  only match is in `briefing/claude_code.py`.
- AC-2.2 — A CI grep guard (`scripts/check_no_anthropic_sdk.py`,
  added during u2 Code Generation, executed by the lint job) fails
  the build if **any** of these conditions hold:
  - Any file under `src/` matches the regex
    `^\s*(from anthropic|import anthropic)`.
  - `pyproject.toml` `[project.dependencies]` or
    `[project.optional-dependencies]` includes `anthropic` at any
    version.
  - Any file under `src/` matches `subprocess\.(run|Popen)\([^)]*shell\s*=\s*True`.
  - Any file under `src/` matches `subprocess\.(run|Popen)\(\s*"[^"]*"\s*[,)]`
    (string-form first arg → likely `shell=True` candidate).
- AC-2.3 — Scope of the AC-2.2 grep is **whole repo**, not just
  `src/investo/briefing/`. The Anthropic SDK ban is a project-wide
  invariant.
- AC-2.4 — The `/code-review` skill rule (already in `dev-investo`
  §5.1) catches the same patterns earlier in PR review. AC-2.2 is
  the safety net.
- AC-2.5 — `briefing/claude_code.py` does NOT read or log
  `CLAUDE_CODE_OAUTH_TOKEN`. The token is consumed by the `claude`
  CLI itself, not by our Python code. Pinned by a test that asserts
  `"CLAUDE_CODE_OAUTH_TOKEN"` is not a literal in executable code
  under `src/investo/briefing/`; explanatory docstrings may mention
  the env var in negative context.

---

## NFR-003: Reliability — failure contract

### Acceptance criteria
- AC-3.1 — `generate_briefing(target_date, items)` returns
  `Briefing` on success and raises `BriefingGenerationError` (BGE)
  on failure. There is no `Briefing | None`, no partial `Briefing`,
  no failure-bearing union return (FD R4 + R12).
- AC-3.2 — Test `tests/unit/briefing/test_failure_contract.py`
  pins all four BGE stages:
  - **Classification**: Stage 1 LLM returns malformed JSON × 3 →
    `BGE(stage="classification", attempt_count=3, last_stderr=..., cause=json.JSONDecodeError)`.
  - **Synthesis**: Stage 2 LLM returns blank stdout × 3 →
    `BGE(stage="synthesis", attempt_count=3, last_stderr="", cause=None)`.
  - **Post-validation**: Leak guard hits on Stage 2 output →
    `BGE(stage="post_validation", attempt_count=1, last_stderr=None, cause=ValueError(<pattern-name>))`
    with **no retry** (R6 is terminal).
  - **Budget**: Total elapsed_s ≥ total_budget_s before next dispatch
    → `BGE(stage="budget", ...)` immediately, no further subprocess
    call.
- AC-3.3 — Type-system AC: `generate_briefing` signature is
  `async def generate_briefing(target_date: date, items: list[NormalizedItem]) -> Briefing`.
  No `Optional`, no `Union`, no `| None`. mypy strict mode catches
  drift; pinned by code review (no test required — the type
  checker is the test).
- AC-3.4 — Programmer-error pass-through: `KeyError` /
  `AttributeError` / `TypeError` originating inside u2's own logic
  (not from the LLM response) propagates as-is, NOT wrapped in
  BGE. Test pins this: monkeypatch `build_section_plan` to raise
  `KeyError("synthetic")` → `pytest.raises(KeyError)` succeeds,
  `pytest.raises(BriefingGenerationError)` fails.
- AC-3.5 — `BriefingGenerationError` does not catch
  `pydantic.ValidationError` raised when constructing the final
  `Briefing` model. ValidationError propagates as-is — it means
  u2's parser produced something the model rejects, which is a
  programmer error. Test pins this with a fake parser that returns
  a dict missing a required field.

---

## NFR-004: Compliance — disclaimer auto-insert + defense-in-depth

### Acceptance criteria
- AC-4.1 — `append_disclaimer(markdown: str) -> str` is **idempotent**:
  for any string `x`, `append_disclaimer(append_disclaimer(x)) == append_disclaimer(x)`.
  Pinned by a hypothesis-based PBT (`text()` strategy, ≥ 100
  examples).
- AC-4.2 — `append_disclaimer(x)` always returns a string containing
  the exact `briefing.disclaimer.DISCLAIMER` constant as a substring.
  Example-based test on representative inputs (empty string, no
  sections, sections 1-6, sections 1-6 + 7).
- AC-4.3 — `append_disclaimer(x)` adds the disclaimer **at the end**
  of the markdown — never at the top, never embedded mid-string.
  Test verifies that `## ⑦ 면책조항` is the last `## ` header in
  the result. Drift here would silently produce malformed briefings.
- AC-4.4 — `Briefing.rendered_markdown` always contains the exact
  `briefing.disclaimer.DISCLAIMER` constant as a substring under
  non-adversarial conditions (i.e. when Stage 2 produced six valid
  sections). Pinned by integration test that runs the full
  `generate_briefing` happy path on a recorded fixture and asserts
  the substring.
- AC-4.5 — `briefing.disclaimer.DISCLAIMER` is a module-level
  `Final[str]` constant. Mutation attempts (which mypy strict
  catches at lint time) would surface as type errors. Pinned by
  code review.
- AC-4.6 — Cross-unit boundary: u3 publisher's `verify_disclaimer`
  is a separate AC owned by u3. u2 only commits to producing
  markdown where the disclaimer is present and exactly matches
  the constant; u3's job is to block publish if the substring is
  missing. (DEBT-001 tracks moving this guarantee one layer
  earlier into the `Briefing` model itself; out of scope for v1.)

---

## NFR-005: Maintainability — prompt code separation

### Acceptance criteria
- AC-5.1 — Prompts live in `src/investo/briefing/prompts.py` as
  module-level Python constants:
  - `STAGE1_SYSTEM: Final[str]`
  - `STAGE1_USER_TEMPLATE: Final[str]`
  - `STAGE2_SYSTEM: Final[str]`
  - `STAGE2_USER_TEMPLATE: Final[str]`
  Variable substitution uses `str.format(**kwargs)`. The only
  placeholders are `{items_json}`, `{grouped_json}`, and
  `{target_date}` (or equivalent) — trivially shaped, no nested
  control flow.
- AC-5.2 — `briefing/pipeline.py` does NOT contain prompt body
  strings. It only imports from `briefing.prompts`. Pinned by a
  test that greps `src/investo/briefing/pipeline.py` for sentinel
  substrings of the prompts (e.g. the "JSON schema" or "Korean
  market-briefing" anchors); a non-empty match fails the test.
- AC-5.3 — `briefing/claude_code.py` does NOT contain prompt body
  strings. It only knows about `subprocess.run` semantics, retry
  primitives, and the `SubprocessOutcome` dataclass. Pinned by the
  same grep approach as AC-5.2.
- AC-5.4 — A change to a prompt = a change to one file
  (`prompts.py`). PR diff for prompt iteration is local to that
  module; review can be done in isolation. This is the
  "코드와 분리" guarantee from `docs/requirements.md` NFR-005,
  satisfied without a template engine.
- AC-5.5 — No template engine dep is added. Specifically: `jinja2`,
  `pyyaml`, and `ruamel.yaml` are NOT in `[project.dependencies]`.
  Pinned by AC-2.2's grep extension (any of these patterns added
  later → grep flags it as a regression alongside the SDK ban).

**Note**: NFR-005 also mentions "Plugin 구조" (data-source plugin
extensibility). That is u1's domain (`u1` AC-5.1 ~ AC-5.4). NOT in
scope for u2.

---

## NFR-006: Testing — PBT partial + LLM fixtures

### Acceptance criteria
- AC-6.1 — `append_disclaimer(s)` has a hypothesis-based property
  test (`tests/unit/briefing/test_disclaimer_pbt.py`) asserting:
  - **Idempotence**: `append_disclaimer(append_disclaimer(x)) == append_disclaimer(x)`.
  - **Presence**: `DISCLAIMER in append_disclaimer(x)`.
  - Strategy: hypothesis `text()` with default size; ≥ 100 examples.
- AC-6.2 — `serialize_items_for_prompt(items)` (R7 serializer) has a
  hypothesis-based round-trip property test
  (`tests/unit/briefing/test_serialize_pbt.py`) asserting:
  - For any `list[NormalizedItem]` (using the strategy already
    defined in `tests/unit/models/`), the serialized JSON parses
    back via `json.loads` to a structurally equivalent list with
    fields `{id, category, source, title, summary, url, ts}` and
    no others.
  - `raw_metadata` is deliberately stripped (R7) — verified by
    asserting it is NOT a key in any serialized object.
  - Empty `summary` / `url` round-trip as `""` (not `None`),
    matching R7's stability rule.
  - ≥ 100 examples.
- AC-6.3 — `parse_six_sections(markdown)` has a hypothesis-based
  round-trip property test
  (`tests/unit/briefing/test_parse_pbt.py`) asserting:
  - For any synthetic markdown built by joining six bodies under
    the fixed headers `## ① 요약`, `## ② 전일 핵심 이슈`, ...,
    `## ⑥ 오늘의 관전 포인트`, `parse_six_sections` returns those
    exact six bodies (whitespace-normalized).
  - Strategy: `text()` × 6, headers prepended; bodies must be
    non-blank (matches Stage 2's "non-blank" invariant).
  - ≥ 100 examples.
- AC-6.4 — `leak_guard.scan(markdown)` does NOT get a PBT.
  Coverage is example-based (`tests/unit/briefing/test_leak_guard.py`):
  - **Hit cases** — at least one canonical example per R6 pattern:
    GitHub PAT, AWS access key, JWT, generic long base64 (outside
    URL context), email, Korean phone.
  - **Miss cases** (false-positive calibration) — a curated list
    of strings that LOOK like patterns but are intentionally fine:
    a markdown URL with a long path slug, a base64-looking string
    inside a `https://` URL, a sample CUSIP, a long ticker name.
- AC-6.5 — All LLM calls in tests go through `FakeClaudeRunner`
  (R9). A test asserts that no test imports `subprocess` directly
  to invoke `claude` — pinned by a grep test on `tests/`.
- AC-6.6 — Hypothesis examples count ≥ 100 per PBT (matches the
  setting already used by `tests/unit/models/test_roundtrip.py`).

---

## NFR-007: Security — subprocess hygiene + leak guard + secret handling

### Acceptance criteria
- AC-7.1 — `subprocess.run` is invoked with the **list form**
  `["claude", "-p", prompt]`, never the string form. AC-2.2's grep
  enforces this repo-wide.
- AC-7.2 — `briefing/claude_code.py` never reads, logs, or passes
  `CLAUDE_CODE_OAUTH_TOKEN` explicitly. Re-stated from AC-2.5;
  pinned by the same grep test.
- AC-7.3 — Leak-guard regex set is exactly the R6 list (no addition,
  no removal without an audit-log entry):
  - GitHub PAT: `gh[pousr]_[A-Za-z0-9]{36,}`
  - AWS access key: `AKIA[0-9A-Z]{16}`
  - JWT: `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
  - Generic OAuth-looking long base64 (≥ 40 chars, base64 alphabet,
    NOT inside `https?://...` URL context):
    `[A-Za-z0-9+/]{40,}={0,2}`
  - Email: `\S+@\S+\.\S+`
  - Korean phone: `010[- ]?\d{4}[- ]?\d{4}`
  Pinned by `tests/unit/briefing/test_leak_guard.py` (AC-6.4).
- AC-7.4 — `BriefingGenerationError.last_stderr` is **truncated to
  1024 bytes** before attachment. AC: a test passes a 10 KB stderr
  via `FakeClaudeRunner` and asserts
  `len(bge.last_stderr.encode("utf-8")) <= 1024`.
- AC-7.5 — `Briefing.rendered_markdown` does NOT contain the
  literal substring `<script>` (case-insensitive). Belt-and-braces
  verification — u1 strips HTML at the source boundary, but a
  malicious LLM response could in principle invent it. Pinned by
  a test that runs the happy path and asserts the substring is
  absent.
- AC-7.6 — `subprocess.run` invocation excludes `shell=True`
  globally under `src/`. Pinned by AC-2.2 grep.
- AC-7.7 — No `eval`, no `pickle.loads`, no `exec` on response
  data inside u2. Implicit in NFR-007 baseline; pinned by
  `tests/unit/briefing/test_no_eval.py` greps over
  `src/investo/briefing/`.

---

## NFR drift / monitoring

### Acceptance criteria
- AC-D.1 — All PBT (AC-6.1, AC-6.2, AC-6.3) and example-based
  regression tests above run in CI on every PR via `pytest`.
- AC-D.2 — The Anthropic SDK + `shell=True` CI grep
  (`scripts/check_no_anthropic_sdk.py`) runs in CI on every PR.
- AC-D.3 — Functional changes that touch u2's public surface
  (`generate_briefing` signature, `BriefingGenerationError`
  attributes, `DISCLAIMER` constant, leak-guard regex set) trigger
  a fresh `/code-review git` per the standard `/dev-investo` flow.
- AC-D.4 — Adding or removing a leak-guard regex requires both:
  (a) a code change to `briefing/leak_guard.py`,
  (b) a corresponding test update,
  (c) an audit-log entry justifying the change.
  AC-D.4 is a **process** AC, not an automated check.
- AC-D.5 — Runtime metrics (per-stage attempt counts, p50/p95 LLM
  latency, leak-guard hit count) are NOT required at v1 — deferred
  to a future ADR if/when operations evidence demands them.
  Matches u1's AC-D.4 deferral.

---

## Trace map

| NFR | Stories tied | Acceptance count |
|-----|--------------|------------------|
| NFR-001 (share) | US-005 | 5 |
| NFR-002 | US-009 | 5 |
| NFR-003 | US-002 | 5 |
| NFR-004 | US-002, FR-002 (compliance) | 6 |
| NFR-005 | US-002 (template separation) | 5 |
| NFR-006 | (cross-cutting) | 6 |
| NFR-007 | (cross-cutting) | 7 |
| Drift | (cross-cutting) | 5 |

**Total ACs**: 44 (NFR) + 5 (drift) = 49 testable acceptance criteria.

Notable cross-references:
- AC-1.5 ↔ FD R3 (shared RetryBudget across stages)
- AC-2.1 / AC-2.2 ↔ FD R2 (Claude Code CLI subprocess only)
- AC-3.5 ↔ FD R4 (programmer-error pass-through)
- AC-4.1 ↔ FD R5 (idempotent disclaimer)
- AC-4.6 ↔ DEBT-001 (Briefing model invariant — future)
- AC-5.5 ↔ Q5 decision rejecting jinja2/pyyaml
- AC-6.4 ↔ FD R6 (leak-guard regex set)
- AC-7.4 ↔ FD E4 (BriefingGenerationError schema)
