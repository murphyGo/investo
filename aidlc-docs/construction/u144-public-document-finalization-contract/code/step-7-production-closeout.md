# U-144 Step 7 Production Closeout

## Exact-date replay

`daily-briefing.yml` run `29901183324` replayed
`target_date=2026-07-17` at implementation head `614b3da`.

- Generation completed with `ok=3 failed=0`.
- Domestic equity, US equity, and crypto each emitted
  `state=finalized codes=none`.
- The publisher wrote all three canonical archive paths:
  `archive/domestic-equity/2026/07/2026-07-17.md`,
  `archive/us-equity/2026/07/2026-07-17.md`, and
  `archive/crypto/2026/07/2026-07-17.md`.
- Publication committed and pushed bot commit `28173ce`; Telegram notification
  completed with message ID `74`.
- The pipeline completed with `status=success`, `PIPELINE_RC=0`, and the daily
  workflow conclusion was `success`.
- The separately dispatched Pages run `29901936785`, at head `28173ce`,
  completed with `success`.

This closes AC-144.14 for the original failed date.

## Current-date characterization and repair

The first no-input current-date run `29902837609` resolved the normal target
date to `2026-07-21` and generated all three drafts. Crypto finalized, while
domestic and US equity were reported as trust-blocked with
`summary.truncated_mid_token`. The intended partial contract committed
`6f3053a`, delivered Telegram message `75`, exited 2, and dispatched successful
Pages run `29903899895`.

The trust blocks were presentation false positives, not genuine trust-gate
failures. E3 invokes the canonical surface scanner once per indexed region,
but the scanner necessarily treats the start of an isolated input as a
document first viewport. Therefore the first line of a section body could
receive the viewport-only `summary.truncated_mid_token` code. Region policy
then correctly blocked that non-viewport required region, accidentally
escalating a presentation artifact to segment absence.

Commit `39381dc` retains this scanner finding only when the indexed owner is an
actual `first_viewport` block. The same text in any section body no longer
creates the viewport-only finding, while a real viewport occurrence remains
detectable and uses the existing deterministic replacement policy.

Validation at the repair commit:

- U-144 unit scope: 422 passed;
- Ruff check and format check: passed;
- strict mypy for the changed source: passed;
- `git diff --check`: passed.

## Current-date successful run

The no-input retry `29906481364` ran at head `39381dc` and again resolved
`target_date=2026-07-21`.

- Generation completed with `ok=3 failed=0`.
- Domestic equity, US equity, and crypto each emitted
  `state=finalized codes=none`.
- The publisher wrote all three canonical archive paths:
  `archive/domestic-equity/2026/07/2026-07-21.md`,
  `archive/us-equity/2026/07/2026-07-21.md`, and
  `archive/crypto/2026/07/2026-07-21.md`.
- Publication committed and pushed bot commit `e3c8b2f`; Telegram notification
  completed with message ID `76`.
- The pipeline completed with `status=success` in 1,150.095 seconds,
  `PIPELINE_RC=0`, and the daily workflow conclusion was `success`.
- The separately dispatched Pages run `29907789648`, at head `e3c8b2f`,
  completed with `success`.

The exact-date and current-date evidence together close the remaining Step 7
checklist and AC-144.14 without weakening numeric, entity, compliance,
structure, disclaimer, or notification-summary trust blocks.
