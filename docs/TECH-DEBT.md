# Technical Debt Registry

## Summary

| Priority | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 4 | 2026-05-07 |
| Low | 6 | 2026-04-27 |

---

## Active Items

### Critical Priority

_No critical items._

### High Priority

_No high priority items._

### Medium Priority

#### DEBT-040: Layout reposition ordering when multiple non-hero cards share the same anchor

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (M3)
- **Reference**: NFR-005 (consistency / contract integrity), NFR-006 (test robustness), FR-003 (static web publishing)
- **Description**: `_reposition_visual_links` in `src/investo/visuals/assets.py` reinserts non-hero cards via `lines[insert_at:insert_at] = […]`. When two or more non-hero asset paths anchor to the same H2 (e.g., two cards both flagged for `① 요약`), the inserts happen in `asset_paths` reverse order, so the rendered layout sees the cards in the opposite order from the iteration order. The ordering intent (intentional reverse vs. accidental) is not documented and no test pins it. A future contributor adding a third non-hero card to the same anchor will land an unintended layout reshuffle.
- **Suggested Fix**: Either (a) introduce a stable secondary sort key when collecting per-anchor inserts, e.g. `(anchor_line, -original_index)` to make the inversion explicit, or (b) keep the current `lines[insert_at:insert_at]` shape but document the inversion in a docstring on `_reposition_visual_links` plus add a test that pins layout order for ≥ 2 non-hero cards at the same anchor.
- **Effort**: ~30 min including the chosen fix + test.
- **Priority Reasoning**: Medium — works correctly today on the observed segment shapes (≤ 1 non-hero card per anchor), but is the kind of regression that escapes review when a fourth card type lands.

#### DEBT-041: `_provenance_caption_for` swallows the pydantic `ValueError` from corrupt sidecars

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (M4)
- **Reference**: NFR-003 (graceful degradation), NFR-007 (R13 — secret hygiene), FR-002 (Korean briefing comprehension)
- **Description**: `_provenance_caption_for` in `src/investo/visuals/assets.py` reads the `<asset>.json` sidecar and constructs a `VisualProvenanceManifest` to choose a Korean caption. If the sidecar JSON is corrupt or schema-violating, the pydantic `ValidationError` (a `ValueError` subclass) is swallowed and the function returns `None`, which renders an image without a caption. Today, `prepare_segment_visual_assets` writes manifests atomically and validates them at write time, so the corrupt-sidecar case is not reachable through the supported call path. However, any future call site that bypasses `prepare_segment_visual_assets` (e.g., a one-off backfill script that copies pre-existing assets) can produce captionless images while looking syntactically correct.
- **Suggested Fix**: Either (a) move sidecar validation **before** caption rendering inside `_provenance_caption_for` so corrupt sidecars raise `VisualAssetError` (re-using the existing publish-side fallback), or (b) re-raise as `VisualAssetError` from inside `_provenance_caption_for`, or (c) add an explicit `validate_sidecar_or_raise(asset_path)` helper and require every caller (including future ones) to invoke it before captioning.
- **Effort**: ~25 min including a test that pins the corrupt-sidecar rejection path.
- **Priority Reasoning**: Medium — not reachable through today's supported call path, but the silent fall-through is a degradation in observability and could mask malformed sidecars produced by future tooling.

#### DEBT-042: Sanitizer policy unification across coverage / provenance / leak-guard

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (L2)
- **Reference**: NFR-005 (consistency across symmetric components), NFR-007 (R8 / R13 — secret hygiene)
- **Description**: `sanitize_source_error_message` (from u22) now has 3 call-site locations — the coverage badge, the new visual provenance sanitizer, and `__main__._redact_diagnostic_text` (per DEBT-035). On top of those, `briefing.leak_guard` carries its own pattern set with a different policy. As more reader-/operator-facing surfaces are added (e.g., a future "operator step summary" card or a watchlist export), the patterns can drift across these four sites and a future redaction site could land copy #5. Extends DEBT-035 / DEBT-036 — those address `__main__` ↔ `coverage` drift; this one widens the scope to include `provenance` and `leak_guard`.
- **Suggested Fix**: Define a single named policy object (e.g., `RedactionPolicy.PUBLIC_OUTPUT` and `RedactionPolicy.LLM_OUTPUT`) in a shared `src/investo/_internal/redaction.py` module that exposes `redact(text: str, policy: RedactionPolicy) -> str`. Each existing call site passes the appropriate policy. Pin via a regression test that imports the module and asserts every redaction site uses one of the named policies.
- **Effort**: ~1 hour including the shared module + 4 call-site updates + tests. Larger scope than DEBT-035 alone.
- **Priority Reasoning**: Medium — the threat is policy drift across 4 surfaces with overlapping but non-identical pattern sets. Cheap to consolidate before a 5th site lands.

#### DEBT-038: `source_outcomes` segment-filtering contract is not enforced at the type level

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L4)
- **Reference**: NFR-005 (consistency / contract integrity), NFR-006 (test robustness), FR-008 (segmented briefing)
- **Description**: `build_segment_coverage(...)` in `src/investo/briefing/segments.py` accepts `Sequence[SourceOutcome]` for the segment's source results. The function trusts the caller to have already filtered outcomes to the current segment (orchestrator does this today), but the type signature is identical to a "global outcomes list", so a future refactor could silently feed cross-segment outcomes — leaking another segment's source statuses into a segment's data-confidence card or markdown reason callout.
- **Suggested Fix**: Introduce a `SegmentScopedOutcomes = NewType("SegmentScopedOutcomes", tuple[SourceOutcome, ...])` and have the orchestrator construct it via a small validating builder that asserts every outcome's category belongs to the segment's allowed categories. Alternatively, add a runtime guard inside `build_segment_coverage` that raises if any outcome category is not in the segment's allow-list.
- **Effort**: ~45 min including builder + orchestrator/test updates.
- **Priority Reasoning**: Medium — the orchestrator currently filters correctly, but the contract is invisible to mypy and would be the kind of regression that escapes review. Cheap to harden once and prevents a class of cross-segment data-leak bugs.

### Low Priority

#### DEBT-043: External image fetch builder bypass risk in `VisualProvenanceManifest`

- **Created**: 2026-05-07
- **Source**: u24 visual-provenance-and-layout QA review (L3)
- **Reference**: NFR-007 (R8 / R13 — secret hygiene), NFR-002 (no paid APIs / contract-only external image schema)
- **Description**: `build_external_provenance` in `src/investo/visuals/provenance.py` is the single sanitize hook for the `external_image` source type today. The model's `field_validator("source_attribution", "generator", "version")` does run `sanitize_provenance_text` on construction, so direct `VisualProvenanceManifest.model_validate({...source_type: "external_image"...})` calls are still sanitized. The risk is that as the field set grows (a new `crawl_target_url`, `image_alt_text`, etc.), a future contributor may add a field that needs sanitization but only update `build_external_provenance`, leaving `model_validate` callers with the unsanitized field. Today the model fields are exhaustively listed in the validator tuple, but the convention is brittle.
- **Suggested Fix**: Either (a) add a `model_validator(mode="after")` that asserts every string-typed user-/operator-derived field went through `sanitize_provenance_text` (e.g., by re-running it and comparing), or (b) document the rule in a docstring on `VisualProvenanceManifest` and add a test that walks all string-typed fields via `model_fields` and pins each one through `sanitize_provenance_text`. Option (b) is cheaper and equally robust.
- **Effort**: ~20 min for option (b).
- **Priority Reasoning**: Low — `model_validate` bypass is contract-only today (no caller exists), and the existing tuple-form `field_validator` covers every current field. The threat is field-set growth, not current behaviour.

