# u133 rendered regression fixture

`watchlist-registry-2026-06-30.json` reconstructs the minimum registry-only
subset behind the 2026-06-30 US-equity watchlist incident.

- It keeps the observed source/title shapes for MSFT, NVDA, and TSLA.
- It contains no raw payload, source URL, credential, destination, or private
  metadata.
- It intentionally has six accepted registry matches and zero non-registry
  items so the public empty-state and collapsed diagnostics boundary are
  deterministic.
