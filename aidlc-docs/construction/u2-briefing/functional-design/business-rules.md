# Business Rules — `u2 briefing`

**Date**: 2026-04-28
**Source**: u2-briefing-functional-design-plan.md (Q1=A through Q9=A)

Rules are listed in order of precedence: a higher-numbered rule
cannot override a lower-numbered one without an explicit ADR.

---

## R1. Two-stage LLM pipeline (Q1=A)

- u2 invokes the LLM **twice**:
  - **Stage 1 — classification**: input is `list[NormalizedItem]`
    serialized as JSON; output is a JSON map
    `{"assignments": {item_id: section_id ∈ {2,3,4,5}}, "unassigned": [item_id, ...]}`.
  - **Stage 2 — synthesis**: input is the items grouped by section
    (the `SectionPlan`); output is markdown with the six section
    headers and Korean prose body for each.
- Stage 1's output is **machine-parsed** before Stage 2 runs. A
  Stage 1 failure halts the pipeline (no Stage 2 invocation).
- Stage 2 produces sections ①, ②, ③, ④, ⑤, ⑥ — six sections only.
  Section ⑦ (disclaimer) is **never** the LLM's job (R5).

**Violation**: a single-prompt collapse, an LLM that writes its own
disclaimer, or a Stage 2 invocation without a successful Stage 1 —
all are forbidden.

---

## R2. Claude Code CLI subprocess only (NFR-002, US-009)

- Every LLM call goes through `briefing.claude_code.call_claude_code`
  which invokes `subprocess.run(["claude", "-p", prompt],
  capture_output=True, text=True, timeout=...)` (Q3=A).
- Auth is via the `CLAUDE_CODE_OAUTH_TOKEN` env var (already injected
  by GitHub Secrets per FR-002). u2 does not read or log the token.
- **Anthropic SDK import is forbidden in the entire repository, not
  just u2**: `from anthropic ...`, `import anthropic`, and the
  `anthropic` package in dependencies are all rejected. The
  `dev-investo` skill's §5.1 sub-agent prompt explicitly enforces
  this; a CI grep test (planned in u2 Code Generation step 9 or
  similar) will pin it as a regression guard.
- `subprocess.run(shell=True)` is forbidden — always use the list form
  to avoid shell injection (a static-analysis lint, not a runtime
  concern, but pinned for the future).

**Violation**: any code path that bypasses `call_claude_code` to reach
the LLM, any addition of `anthropic` to deps, or any `shell=True`.

---

## R3. Retry policy + total budget (NFR-003, NFR-001) (Q4=A)

| Knob | Default |
|------|---------|
| Per-call timeout | 120 s |
| Max attempts (Stage 1) | 3 (1 initial + 2 retries) |
| Max attempts (Stage 2) | 3 (1 initial + 2 retries) |
| Backoff schedule | 0 s, 2 s, 8 s (between attempts) |
| Total wall-clock budget (both stages combined) | 300 s (5 min) |

- **Retry on**: subprocess `returncode != 0`, `subprocess.TimeoutExpired`,
  empty stdout, stdout under a sanity-floor byte length (~50 bytes for
  Stage 1, ~500 bytes for Stage 2), and Stage 1 JSON-parse failure.
