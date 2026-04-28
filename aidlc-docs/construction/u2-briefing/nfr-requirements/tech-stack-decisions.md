# Tech Stack Decisions — `u2 briefing`

**Date**: 2026-04-28
**Source**: u2-briefing-nfr-requirements-plan.md (all recommended)

This locks `u2`-specific library choices. Project-wide stack
(Python 3.11+, pydantic v2, ruff, mypy --strict, pytest, hypothesis)
is already fixed in `docs/tech-env.md` and `pyproject.toml` and is
not re-decided here. Unit `u1` already added `defusedxml` and
`bleach` for source-side parsing/sanitization (see
`u1/nfr-requirements/tech-stack-decisions.md`); those are in scope
for `u1` but not used by `u2`.

**Headline result**: u2 adds **zero** new external dependencies.
Every choice below is stdlib or already-locked project core.

---

## TS-1. LLM invocation — stdlib `subprocess`

- **Status**: stdlib, no dep change.
- **Used here**: `briefing/claude_code.py` invokes
  `subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=120)`
  per FD R2.
- **Why stdlib**: the only requirement is "spawn the `claude` CLI
  binary, capture stdout/stderr/returncode, enforce a per-call
  timeout." stdlib `subprocess` does this with no extras needed.
- **Why not `pytest-subprocess` or `anyio.run_process`**:
  - `pytest-subprocess` is test-only; we use `FakeClaudeRunner`
    instead (TS-9) — finer-grained control over the recorded
    fixture lookup.
  - `anyio.run_process` would be the async-native option, but the
    `claude` CLI invocation is sequential per stage, so there's no
    concurrency to gain. The FD R3 retry budget already uses
    `time.monotonic` for cumulative tracking.
- **Forbidden invocations**:
  - `subprocess.run(shell=True)` — pinned by AC-2.2 / AC-7.6 grep.
  - String-form first arg (`subprocess.run("claude -p ...")`) —
    pinned by the same grep.

---

## TS-2. Hashing (fixture key) — stdlib `hashlib`

- **Status**: stdlib, no dep change.
- **Used here**: `FakeClaudeRunner` and the live recording mode
  compute `hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]`
  as the fixture filename key (FD R9).
- **Why sha256 specifically**: collision-resistant enough that two
  different prompts yielding the same first-16-hex-chars key is
  vanishingly improbable; matches the convention u1 might adopt
  for any future hash-keyed fixture.
- **Why 16 chars**: filename ergonomics. Full sha256 is 64 hex
  chars; 16 is enough for practical uniqueness while staying
  human-scannable in a directory listing.

---

## TS-3. JSON — stdlib `json`

- **Status**: stdlib, no dep change.
- **Used here**:
  - R7 serialization: `NormalizedItem` list → JSON array string for
    Stage 1 prompt insertion.
  - Stage 1 output parsing: LLM returns JSON object literal, parsed
    with `json.loads`.
  - LLM fixture file format: `tests/fixtures/llm/<key>.json` is
    parsed with `json.loads`.
- **Why stdlib**: safe by default (no XXE-equivalent vulnerability),
  fast enough for our payload sizes (≤ a few hundred items per
  briefing).
- **Why not `orjson` / `ujson`**: throughput is irrelevant at our
  scale (one briefing/day, ≤ ~100 items). The stdlib's stable API
  + zero deps wins.

---

## TS-4. Time / monotonic clock — stdlib `time.monotonic`

- **Status**: stdlib, no dep change.
- **Used here**: `RetryBudget.elapsed_s` accumulator (FD R3 + L4).
  Each `call_claude_code` invocation records its wall-clock
  duration via `time.monotonic()` deltas; the cumulative total is
  compared to `total_budget_s` before the next attempt is
  dispatched.
- **Why `time.monotonic` and not `time.time`**: monotonic clock is
  immune to NTP corrections and DST jumps. We're measuring
  **elapsed time within one process run**, not absolute wall-clock,
  so monotonic is the right tool.
- **Why not `asyncio.get_event_loop().time()`**: would tie us to a
  specific event-loop implementation; `time.monotonic` works in
  any async runtime.

---