#### DEBT-035: Bot-token / chat-id redaction regex duplicated across `__main__` and `models/coverage`

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L1)
- **Reference**: NFR-007 (R13 — no secret values in logs / errors / raw_metadata / fixtures), NFR-005 (DRY constants across module boundaries)
- **Description**: Two redaction regexes for the bot-token / chat-id shape live in two places with **non-identical** patterns:
  - `src/investo/__main__.py::_redact_diagnostic_text` uses `\b\d{6,}:[A-Za-z0-9_-]{20,}\b`.
  - `src/investo/models/coverage.py::sanitize_source_error_message` uses `(?<![\d:])\d{6,}:[A-Za-z0-9_-]{20,}(?![\w-])`.
  The patterns differ on word-boundary handling (lookaround vs `\b`), so a borderline payload could be redacted by one site and not the other. Both layers exist in the public output path (Step Summary diagnostics + reader-facing source coverage), so silent drift on the redaction shape directly threatens R13.
- **Suggested Fix**: Extract a shared helper module (e.g. `src/investo/_internal/redaction.py`) exporting `BOT_TOKEN_PATTERN`, `CHAT_ID_PATTERN`, and a `redact_secret_shapes(text: str) -> str` function. Both `__main__._redact_diagnostic_text` and `sanitize_source_error_message` call it. Pin the patterns in one place with regression tests for both call sites.
- **Effort**: ~30 min including the shared module + 2 call-site updates + tests.
- **Priority Reasoning**: Low — both patterns work correctly today on the observed shapes; the threat is pattern drift across future edits. Cheap to consolidate before another redaction site lands.

#### DEBT-036: `_SECRET_ENV_VARS` set is wider than the `__main__._redact_diagnostic_text` literal list

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L2)
- **Reference**: NFR-007 (R13 — secret hygiene), NFR-005 (consistency)
- **Description**: `_SECRET_ENV_VARS` covers 6 env vars (the canonical secret list), but `__main__._redact_diagnostic_text`'s in-line redacted-name set covers only 4. When a future contributor adds a new secret env var (e.g. an additional Telegram channel token, a new GH PAT), they may register it in `_SECRET_ENV_VARS` and forget to add it to `_redact_diagnostic_text`'s literal list, leaving Step Summary output exposed.
- **Suggested Fix**: Make `_redact_diagnostic_text` iterate over `_SECRET_ENV_VARS` (or a curated subset) at runtime instead of a hard-coded literal list. Single source of truth for "names whose values must be scrubbed."
- **Effort**: ~15 min including a regression test that adds a synthetic env var to `_SECRET_ENV_VARS` and asserts redaction.
- **Priority Reasoning**: Low — current 6-vs-4 set is intentional today, but the duplication is a foot-gun for new-secret onboarding.

#### DEBT-037: `_render_source_rows` silently truncates after 4 rows in SVG only

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L3)
- **Reference**: NFR-005 (UX consistency between markdown and visual artefacts)
- **Description**: `src/investo/visuals/render.py::_render_source_rows` caps SVG source-row rendering at 4 entries and silently drops the rest. The corresponding markdown callout (in `src/investo/briefing/pipeline.py`) lists every source. When 5+ adapters fail in a segment, the SVG quietly hides the tail while markdown shows the full picture. Cosmetic today (the most-failed segment in tests has ≤4 sources), but a reader using only the SVG (e.g. on a device where the markdown is collapsed) misses information.
- **Suggested Fix**: Either (a) widen the SVG to render up to 8 rows with a smaller font, (b) render the first N and append a `+M more` row when truncated, or (c) accept the cap and document it in `_render_source_rows`'s docstring with a `# truncated to keep first-viewport height` comment.
- **Effort**: ~25 min for option (b) including a test that pins the `+M more` row.
- **Priority Reasoning**: Low — markdown already carries the full information; this is a visual completeness improvement, not a correctness bug.

#### DEBT-039: `CoverageReasonCode` Literal and `COVERAGE_REASON_LABELS` keys not pinned in sync by mypy

- **Created**: 2026-05-07
- **Source**: u22 source-coverage-transparency QA review (L7)
- **Reference**: NFR-005 (consistency), NFR-006 (test robustness)
- **Description**: `CoverageReasonCode` is a `Literal[...]` of allowed reason-code strings, and `COVERAGE_REASON_LABELS: dict[CoverageReasonCode, str]` carries the Korean label for each. Adding a new reason code to the Literal without adding its label to the dict raises only at runtime (when the missing key is first looked up), not at type-check time. Conversely, dropping a code from the Literal while leaving the dict entry behind passes mypy.
- **Suggested Fix**: Either (a) add an `assert_never` branch in the labelling helper so an unhandled code raises at typecheck time, (b) add a runtime assertion at module import that `set(COVERAGE_REASON_LABELS.keys()) == set(get_args(CoverageReasonCode))`, or (c) replace the Literal + dict pair with a `StrEnum` whose members carry their Korean label as a class attribute.
- **Effort**: ~20 min for option (b); ~45 min for option (c) including downstream call-site updates.
- **Priority Reasoning**: Low — the pair is in sync today and the test suite indirectly covers every label via existing reason-callout assertions; this is contract hardening for future edits.

#### DEBT-004: `_sanitize.py` depends on `bleach` (maintenance-mode)

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/sources/_sanitize.py` (Step 4)
- **Reference**: NFR-007 AC-7.2 (sanitization library)
- **Description**: `bleach>=6` is in maintenance-only mode and the maintainers have publicly recommended `nh3` (Rust-based, actively maintained) as the successor. Today bleach 6 is correct and behaves as we expect; the risk is future EOL or accumulating `DeprecationWarning`s from the underlying `html5lib`.
- **Suggested Fix**: When bleach hits EOL, replace `bleach.clean(text, tags=[], strip=True, strip_comments=True)` with `nh3.clean_text(text)` (or `nh3.clean(text, tags=set())` for HTML output). Single-function module makes the migration trivial. Update the pipeline so HTML entities still decode and whitespace still collapses.
- **Effort**: ~30 min including test updates and verifying nh3 entity-decoding behavior.
- **Priority Reasoning**: Low — the project's only sanitization need is plain-text output; bleach 6 is fine for v1. Watch for EOL announcements or CI deprecation warnings.

---

## Resolved Items

#### DEBT-024: `astral-sh/setup-uv@v3` not pinned to a SHA in either workflow

- **Created**: 2026-05-01
- **Resolved**: 2026-05-04 — Replaced both `astral-sh/setup-uv@v3` workflow references with the peeled `v3` commit SHA `caf0cab7a618c569241d31dcd442f54681755d39` and kept a `# v3` trailing comment for reviewability. Added `.github/dependabot.yml` with weekly `github-actions` updates so action pins stay visible and maintainable.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L4)
- **Reference**: NFR-007 baseline (supply-chain hygiene)
- **Description**: Both `.github/workflows/daily-briefing.yml:95` and `pages.yml:72` use `astral-sh/setup-uv@v3` — major-version pin. A compromised v3 release could exfiltrate the 5 GitHub Secrets injected via `env:`. For a 1-person tool with no untrusted contributors the supply-chain risk is minimal, but pinning to a SHA per the canonical GitHub-recommended pattern would tighten the boundary.
- **Suggested Fix**: Replace both `@v3` references with `@<full-sha>`. Add a Dependabot config (`.github/dependabot.yml`) so the SHA stays current.
- **Effort**: ~15 min including Dependabot setup.
- **Priority Reasoning**: Low — see "1-person tool" above. Re-evaluate if the project ever onboards external contributors or stores higher-value secrets.

