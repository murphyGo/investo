# u135 Code Generation Summary — Watchpoint current values and fallback

## Outcome

u135 is complete. Public watchpoint cards no longer retain a source-shaped
`현재:` when a matching reconciled value exists, and a data-rich segment no
longer collapses to the bounded note solely because every LLM row was filtered.

## Delivered contracts

1. Immutable segment-scoped payloads expose only bounded reconciled anchor,
   CoinGecko, funding/OI, fear-and-greed, and CFTC scalar candidates.
2. Exact semantic/token precedence resolves a real current value; an unresolved
   payload-backed non-value follows the existing u110 invalid-row path.
3. Zero surviving rows trigger at most two deterministic cards in the fixed
   RANGE/domestic close-reference → CFTC → F&G order, with closed Korean
   templates. The domestic reference card reuses its trusted close and invents
   neither a percentage nor a 52-week range.
4. Synthesized rows reuse the u64 structure and compliance owners; a rejected
   row is dropped without blocking publication.
5. A typed private synthesized-card count crosses the u144 pre-seal lifecycle
   and reaches quality history without changing public rendering.

## Regression evidence

- The 2026-06-29 crypto source-in-value shape resolves to
  `$60,284.00 (+2.23%)` with semantic indicator precedence preserved.
- The 2026-06-30 US bounded-note shape renders RANGE then CFTC with count 2.
- The production u67/u138 close-only domestic anchor renders one explicit
  close-reference card with no derived percentage.
- Empty payload, partial compliance drop, and repeated application are
  byte-stable.
- RANGE, domestic close-reference, CFTC, FEAR, and GREED pass the shared
  structure and compliance contracts, including forced partial/all rejection
  behavior.

## Validation

- Ruff/format: 17 changed Python files passed.
- mypy: 250 source files passed.
- Publisher and orchestrator: 1,464 tests passed.
- Lock, fixture JSON, and diff integrity: passed.
- No `site_docs` change; the conditional MkDocs gate did not apply.
- Cumulative fresh-eyes review: AC-135.1-6 and Fixed Contracts 1-7 approved
  with no findings.

## TECH-DEBT

None added.
