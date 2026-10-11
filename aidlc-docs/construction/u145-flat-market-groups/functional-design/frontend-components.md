# Flat radar frontend

At the top: date/freshness and view coverage, accessible `분야별 비교` / `시장 요약`
switch, then category filters (`전체`, `기술`, `소비`, `금융`, `기타`). Default groups
are peers; no parent/child tree. Industry/theme/representative labels and measured
ETF or eight-stock basket are visible. Summary cards precede diverging21D bars,
regime grid and detailed ranked rows. Sources/methodology follow both views.

Only fixed generated DOM is used. JavaScript has no fetch, dynamic HTML injection,
external library or hidden source data. Material navigation initializes once per
dashboard. Tabs use keyboard navigation and ARIA selected/controls; filter buttons
use pressed state. Stable data-testid attributes identify every control. Text and
values remain available without color; absent JS leaves both views readable.

Filters never recompute ranking or rescale bars; this basis is stated near controls.
Regime chip/count visibility follows the filter. Dark/light and390px/desktop layouts
reuse scoped CSS. Existing Browser acceptance stays waived; supplementary viewport
inspection may inform repairs but is not labeled Browser acceptance.
