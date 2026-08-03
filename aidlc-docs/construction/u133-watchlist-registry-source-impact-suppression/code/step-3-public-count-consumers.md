# u133 Step 3 — Public count-consumer alignment

## Outcome

- Audited the briefing callout, notifier summary, visual card, per-term pages,
  and daily impact page from matcher input through public rendering.
- The briefing generation path already projects through
  `build_impact_center` + `public_impact`; the notifier extracts that finalized
  public line and therefore does not recompute raw matches.
- The visual-preparation stage now applies the same impact-center projection
  before building the watchlist card.
- The publish stage now passes only `impact_center.public_matches()` to
  per-term path snapshotting and page generation. The full center remains
  available only to the redacted daily diagnostics page.

## Regression coverage

- A visual-stage test combines one `nasdaq-symbol-directory` item and one
  `yahoo-finance-news` item for AAPL and proves the card receives only the
  public news match.
- A publish-stage test proves both pre-snapshot and per-term writers receive
  only the public news match while the daily center retains the registry item
  in `uncertain` diagnostics.
- The existing concurrency test now uses a valid unconfigured watchlist DTO,
  preserving its original ordering/concurrency assertions through the new
  projection seam.

## Validation

- Orchestrator, impact, daily-page, and visual-card suites: 154 passed.
- Scoped Ruff and format: passed.
- Scoped mypy: passed.
- `git diff --check`: passed.
- Fresh-eyes review: approved with no findings; independent targeted
  concurrency/rollback/regression tests (6), Ruff, mypy, and diff check passed.
