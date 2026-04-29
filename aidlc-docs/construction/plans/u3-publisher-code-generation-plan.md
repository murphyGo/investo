# Code Generation Plan: `u3 publisher`

**Date**: 2026-04-30
**Unit**: u3 publisher — Static-site archive writer + disclaimer guard + git commit/push
**Stage**: Code Generation (FD + NFR Requirements both SKIPPED per `execution-plan.md`)

**Plan source**:
- `aidlc-docs/inception/application-design/unit-of-work.md` — u3 module path + DoD
- `aidlc-docs/inception/application-design/component-methods.md` — canonical method signatures
- `docs/requirements.md` — FR-003 (정적 게시) + FR-006 (영구 보관) + NFR-004 (disclaimer enforcement)
- `src/investo/models/briefing.py` — `Briefing` consumer shape (already shipped)
- `src/investo/briefing/disclaimer.py` — `DISCLAIMER` constant for verification anchor

---

## Unit Context

### Stories closed by this stage
- **US-003 정적 게시** — `archive/YYYY/MM/YYYY-MM-DD.md` markdown write (closes when CG completes)
- **US-006 영구 이력 보관** — git commit + push retains every briefing

### Dependencies
- `investo.models.Briefing` — frozen 8-field model
- `investo.briefing.disclaimer.DISCLAIMER` — exact-substring verification anchor
- `subprocess` (stdlib) — git invocation (list form, no `shell=True`)
- **NEW external deps**: NONE. Stdlib + already-locked `pydantic`. No HTTP, no parsing libs needed.

### Definition of Done (from unit-of-work)
- [ ] markdown write follows `archive/YYYY/MM/YYYY-MM-DD.md` structure
- [ ] `verify_disclaimer` matches the canonical `DISCLAIMER` constant from u2
- [ ] `commit_and_push` retries (max N attempts) before raising
- [ ] pre-publish disclaimer-missing → blocks publish with explicit exception (NFR-004)
- [ ] Quality gate green: `ruff check .`, `ruff format --check .`, `mypy --strict src/`, `pytest`
- [ ] Closeout summary written to `aidlc-docs/construction/u3-publisher/code/summary.md`

### Module boundary recap
- u3 imports from `investo.models` (Briefing) and `investo.briefing.disclaimer` (DISCLAIMER constant + `append_disclaimer` defense-in-depth helper). NO other u2 imports.
- u3 does NOT import from `sources` or `notifier` (per Application Design DAG; u3 is a leaf consumer of u2 + models).

---

## Steps

### Step 1: Project bootstrap

- [x] **1.1** Created `src/investo/publisher/__init__.py` — docstring describes the
  3-step publisher contract (verify → atomic write → commit/push) + references plan
  + canonical `component-methods.md`. `__all__: list[str] = []` (public surface
  finalized in Step 7).
- [x] **1.2** Created `tests/unit/publisher/__init__.py` (empty) and
  `tests/unit/publisher/conftest.py` (placeholder docstring noting per-test fixtures
  will land with the writer + git_ops tests; references the Step 5.3 design decision
  (a) for `ARCHIVE_ROOT` redirection).
