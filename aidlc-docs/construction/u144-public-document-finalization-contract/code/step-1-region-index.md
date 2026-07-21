# Step 1.3 Canonical Region Index

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`PublicDocumentLayout.reindex()` now builds the exhaustive publisher-owned
region index before any finalization path is made public:

- the 17 FD priorities cover the canonical disclaimer, protected diagnostics,
  typed supplement markers, conditional macro/indicator/channel/thesis/anchor
  producers, navigation, exact segment disclaimer, five required sections,
  watchpoints, exact H1, and residual first viewport;
- typed E1 supplements render through paired `investo:block` comments, and
  missing, unexpected, duplicated, nested, mismatched, or malformed markers
  fail closed without looking at evidence text or Markdown URLs;
- section/watchpoint marker placement is partitioned into one heading-owning
  primary plus deterministic source-ordered continuation regions. This is the
  minimal FD refinement needed to preserve current H2-scoped producer layout
  while retaining contiguous, unique, non-overlapping regions;
- every byte belongs to exactly one region. Unexpected circled-number H2s,
  duplicate/missing canonical headings, overlaps, and non-whitespace unclaimed
  bytes fail closed;
- body replacement uses the indexed offsets and then fully reindexes with the
  same expectation. Marker omission empties only the paired shell; the optional
  cause line removes its whole span;
- exact equity/crypto anchor headers and delimiter are conditional on typed
  non-empty anchor expectation, and the wrong segment header is rejected.

The duplicated-evidence regression replaces only the requested marker ID, so
the implementation cannot regress to `str.find()`-based ownership.