- **Do NOT retry on**: stderr containing recognized "auth failed" /
  "missing token" markers (re-issuing won't help — fail fast and
  alert), or `BriefingGenerationError(stage="post_validation")` (PII
  guard hit — re-running the same prompt won't help).
- **Total budget enforcement**: cumulative `elapsed_s` across all
  subprocess calls is compared to `total_budget_s` *before* dispatching
  the next attempt. If the next attempt would exceed budget, raise
  `BriefingGenerationError(stage="budget")` immediately.

**Violation**: ad-hoc retries inside individual functions. All retry
logic lives in one helper consumed by both stages.

---

## R4. Failure isolation contract (Q5=A)

- A failed `call_claude_code` (after retries exhausted) raises
  `BriefingGenerationError` with the appropriate `stage` (R3).
- u5 orchestrator catches the exception in its stage guard, builds a
  `FailureContext`, and routes to `OperatorAlerter` (FR-007).
- u3 Publisher **never** sees a failed briefing. The publish step is
  skipped entirely on `BriefingGenerationError`. This is enforced by
  the type system: `generate_briefing` returns `Briefing` on success;
  there is no failure-bearing union return.
- Programmer errors (e.g. `KeyError` on a missing dict key, attribute
  errors on a None) propagate as ordinary exceptions and are *not*
  wrapped in `BriefingGenerationError`. u5's stage guard converts them
  to a separate "PROGRAMMER_ERROR" alert.

**Violation**: any path that returns a partial `Briefing`, a
`Briefing` with placeholder content, or `Briefing | None`. The
contract is "success → Briefing; failure → exception". Period.

---

## R5. Disclaimer auto-insert + idempotence (NFR-004) (Q7=A)

- The disclaimer text is a **module-level constant**
  `briefing.disclaimer.DISCLAIMER`. It is the literal Korean text
  approved at FD time:

  ```
  ## ⑦ 면책조항
  본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,
  특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다.
  투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,
  본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다.
  ```

- `append_disclaimer(markdown: str) -> str` appends the constant **only
  if not already present**. Substring match on the section header
  `## ⑦ 면책조항` is the idempotence anchor (the body text is allowed
  to drift if a future ADR updates the wording, but the section
  header is the canonical detect).
- The function is **pure** — same input always returns the same
  output. No timestamp, no version, no per-call variation in the
  appended text.
- u3 Publisher's `verify_disclaimer` performs a stricter check:
  exact-substring match of the full `DISCLAIMER` constant. A drift
  between u2's appended text and `DISCLAIMER` (e.g. someone edited
  the constant but not the test fixtures) → publish is blocked. This
  is the defense-in-depth layer (NFR-004).

**Violation**: LLM-authored disclaimer, per-call disclaimer mutation,
disclaimer at the top of the markdown, or relying on the LLM to omit
the disclaimer when re-running on already-disclaimed input.

---

## R6. PII / secret leak guard (US-002 AC) (Q8=A)

- Before constructing the `Briefing` model, the synthesized markdown
  is scanned by `briefing.leak_guard.scan(markdown)`.
- The blocklist (regex, case-insensitive where appropriate):
  - GitHub PAT: `gh[pousr]_[A-Za-z0-9]{36,}`
  - AWS access key: `AKIA[0-9A-Z]{16}`
  - JWT: `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
  - Generic OAuth-looking long base64 (≥ 40 chars, all base64 alphabet): `[A-Za-z0-9+/]{40,}={0,2}` — careful: this can false-positive on legitimate long URLs; pinned to look for the pattern *outside* a `https?://` context
  - Email address: `\S+@\S+\.\S+`
  - Korean phone number: `010[- ]?\d{4}[- ]?\d{4}`
- A hit raises `BriefingGenerationError(stage="post_validation",
  attempt_count=<current>, last_stderr=None,
  cause=ValueError(<which-pattern-matched>))`.
- The blocklist lives in the same module as the scanner. Adding /
  removing patterns is a code change, not config. Justification is
  recorded in the audit log per change.

**Violation**: trusting the LLM via prompt-side instructions only,
deferring all leak detection to u4 notifier (the public archive is a
wider leak surface than Telegram).

---

## R7. NormalizedItem → prompt JSON serialization (Q6=A)

- Items are serialized as a JSON array, one object per item, with
  these fields only:

  ```json
  {
    "id": <int>,
    "category": "news"|"price"|"macro"|"calendar"|"earnings",
    "source": "<source_name>",
    "title": "<title>",
    "summary": "<summary or empty string>",
    "url": "<url or empty string>",
    "ts": "<published_at as RFC 3339 UTC>"
  }
  ```

- `id` is a synthetic integer assigned at serialization time
  (`enumerate`-based, starting at 1). It exists only for Stage 1's
  classification map and is not propagated into the `Briefing`
  output.
- `summary` and `url` collapse `None` to empty string for prompt
  stability (the LLM gets a well-formed JSON regardless of
  optionality).
- `ts` is RFC 3339 UTC (`isoformat()` after `astimezone(UTC)`) — same
  format u1 already produces.
