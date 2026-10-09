# u145 — public Pages activation

## Authorization and implementation

The user's `진행시켜` after Step 5 completion authorized main integration, actual public
publication and automatic refresh. Work used the isolated
`.tmp/u145-public-activation-20261005` worktree, preserving the dirty root and newer main work.
Free-only, unverified Yahoo permission under the operator exception, and Browser
**WAIVED / NOT_EXECUTED** remain unchanged.

The qualified implementation (`ec7ac84b`, five successful Actions probes) was integrated
separately at `782ace94`. Public activation is a distinct commit `1a753c7c`; subsequent
main integration `6d91aaaa` preserves `fc673d3a` and its independent news/archive updates.
Review repair `6b371a1c` retains honest last-good status on unsupported-calendar failures.

The new build composition and fixed write/verify CLI reuse the qualified collector, metric
models, renderer and transactional store. The dedicated main-only workflow runs weekdays
21:35 UTC (next day 06:35 KST), publishes a fresh normal/partial canonical pair, and explicitly
dispatches Pages. Partial output can publish but the collection job exits 2. Failed collection
holds the prior validated bytes/date/id; first failure and corrupt prior state block. Only
the two derived sector files are staged; concurrent main changes reject the push without
force/merge. An unchanged valid run can recover a failed Pages deployment without data churn.

Pages verifies the canonical pair before strict MkDocs build. The navigation includes
`미국 섹터`; the page labels freshness at generation time so held bytes do not imply a new
check. No Telegram, private NAV or daily-briefing composition changed.

## Review and local validation

Independent reviewer `u145_activation_review` applied concurrency, data integrity, error
contract, lifecycle and security protocols. One P2 was fixed: a calendar failure had retained
the files but reported `blocked` even with a valid prior pair. It now reports `held_last_good`
with the original identity/date. Three zero-network cases (valid/absent/damaged store) passed
the reviewer's direct rerun; final independent approval has zero remaining findings.

- Initial focused tests: 105 tests passed; teardown detected the operator's concurrent
  bootstrap generation under `site_docs/sectors`. No testcase failed. Subsequent testing uses
  committed/fixed generated files, with no concurrent publication mutation.
- Initial complete integration run: 6,441 passed, one obsolete u139 guard failed because it
  prohibited the newly authorized public Pages verifier. Narrow path/exact-command exceptions
  preserve the private no-network/no-public-pipeline boundary.
- Review repair/public-build/private suite: **72 passed in 85.90 s**.
- Actual isolated workflow git tests: **2 passed in 3.18 s**; exact pair-only staging,
  unchanged commit identity, concurrent remote-main preservation.
- Ruff check/format: pass, **687 files**. Strict mypy: pass, **299 source files**.
- No-paid/provider, no-Anthropic, curated-assets and image-store guards: pass; lock check pass.
- Strict MkDocs, canonical public pair and Material stylesheet/rendered-pair checks: pass.
- Built public HTML: 11 sector rows, 10 table headers, responsive viewport metadata,
  source/coverage before the metric table, embedded snapshot id and exact JSON copy verified.
  These are static checks, not Browser visual acceptance.
- Synthetic maximum input: **12 × 1 MiB**, 140 rows each, 12 requests, CPU **1,151 ms**,
  wall **1,253 ms**, peak RSS above baseline **48,365,568 bytes**, passed.
- Live bootstrap: **promoted**, fresh target/as-of **2026-10-02**, **12/12 requests**,
  **11/11 available and comparable sectors**, no failure; collection **1,317 ms**,
  total **4,772 ms**, CPU **3,504 ms**. Only derived files were retained.
- Snapshot: `sha256:838023f96f0c8deee3d2839849d296f0b5f7a7e8815d998f09bacdd7150cd2ee`.

Final full regression and live publication evidence: pending.

## Operational acceptance

Public destination: <https://murphygo.github.io/investo/sectors/>.
Current operational acceptance remains pending; no deployment success is claimed by the
local bootstrap alone. Exact main SHA, refresh/Pages/quality run IDs and live HTML/JSON
identity will be recorded here after deployment.

Traceability: [cross-check](../cross-checks/2026-10-06-u145-public-activation.md),
[public runbook](../sector-dashboard-public-runbook.md),
[Step 5 source record](2026-10-05-u145-yahoo-public-source.md),
[five-run evidence](2026-10-05-u145-yahoo-actions-evidence.json).
