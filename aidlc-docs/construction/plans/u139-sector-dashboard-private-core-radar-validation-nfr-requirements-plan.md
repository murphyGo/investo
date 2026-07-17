# NFR Requirements Plan: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Stage**: NFR Requirements
**Status**: Complete — approved 2026-07-18
**Approved Functional Design**: `aidlc-docs/construction/u139-sector-dashboard-private-core-radar-validation/functional-design/`
**Requirements**: NFR-002, NFR-003, NFR-005, NFR-006, NFR-008, US-010

## Context Loaded

- Approved Functional Design R1-R33, E1-E21, I1-I6, and C1-C8
- Existing Python 3.11+, pydantic v2, defusedxml, pytest, Hypothesis, ruff, and
  mypy-strict project stack
- State Street spike envelope: 12 workbooks, approximately 2.9 MB compressed total,
  at most 5,694 observed rows per workbook
- Private-data boundary: no network, no public artifact, no raw fixture, no path/value
  logging, and no integration with the existing briefing pipeline

## NFR Decisions Already Fixed

- Monthly service/API cost remains zero and the unit makes zero network requests.
- Manifest, workbooks, and output remain outside the repository.
- Tests use synthetic XLSX bytes and typed series, never provider data.
- Output contains one deterministic JSON/Markdown pair from one snapshot.
- Every diagnostic follows the approved redacted field set.
- u139 does not run in GitHub Actions or claim availability as a scheduled service.

## Plan Steps

- [x] Load approved Functional Design, requirements, project stack, and current
  dependency/test conventions.
- [x] Identify NFR decisions that materially affect correctness, privacy, resource
  safety, reproducibility, and operator recovery.
- [x] Create bounded questions for parser stack, resource limits, numeric precision,
  output replacement, and platform/file permissions.
- [x] Collect and validate every `[Answer]:` response.
- [x] Resolve contradictions or create a dedicated clarification file.
- [x] Author `nfr-requirements/nfr-requirements.md` with measurable acceptance criteria.
- [x] Author `nfr-requirements/tech-stack-decisions.md` with dependency and platform
  choices.
- [x] Reconcile the code-generation plan Step 0 and fixed validation commands.
- [x] Validate markdown, identifiers, acceptance-criteria coverage, and contextless
  implementation readiness.
- [x] Record review-ready status in `aidlc-state.md` and `audit.md`, then present the
  required two-option stage closeout.

## NFR Questions

Please fill every `[Answer]:` tag with one letter. The first option is the recommended
contract where applicable.

### Question 1 — XLSX parser stack

Which implementation should parse the private workbooks?

A) Add `openpyxl>=3.1,<4` as the only new runtime dependency, use read-only/data-only
mode after an explicit ZIP safety preflight, and keep `Date`/`NAV` extraction behind
the `sector_dashboard.private_input` boundary.
B) Add no dependency and implement XLSX ZIP/shared-string/style/date parsing directly
with `zipfile` plus `defusedxml`.
C) Require the operator to convert all workbooks to CSV before running u139 and remove
native XLSX parsing from the unit.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 2 — Resource and performance envelope

What bounded local-run profile should be enforced?

A) Per workbook: compressed file at most 8 MiB, declared uncompressed ZIP content at
most 64 MiB, compression ratio at most 100:1, at most 20 worksheets and 250,000
non-empty cells; whole 12-file run at most 10 seconds and 256 MiB peak memory on the
supported reference environment.
B) Per workbook: 32 MiB compressed and 256 MiB uncompressed, with a 30-second and
512-MiB whole-run budget.
C) No explicit file/cell/time/memory bounds; rely on local operator judgment.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 3 — Numeric reproducibility and display precision

How should deterministic numeric output be fixed?

A) Parse NAV and compute simple returns/rank with `Decimal`; use binary float only for
`log`, sample standard deviation, and square root; convert that result through its
shortest decimal representation; quantize snapshot ratios to 10 decimal places with
ROUND_HALF_EVEN, report percentages/percentage-points to 2 decimal places, and rank
scores to 4 decimal places.
B) Use Python float for every calculation and serialize the default representation.
C) Use Decimal everywhere and implement custom Decimal logarithm/square root routines
inside u139.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 4 — Existing output replacement and atomicity

What should happen when `snapshot.json` and `report.md` already exist?

A) Byte-identical output is a no-op; different output requires explicit `--replace`;
write and validate both files in a sibling temporary directory, embed one shared
snapshot id in both projections, replace under an exclusive transaction marker with
backup/rollback, and refuse a mismatched pair during recovery after an interrupted
process.
B) Always replace existing files atomically without a confirmation flag.
C) Never replace; create a new versioned subdirectory for every execution.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

### Question 5 — Supported platform and private file permissions

Which platform/permission contract should the manual runner guarantee?

A) Support macOS and Linux POSIX only for u139; create a new output directory with
mode `0700` and artifact files with `0600`, reject symlinked output paths, and fail
closed when owner-only permissions cannot be verified.
B) Support Windows as well, using owner-only permissions on POSIX but best-effort
warnings rather than an ACL guarantee on Windows.
C) Remain platform-neutral and do not change or verify filesystem permissions.
D) Other (please describe after the `[Answer]:` tag below).

[Answer]: A

## Answer Reconciliation

- Q1-Q5 are all option A, as approved by the user.
- No contradiction or unresolved ambiguity remains, so no clarification file is
  required.
- The 10-second/256-MiB measurement uses the observed-shape 12-workbook reference
  benchmark; the larger file/cell thresholds remain hard rejection ceilings.
- Two independent POSIX file renames are specified honestly as a recoverable pair
  transaction with a shared snapshot id, marker, backup, and deterministic recovery,
  not as an impossible pair-level atomic primitive.
- The user approved the complete NFR artifacts on 2026-07-18 with
  `승인, 다음단계 진행`; Code Generation is authorized and Step 1 has begun.