#### DEBT-006: `call_claude_code` cancellation does not stop the worker thread

- **Created**: 2026-04-29
- **Resolved**: 2026-05-04 — Closed after u5 orchestrator re-evaluation. `_stage_generate` awaits u2's async `generate_briefing` directly, `run_pipeline` does not wrap stage calls in `asyncio.wait_for`, and `tests/unit/orchestrator/test_run_pipeline.py::test_pipeline_source_has_no_asyncio_wait_for_on_stages` statically pins that contract. With no stricter outer cancellation wrapper around `call_claude_code`, the remaining `asyncio.to_thread(subprocess.run, timeout=...)` behavior is bounded by the existing per-call timeout and does not need the larger async-subprocess refactor.
- **Source**: Code review of `src/investo/briefing/claude_code.py` (Step 6 sub-agent M1)
- **Reference**: NFR-001 (≤10 min), NFR-003 (graceful degradation); FD R3 (per-call timeout)
- **Description**: `call_claude_code` uses `asyncio.to_thread(subprocess.run, ...)`. If the awaiting coroutine is cancelled (e.g. an upstream `asyncio.wait_for` enforces a stricter deadline than the per-call timeout), the `CancelledError` propagates to the awaiter but the inner thread continues running until `subprocess.run`'s own `timeout=` fires. During that window, the spawned `claude` child process is still alive. For u2's bounded use (per-call ≤120 s), this is acceptable — the kernel reaps the child when `subprocess.run` raises `TimeoutExpired` inside the orphaned thread — but it could matter when u5 orchestrator wraps `generate_briefing` in its own `wait_for`.
- **Suggested Fix**: Switch to `asyncio.create_subprocess_exec("claude", "-p", prompt, stdout=PIPE, stderr=PIPE)` for true async cancellation (sends SIGTERM/SIGKILL to the child on cancellation). Trade-off: changes the runner-seam Protocol shape (no more `subprocess.run` signature compatibility); `FakeClaudeRunner` would need a parallel async-mode entry point. Defer until u5 orchestrator's `wait_for` wrapping is finalized.
- **Effort**: ~2 hours including FakeClaudeRunner refactor + test migration.
- **Priority Reasoning**: Low — orchestrator does not currently wrap `call_claude_code` in `wait_for` (the per-call timeout is enforced by `subprocess.run` itself, not asyncio). When u5 lands and the wrapping pattern is concrete, re-evaluate; if u5 takes the simpler "no outer wait_for, trust the inner timeout" path, this can be closed without action.

#### DEBT-003: `retry_get` 5 MB body cap is post-hoc, not streaming

- **Created**: 2026-04-27
- **Resolved**: 2026-05-04 — Switched `retry_get` from `client.get()` to `client.stream("GET", ...)` for successful responses. The helper now rejects oversized `Content-Length` before reading the body, enforces the cap while accumulating `aiter_bytes()`, and returns a fully buffered synthetic `httpx.Response` so adapter callers keep the same surface. Added tests that prove the body is not read when `Content-Length` already exceeds the cap and that no-length streams abort once the running total crosses the cap.
- **Source**: Code review of `src/investo/sources/_retry.py` (Step 3)
- **Reference**: NFR-007 AC-7.1 (5 MB response body cap)
- **Description**: `retry_get` checks `len(response.content) > max_response_bytes` after `httpx.AsyncClient.get()` has already buffered the full body into memory. A hostile server returning a 100 MB payload would briefly hold 100 MB resident before the cap fires. Acceptable for v1 because the only adapter (FOMC RSS, Step 8) returns < 200 KB; would matter if a future adapter pulled larger feeds or hit a hostile endpoint.
- **Suggested Fix**: Switch to `client.stream("GET", url)` and (a) reject up-front if `Content-Length` header exceeds the cap, (b) accumulate via `aiter_bytes()` and abort once the running total exceeds the cap. Trade-off: streaming requires constructing a synthetic `httpx.Response` to return, since downstream callers expect a fully-buffered response.
- **Effort**: ~1 hour including test updates (need a streaming MockTransport response).
- **Priority Reasoning**: Low — the threat is "hostile server returning huge body", which is unlikely against the curated free-tier endpoints `u1` consumes. Re-evaluate when a non-RSS adapter (e.g. JSON market data) lands.

#### DEBT-005: Aggregator log line is printf-style, not structured

- **Created**: 2026-04-27
- **Resolved**: 2026-05-04 — Changed `fetch_all` source-failure logging to `_logger.warning("source failed", extra={...})` with `source_name`, `category`, `error`, and `transient` fields. The structured log keeps the existing debugging contract by using the `SourceFetchError` self-reported `source_name` while taking `category` from the registered adapter. Updated unit and integration assertions to inspect `LogRecord` fields instead of rendered printf text.
- **Source**: Code review of `src/investo/sources/aggregator.py` (Step 7)
- **Reference**: FD `business-logic-model.md` L5 (logging contract — "structured fields"), NFR-007 baseline
- **Description**: `_logger.warning("source %s failed: %s (transient=%s)", ...)` is a printf approximation of L5's structured-fields requirement (`source_name`, `category`, `error`, `transient`). It's grep-friendly but not JSON-parseable. The rest of the codebase has no structured-logging convention yet (NFR AC-D.4 explicitly defers metrics + structured logs to v2 / future ADR).
- **Suggested Fix**: When the project adopts structured logging (likely as part of an operations ADR), migrate to `_logger.warning("source failed", extra={"source_name": ..., "transient": ..., "category": ..., "error": str(result)})`. Update any test that assert on log message format.
- **Effort**: ~30 min including test updates and verifying the chosen logging adapter (stdlib logging + JSON formatter, structlog, etc.).
- **Priority Reasoning**: Low — printf logs are fine for a 1-person operator using `journalctl` / `gh actions logs`. Re-evaluate when remote log aggregation enters the picture.

#### DEBT-011: Integration PoC bypasses `aggregator.fetch_all`

