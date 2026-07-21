# Step 3.1 Terminal Public Projection

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`publisher.reader_format.public_projection.project_public_markdown()` is now
the canonical E2 public-language boundary. It iterates the exhaustive typed
layout partition and uses `PublicDocumentRegion.projection_policy` as the only
visibility decision:

- `reader_visible` fragments, including Markdown table rows, cross the single
  u108 `project_public_quality_language()` wording owner;
- `protected_diagnostics` and `exact_disclaimer` fragments remain byte exact;
- fenced code inside a reader-visible region remains byte exact;
- changed lines retain their original LF, CRLF, or CR ending; and
- a changed document is fully reindexed with the original typed expectation.

The concrete `_project_assembled_draft()` collaborator installs this algorithm
on the monotonic `assembled -> projected` transition and preserves its typed
limitation reasons. Coverage-derived reasons land in the later dedicated Step
3 checklist item; the canonical API already rejects duplicate unordered phase
input.

Fresh-eyes review found that the first fence implementation treated a body
line such as `````not-a-close`` as a closing marker. Opening and closing rules
are now separate. A close must use the same backtick/tilde kind, be at least as
long as the opener, and contain only trailing whitespace. Regression coverage
pins both fence kinds and proves the raw fenced body is unchanged.

## Pre-switch boundary

The concrete phase algorithm is ready, but Step 5 still owns the atomic
default segmented finalizer and sealed-writer switch. The legacy earlier
`normalize_data_limited_reader_copy()` call remains active until that switch so
current production does not lose its compatibility projection in the interim.

## Validation

- projection/layout/reader-format set: 78 passed;
- publisher and existing surface suite: 638 passed;
- Ruff check and format check: passed;
- strict mypy for changed source/test modules: passed;
- fresh-eyes final review: 52 focused tests passed, approved.
