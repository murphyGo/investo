# u3 publisher — Code Generation Summary

**Date**: 2026-04-30
**Stage**: Code Generation (final stage for u3 publisher; FD + NFR Requirements both SKIP per execution-plan)
**Status**: ✅ COMPLETE
**Stories closed**: US-003 (정적 게시), US-006 (영구 이력 보관)

---

## Files created

### Source code (`src/investo/publisher/`)

| File | LOC | Role |
|------|----:|------|
| `__init__.py` | 75 | Public surface — 9 re-exports + module docstring (Step 7) |
| `errors.py` | 143 | 4-class hierarchy w/ 1024-byte UTF-8 stderr cap (Step 2) |
| `paths.py` | 47 | `ARCHIVE_ROOT` + pure `archive_path(date) -> Path` (Step 3) |
| `verifier.py` | 41 | Pure `verify_disclaimer(md) -> bool` substring check (Step 4) |
| `writer.py` | 79 | Atomic markdown write w/ verify-first ordering (Step 5) |
| `git_ops.py` | 196 | `commit_and_push` w/ whole-pipeline retry + idempotent-commit detection (Steps 6 + 8 H1 fix) |
| **Total** | **581** | 6 source files |

### Tests (`tests/unit/publisher/` + `tests/integration/`)

| File | LOC | Tests | Role |
|------|----:|------:|------|
| `__init__.py` | 0 | 0 | Empty marker (Step 1) |
| `conftest.py` | 6 | 0 | Placeholder docstring (Step 1) |
| `test_errors.py` | 217 | 20 | 4-class inheritance + field round-trip + 1024-byte truncation (Step 2) |
| `test_paths.py` | 130 | 12 | Happy + boundary + purity + monkeypatch redirection (Step 3) |
| `test_verifier.py` | 123 | 9 | Substring + negative cases + cross-unit AST-grep boundary pin (Step 4) |
| `test_writer.py` | 307 | 11 | Happy + NFR-004 block + atomicity + mkdir + stale-tmp + verify-first (Step 5) |
| `test_git_ops.py` | 409 | 15 | Happy + retry + exhaustion + list-form pin + backoff + H1 partial-success (Step 6 + Step 8 H1 fix) |
| `tests/integration/test_publisher_smoke.py` | 142 | 3 | End-to-end write→commit/push + public-surface + cross-unit alignment (Step 7) |
| **Total** | **1,334** | **70** | 7 test files (6 unit + 1 integration) |

### Surface area

| Public re-export | Defined in | Consumed by |
|------------------|------------|-------------|
| `write_briefing(briefing, target_date) -> Path` | `writer.py` | u5 orchestrator |
| `commit_and_push(message, files, *, retries=2, runner=None)` | `git_ops.py` | u5 orchestrator |
| `verify_disclaimer(md) -> bool` | `verifier.py` | u5 orchestrator (debugging / pre-flight check); u3-internal at `write_briefing` boundary |
| `archive_path(date) -> Path`, `ARCHIVE_ROOT` | `paths.py` | u5 orchestrator (path inspection); u3-internal at `write_briefing` |
| `GitRunner` Protocol | `git_ops.py` | Test seam — u5 may inject a fake in integration tests |
| `PublisherError`, `PublisherDisclaimerError`, `PublisherIOError`, `PublisherGitError` | `errors.py` | u5 orchestrator stage guard (3-class taxonomy: Disclaimer / IO / Git) |

### Cross-unit imports (module-boundary)

u3 imports ONLY from:
- `investo.models.Briefing` (re-exported via `investo.models`) — the consumer shape.
- `investo.briefing.disclaimer.DISCLAIMER` — canonical anchor for `verify_disclaimer`.

u3 does NOT import any other u2 symbol — `pipeline`, `claude_code`, `prompts`, `briefing.errors`, `leak_guard`, `RetryBudget`, `BriefingGenerationError` — those are u5 orchestrator concerns. Verified by `grep -rn "from investo" src/investo/publisher/` (only `investo.models` + `investo.briefing.disclaimer` + intra-`investo.publisher.*`).

---

## FR / NFR traceability