## TS-5. Date / datetime — stdlib `datetime`

- **Status**: stdlib, no dep change.
- **Used here**:
  - `target_date: date` — input parameter, KST trading date.
  - `published_at: datetime` (UTC, tz-aware) — already locked at
    the `models/items.py` level; u2 just consumes.
  - `ts` field in R7 serialization: `dt.astimezone(UTC).isoformat()`
    produces RFC 3339 — same format u1 already produces.
- **Why no third-party date library**: stdlib `datetime` + `zoneinfo`
  cover everything (`Asia/Seoul` is one `ZoneInfo` away). Adding
  `pendulum` or `arrow` would be tooling churn for no clear win.

---

## TS-6. Logging — stdlib `logging`

- **Status**: stdlib, no dep change.
- **Used here**: u2 stays silent at INFO/DEBUG on success (FD L6).
  The orchestrator (u5) emits lifecycle logs around the call. On
  failure, u5's stage guard reads `BriefingGenerationError`
  attributes and logs them as structured fields.
- **Why no `structlog` / `loguru`**: project-wide call from u1
  (TS-5 there). No log aggregation in scope; defer to a future
  operations ADR if/when that changes.
- **Note**: per DEBT-005, the eventual structured-log migration
  spans both u1 and u2 — the choice happens once at the project
  level, not unit-by-unit.

---

## TS-7. Prompt templating — stdlib `str.format`

- **Status**: stdlib, no dep change.
- **Used here**: prompt strings live in
  `src/investo/briefing/prompts.py` as module-level `Final[str]`
  constants (`STAGE1_SYSTEM`, `STAGE1_USER_TEMPLATE`,
  `STAGE2_SYSTEM`, `STAGE2_USER_TEMPLATE`). Variable substitution
  is `template.format(items_json=..., target_date=...)` — only
  literal placeholders, no nested logic.
- **Why `str.format` and not `f-string`**: the templates are
  *constants* loaded at import time; placeholders are filled
  later at call time. `f-string` requires the variables to be in
  scope at template-definition time, which they aren't.
- **Why not `string.Template`**: `str.format` is more idiomatic for
  simple keyword substitution; `string.Template` is geared toward
  user-supplied templates with safety concerns we don't have here
  (the templates are project source code, not user input).
- **Why not `jinja2`**: explicit decision per Q5 of the NFR
  Requirements plan. Templates have 2-3 placeholders, no loops,
  no conditionals — jinja2 syntax + transitive deps + ecosystem
  surface is too much for the payoff. AC-5.5 actively rejects
  the dep.
- **Why not `pyyaml`**: same rationale as jinja2 plus YAML's
  multi-line string ergonomics (`|` vs `>`, indentation rules)
  are worse than triple-quoted Python strings for prompt copy.
- **Forbidden alternatives** (pinned by AC-5.5 / AC-2.2 grep):
  `jinja2`, `pyyaml`, `ruamel.yaml`, `mako`, `chevron`.

---

## TS-8. LLM fixture format — JSON files in `tests/fixtures/llm/`

- **Status**: convention, not a library choice.
- **Used here**: each fixture is one JSON file at
  `tests/fixtures/llm/<sha256(prompt)[:16]>.json` containing:
  ```json
  {
    "prompt": "<full prompt string>",
    "stdout": "<recorded stdout>",
    "stderr": "<recorded stderr>",
    "returncode": 0,
    "elapsed_s": 12.34
  }
  ```
- **Why JSON and not pickle / msgpack / parquet**:
  - Diffable in PR review (every fixture refresh shows up as a
    text diff).
  - Hand-editable when the LLM response is known-good but not
    worth re-recording.
  - Stdlib-only — no extra parser needed.
- **Why one file per prompt**: keeps the prompt-hash → fixture map
  as plain filesystem lookup; no extra index needed; deletes are
  trivial.
- **Why store the prompt itself in the fixture**: lets a developer
  reading a stale fixture see the actual input that produced it,
  without recomputing the hash.

---

## TS-9. Test-side runner — `FakeClaudeRunner` in-house

- **Status**: project-internal class, lives at
  `tests/_helpers/fake_claude_runner.py`.
