# Step 3.5 Owned-Region Public-Label Leakage Traversal

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`find_reader_visible_public_label_leaks(layout)` is the read-only terminal
public-language detector. It walks the typed `PublicDocumentRegion` sequence in
source order and inspects only regions whose projection policy is
`reader_visible`.

Detection delegates every visible line to the existing u108
`first_forbidden_public_evidence()` owner. No phrase table or regular expression
is copied. The traversal also reuses the projection module's exact backtick and
tilde fence state, so protected fenced bytes are not reclassified as prose.
Typed diagnostics and exact disclaimer regions are excluded by their existing
region policy, while reader-visible tables and arbitrary details receive no
blanket exemption.

Each finding is a frozen `PublicLabelLeakage(region_id, block, evidence)` with
the predicate's bounded evidence. The function never projects, repairs,
reindexes, or mutates the supplied layout. Step 4 will consume this specialized
detector as one typed input to the broader owned-surface disposition/grouping
workflow.

## Validation

- public projection, reader format, lifecycle, surface, and integration set:
  114 passed;
- direct scanner regression: raw layout returns ordered `section:1` and
  `watchpoints:section` findings only; projected layout returns none;
- Ruff check and format check: passed;
- strict mypy: passed;
- scoped diff check: passed;
- fresh-eyes review: 98 focused tests passed, approved.
