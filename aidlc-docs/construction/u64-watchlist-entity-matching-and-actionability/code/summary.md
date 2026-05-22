# u64 watchlist-entity-matching-and-actionability Code Summary

**Date**: 2026-05-23
**Status**: Complete

## Delivered

- Removed source-name/category text from watchlist free-text matching so source labels cannot create false entity hits.
- Added structured metadata matching for ticker/symbol/asset-style fields before title/summary matching.
- Added match confidence and reason fields, rendered in watchlist callouts.
- Pinned `BTC` not matching `BTM`, `BTCS`, or longer uppercase substrings while preserving `BTC-USD`, `Bitcoin`, and `비트코인` matches.
- Added watchpoint actionability diagnostics for bullets that lack source, trigger, and implication structure.

## Verification

- `uv run pytest tests/unit/briefing/test_watchlist.py tests/unit/publisher/test_reader_format.py -q`
- Included in combined targeted gate: 192 passed.

