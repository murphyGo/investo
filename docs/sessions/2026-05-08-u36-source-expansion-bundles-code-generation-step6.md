# 2026-05-08 u36 source expansion bundles — step 6

## Context

Close u36 by finishing the remaining official macro-calendar and crypto public market data sources.

## Implementation

- Added `src/investo/sources/binance_crypto_market.py`.
- Added `src/investo/sources/us_economic_calendar.py`.
- Registered both adapters in source discovery and plugin-contract tests.
- Routed `binance-crypto-market` to crypto and `us-economic-calendar` to US-equity.
- Added fixtures and tests for Binance symbol parsing/isolation and BEA schedule parsing.
- Marked u36 complete after full quality gates.

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest -q
uv run mkdocs build --strict
```

Result:

- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed; 201 files already formatted.
- `uv run mypy --strict src/` — passed; no issues in 78 source files.
- `uv run pytest -q` — passed; 1344 tests.
- `uv run mkdocs build --strict` — passed.
