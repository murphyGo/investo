# u176 Site shell and navigation — completed

2026-10-10. User authorized all UI implementation and a commit per completed unit. FD/NFR decisions are developer-selected; no individual user design answers are invented.

Korean primary navigation preserves every existing route and adds watchlist. Home has its own wider scope; articles retain76ch reading width. Local tokens follow both Material palettes with actual computed-color checks. Mobile/tablet native shortcuts expose the three primary entries, while Material retains its complete drawer/search/theme owner. Existing labels gain keyboard semantics; Enter/Space avoid duplicate Material handling, Escape restores a visible trigger after overlay cleanup. Static no-JS navigation uses native links/details. Current links expose aria-current and underline/bold selection.

## Validation

- Actual-config built HTML + existing publisher/Material/watchlist tests: **30 passed**,7.52s.
- Strict full-site MkDocs, Ruff/format712, JavaScript syntax and Material image-pair contract passed. Python application code is unchanged; initial6711 full regression remains the runtime baseline and final program regression follows remaining units.
- Actual headless Chromium: **33 cases**. Five actual pages × desktop1440/mobile390 × light/dark; keyboard search/drawer/Escape and palette round trips;1024 tablet focus; JS-off keyboard navigation;200% reflow. No document horizontal overflow, body16px,44px controls, measured normal/muted/focus contrast, actual header/body colors and current-menu aria. [Metrics](../browser-evidence/metrics.json). Screenshots visually inspected.
- Independent ui_home_review found search naming/no-JS keyboard, tablet focus, and current-menu indication issues; all corrected before closure. Final re-review: **APPROVE, residual P1/P2 zero**. Material removes href from a current item; aria-current also applies to that active element.

## Acceptance and scope

AC176.1 routes and native navigation;176.2 scope/read width;176.3 twenty overflow cases;176.4 actual keyboard/no-JS/zoom/contrast/aria;176.5 OG/search/theme/sector regression;176.6 authored FD/NFR and actual build evidence. Archive bytes, publisher/seal/source/API/activation are unchanged. No remote publication performed. Future v3 semantics remain u169/u171.
