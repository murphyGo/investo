# u107 cftc-positioning-layer — Code Summary

Completed: 2026-06-18

## Scope

Added the official no-key `cftc-cot-positioning` adapter for regulated futures positioning context across:

- TFF futures-only rows: E-mini S&P 500, Nasdaq-100 mini, VIX futures, 10Y Treasury note, U.S. Dollar Index, Bitcoin CME, and Ether CME.
- Disaggregated futures-only rows: WTI crude oil and gold.

## Implementation Notes

- Fetches CFTC public reporting Socrata endpoints with bounded contract-code allow-lists and a target-date cutoff.
- Emits only allow-listed contracts; unmapped rows are ignored.
- Converts TFF leveraged-money rows and disaggregated managed-money rows into `NormalizedItem(category="macro")`.
- Stamps report kind, contract code/label/group, trader category, as-of date, release date, long/short/spread/net contracts, net percent of open interest, open interest, units, source lag, release lag, `data_frequency=weekly`, and an explicit delayed-data label.
- Estimates CFTC publication as Friday 15:30 America/New_York for Tuesday positions, with conservative U.S. federal-holiday delay handling, and drops pre-release rows.
- Registers the adapter import, S-tier label, US market window, source-outcome composition, and contract-group item-level routing so US and crypto CFTC rows do not cross-pollute segment evidence.
- Extends `publisher.channel_anchor_block` so US and crypto briefings can render CFTC positioning as a weekly delayed context row instead of current-session flow.
- Keeps paid liquidation, exchange netflow, CryptoQuant, Glassnode, and Coinglass out of scope.

## Validation

- `uv run pytest tests/unit/sources/test_cftc_cot_positioning.py tests/unit/publisher/test_channel_anchor_block.py tests/unit/sources/test_plugin_contract.py -q` — 32 passed.
- `uv run pytest tests/unit/briefing/test_segments.py tests/unit/sources/test_aggregator.py -q` — 81 passed.
- `uv run pytest tests/unit/sources/test_cftc_cot_positioning.py tests/unit/briefing/test_segments.py tests/unit/publisher/test_channel_anchor_block.py tests/unit/sources/test_plugin_contract.py -q` — 54 passed.
- `uv run ruff check src/investo/sources src/investo/briefing src/investo/publisher tests/unit/sources tests/unit/publisher/test_channel_anchor_block.py` — passed.
- `uv run ruff format --check` on touched source/test files — passed.
- `uv run mypy --strict src/investo/sources src/investo/briefing src/investo/publisher` — passed.
- `uv run python scripts/check_no_paid_apis.py` — passed.

## Notes

Full-scope `ruff format --check src/investo/sources src/investo/briefing src/investo/publisher tests/unit/sources` still reports six pre-existing out-of-scope files needing formatting. u107 touched files pass the scoped format check.
