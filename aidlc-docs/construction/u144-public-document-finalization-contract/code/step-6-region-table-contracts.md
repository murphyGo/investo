# Step 6.6 Region-Table Contracts

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The region-layout suite now pins every field of all 17 ordered `RegionSpec`
rows, including the two exact-disclaimer regions, protected diagnostics, and
all reader-visible remainder regions. The complete contract set covers:

- empty and non-empty equity/crypto anchor inputs with exact headers;
- supplement marker pairing and carryover heading ownership;
- duplicate, nested/overlapping, missing, mismatched, and orphan markers;
- marker-shell-preserving omission with no omitted E5/E6 artifact ID;
- exhaustive zero-gap residual partitioning around section-scoped markers;
- stable region IDs and exact targeting after body replacement;
- duplicate/missing/unexpected numbered sections; and
- reader-visible policy for every region that contains a Markdown table.

The new table-policy test includes carryover, anchor, and ordinary section
tables, preventing table content from acquiring a broad projection exemption.

## Validation

- region/type and terminal projection tests: 341 passed;
- scoped Ruff and format check: passed.
