# Cross-Check: u28 watchlist-usability-foundation

**Scope**: u28 watchlist-usability-foundation
**Date**: 2026-05-08
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 6 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **6** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u28 is a Wave 1 P0 follow-up from the 2026-05-07 persona evaluation (persona #4 — P0 + P1) that makes the watchlist surface legible to first-time users (onboarding nudge), forgiving across Korean / English aliases, and disciplined under partial coverage so it does not produce false-confidence callouts. The unit does not introduce paid sources, accounts, trading, or new external dependencies.

**Plan**: `aidlc-docs/construction/plans/u28-watchlist-usability-foundation-code-generation-plan.md`
**Goal**: Make watchlist matching legible to first-time users (onboarding nudge), forgiving across Korean / English aliases, and disciplined under partial coverage so it does not produce false-confidence callouts.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-002 Korean briefing comprehension | ✅ | `src/investo/briefing/watchlist.py` (`_matches_korean_term` Hangul word-boundary heuristic, `DEFAULT_CORE_ALIASES` Korean / English bundle for BTC / ETH / SOL + NVDA / TSLA / AAPL / MSFT / GOOGL / META / AMZN), `tests/unit/briefing/test_watchlist.py` | Korean term matching now applies a Hangul particle / whitespace / punctuation boundary heuristic rather than naive substring containment, eliminating "비트" → "비트맵" false positives; the default alias bundle covers the most common reader-facing aliases without requiring config edits. |
| FR-003 static web publishing | ✅ | `src/investo/briefing/pipeline.py` (`render_watchlist_prompt_context`, segment markdown callout), `src/investo/visuals/cards.py` (`WatchlistRelevanceCardInput.rows max_length=5`, slice in `build_watchlist_relevance_card`) | Site callout match cap raised to 5 entries (markdown + visual card). The unconfigured branch renders an onboarding nudge ("관심 목록 미설정 — config/watchlist.json 추가하세요") on the public site without a duplicate Telegram surface. |
| FR-008 segmented briefing | ✅ | `src/investo/briefing/pipeline.py` (channel/coverage thread), `src/investo/orchestrator/pipeline.py` (visual-asset coverage_status thread), `tests/unit/briefing/test_watchlist_pipeline_u28.py` | Coverage hold branch (`status="coverage_hold"`) is honoured per segment — the watchlist callout switches to the "데이터 수집 부족으로 매칭 판단 보류" copy instead of asserting absence; site callout + LLM prompt context + Telegram skip stay consistent. |
| NFR-002 cost / no paid APIs | ✅ | `src/investo/briefing/watchlist.py` (config-driven matching only, no HTTP), `config/watchlist.json` (non-secret JSON) | u28 is a deterministic config-driven matcher refactor; no Anthropic SDK introduced, no paid call surface added, no external dependency added. |
| NFR-003 graceful degradation | ✅ | `src/investo/briefing/watchlist.py::_matches_korean_term` (defensive empty-term guard), `WatchlistImpactStatus`, `WatchlistChannel` | Coverage_hold and unconfigured states never raise — they branch to dedicated copy. M5 fix (`if not term_cf: return False`) prevents an empty alias from short-circuiting to truthy on entry. |
| NFR-004 compliance / disclaimer boundary | ✅ | Publisher's `verify_disclaimer` (unchanged), `src/investo/orchestrator/pipeline.py` | u28 only changes pre-publish briefing content; disclaimer enforcement is unchanged. |
| NFR-005 consistency / DRY | ✅ | `src/investo/briefing/watchlist.py` (single `_match_term_with_aliases` helper), `WatchlistChannel` enum routing, `WatchlistImpactStatus` enum | Single canonical alias-resolution path for ticker / asset / keyword / sector kinds. Site/Telegram divergence routed through one channel parameter rather than duplicate render paths. |
| NFR-006 testing | ✅ | `tests/unit/briefing/test_watchlist.py` (+25), `tests/unit/briefing/test_watchlist_pipeline_u28.py` (+2 new file), `tests/unit/visuals/test_cards.py`, `tests/unit/notifier/test_summary.py` | +28 targeted tests (1182 → 1210); covers Korean word-boundary, alias normalisation, short-ticker case-sensitive raw matching, coverage_hold branch, site cap 5 vs Telegram cap 3, onboarding nudge, defensive empty-term guard. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/briefing/watchlist.py` (config-driven, non-secret tickers / aliases only) | No new secret surfaces; `WatchlistConfig` carries reader-facing labels only; no env-var / log / error / fixture leak surface introduced. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| When `config/watchlist.json` is absent, the public site first viewport renders an onboarding nudge ("관심 목록 미설정 — config/watchlist.json 추가하세요"). Telegram surface is unchanged. | ✅ | `src/investo/briefing/watchlist.py::WatchlistImpactStatus.UNCONFIGURED` + `is_empty()`; site render path emits the nudge; `notifier/summary.py` skips the impact suffix when unconfigured. Pinned by `tests/unit/briefing/test_watchlist.py` and `test_watchlist_pipeline_u28.py`. |
| `WatchlistConfig` gains an `aliases: dict[str, list[str]]` field with a default core-asset bundle (BTC↔Bitcoin↔비트코인, ETH↔Ethereum↔이더리움, NVDA↔엔비디아, etc.). | ✅ | `src/investo/briefing/watchlist.py::DEFAULT_CORE_ALIASES` (BTC / ETH / SOL + NVDA / TSLA / AAPL / MSFT / GOOGL / META / AMZN with English + Korean aliases); `WatchlistConfig.aliases` field + `effective_aliases()` resolver merging user config over defaults. |
| Korean term matching applies a word-boundary heuristic (Hangul particle / whitespace / punctuation) or supports an explicit `exact_match: true` per-term option to suppress partial-string false positives. | ✅ | `src/investo/briefing/watchlist.py::_matches_korean_term` (Hangul boundary heuristic — checks adjacency of Hangul syllables, whitespace, and punctuation around the matched span); `tests/unit/briefing/test_watchlist.py` (boundary positive / negative cases). |
| In zero / insufficient coverage segments the watchlist callout switches to a "데이터 수집 부족으로 매칭 판단 보류" branch instead of asserting absence. | ✅ | `WatchlistImpactStatus.COVERAGE_HOLD` flowed through `briefing/pipeline.py` (segment markdown callout + LLM prompt context) and `orchestrator/pipeline.py` (visual-asset coverage_status thread); `notifier/summary.py` strips the coverage_hold prefix for Telegram. |
| Site callout match cap is raised to 5 entries while Telegram remains capped at 3. | ✅ | `src/investo/briefing/watchlist.py::_SITE_MAX_RENDERED_MATCHES = 5`; `src/investo/visuals/cards.py::WatchlistRelevanceCardInput.rows` `max_length=5` + slice in `build_watchlist_relevance_card`; Telegram cap remains in `notifier/summary.py`. |
| Single-character / two-character ticker inputs trigger an explicit warning, or are captured via a capitalize / parenthesized-token heuristic. | ✅ | `src/investo/briefing/watchlist.py::_matches_short_ticker` — short (≤ 2 ASCII) ticker / asset terms match case-sensitive raw token (so `AI` does not match `ai` inside arbitrary words); short keyword / sector terms still use the casefold word-boundary regex (M3 fix). |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed
- `uv run mypy --strict src/` — passed (66 source files)
- `uv run pytest -q` — 1210 passed (1182 → 1210, +28 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u25-u33 follow-up wave (no new mkdocs nav/content changes in u28)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u28 is a deterministic matcher refactor; no LLM client introduced. The watchlist context only feeds the existing Stage 2 prompt as plain text. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | All u28 source changes are inside `briefing/` (`watchlist.py`, `pipeline.py`), `visuals/cards.py`, `notifier/summary.py`, and the orchestrator's existing visual-asset thread. No new cross-unit import added. |
| 무료 API only (no paid keys) | ✅ | No new external endpoints. `config/watchlist.json` is local non-secret JSON. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u28 does not change notifier targets; the channel split routes through `WatchlistChannel` (site vs telegram render path), not chat-id. |
| R8 (NormalizedItem `raw_metadata` provenance shape) | ✅ | u28 does not touch `raw_metadata`. The watchlist surface consumes only `briefing` outputs; no new provenance fields introduced. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | The watchlist config carries reader-facing labels only (tickers, asset names, sectors, Korean keywords). No env-var / secret value flows through the matcher. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u28 does not introduce any XML parsing path. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **M3** — `_matches_term` signature gained an explicit `kind` parameter so short (≤ 2 ASCII) ticker / asset terms match case-sensitive raw token (e.g., `AI` no longer matches `ai` inside arbitrary words), while short keyword / sector terms continue to use the casefold word-boundary regex (consistent with longer terms). Distinguishes the "ticker is a proper noun shape" expectation from the "keyword is a casefold concept" expectation.
  - **M5** — `_matches_korean_term` entry added a defensive `if not term_cf: return False` guard so an empty alias cannot short-circuit to a truthy match. Eliminates a latent fall-through path when a user supplies a `""` entry in `aliases`.
- Deferred to TECH-DEBT (no Critical / High findings outstanding):
  - **M1** → `DEBT-051 (Low)` — alias value cross-key collision validation is not enforced (e.g., `aliases={"BTC": ("ETH",)}` is silently accepted).
  - **M2** → `DEBT-052 (Low)` — `match_watchlist_items` docstring does not document `partial` / `normal` semantics; only `insufficient` / coverage_hold is explicit.
  - **M4** → `DEBT-053 (Low)` — site cap 5 is hard-coded in 4 separate places; consolidate `cards.py` to import `_SITE_MAX_RENDERED_MATCHES` from `watchlist.py`.
  - **M6** → `DEBT-054 (Low)` — `WatchlistImpact` invariants (e.g., `matches=()` when `status="coverage_hold"` / `"unconfigured"`) are not enforced at construction time.
  - **L1** → `DEBT-055 (Low)` — site / telegram channel branching heuristics are spread across `watchlist.py`, `cards.py`, and `summary.py`; introduce a shared `WatchlistChannel` adapter to collapse the three branches.
  - **L2** → `DEBT-057 (Low)` — `WatchlistMatch.matched_alias` exposure semantics (audit/log only, not user-facing display) are not documented.
  - **L3** → `DEBT-056 (Low)` — short ASCII ticker registration does not produce a config-load warning; add an advisory log line for 1-2 character tickers.
- No Critical or High findings.

---

## TECH-DEBT Surfaced by This Unit

Seven new low-priority items registered (`docs/TECH-DEBT.md`):

- **DEBT-051 (Low)** — alias value cross-key collision validation is not enforced. A `WatchlistConfig` model_validator should warn (or raise) when an alias resolves to a different canonical key already declared by the user.
- **DEBT-052 (Low)** — `match_watchlist_items` docstring lacks explicit `partial` / `normal` semantics; only the `insufficient` (coverage_hold) branch is documented today.
- **DEBT-053 (Low)** — site cap 5 is hard-coded in 4 separate places (`watchlist._SITE_MAX_RENDERED_MATCHES`, `cards.WatchlistRelevanceCardInput.rows max_length`, `cards.build_watchlist_relevance_card` slice, `watchlist.render_watchlist_prompt_context`). `cards.py` should import the constant from `watchlist.py` to collapse the four declarations into one.
- **DEBT-054 (Low)** — `WatchlistImpact` invariants are not enforced at construction time. Specifically, `matches=()` when `status="coverage_hold"` / `"unconfigured"` is convention only; a `__post_init__` validator would harden this.
- **DEBT-055 (Low)** — `WatchlistChannel` abstraction is partial; site / telegram branching heuristics are spread across `watchlist.py`, `cards.py`, and `summary.py`.
- **DEBT-056 (Low)** — short ASCII ticker registration does not produce a config-load warning. A `WatchlistConfig` model_validator should advisory-log when a 1-2 character ASCII ticker is declared.
- **DEBT-057 (Low)** — `WatchlistMatch.matched_alias` exposure semantics (audit / log only, not user-facing display) are not documented; add a docstring note.

---

## Gaps Analysis

No gaps found.

## Proposed Actions

- No requirements / design changes.
- TECH-DEBT updates already registered (DEBT-051 through DEBT-057).
- `mkdocs build --strict` to be re-verified at the close of the broader u25-u33 follow-up wave.
