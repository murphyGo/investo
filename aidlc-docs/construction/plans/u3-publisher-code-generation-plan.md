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

- [ ] **3.1** `src/investo/publisher/paths.py`:
  - `ARCHIVE_ROOT: Final[Path]` — `Path("archive")`. Relative to repo root; the orchestrator (u5) is responsible for cwd alignment when invoking the pipeline.
  - `def archive_path(target_date: date) -> Path` — returns `ARCHIVE_ROOT / f"{date.year:04d}" / f"{date.month:02d}" / f"{date.isoformat()}.md"`. Pure function; no I/O.
  - Module docstring documents the FR-006 directory contract.
- [ ] **3.2** `tests/unit/publisher/test_paths.py`:
  - `archive_path(date(2026, 4, 25)) == Path("archive/2026/04/2026-04-25.md")`.
  - Year-end boundary: `date(2026, 12, 31)` → `archive/2026/12/2026-12-31.md`.
  - Year-start boundary: `date(2026, 1, 1)` → `archive/2026/01/2026-01-01.md`.
  - Pre-2000 + post-9999 dates: pass through (no clamping; u3 trusts upstream).
  - `archive_path` is pure (no side effects, no I/O).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 4: `verifier.py` — Disclaimer verification (NFR-004)

**Refs**: NFR-004 (게시 전 disclaimer 검증 강제); component-methods canonical signature `verify_disclaimer(briefing_md: str) -> bool`; cross-unit AC-4.6 (u3 imports u2's `DISCLAIMER` constant).

- [ ] **4.1** `src/investo/publisher/verifier.py`:
  - `def verify_disclaimer(briefing_md: str) -> bool` — `return DISCLAIMER in briefing_md`. Imports `DISCLAIMER` from `investo.briefing.disclaimer`. Pure boolean predicate; the caller (`write_briefing` in Step 5) blocks the publish on `False`.
  - Module docstring documents the cross-unit contract: u3 SHOULD NOT redefine `DISCLAIMER`; the canonical anchor lives in u2.
- [ ] **4.2** `tests/unit/publisher/test_verifier.py`:
  - `verify_disclaimer(DISCLAIMER)` → True (trivial substring case).
  - `verify_disclaimer("")` → False.
  - `verify_disclaimer(prefix + DISCLAIMER + suffix)` → True (substring check).
  - `verify_disclaimer(DISCLAIMER[:-5])` → False (truncated disclaimer is NOT acceptable; the constraint is exact-substring).
  - `verify_disclaimer(altered_disclaimer)` → False (a single-character change to the disclaimer body breaks the check).
  - **Cross-unit pin**: import `DISCLAIMER` from `investo.briefing.disclaimer` directly in the test and confirm `verify_disclaimer(DISCLAIMER)` returns True. If u2 changes the constant, u3 follows automatically because the import is shared.

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 5: `writer.py` — `write_briefing` (FR-003 + NFR-004 enforcement)

**Refs**: component-methods.md (`write_briefing(briefing, target_date) -> Path; raises PublisherIOError`); FR-003 acceptance criteria; NFR-004 (disclaimer enforcement at publish boundary).

- [ ] **5.1** `src/investo/publisher/writer.py`:
  - `def write_briefing(briefing: Briefing, target_date: date) -> Path`:
    - Step 1: Call `verify_disclaimer(briefing.rendered_markdown)`. If False → raise `PublisherDisclaimerError` with `target_date` context. **No write happens** (NFR-004 hard block).
    - Step 2: Compute `path = archive_path(target_date)`.
    - Step 3: `path.parent.mkdir(parents=True, exist_ok=True)`.
    - Step 4: **Atomic write** via tmp file + `os.replace`: write `briefing.rendered_markdown` to `path.with_suffix(".md.tmp")`, then `os.replace(tmp, path)`. Same pattern as u2's `FakeClaudeRunner` fixture write.
    - Step 5: Return `path`.
    - On any `OSError` during the write/replace path, raise `PublisherIOError(target_date=..., path=path, cause=exc)` and ensure no partial `.tmp` file is left.
- [ ] **5.2** `tests/unit/publisher/test_writer.py`:
  - **Happy path**: a valid Briefing (with disclaimer) writes the markdown to `tmp_path/archive/YYYY/MM/YYYY-MM-DD.md`. Use `monkeypatch` to point `paths.ARCHIVE_ROOT` (or pass `archive_root` explicitly — see open question below) at `tmp_path`. Verify file content equals `briefing.rendered_markdown`.
  - **Disclaimer missing**: a Briefing whose `rendered_markdown` lacks DISCLAIMER (constructed by mutating a valid one — `model_validate` will accept it because the model doesn't enforce the cross-field invariant per DEBT-001) → raises `PublisherDisclaimerError`. Confirm NO file is created.
  - **Idempotent overwrite (FR-006 same-day re-run)**: write twice with the same `target_date` and slightly different markdown content. Second write overwrites; final content matches the second write.
  - **Atomic guarantee**: monkeypatch `os.replace` to raise `OSError`; confirm `PublisherIOError` is raised and the destination file does NOT exist (the tmp file may or may not exist depending on the failure mode — pin only that the destination is unaffected).
  - **mkdir creates nested year/month dirs**: a fresh `tmp_path` with no `archive/` tree → write succeeds and creates the `2026/04/` hierarchy.
- [ ] **5.3** **Open design question to resolve at planning approval**: `paths.ARCHIVE_ROOT` is a module-level constant (`Path("archive")`). Tests need to redirect it to a tmp directory. Two options:
  - (a) `monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp_path / "archive")` per-test. Simple but requires every test to remember.
  - (b) Add an `archive_root: Path | None = None` parameter to `write_briefing` (and `archive_path`) defaulting to `ARCHIVE_ROOT`. Opens an injection seam for tests + future operations.
  - **Recommendation**: (a) for v1 — minimal API surface, matches u1's `_isolate_registry` autouse-fixture pattern. Promote to (b) only if u5 orchestrator surfaces a real need to pass a non-default archive root.

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 6: `git_ops.py` — `commit_and_push` (US-006)

**Refs**: component-methods.md (`commit_and_push(message, files, *, retries=2)` with `PublisherGitError` on exhaustion); US-006 (영구 보관 via git commit); module-boundary rule (subprocess list-form, no `shell=True` — already CI-pinned by `scripts/check_no_anthropic_sdk.py` from u2 Step 10.1).

- [ ] **6.1** `src/investo/publisher/git_ops.py`:
  - `def commit_and_push(message: str, files: Sequence[Path], *, retries: int = 2, runner: GitRunner | None = None) -> None`:
    - Three subprocess invocations in sequence: `git add <files>`, `git commit -m <message>`, `git push origin <current-branch>`.
    - List form, capture output, no `shell=True`.
    - Retry on each step independently? Or whole-pipeline retry? Per FD R3 precedent in u2: **whole-pipeline retry** — easier to reason about (a partial state from a `git commit` succeeding but `git push` failing is recovered by re-running the full sequence; `git commit` is idempotent if the working tree matches).
    - Backoff: `0s, 2s, 8s` (matches u2 R3). Total budget: not strictly needed for git (no LLM cost concern), but document the worst case (3 attempts × ~5s push each = 15s).
    - On exhausting `retries + 1` attempts: raise `PublisherGitError(attempt_count=retries+1, last_stderr=..., cause=last_exc)`.
    - `runner` is a test seam (Protocol matching `subprocess.run`'s shape) so tests can inject a fake without spawning real `git`.
- [ ] **6.2** `tests/unit/publisher/test_git_ops.py`:
  - **Happy path**: 3 `add/commit/push` calls succeed on first attempt. Asserts exactly 3 runner invocations + arg shapes (`["git", "add", ...]`, `["git", "commit", "-m", ...]`, `["git", "push", ...]`).
  - **Retry on transient push failure**: push returncode=1 on attempt 1, returncode=0 on attempt 2 → succeeds. 6 invocations total (3 × 2 attempts).
  - **Failure exhaustion**: all attempts fail → `PublisherGitError`, `attempt_count=3`, `last_stderr` populated and ≤ 1024 bytes.
  - **stderr 1024-byte truncation**: 10 KB stderr from a fake-failed `git push` → truncated to ≤ 1024 bytes in `PublisherGitError.last_stderr`.
  - **List-form pin** (defensive): `inspect.getsource(git_ops)` doesn't contain `shell=True` or string-form `subprocess.run("git ..."` — same pattern as u2 `test_claude_code.py`. Belt-and-braces with the repo-wide CI grep.
  - **No retry on programmer errors**: a synthetic `TypeError` from the runner propagates as-is (not wrapped in PublisherGitError).
  - **Backoff respected**: monkeypatch `time.sleep` to record durations; confirm `[0.0, 2.0, 8.0]` schedule (or skip via autouse fixture in tests that don't care about timing).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 7: `publisher/__init__.py` public surface + integration smoke test

**Refs**: u3 hand-off notes from u2 summary.md (only `Briefing`, `DISCLAIMER`, `append_disclaimer` consumed; u4/u5 will consume u3's `write_briefing` + `commit_and_push`).

- [ ] **7.1** Finalize `src/investo/publisher/__init__.py`:
  - Re-export the public surface: `write_briefing`, `commit_and_push`, `verify_disclaimer`, `archive_path`, `ARCHIVE_ROOT`, plus the four error classes.
  - Module docstring documents what u5 orchestrator should call (`write_briefing` then `commit_and_push`) and the failure-mode contract (any raise = block subsequent stages).
- [ ] **7.2** `tests/integration/test_publisher_smoke.py` (~80 lines, 1 test):
  - Construct a valid `Briefing` (with DISCLAIMER) by hand.
  - Call `write_briefing(briefing, target_date)` — verify the archive file is written.
  - Call `commit_and_push(message="test", files=[path])` with a fake runner — verify the 3 git invocations fire correctly.
  - Confirm cross-unit imports work: u3 successfully imports `Briefing` from `investo.models` and `DISCLAIMER` from `investo.briefing.disclaimer`.
- [ ] **7.3** Public-surface pin test:
  - `tests/unit/publisher/test_public_surface.py` — assert `from investo.publisher import write_briefing, commit_and_push, verify_disclaimer, archive_path, ARCHIVE_ROOT, PublisherError, PublisherDisclaimerError, PublisherIOError, PublisherGitError` all succeed.
  - Locks against accidental removals from `__all__`.

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
