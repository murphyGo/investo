# Technical Debt Registry

## Summary

| Priority | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 5 | 2026-04-27 |
| Low | 14 | 2026-04-27 |

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

#### DEBT-028: `raw_metadata` numeric serialization is inconsistent across u1 adapters

- **Created**: 2026-05-01
- **Source**: Cross-cutting sub-agent code review of u1 sources extension Step 5.7 (M1)
- **Reference**: NFR-005 (consistency across symmetric components), R8 (NormalizedItem field rules), R9 (idempotence)
- **Description**: The 3 new u1 adapters use 3 different float-to-string idioms for `NormalizedItem.raw_metadata` values:
  - `yfinance.py` — `f"{value:.4f}"` for OHLC, `str(int)` for volume
  - `coingecko.py` — `f"{price:.6f}"` / `f"{pct:.6f}"` for prices+pct, `f"{value:.2f}"` for volume/market_cap
  - `fred.py` — `f"{value}"` (bare repr; depends on Python's float-to-str default)
  Two issues compound: (a) the bare `f"{value}"` in FRED can drift between Python releases or with payload type (`f"{1.0}"` → `"1.0"` vs `f"{1}"` → `"1"`); (b) cross-adapter, identical numerics serialize to different strings (e.g., `1.5` becomes `"1.5000"` in yfinance, `"1.500000"` in coingecko, `"1.5"` in fred). R9 (idempotence — same source state → equal items) is technically satisfied within each adapter but the cross-adapter inconsistency means u2's downstream prompt sees jagged data.
- **Suggested Fix**: Add a `_format_numeric()` helper to `src/investo/sources/_config.py` (or a new `_format.py` if scope grows): `format_float(v) -> str` (fixed precision, e.g. 6 decimals), `format_int(v) -> str`. Update all 3 adapters to call the helpers. Bonus: the helper becomes the canonical place to add NaN/inf handling if a future adapter needs it.
- **Effort**: ~30 min including helper + 3 adapter call-site updates + test fixture string updates (the existing tests pin exact strings like `"272.255"` / `"4.1"` and would need adjustment).
- **Priority Reasoning**: Medium — not breaking anything today (each adapter's tests pass with their own format), but will surface as soon as a 4th adapter author has to choose between the 3 existing styles, OR when u2 starts grouping items by category and the cross-adapter inconsistency becomes visible in the LLM prompt. Address before the next adapter lands.

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

#### DEBT-017: `_TRACEBACK_EXCERPT_MAX_CHARS` duplicated between `pipeline.py` and `models/results.py`

- **Created**: 2026-04-30
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L1)
- **Reference**: NFR-005 (maintainability — DRY constants across module boundaries)
- **Description**: `pipeline.py` carries `_TRACEBACK_EXCERPT_MAX_CHARS = 2000`; `models/results.py` carries `_TRACEBACK_EXCERPT_MAX = 2000`. Both must agree or `FailureContext` construction in the orchestrator's catch site will start raising `ValidationError` — the exact bug `_truncate_excerpt` exists to prevent.
- **Suggested Fix**: Promote one to a public constant (e.g., `FailureContext.MAX_TRACEBACK_EXCERPT` class-attr or module-level `TRACEBACK_EXCERPT_MAX`) and import it in `pipeline.py`. Trivial.
- **Effort**: ~5 min.
- **Priority Reasoning**: Low — both values are 2000 and there's no current change pressure on either; but the next person who tweaks one will cause an obscure failure if they miss the other.

#### DEBT-018: AST-grep deny tests use substring matching instead of callable identity

- **Created**: 2026-04-30
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L4)
- **Reference**: NFR-006 (test robustness)
- **Description**: `tests/unit/orchestrator/test_run_pipeline.py`'s 3 AST-grep deny tests (AC-001-3 / AC-001-5 / AC-003-11) use `"_stage_"` substring matching against `ast.unparse` output. If a future refactor renames `_stage_collect` → `_collect_stage`, the deny tests silently pass on a real violation. Robust today; brittle to refactoring.
- **Suggested Fix**: Replace substring match with callable-identity match: walk the AST for `ast.Name(id in {"_stage_collect", "_stage_generate", "_stage_publish", "_stage_notify_briefing"})`. The whitelist becomes the contract — adding a new stage runner without updating it is the new failure mode (which is fine; deliberate).
- **Effort**: ~20 min.
- **Priority Reasoning**: Low — current tests work; future-proofing only.

