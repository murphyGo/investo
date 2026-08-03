# u133 Code Generation Summary — Watchlist Registry Source Impact Suppression

## Outcome

u133 is complete. Static exchange/company registries still support entity and
fact verification, but they no longer create public watchlist events, counts,
visual rows, per-term history, §⑤ registry-only narrative, or Telegram details.

## Delivered contracts

1. `SourceSpec.reference_registry` defaults false and is true for exactly
   `nasdaq-symbol-directory` and `sec-company-facts`.
2. Registry-evidenced accepted matches route to redacted diagnostics with
   `reason="reference-registry"` before normal Direct/Related classification.
3. Every public consumer counts only `WatchlistImpactCenter.public_matches()`;
   the daily page alone retains the full center inside collapsed diagnostics.
4. Stage 2 treats registry rows as entity-identification evidence only and
   forbids registry-only §⑤ subsections.
5. The impact-center projection remains the deterministic backstop; no new
   post-render scanner exists.

## Regression evidence

A redacted 2026-06-30 fixture carries six MSFT/NVDA/TSLA registry matches and
zero non-registry rows. Site and Telegram use the exact established no-public
state; the daily page has zero public rows and six uniquely contained redacted
diagnostics; full titles never render.

## Validation

- Ruff/format: 11 changed Python files passed.
- mypy: 248 source files passed.
- Planned unit scope: 3,138 passed.
- Lock, fixture JSON, and diff integrity: passed.
- Cumulative fresh-eyes review: AC-133.1-6 and Fixed Contracts 1-5 approved
  with no findings; independent 23-test target passed.

## TECH-DEBT

None added.
