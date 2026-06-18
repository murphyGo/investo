# u106 money-energy-volatility-source-expansion — Code Summary

Completed: 2026-06-18

## Scope

Added three official/free source adapters for funding, energy supply, and volatility-structure context:

- `nyfed-reference-rates`: NY Fed SOFR/EFFR/OBFR/BGCR/TGCR latest observed rates, volumes, percentile fields, effective date, and source lag.
- `eia-petroleum-weekly`: EIA weekly petroleum status rows for crude/gasoline/distillate inventories, crude production, crude imports, and refinery utilization.
- `cboe-volatility-indices`: Cboe official daily VVIX and SKEW CSV closes; VIX is intentionally not emitted as a duplicate price snapshot.

## Implementation Notes

- Registered all three adapters in source discovery, tier registry, US market windows, and US segment routing.
- Classified NY Fed and EIA as S-tier official/source-of-record feeds; Cboe volatility CSVs as A-tier first-party market data.
- Added `EIA_API_KEY` to the redaction chokepoint. The adapter uses `EIA_API_KEY` when present and falls back to official `DEMO_KEY` for the bounded public request path.
- Added raw metadata for `units`, `as_of_date`, `release_date` or `effective_date`, `source_lag_days`, `release_lag_days`, `data_frequency`, and explicit delayed/weekly labels.
- Guarded against future-dated rows relative to the pipeline target date. EIA requests also pass `end=<target_date>`.
- EIA WPSR `period` is treated as the week-ending data date, not the public release date. The adapter estimates the WPSR release date as the following Wednesday 10:30 ET, with conservative U.S. federal-holiday delay handling, and drops rows not yet public for the target date.
- Kept restricted FRED ICE BofA series out of default config; the no-paid API check remains green.

## Validation

- `uv run pytest tests/unit/sources/test_nyfed_reference_rates.py tests/unit/sources/test_eia_petroleum_weekly.py tests/unit/sources/test_cboe_volatility_indices.py -q` — 11 passed.
- `uv run pytest tests/unit/sources/test_nyfed_reference_rates.py tests/unit/sources/test_eia_petroleum_weekly.py tests/unit/sources/test_cboe_volatility_indices.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py -q` — 80 passed.
- `uv run pytest tests/unit/publisher/test_channel_anchor_block.py tests/unit/briefing -q -k 'macro or channel or source'` — 94 passed, 774 deselected.
- `uv run ruff check src/investo/sources src/investo/publisher tests/unit/sources` — passed.
- `uv run ruff format --check` on touched source/test files — passed.
- `uv run mypy --strict src/investo/sources src/investo/briefing` — passed.
- `uv run python scripts/check_no_paid_apis.py` — passed.
