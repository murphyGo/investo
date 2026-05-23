# Code Generation Plan: `u73 watchlist-impact-center-v2`

**Date**: 2026-05-24
**Unit**: u73 watchlist-impact-center-v2
**Stage**: Code Generation
**Status**: Complete (5/5)
**Source**: 2026-05-24 ten-subagent user-quality review of generated segmented briefings and watchlist surfaces
**Estimated Effort**: ~5-8 h
**Dependencies**:
- u18 watchlist-relevance
- u28 watchlist-usability-foundation
- u33 watchlist-depth
- u64 watchlist-entity-matching-and-actionability

---

## Problem Statement

The watchlist layer has useful foundations, but the reader experience is still closer to keyword matching than a daily impact workflow. Reviewers found that:
- Direct watchlist hits are not clearly separated from related macro/sector context.
- Uncertain or rejected false-positive matches are not visible enough for operator/debug trust.
- Short ticker classes still need stronger product-level handling, especially SOL-like and BTC-like ambiguity.
- `site_docs/watchlist/` pages are not yet a daily-first impact center; they feel like configuration/history surfaces.

The user does not need brokerage-style portfolio accounting. They need a daily "what affected my watchlist today, and what was intentionally ignored?" page.

---

## Goal

Create a watchlist impact center v2 that groups daily impacts into:
- Direct
- Related macro/sector
- Uncertain
- Rejected

Only high-confidence Direct/Related impacts should surface in the briefing/Telegram first impression. Uncertain/Rejected groups should support debugging and trust on the watchlist page.

Public/diagnostic boundary:
- `Direct` and `Related` are public-facing groups.
- `Uncertain` and `Rejected` may appear on the public static watchlist page only inside a collapsed `<details><summary>진단: 보류/제외된 후보</summary>` block with source titles redacted to at most source name + hashed/short reason. They never appear in Telegram or the briefing first viewport.
- If redaction cannot be guaranteed, Uncertain/Rejected are emitted only to tests/operator artifacts, not `site_docs/watchlist/`.

---

## Existing Coverage / Deduplication

This unit is not a new watchlist system.

- u18 added watchlist configuration and basic relevance.
- u28 added aliases and boundary-aware matching foundations.
- u33 added depth around watchlist context.
- u64 added strict entity matching, confidence/reason, and false-positive regressions such as BTC vs BTM.

u73 adds workflow grouping, daily page priority, and explicit rejected-match visibility. It should reuse u64 match confidence and reason codes wherever possible.

---

## Scope Boundary

In scope:
- Impact type grouping: Direct / Related / Uncertain / Rejected.
- Short-ticker false-positive regression expansion for SOL/BTC-like cases.
- Daily-first watchlist page rendering.
- Public briefing/notifier rules for which impact groups may surface.

Out of scope:
- User accounts, position sizes, brokerage sync, P&L, or tax lots.
- Buy/sell/hold recommendations.
- New market data sources.
- Replacing the existing watchlist configuration format unless a backward-compatible field is required.

---

## Stage Decision

- **Functional Design — SKIP**. The existing watchlist domain model can be extended with match/impact classification. No new product domain object outside the watchlist layer is required.
- **NFR Requirements — SKIP**. No new external source, dependency, secret, or runtime budget.

---

## Implementation Steps

### Step 1 — Extend impact classification `[x]`
- [x] Define `Direct`, `Related`, `Uncertain`, and `Rejected` groups using existing match confidence/reason data.
- [x] Keep rejected records bounded and redaction-safe.
- [x] Apply the fixed public eligibility above: Direct and selected Related are public-eligible; Uncertain/Rejected are collapsed diagnostics only.
- **Acceptance**: classification table in tests maps common match reasons to the four groups.

Decision table and precedence:

