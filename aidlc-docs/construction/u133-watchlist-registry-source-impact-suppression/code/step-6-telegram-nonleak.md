# u133 Step 6 — Telegram registry non-leakage

## Outcome

- Extended the existing u73 diagnostics non-leak test with a real
  `nasdaq-symbol-directory` AAPL match.
- Added a terminal typed-summary regression using both pinned registry sources.
- The projected Telegram watchlist uses the existing no-public-impact state;
  the final segmented notification contains no raw registry count, diagnostic
  reason, source name, or title fragment.

## Boundary

The notifier remains a formatter of validated `PublicNotificationSummary`
DTOs. It does not receive raw matcher results or reimplement source-spec
classification. Registry suppression remains upstream in the deterministic
impact-center projection.

## Validation

- Impact + notifier summary suites: 82 passed.
- Scoped Ruff and format: passed.
- `git diff --check`: passed.
- Fresh-eyes review initially found one Low test-adequacy gap because the
  renderer empty state was checked only as a final-summary substring. Exact
  renderer equality before DTO construction closed it; re-review approved with
  no findings.