- **Created**: 2026-04-30
- **Resolved**: 2026-05-04 — Updated `tests/integration/test_briefing_pipeline_poc.py` to call `aggregator.fetch_all(_TARGET_DATE)` with `aggregator.list_sources` patched to two controlled adapters: one wraps the recorded FOMC fixture through `FomcRssAdapter`, and one raises `SourceFetchError`. The test now pins registry-driven fan-out, failure isolation, warning-log behavior, and u1→u2 briefing generation in the same PoC.
- **Source**: Step 9.5 sub-agent code review (M2 / Q4)
- **Reference**: u1 R6 (failure isolation), u1 L5 (warning-log contract), FD L9 (PoC integration scope)
- **Description**: `tests/integration/test_briefing_pipeline_poc.py` calls `FomcRssAdapter().fetch(client, window)` directly via `httpx.MockTransport`, bypassing `investo.sources.fetch_all`. Consequences: (a) the aggregator's `gather(return_exceptions=True)` failure-isolation contract is not exercised end-to-end — covered only by u1's unit tests; (b) registry-driven adapter discovery is bypassed; (c) the warning-log behavior on adapter failures is not cross-unit-pinned. Today FomcRss is the only registered adapter so the impact is minimal, but this is a brittle assumption that widens silently as u1 grows.
- **Suggested Fix**: Once a second u1 adapter exists (e.g., a price feed or earnings calendar), upgrade the integration test to call `fetch_all(target_date)` and use `monkeypatch` to control adapter responses (one returns FOMC fixture data, one raises `SourceFetchError`). Verify the failed adapter contributes `[]` and the briefing still generates from the remaining items.
- **Effort**: ~45 min including the second-adapter mock setup. Cannot land before u1 has a second adapter.
- **Priority Reasoning**: Low — the contract being uncovered is u1's, which has its own unit tests. The integration test still exercises u1→u2 wiring for the only adapter that currently exists. Re-evaluate when a second adapter is added.

#### DEBT-014: u4 BriefingPublisher uses `parse_mode="Markdown"` without escape fallback

- **Created**: 2026-04-30
- **Resolved**: 2026-05-04 — `BriefingPublisher.send` now retries Telegram `"can't parse entities"` failures once with `parse_mode=None`, allowing malformed LLM Markdown to publish as plain text instead of failing the public-channel send. `_telegram.send_message` omits `parse_mode` when callers pass `None`, and unit tests pin both the retry and the no-retry behavior for unrelated API errors.
- **Source**: Step 7 sub-agent code review of u4 notifier (L3 / TD-N01)
- **Reference**: FR-004 (Telegram channel), NFR-003 (graceful degradation)
- **Description**: `BriefingPublisher.send` and `OperatorAlerter.alert` both pass `parse_mode="Markdown"` to the Telegram API. If the LLM-generated `briefing.market_summary` (or formatted alert text) contains an unbalanced `*` or `_`, or unescaped `[`, Telegram returns 400 with `"can't parse entities..."` which we encode as `SendResult(ok=False)`. The pipeline degrades gracefully — but the public-channel publish silently fails until an operator notices. The current prompt template doesn't specifically instruct the LLM to avoid Markdown footguns.
- **Suggested Fix**: One of (in order of effort):
  1. Document the failure mode in the prompt template (cheapest).
  2. Add a `parse_mode=None` retry in `BriefingPublisher.send` when the API returns "can't parse entities" — the briefing publishes as plain text instead of failing.
  3. Switch to `parse_mode="MarkdownV2"` and escape the body with a vetted helper (heaviest; loses some readability).