- **Used here**: every test that invokes `generate_briefing` or
  `call_claude_code` injects a `FakeClaudeRunner` in place of the
  real subprocess call. Lookups go to `tests/fixtures/llm/`. Live
  recording is enabled via `INVESTO_LIVE_LLM=1` env var.
- **Why in-house and not `pytest-subprocess`**:
  - `pytest-subprocess` registers process-mock behavior at the
    subprocess module level; less precise than wrapping our own
    `call_claude_code` boundary.
  - We need fixture key = `sha256(prompt)[:16]` — a custom matching
    rule that doesn't exist in any pre-built mock library.
  - The "missing fixture → fail loudly with hash + prompt excerpt"
    UX is custom; building it on top of a generic library is more
    code than writing the runner from scratch.
- **Why not `unittest.mock.patch("subprocess.run")`**:
  - Patches `subprocess.run` globally for the test, which interferes
    with anything else under test that happens to use subprocess
    (unlikely today, but a footgun for the future).
  - Doesn't enforce the prompt → fixture correspondence the way a
    dedicated runner does.

---

## TS-10. Async runtime — already locked (project core)

- **Status**: already in `pyproject.toml` core deps via
  `pytest-asyncio>=0.23`.
- **Used here**: `generate_briefing`, `call_claude_code`, and the
  Stage 1 / Stage 2 inner helpers are `async def`. The
  `subprocess.run` call inside `call_claude_code` is **sync** —
  wrapped via `asyncio.to_thread(...)` so the event loop isn't
  blocked while `claude` runs.
- **Why `asyncio.to_thread` and not `asyncio.create_subprocess_exec`**:
  - `to_thread` keeps the function shape simple (sync `subprocess.run`
    call, async wrapper).
  - `create_subprocess_exec` would let us stream stdout but we
    don't need streaming (FD L8 — full output, no streaming
    parsing).
  - `to_thread`'s overhead is ~µs; irrelevant compared to the
    subprocess's seconds-scale cost.

---

## Cumulative dependency delta

After Code Generation completes for u2, `pyproject.toml`
`[project.dependencies]` adds:

```toml
# (none — u2 introduces no new external deps)
```

Total project external deps after `u2` lands:
`pydantic`, `httpx`, `defusedxml`, `bleach`. Same four packages
as after u1. **u2 = stdlib + already-locked deps only.**

---

## Out of scope for this unit

- `jinja2` — explicitly rejected (TS-7, AC-5.5)
- `pyyaml` / `ruamel.yaml` — explicitly rejected (TS-7, AC-5.5)
- `mako` / `chevron` / other template engines — same reasoning
- `anthropic` SDK — forbidden repo-wide (AC-2.2, AC-2.3)
- `orjson` / `ujson` — superseded by stdlib `json` (TS-3)
- `pendulum` / `arrow` — superseded by stdlib `datetime` + `zoneinfo`
  (TS-5)
- `structlog` / `loguru` — defer until project-wide log aggregation
  decision (TS-6)
- `pytest-subprocess` — superseded by in-house `FakeClaudeRunner`
  (TS-9)
- LLM streaming — explicitly out per FD L8
- LLM caching — explicitly out per FD L8 (cron is daily; cache
  TTL would be < cron interval)
- Multi-LLM fallback — explicitly out per FD L8 (alert operator,
  skip publish on `claude` failure)

---

## Comparison to u1's dep delta

| Dep | u1 | u2 | Notes |
|-----|----|----|-------|
| `pydantic` | ✓ | ✓ | project core, both consume |
| `httpx` | ✓ | — | u1 fetches HTTP; u2 has no network |
| `defusedxml` | ✓ | — | u1 parses RSS XML; u2 has no XML |
| `bleach` | ✓ | — | u1 sanitizes feed HTML; u2 trusts u1's output |
| `subprocess` (stdlib) | — | ✓ | u2-only — invokes `claude` |
| `hashlib` (stdlib) | — | ✓ | u2-only — fixture key |

The two units have **complementary** dep profiles: u1 handles the
HTTP+parse+sanitize trust boundary; u2 handles the LLM+disclaimer+
leak-guard boundary. Neither overlaps the other's surface area.
