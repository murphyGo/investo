# Technical Debt Registry

## Summary

| Priority | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 4 | 2026-04-27 |
| Low | 12 | 2026-04-27 |

---

## Active Items

### Critical Priority

_No critical items._

### High Priority

_No high priority items._

### Medium Priority

#### DEBT-001: `Briefing` model lacks `disclaimer ∈ rendered_markdown` invariant

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3)
- **Reference**: NFR-004 (compliance / disclaimer enforcement)
- **Description**: The `Briefing` pydantic model permits a state where `disclaimer` text is not actually present in `rendered_markdown`. Today the only enforcement is `publisher.verify_disclaimer` (called pre-publish). Defense-in-depth would shift the guarantee one layer earlier — into the data model — so the bug class becomes impossible by construction.
- **Suggested Fix**: Add a `model_validator(mode="after")` on `Briefing` that asserts `self.disclaimer.strip() in self.rendered_markdown`. Trade-off: rejects ambiguous test fixtures that pass section text without re-running the rendering pipeline. Either weaken the check (substring of the disclaimer's first line) or update fixtures to always pass full rendered markdown.
- **Effort**: ~30 min including fixing fixtures
- **Priority Reasoning**: Medium — not yet a real bug because the publisher guard exists, but if anyone ever bypasses the publisher path (e.g., direct unit-tests, future replays, ADR'd alternate flow), the guard disappears.

#### DEBT-002: No date sanity bounds on `target_date` / `published_at` (project-wide)

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3); same pattern in `items.py`
- **Reference**: US-005 (scheduled execution), FR-006 (archival)
- **Description**: `Briefing.target_date`, `BriefingNotification.target_date`, and `NormalizedItem.published_at` accept any valid date — including far-future (`date(2206, 4, 27)`) or pre-epoch values. A typo upstream would commit nonsensical archive paths or stamp items with bad timestamps.
- **Suggested Fix**: Add sanity bounds at the **orchestrator** boundary (`resolve_target_date`) rather than in the models, since the models are also used in historical replays where wider bounds may be needed. Concrete check: `2024-01-01 ≤ target_date ≤ today + 1`. For Source Adapters, reject items whose `published_at` is more than 30 days in the future.
- **Effort**: ~15 min in u5 orchestrator; ~10 min in u1 sources base.
- **Priority Reasoning**: Medium — defensive only; would catch upstream typos but does not currently block any real flow.

#### DEBT-007: No byte-exact JSON snapshot test for `serialize_items_for_prompt`

- **Created**: 2026-04-29
- **Source**: Step 8.5 sub-agent code review (L4 / Q4) of `pipeline.py`
- **Reference**: AC-6.2 (serialize round-trip), `tests/_helpers/fake_claude_runner.py` (FakeClaudeRunner uses `sha256(prompt)[:16]` as fixture key)
- **Description**: `serialize_items_for_prompt` produces a JSON string that downstream becomes part of the Stage 1 prompt; that prompt is then SHA-256'd to derive the FakeClaudeRunner fixture key. The serializer is *deterministic in practice* (Python ≥3.7 dict insertion order; explicit field order in the dict literal; `astimezone(UTC).isoformat()` always emits `+00:00`) but no test pins the byte-exact JSON output. A future refactor that, e.g., switches to `json.dumps(payload, sort_keys=True)` or reorders keys would silently invalidate every recorded LLM fixture and break replay.
- **Suggested Fix**: Add a snapshot test in `test_pipeline_unit.py` that constructs a known `NormalizedItem` and asserts the exact bytes returned by `serialize_items_for_prompt([item])`. Pin both the key order (`{"id": 1, "category": ..., "source": ..., "title": ..., "summary": ..., "url": ..., "ts": ...}`) and the timestamp format (`"+00:00"` not `"Z"`). The PBT shape test does NOT cover this — it only checks the key set, not the order or whitespace.
- **Effort**: ~15 min including a 2-3 line test addition.
- **Priority Reasoning**: Medium — the determinism assumption is currently correct but undocumented; the FakeClaudeRunner architecture depends on it. Cheap to pin.

#### DEBT-012: `_truncate_stderr` helper duplicated across u2 + u3 errors modules

- **Created**: 2026-04-30
- **Source**: Step 8 sub-agent code review of u3 publisher (M1 finding)
- **Reference**: NFR-006 (test-suite/source maintainability); NFR-007 AC-7.4 (1024-byte stderr cap)
- **Description**: `_STDERR_BYTE_CAP: Final[int] = 1024` constant + `_truncate_stderr(value: str | None) -> str | None` helper appear byte-identically in `src/investo/briefing/errors.py` and `src/investo/publisher/errors.py`. u4 notifier will likely need the same cap when bounding error-text payloads to Telegram. Three copies risks silent drift if one site changes the cap value or the `errors="ignore"` decode strategy.
- **Suggested Fix**: Lift to a shared internal module — `src/investo/_internal/text.py` (new) or extend `src/investo/models/_validators.py`. Both u2 + u3 errors modules import from there. u4 notifier picks it up at construction time.
- **Effort**: ~20 min including import updates and verifying both unit's truncation tests still pass.
- **Priority Reasoning**: Medium — promotes to High when u4 introduces a third copy. Address before u4 starts to avoid the third-copy problem.

### Low Priority

#### DEBT-003: `retry_get` 5 MB body cap is post-hoc, not streaming

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/sources/_retry.py` (Step 3)
- **Reference**: NFR-007 AC-7.1 (5 MB response body cap)
- **Description**: `retry_get` checks `len(response.content) > max_response_bytes` after `httpx.AsyncClient.get()` has already buffered the full body into memory. A hostile server returning a 100 MB payload would briefly hold 100 MB resident before the cap fires. Acceptable for v1 because the only adapter (FOMC RSS, Step 8) returns < 200 KB; would matter if a future adapter pulled larger feeds or hit a hostile endpoint.
- **Suggested Fix**: Switch to `client.stream("GET", url)` and (a) reject up-front if `Content-Length` header exceeds the cap, (b) accumulate via `aiter_bytes()` and abort once the running total exceeds the cap. Trade-off: streaming requires constructing a synthetic `httpx.Response` to return, since downstream callers expect a fully-buffered response.
- **Effort**: ~1 hour including test updates (need a streaming MockTransport response).
- **Priority Reasoning**: Low — the threat is "hostile server returning huge body", which is unlikely against the curated free-tier endpoints `u1` consumes. Re-evaluate when a non-RSS adapter (e.g. JSON market data) lands.

#### DEBT-004: `_sanitize.py` depends on `bleach` (maintenance-mode)

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/sources/_sanitize.py` (Step 4)
- **Reference**: NFR-007 AC-7.2 (sanitization library)
- **Description**: `bleach>=6` is in maintenance-only mode and the maintainers have publicly recommended `nh3` (Rust-based, actively maintained) as the successor. Today bleach 6 is correct and behaves as we expect; the risk is future EOL or accumulating `DeprecationWarning`s from the underlying `html5lib`.
- **Suggested Fix**: When bleach hits EOL, replace `bleach.clean(text, tags=[], strip=True, strip_comments=True)` with `nh3.clean_text(text)` (or `nh3.clean(text, tags=set())` for HTML output). Single-function module makes the migration trivial. Update the pipeline so HTML entities still decode and whitespace still collapses.
- **Effort**: ~30 min including test updates and verifying nh3 entity-decoding behavior.
- **Priority Reasoning**: Low — the project's only sanitization need is plain-text output; bleach 6 is fine for v1. Watch for EOL announcements or CI deprecation warnings.

#### DEBT-006: `call_claude_code` cancellation does not stop the worker thread

- **Created**: 2026-04-29
- **Source**: Code review of `src/investo/briefing/claude_code.py` (Step 6 sub-agent M1)
- **Reference**: NFR-001 (≤10 min), NFR-003 (graceful degradation); FD R3 (per-call timeout)
- **Description**: `call_claude_code` uses `asyncio.to_thread(subprocess.run, ...)`. If the awaiting coroutine is cancelled (e.g. an upstream `asyncio.wait_for` enforces a stricter deadline than the per-call timeout), the `CancelledError` propagates to the awaiter but the inner thread continues running until `subprocess.run`'s own `timeout=` fires. During that window, the spawned `claude` child process is still alive. For u2's bounded use (per-call ≤120 s), this is acceptable — the kernel reaps the child when `subprocess.run` raises `TimeoutExpired` inside the orphaned thread — but it could matter when u5 orchestrator wraps `generate_briefing` in its own `wait_for`.
- **Suggested Fix**: Switch to `asyncio.create_subprocess_exec("claude", "-p", prompt, stdout=PIPE, stderr=PIPE)` for true async cancellation (sends SIGTERM/SIGKILL to the child on cancellation). Trade-off: changes the runner-seam Protocol shape (no more `subprocess.run` signature compatibility); `FakeClaudeRunner` would need a parallel async-mode entry point. Defer until u5 orchestrator's `wait_for` wrapping is finalized.
- **Effort**: ~2 hours including FakeClaudeRunner refactor + test migration.
- **Priority Reasoning**: Low — orchestrator does not currently wrap `call_claude_code` in `wait_for` (the per-call timeout is enforced by `subprocess.run` itself, not asyncio). When u5 lands and the wrapping pattern is concrete, re-evaluate; if u5 takes the simpler "no outer wait_for, trust the inner timeout" path, this can be closed without action.

#### DEBT-008: `_parse_classification` does not catch `RecursionError` on adversarial JSON

- **Created**: 2026-04-29
- **Source**: Step 8.5 sub-agent code review (M2 / Q5) of `pipeline.py`
- **Reference**: AC-3.2 (failure contract — BGE wraps LLM-traceable failures), AC-3.4 (programmer errors propagate as-is)
- **Description**: `_parse_classification` calls `json.loads(stdout)` on raw LLM stdout. Default Python `json.loads` raises `RecursionError` (verified) at JSON nesting depth >~1000. `_classify`'s except clause catches `(json.JSONDecodeError, ValidationError, ValueError)` — `RecursionError` is NOT caught and propagates uncaught from `generate_briefing`, bypassing the BGE failure contract. The contract says LLM-traceable failures map to BGE; a recursion-bomb in stdout is logically an LLM failure, not a programmer error.
- **Suggested Fix**: Either (a) add a cheap `len(stdout) > 64 * 1024` upper-bound check before `json.loads` and route over-cap to retry as a malformed response, or (b) add `RecursionError` to the except tuple in `_classify`. (a) is more defensible — bounds the bytes you parse, not just the failure mode.
- **Effort**: ~15 min including unit test.
- **Priority Reasoning**: Low — Claude does not emit deeply-nested JSON in normal operation, and even if it did the failure surface is "uncaught exception in production" rather than data loss or security. Defense-in-depth, not a hot bug.

#### DEBT-010: u2 briefing test helpers duplicated across 4 files

- **Created**: 2026-04-30
- **Source**: Step 9.5 sub-agent code review (L1 / Q8)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `_valid_classification_stdout(item_count)` is copied across `tests/unit/briefing/test_failure_contract.py`, `test_budget_happy_path.py`, `test_budget_guard.py`, and `tests/integration/test_briefing_pipeline_poc.py` (4 files). `_valid_stage2_markdown()` is duplicated in 2 of those files with subtle Korean-prose variation that's irrelevant to the assertions. The autouse `_zero_backoff` fixture appears in `test_failure_contract.py` and `test_budget_guard.py`. `tests/unit/briefing/conftest.py` is already a placeholder for shared fixtures. Risk: divergence over time as one site updates a helper for a new test concern and the others lag.
- **Suggested Fix**: Consolidate into `tests/unit/briefing/conftest.py` (already declared as the home for shared fixtures). Move `_valid_classification_stdout`, `_valid_stage2_markdown`, and the `_zero_backoff` autouse fixture there. Integration test under `tests/integration/` would either re-import via `from tests.unit.briefing.conftest import ...` or have its own thin shim.
- **Effort**: ~30 min including import updates and verifying no new fixture-name collisions.
- **Priority Reasoning**: Low — defensive duplication, all 11 Step 9 tests pass, no functional risk. Best addressed in a post-Step-10 cleanup pass to avoid merge churn against ongoing work.

#### DEBT-011: Integration PoC bypasses `aggregator.fetch_all`

- **Created**: 2026-04-30
- **Source**: Step 9.5 sub-agent code review (M2 / Q4)
- **Reference**: u1 R6 (failure isolation), u1 L5 (warning-log contract), FD L9 (PoC integration scope)
- **Description**: `tests/integration/test_briefing_pipeline_poc.py` calls `FomcRssAdapter().fetch(client, window)` directly via `httpx.MockTransport`, bypassing `investo.sources.fetch_all`. Consequences: (a) the aggregator's `gather(return_exceptions=True)` failure-isolation contract is not exercised end-to-end — covered only by u1's unit tests; (b) registry-driven adapter discovery is bypassed; (c) the warning-log behavior on adapter failures is not cross-unit-pinned. Today FomcRss is the only registered adapter so the impact is minimal, but this is a brittle assumption that widens silently as u1 grows.
- **Suggested Fix**: Once a second u1 adapter exists (e.g., a price feed or earnings calendar), upgrade the integration test to call `fetch_all(target_date)` and use `monkeypatch` to control adapter responses (one returns FOMC fixture data, one raises `SourceFetchError`). Verify the failed adapter contributes `[]` and the briefing still generates from the remaining items.
- **Effort**: ~45 min including the second-adapter mock setup. Cannot land before u1 has a second adapter.
- **Priority Reasoning**: Low — the contract being uncovered is u1's, which has its own unit tests. The integration test still exercises u1→u2 wiring for the only adapter that currently exists. Re-evaluate when a second adapter is added.

#### DEBT-013: u3 publisher test `_build_briefing` fixture duplicated

- **Created**: 2026-04-30
- **Source**: Step 8 sub-agent code review of u3 publisher (M3 finding)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `_build_briefing()` helper lives in both `tests/unit/publisher/test_writer.py` and `tests/integration/test_publisher_smoke.py`. Sibling-shape with DEBT-010 (u2 test helper duplication). Will recur when u4 notifier + u5 orchestrator need a `Briefing` fixture.
- **Suggested Fix**: Lift to a shared `tests/_fixtures/briefings.py` (or extend `tests/_helpers/`) so both unit + integration tests can import. Bundling with DEBT-010's resolution is reasonable since both target test-helper consolidation.
- **Effort**: ~20 min. Could be folded into DEBT-010's resolution PR.
- **Priority Reasoning**: Low — defensive duplication, all tests pass, no functional risk. Address alongside DEBT-010 in a post-u3 cleanup pass.

#### DEBT-014: u4 BriefingPublisher uses `parse_mode="Markdown"` without escape fallback

- **Created**: 2026-04-30
- **Source**: Step 7 sub-agent code review of u4 notifier (L3 / TD-N01)
- **Reference**: FR-004 (Telegram channel), NFR-003 (graceful degradation)
- **Description**: `BriefingPublisher.send` and `OperatorAlerter.alert` both pass `parse_mode="Markdown"` to the Telegram API. If the LLM-generated `briefing.market_summary` (or formatted alert text) contains an unbalanced `*` or `_`, or unescaped `[`, Telegram returns 400 with `"can't parse entities..."` which we encode as `SendResult(ok=False)`. The pipeline degrades gracefully — but the public-channel publish silently fails until an operator notices. The current prompt template doesn't specifically instruct the LLM to avoid Markdown footguns.
- **Suggested Fix**: One of (in order of effort):
  1. Document the failure mode in the prompt template (cheapest).
  2. Add a `parse_mode=None` retry in `BriefingPublisher.send` when the API returns "can't parse entities" — the briefing publishes as plain text instead of failing.
  3. Switch to `parse_mode="MarkdownV2"` and escape the body with a vetted helper (heaviest; loses some readability).
- **Effort**: Option 2 ~1 hour including tests; option 1 trivial; option 3 ~3 hours.
- **Priority Reasoning**: Low — graceful-degradation already covers the failure (operator alert fires when the publish step's `SendResult.ok=False` lands). No silent data loss. Re-evaluate when the first real Markdown-parse failure occurs in production.

#### DEBT-015: `_TrackingClient` test pattern fragile to httpx version changes

- **Created**: 2026-04-30
- **Source**: Step 7 sub-agent code review of u4 notifier (L1 / TD-N03)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `tests/unit/notifier/test_briefing_publisher.py::test_briefing_publisher_creates_default_client_when_http_none` subclasses `httpx.AsyncClient` and overrides `__init__(self, **kwargs)` then forwards via `super().__init__(**kwargs)`. This assumes httpx's signature stays compatible — if a future httpx adds a positional-only param or renames a kwarg, the test silently breaks (or worse, masks a real production breakage on httpx upgrade).
- **Suggested Fix**: Replace with a factory-mock pattern. Patch `httpx.AsyncClient` in the briefing_publisher module to a `MagicMock` that returns a pre-configured `MockTransport`-backed client. Capture construction args via the mock's `call_args`. Less coupled to httpx internals.
- **Effort**: ~30 min including verifying the new test still pins the timeout=30.0 contract.
- **Priority Reasoning**: Low — works today; only matters at httpx upgrade time.

#### DEBT-016: `_mock_client` test helper duplicated across 3 u4 test files

- **Created**: 2026-04-30
- **Source**: Step 7 sub-agent code review of u4 notifier (L5 / TD-N04)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: Three near-identical `_mock_client(handler)` helpers in `test_telegram.py`, `test_briefing_publisher.py`, `test_operator_alerter.py`. `tests/unit/notifier/conftest.py` exists as a placeholder explicitly waiting for shared fixtures. Sibling-shape with DEBT-010 (u2 test helper duplication) and DEBT-013 (u3 test helper duplication).
- **Suggested Fix**: Move `_mock_client` to `tests/unit/notifier/conftest.py` as a fixture or module-level helper, then import from each test file. Could be folded into the existing DEBT-010 / DEBT-013 cleanup pass.
- **Effort**: ~10 min.
- **Priority Reasoning**: Low — defensive duplication, all tests pass, no functional risk.

#### DEBT-009: `_executable_source` AST helper is duplicated across two test files

- **Created**: 2026-04-29
- **Source**: Step 8.5 sub-agent code review (L1 / Q8); also flagged in the Step 8.4 docstring
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: The `_executable_source(module)` helper (AST round-trip that strips module + class + function docstrings) appears verbatim in `tests/unit/briefing/test_claude_code.py` and `tests/unit/briefing/test_pipeline_no_prompt_strings.py`. Both copies are ~25 lines. A future fix (e.g., handling decorated functions, async vs sync function defs) needs to land in two places.
- **Suggested Fix**: Move to `tests/_helpers/ast_helpers.py` (the helpers package already exists per `tests/_helpers/fake_claude_runner.py`). Both call sites import as `from tests._helpers.ast_helpers import executable_source`.
- **Effort**: ~10 min including import updates.
- **Priority Reasoning**: Low — the duplication is small and stable. The helper is unlikely to need refactoring in v1.

---

#### DEBT-005: Aggregator log line is printf-style, not structured

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/sources/aggregator.py` (Step 7)
- **Reference**: FD `business-logic-model.md` L5 (logging contract — "structured fields"), NFR-007 baseline
- **Description**: `_logger.warning("source %s failed: %s (transient=%s)", ...)` is a printf approximation of L5's structured-fields requirement (`source_name`, `category`, `error`, `transient`). It's grep-friendly but not JSON-parseable. The rest of the codebase has no structured-logging convention yet (NFR AC-D.4 explicitly defers metrics + structured logs to v2 / future ADR).
- **Suggested Fix**: When the project adopts structured logging (likely as part of an operations ADR), migrate to `_logger.warning("source failed", extra={"source_name": ..., "transient": ..., "category": ..., "error": str(result)})`. Update any test that assert on log message format.
- **Effort**: ~30 min including test updates and verifying the chosen logging adapter (stdlib logging + JSON formatter, structlog, etc.).
- **Priority Reasoning**: Low — printf logs are fine for a 1-person operator using `journalctl` / `gh actions logs`. Re-evaluate when remote log aggregation enters the picture.

---

## Resolved Items

_No resolved items yet._

---

*Managed by `/tech-debt` skill. Run `/tech-debt add` to add new items.*