- **Effort**: Option 2 ~1 hour including tests; option 1 trivial; option 3 ~3 hours.
- **Priority Reasoning**: Low — graceful-degradation already covers the failure (operator alert fires when the publish step's `SendResult.ok=False` lands). No silent data loss. Re-evaluate when the first real Markdown-parse failure occurs in production.

#### DEBT-027: Windows checkout symlink limitation undocumented

- **Created**: 2026-05-01
- **Resolved**: 2026-05-04 — Added a `CONTRIBUTING.md` cross-platform note documenting the `site_docs/archive` symlink, the Windows `core.symlinks=true` plus Developer Mode/admin requirement, and the expected local MkDocs symptom when symlinks are checked out as plain text files.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (Q9)
- **Reference**: NFR-005 (cross-platform clarity)
- **Description**: `site_docs/archive` is a git symlink (mode 120000) → `../archive`. Linux runners (GHA `ubuntu-latest`) and macOS dev environments handle it natively. Windows checkouts require `core.symlinks=true` AND either developer mode enabled OR admin privileges. Investo runs on Linux only (GHA + macOS-dev), so this is fine in practice; if a Windows contributor ever appears they'll see the symlink as a regular file containing the literal text `../archive`.
- **Suggested Fix**: Add a "Cross-platform notes" section to CONTRIBUTING.md documenting the symlink limitation, OR migrate to a non-symlink solution (e.g., mkdocs-monorepo-plugin or post-build copy). Re-evaluate when a Windows contributor surfaces.
- **Effort**: ~10 min docs edit; ~1 hour for full migration.
- **Priority Reasoning**: Low — Investo is a 1-person Linux/macOS tool; Windows is hypothetical.

#### DEBT-034: `_mock_client` test helper duplicated across 5 news-adapter test files

- **Created**: 2026-05-01
- **Resolved**: 2026-05-04 — Added shared `tests/unit/sources/_mock_transport.py::mock_client()` for source adapter tests, including optional request capture for the SEC User-Agent pin. Updated Yahoo Finance, SEC EDGAR 8-K, Yonhap Market, The Block Crypto, and CNBC Top News tests to import the shared helper instead of carrying local `httpx.MockTransport` wrappers.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (L4)
- **Reference**: NFR-006 (test-suite/source maintainability)
- **Description**: A `_mock_client(body, status=200)` test helper appears in 5 news-adapter test files: `test_yahoo_finance_news.py`, `test_sec_edgar_8k.py`, `test_yonhap_market.py`, `test_theblock_crypto.py`, `test_cnbc_top_news.py`. The bodies differ only by content-type header value (`application/rss+xml` vs `application/atom+xml` vs `text/xml`); the SEC variant additionally captures the outgoing request to assert the User-Agent header (R14 test). Five copies of a small but non-trivial httpx `MockTransport`-wrapping helper — a clear consolidation target.
- **Suggested Fix**: Extract a shared `tests/unit/sources/_mock_transport.py` helper exporting `mock_client(body: bytes | str, status: int = 200, content_type: str = "application/rss+xml", capture_requests: bool = False)`. Returns `httpx.AsyncClient` plus optionally a `list[httpx.Request]` capture sink. Update all 5 test files to import. SEC's UA-pin test uses `capture_requests=True`.
- **Effort**: ~25 min including the new helper + 5 test-file import updates + verification all 5 test files still green. Test-code only — no production-code touch.
- **Priority Reasoning**: Low — test code only, not production; works correctly today; cleanup pays off when the 6th news adapter lands or when the underlying httpx test API ever changes (single update site vs five). Pairs naturally with DEBT-016 (`_mock_client` duplicated across 3 u4 test files) — both could be resolved together via a shared `tests/_helpers/mock_transport.py` if the lead chooses to widen scope.

#### DEBT-010: u2 briefing test helpers duplicated across 4 files

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Added shared `tests/_helpers/briefing_pipeline.py` for valid Stage 1 classification stdout and Stage 2 markdown payloads. Moved the unit briefing zero-backoff autouse fixture into `tests/unit/briefing/conftest.py`. Updated the three u2 unit files and the integration PoC to consume the shared helpers.
- **Source**: Step 9.5 sub-agent code review (L1 / Q8)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `_valid_classification_stdout(item_count)` was copied across 4 files, `_valid_stage2_markdown()` was duplicated in 2 files, and `_zero_backoff` appeared in 2 unit files.
- **Suggested Fix**: Consolidate shared helpers and the zero-backoff fixture so future prompt/output shape changes have one update site.
- **Effort**: ~30 min including import updates and verifying no fixture-name collisions.
- **Priority Reasoning**: Low — defensive duplication; all tests already passed.

#### DEBT-013: u3 publisher test `_build_briefing` fixture duplicated

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Added shared `tests/_helpers/briefings.py::build_briefing()` plus `DEFAULT_TARGET_DATE`, then updated publisher unit and integration smoke tests to use the shared builder. The helper keeps the explicit `model_construct` path for malformed disclaimer fixtures.
- **Source**: Step 8 sub-agent code review of u3 publisher (M3 finding)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `_build_briefing()` helper lived in both `tests/unit/publisher/test_writer.py` and `tests/integration/test_publisher_smoke.py`.
- **Suggested Fix**: Lift to a shared test helper so both unit and integration tests can import it.
- **Effort**: ~20 min.
- **Priority Reasoning**: Low — defensive duplication; all tests already passed.

#### DEBT-016: `_mock_client` test helper duplicated across 3 u4 test files

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Replaced the three u4 notifier-local `_mock_client(handler)` helpers with shared `tests/unit/notifier/conftest.py::mock_client()`, then updated telegram, briefing publisher, and operator alerter tests to import the helper.
- **Source**: Step 7 sub-agent code review of u4 notifier (L5 / TD-N04)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: Three near-identical `_mock_client(handler)` helpers lived in `test_telegram.py`, `test_briefing_publisher.py`, and `test_operator_alerter.py`.
- **Suggested Fix**: Move `_mock_client` to `tests/unit/notifier/conftest.py` as a module-level helper, then import from each test file.
- **Effort**: ~10 min.
- **Priority Reasoning**: Low — defensive duplication; all tests already passed.

#### DEBT-015: `_TrackingClient` test pattern fragile to httpx version changes

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Replaced the `httpx.AsyncClient` subclass-based tracking test with a `MagicMock` factory that returns a MockTransport-backed client and asserts `timeout=30.0` from `call_args`.
- **Source**: Step 7 sub-agent code review of u4 notifier (L1 / TD-N03)
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: `test_briefing_publisher_creates_default_client_when_http_none` subclassed `httpx.AsyncClient`, coupling the test to httpx constructor internals.
- **Suggested Fix**: Replace with a factory-mock pattern.
- **Effort**: ~30 min including verifying the new test still pins the timeout contract.
- **Priority Reasoning**: Low — only mattered at httpx upgrade time, but was cheap to harden.

#### DEBT-030: SEC accession-number extraction uses regex on summary instead of canonical `<id>`

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Changed `SecEdgar8kAdapter` to parse `raw_metadata["accession_no"]` from the canonical Atom `<id>` `accession-number=...` payload first, with the existing summary `AccNo:` regex retained as a defensive fallback. Added synthetic tests for canonical-id precedence and summary fallback.
- **Source**: Phase 3 cross-cutting qa review of u1 sources Extension #2 (M2 / Developer self-flag #2)
- **Reference**: R8 (NormalizedItem field rules — `raw_metadata` provenance), R10 (test fixtures)
- **Description**: `sec_edgar_8k.py` extracted `raw_metadata["accession_no"]` by regex on the HTML-stripped summary text even though SEC's Atom feed exposes the accession number canonically in `<id>`.
- **Suggested Fix**: Switch to `<id>` parsing first and keep the regex on summary as fallback if `<id>` is missing.
- **Effort**: ~15 min code change + tests.
- **Priority Reasoning**: Low — current path worked on the recorded fixture; this removes a future-fragile dependency on summary HTML shape.

#### DEBT-025: `ConfigError.missing_vars` overloaded for "malformed value" case

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Added `ConfigError.bad_value_var` plus `ConfigError.for_bad_value()` for present-but-malformed env vars. Updated malformed `SITE_URL_BASE` and `INVESTO_TARGET_DATE` paths to use the new discriminator while leaving `missing_vars` reserved for absent required vars.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L6 — surfaced by the INVESTO_TARGET_DATE side-quest)
- **Reference**: NFR-005 (clarity / discriminator integrity)
- **Description**: `_resolve_target_date_override()` reported a present-but-malformed `INVESTO_TARGET_DATE` through `missing_vars`, blurring the original absent-var discriminator.
- **Suggested Fix**: Add `bad_value_var: str | None = None` field to `ConfigError` and a factory for malformed values.
- **Effort**: ~20 min including factory + tests.
- **Priority Reasoning**: Low — operator alert text was already actionable; this tightens the internal error contract.

#### DEBT-018: AST-grep deny tests use substring matching instead of callable identity

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Replaced substring checks with AST callable-identity helpers that only match calls to the explicit stage-runner whitelist (`_stage_collect`, `_stage_generate`, `_stage_publish`, `_stage_notify_briefing`).
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L4)
- **Reference**: NFR-006 (test robustness)
- **Description**: `tests/unit/orchestrator/test_run_pipeline.py`'s 3 AST-grep deny tests used `"_stage_"` substring matching against `ast.unparse` output, making them brittle to future stage function renames.
- **Suggested Fix**: Replace substring match with callable-identity match.
- **Effort**: ~20 min.
- **Priority Reasoning**: Low — current tests worked; this future-proofs the static contract.

#### DEBT-017: `_TRACEBACK_EXCERPT_MAX_CHARS` duplicated between `pipeline.py` and `models/results.py`

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Promoted the model limit to public `TRACEBACK_EXCERPT_MAX` in `investo.models.results` and updated the orchestrator truncation helper/tests to use the shared constant without widening the package-root `investo.models` public API.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L1)
- **Reference**: NFR-005 (maintainability — DRY constants across module boundaries)
- **Description**: `pipeline.py` and `models/results.py` both carried the traceback excerpt limit as separate 2000-char constants. Drift would make `FailureContext` construction fail from the orchestrator's catch site.
- **Suggested Fix**: Promote one to a public constant and import it in `pipeline.py`.
- **Effort**: ~5 min.
- **Priority Reasoning**: Low — no current drift, but future edits had an obscure failure mode.

