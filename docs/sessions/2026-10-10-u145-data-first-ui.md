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
Scoped commit, exact-SHA quality CI, Pages deployment, live HTML/CSS/JSON checks
and the normal refresh path are verified during delivery. Final run evidence is
appended here after publication.