| AC | Description | Pinned by |
|----|-------------|-----------|
| FR-003 markdown to git repo | `write_briefing` → atomic write to `archive/YYYY/MM/YYYY-MM-DD.md` | `test_writer.py::test_write_briefing_writes_markdown_to_archive_path` |
| FR-003 git-repo lifecycle | `commit_and_push` adds + commits + pushes via subprocess | `test_git_ops.py::test_commit_and_push_happy_path_runs_three_steps_in_order` + integration smoke |
| FR-006 directory contract | `archive_path(date)` → `archive/YYYY/MM/YYYY-MM-DD.md` | `test_paths.py::test_archive_path_typical_date` (+ 11 boundary cases) |
| FR-006 same-day re-run | `write_briefing` overwrites (no in-place backup; git history retains versions) | `test_writer.py::test_write_briefing_same_day_overwrites_previous` |
| NFR-004 disclaimer hard block | `write_briefing` calls `verify_disclaimer` FIRST; raises `PublisherDisclaimerError` w/ no write on failure | `test_writer.py::test_write_briefing_blocks_when_disclaimer_missing` + `test_write_briefing_verify_runs_before_mkdir` |
| NFR-004 verifier substring | `verify_disclaimer(md)` checks exact-substring of `DISCLAIMER` | `test_verifier.py` (9 tests) + integration smoke |
| NFR-007 AC-7.1 list-form subprocess | `git_ops.py` uses list form, no `shell=True` | `test_git_ops.py::test_git_ops_module_uses_only_list_form_subprocess` (AST-stripped) + repo-wide CI grep `scripts/check_no_anthropic_sdk.py` |
| NFR-003 retry on transient failure | `commit_and_push` retries up to `retries+1=3` attempts w/ backoff `(0, 2, 8)` | `test_git_ops.py::test_commit_and_push_retries_on_transient_push_failure` + `test_commit_and_push_handles_partial_success_on_retry` |
| Atomic-write contract (FR-006 reliability) | tmp + `os.replace` — destination unchanged on failure | `test_writer.py::test_write_briefing_atomicity_does_not_leave_destination_corrupted` |
| 1024-byte stderr cap (mirrors u2 AC-7.4) | `PublisherGitError.last_stderr` truncated UTF-8 byte-safe | `test_errors.py` (4 boundary tests) + `test_git_ops.py::test_commit_and_push_truncates_long_stderr_to_1024_bytes` |

u3 has no NFR Requirements file (skipped per execution-plan); the AC table above is a synthesis of the relevant FRs + the NFRs that touch the publisher boundary.

---

## Open TECH-DEBT items

### From u3 (new this stage)

| ID | Priority | Source step | Description |
|----|----------|-------------|-------------|
| DEBT-012 | Medium | Step 8 review | `_truncate_stderr` byte-identical between u2 + u3 errors modules |
| DEBT-013 | Low | Step 8 review | u3 publisher test `_build_briefing` fixture duplicated across writer + smoke tests |

### Cross-unit / pre-existing (unchanged)

| ID | Priority | Origin |
|----|----------|--------|
| DEBT-001 | Medium | models step 3 |
| DEBT-002 | Medium | models step 3 |
| DEBT-007 | Medium | u2 step 8.5 |
| DEBT-006 / 008 / 009 / 010 / 011 | Low | u2 |
| DEBT-003 / 004 / 005 | Low | u1 |

None block u3. 2 of 13 open items originated in u3; 6 from u2; 3 from u1; 2 cross-unit (models).

---

## FD-vs-implementation divergences (ratified in audit log)

Three structural deviations or ratified fixes landed during u3:

1. **Step 5.3** — `paths.ARCHIVE_ROOT` redirection design decision. Plan offered two options: (a) per-test `monkeypatch.setattr` vs (b) explicit `archive_root` parameter. Ratified (a) for v1 — minimal API surface, matches u1's `_isolate_registry` autouse-fixture pattern. Promote to (b) only if u5 orchestrator surfaces a real need to pass a non-default root.

2. **Step 7.3** — public-surface pin test. Plan called for a separate `tests/unit/publisher/test_public_surface.py`. Folded into the integration smoke test's `test_publisher_public_surface_is_importable` to avoid a 1-test file with overlapping coverage. Single home (smoke test) is cleaner.