#### DEBT-009: `_executable_source` AST helper is duplicated across two test files

- **Created**: 2026-04-29
- **Resolved**: 2026-05-03 — Added shared `tests/_helpers/ast_helpers.py::executable_source()` and updated both briefing source-shape test files to import it instead of carrying duplicate helper bodies.
- **Source**: Step 8.5 sub-agent code review (L1 / Q8); also flagged in the Step 8.4 docstring
- **Reference**: NFR-006 (test-suite maintainability)
- **Description**: The `_executable_source(module)` helper appeared verbatim in `tests/unit/briefing/test_claude_code.py` and `tests/unit/briefing/test_pipeline_no_prompt_strings.py`.
- **Suggested Fix**: Move to `tests/_helpers/ast_helpers.py`.
- **Effort**: ~10 min including import updates.
- **Priority Reasoning**: Low — small duplication, but cheap to remove.

#### DEBT-008: `_parse_classification` does not catch `RecursionError` on adversarial JSON

- **Created**: 2026-04-29
- **Resolved**: 2026-05-03 — Added a 64 KiB Stage 1 stdout byte cap before `json.loads`; over-cap classification output now raises `ValueError` and enters the existing classification retry/failure path. Added a unit test that pins rejection before JSON parsing.
- **Source**: Step 8.5 sub-agent code review (M2 / Q5) of `pipeline.py`
- **Reference**: AC-3.2 (failure contract — BGE wraps LLM-traceable failures), AC-3.4 (programmer errors propagate as-is)
- **Description**: `_parse_classification` called `json.loads(stdout)` on raw LLM stdout. Deep or oversized adversarial JSON could raise outside the intended LLM-failure path.
- **Suggested Fix**: Add a cheap `len(stdout) > 64 * 1024` upper-bound check before `json.loads` and route over-cap to retry as a malformed response.
- **Effort**: ~15 min including unit test.
- **Priority Reasoning**: Low — defense-in-depth for abnormal LLM output.

#### DEBT-033: `_FEED_URL` placement inconsistent — sec_edgar_8k uses module-level while 4 sibling news adapters use `ClassVar`

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Moved SEC EDGAR endpoint configuration onto `SecEdgar8kAdapter` as class-level `_FEED_URL` / `_USER_AGENT` `ClassVar[str]` fields and updated the adapter/test call sites to use the class attribute, matching sibling news-adapter shape.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (L1)
- **Reference**: NFR-005 (consistency across symmetric components), R2 (plugin module shape)
- **Description**: Across the 5 news adapters, `_FEED_URL` placement diverged: `yahoo_finance_news.py`, `yonhap_market.py`, `theblock_crypto.py`, `cnbc_top_news.py` declared it as class-level `ClassVar[str]` inside the adapter class; `sec_edgar_8k.py` declared it as module-level `Final[str]`.
- **Suggested Fix**: Move `sec_edgar_8k._FEED_URL` to `ClassVar[str]` on `SecEdgar8kAdapter`. The `_USER_AGENT` constant should follow the same placement decision for symmetry.
- **Effort**: ~5 min — single-file move, no test changes needed beyond the existing SEC User-Agent assertion.
- **Priority Reasoning**: Low — purely cosmetic; the inconsistency surfaced only when a developer read two adapter sources side by side.

#### DEBT-029: SEC URL-constant placement diverges from sibling adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Resolved alongside DEBT-033 by moving `sec_edgar_8k` endpoint configuration from module-level constants to class-level `ClassVar` attributes on `SecEdgar8kAdapter`.
- **Source**: Phase 3 cross-cutting qa review of u1 sources Extension #2 (M1)
- **Reference**: NFR-005 (consistency across symmetric components), R2 (plugin module shape)
- **Description**: 5 of 6 registered adapters declared their endpoint URL as a class-level `ClassVar[str]`; the 6th — `sec_edgar_8k._FEED_URL` — used module-level `Final[str]`. No test or import required the module-level position.
- **Suggested Fix**: Move `sec_edgar_8k._FEED_URL` and `_USER_AGENT` to class-level `ClassVar` on `SecEdgar8kAdapter`.
- **Effort**: ~5 min code move.
- **Priority Reasoning**: Low — purely cosmetic, no behavior impact, no test pressure.

#### DEBT-026: `archive/.gitkeep` redundant once `archive/index.md` exists

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Removed `archive/.gitkeep`; `archive/index.md` already keeps the archive directory tracked.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L3)
- **Reference**: NFR-005 (no dead files)
- **Description**: `archive/.gitkeep` was created to ensure the directory existed in git before the daily-briefing bot's first write. `archive/index.md` already keeps the directory tracked, so `.gitkeep` was redundant.
- **Suggested Fix**: `git rm archive/.gitkeep`.
- **Effort**: ~1 min.
- **Priority Reasoning**: Low — harmless artifact.

#### DEBT-023: `daily-briefing.yml` installs `--extra dev` but never runs pytest

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Changed the daily briefing workflow install step to runtime-only (`uv sync --no-dev`) and updated the step name/comment to reflect that tests and docs tooling run elsewhere.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (L7)
- **Reference**: NFR-001 (cron run wall-clock budget)
- **Description**: `.github/workflows/daily-briefing.yml` installed dev dependencies even though the job only invokes `python -m investo`.
- **Suggested Fix**: Switch to `uv sync --no-dev` and update the step name + comment to "Install project (runtime only)".
- **Effort**: ~5 min YAML edit.
- **Priority Reasoning**: Low — saves cold-start install time; the 10-minute budget had margin.

#### DEBT-022: `pages.yml` permissions set at workflow level instead of job level

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Removed workflow-level Pages permissions and moved them to job level: `build` now has only `contents: read`; `deploy` has `pages: write` and `id-token: write`.
- **Source**: Step 6 sub-agent code review of u6 infra/CI (M2)
- **Reference**: NFR-007 (least-privilege secrets / permissions handling)
- **Description**: `.github/workflows/pages.yml` granted `pages: write` and `id-token: write` to both `build` and `deploy`, though only `deploy` needs them.
- **Suggested Fix**: Move to job-level permissions.
- **Effort**: ~5 min YAML edit.
- **Priority Reasoning**: Low — cosmetic least-privilege improvement.

#### DEBT-021: Unused `PublisherError` re-export in `pipeline.__all__`

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Removed the unused `PublisherError` import/re-export and stale comment from `src/investo/orchestrator/pipeline.py`.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L2)
- **Reference**: NFR-005 (no dead code)
- **Description**: `pipeline.__all__` re-exported `"PublisherError"` with a stale comment, but `__main__.py` does not import it.
- **Suggested Fix**: Drop `"PublisherError"` from `pipeline.__all__`.
- **Effort**: ~2 min.
- **Priority Reasoning**: Low — dead code, not load-bearing.

