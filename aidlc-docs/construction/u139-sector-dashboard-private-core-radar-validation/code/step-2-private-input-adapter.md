# u139 Code Generation Step 2 — Local Private Input Adapter

**Date**: 2026-07-18
**Status**: Complete
**Plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-code-generation-plan.md`

## Delivered Surface

- `src/investo/sector_dashboard/private_input.py` reads one explicit versioned JSON
  manifest and the fixed eleven-sector plus SPY workbook set without network access.
- `src/investo/sector_dashboard/__init__.py` exports the manifest reader, parser,
  bundle loader, and the redacted run-level error contract.
- `pyproject.toml` and `uv.lock` add the approved sole runtime dependency
  `openpyxl>=3.1,<4` (`3.1.5` resolved) and its `et-xmlfile` transitive dependency.
- `tests/unit/sector_dashboard/test_private_input.py` generates synthetic XLSX/OOXML
  packages at runtime and pins normal, partial, warming-up, insufficient, malformed,
  adversarial, and resource-lifecycle behavior.

## Input and Resource Boundary

1. The manifest key set is exact and case-sensitive. Duplicate JSON keys, extra schema
   fields, relative/inside-repository paths, symlinks, hardlink aliases, non-regular
   files, and non-`.xlsx` inputs fail closed with stable redacted codes.
2. Manifest and workbook identities are captured as device/inode/size/mtime/ctime and
   opened with `O_NOFOLLOW`. Each stable handle is bounded-read once into an at-most
   8 MiB ticker-local snapshot; ZIP preflight, SHA-256, and openpyxl all consume that
   exact snapshot, while pre/post identity changes fail closed.
3. ZIP preflight enforces 8 MiB compressed, 64 MiB declared-uncompressed, 100:1,
   2,000-member, 20-worksheet, and 250,000-cell limits; it rejects encryption,
   duplicate/unsafe members, malformed XML, and unsupported packages without extracting.
4. Workbook sheet relationship IDs and `workbook.xml.rels` are parsed through
   `defusedxml`. Cell counting follows the actual unique internal worksheet targets and
   requires their exact XLSX worksheet content type, preventing relationship retargeting
   from bypassing the shape ceiling.
5. openpyxl runs one workbook at a time with `read_only=True`, `data_only=True`,
   `keep_links=False`, and `keep_vba=False`; every workbook closes in `finally` before
   the next handle opens.

## Canonical and Redaction Contracts

- Exactly one success or typed failure is produced per fixed ticker. Only normalized
  `Date` and `NAV` values enter `NavSeries`; formulas without cached values, invalid or
  non-midnight dates, non-finite/non-positive NAV, duplicates, and interior disorder
  reject only that ticker.
- Strict SPY/newest-date alignment and the approved coverage precedence produce
  deterministic `normal`, `partial`, `warming_up`, or `insufficient` bundles.
- Diagnostics contain only closed issue codes plus approved ticker/count/date fields.
  Paths, sheet names, cell coordinates/values, raw rows, ZIP names, and exception text
  do not cross the adapter boundary.
- The private input fingerprint uses a versioned, binary-safe frame of fixed-order
  ticker identities and 32-byte per-workbook SHA-256 digests. It is omitted when all
  twelve inputs cannot be safely hashed.

## Review and Verification

The required independent fresh-eyes review found three High and two Medium issues:
path-reopen TOCTOU, relationship-target cell-limit bypass, same-inode in-place mutation
after preflight, ambiguous binary fingerprint framing, and duplicate JSON key
acceptance. All five were fixed with synthetic adversarial regressions before Step 2
closeout. The final independent re-review returned `APPROVED` with no remaining
Critical, High, or Medium finding.

Local validation:

- focused private-input tests — 36 passed
- combined Step 1 model plus Step 2 adapter tests — 273 passed
- scoped Ruff check and format check — passed
- scoped strict mypy — passed
- `git diff --check` — passed

Step 3 owns pure metric and regime computation. Step 2 adds no renderer, manual CLI,
source adapter, scheduled pipeline, public artifact, Pages, or Telegram behavior and
does not change u140's blocked public-source gate.
