# Private Report Components: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Status**: Complete — approved 2026-07-18
**Surface**: local `report.md` only; no web application or public page
**Parent plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-functional-design-plan.md`

## 1. Surface Contract

The private report intentionally mirrors the future dashboard's information hierarchy
without becoming a public artifact. It is deterministic Markdown derived entirely
from `SectorDashboardSnapshot`; it has no client state, API request, JavaScript,
navigation entry, HTML page, SVG, or Telegram projection.

## 2. Component Order

| Order | Component | Required input | Visible states |
| ---: | --- | --- | --- |
| 1 | `PrivateValidationBanner` | snapshot scope flags | always |
| 2 | `CoverageHeader` | coverage, as-of, source id | always |
| 3 | `RadarSummary` | rank and regime records | normal/partial only |
| 4 | `SectorMetricTable` | sector records | normal/partial; reduced in warming-up |
| 5 | `TextQuadrant` | primary regimes | normal/partial only |
| 6 | `NeutralBandSensitivity` | sensitivity regimes | normal/partial only |
| 7 | `DiagnosticSummary` | redacted diagnostics | when diagnostics exist or coverage is not normal |
| 8 | `PrivateMethodNote` | fixed labels/policy ids | always |

The order is stable. Components are omitted only by the visibility rules below.

## 3. Component Definitions

### C1. `PrivateValidationBanner`

Fixed content:

- `PRIVATE VALIDATION`
- `NAV 수익률 기준`
- `실제 시장 OHLCV 아님`
- `공개 게시 금지`

The banner is the first content after the H1 and cannot be collapsed or removed by a
coverage state.

### C2. `CoverageHeader`

Fields:

- status: `normal / partial / warming_up / insufficient`
- `as_of_date` or `기준일 없음`
- available sectors as `{n}/11`
- benchmark availability
- source label `State Street NAV History (private input)`
- primary policy id and 10 bps band

It never prints input filenames or paths.

### C3. `RadarSummary`

Normal/partial content:

- top two and bottom two sectors by `relative_rank_v1` when at least four ranked
  records exist;
- count by each complete regime;
- number of records with unavailable 63D metrics;
- one fixed statement that rank measures SPY-relative NAV momentum, not sector health
  or investability.

The summary is hidden for warming-up/insufficient. It contains no generated narrative
or causal explanation.

### C4. `SectorMetricTable`

Normal/partial columns:

1. rank
2. ticker
3. primary regime
4. NAV return 1D
5. NAV excess vs SPY 5D
6. NAV excess vs SPY 21D
7. NAV excess vs SPY 63D
8. 5D relative acceleration
9. NAV realized volatility 20D
10. NAV max drawdown 20D
11. availability note

Warming-up columns are limited to ticker, NAV return 1D/5D, NAV excess 1D/5D, and
availability note. Formal rank/regime/21D/63D/volatility/drawdown columns are absent.

Missing values render as `데이터 부족 ({reason})`, never `0` or an empty cell.

### C5. `TextQuadrant`

The report uses four text groups in fixed order:

1. `주도 (leading)`
2. `둔화 (weakening)`
3. `회복 (recovering)`
4. `부진 (lagging)`

Each group lists tickers in rank order. `insufficient` sector records appear in a
separate `상태 계산 불가` line below the four groups. There is no chart coordinate,
SVG, or inferred position beyond the two regime axes.

### C6. `NeutralBandSensitivity`

Columns are ticker plus regime at `0 / 5 / 10 / 15 / 20 bps`. The 10 bps column is
marked primary. A deterministic change count states how many sectors differ from the
primary regime at each alternate band.

This component contains the fixed label `private policy sensitivity only` and cannot
claim that a band is approved for public use.

### C7. `DiagnosticSummary`

Groups diagnostics by issue code and displays only:

- issue code;
- affected ticker where allowed;
- count;
- approved date range or metric name fields.

Repeated instances collapse to one row with a count. Paths, raw cell values, sheet
names, and exception messages are forbidden.

### C8. `PrivateMethodNote`

Fixed notes:

- returns are simple NAV returns;
- excess return subtracts SPY over identical dates;
- acceleration compares adjacent non-overlapping 5-day excess-return windows;
- volatility is annualized from NAV log returns;
- rank excludes volume, flow, earnings, volatility, and drawdown;
- u140 remains blocked and this artifact grants no public-data right.

## 4. State Behavior

| Coverage | Banner | Header | Summary | Metric table | Quadrant | Sensitivity | Diagnostics |
| --- | :---: | :---: | :---: | --- | :---: | :---: | :---: |
| normal | show | show | show | full | show | show | optional |
| partial | show | show | show | available sectors + missing notes | show | show | show |
| warming_up | show | show | hide | reduced 1D/5D | hide | hide | show |
| insufficient | show | show | hide | hide | hide | hide | show |

An as-of mismatch always follows the insufficient row, regardless of the number of
otherwise valid sector files.

## 5. Formatting and Accessibility

- H1/H2 headings and Markdown tables provide the complete structure without color.
- Regimes always include Korean and canonical English identifiers at first use.
- Positive/negative meaning is expressed with signs and text, not emoji or color.
- Percentages and percentage points are labeled distinctly.
- Stable column/order rules make two reports diff-friendly.
- Long diagnostics are grouped and counted rather than copied verbatim.

## 6. Forbidden Surface Content

- `가격수익률`, exchange volume, dollar volume, flow, shares, AUM, holdings, earnings.
- Provider workbook URL, local manifest/workbook/output path, raw row, or cell value.
- Buy/sell language, target price, forecast, recommendation, or causal narrative.
- Public readiness, license approval, Pages publishing, or TradingView-data claim.
- Links into `archive/`, `site_docs/`, or any public repository artifact.