#### DEBT-020: `_safe_alert` and `_attempt_boot_alert` exception lists not aligned

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Broadened `_attempt_boot_alert` to catch `Exception`, matching `_safe_alert`; parametrized the boot-alert test across transport, validation, and future-contract failures.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L6 — partially resolved by H1 fix)
- **Reference**: NFR-005 (consistency across symmetric helpers)
- **Description**: `_safe_alert` caught `Exception`, while `_attempt_boot_alert` used the narrower `(OSError, RuntimeError, httpx.HTTPError)`.
- **Suggested Fix**: Broaden `_attempt_boot_alert`'s `except` to `Exception`.
- **Effort**: ~5 min for the change + ~10 min for parametrized tests.
- **Priority Reasoning**: Low — pure consistency tightening.

#### DEBT-019: `resolve_target_date` PBT covers only 2026

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Widened both `resolve_target_date` hypothesis strategies from 2026-only to 2024-2030 and updated the test docstring to describe the broader domain.
- **Source**: Step 12 sub-agent code review of u5 orchestrator (L5)
- **Reference**: NFR-006 (PBT coverage breadth)
- **Description**: `tests/unit/orchestrator/test_date_resolution.py`'s 2 hypothesis PBTs used 2026-only bounds, leaving leap-year edges and additional year-boundary crossings unverified.
- **Suggested Fix**: Widen the strategy to span 2024-2030.
- **Effort**: ~5 min.
- **Priority Reasoning**: Low — date math is mechanical; PBT primarily catches strategy bugs, not algorithm bugs.

#### DEBT-012: `_truncate_stderr` helper duplicated across u2 + u3 errors modules

- **Created**: 2026-04-30
- **Resolved**: 2026-05-03 — Added shared internal `investo._internal.text` module exporting `STDERR_BYTE_CAP` and `truncate_stderr()`. Updated u2 `BriefingGenerationError` and u3 `PublisherGitError` to use the shared helper, removing duplicated truncation implementations while preserving the 1024-byte UTF-8-safe behavior.
- **Source**: Step 8 sub-agent code review of u3 publisher (M1 finding)
- **Reference**: NFR-006 (test-suite/source maintainability); NFR-007 AC-7.4 (1024-byte stderr cap)
- **Description**: `_STDERR_BYTE_CAP: Final[int] = 1024` constant + `_truncate_stderr(value: str | None) -> str | None` helper appeared byte-identically in `src/investo/briefing/errors.py` and `src/investo/publisher/errors.py`. u4 notifier will likely need the same cap when bounding error-text payloads to Telegram. Three copies risked silent drift if one site changed the cap value or the `errors="ignore"` decode strategy.
- **Suggested Fix**: Lift to a shared internal module — `src/investo/_internal/text.py` (new) or extend `src/investo/models/_validators.py`. Both u2 + u3 errors modules import from there. u4 notifier picks it up at construction time.
- **Effort**: ~20 min including import updates and verifying both unit's truncation tests still pass.
- **Priority Reasoning**: Medium — promoted risk if u4 introduced a third copy. Addressed by creating one shared helper before further drift.

#### DEBT-007: No byte-exact JSON snapshot test for `serialize_items_for_prompt`

- **Created**: 2026-04-29
- **Resolved**: 2026-05-03 — Added a byte-exact snapshot test in `tests/unit/briefing/test_pipeline_unit.py` that pins `serialize_items_for_prompt([item])` including key order, default JSON whitespace, URL string, and UTC timestamp format (`+00:00`). This protects FakeClaudeRunner prompt-hash fixture keys from accidental serializer drift.
- **Source**: Step 8.5 sub-agent code review (L4 / Q4) of `pipeline.py`
- **Reference**: AC-6.2 (serialize round-trip), `tests/_helpers/fake_claude_runner.py` (FakeClaudeRunner uses `sha256(prompt)[:16]` as fixture key)
- **Description**: `serialize_items_for_prompt` produces a JSON string that downstream becomes part of the Stage 1 prompt; that prompt is then SHA-256'd to derive the FakeClaudeRunner fixture key. The serializer is deterministic in practice (Python >=3.7 dict insertion order; explicit field order in the dict literal; `astimezone(UTC).isoformat()` always emits `+00:00`) but no test pinned the byte-exact JSON output. A future refactor that, e.g., switches to `json.dumps(payload, sort_keys=True)` or reorders keys would silently invalidate every recorded LLM fixture and break replay.
- **Suggested Fix**: Add a snapshot test in `test_pipeline_unit.py` that constructs a known `NormalizedItem` and asserts the exact bytes returned by `serialize_items_for_prompt([item])`. Pin both the key order (`{"id": 1, "category": ..., "source": ..., "title": ..., "summary": ..., "url": ..., "ts": ...}`) and the timestamp format (`"+00:00"` not `"Z"`). The PBT shape test does NOT cover this — it only checks the key set, not the order or whitespace.
- **Effort**: ~15 min including a 2-3 line test addition.
- **Priority Reasoning**: Medium — the determinism assumption is currently correct but undocumented; the FakeClaudeRunner architecture depends on it. Cheap to pin.

#### DEBT-002: No date sanity bounds on `target_date` / `published_at` (project-wide)

- **Created**: 2026-04-27
- **Resolved**: 2026-05-03 — Added `validate_target_date_sanity()` at the orchestrator boundary with `2024-01-01 <= target_date <= today(UTC)+1`; wired it into `run_pipeline()` and `INVESTO_TARGET_DATE` override parsing so malformed manual backfill dates fail before publish. Added an aggregator-level future timestamp guard that drops source items whose `published_at` is more than 30 days after the fetch window and logs a warning.
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3); same pattern in `items.py`
- **Reference**: US-005 (scheduled execution), FR-006 (archival)
- **Description**: `Briefing.target_date`, `BriefingNotification.target_date`, and `NormalizedItem.published_at` accepted any valid date — including far-future (`date(2206, 4, 27)`) or pre-epoch values. A typo upstream could commit nonsensical archive paths or stamp items with bad timestamps.
- **Suggested Fix**: Add sanity bounds at the **orchestrator** boundary (`resolve_target_date`) rather than in the models, since the models are also used in historical replays where wider bounds may be needed. Concrete check: `2024-01-01 <= target_date <= today + 1`. For Source Adapters, reject items whose `published_at` is more than 30 days in the future.
- **Effort**: ~15 min in u5 orchestrator; ~10 min in u1 sources base.
- **Priority Reasoning**: Medium — defensive only; catches upstream typos before writing archive paths or sending future-dated items downstream.

#### DEBT-001: `Briefing` model lacks `disclaimer ∈ rendered_markdown` invariant

