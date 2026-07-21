# Step 1.4 Notification and Watchpoint Contracts

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The shared `PublicNotificationSummary` compatibility DTO now enforces the
identity and shape expected from terminal validation:

- segment and coverage status belong to their closed typed sets;
- target date is an exact `date`, not a `datetime` subtype;
- the public coverage label exactly matches the typed coverage status;
- conclusion and optional watchlist values are already-cleaned, non-empty,
  single-line values;
- publisher-private summary validation failures expose one of four bounded
  issue codes and cannot carry arbitrary or secret-shaped text.

`render_watchpoint_matrix_result()` adds a typed assembly result without
switching any production caller. A rendered result has one to six usable cards
and no limitation reason. A limited result has zero cards and exactly
`watchpoint_unavailable`. The legacy string function delegates to this result
while retaining its historical empty-input behavior.

Same-day idempotency recognizes only canonical renderer output. Existing cards
are parsed back into `WatchpointRow`, checked by the normal usability predicate,
bounded by `MAX_VISIBLE_ROWS`, and byte-compared with canonical re-rendering.
Malformed, mixed, data-limited, URL-bearing, trace-bearing, or over-bound card
shapes therefore cannot forge a rendered result.

No notifier, orchestrator, finalizer, or production watchpoint call site was
changed in this step.
