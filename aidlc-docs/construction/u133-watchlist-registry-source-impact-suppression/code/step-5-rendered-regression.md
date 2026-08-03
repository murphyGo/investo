# u133 Step 5 — 2026-06-30 rendered regression

## Fixture

Added a minimum reconstructed fixture for the production incident:

- target date `2026-06-30`;
- watchlist tickers `MSFT`, `NVDA`, and `TSLA`;
- one Nasdaq directory row and one SEC company-facts row per ticker;
- six accepted registry matches and zero non-registry matches.

The fixture contains no raw payload, URL, credential, notification destination,
or private metadata.

## Rendered contract

- The public impact projection contains zero rows and the site callout renders
  the existing no-public-impact sentence, not an `N건 확인` count.
- The daily page renders `직접 0 · 관련 0 · 보류 6 · 제외 0`.
- Every term/source/reason signature appears only between `<details>` and
  `</details>`.
- Full registry titles do not appear on either the site or daily surface.

## Validation

- Rendered regression: 1 passed.
- Cumulative impact/daily/rendered scope: 37 passed.
- Fixture JSON parse: passed.
- Scoped Ruff/format and `git diff --check`: passed.
- Fresh-eyes review initially found one Low test-adequacy gap: the empty-state
  assertion was not exact and only the pre-`<details>` public region was
  checked. Exact equality plus full before/after public-region and one-occurrence
  assertions closed it; re-review approved with no findings.
