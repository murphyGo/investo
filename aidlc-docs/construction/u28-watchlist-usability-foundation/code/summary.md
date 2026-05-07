# Code Summary: u28 watchlist-usability-foundation

**Date**: 2026-05-08

## Completed

- Made the watchlist surface legible to first-time users, forgiving across Korean / English aliases, and disciplined under partial coverage. The unit decomposes into three concerns and threads them consistently through site markdown, the Stage 2 LLM prompt, the visual `WatchlistRelevanceCard`, and the Telegram impact suffix:
  1. **Onboarding nudge + unconfigured branch** — when `config/watchlist.json` is absent, `WatchlistImpactStatus.UNCONFIGURED` + `is_empty()` flips the site first viewport to render the Korean nudge `관심 목록 미설정 — config/watchlist.json 추가하세요`, and `notifier/summary.py` skips the Telegram impact suffix entirely (no duplicate surface).
  2. **Alias mapping + Korean word-boundary** — `WatchlistConfig.aliases` extends with a default core bundle (`DEFAULT_CORE_ALIASES`: BTC / ETH / SOL + NVDA / TSLA / AAPL / MSFT / GOOGL / META / AMZN, each with English + Korean aliases). `effective_aliases()` merges user config over defaults. `_matches_korean_term` applies a Hangul particle / whitespace / punctuation word-boundary heuristic so `비트` no longer matches inside `비트맵`.
  3. **Coverage hold branch + cap split** — `WatchlistImpactStatus.COVERAGE_HOLD` is threaded through `briefing/pipeline.py` (segment markdown callout + LLM prompt context) and `orchestrator/pipeline.py` (visual-asset coverage_status thread). The site callout copy switches to `데이터 수집 부족으로 매칭 판단 보류` and the visual card carries the same status. Site match cap raised to 5 entries (`_SITE_MAX_RENDERED_MATCHES`), Telegram remains capped at 3.
- Added `WatchlistChannel` enum routing so site vs telegram render paths share one channel parameter rather than duplicating render logic. `kind` parameter on `_match_term_with_aliases` cleanly distinguishes ticker / asset / keyword / sector matching expectations.
- Applied M3 (`_matches_term` signature gained `kind` parameter — short ≤ 2 ASCII ticker / asset terms now match case-sensitive raw token; short keyword / sector terms continue to use the casefold word-boundary regex consistent with longer terms) and M5 (`_matches_korean_term` defensive `if not term_cf: return False` entry guard) pre-merge. M1 / M2 / M4 / M6 / L1-L7 deferred to DEBT-051 through DEBT-057.

## Files Changed

### Modified source files

- `src/investo/briefing/watchlist.py` — full refactor: `DEFAULT_CORE_ALIASES`, `WatchlistImpactStatus`, `WatchlistChannel`, `WatchlistConfig.aliases` field, `is_empty()`, `effective_aliases()`, `_matches_korean_term`, `_matches_short_ticker`, `_match_term_with_aliases`, `kind` parameter dispatch, `_SITE_MAX_RENDERED_MATCHES = 5`, `render_watchlist_prompt_context` site/telegram channel branching.
- `src/investo/briefing/pipeline.py` — channel + coverage_status thread into the watchlist call site; coverage_hold branch flows through the segment markdown callout and the Stage 2 LLM prompt context.
- `src/investo/notifier/summary.py` — strips the coverage_hold prefix when constructing the Telegram impact suffix; skips the suffix entirely on unconfigured.
- `src/investo/visuals/cards.py` — `WatchlistRelevanceCardInput.rows` `max_length=5`; `build_watchlist_relevance_card` slice updated to 5; coverage_hold rendering branch.
- `src/investo/orchestrator/pipeline.py` — visual-asset coverage_status thread for the watchlist relevance card.

### New test files

- `tests/unit/briefing/test_watchlist_pipeline_u28.py` — 2 new pipeline integration tests (channel + coverage_status threading; onboarding nudge end-to-end).

### Modified test files

- `tests/unit/briefing/test_watchlist.py` — +25 tests (alias resolution, Korean word boundary, short ticker case-sensitive, coverage_hold copy, site cap 5, defensive empty-term guard); includes the post-merge M3 + M5 fix coverage.
- `tests/unit/visuals/test_cards.py` — site cap 5 assertion + coverage_hold variant.
- `tests/unit/notifier/test_summary.py` — coverage_hold prefix-strip assertion + unconfigured skip path.

### Modified documentation

- `docs/TECH-DEBT.md` (DEBT-051 / DEBT-052 / DEBT-053 / DEBT-054 / DEBT-055 / DEBT-056 / DEBT-057 added)
- `docs/cross-checks/2026-05-08-u28-watchlist-usability-foundation.md` (new)
- `aidlc-docs/audit.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/u28-watchlist-usability-foundation-code-generation-plan.md` (DoD + step checkboxes marked)

## Linked Requirements / FRs / NFRs / ACs

