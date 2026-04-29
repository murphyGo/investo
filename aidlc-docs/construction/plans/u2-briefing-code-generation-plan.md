# Code Generation Plan: `u2 briefing`

**Date**: 2026-04-28
**Unit**: u2 briefing — Briefing Generator (Claude Code CLI two-stage flow)
**Stage**: Code Generation
**Plan source**:
- `aidlc-docs/construction/u2-briefing/functional-design/` — entities (E1-E5), rules (R1-R12), business-logic-model (L1-L9)
- `aidlc-docs/construction/u2-briefing/nfr-requirements/` — 49 ACs + tech-stack-decisions (zero new deps)
- `src/investo/models/` — already-shipped foundation (`Briefing`, `NormalizedItem`)
- `src/investo/sources/` — already-shipped (`fetch_all`, `NormalizedItem` producer; consumed by Step 9 PoC)

---

## Unit Context

### Stories Closed by This Stage
- **US-002 매일 한국어 7섹션 시황을 자동 생성한다** (closes when this unit's CG completes)
- **US-009 LLM은 Claude Code CLI(setup token)로만 호출** (closes when this unit's CG completes; cross-cutting CI grep also pins it for the rest of the repo)

### Dependencies
- `investo.models.Briefing` (8-field frozen model with `min_length=1` validators) — foundation
- `investo.models.NormalizedItem`, `Category` — produced by u1, consumed via R7 serializer
- `investo.sources.fetch_all` — used in Step 9's PoC integration test against u1's recorded FOMC fixture
- **NEW external deps**: NONE (per `tech-stack-decisions.md` cumulative delta = 0). Stdlib-only:
  `subprocess`, `hashlib`, `json`, `time.monotonic`, `datetime`, `logging`, `re`, `string.format`,
  `asyncio.to_thread`. Plus already-locked `pydantic`, `hypothesis`, `pytest-asyncio`.

### Definition of Done
- [ ] Every NFR AC from `nfr-requirements.md` has a test pinning it (44 NFR + 5 drift = 49 ACs)
- [ ] Two-stage `generate_briefing` happy path passes against u1's recorded FOMC RSS fixture
  (FD L9 PoC) using a recorded LLM fixture
- [ ] CI grep `scripts/check_no_anthropic_sdk.py` rejects Anthropic SDK + `shell=True` + string-form
  subprocess across `src/`
- [ ] Quality gate green: `ruff check`, `ruff format --check`, `mypy --strict src/`, `pytest`
- [ ] `aidlc-docs/construction/u2-briefing/code/summary.md` written
- [ ] PBT (NFR-006 AC-6.1, 6.2, 6.3) passes with ≥100 examples each

---

## Steps

### Step 1: Project bootstrap for `u2` ✅

- [x] **1.1** `pyproject.toml` `[project.dependencies]` audit — confirmed: deps are
  `pydantic>=2.0`, `httpx>=0.27`, `defusedxml>=0.7`, `bleach>=6` (unchanged); dev deps include
  `pytest`, `pytest-asyncio`, `hypothesis`, `ruff`, `mypy`, `types-bleach`, `types-defusedxml`
  (unchanged). NO `anthropic` entry (grep clean). No edit performed.
- [x] **1.2** Skeleton created:
  - `src/investo/briefing/__init__.py` — docstring placeholder + empty `__all__: list[str] = []`
    (public re-exports finalized in Step 10)
  - `tests/unit/briefing/__init__.py` — empty
  - `tests/_helpers/__init__.py` — empty (FakeClaudeRunner home per TS-9)
  - `tests/fixtures/llm/.gitkeep` — empty (TS-8 fixture-key directory)
- [x] **1.3** `tests/unit/briefing/conftest.py` — docstring placeholder for shared fixtures
  introduced in later steps.
- [x] **1.4** Quality gate clean: ruff ✅, ruff format ✅, mypy --strict ✅ (16 source files,
  +1 from u1 baseline 15), pytest **252/252** ✅ (no new tests this step — bootstrap only).

---

### Step 2: `disclaimer.py` — DISCLAIMER constant + idempotent append_disclaimer ✅

**FD refs**: R5, E (output → `Briefing.disclaimer` field).
**NFR refs**: AC-4.1 (idempotence PBT), AC-4.2 (DISCLAIMER substring), AC-4.3 (last-section anchor),
AC-4.4 (rendered_markdown substring — pinned in Step 9 integration test), AC-4.5 (Final[str] constant),
AC-6.1 (idempotence PBT ≥100 examples).

- [x] **2.1** `src/investo/briefing/disclaimer.py`:
  - `DISCLAIMER: Final[str]` — exact Korean text per FD R5 (5 lines including the `## ⑦ 면책조항`
    header).
  - `append_disclaimer(markdown: str) -> str` — idempotence anchored on the literal substring
    `## ⑦ 면책조항`. If anchor present → return input unchanged. If absent → append `\n\n` +
    `DISCLAIMER` (newline separation guarantees the disclaimer header is the last `## ` block).
  - Module docstring documents the cross-unit contract (u3 publisher's `verify_disclaimer` will
    do an exact substring match on the constant).
- [x] **2.2** `tests/unit/briefing/test_disclaimer.py` — anchor tests:
  - `DISCLAIMER` contains the literal `## ⑦ 면책조항` header.
  - `append_disclaimer("")` → `DISCLAIMER` is a substring of the result.
  - `append_disclaimer("## ① ...\n## ② ...\n## ⑥ ...\n")` → result ends with `DISCLAIMER`,
    `## ⑦ 면책조항` is the last `## ` header (regex find-all anchor check).
  - `append_disclaimer(append_disclaimer(x))` example-based for representative inputs.
  - `append_disclaimer(prefix + DISCLAIMER + suffix)` returns input unchanged when anchor already
    present (idempotence under non-trivial wrapping).
- [x] **2.3** `tests/unit/briefing/test_disclaimer_pbt.py` — hypothesis ≥100 examples:
  - **AC-6.1 idempotence**: `append_disclaimer(append_disclaimer(x)) == append_disclaimer(x)` for
    arbitrary `text()` (unconditional — once anchor is in result, further calls are no-ops).
  - **AC-6.1 presence**: `DISCLAIMER in append_disclaimer(x)` for `x` not containing the anchor.
    Conditioned on anchor-absence: when input already has the anchor (e.g. LLM hallucinated
    section ⑦), R5's anchor-on-header semantics mean we trust the input — u3's
    `verify_disclaimer` is the safety net for body drift. Documented in PBT docstring.
  - **Canary** (third PBT): `_ANCHOR in append_disclaimer(x)` unconditionally — if this breaks,
    the implementation has regressed.
- [x] **2.4** Sub-agent code review — APPROVE; 0 Critical/High/Medium, 4 Lows + 1 verification:
  - **L1** DEBT-001 docstring reference — verified registered in `docs/TECH-DEBT.md` ✅
  - **L2** derive `_ANCHOR` from `DISCLAIMER.split("\n", 1)[0]` — skipped (R5 explicitly decouples
    the anchor from full body wording; explicit form is defensible)
  - **L3** test-side `ANCHOR` literal duplication — skipped (black-box virtue; agent agreed)
  - **L4** regex intent comment in `test_disclaimer.py` — applied
  - No new TECH-DEBT items.

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅ (17 source files; +1 from Step 1's 16),
pytest **265/265** ✅ (+13 new tests: 9 anchor + 3 PBT + 1 type check; 3 PBTs each ran 100 examples).

---

### Step 3: `leak_guard.py` — PII/secret regex blocklist ✅

**FD refs**: R6 (regex set).
**NFR refs**: AC-6.4 (example-based hit/miss), AC-7.3 (regex set pinned), AC-D.4 (process AC —
pattern add/remove requires test + audit log).

- [x] **3.1** `src/investo/briefing/leak_guard.py`:
  - Module-level frozen tuple of `(pattern_name: str, compiled_regex: re.Pattern)` covering the R6
    set:
    GitHub PAT (`gh[pousr]_[A-Za-z0-9]{36,}`), AWS access key (`AKIA[0-9A-Z]{16}`), JWT
    (`eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`), email (`\S+@\S+\.\S+`), Korean phone
    (`010[- ]?\d{4}[- ]?\d{4}`), generic long base64 (`[A-Za-z0-9+/]{40,}={0,2}`) — last pattern
    requires **URL-context exclusion**: if the candidate match is preceded by `https?://` (within a
    short lookbehind window) it does NOT count as a leak.
  - `class LeakGuardHit(NamedTuple)`: `pattern_name: str`, `match_text: str` (truncated to ~64
    chars for safe logging).
  - `scan(markdown: str) -> LeakGuardHit | None` — returns the first hit (deterministic order =
    tuple order). Returns None if clean.
  - **Refinement**: email regex tightened from FD R6 literal `\S+@\S+\.\S+` to ReDoS-safe
    `[^\s@]+@[^\s@]+\.[^\s@]+` after Step 3 sub-agent review (H1). Same matches in practice
    for leak-guard purpose; eliminates quadratic-backtracking on adversarial input. Inline
    comment in `leak_guard.py` documents the change; audit log entry per AC-D.4.
- [x] **3.2** `tests/unit/briefing/test_leak_guard.py` — example-based:
  - **Hit cases (one per pattern)**: `ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`, `AKIA1234567890123456`,
    a synthetic JWT (3 base64url segments joined by `.`), `user@example.com`, `010-1234-5678`,
    a 40+ base64-alphabet blob outside URL context. Each hit returns the corresponding
    `pattern_name`.
  - **Miss cases (false-positive calibration)**:
    - Markdown URL with long path slug `[link](https://example.com/very/long/path/that-looks-base64-AAAAAAAAAAAAAAAA)`.
    - Base64-looking string inside `https://...` URL.
    - Plain Korean text with numbers (`"오늘 010실에서 회의"` ← not 010-XXXX-XXXX format).
    - A normal sentence with `@` (e.g. Twitter handle without domain).
- [x] **3.3** Sub-agent code review — APPROVE_WITH_FIXES; 0 Critical, 2 Highs + 2 Mediums + 3 Lows
  + 2 TECH-DEBT candidates. Applied:
  - **H1** Email regex ReDoS — tightened to `[^\s@]+@[^\s@]+\.[^\s@]+` (audit log per AC-D.4) +
    regression test (`test_email_long_no_dot_completes_quickly`) pins linear behavior on
    adversarial input.
  - **H2** Autolink form `<https://...>` — added `test_autolink_https_excludes_long_base64` to
    pin current correct exclusion behavior.
  - **M2** `mailto:user@example.com` — added `test_mailto_link_is_flagged_as_email` to pin
    documented behavior (mailto in public archive is treated as email leak).
  - **L1** URL-safe base64 alphabet (`-_`) not covered by `oauth_long_base64` — design
    observation; matches FD R6 verbatim. Skipped.
  - **L2** Boundary test at exactly 199/200 chars for `_URL_LOOKBACK_WINDOW` — skipped as cosmetic.
  - **L3** `match_text[:64]` Python str (codepoint) slice — sound for ASCII-only patterns.
  - **TECH-DEBT skipped**: TD-leak-guard-1 (now applied as part of H1) and TD-leak-guard-2
    (URL-safe base64 expansion — defer pending real false-negative evidence; matches u1's
    "wait for ops evidence" pattern for AC-D.5).

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅ (18 source files; +1 from Step 2's 17),
pytest **294/294** ✅ (+29 new tests: 26 leak_guard + 3 ReDoS/autolink/mailto regression pins).

---

### Step 4: `errors.py` — BriefingGenerationError + SubprocessOutcome ✅

**FD refs**: E4 (BriefingGenerationError schema), E5 (SubprocessOutcome value object), L5 (failure
classification matrix).
**NFR refs**: AC-3.2 (BGE shape — pinned via construction examples), AC-7.4 (stderr 1024-byte cap).

- [x] **4.1** `src/investo/briefing/errors.py`:
  - `class SubprocessOutcome` — frozen `@dataclass(frozen=True, slots=True)` with `stdout: str`,
    `stderr: str`, `returncode: int`, `elapsed_s: float`. No methods.
  - `BriefingStage = Literal["classification", "synthesis", "post_validation", "budget"]`
  - `class BriefingGenerationError(Exception)` — subclass of `Exception` (NOT `RuntimeError`,
    matches u1's `SourceFetchError` decision). `__init__(self, *, stage: BriefingStage,
    attempt_count: int, last_stderr: str | None, cause: BaseException | None)`. `__init__`
    truncates `last_stderr` to **1024 bytes** (UTF-8) when non-None — exact byte cap, not
    character cap; trailing partial multi-byte sequence trimmed safely. Message format:
    `briefing failed at stage={stage} after {attempt_count} attempts`.
  - `__all__` re-exports `BriefingGenerationError`, `BriefingStage`, `SubprocessOutcome`.
- [x] **4.2** `tests/unit/briefing/test_errors.py` — anchor tests:
  - `BriefingGenerationError` is `Exception` (not `RuntimeError` — pinned by `assert issubclass(...)
    and not issubclass(BGE, RuntimeError)`).
  - All four `stage` literals construct without error.
  - `attempt_count`, `last_stderr`, `cause` round-trip on access.
  - `from`-chain preserves `__cause__` when raised with `raise BGE(...) from json.JSONDecodeError(...)`.
  - **AC-7.4**: 10 KB stderr → after construction `len(bge.last_stderr.encode("utf-8")) <= 1024`.
  - 1024-byte boundary: 1023-byte stderr passes through unchanged; 1025-byte stderr truncates.
  - Multi-byte truncation safety: stderr ending in mid-character UTF-8 → result is valid UTF-8
    (not `UnicodeDecodeError` on access).
  - `last_stderr=None` for `post_validation` and `budget` stages — explicit construction example
    per E4.
  - `SubprocessOutcome` is frozen (assignment raises `dataclasses.FrozenInstanceError`).
- [x] **4.3** Sub-agent code review — APPROVE; 0 Critical/High/Medium, 2 Lows. Applied:
  - **L1** Stale `__dict__` / "logical immutability" comment in `BGE.__init__` — REMOVED
    (Exception subclasses cannot be easily frozen; matches u1's `SourceFetchError` pattern).
  - **L2** `BriefingStage` Literal alias re-declaration — kept (re-exported in `__all__`).
  - No new TECH-DEBT items.

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅ (19 source files; +1 from Step 3's 18),
pytest **314/314** ✅ (+20 new tests: BGE stage parametrize × 4 + cause-chain + AC-7.4 truncation
×4 (at-cap, just-over, far-over, multi-byte boundary) + SubprocessOutcome × 3 + 4 E4 example cases).

---

### Step 5: `prompts.py` — module-level prompt constants + str.format usage ✅

**FD refs**: L2 prompt skeleton, L3 prompt skeleton, R7 (item serialization shape used in templates),
R8 (Korean+ticker rule embedded in Stage 2 prompt).
**NFR refs**: AC-5.1 (4 Final[str] constants), AC-5.2 (pipeline.py no prompt strings — pinned now
via sentinel-grep test, will continue to enforce when Step 8 lands), AC-5.3 (claude_code.py no
prompt strings — same grep, enforced when Step 6 lands).

- [x] **5.1** `src/investo/briefing/prompts.py`:
  - `STAGE1_SYSTEM: Final[str]` — Korean classifier role + JSON output schema + section-id legend
    + "categories are hints" rule per FD L2.
  - `STAGE1_USER_TEMPLATE: Final[str]` — single placeholder `{items_json}`. Header `Items:` then
    placeholder.
  - `STAGE2_SYSTEM: Final[str]` — Korean writer role + 6-section header list (`## ① 요약` ...
    `## ⑥ 오늘의 관전 포인트`) + Korean+ticker rule (R8) + "do NOT include section ⑦" + "do NOT
    include private tokens/keys" guidance per FD L3.
  - `STAGE2_USER_TEMPLATE: Final[str]` — placeholders `{stage1_grouped}` (or split per section
    bucket), `{unassigned}`, `{target_date}`. Single keyword-format substitution.
  - Module docstring documents the str.format substitution convention and forbids re-introducing
    prompt strings into other modules.
  - `__all__` re-exports the four constants only.
- [x] **5.2** `tests/unit/briefing/test_prompts.py` — anchor tests:
  - The four constants exist, are non-empty, are `str`.
  - Each constant contains its expected anchor: STAGE1_SYSTEM contains `assignments`, STAGE2_SYSTEM
    contains `## ① 요약` and `## ⑥`, etc.
  - `STAGE1_USER_TEMPLATE.format(items_json="[]")` succeeds (placeholder matches).
  - `STAGE2_USER_TEMPLATE.format(...)` with the documented keyword set succeeds.
  - Type-system pin: each constant is `Final[str]` (mypy strict catches drift; not a runtime test).
- [x] **5.3** Sub-agent code review — APPROVE; 0 Critical/High, 2 Mediums + 3 Lows + 2 TECH-DEBT
  candidates. Applied:
  - **M-1** `grouped_sections` brace-contamination forward-warning — DOCUMENTED in module docstring
    "Caller obligations" section (Step 8 wiring contract).
  - **M-2** Defense-in-depth NOT documented in code — DOCUMENTED in module docstring
    "Defense in depth (NFR-007 R6)" section.
  - **L-1** Sentinel rephrase ("Section ID legend" generic) — skipped; already unique enough.
  - **L-2** `pytest.raises(KeyError)` test for SYSTEM-never-formatted convention — APPLIED
    (`test_stage1_system_format_call_raises_key_error`).
  - **L-3** Disclaimer collision check — APPLIED
    (`test_stage1_system_does_not_collide_with_disclaimer_anchor`).
  - **TD-prompts-001** (locked SYSTEM convention test) — applied as L-2 fix.
  - **TD-prompts-002** (Step 8 brace-escaping in build_section_plan) — deferred to Step 8 plan as
    explicit caller obligation.

**Quality gate**: ruff ✅, ruff format ✅ (50 files already formatted), mypy --strict ✅
(20 source files; +1 from Step 4's 19), pytest **332/332** ✅ (+18 new tests: 16 prompts + 2 review-driven).

---

### Step 6: `claude_code.py` — subprocess wrapper + RetryBudget ✅

**FD refs**: R2 (Claude Code CLI subprocess only), R3 (retry policy + total budget), L4 (RetryBudget
algorithm), E5 (SubprocessOutcome).
**NFR refs**: AC-1.1/1.2/1.5 (300 s budget, shared across stages), AC-2.1 (only LLM call site —
also pinned in Step 10 grep), AC-2.5/7.2 (no `CLAUDE_CODE_OAUTH_TOKEN` literal in executable code),
AC-7.1 (list-form subprocess — also pinned in Step 10 grep).

- [x] **6.1** `src/investo/briefing/claude_code.py`:
  - `class RetryBudget` — `@dataclass` with `total_budget_s: float = 300.0`, `elapsed_s: float = 0.0`.
    Methods: `record(seconds: float) -> None` (adds), `would_exceed(next_attempt_estimate_s: float)
    -> bool` (returns `self.elapsed_s + next_attempt_estimate_s >= self.total_budget_s`),
    `check_or_raise(*, stage)` (raises `BriefingGenerationError(stage="budget", ...)` when
    `elapsed_s >= total_budget_s`).
  - `async def call_claude_code(prompt: str, *, timeout_s: float = 120.0, runner=None) ->
    SubprocessOutcome` — when `runner` is None, dispatches via
    `await asyncio.to_thread(subprocess.run, ["claude", "-p", prompt], capture_output=True,
    text=True, timeout=timeout_s)`. Wraps `subprocess.TimeoutExpired` → returns
    `SubprocessOutcome(stdout="", stderr="<timeout>", returncode=124, elapsed_s=timeout_s)` (does
    NOT raise — caller decides whether to retry). When `runner` is non-None, delegates to it (test
    seam for `FakeClaudeRunner` from Step 7).
  - Module docstring re-states R2 / NFR-002 (no Anthropic SDK; subprocess list-form only).
  - `__all__` = `["DEFAULT_TIMEOUT_S", "DEFAULT_TOTAL_BUDGET_S", "ClaudeRunner", "RetryBudget", "call_claude_code"]`.
- [x] **6.2** `tests/unit/briefing/test_claude_code.py` — anchor tests:
  - `RetryBudget` initial state (`elapsed_s == 0`); `record(120)` then `would_exceed(60)` returns
    False; `record(120)` again → `would_exceed(60)` returns True (240 + 60 = 300, threshold met).
  - `check_or_raise(stage="classification")` raises BGE when budget exhausted, returns None
    otherwise.
  - **AC-2.5**: grep `inspect.getsource(claude_code)` for `"CLAUDE_CODE_OAUTH_TOKEN"` substring →
    must be absent.
  - **AC-7.1**: `inspect.getsource(claude_code)` does NOT contain `shell=True` or
    `subprocess.run("claude` (string-form first arg). Pinned redundantly with the Step 10 CI grep
    (belt-and-braces).
  - Smoke test with an injected runner (`runner=FakeRunner` returning canned outcome) — proves
    the runner seam works without spawning a real `claude` subprocess.
  - Timeout simulation via the runner seam (returner that raises `subprocess.TimeoutExpired`) →
    `call_claude_code` returns `SubprocessOutcome` with `returncode=124` and `stderr` containing
    "timeout"; does NOT raise.
- [x] **6.3** Sub-agent code review — APPROVE (ship as-is); 0 Critical/High, 2 Mediums + 3 Lows
  + 2 TECH-DEBT candidates. Applied:
  - **M1** Cancellation propagation gap (`asyncio.to_thread` does not stop the worker thread on
    awaiter cancellation) — REGISTERED as **DEBT-006** (Low priority, defer until u5 orchestrator
    finalizes its `wait_for` wrapping pattern).
  - **M2** Test margin too tight (0.18s for 0.10+0.05 concurrent work) — APPLIED, bumped to
    0.25s with explanatory comment.
  - **L1** `del stage` in `check_or_raise` — kept (defensible per agent reasoning).
  - **L2** `stderr=None` defensive coercion — kept (theoretical defensive code, harmless).
  - **L3** `_executable_source` nested-function docstring stripping — agent's concern was
    incorrect; `ast.walk(tree)` already recurses into nested defs. No action.
  - Added DEBT-006 to TECH-DEBT registry.

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅ (21 source files; +1 from Step 5's 20),
pytest **353/353** ✅ (+21 new tests: 7 RetryBudget + 8 call_claude_code (success/error/passthrough/
timeout/concurrency) + 4 source self-checks (oauth literal/shell=True/string-form-subprocess/
anthropic-sdk-import) via AST-stripped grep + 2 module-shape).

---

### Step 7: `FakeClaudeRunner` — recorded-fixture replay + INVESTO_LIVE_LLM record mode ✅

**FD refs**: R9 (fixture mechanism).
**NFR refs**: AC-6.5 (no test imports `subprocess` directly to invoke `claude`).

- [x] **7.1** `tests/_helpers/fake_claude_runner.py`:
  - `class FakeClaudeRunner` — initializer accepts `fixture_dir: Path` (default
    `Path("tests/fixtures/llm")`). Method `__call__(self, args: list[str], *, capture_output, text,
    timeout) -> subprocess.CompletedProcess` (signature matches `subprocess.run`).
  - Inside `__call__`: extract `prompt = args[args.index("-p") + 1]`, compute
    `key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]`, look up
    `fixture_dir / f"{key}.json"`. Missing file → raise `FixtureMissingError(prompt=prompt[:200],
    key=key, expected_path=...)` with a clear "to record this fixture, set
    INVESTO_LIVE_LLM=1 and re-run" message.
  - Live-recording mode: when `os.environ.get("INVESTO_LIVE_LLM") == "1"`, dispatch
    `subprocess.run` for real, then write the resulting `{prompt, stdout, stderr, returncode,
    elapsed_s}` JSON to `fixture_dir / f"{key}.json"` before returning. Otherwise pure replay.
  - **Atomic write**: live-record path writes to `<key>.json.tmp` then `os.replace(...)` so a
    SIGINT mid-write cannot leave a corrupt fixture (Step 7 review M1).
  - **Args-shape guard**: `args.index("-p")` is wrapped in try/except so a malformed call site
    surfaces a clear ValueError instead of a raw `ValueError`/`IndexError` (Step 7 review L1).
- [x] **7.2** `tests/unit/briefing/test_fake_claude_runner.py`:
  - Replay round-trip: write a fixture file → runner returns matching CompletedProcess.
  - Missing fixture → `FixtureMissingError` with key + prompt-prefix in message.
  - Live mode: when `INVESTO_LIVE_LLM=1` is set + a synthetic recordable command (e.g. `["echo",
    "-p", "test"]` — does NOT actually spawn `claude`) → fixture file is written; subsequent
    replay finds it. Test uses monkeypatch to stub `subprocess.run` itself, so no real subprocess
    is spawned even in live mode.
  - **AC-6.5**: a grep test (`tests/unit/briefing/test_no_direct_subprocess.py`) verifies no test
    file under `tests/` directly imports `subprocess` *and* calls `subprocess.run(["claude",
    ...])`. The only allowed direct-`subprocess` use sites are: the production
    `briefing/claude_code.py`, the FakeClaudeRunner's live-mode escape hatch (also under `tests/`),
    and existing test files (e.g., `test_no_paid_apis.py` which spawns the script for end-to-end
    verification — already excluded by allowlist).
- [x] **7.3** Sub-agent code review — APPROVE; 0 Critical/High, 1 Medium + 4 Lows + 2 TD candidates.
  Applied:
  - **M1** Non-atomic fixture write — APPLIED (tmp-file + `os.replace`); test pins no `.tmp`
    leftover after successful write.
  - **L1** Args-shape contract guard — APPLIED (clear ValueError for `["claude"]` /
    `["claude", "-p"]` / etc.); 2 new tests pin the guard.
  - **L2** `_KEY_LENGTH = 16` "64 bits" comment — sound; no action.
  - **L3** AST grep doesn't cover `from subprocess import run` aliased imports — acceptable
    trade-off (false-positive immunity > exhaustiveness); deferred.
  - **L4** Test reads private `_fixture_dir` attribute — acceptable for internal helper test;
    deferred.
  - TD-fake-claude-runner-atomic-write applied as M1 fix (no TECH-DEBT registry entry needed).
  - TD-fake-claude-runner-args-shape-guard applied as L1 fix (no registry entry needed).

**Quality gate**: ruff ✅, ruff format ✅, mypy --strict ✅ (21 source files; +0 — helper lives
under `tests/`), pytest **369/369** ✅ (+16 new tests: 13 base behavior + 3 review-driven
regression pins for atomic write + args-shape guard).

---

### Step 8: `pipeline.py` — classify + synthesize + generate_briefing + R7/E3 helpers

**FD refs**: L1 end-to-end flow, L2 classify, L3 synthesize, L4 RetryBudget shared across stages,
R1 two-stage, R7 NormalizedItem JSON serialization, R10 LLM-decided assignment, R12 atomic
generate_briefing, E2 ClassificationResult, E3 SectionPlan.
**NFR refs**: AC-1.1/1.2/1.5 (budget integration), AC-3.1 (Briefing return type — no Optional),
AC-4.4 (DISCLAIMER substring in rendered_markdown — pinned in Step 9 integration), AC-5.2 (pipeline
contains no prompt body strings — sentinel grep test), AC-6.2 (serialize_items_for_prompt
round-trip PBT), AC-6.3 (parse_six_sections round-trip PBT).

- [x] **8.1** `src/investo/briefing/pipeline.py`:
  - `ClassificationResult` — pydantic model with `assignments: dict[int, int]` and
    `unassigned: list[int]`. `model_config = ConfigDict(extra="forbid", frozen=True)`. **Impl
    note**: section-id constraint enforced via `field_validator("assignments")` with
    `_VALID_SECTION_IDS = frozenset({2, 3, 4, 5})` rather than the planned
    `Field(ge=2, le=5)`; identical effect for ints + clearer error.
  - `SectionPlan` — frozen dataclass: `target_date: date`, `items_by_section:
    dict[int, tuple[NormalizedItem, ...]]`, `unassigned: tuple[NormalizedItem, ...]`.
  - `serialize_items_for_prompt(items)` — R7: emit JSON array, fields `{id, category, source,
    title, summary, url, ts}`. Synthetic `id` = `enumerate(items, start=1)`. `summary`/`url`
    collapse `None` → `""`. `ts` = `published_at.astimezone(UTC).isoformat()`. `raw_metadata`
    excluded. `json.dumps(payload, ensure_ascii=False)` → str.
  - `_parse_classification(stdout, item_count)` — strict JSON parse +
    `ClassificationResult.model_validate(...)` + id-set check (every key + unassigned element
    in `1..item_count`); raises `ValueError`/`ValidationError`/`json.JSONDecodeError` on mismatch.
  - `build_section_plan(items, classification, target_date)` — pure; sorts each section bucket
    by `published_at desc`.
  - `parse_six_sections(markdown)` — splits on `STAGE2_SECTION_HEADERS`. Returns 6 bodies.
    Raises `ValueError` if any header missing, headers out of order (defensive — beyond plan),
    or body blank.
  - `async def _classify(items, *, runner, budget)` and `async def _synthesize(plan, *,
    runner, budget)` — FD R3 retry loop (3 attempts × 0/2/8s backoff × 120s per-call). **Impl
    note**: prompts imported at module level (no `prompts` parameter); single-prompt-set reality
    doesn't need an injection seam.
  - `async def generate_briefing(target_date, items, *, runner=None, budget=None) -> Briefing`
    — atomic L1 + R12: classify → `build_section_plan` → `_synthesize` → `parse_six_sections`
    (extraction) → `append_disclaimer` → `leak_guard.scan` (raise BGE `post_validation` on
    hit) → `Briefing(...)`. Verified: `DISCLAIMER` does not trigger `leak_guard`, so the
    "scan after append" order is safe.
  - **Cross-module fix**: `STAGE2_SECTION_HEADERS: Final[tuple[str, ...]]` moved to
    `prompts.py` (Stage 2 output-contract owner) and re-imported here. Resolves the AC-5.2
    sentinel grep against `## ① 요약` while keeping a single source of truth between "what
    the prompt asks for" and "what we parse for".
  - **prompts.py docstring**: "Caller obligations (Step 8 wiring)" section rewritten as
    "Brace handling note" — `str.format` inserts substituted values as literals (no recursive
    expansion), so `pipeline.py` does NOT need to escape `{` / `}` in user-controlled
    content. Verified empirically: `"a {x} b".format(x="{y}") == "a {y} b"`.
  - Quality gate: ruff ✅, ruff format ✅ (55 files), mypy --strict ✅ (22 source files;
    +1 from Step 7's 21), pytest **369/369** ✅ (no regressions; no new tests yet —
    8.2 / 8.3 / 8.4 still pending).
- [ ] **8.2** `tests/unit/briefing/test_pipeline_unit.py` — anchor tests for the pure helpers:
  - `serialize_items_for_prompt([])` returns `"[]"`.
  - `serialize_items_for_prompt(items)` includes all expected keys, excludes `raw_metadata`,
    collapses None→"", isoformat ts in UTC.
  - `_parse_classification` happy + reject (invalid section_id, unknown id, bad JSON, extra keys).
  - `build_section_plan` happy: items 1,2,3 → section 2,3,4 → plan has 3 buckets each with 1 item.
  - `parse_six_sections` happy + reject (missing header, blank body, headers in wrong order).
- [ ] **8.3** `tests/unit/briefing/test_pipeline_pbt.py` — hypothesis ≥100 examples each:
  - **AC-6.2**: `serialize_items_for_prompt(items)` round-trip — `json.loads(serialize(items))`
    yields list of dicts, `len == len(items)`, fields exactly `{id, category, source, title,
    summary, url, ts}`, `raw_metadata` not in keys, empty url/summary serialized as `""`.
  - **AC-6.3**: `parse_six_sections` round-trip — for synthetic markdown built by joining six
    non-blank bodies under fixed headers, output equals input bodies (whitespace-normalized).
- [ ] **8.4** `tests/unit/briefing/test_pipeline_no_prompt_strings.py`:
  - **AC-5.2**: `inspect.getsource(briefing.pipeline)` does NOT contain sentinel substrings of
    Stage 1 / Stage 2 prompts (e.g. `"market-briefing classifier"`, `"## ① 요약"`,
    `"market-briefing writer"`). Same shape as u1's no-prompt-leak grep.
  - **AC-5.3**: same grep against `inspect.getsource(briefing.claude_code)`.
- [ ] **8.5** Sub-agent code review — focus on the retry-loop algorithm (does it correctly
  decrement the shared budget?), the parse_six_sections regex/split logic (Korean numerals
  ① through ⑥ are non-ASCII), and the L1 ordering (disclaimer must come AFTER leak_guard? — re-read
  FD L1 step 9 vs 10: append_disclaimer first, THEN leak_guard scan on the disclaimer-included
  markdown).

**Quality gate**: ruff, mypy --strict, pytest (full suite + pipeline unit + 2 PBTs at 100 each +
sentinel grep).

---

### Step 9: Failure-contract + budget tests + happy-path PoC integration

**FD refs**: L9 PoC reference flow (against u1's recorded FOMC fixture).
**NFR refs**: AC-1.3, AC-1.4, AC-1.5 (budget tests); AC-3.2, AC-3.4, AC-3.5 (failure modes);
AC-4.4 (rendered_markdown contains DISCLAIMER); AC-7.5 (no `<script>` substring); AC-6.5 (all LLM
calls go through FakeClaudeRunner — pinned by overall test design).

- [ ] **9.1** `tests/unit/briefing/test_failure_contract.py`:
  - **Classification BGE**: FakeClaudeRunner serves a fixture with malformed JSON stdout → assert
    `pytest.raises(BriefingGenerationError) as exc; exc.value.stage == "classification"; exc.value.attempt_count == 3;
    isinstance(exc.value.cause, json.JSONDecodeError)`.
  - **Synthesis BGE**: blank stdout × 3 → `stage="synthesis"`, `attempt_count==3`.
  - **Post-validation BGE**: Stage 2 fixture returns markdown containing a synthetic GitHub PAT
    → `stage="post_validation"`, `attempt_count==1` (no retry per R6), `cause` is `ValueError`
    naming the matched pattern.
  - **AC-3.4 programmer-error**: monkeypatch `build_section_plan` to raise `KeyError("synthetic")`
    → `pytest.raises(KeyError)` succeeds, `pytest.raises(BriefingGenerationError)` fails (verify
    the KeyError is NOT wrapped).
  - **AC-3.5 ValidationError**: monkeypatch `parse_six_sections` to return a dict missing fields →
    `pytest.raises(pydantic.ValidationError)` (NOT wrapped in BGE).
- [ ] **9.2** `tests/unit/briefing/test_budget_happy_path.py`:
  - **AC-1.1**: FakeClaudeRunner serves Stage 1 + Stage 2 fixtures with `elapsed_s=60.0`. Patch
    `time.monotonic` (or use a controllable clock) so the runner reports those elapsed values.
    Assert `generate_briefing` returns within ≤300 s wall-clock.
- [ ] **9.3** `tests/unit/briefing/test_budget_guard.py`:
  - **AC-1.4 + 1.5**: Stage 1 first attempt reports `elapsed_s=200`. RetryBudget records 200.
    Stage 2 first attempt would push elapsed to 400 → `would_exceed` returns True before dispatch
    → `BriefingGenerationError(stage="budget")` raised. Assert exactly **2** runner invocations
    (Stage 1 + the budget-check-fired-early case; Stage 2 never dispatches).
- [ ] **9.4** `tests/integration/test_briefing_pipeline_poc.py` — FD L9 PoC:
  - Use u1's recorded `tests/unit/sources/fixtures/api/fomc-rss/feed.xml` to drive
    `fetch_all(date(2026, 4, 25))`. Get the 2 FOMC items.
  - Use a recorded LLM fixture under `tests/fixtures/llm/` (key = sha256 of the actual Stage 1
    prompt produced by the serializer + system prompt). Stage 1 fixture asserts
    `{"assignments": {1: 4, 2: 4}, "unassigned": []}`. Stage 2 fixture provides 6 valid Korean
    sections with the FOMC events mentioned in section ④.
  - Run the full `generate_briefing` pipeline. Assert:
    - Result is a `Briefing` (not None).
    - `briefing.disclaimer == DISCLAIMER`.
    - `DISCLAIMER in briefing.rendered_markdown` (AC-4.4).
    - `"<script>" not in briefing.rendered_markdown` (AC-7.5, case-insensitive).
    - All 7 section fields are non-blank (`min_length=1` already enforced by the model, but
      we re-check for diagnostic clarity).
  - **Bootstrapping note**: this fixture must be initially recorded by setting
    `INVESTO_LIVE_LLM=1` and running the test against a real `claude` CLI. Document this in the
    test's docstring + in `aidlc-docs/construction/u2-briefing/code/summary.md` under "Fixture
    refresh procedure". CI runs in pure replay mode.
- [ ] **9.5** Sub-agent code review — focus on the integration test's coupling to u1's recorded
  fixture (any change to u1's fetcher should not silently break u2's PoC), and the deterministic-
  prompt-hash dependency (R7 serializer must produce stable JSON: key ordering, whitespace).

**Quality gate**: ruff, mypy --strict, pytest (full suite + failure-contract + 2 budget tests +
integration PoC).

---

### Step 10: CI SDK guard + CONTRIBUTING.md update + closeout

**FD refs**: R2 (Anthropic SDK ban + shell=True ban — repo-wide enforcement).
**NFR refs**: AC-2.1, AC-2.2, AC-2.3, AC-2.4 (CI grep); AC-7.1, AC-7.6 (no shell=True / no
string-form subprocess — same grep); AC-D.1, AC-D.2, AC-D.3 (drift).

- [ ] **10.1** `scripts/check_no_anthropic_sdk.py`:
  - Greps `src/**/*.py` for the three regexes per AC-2.2:
    `^\s*(from anthropic|import anthropic)`,
    `subprocess\.(run|Popen)\([^)]*shell\s*=\s*True`,
    `subprocess\.(run|Popen)\(\s*"[^"]*"\s*[,)]` (string-form first arg).
  - Greps `pyproject.toml` for `anthropic` in `[project.dependencies]` or
    `[project.optional-dependencies]`.
  - Exit 0 on clean tree, exit 1 with offender list to stderr.
  - Style mirrors u1's `scripts/check_no_paid_apis.py`.
- [ ] **10.2** `tests/unit/briefing/test_no_anthropic_sdk.py`:
  - Script-exists + executable.
  - Subprocess-runs-cleanly on the current tree (exit 0).
  - `find_offenders` (importable function) returns empty for the repo.
  - Monkeypatch a synthetic file with `import anthropic` → script flags it. Same for
    `shell=True` and string-form `subprocess.run("claude ...")`.
- [ ] **10.3** Update `CONTRIBUTING.md` (existing file from u1 Step 10):
  - Add a "Briefing prompts" section: prompts live ONLY in `src/investo/briefing/prompts.py`;
    do not embed in `pipeline.py` or `claude_code.py` (AC-5.2/5.3).
  - Add a "LLM fixture refresh" section: how to set `INVESTO_LIVE_LLM=1` to record fresh
    fixtures, and what to commit (`tests/fixtures/llm/<key>.json`).
  - Add a "PR description checklist" item: any new external network call must declare its cost
    impact in the PR description (AC-2.4 extension to all units).
- [ ] **10.4** `aidlc-docs/construction/u2-briefing/code/summary.md` — closeout:
  - Files-created table (source + tests).
  - Full 49-AC traceability table (every AC mapped to a canonical test or documented passive
    guarantee).
  - Story status: US-002 ✅ closed, US-009 ✅ closed.
  - FD-vs-impl divergences (if any during steps 2-9; record per-step audit log).
  - Open TECH-DEBT (DEBT-001 referenced under AC-4.4 as future invariant; check for new items
    introduced during steps 2-9).
  - Hand-off notes for u3 publisher: u3 imports `briefing.disclaimer.DISCLAIMER` for its
    `verify_disclaimer` exact-substring match; u3 imports `briefing.Briefing` (already from
    `models`). u3 does NOT import any other u2 symbol.
- [ ] **10.5** Final quality gate green: `ruff check .` ✅, `ruff format --check .` ✅,
  `mypy --strict src/` ✅, `pytest` ✅ (full suite — u1 baseline + all u2 tests).

**Exit**: ✅ `u2 briefing` Code Generation stage CLOSED. Stories US-002 and US-009 close. The
unit is eligible for `/cross-check`. Next: u3 publisher / u4 notifier / u5 orchestrator (all
SKIP FD/NFR per execution-plan — straight to Code Generation), then global Build & Test.

---

## Step Dependency Graph

```
1 bootstrap
  ├── 2 disclaimer    (independent — pure function)
  ├── 3 leak_guard    (independent — pure function)
  ├── 4 errors        (used by 6, 8, 9)
  ├── 5 prompts       (used by 8)
  ├── 6 claude_code   (depends on 4)
  ├── 7 FakeClaudeRunner (independent of src/; testbed for 6, 8, 9)
  ├── 8 pipeline      (depends on 2, 3, 4, 5, 6)
  ├── 9 tests         (depends on 2, 3, 4, 5, 6, 7, 8 + u1 fixture)
  └── 10 closeout     (depends on all)
```

Steps 2/3 can run in parallel after 1 (both pure, no deps). Step 4 must precede 6 (BGE used).
Step 5 must precede 8. Step 6 must precede 8. Step 7 must precede 8 + 9. Step 8 must precede 9.

In practice: execute 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 sequentially (one step per
`/dev-investo` invocation per the skill rule).

---

## Estimated Scope

- ~7 source files in `src/investo/briefing/` (`__init__.py`, `disclaimer.py`, `leak_guard.py`,
  `errors.py`, `prompts.py`, `claude_code.py`, `pipeline.py`)
- ~1 test helper (`tests/_helpers/fake_claude_runner.py`)
- ~10 test files in `tests/unit/briefing/` + 1 integration test
- ~1 CI script (`scripts/check_no_anthropic_sdk.py`)
- ~10 plan steps, each yielding 1 commit
- Solo dev: ~1.5-2 days

---

## NFR AC Coverage Map

| AC | Pinned at step |
|----|----------------|
| AC-1.1 | 9 (test_budget_happy_path) |
| AC-1.2 | 9 (worst-case = budget cap) |
| AC-1.3 | 9 (test_budget_happy_path) |
| AC-1.4 | 9 (test_budget_guard) |
| AC-1.5 | 9 (test_budget_guard — same RetryBudget instance) |
| AC-2.1 | 10 (CI grep — only `claude_code.py` invokes) |
| AC-2.2 | 10 (CI grep) |
| AC-2.3 | 10 (CI grep — repo-wide scope) |
| AC-2.4 | 10 (CONTRIBUTING.md PR-description checklist) |
| AC-2.5 | 6 (test_claude_code — no token literal) |
| AC-3.1 | 8 (signature `-> Briefing`); enforced by mypy strict |
| AC-3.2 | 9 (test_failure_contract — 4 BGE stages) |
| AC-3.3 | 8 (signature in source); enforced by mypy strict |
| AC-3.4 | 9 (test_failure_contract — KeyError pass-through) |
| AC-3.5 | 9 (test_failure_contract — ValidationError pass-through) |
| AC-4.1 | 2 (test_disclaimer_pbt — idempotence) |
| AC-4.2 | 2 (test_disclaimer — DISCLAIMER substring) |
| AC-4.3 | 2 (test_disclaimer — last `## ` header anchor) |
| AC-4.4 | 9 (test_briefing_pipeline_poc — DISCLAIMER in rendered_markdown) |
| AC-4.5 | 2 (Final[str] declaration); enforced by mypy strict |
| AC-4.6 | (cross-unit — u3's NFR scope; documented in 10 summary) |
| AC-5.1 | 5 (prompts.py file structure); reviewed in 5.3 |
| AC-5.2 | 8 (test_pipeline_no_prompt_strings — sentinel grep) |
| AC-5.3 | 8 (test_pipeline_no_prompt_strings — sentinel grep on claude_code) |
| AC-5.4 | (passive — single-file edit pattern; reviewed in 10 closeout) |
| AC-5.5 | 10 (CI grep extension flags jinja2/pyyaml additions) |
| AC-6.1 | 2 (test_disclaimer_pbt) |
| AC-6.2 | 8 (test_pipeline_pbt — serialize round-trip) |
| AC-6.3 | 8 (test_pipeline_pbt — parse_six_sections round-trip) |
| AC-6.4 | 3 (test_leak_guard — hit + miss calibration) |
| AC-6.5 | 7 (test_no_direct_subprocess grep) |
| AC-6.6 | 2, 8 (`@settings(max_examples=100)`) |
| AC-7.1 | 6, 10 (test_claude_code self-check + CI grep) |
| AC-7.2 | 6 (test_claude_code — no token literal); same as AC-2.5 |
| AC-7.3 | 3 (test_leak_guard — R6 set pinned) |
| AC-7.4 | 4 (test_errors — stderr 1024-byte cap) |
| AC-7.5 | 9 (test_briefing_pipeline_poc — `<script>` absent) |
| AC-7.6 | 6, 10 (no `shell=True` test + CI grep) |
| AC-7.7 | (passive — no eval/pickle.loads/exec used; documented in 10 summary) |
| AC-D.1 | 10 (CI test inventory in summary.md) |
| AC-D.2 | 10 (CI grep wired into lint job) |
| AC-D.3 | (process — `/dev-investo` flow) |
| AC-D.4 | (process — leak-guard pattern add/remove requires audit log) |
| AC-D.5 | (deferred — no metrics in v1) |

All 49 ACs traced.

---

## How to Approve

This plan is the single source of truth for `u2` Code Generation. Reply
**approve** to begin Step 1; **changes [N]** to revise step N.