#### DEBT-019: `resolve_target_date` PBT covers only 2026

- **Created**: 2026-04-30
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L5)
- **Reference**: NFR-006 (PBT coverage breadth)
- **Description**: `tests/unit/orchestrator/test_date_resolution.py`'s 2 hypothesis PBTs use `min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31, 23, 59)`. Leap-year edges (2024, 2028, 2032) and additional year-boundary crossings (e.g. KST 2027-01-01 cron firing for 2026-12-31) are unverified.
- **Suggested Fix**: Widen the strategy to span 2024–2030 (or wider). KST has been fixed UTC+9 since 1988 so historical years are safe; future bound limited only by reasonable cron lifetimes.
- **Effort**: ~5 min (one-line bounds change).
- **Priority Reasoning**: Low — date math is mechanical; PBT primarily catches strategy bugs, not algorithm bugs.

#### DEBT-020: `_safe_alert` and `_attempt_boot_alert` exception lists not aligned

- **Created**: 2026-04-30
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L6 — partially resolved by H1 fix)
- **Reference**: NFR-005 (consistency across symmetric helpers)
- **Description**: H1 broadened `_safe_alert` to `except Exception`. `_attempt_boot_alert` in `__main__.py:171` still uses the narrower `except (OSError, RuntimeError, httpx.HTTPError)`. Symmetric helpers should have symmetric semantics.
- **Suggested Fix**: Broaden `_attempt_boot_alert`'s `except` to `Exception` for the same reason `_safe_alert` was broadened — programmer errors / pydantic ValidationError / future u4-contract changes should never mask the underlying exit code. Test `test_main_alert_construction_failure_silenced` already exercises one of these paths but more coverage would be welcome.
- **Effort**: ~5 min for the change + ~10 min for parametrized tests.
- **Priority Reasoning**: Low — the boot path is rarely exercised + the existing `(OSError, RuntimeError, httpx.HTTPError)` covers the realistic transport failure modes. Pure consistency tightening.

#### DEBT-021: Unused `PublisherError` re-export in `pipeline.__all__`

- **Created**: 2026-04-30
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L2)
- **Reference**: NFR-005 (no dead code)
- **Description**: `src/investo/orchestrator/pipeline.py:__all__` re-exports `"PublisherError"` with a comment claiming "the orchestrator's main module imports the umbrella ``PublisherError`` for top-level catch." But `__main__.py` does not import `PublisherError` — it catches `Exception`. So this re-export is unused.
- **Suggested Fix**: Drop `"PublisherError"` from `pipeline.__all__`. One-line change.
- **Effort**: ~2 min.
- **Priority Reasoning**: Low — dead code, but not load-bearing on anything.

#### DEBT-022: `pages.yml` permissions set at workflow level instead of job level

- **Created**: 2026-05-01
- **Source**: Step 6 sub-agent code review of u6 infra/CI (M2)
- **Reference**: NFR-007 (least-privilege secrets / permissions handling)
- **Description**: `.github/workflows/pages.yml` declares `permissions: { pages: write, id-token: write, contents: read }` at workflow level (lines 48-51). This grants `pages: write` and `id-token: write` to BOTH the `build` and `deploy` jobs — but `build` only needs `contents: read` (it uploads a workflow artifact, not a Pages deploy). The `deploy` job is the only one that talks to GHA Pages.
- **Suggested Fix**: Move to job-level: `build: { permissions: contents: read }`, `deploy: { permissions: pages: write, id-token: write }`. Tightens least-privilege without changing functionality.
- **Effort**: ~5 min YAML edit.
- **Priority Reasoning**: Low — the runner is already trusted (1-person repo); cosmetic least-privilege improvement.

#### DEBT-023: `daily-briefing.yml` installs `--extra dev` but never runs pytest

