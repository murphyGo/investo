# Step 1.1 Lifecycle Types

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`publisher.public_document` now owns the immutable E1-E8 construction values:

- E1 context, supplements, and staged-artifact descriptors with canonical
  segment order, timezone, mapping immutability, and full artifact-reference
  validation;
- E2 phase envelope with direct construction disabled, ordered private
  transitions, and a terminal-validation witness required by the seal, plus E3
  bounded layout/region/outcome types;
- E4 typed limitation reasons;
- E5 `FinalizedPublicDocument`, constructible only through the module-private
  pure seal factory, with a SHA-256 digest over the final compatibility
  briefing bytes;
- E6 ordered bundle, per-segment outcomes, and a private bundle factory that
  derives the exact E1 staged-artifact descriptors for its promotion manifest;
- E7 closed dispositions (the executable surface policy remains in
  `_public_document_policy.py`); and
- E8 bounded `PublicDocumentFinalizationError`, whose message never renders its
  retained cause.

The minimal `models.public_notification.PublicNotificationSummary` shell is
present because it is an E2/E5 field. Its field validation/shared-model export
and the typed watchpoint renderer are still Step 1 checklist 4. Phase execution,
region indexing, writer integration, and production routing remain later
explicit checklist items; this slice does not switch behavior.

E1 also snapshots and freezes dict-backed fields inside `NormalizedItem` and
`BundleContext`, so callers cannot alter finalizer inputs through a frozen
model's mutable nested container after context construction.