- `raw_metadata` is **NOT** included in the prompt. It is provenance
  data (R8 in u1's rules) — interesting for archival but noise for
  the LLM. Including it costs tokens for no benefit.

**Violation**: passing items as YAML, CSV, free-form prose, or with
`raw_metadata` included.

---

## R8. Korean output, English ticker preservation (FR-002 AC, NFR-004)

- Stage 2 prompt instructs the LLM to write all prose in Korean
  except:
  - English ticker symbols stay as-is (`AAPL`, `MSFT`, `BTC-USD`,
    `SPY`).
  - English company / fund / index names stay as-is when they're
    canonical (`Federal Reserve`, `S&P 500`, `Bitcoin`).
  - Currency symbols (`$`, `¥`, `€`) and number formats (Western
    digits, `1,234.56`) stay as-is.
- The LLM is NOT asked to translate news headlines that happen to be
  in English in the source. Quoting the original headline in Korean
  prose is acceptable; full translation is discouraged unless the
  English-only headline would be unintelligible to a Korean reader.

**Violation**: full Korean translation of tickers (e.g. `애플` for
`AAPL`), Korean transliteration of fund names that have established
Korean names (e.g. `에스피500` for `S&P 500`).

---

## R9. Test fixtures via hash-of-prompt (Q9=A)

- All LLM calls in tests are intercepted by a `FakeClaudeRunner`
  that:
  1. Computes `sha256(prompt)[:16]` as the fixture key.
  2. Looks up `tests/fixtures/llm/<key>.json` containing
     `{prompt, stdout, stderr, returncode, elapsed_s}`.
  3. Replays the recorded `stdout` / `stderr` / `returncode`.
  4. If the fixture is missing, fails the test with a clear "missing
     LLM fixture for prompt <hash>" message.
- A developer regenerating fixtures sets `INVESTO_LIVE_LLM=1`; the
  runner then dispatches a real `subprocess.run` and *records* the
  result to disk before returning. The `INVESTO_LIVE_LLM` mode is
  intended for local fixture refresh; CI never sets it.
- Fixtures are committed to the repo (text-mode JSON, ~few KB each).
  A new prompt hash → a new fixture file → a new commit. PR review
  catches stale fixtures the same way it catches anything else.

**Violation**: stub functions that return canned strings inline in
test code, mocking `subprocess.run` directly without going through
`FakeClaudeRunner`, or hitting the real `claude` CLI in CI.

---

## R10. Section assignment is LLM-decided with category as hint (Q2=A)

- Stage 1's prompt presents `NormalizedItem.category` to the LLM as
  *guidance*, not as a hard rule. The LLM is told:
  - "An `earnings` item usually belongs in section ⑤; a `calendar`
    item usually belongs in section ④. But you may override these
    when the item's substance suggests a better fit."
- The Stage 1 output schema constrains values to `{2, 3, 4, 5}` only
  (R1). Section ① and ⑥ are Stage 2's job; section ⑦ is R5's job.
- An item that the LLM judges to have low signal can be placed in
  `unassigned`. Stage 2's prompt receives the unassigned list as
  context for sections ① and ⑥ but does not direct-quote them.

**Violation**: a hard-coded `category → section` table that bypasses
the LLM (loses the cross-cutting flexibility US-002 implies); a
prompt that doesn't pass `category` at all (loses the signal we
already have).

---

## R11. Determinism vs LLM variance — best-effort

- u2 does NOT pass any `--temperature` / sampling flag to the
  `claude` CLI. Output variance across runs is acceptable as long as:
  - All 6 sections (①-⑥) are present and non-empty (R1).
  - The disclaimer is present (R5).
  - The leak guard (R6) does not match.
  - The Korean / ticker rule (R8) is followed.
- Test suite uses fixtures (R9) for determinism; production accepts
  variance.

**Why pinned**: prevents a future contributor from quietly adding
`--temperature 0` to "make tests deterministic" — that's the wrong
fix; the right fix is the fixture mechanism.

---

## R12. No partial commits across stage boundaries

- `generate_briefing(target_date, items)` is the only public entry
  point for u5. Internally it dispatches to:
  1. Stage 1 LLM call → `ClassificationResult`
  2. Build `SectionPlan`
  3. Stage 2 LLM call → markdown body
  4. `append_disclaimer` → markdown with disclaimer
  5. `leak_guard.scan` → may raise
  6. Build `Briefing` model → may raise `pydantic.ValidationError`
- If any step 1-6 raises, the whole call raises. There is **no path**
  by which a partial `Briefing` reaches the caller. The caller (u5)
  treats the function as atomic.

**Violation**: surfacing intermediate state via output parameters,
side-effect file writes inside `generate_briefing`, or partial
`Briefing` returns.
