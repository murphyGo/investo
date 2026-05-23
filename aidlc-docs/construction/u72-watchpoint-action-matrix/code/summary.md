# u72 watchpoint-action-matrix — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u72 watchpoint-action-matrix
**Status**: Complete (6/6 steps)

## Goal

Render §⑥ "오늘의 관전 포인트" as a bounded **observational monitoring matrix** (not a recommendation engine): each watchpoint exposes Signal / Current / Bullish trigger / Bearish trigger / Confidence / section-local Portfolio implication. The matrix stays compliance-safe (u56 observational-only), source-backed where evidence exists, concise enough for daily reading, and Telegram receives only a compact cue — never the full table.

## Scope

In scope: prompt contract for matrix-shaped watchpoints; deterministic renderer/validator for the matrix; data-limited fallback when triggers cannot be source-backed; compact Telegram summary behavior.
Out of scope: buy/sell signals, position sizing, target prices, portfolio optimization; new accounts/brokerage; replacing u64 entity matching; new numeric data sources; Direct/Related/Uncertain/Rejected watchlist workflow grouping (belongs to u73); charting change.

## Stage Decision

- **Functional Design — SKIP** (per plan). The business rule is a presentation/validation rule over existing evidence (u55 CoreFact/anchor, u52 carryover, u64 WatchlistImpact). The matrix schema is a thin internal rendering dataclass, not a new domain entity. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP** (per plan). No new external service, dependency, secret, or runtime budget. Confirmed at closeout — no NFR file created.

## Deduplication / Non-Overlap (u64 extension, not replacement)

u72 **extends** u64; it does not rewrite the watchlist matcher and does not create a second source/trigger/threshold/implication validation contract (plan "Existing Coverage / Deduplication").

- **u64 reused as the single validation contract**: u72 reuses u64's `check_watchpoint_actionability` (`reader_format.py`) and its three structure regexes (`_WATCHPOINT_SOURCE_RE` / `_TRIGGER_RE` / `_IMPLICATION_RE`) via `_is_structured`. A generic-verb bullet that u64 rejects becomes a `데이터부족` row — never an invented trigger.
- **Watchlist matcher unchanged**: `briefing/watchlist.py` is untouched; u72 consumes its `WatchlistImpact` / evidence-reason strings only for section-local `섹션 내 관심 영향` (no workflow grouping — that is u73).
- **u56 unchanged**: observational language and forbidden investment-advice phrasing remain owned by u56; u72 runs the existing compliance scanner over both the raw bullet prose and the rendered matrix.

## Key Deliverables

- **New** `src/investo/publisher/watchpoint_matrix.py`: the matrix schema + a deterministic renderer/validator. `render_watchpoint_matrix` converts §⑥ bullets into the 6-column matrix; `_clauses` + keyword-bucket clause-slotting populates trigger columns where feasible; `_is_structured` reuses the u64 contract.
- **Changed** `src/investo/orchestrator/pipeline.py`: `render_watchpoint_matrix` wired into the per-segment publish chain. The matrix conversion runs **after** the first `scan_compliance` pass, then a **second** `scan_compliance` runs over the rendered matrix (double-scan rationale below).
- **Changed** `src/investo/briefing/prompts.py`: §⑥ matrix contract added as a Stage-2 rule (observational templates + banned advice vocabulary + source-backed-threshold requirement).
- **Tests**: new `tests/unit/publisher/test_watchpoint_matrix.py` (17) + `tests/unit/notifier/test_summary.py` (+1). Net delta +18.

## Matrix Schema

6 columns: `관찰 신호 | 현재 | 상방 확인 조건 | 하방 확인 조건 | 신뢰도 | 섹션 내 관심 영향`.

- `MAX_VISIBLE_ROWS = 6` with an overflow note when exceeded.
- Confidence is a closed set `{높음, 보통, 낮음, 데이터부족}`:
  - **높음** — verified numeric (u55 anchor) + non-limited segment coverage.
  - **보통** — u64 source-backed watchpoint, no verified numeric threshold (or partial coverage).
  - **낮음** — carryover/topic evidence only, no fresh numeric/source anchor.
  - **데이터부족** — segment coverage limited/failed, required source/anchor missing, or the bullet is non-structured.
- Rendered as a compact Markdown table; in-cell pipes are escaped.
- **Idempotent** — re-render is a no-op (header presence detected).
- **§⑥-body-local** — only the §⑥ body is rewritten; all other sections and the disclaimer footer are byte-preserved.

## Evidence Precedence (row population)

1. u55 verified anchor/core fact → `현재` and numeric trigger text.
2. u64 watchpoint evidence/reason → `관찰 신호` and source-backed rationale.
3. u52 carryover item → prior context only; cannot create a new trigger by itself.
4. Otherwise render one `데이터부족` row and omit invented triggers.

## Double Compliance Scan (u56 invariant preserved)

The matrix conversion runs **after** the first `scan_compliance` so the raw bullets are scanned as prose **before** the P0 compliance gate can be masked by table-cell structure (a table cell could otherwise hide advice wording from the prose scanner). A **second** `scan_compliance` then runs over the rendered matrix document. Matrix cells copy LLM bullet text only — no buy/sell/목표가 vocabulary is introduced; observational-only. `verify_disclaimer` and the numeric verifier are unchanged.

## Module Boundary

`watchpoint_matrix.render_watchpoint_matrix` is publisher-internal over prepared markdown; the orchestrator wires it into the per-segment publish chain. No briefing/notifier import added — orchestrator-only cross-unit import rule upheld. The §⑥ prompt rule lives in `briefing/prompts.py` (briefing-internal).

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-72.1 | §⑥ renders bounded matrix with Signal/Current/Bullish trigger/Bearish trigger/Confidence/Portfolio implication | MET | 6-column schema + `MAX_VISIBLE_ROWS=6` overflow note; `test_watchpoint_matrix.py` schema tests |
| AC-72.2 | Missing triggers require explicit `데이터부족`; generic monitor verbs alone are not enough | MET | u64 `check_watchpoint_actionability`/`_is_structured` reuse; generic `확인/점검` fixture → `데이터부족` row |
| AC-72.3 | Rows consume verified anchors, carryover, watchlist evidence without inventing facts | MET | evidence precedence 1-4; per-evidence-type row tests, no cross-segment leakage |
| AC-72.4 | Compliance scanner blocks investment-advice wording | MET | double `scan_compliance` (raw bullets then rendered matrix); banned-vocab prompt rule + tests |
| AC-72.5 | Telegram concise; does not embed the full matrix | MET | `test_summary.py` asserts no large table in Telegram payload (compact cue only) |

## FD Divergences Ratified

None. FD was SKIP (presentation/validation contract over existing models; no new entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

- **DEBT-074** (Low) — clause-slotting heuristic (`_clauses` + keyword bucket) is regex-based and can under-populate the trigger columns on non-standard bullets; suggested fix is to plumb typed evidence (u55 CoreFact / u52 carryover / u64 WatchlistImpact) directly into the matrix builder as an additive improvement.

## Potential Risks

- **Clause-slotting under-population**: the trigger-column slotting heuristic is regex/keyword-bucket based, so an unconventional §⑥ bullet can leave a trigger column thin. This degrades **gracefully** to a `데이터부족` row (not a misfire / not an invented trigger), so reader-trust and compliance are preserved. Tracked as DEBT-074.

## Verification Gate

- ruff check: clean
- ruff-format: clean
- mypy --strict: 140 files clean
- pytest: 2561 passed (+18 net: 17 new watchpoint-matrix + 1 notifier)
- mkdocs build --strict: pass
