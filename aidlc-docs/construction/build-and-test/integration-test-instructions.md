# Integration Test Instructions

**Project**: Investo
**Date**: 2026-05-04
**Test scope**: cross-unit interactions; complete pipeline end-to-end with all external dependencies mocked.

---

## Purpose

Integration tests verify that the 6 units work together correctly under the documented Q9=B Error Policy routing — without requiring real external infrastructure (no real `claude` CLI, no real httpx network, no real git push, no real Telegram). Existing per-unit unit tests already pin each unit's internal contract; integration tests verify the **cross-unit boundaries**.

The project ships **4 integration test files** in `tests/integration/`:

| File | Scope | Test count |
|------|-------|-----------:|
| `test_briefing_pipeline_poc.py` | u1 → u2 cross-unit (FOMC RSS → generate_briefing) | 1 |
| `test_publisher_smoke.py` | u3 internal end-to-end (write + commit + push) | 3 |
| `test_notifier_smoke.py` | u4 internal end-to-end (BriefingPublisher + OperatorAlerter dispatch) | 4 |
| `test_pipeline.py` | u5 — **all 6 units wired simultaneously** (the project's primary integration test) | 7 |
| **Total** | | **15** |

---

## Test scenarios

### Scenario 1: u1 → u2 (`test_briefing_pipeline_poc.py`)

- **What**: FOMC RSS XML fixture → `FomcRssAdapter.fetch` → `list[NormalizedItem]` → `generate_briefing` → validated `Briefing`.
- **Setup**: pre-recorded XML fixture at `tests/unit/sources/fixtures/api/fomc-rss/feed.xml`. `httpx.MockTransport` returns the fixture body.
- **u2 LLM stub**: `monkeypatch.setattr(pipeline, "call_claude_code", fake_call)` returns canned Stage 1 + Stage 2 stdouts. NOT the FakeClaudeRunner replay path; this is a simpler stub for the cross-unit smoke.
- **Pins**: AC-4.4 (DISCLAIMER substring in `rendered_markdown`); AC-7.5 (no `<script>` substring in rendered markdown).
- **Expected**: `Briefing` instance with all 7 sections non-blank + disclaimer appended.

### Scenarios 2-4: u3 publisher (`test_publisher_smoke.py`)

- **What**: `write_briefing(briefing, target_date)` + `commit_and_push(message, files)` end-to-end.
- **Setup**: `monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")` redirects writes off the real repo. Fake `GitRunner` Protocol records subprocess calls.
- **Pins**: NFR-004 disclaimer hard-block (verify-first; nothing on disk on missing disclaimer); FR-006 atomic markdown write; FR-006 same-day overwrite; commit message format `briefing: YYYY-MM-DD`.

### Scenarios 5-8: u4 notifier (`test_notifier_smoke.py`)

- **What**: `BriefingPublisher.send` + `OperatorAlerter.alert` against shared `httpx.AsyncClient` with `MockTransport`.
- **Setup**: per-test handler routes by `chat_id` so a single mock can serve both dispatchers.
- **Pins**: end-to-end public dispatch (chat_id matches `_PUBLIC_CHANNEL`); operator dispatch (chat_id matches `_OPERATOR_CHAT`); CLAUDE.md #5 chat_id-separation invariant (publish + alert against same MockTransport → assert never swapped); public-surface importability.

### Scenarios 9-15: u5 orchestrator full pipeline (`test_pipeline.py`)

This is the project's primary integration test. **All 4 mock patterns wired simultaneously**:

| Layer | Mock | Purpose |
|-------|------|---------|
| u1 | Fake `fetch` callable | Returns pre-built `list[NormalizedItem]` |
| u2 | `monkeypatch` of `call_claude_code` | Canned Stage 1 + Stage 2 stdouts; **drives the real `generate_briefing`** so u2's prompt parsing + disclaimer + leak guard are exercised |
| u3 | `ARCHIVE_ROOT` to `tmp_path` + fake `GitRunner` | Real `write_briefing` writes the markdown; git lifecycle is faked |
| u4 | Single shared `httpx.AsyncClient(transport=MockTransport)` | Per-test handler routes by `chat_id` (public vs operator) |

**7 scenarios pinned**:

1. **Happy path** (`test_pipeline_end_to_end_success`) — SUCCESS, all 4 stage_timings populated, file on disk with disclaimer (verified by reading `archive_path(target_date)`), git add/commit/push sequence, public-channel send with per-day URL footer, NO operator alert.
2. **Empty collect** (`test_pipeline_end_to_end_empty_collect_alerts_operator`) — FAILED + 1 operator alert (chat_id verified to be operator-not-public); u2/u3/public never invoked.
3. **Notify failure** (`test_pipeline_end_to_end_notify_failure_yields_partial`) — Telegram `{"ok":false}` → PARTIAL + briefing_url set + NO operator alert + file on disk + git lifecycle ran.
4. **Chat-ID isolation invariant** (`test_pipeline_chat_id_separation_on_failure_path`) — empty-collect failure → assert `chat_ids_seen == [_OPERATOR_CHAT]`; public channel never receives anything (CLAUDE.md #5 cross-class pin at the integration boundary).
5. **Public-surface importability** (`test_orchestrator_public_surface_is_importable`) — 4 names resolve from `investo.orchestrator`; internal `_stage_*` NOT exposed; `main` NOT re-exported (lives in `__main__`); `__all__` exact set check.
6. **Imports correct types** (`test_orchestrator_imports_have_correct_types`) — `callable`, `RuntimeError` subclass checks.
7. **`resolve_target_date` round-trip via re-export** (`test_resolve_target_date_via_public_surface_returns_weekday`) — guard against accidental shadowing in `__init__`.

---

## Setup integration test environment

No external services required. Only Python + the dev extras:

```bash
uv sync --extra dev
```

All integration tests run from a clean checkout in <1 second.

---

## Run integration tests

### 1. Execute integration suite

```bash
uv run pytest tests/integration/ -v
```

Expected output:

```
tests/integration/test_briefing_pipeline_poc.py::test_full_pipeline_poc_against_recorded_fomc_fixture PASSED
tests/integration/test_notifier_smoke.py::test_briefing_publisher_end_to_end PASSED
tests/integration/test_notifier_smoke.py::test_operator_alerter_end_to_end PASSED
tests/integration/test_notifier_smoke.py::test_chat_id_separation_invariant PASSED
tests/integration/test_notifier_smoke.py::test_public_surface_is_importable PASSED
tests/integration/test_pipeline.py::test_pipeline_end_to_end_success PASSED
tests/integration/test_pipeline.py::test_pipeline_end_to_end_empty_collect_alerts_operator PASSED
tests/integration/test_pipeline.py::test_pipeline_end_to_end_notify_failure_yields_partial PASSED
tests/integration/test_pipeline.py::test_pipeline_chat_id_separation_on_failure_path PASSED
tests/integration/test_pipeline.py::test_orchestrator_public_surface_is_importable PASSED
tests/integration/test_pipeline.py::test_orchestrator_imports_have_correct_types PASSED
tests/integration/test_pipeline.py::test_resolve_target_date_via_public_surface_returns_weekday PASSED
tests/integration/test_publisher_smoke.py::... (3 tests) PASSED
============= 15 passed in ~0.6s =============
```

### 2. Run a single integration scenario

```bash
uv run pytest tests/integration/test_pipeline.py::test_pipeline_end_to_end_success -v
```

### 3. Cleanup

No cleanup required — all tests use `tmp_path` (auto-cleaned by pytest) and `monkeypatch` (auto-restored).

---

## Q9=B Error Policy coverage

The `test_pipeline.py::test_pipeline_end_to_end_*` family covers the most operationally-relevant rows of the Q9=B Error Policy table (defined in `aidlc-docs/inception/application-design/application-design.md`):

| Failure row | Integration test |
|-------------|------------------|
| Per-source collect failure → SUCCESS (graceful) | covered indirectly by happy path (u1's aggregator already swallows source-fetch errors per its unit tests) |
| Empty collect → operator alert + FAILED | `test_pipeline_end_to_end_empty_collect_alerts_operator` |
| BGE → operator alert + FAILED | covered by u5 unit `test_run_pipeline_generate_failure_fails_with_alert` (4-parametrized over 4 BGE stages); not duplicated at integration level |
| Publisher errors → operator alert + FAILED | covered by u5 unit `test_run_pipeline_publisher_*_fails_with_alert`; not duplicated at integration level |
| Notify failure → PARTIAL (no alert) | `test_pipeline_end_to_end_notify_failure_yields_partial` |
| Top-level Exception → main() alert + exit 1 | covered by u5 unit `test_main_top_level_exception_attempts_alert_and_exits_1` |

The integration tests pin the **operator-visible cross-unit flows** (happy path; empty-collect alert routing; PARTIAL detection; chat-ID isolation); the deeper Q9=B routing matrix is exhaustively covered at the u5 unit level (32 tests in `test_run_pipeline.py`).

---

## What integration tests do NOT cover (operational only)

- Real `claude` CLI subprocess invocation (covered by FakeClaudeRunner record/replay; live mode requires `INVESTO_LIVE_LLM=1` + `claude` binary; not in CI).
- Real Telegram Bot API delivery (covered by `httpx.MockTransport`; first verifiable in production with operator's actual bot + chat IDs).
- Real `git push` to GitHub (covered by fake `GitRunner` Protocol; first verifiable when the daily-briefing workflow runs in CI).
- GitHub Actions workflow YAML execution (verified by GHA's parser at push time + first cron fire; `mkdocs build --strict` is locally verifiable).