- **Created**: 2026-05-01
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L7)
- **Reference**: NFR-001 (cron run wall-clock budget)
- **Description**: `.github/workflows/daily-briefing.yml:104` step "Install project (runtime + dev for pytest sanity)" runs `uv sync --extra dev`, pulling pytest / hypothesis / ruff / mypy / types-* into the runner. The job only invokes `python -m investo` — it does NOT run any test or lint command. The dev extras are dead weight on the cold-start install (~10-15s per run × 6 fires/week).
- **Suggested Fix**: Switch to `uv sync --no-dev` (or just `uv sync` without any `--extra`, since runtime deps are in `[project] dependencies` not in `dev`). Update the step name + comment to "Install project (runtime only)".
- **Effort**: ~5 min YAML edit + visual verification on the next workflow run.
- **Priority Reasoning**: Low — saves ~60-90s/week of GHA minutes; the 10-min budget per run has plenty of margin so this isn't blocking AC-001-1.

#### DEBT-024: `astral-sh/setup-uv@v3` not pinned to a SHA in either workflow

- **Created**: 2026-05-01
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L4)
- **Reference**: NFR-007 baseline (supply-chain hygiene)
- **Description**: Both `.github/workflows/daily-briefing.yml:95` and `pages.yml:72` use `astral-sh/setup-uv@v3` — major-version pin. A compromised v3 release could exfiltrate the 5 GitHub Secrets injected via `env:`. For a 1-person tool with no untrusted contributors the supply-chain risk is minimal, but pinning to a SHA per the canonical GitHub-recommended pattern would tighten the boundary.
- **Suggested Fix**: Replace both `@v3` references with `@<full-sha>`. Add a Dependabot config (`.github/dependabot.yml`) so the SHA stays current.
- **Effort**: ~15 min including Dependabot setup.
- **Priority Reasoning**: Low — see "1-person tool" above. Re-evaluate if the project ever onboards external contributors or stores higher-value secrets.

#### DEBT-025: `ConfigError.missing_vars` overloaded for "malformed value" case

- **Created**: 2026-05-01
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L6 — surfaced by the INVESTO_TARGET_DATE side-quest)
- **Reference**: NFR-005 (clarity / discriminator integrity)
- **Description**: `_resolve_target_date_override()` raises `ConfigError("...not a valid ISO-8601 date...", missing_vars=("INVESTO_TARGET_DATE",))`. The `missing_vars` field is documented as "names of required env vars absent" — but `INVESTO_TARGET_DATE` is *present but malformed*, not missing. The current overload works (alert text remains actionable, exit code is correct) but blurs the original 2-mode discriminator (empty tuple ⇒ chat-ID-equality; non-empty tuple ⇒ missing-var). A 3rd mode now exists implicitly: non-empty tuple AND var IS present.
- **Suggested Fix**: Either (a) add `bad_value_var: str | None = None` field to `ConfigError` and a 3rd factory `ConfigError.for_bad_target_date(raw)`, or (b) rename the field to something neutral like `affected_vars` and document the 3 modes explicitly.
- **Effort**: ~20 min including factory + tests.
- **Priority Reasoning**: Low — operator alert text remains correct; this is internal cleanliness. Re-evaluate if a 4th mode appears (e.g., a future override env var with its own validation).

#### DEBT-026: `archive/.gitkeep` redundant once `archive/index.md` exists

- **Created**: 2026-05-01
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L3)
- **Reference**: NFR-005 (no dead files)
- **Description**: `archive/.gitkeep` was created in Step 4 to ensure the directory exists in git before the daily-briefing bot's first write. `archive/index.md` (the placeholder landing page) already keeps the directory tracked, so `.gitkeep` is redundant.
- **Suggested Fix**: `git rm archive/.gitkeep`. One-line change.
- **Effort**: ~1 min.
- **Priority Reasoning**: Low — harmless artifact; remove during the next u6 cleanup pass.

#### DEBT-027: Windows checkout symlink limitation undocumented