| Group | Source condition | Public surface |
|-------|------------------|----------------|
| Direct | u64 high-confidence structured ticker/symbol match, exact configured alias, or configured Korean asset alias with source evidence | Briefing, watchlist page, Telegram candidate |
| Related | configured sector/keyword/macro relation with explicit source evidence but no exact asset/ticker hit | Briefing body/watchlist page; Telegram only when no Direct exists and line is clearly macro/sector context |
| Uncertain | low-confidence title/summary text match, ambiguous short ticker, or missing source evidence | Collapsed diagnostics only |
| Rejected | u64 false-positive rule, boundary failure, conflicting symbol, or explicit SOL/BTC/BTC-like negative fixture | Collapsed diagnostics only or operator/test artifact |

When multiple groups match the same source item and configured term, choose the highest-precedence public-safe group: Direct > Related > Uncertain > Rejected, except an explicit u64 rejection reason always wins over text-only matches.

### Step 2 — Pin short-ticker false-positive classes `[x]`
- [x] Add SOL false-positive fixtures such as unrelated tickers/names and generic Solana-company references without configured alias evidence.
- [x] Add BTC/BTC-like fixtures beyond the existing BTM regression if gaps remain.
- [x] Preserve valid explicit aliases such as Solana, SOL-USD, Bitcoin, BTC-USD when configured.
- [x] u73 consumes u64 match outputs and only adds grouping/rendering. No matcher change was needed — u64 already rejects SOL/BTC near-misses; u73 surfaces those rejections.
- **Acceptance**: false positives land in Rejected or are suppressed; valid aliases remain Direct.

### Step 3 — Render daily-first watchlist page `[x]`
- [x] Update static watchlist pages so today's impacts are the first content block.
- [x] Separate Direct/Related/Uncertain/Rejected groups with counts and concise reasons.
- [x] Link back to the relevant briefing segment/date when available.
- [x] Canonical renderer: `src/investo/publisher/watchlist_pages.py` writes `site_docs/watchlist/daily.md`; index links to it.
- **Acceptance**: generated page fixture starts with today's impact groups, not configuration prose.

### Step 4 — Briefing and Telegram integration `[x]`
- [x] Public briefing surfaces high-confidence Direct and selected Related impacts only (via `public_impact` projection feeding the existing render path).
- [x] Telegram includes Direct/Related public matches via the existing capped `render_watchlist_impact` Telegram path; diagnostics are projected out before that surface.
- [x] Uncertain/Rejected groups are omitted from public first impression but available on the watchlist daily page.
- **Acceptance**: notifier tests prove no rejected/uncertain diagnostics leak into Telegram.

### Step 5 — Tests and docs `[x]`
- [x] Unit tests for classification, rendering, false positives, and notification filtering.
- [x] Required fixtures: Direct, Related, Uncertain, Rejected, redacted collapsed diagnostics block, Telegram non-leakage assertion, and a daily watchlist page ordering assertion.
- [x] Watchlist group semantics + alias guidance embedded in the generated watchlist index page (`_GROUP_SEMANTICS_GUIDE`).
- [x] Ran targeted watchlist/publisher/notifier tests + full suite + ruff/mypy + mkdocs --strict.

---

## Acceptance Criteria

- **AC-73.1** — Watchlist impacts are grouped as Direct, Related, Uncertain, and Rejected.
- **AC-73.2** — SOL/BTC-like short-ticker false positives are rejected or suppressed while valid aliases still match.
- **AC-73.3** — Daily watchlist pages prioritize today's impacts and link to relevant segment/date.
- **AC-73.4** — Briefing/Telegram first impressions show only high-confidence public-eligible impacts.
- **AC-73.5** — No account, brokerage, P&L, or recommendation feature is introduced.

---

## Tests / Validation

Expected test areas:
- `tests/unit/briefing/test_watchlist*.py`
- `tests/unit/publisher/test_site_index*.py` or watchlist renderer tests
- `tests/unit/notifier/test_summary.py`
- `tests/unit/publisher/test_briefing_replay.py` if replay checks watchlist groups

Minimum local gate:
- Targeted pytest for watchlist/publisher/notifier.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if model signatures change.
- `uv run mkdocs build --strict` if site pages/docs change.

---

## Non-Goals

- Portfolio accounting.
- Personalized risk scoring.
- Paid data sources.
- Replacing existing watchlist config.
