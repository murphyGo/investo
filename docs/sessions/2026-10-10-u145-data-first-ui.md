# u145 — data-first dashboard presentation

## Authorization and scope

The user requested core data/charts first, secondary source information below,
and a more polished presentation on 2026-10-10. The prior instruction to finish
public publication remains authorization to deliver this bounded UI follow-up.
The isolated `.tmp/u145-ui-20261010` worktree starts from current remote main
`838bed607e1e170893de8f9230634a1f8568a06e`; unrelated dirty root and site-wide UI
planning work are preserved.

The active [presentation amendment](../../aidlc-docs/construction/plans/u145-sector-radar-data-first-ui-plan.md)
supersedes the historical source-first ordering in R26/AC-5.1. The original
Yahoo permission operator exception and Browser `WAIVED / NOT_EXECUTED` decision
remain. This follow-up changes presentation, not data collection or calculations.

## Delivered behavior

- Date, generation-time freshness and actual available/comparable coverage stay
  directly below the title.
- Four summary cards precede 21-session SPY-relative diverging bars and a
  four-regime board. All chart values and classifications come from the existing
  typed snapshot. Negative, zero and unavailable values remain explicit.
- All eleven detailed rows follow in existing relative-rank order.
- Visible sources, attribution and qualifications follow the data. Only the
  longer methodology is expandable; disclaimer and identity marker remain.
- Scoped CSS includes narrow-screen layouts and both Material themes. The page
  makes no client-side source requests and adds no dependencies.

## Local verification

- Focused renderer/store/build suite: 67 passed initially; the remaining build
  test required the existing explicit freshness label. Restoring that label
  resolved it: 1 passed in 25.64s. All 68 selected tests passed across these runs.
- Ruff check and format: PASS, 706 Python files. Strict mypy: PASS, 302 source files.
- Anthropic, paid-provider, curated-asset and image-store policy guards: PASS.
- Canonical pair verification: PASS. The existing JSON is byte-identical and its
  snapshot remains
  `sha256:6ac61b30de1c6133f411bb16e426a42d89ee727640dcb4f2bf188ddb0e9057f8`,
  as-of 2026-10-08, normal, 11/11 sectors.
- Strict MkDocs build and built Material theme/rendered-pair guard: PASS.
- Built HTML: 4 cards, 11 bars, 4 regime cells and 11 detailed rows; summary and
  charts precede the table, then sources; the sector stylesheet is loaded.
- A supplementary local headless Chrome screenshot at 1440×1600 was inspected
  in slate mode. Cards and charts render before the detailed table. This is not
  the waived Browser acceptance or an empirical mobile/light-theme acceptance.
- Separate read-only code reviewer: APPROVE, no blocking findings; typed data,
  identity, missing states, geometry, source disclosures, scoped CSS and
  refresh/store compatibility reviewed.

## Publication

Public destination: <https://murphygo.github.io/investo/sectors/>.
UI commit `2e701c4211cf2d574a94591bb1fb41953d61d2ec` was pushed to remote main
and confirmed with `git ls-remote`.

- Initial Pages [37965908527](https://github.com/murphyGo/investo/actions/runs/37965908527)
  succeeded for build and deploy on the exact UI commit.
- Live HTML, sector CSS and JSON returned HTTP200. The live page has 4 cards and
  11 bars preceding the table, then visible sources. CSS bytes equal the scoped
  stylesheet and JSON bytes equal the original snapshot; the HTML identity agrees.
- Normal refresh [37966083788](https://github.com/murphyGo/investo/actions/runs/37966083788)
  succeeded: fresh 2026-10-08, 12 successful responses, zero failures, 11/11
  available/comparable, status `unchanged`, same snapshot. Collection 880ms,
  total 2002ms, CPU1189ms. Maximum-shape gate also passed (12×1MiB/140 rows,
  wall951ms, CPU941ms, incremental RSS27967488 bytes).
- Refresh-dispatched Pages [37966152984](https://github.com/murphyGo/investo/actions/runs/37966152984)
  also succeeded on the exact UI commit. Refresh introduced no data commit.
- Exact code-quality [37965908536](https://github.com/murphyGo/investo/actions/runs/37965908536)
  succeeded on the UI commit: **6,693 tests passed in 556.12s**, Ruff/format706,
  mypy302, all four policy guards, strict MkDocs and Material rendered-pair guard.

The public UI and refresh path are delivered. The final evidence-only closeout
changes no executable code, generated page, stylesheet or snapshot.