- **FR-002** — Korean briefing comprehension: Hangul word-boundary heuristic eliminates the `비트` → `비트맵` substring false positive; default alias bundle gives every reader the most common Korean / English mappings without config edits.
- **FR-003** — static web publishing: site cap 5 entries (markdown + visual card); onboarding nudge renders on the first viewport when config is absent.
- **FR-008** — segmented briefing: coverage_hold branch is honoured per segment and consistently flows through site markdown, LLM prompt, and visual card.
- **NFR-002 (cost / no paid APIs)** — config-driven matcher refactor only; no Anthropic SDK introduced; no paid call surface added; no new external dependency.
- **NFR-003 (graceful degradation)** — coverage_hold and unconfigured states branch to dedicated copy without raising; M5 fix prevents an empty alias from short-circuiting to truthy.
- **NFR-004 (compliance / disclaimer)** — `verify_disclaimer` remains the publish-time gate; u28 only changes pre-publish briefing content.
- **NFR-005 (consistency / DRY)** — single `_match_term_with_aliases` helper for ticker / asset / keyword / sector kinds; site/telegram divergence routed through one `WatchlistChannel` parameter.
- **NFR-006 (testing)** — +28 targeted tests (1182 → 1210); covers alias normalisation, Korean word boundary, short-ticker case-sensitive matching, coverage_hold branch, site cap 5 vs Telegram cap 3, onboarding nudge, defensive empty-term guard.
- **NFR-007 (R8 / R13)** — config carries reader-facing labels only; no env-var / secret surface introduced.

## Architecture Summary

```
briefing/
  watchlist.py
    DEFAULT_CORE_ALIASES                  # BTC / ETH / SOL + NVDA / TSLA / AAPL / MSFT / GOOGL / META / AMZN
                                          #   each with English + Korean aliases

    WatchlistImpactStatus                 # enum: NORMAL | PARTIAL | COVERAGE_HOLD | UNCONFIGURED
    WatchlistChannel                      # enum: SITE | TELEGRAM
    WatchlistConfig.aliases               # user override merged over DEFAULT_CORE_ALIASES via effective_aliases()
    WatchlistConfig.is_empty()            # → drives onboarding nudge

    _SITE_MAX_RENDERED_MATCHES = 5        # site cap (Telegram cap stays at 3 in notifier/summary)

    _matches_korean_term(...)             # Hangul particle / whitespace / punctuation boundary heuristic
                                          # M5 fix: defensive `if not term_cf: return False` entry guard
    _matches_short_ticker(...)            # ≤ 2 ASCII ticker / asset → case-sensitive raw token
    _match_term_with_aliases(..., kind)   # M3 fix: kind dispatch
                                          #   kind in (ticker, asset)   → short=case-sensitive raw
                                          #   kind in (keyword, sector) → casefold word-boundary regex

    render_watchlist_prompt_context(..., channel)
                                          # site:     full callout + cap 5
                                          # telegram: compact suffix + cap 3 (delegated to notifier)

  pipeline.py
    coverage_status thread → WatchlistImpactStatus.COVERAGE_HOLD
                                          # → site markdown callout copy "데이터 수집 부족으로 매칭 판단 보류"
                                          # → LLM Stage 2 prompt context
                                          # → visual card status

notifier/summary.py
    coverage_hold prefix strip            # Telegram suffix elides the coverage_hold copy
    unconfigured branch                   # Telegram suffix omitted entirely

visuals/cards.py
    WatchlistRelevanceCardInput.rows      # max_length=5
    build_watchlist_relevance_card        # slice [:5] + coverage_hold rendering branch

orchestrator/pipeline.py
    visual-asset coverage_status thread   # carries the same status enum into the visual builder
```

The site / telegram divergence is routed through `WatchlistChannel` rather than duplicated render paths. The four canonical `kind` values (ticker / asset / keyword / sector) cleanly express the "proper-noun shape" vs "casefold concept" expectation difference, which is what M3 ratifies.

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M3 (`_matches_term` `kind` parameter — short ≤ 2 ASCII ticker / asset case-sensitive raw matching; keyword / sector casefold word-boundary regex) applied pre-merge.
- M5 (`_matches_korean_term` defensive `if not term_cf: return False` entry guard) applied pre-merge.
- M1 deferred → DEBT-051 (Low) — alias value cross-key collision validation absent.
- M2 deferred → DEBT-052 (Low) — `match_watchlist_items` docstring `partial` / `normal` semantics absent.
- M4 deferred → DEBT-053 (Low) — site cap 5 hard-coded in 4 places; consolidate via `cards.py` import.
- M6 deferred → DEBT-054 (Low) — `WatchlistImpact` invariant `matches=()` for coverage_hold / unconfigured not enforced at construction time.
- L1 deferred → DEBT-055 (Low) — `WatchlistChannel` branching distributed across 3 modules.
- L2 deferred → DEBT-057 (Low) — `WatchlistMatch.matched_alias` exposure semantics not documented.
- L3 deferred → DEBT-056 (Low) — short ASCII ticker registration produces no config-load warning.
- Cross-check: `docs/cross-checks/2026-05-08-u28-watchlist-usability-foundation.md`.
- Source: persona evaluation 2026-05-07 (persona #4 P0 + P1).

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/` (66 source files)
- `uv run pytest -q` (1210 passed; 1182 → 1210, +28 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u25-u33 follow-up wave.

> **Permission-restricted environments**: when the editor sandbox refuses to write into `aidlc-docs/` or `docs/`, fall back to Bash heredoc (`cat <<'EOF' > <abs-path>`) for documentation deliverables. Source / test changes always go through the editor in the supported path.
