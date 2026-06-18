# Session Log: 2026-06-18 - u105 - Code Generation

## Overview

- **Date**: 2026-06-18
- **Unit**: u105 macro-actual-source-of-record
- **Stage**: Code Generation
- **Step**: Steps 1-7

## Work Summary

Added official BLS/BEA macro actual adapters and connected their canonical period keys to the existing macro lifecycle path.

## Key Decisions

| Decision | Rationale |
| --- | --- |
| Keep BLS no-key and BEA free-key paths separate | BLS Public Data API works without a key; BEA rejects unauthenticated/sample credentials, so missing `BEA_API_KEY` must degrade explicitly. |
| Use source-period canonical keys | BLS/BEA actual payloads expose observation periods, not verified release event dates; FRED calendar rows derive the same period keys for CPI/PPI/NFP/GDP/PCE schedules. |
| Do not emit consensus/surprise metadata | BLS/BEA official actual endpoints provide actual observations, not economist forecasts. |
| Register as macro-actual health sources | These official actual rows should satisfy u59 macro-actual coverage for US equity. |

## Validation

- `uv run pytest tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py tests/unit/sources/test_fred_economic_calendar.py tests/unit/briefing/test_macro_carryover.py -q` -> 48 passed
- `uv run pytest tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py -q` -> 66 passed
- `uv run pytest tests/unit/_internal/test_redaction.py tests/unit/sources/test_no_paid_apis.py -q` -> 59 passed
- `uv run ruff check src/investo/sources/bls_macro_actuals.py src/investo/sources/bea_macro_actuals.py src/investo/sources/fred_economic_calendar.py tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py tests/unit/briefing/test_macro_carryover.py` -> clean
- `uv run mypy --strict src/investo/sources src/investo/briefing` -> clean over 100 source files
- `uv run python scripts/check_no_paid_apis.py` -> clean
- `git diff --check` -> clean

## TECH-DEBT Items

- None added.