- **Created**: 2026-05-01
- **Source**: Step 6 sub-agent code review of u6 infra/CI (Q9)
- **Reference**: NFR-005 (cross-platform clarity)
- **Description**: `site_docs/archive` is a git symlink (mode 120000) → `../archive`. Linux runners (GHA `ubuntu-latest`) and macOS dev environments handle it natively. Windows checkouts require `core.symlinks=true` AND either developer mode enabled OR admin privileges. Investo runs on Linux only (GHA + macOS-dev), so this is fine in practice; if a Windows contributor ever appears they'll see the symlink as a regular file containing the literal text `../archive`.
- **Suggested Fix**: Add a "Cross-platform notes" section to CONTRIBUTING.md documenting the symlink limitation, OR migrate to a non-symlink solution (e.g., mkdocs-monorepo-plugin or post-build copy). Re-evaluate when a Windows contributor surfaces.
- **Effort**: ~10 min docs edit; ~1 hour for full migration.
- **Priority Reasoning**: Low — Investo is a 1-person Linux/macOS tool; Windows is hypothetical.

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

#### DEBT-029: SEC URL-constant placement diverges from sibling adapters

- **Created**: 2026-05-01
- **Source**: Phase 3 cross-cutting qa review of u1 sources Extension #2 (M1)
- **Reference**: NFR-005 (consistency across symmetric components), R2 (plugin module shape)
- **Description**: 5 of 6 registered adapters declare their endpoint URL as a class-level `ClassVar[str]` (`fomc_rss._FEED_URL`, `yfinance._BASE_URL`, `coingecko._ENDPOINT`, `fred._ENDPOINT`, `yahoo_finance_news._FEED_URL`). The 6th — `sec_edgar_8k._FEED_URL` — uses module-level `Final[str]`. No test or import requires the module-level position; appears to be authoring-order accident. The cross-adapter inconsistency means the next adapter author has to choose between two precedents.
- **Suggested Fix**: Move `sec_edgar_8k._FEED_URL` (and `_USER_AGENT` for symmetry, since they're both endpoint-config) to class-level `ClassVar` on `SecEdgar8kAdapter`. Optionally add a passive consistency test in `test_plugin_contract.py` that asserts each registered adapter class has a `ClassVar[str]` whose name matches a known set (`{"_FEED_URL", "_BASE_URL", "_ENDPOINT"}` — or pick one canonical name and migrate all 6).
- **Effort**: ~5 min code move (sec_edgar_8k only); ~30 min if also adding the consistency test + migrating the field name across all 6 adapters.
- **Priority Reasoning**: Low — purely cosmetic, no behavior impact, no test pressure. Address in a future cleanup pass.

---

#### DEBT-030: SEC accession-number extraction uses regex on summary instead of canonical `<id>`

- **Created**: 2026-05-01
- **Source**: Phase 3 cross-cutting qa review of u1 sources Extension #2 (M2 / Developer self-flag #2)
- **Reference**: R8 (NormalizedItem field rules — `raw_metadata` provenance), R10 (test fixtures)
- **Description**: `sec_edgar_8k.py` extracts `raw_metadata["accession_no"]` by regex (`r"AccNo:\s*(\S+)"`) on the HTML-stripped summary text. SEC's Atom feed also exposes the accession number canonically in the entry's `<id>` element (e.g. `urn:tag:sec.gov,2008:accession-number=0001193125-26-197921`). The regex path works on every entry in the recorded fixture (40/40), but would silently break if SEC ever reflows the summary HTML; the `<id>` parse would be format-stable. Today's tests (`test_fetch_accession_no_extracted`, `test_no_item_codes_emits_entry_with_empty_items`) cover the current regex path.
- **Suggested Fix**: Switch to `entry.find(f"{_ATOM_NS}id").text` parsing during the next fixture re-record. Strip the `urn:tag:sec.gov,2008:accession-number=` prefix; assert the remaining substring matches `r"^\d{10}-\d{2}-\d{6}$"`. The regex on summary becomes the fallback if `<id>` is missing (defensive).
- **Effort**: ~15 min code change + 1 test update + re-record fixture (or use synthetic Atom for the test).
- **Priority Reasoning**: Low — current path works on the recorded fixture; future SEC schema change is hypothetical. Address during the next re-record pass (project-wide re-record cadence is also unpinned — a separate concern the lead can re-dispatch later).

---

## Resolved Items

_No resolved items yet._

---

*Managed by `/tech-debt` skill. Run `/tech-debt add` to add new items.*
