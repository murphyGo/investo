# Step 5.3 Notifier DTO Boundary

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The default segmented formatter now accepts only a mapping of
`PublicNotificationSummary` values, segment URLs, and the existing typed
lookahead/price inputs. It rejects `Briefing`, checks mapping-key/DTO-segment
identity, and requires every DTO to share one target date.

Conclusion, watchlist impact, coverage state, and coverage label are derived
inside terminal publisher validation from final layout bytes and E1 coverage.
Validated E2 stores the DTO; E5 copies it; PublishStage hands only those E5
DTOs to notification. Telegram formatting performs presentation and optional
price decoration but no public-text extraction or generated-field fallback.

## Regression evidence

- A `Briefing` value is rejected with `TypeError`, making generated
  `market_summary` unreachable from the segmented formatter.
- Mapping-key/segment mismatch and mixed target dates fail before rendering.
- Failed coverage collapses from the DTO; partial coverage keeps the normal
  block shape and typed label.
- Existing imminent-event, price snapshot, watchlist decoration, UTF-16,
  truncation, enabled-segment, and partial-link behavior remains green.

## Validation

- notifier, terminal DTO/finalizer, and orchestrator regressions: 300 passed;
- Ruff check/format and strict mypy over 243 source files: passed;
- no dependency, schema persistence, source, secret, network, or workflow change.