- **Created**: 2026-04-27
- **Resolved**: 2026-05-03 — Added a `model_validator(mode="after")` on `Briefing` that rejects instances whose stripped `disclaimer` is absent from `rendered_markdown`. Added a model-level regression test and updated publisher/orchestrator failure-path tests that intentionally need malformed Briefing objects to use `Briefing.model_construct(...)` explicitly.
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3)
- **Reference**: NFR-004 (compliance / disclaimer enforcement)
- **Description**: The `Briefing` pydantic model permitted a state where `disclaimer` text was not actually present in `rendered_markdown`. The only enforcement was `publisher.verify_disclaimer` (called pre-publish). Defense-in-depth shifted the guarantee one layer earlier — into the data model — so normal construction cannot represent that invalid state.
- **Suggested Fix**: Add a `model_validator(mode="after")` on `Briefing` that asserts `self.disclaimer.strip() in self.rendered_markdown`. Trade-off: rejects ambiguous test fixtures that pass section text without re-running the rendering pipeline. Tests that deliberately exercise publisher failure paths should bypass validation with `model_construct` to make the malformed fixture explicit.
- **Effort**: ~30 min including fixing fixtures
- **Priority Reasoning**: Medium — not yet a real bug because the publisher guard existed, but if anyone ever bypassed the publisher path (e.g., direct unit-tests, future replays, ADR'd alternate flow), the guard disappeared.

#### DEBT-028: `raw_metadata` numeric serialization is inconsistent across u1 adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-03 — Added canonical `format_float()` / `format_int()` helpers to `src/investo/sources/_config.py`; updated yfinance, CoinGecko, and FRED numeric `raw_metadata` call sites to use fixed six-decimal float formatting and plain integer formatting. Added helper tests, updated adapter expectation tests, and verified the targeted source test suite.
- **Source**: Cross-cutting sub-agent code review of u1 sources extension Step 5.7 (M1)
- **Reference**: NFR-005 (consistency across symmetric components), R8 (NormalizedItem field rules), R9 (idempotence)
- **Description**: The 3 new u1 adapters used 3 different float-to-string idioms for `NormalizedItem.raw_metadata` values:
  - `yfinance.py` — `f"{value:.4f}"` for OHLC, `str(int)` for volume
  - `coingecko.py` — `f"{price:.6f}"` / `f"{pct:.6f}"` for prices+pct, `f"{value:.2f}"` for volume/market_cap
  - `fred.py` — `f"{value}"` (bare repr; depends on Python's float-to-str default)
  Two issues compounded: (a) the bare `f"{value}"` in FRED could drift between Python releases or with payload type (`f"{1.0}"` → `"1.0"` vs `f"{1}"` → `"1"`); (b) cross-adapter, identical numerics serialized to different strings (e.g., `1.5` became `"1.5000"` in yfinance, `"1.500000"` in coingecko, `"1.5"` in fred). R9 (idempotence — same source state → equal items) was technically satisfied within each adapter but the cross-adapter inconsistency meant u2's downstream prompt saw jagged data.
- **Suggested Fix**: Add a `_format_numeric()` helper to `src/investo/sources/_config.py` (or a new `_format.py` if scope grows): `format_float(v) -> str` (fixed precision, e.g. 6 decimals), `format_int(v) -> str`. Update all 3 adapters to call the helpers. Bonus: the helper becomes the canonical place to add NaN/inf handling if a future adapter needs it.
- **Effort**: ~30 min including helper + 3 adapter call-site updates + test fixture string updates.
- **Priority Reasoning**: Medium — not breaking anything today (each adapter's tests pass with their own format), but would surface as soon as a 4th adapter author had to choose between the 3 existing styles, OR when u2 starts grouping items by category and the cross-adapter inconsistency becomes visible in the LLM prompt. Addressed before the next adapter lands.

#### DEBT-031: `_NS_DC_CREATOR` namespace constant duplicated across 2 news adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-01 — Extracted to new `src/investo/sources/_xml_namespaces.py` module exporting `DC_CREATOR: Final[str]`; both `yonhap_market.py` and `theblock_crypto.py` now import from there.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (M2)
- **Reference**: NFR-006 (test-suite/source maintainability), NFR-005 (consistency across symmetric components)
- **Description**: The Dublin Core `<dc:creator>` namespace constant `_NS_DC_CREATOR: Final[str] = "{http://purl.org/dc/elements/1.1/}creator"` appears byte-identically in `src/investo/sources/yonhap_market.py` and `src/investo/sources/theblock_crypto.py`. Both adapters use it the same way: `entry.find(_NS_DC_CREATOR)`. Two copies is the minimum threshold for "extract" under NFR-006 — and any third RSS adapter that needs `<dc:creator>` (a common Dublin Core element across many Korean and English wire feeds) would land a third copy.
- **Suggested Fix**: Lift to a new module `src/investo/sources/_xml_namespaces.py` exporting a small set of curated Clark-notation namespace constants (`NS_DC_CREATOR`, room for `NS_DC_DATE`, `NS_MEDIA_THUMBNAIL`, etc. as future adapters need them). Update both call sites to import. The module mirrors `_config.py` / `_sanitize.py` as an underscore-prefixed internal helper.
- **Effort**: ~15 min including the new file + 2 import updates + ruff/mypy verification.
- **Priority Reasoning**: Medium — promotes to High when a third dc:creator-using adapter lands (likely soon given the Korean/English RSS pattern). Address before the next news-adapter extension.

#### DEBT-032: `_SUMMARY_MAX_LEN = 280` constant duplicated across 8 source adapters

- **Created**: 2026-05-01
- **Resolved**: 2026-05-01 — Lifted to `src/investo/sources/_config.py` as `SUMMARY_MAX_LEN: Final[int] = 280`; all 8 adapters (cnbc_top_news, coingecko, fomc_rss, fred, sec_edgar_8k, theblock_crypto, yfinance, yonhap_market) now import the constant.
- **Source**: Phase 4 cross-cutting qa review of u1 sources Extension #3 (M3)
- **Reference**: NFR-006 (test-suite/source maintainability), R8 (NormalizedItem field rules — summary length cap)
- **Description**: The 280-character summary truncation cap `_SUMMARY_MAX_LEN: Final[int] = 280` appears byte-identically across **8** adapter files: `cnbc_top_news.py`, `coingecko.py`, `fred.py`, `fomc_rss.py`, `sec_edgar_8k.py`, `yfinance.py`, `theblock_crypto.py`, `yonhap_market.py`. All 8 use it the same way: `summary[:_SUMMARY_MAX_LEN]` (or equivalent). Eight copies of a magic-number constant; any future change to the cap (e.g., raising to 400 chars to give the briefing layer richer context) requires touching 8 files in lockstep, with a high silent-drift risk if any is missed during a refactor. Independent of DEBT-028 (DEBT-028 = numeric formatting; this = string-length cap).
- **Suggested Fix**: Lift to `src/investo/sources/_config.py` as `SUMMARY_MAX_LEN: Final[int] = 280` (un-underscored at the module level since `_config` itself is the underscore boundary). Update all 8 adapters to `from ._config import SUMMARY_MAX_LEN`. Optionally, a small helper `truncate_summary(s: str | None) -> str | None` in `_config.py` would absorb the `summary[:cap] if summary else None` shape too.
- **Effort**: ~20 min including the constant lift + 8 import updates + verification (the existing per-adapter tests already pin truncation behavior empirically; no test rewrite needed).
- **Priority Reasoning**: Medium — not breaking anything today (all 8 copies are byte-identical), but the duplication is the single largest constant-drift surface in u1 and the next adapter author will land copy #9 if not fixed. Addresses NFR-006 directly.

---

*Managed by `/tech-debt` skill. Run `/tech-debt add` to add new items.*