- [x] **1.3** `pyproject.toml` deps confirmed unchanged. No new dependency.
- [x] **1.4** Quality gate: ruff ✅, ruff format ✅ (68 files), mypy --strict ✅
  (**23 source files**; +1 from u2's 22 baseline = `publisher/__init__.py`),
  pytest **430/430** ✅ (bootstrap-only step; no new tests yet).

---

### Step 2: `errors.py` — Publisher exception hierarchy

**Refs**: component-methods.md (`raises: PublisherIOError` / `raises: PublisherGitError`); unit-of-work DoD (explicit exception on disclaimer miss).

- [x] **2.1** `src/investo/publisher/errors.py` (~140 lines):
  - `class PublisherError(Exception)` — base (matches u1 / u2 precedent: not RuntimeError).
  - `class PublisherDisclaimerError(PublisherError)` — `target_date: date` field; message
    mentions both ISO date + NFR-004 anchor for grep-friendly operator alerts.
  - `class PublisherIOError(PublisherError)` — `target_date / path / cause`; message
    includes `type(cause).__name__` (or "no-cause") for fast triage of `OSError`
    sub-types (PermissionError vs FileNotFoundError vs disk full vs ...).
  - `class PublisherGitError(PublisherError)` — `attempt_count / last_stderr / cause`;
    `last_stderr` UTF-8 byte-truncated to 1024 via the same `_truncate_stderr` helper
    shape as u2's `briefing/errors.py` (errors="ignore" decode for multi-byte safety).
- [x] **2.2** `tests/unit/publisher/test_errors.py` (~210 lines, 20 tests):
  - **Inheritance** (4 tests): all 4 classes subclass `Exception`, not `RuntimeError`;
    the 3 specific classes subclass `PublisherError`.
  - **PublisherDisclaimerError** (2): `target_date` round-trip; message mentions ISO
    date + "NFR-004" substring.
  - **PublisherIOError** (4): full field round-trip; None cause → "no-cause" in message;
    `type(cause).__name__` in message; `from`-chain preserves `__cause__`.
  - **PublisherGitError** (8): field round-trip; attempt_count in message; None stderr
    safe; **4 boundary truncation tests** (at-cap=1024, just-over=1025, far-over=10240,
    multi-byte safe via Korean `가가` straddling the 1024-byte boundary — verifies
    `errors="ignore"` decode produces valid UTF-8); `from`-chain preserves cause.
  - **Public surface** (1): module exports the 4 expected names.
  - **Smoke** (1): `pytest.raises(PublisherDisclaimerError)` round-trip works.
  - Quality gate: ruff ✅, ruff format ✅ (1 file auto-formatted), mypy --strict ✅
    (24 source files; +1 from Step 1's 23 = `publisher/errors.py`), pytest **450/450**
    ✅ (+20 tests; zero regressions).

**Quality gate**: ruff, ruff format, mypy --strict, pytest (full suite + new error tests).

---

### Step 3: `paths.py` — Archive path builder (FR-006)

**Refs**: FR-006 acceptance criteria (`archive/YYYY/MM/YYYY-MM-DD.md`); unit-of-work module path.

- [x] **3.1** `src/investo/publisher/paths.py` (~50 lines):
  - `ARCHIVE_ROOT: Final[Path] = Path("archive")` — repo-root-relative.
  - `def archive_path(target_date: date) -> Path` — `ARCHIVE_ROOT / YYYY / MM /
    YYYY-MM-DD.md` with zero-padded year + month. Pure function; no I/O.
  - Module docstring references FR-006 + cross-units the Step 5.3 decision
    (`monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp_path)` for tests).
- [x] **3.2** `tests/unit/publisher/test_paths.py` (~130 lines, 12 tests):
  - **Constant + signature** (1): `ARCHIVE_ROOT == Path("archive")`, not absolute.
  - **Happy path** (3): typical `2026-04-25`; single-digit month padded; single-digit
    day padded.
  - **Boundaries** (5): year-start (Jan 1), year-end (Dec 31), leap day
    (`date(2024, 2, 29)`), pre-2000 pass-through, year-9999 pass-through. The pass-
    through tests pin that u3 trusts upstream date validation (DEBT-002 tracks the
    model-side bounds question).
  - **Purity** (2): no filesystem stat-check raised on a non-existent path; the
    function reads `ARCHIVE_ROOT` at call time so monkeypatch redirection works
    (proves the Step 5.3 (a) testability claim).
  - **Public surface** (1): module exports `ARCHIVE_ROOT` + `archive_path`.
  - Quality gate: ruff ✅ (1 SIM300 auto-fix — `Path("archive") == ARCHIVE_ROOT`
    literal-first form), ruff format ✅, mypy --strict ✅ (25 source files; +1 from
    Step 2's 24 = `publisher/paths.py`), pytest **462/462** ✅ (+12 tests; zero
    regressions in the prior 450).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 4: `verifier.py` — Disclaimer verification (NFR-004)

**Refs**: NFR-004 (게시 전 disclaimer 검증 강제); component-methods canonical signature `verify_disclaimer(briefing_md: str) -> bool`; cross-unit AC-4.6 (u3 imports u2's `DISCLAIMER` constant).

- [x] **4.1** `src/investo/publisher/verifier.py` (~40 lines): pure
  `verify_disclaimer(briefing_md) -> bool` predicate (`DISCLAIMER in briefing_md`).
  Imports the canonical `DISCLAIMER` from `investo.briefing.disclaimer` — single
  source of truth across u2 + u3. Module docstring documents the NFR-004 +
  AC-4.6 cross-unit contract and the relationship to the future model-side
  invariant (DEBT-001).
- [x] **4.2** `tests/unit/publisher/test_verifier.py` (~125 lines, 9 tests):
  - **Trivial** (2): `verify_disclaimer(DISCLAIMER)` → True; `verify_disclaimer("")`
    → False.
  - **Substring semantics** (2): typical 6-section briefing + DISCLAIMER appended
    at the end → True; arbitrary prefix + suffix wrapping → True.
  - **Negative safety net** (3): truncated DISCLAIMER (`[:-5]`) → False; altered
    DISCLAIMER (single Korean char replaced) → False; header-only `"## ⑦ 면책조항\n"`
    → False (catches LLM-emits-header-but-no-body failure mode).
  - **Cross-unit pin** (1): `inspect.getsource(verifier_module)` contains
    `"from investo.briefing.disclaimer import DISCLAIMER"` — locks against a
    refactor that copies the constant locally and silently desyncs u2 vs u3.
  - **Public surface** (1): module exports `verify_disclaimer`.
  - Quality gate: ruff ✅ (1 I001 import-sort auto-fix on a deferred import block;
    1 file auto-formatted), mypy --strict ✅ (26 source files; +1 from Step 3's 25
    = `publisher/verifier.py`), pytest **471/471** ✅ (+9 tests; zero regressions
    in the prior 462).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 5: `writer.py` — `write_briefing` (FR-003 + NFR-004 enforcement)

**Refs**: component-methods.md (`write_briefing(briefing, target_date) -> Path; raises PublisherIOError`); FR-003 acceptance criteria; NFR-004 (disclaimer enforcement at publish boundary).

- [x] **5.1** `src/investo/publisher/writer.py` (~85 lines): `write_briefing(briefing,
  target_date) -> Path` orchestrating verify-first → mkdir → atomic tmp+os.replace
  → return final path. ``OSError`` during write/replace is wrapped in
  ``PublisherIOError`` with ``target_date`` + ``path`` + ``cause``; `contextlib
  .suppress(OSError)` covers the tmp-file cleanup so the original cause bubbles
  through. Imports `Briefing` from `investo.models`, `archive_path` from
  `publisher.paths`, `verify_disclaimer` from `publisher.verifier`, and the two
  error classes — exactly the surface the orchestrator (u5) needs.
- [x] **5.2** `tests/unit/publisher/test_writer.py` (~250 lines, 11 tests):
  - **Happy path** (3): markdown lands at `archive_root/2026/04/2026-04-25.md` with
    byte-exact content; nested year/month dirs created from a fresh archive tree;
    return value is a `Path` for the orchestrator to stage.
  - **NFR-004 hard block** (1): a Briefing whose `rendered_markdown` lacks DISCLAIMER
    raises `PublisherDisclaimerError` and writes no archive file.
  - **FR-006 same-day overwrite** (1): two writes with the same `target_date` →
    second content fully replaces the first.
  - **Atomic-write contract** (2): monkeypatch `os.replace` to raise `OSError` →
    `PublisherIOError` raised, destination file absent, tmp file cleaned up; AND
    when a previous successful write exists, a failed second write leaves the
    prior content untouched (true atomic guarantee, not just "no destination
    file").
  - **Public surface** (1): module exports `write_briefing`.
  - **archive_root used at call time** (1): proves the Step 5.3 (a) testability
    claim works end-to-end through the writer (function reads `ARCHIVE_ROOT` at
    call time via `archive_path`).
  - **Verify-first ordering** (1): on disclaimer failure, no `mkdir` runs → fresh
    archive tree stays untouched.
  - **Stale tmp cleanup** (1): a stale `.md.tmp` left by a prior crashed run does
    NOT block a fresh write; `open("w")` truncates + `os.replace` atomically
    promotes; no leftover tmp.
  - **`archive_root` test fixture**: introduced in `test_writer.py` per Step 5.3 (a)
    — `monkeypatch.setattr(paths_module, "ARCHIVE_ROOT", tmp_path / "archive")`.
    Could promote to `conftest.py` if other publisher tests need it (defer; only
    writer tests need it today).
- [x] **5.3** Decision (a) confirmed: `ARCHIVE_ROOT` redirection via per-test
  `monkeypatch.setattr` works cleanly and keeps `write_briefing`'s public API
  minimal. `archive_root: Path | None = None` parameter NOT added — would only
  be promoted if u5 orchestrator surfaces a real need.
  - **Lint**: 1 SIM105 issue (`try/except OSError: pass`) → replaced with
    `with contextlib.suppress(OSError):` for the tmp-cleanup path. Cosmetic.
  - Quality gate: ruff ✅, ruff format ✅ (2 files reformatted on initial save),
    mypy --strict ✅ (27 source files; +1 from Step 4's 26 = `publisher/writer.py`),
    pytest **482/482** ✅ (+11 tests; zero regressions in the prior 471).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 6: `git_ops.py` — `commit_and_push` (US-006)

**Refs**: component-methods.md (`commit_and_push(message, files, *, retries=2)` with `PublisherGitError` on exhaustion); US-006 (영구 보관 via git commit); module-boundary rule (subprocess list-form, no `shell=True` — already CI-pinned by `scripts/check_no_anthropic_sdk.py` from u2 Step 10.1).

- [x] **6.1** `src/investo/publisher/git_ops.py` (~150 lines): `commit_and_push(message,
  files, *, retries=2, runner=None)` runs `git add → git commit → git push origin HEAD`
  via injectable `GitRunner` Protocol (test seam matching `subprocess.run`'s shape).
  Whole-pipeline retry — failure at any step rewinds to attempt-1 of the next attempt;
  `_BACKOFF_SCHEDULE = (0.0, 2.0, 8.0)` (mirrors u2 R3). Default `_default_runner`
  delegates to `subprocess.run` with list-form args, no `shell=True`. `OSError` from
  the runner is caught + counted as a failed attempt with `cause` populated; non-zero
  rc records `last_stderr` for the operator alert. Exhaustion → `PublisherGitError(
  attempt_count=retries+1, last_stderr=..., cause=...)`. `git push origin HEAD` avoids
  branch-name resolution.
- [x] **6.2** `tests/unit/publisher/test_git_ops.py` (~270 lines, 12 tests):
  - **Happy path** (2): 3 calls in order with exact argv shapes (`["git", "add", "--",
    ...]`, `["git", "commit", "-m", message]`, `["git", "push", "origin", "HEAD"]`);
    multiple files in a single `git add`.
  - **Retry** (2): push fails on attempt 1, succeeds on attempt 2 → 6 invocations;
    `add` step failure also triggers retry (fails-anywhere semantics).
  - **Exhaustion** (3): 3 push failures → `PublisherGitError(attempt_count=3,
    last_stderr=...)` w/ 9 invocations; 10 KB stderr → truncated to ≤ 1024 bytes
    end-to-end through git_ops; `retries=0` → 1 attempt only, `attempt_count=1`.
  - **Programmer-error pass-through** (2): synthetic `TypeError` from runner
    propagates as-is (not wrapped); `OSError` from runner counts as a failed attempt
    and lands in `cause` on exhaustion (system-level "git not found" diagnosis).
  - **List-form pin** (1): AST-stripped `executable` source contains no `shell=True`
    + no string-form `subprocess.run("git ...")`. Uses local `_strip_docstring`
    helper since `git_ops`'s docstring intentionally mentions the forbidden patterns
    in prose ("no `shell=True`") which would false-positive a raw substring grep.
  - **Backoff** (1): `time.sleep` records `[2.0, 8.0]` for the 2 retry sleeps; no
    sleep before attempt 0. Autouse `_no_real_sleep` fixture skips sleeps elsewhere
    so the rest of the test file runs in ms.
  - **Public surface** (1): module exports `commit_and_push` + `GitRunner`.
  - Quality gate: ruff ✅ (3 lints fixed: 2 RUF002 multiplication-sign in docstrings
    swapped for ASCII `x`; 1 UP037 quoted-type-annotation removed by un-deferring
    the import), mypy --strict ✅ (28 source files; +1 from Step 5's 27 =
    `publisher/git_ops.py`), pytest **494/494** ✅ (+12 tests; zero regressions).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 7: `publisher/__init__.py` public surface + integration smoke test

**Refs**: u3 hand-off notes from u2 summary.md (only `Briefing`, `DISCLAIMER`, `append_disclaimer` consumed; u4/u5 will consume u3's `write_briefing` + `commit_and_push`).

- [x] **7.1** Finalized `src/investo/publisher/__init__.py` (~75 lines):
  - Re-exports the public surface: `write_briefing`, `commit_and_push`, `verify_disclaimer`,
    `archive_path`, `ARCHIVE_ROOT`, plus `GitRunner` Protocol and the 4 error classes.
  - Module docstring documents the orchestrator flow (`write_briefing` → stage path →
    `commit_and_push`), the 3-class failure-mode taxonomy (Disclaimer / IO / Git) with
    operator-alert routing hints, and the module-boundary contract (u3 imports only from
    `investo.models` + `investo.briefing.disclaimer`; explicitly NOT pipeline / claude_code
    / prompts / errors / leak_guard / RetryBudget / BriefingGenerationError).
- [x] **7.2** `tests/integration/test_publisher_smoke.py` (~145 lines, 3 tests):
  - **End-to-end orchestrator flow** (1): `monkeypatch ARCHIVE_ROOT` → `write_briefing`
    → assert archive file at `tmp_path/archive/2026/04/2026-04-25.md` w/ correct content
    + disclaimer present → `commit_and_push` with fake runner → assert 3 invocations
    with exact argv shapes (`["git", "add", "--", ...]` / `["git", "commit", "-m", "publish
    2026-04-25"]` / `["git", "push", "origin", "HEAD"]`).
  - **Public-surface pin** (1): `from investo.publisher import ...` resolves all 9
    expected names (5 functions + ARCHIVE_ROOT + 4 error classes via subclass check).
    The top-of-file import block would have failed if any name were missing — assertions
    are belt-and-braces + grep-friendly.
  - **Cross-unit alignment** (1): `verify_disclaimer(DISCLAIMER)` returns True, confirming
    u3's predicate references the same canonical constant u2 exports.
  - **Step 7.3 (separate public-surface pin file)**: NOT needed — folded into 7.2's
    `test_publisher_public_surface_is_importable` test inside the integration smoke file.
    Avoids a 1-test file with overlapping coverage. Plan checkbox 7.3 marked `[x]` with
    this consolidation note.
- [x] **7.3** Public-surface pin consolidated into 7.2 (`test_publisher_public_surface_is
  _importable`). No separate `test_public_surface.py` created — single home is cleaner.
  - Quality gate: ruff ✅, ruff format ✅ (1 file auto-formatted), mypy --strict ✅
    (28 source files; +0 — `publisher/__init__.py` was already counted in Step 1's mypy
    baseline; this step replaces its content but doesn't add a new file), pytest
    **497/497** ✅ (+3 tests; zero regressions in the prior 494).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 8: Sub-agent code review

Delegate fresh-eyes review per dev-investo skill §5.1. Focus areas:

- **`commit_and_push` retry semantics**: is whole-pipeline retry (vs per-step) the right call? Could a partial-success state (commit but push failed) cause double-commits on retry?
- **Atomic write contract** in `writer.py`: does `os.replace` correctly handle the case where `path` already exists (FR-006 same-day re-run)? Are there any race conditions with concurrent runs? (None expected — single-runner architecture per FR-001.)
- **`verify_disclaimer` substring check**: is exact-substring strong enough? Could a malicious LLM emit something that looks like a disclaimer but with subtle modification? (DEBT-001 tracks the model-side invariant; verifier is the runtime safety net.)
- **Module boundary**: did u3 only import `Briefing` (from `investo.models`) and `DISCLAIMER` (from `investo.briefing.disclaimer`)? No leakage from u2's pipeline / claude_code / errors / etc.
- **subprocess hygiene**: list form, no `shell=True`, no string-form first arg. Repo-wide CI grep already enforces but verify for u3 specifically.
- **Failure-mode coverage**: every public function has a documented exception path with a test pin.

After review:
- Apply Critical / High fixes before commit.
- Triage Medium / Low into TECH-DEBT or apply.
- Document Q&A in audit log.

---

### Step 9: Closeout summary.md + final quality gate

- [ ] **9.1** `aidlc-docs/construction/u3-publisher/code/summary.md`:
  - Files-created table (source + tests).
  - FR-003 / FR-006 / NFR-004 acceptance-criteria traceability (smaller table than u1/u2 — only 3 ACs to pin).
  - Story status: US-003 ✅ closed, US-006 ✅ closed.
  - Open TECH-DEBT items (any new ones from u3; cross-unit DEBT-001 / 002 still tracked).
  - Hand-off notes for **u4 notifier** (who consumes `Briefing` for the public Telegram message; doesn't import u3) and **u5 orchestrator** (who calls `write_briefing` then `commit_and_push` on success).
- [ ] **9.2** Final quality gate: `ruff check .` ✅, `ruff format --check .` ✅, `mypy --strict src/` ✅ (24 source files: 22 prior + ~5 new u3), `pytest` ✅ (~430 + ~30 u3 = ~460 tests).

**Exit**: ✅ `u3 publisher` Code Generation stage CLOSED. Stories US-003 + US-006 close. The unit is eligible for `/cross-check`. Next: u4 notifier / u5 orchestrator (both SKIP FD/NFR per execution-plan), then u6 infra/CI (YAML), then global Build & Test.

---

## Step Dependency Graph

```
1 bootstrap
  ├── 2 errors      (independent — pure exception classes)
  ├── 3 paths       (independent — pure function)
  ├── 4 verifier    (depends on u2.briefing.disclaimer.DISCLAIMER — already shipped)
  ├── 5 writer      (depends on 2, 3, 4 + Briefing model)
  ├── 6 git_ops     (depends on 2)
  ├── 7 __init__    (depends on 2, 3, 4, 5, 6)
  ├── 8 review      (depends on all)
  └── 9 closeout    (depends on all)
```

In practice: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 sequentially (one step per `/dev-investo` invocation per skill rule).

---

## Estimated Scope

- ~5 source files in `src/investo/publisher/` (`__init__.py`, `errors.py`, `paths.py`, `verifier.py`, `writer.py`, `git_ops.py` — actually 6).
- ~6-7 test files in `tests/unit/publisher/` + 1 integration smoke.
- ~9 plan steps, each yielding 1 commit.
- Solo dev: ~1 day (significantly smaller than u2; no LLM, no async, no PBT-heavy invariants).

---

## How to Approve

This plan is the single source of truth for `u3` Code Generation. Reply **approve** to begin Step 1; **changes [N]** to revise step N; or call out any specific design question (e.g., `archive_root` injection from Step 5.3) you want resolved before approval.
