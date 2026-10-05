# Public sector dashboard operations

## Active contract

Public route: <https://murphygo.github.io/investo/sectors/>. The static page and
`sectors/latest.json` contain derived metrics only, for SPY and eleven Select Sector ETFs.
The source is free, unauthenticated Yahoo daily closes (`yahoo-chart-daily-v2`, schema 2).
Public-use permission remains **unverified**, under the user's u145 operator exception;
this is not a license grant. No paid fallback or key is used. See the
[source amendment](../aidlc-docs/construction/u145-sector-dashboard-public-hf-limited-radar/source-qualification/2026-10-04-yahoo-public-amendment.md).

## Refresh and publish

`sector-dashboard.yml` runs only on main, manually or weekdays at **21:35 UTC**
(the following day **06:35 Asia/Seoul**). Holiday runs resolve the latest completed session.
The pinned 2026 NYSE calendar handles early closes; an unsupported year fails closed before
network access. Update/review the calendar before the first 2027 session.

```sh
gh workflow run sector-dashboard.yml --ref main
gh run list --workflow sector-dashboard.yml --branch main --limit 5
gh run view RUN_ID --log
```

The job installs locked runtime/docs dependencies, checks the synthetic resource envelope,
then runs `scripts/publish_sector_dashboard.py --write`. This separate CLI collects through
the already-qualified production adapter and atomically stages the canonical public pair.
It accepts no URL, ticker, date, key or output-path override.

Before repository publication, `--verify-only` checks canonical pair integrity and
`mkdocs build --strict` verifies the site. Only `site_docs/sectors/index.md` and
`site_docs/sectors/latest.json` are staged. A normal fast-forward push is required; if another
writer advances main, the run fails and a fresh manual rerun recollects current data. There is
no force push, automatic merge of snapshots, raw-data artifact or Telegram notification.

The job explicitly dispatches `pages.yml`: GITHUB_TOKEN pushes do not trigger push workflows.
An unchanged valid pair also dispatches Pages, allowing deployment recovery without a data
commit. Pages verifies the pair again before strict build and atomic deployment. Inspect
both workflow results; successful collection alone is not evidence of a successful deploy.

## Outcomes and recovery

| Outcome | Files and publication | Exit status |
| --- | --- | --- |
| `promoted`, normal | Fresh 11-sector pair staged, validated, committed if changed, Pages dispatched | 0 |
| `unchanged`, normal | Pair bytes and commit preserved; Pages dispatched | 0 |
| `promoted`/`unchanged`, partial | Fresh 8–10-sector pair may publish with explicit missing-sector states | 2 |
| `held_last_good` | Collection/build failed; verified prior pair, identity and as-of remain unchanged; no publication | 2 |
| `blocked` | First failure or damaged/missing store; no usable new pair and no publication | 2 |

Partial publication intentionally leaves the collection job red **after** dispatching Pages.
The summary separates attempt freshness/coverage from the stored outcome/as-of and reports
bounded request counts, duration, CPU and closed source/build reasons. HTTP response text,
raw bars, URLs and credentials never appear. The page says **generation-time freshness**;
its as-of date does not advance during a failure.

For `auth.rejected`, stop and requalify unauthenticated access; do not add keys or bypasses.
For transport/throttle errors, wait and rerun within existing limits. For stale/insufficient
data, retain the prior page until the provider recovers. For `build.store`, inspect the
canonical pair and recover from a known validated repository commit; never manufacture a
successful identity. For resource/schema errors, reproduce with synthetic data before changing
code. The [probe runbook](sector-dashboard-probe-runbook.md) documents the source boundaries.

If collection succeeded but Pages failed, rerun the dedicated workflow or dispatch Pages
against current main after verifying the pair. A failed Pages build/deploy retains the last
deployed site. Compare live `latest.json` snapshot identity with the committed pair and the
snapshot identity embedded in HTML; confirm the displayed as-of and 11 sector rows.

```sh
gh workflow disable sector-dashboard.yml
gh run cancel RUN_ID
```

Disabling stops future refreshes; cancel an already-running job separately. The last static
page remains available. Removing the public product requires a reviewed change to remove
the sector files, navigation and Pages pair gate together, followed by Pages deployment.
The manual read-only probe remains independent. No daily-briefing or private NAV workflow
is coupled to this activation.

Browser visual acceptance is **WAIVED / NOT_EXECUTED** by the user's 2026-09-27 decision;
canonical/static HTML checks must not be reported as a browser visual pass.