3. **Step 8 H1 — `commit_and_push` partial-success retry**. Sub-agent code review caught a real correctness bug: when attempt 1 succeeds at add+commit but fails at push, attempt 2's `git commit` returns rc=1 with "nothing to commit, working tree clean" because the prior commit absorbed the staged changes. Original code treated this as failure and exhausted the budget, raising `PublisherGitError` with a misleading "publish failed entirely" signal. Fixed via `_is_idempotent_commit_noop(result)` detector — rc=1 + "nothing to commit" substring (case-insensitive, both stdout AND stderr per git-version variance) → no-op success, loop proceeds to push. 3 new regression tests pin the corrected behavior + a non-regression check that legitimate commit failures (rc=1 with `pathspec did not match`) still raise. The plan's "whole-pipeline retry" claim was correct on the absence-of-divergent-history side but wrong about returncode handling on idempotent re-commits.

All three ratified in `aidlc-docs/audit.md`. No cross-unit contract was broken.

---

## Story status

- ✅ **US-003** (정적 게시) — closed by `write_briefing` (atomic markdown write to `archive/YYYY/MM/YYYY-MM-DD.md`) + `commit_and_push` (git lifecycle). The orchestrator (u5) wires these together in sequence.
- ✅ **US-006** (영구 이력 보관) — closed by the FR-006 directory contract (`archive_path`) + `commit_and_push`'s git push to remote. Git history retains every version of every briefing markdown forever (until the operator manually rebases or filters).

---

## Pre-flight notes for u4 notifier

`u4 notifier` is the next unit. It will consume the following stable surface from `investo.models` (and indirectly from u2's briefing render):

| Symbol | Defined in | What u4 needs it for |
|--------|------------|----------------------|
| `Briefing` | `investo.models.briefing` | The shape u4's Telegram payload builder consumes. `rendered_markdown` is the source of the public-channel message body; `target_date` is the message anchor. |
| `BriefingNotification` | `investo.models.briefing` | u4 builds these (4096-char Telegram-message-bounded summaries) — the model already enforces the limit at construction time. |

**u4 does NOT import any u3 symbol** — `write_briefing`, `commit_and_push`, `verify_disclaimer`, etc. are not u4's concern. u4 takes a `Briefing` (already verified + written by the orchestrator) and produces a Telegram-bounded summary message + sends to two separate channels (public `BriefingPublisher` vs operator 1:1 `OperatorAlerter` per FR-004 / FR-007 / NFR module-boundary rule).

### What u4 should be aware of from u3

- u3's failure-mode taxonomy (`PublisherDisclaimerError` / `PublisherIOError` / `PublisherGitError`) is what u5 orchestrator catches at the publish stage. **u4's `OperatorAlerter` will receive those errors via the orchestrator** — u4 is responsible for formatting them into the operator's 1:1 chat. The 3-class names + `target_date` + `last_stderr` (1024-byte truncated) fields are designed for direct interpolation into operator alert messages.
- `PublisherGitError.last_stderr` is already 1024-byte UTF-8 byte-truncated at construction time. u4 may surface it directly in the operator alert without re-truncation.
- The 1024-byte cap matches u2's `BriefingGenerationError.last_stderr` (NFR-007 AC-7.4) — uniform across both error families. DEBT-012 tracks the eventual consolidation of the underlying `_truncate_stderr` helper.

---

## Quality gate (final, Step 9 closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ |
| `mypy --strict src/` | ✅ (28 source files: 7 models + 8 sources + 7 briefing + 6 publisher) |
| `pytest` | ✅ **500/500** passing (252 u1+models baseline + 178 u2 briefing + 70 u3 publisher = 500 total) |

Test breakdown for u3: 20 errors + 12 paths + 9 verifier + 11 writer + 15 git_ops + 3 integration smoke = **70 tests**.

---

## Next stage gate

`u3 publisher` Code Generation is now CLOSED. The unit becomes eligible for `/cross-check` against requirements. Three stage gates remain for the project:

1. `u4 notifier` Code Generation (per `aidlc-docs/inception/plans/execution-plan.md`; FD/NFR SKIP)
2. `u5 orchestrator` Code Generation (the integration glue; FD/NFR SKIP)
3. `u6 infra/CI` (YAML/config only — Code Generation but no FD/NFR)

Then global `Build and Test` after every unit's CG completes.
