# u105 Code Generation Summary

## Overview

u105 adds official source-of-record macro actual rows from BLS and BEA and connects them to the existing u59 macro lifecycle contract. The unit adds no paid provider and does not synthesize consensus, forecast, or surprise values.

## Files Changed

- Created: `src/investo/sources/bls_macro_actuals.py`
- Created: `src/investo/sources/bea_macro_actuals.py`
- Created: `tests/unit/sources/test_bls_macro_actuals.py`
- Created: `tests/unit/sources/test_bea_macro_actuals.py`
- Created: `tests/unit/sources/fixtures/api/bls-macro-actuals/`
- Created: `tests/unit/sources/fixtures/api/bea-macro-actuals/`
- Modified: `src/investo/sources/__init__.py`
- Modified: `src/investo/sources/aggregator.py`
- Modified: `src/investo/sources/tiers.py`
- Modified: `src/investo/sources/fred_economic_calendar.py`
- Modified: `src/investo/briefing/segments.py`
- Modified: `src/investo/_internal/redaction.py`
- Modified: `tests/unit/_internal/test_redaction.py`
- Modified: `tests/unit/briefing/test_macro_carryover.py`
- Modified: `tests/unit/sources/test_fred_economic_calendar.py`
- Modified: `tests/unit/sources/test_plugin_contract.py`

## Implementation

- Added `bls-macro-actuals` for bounded BLS series: CPI, core CPI, payroll employment, unemployment, average hourly earnings, labor-force participation, PPI, and JOLTS.
- Added `bea-macro-actuals` for bounded BEA NIPA actual rows: GDP, PCE, and core PCE.
- Added `BEA_API_KEY` graceful-degradation and redaction coverage. Missing BEA key raises terminal `SourceFetchError` before HTTP.
- Registered both adapters as S-tier, US market-window, US segment, and US macro-actual health sources.
- Stamped official actual rows with `macro_event_key`, `actual_value`, optional `prior_value`, `release_period`, `unit`, `source_url`, and `observed_at`.
- Updated FRED calendar rows for CPI/PPI/NFP/GDP/PCE to stamp matching source-period keys so scheduled and actual rows collapse through u59 lifecycle without inventing release dates from actual endpoints.

## Acceptance Criteria

| AC | Result | Evidence |
| --- | --- | --- |
| CPI, payrolls, PCE, and GDP actual rows are available from official sources | Met | `test_fetch_returns_official_cpi_and_payroll_actuals`, `test_fetch_returns_gdp_and_pce_actuals_without_secret_leak` |
| Actual rows carry canonical keys joining calendar rows | Met | FRED calendar period-key update plus `test_bls_actual_confirms_fred_cpi_schedule_by_canonical_key`, `test_bea_actual_confirms_fred_gdp_schedule_by_canonical_key` |
| No consensus or surprise values are synthesized | Met | BLS/BEA tests assert no `consensus` or `surprise` metadata |
| Missing API keys or endpoint errors degrade per adapter | Met | BEA missing-key/error tests and BLS malformed/empty isolation tests |
| R13 secret hygiene is preserved | Met | `BEA_API_KEY` redaction tests and fixture no-secret tests |
| Macro lifecycle collapses scheduled + actual rows | Met | CPI and GDP lifecycle tests |

## Validation

- `uv run pytest tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py tests/unit/sources/test_fred_economic_calendar.py tests/unit/briefing/test_macro_carryover.py -q` -> 48 passed
- `uv run pytest tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py -q` -> 66 passed
- `uv run pytest tests/unit/_internal/test_redaction.py tests/unit/sources/test_no_paid_apis.py -q` -> 59 passed
- `uv run ruff check src/investo/sources/bls_macro_actuals.py src/investo/sources/bea_macro_actuals.py src/investo/sources/fred_economic_calendar.py tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py tests/unit/briefing/test_macro_carryover.py` -> clean
- `uv run mypy --strict src/investo/sources src/investo/briefing` -> clean over 100 source files
- `uv run python scripts/check_no_paid_apis.py` -> clean
- `git diff --check` -> clean

## Scope Notes

No paid macro provider, forecast/consensus feed, surprise calculation, ISM/PMI source, or global central-bank calendar was added.
