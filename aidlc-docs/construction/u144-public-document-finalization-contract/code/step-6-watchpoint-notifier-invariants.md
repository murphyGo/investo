# Step 6.5 Watchpoint and Notifier Invariants

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The focused watchpoint/notifier matrix now covers the complete typed boundary:

- rendered watchpoints require at least one usable card and no limitation;
- limited watchpoints require zero cards and exactly
  `watchpoint_unavailable`; forged mixed shapes fail or normalize closed;
- notifier values reject legacy `Briefing`, DTO key/segment mismatch, and
  mixed target dates;
- typed failed coverage collapses to one linked status line without rendering
  its conclusion;
- sealed watchlist text is decorated only from typed price items;
- missing terminal conclusion becomes a bounded
  `summary.missing_conclusion` trust block; and
- an unsafe generated `market_summary` remains present only on the private
  source object while the terminal DTO derives its conclusion and watchlist
  exclusively from safe final Markdown.

The new cases call the production terminal summary derivation and DTO-only
formatter directly, avoiding the legacy test adapter where exact boundary
ownership matters.

## Validation

- watchpoint, public-document, and notifier summary tests: 143 passed;
- scoped Ruff and format check: passed.
