# NFR Requirements: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Status**: Complete — approved 2026-07-18
**Parent plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-nfr-requirements-plan.md`
**Approved Functional Design**: `aidlc-docs/construction/u139-sector-dashboard-private-core-radar-validation/functional-design/`
**Requirements**: NFR-002, NFR-003, NFR-005, NFR-006, NFR-008, US-010

## 1. Privacy, Security, and Cost

### AC-1.1 Private path boundary

The manifest, all twelve workbooks, and the output directory are explicit absolute
paths. Their resolved locations must remain outside the repository, its tracked
fixtures, `archive/`, and `site_docs/`. The output directory must not equal, contain,
or be contained by an input file path. All path checks finish before any workbook is
opened.

### AC-1.2 Symlink and file-type boundary

Every workbook is a unique regular `.xlsx` file. The final output directory,
`snapshot.json`, `report.md`, and transaction-management entries must not be
symlinks. Parent aliases such as macOS `/tmp` are resolved before the boundary and
ownership checks; the resolved target, not the spelling supplied by the operator, is
authoritative.

### AC-1.3 Raw-input non-retention

The runner does not copy the manifest or workbooks, persist parsed daily NAV series,
write provider-shaped fixtures, or place input bytes in a cache, temporary output,
exception, diagnostic, snapshot, report, or log. Only the approved aggregate fields
and `input_fingerprint` may cross the private-input boundary.

### AC-1.4 Redacted observability

Standard output/error and caught exceptions may contain only the approved diagnostic
set: stable issue code, ticker, row count, date range, coverage state, metric name,
and policy version. They must not contain an absolute path, filename, sheet name,
cell coordinate/value, raw row, ZIP member name, input fingerprint, exception text,
or traceback derived from private input.

### AC-1.5 Zero network and zero service cost

A u139 execution makes no DNS, socket, HTTP, browser, provider-login, telemetry, or
LLM call and requires no secret. Its incremental monthly service/API cost is zero.
Tests fail if the manual runner reaches a network client or source registry.

### AC-1.6 Owner-only output

On first creation, the private output directory is mode `0700`; `snapshot.json`,
`report.md`, and every temporary, backup, or transaction file are mode `0600`.
Before reading or replacing an existing pair, the runner verifies current-user
ownership and exact owner-only permission bits. It fails closed rather than warning,
auto-relaxing, or publishing when ownership or permissions cannot be verified.

### AC-1.7 Public-surface non-interference

The runner neither reads from nor writes to the briefing/public pipeline. A private
validation run leaves tracked files, `archive/`, `site_docs/`, Pages navigation,
workflows, Telegram state, source registries, and public artifacts byte-unchanged.
Successful u139 output does not change u140's blocked public-source status.

## 2. Resource Safety and Performance

### AC-2.1 ZIP size envelope

Before `openpyxl` is invoked, each workbook passes a bounded `zipfile` preflight:

- compressed file size is at most `8 MiB` (`8 * 1024 * 1024` bytes);
- sum of declared uncompressed member sizes is at most `64 MiB`;
- aggregate declared-uncompressed/compressed ratio is at most `100:1`;
- no single member exceeds the 64 MiB workbook ceiling; and
- the archive contains at most 2,000 members.

Violation produces a ticker-scoped redacted `workbook.open` failure. The rejected
archive is not passed to `openpyxl`.

### AC-2.2 ZIP structural safety

Preflight rejects malformed ZIPs, encrypted members, duplicate member names,
absolute or parent-traversal member paths, NUL-containing names, and unsupported
non-XLSX packages. It never extracts archive members to disk. XML inspected during
preflight is streamed through the project's `defusedxml` boundary.

### AC-2.3 Workbook shape envelope

A workbook contains at most 20 worksheets and at most 250,000 non-empty cells across
all worksheets. Preflight conservatively counts every worksheet cell record against
that ceiling, including styled/formula cell records without a materialized value, so
blank-looking OOXML cannot bypass the resource bound. The bounded streaming count
does not trust a false or extreme worksheet dimension or allocate its declared grid.
Reaching the limit stops that ticker without loading remaining cells.

### AC-2.4 Lazy, sequential workbook handling

Workbooks are opened one at a time with `read_only=True`, `data_only=True`,
`keep_links=False`, and `keep_vba=False`; only Date/NAV values enter the canonical
model. Every workbook is explicitly closed in a `finally` path before the next is
opened. No twelve-workbook object graph or extracted copy is retained.

### AC-2.5 Runtime budget

On the reference profile—CPython 3.11, two logical CPUs, 2 GiB available RAM, local
SSD, and supported macOS or Linux—the synthetic observed-shape benchmark of twelve
workbooks with 6,000 dated rows and four populated columns each completes in at most
10.0 seconds. The hard file/cell ceilings are rejection bounds, not a promise that
twelve maximum-size workbooks finish inside this observed-shape budget.

### AC-2.6 Peak-memory budget

The same reference benchmark stays at or below 256 MiB peak resident memory above
the runner's baseline. A focused benchmark records wall time and peak memory; unit
tests separately prove the sequential-close contract without depending on noisy
wall-clock thresholds.

### AC-2.7 Bounded temporary state

Temporary and backup data contain only the two rendered projections plus bounded
transaction metadata. A normal completion removes owned temporary/backup state.
Caught failure removes newly prepared state after rollback. Interrupted state is
retained only when required for deterministic recovery and remains owner-only.

## 3. Reliability, Idempotency, and Recovery

### AC-3.1 Per-workbook failure isolation

One sector workbook failure does not prevent the other tickers from being parsed.
Manifest/path failures stop before reads; SPY failure, mixed newest dates, and
coverage below the approved threshold follow the Functional Design's bundle-level
insufficient behavior.

### AC-3.2 Deterministic incomplete output

Valid `normal`, `partial`, `warming_up`, and diagnostic-only `insufficient` bundles
render the exact Functional Design surface for that state. An insufficient bundle
never leaks a partial rank, regime, quadrant, or metric claim.

### AC-3.3 Pair integrity

`snapshot.json` and `report.md` are valid only as a pair. The JSON projection contains
one top-level `snapshot_id` immediately after `schema_version`; the report contains
the same id exactly once in the PrivateMethodNote marker
`<!-- snapshot_id: sha256:<64-lowercase-hex> -->`. A missing artifact, malformed
projection, duplicate marker, or different id is a mismatched pair and must never be
treated as current output.

### AC-3.4 Idempotency and explicit replacement

If both newly rendered bytes equal the existing valid pair byte-for-byte, execution
is a no-op and does not rewrite either file. If either byte differs, replacement is
refused unless the operator supplied `--replace`. A refusal leaves the existing pair
unchanged.

### AC-3.5 Recoverable two-file transaction

Because POSIX cannot atomically swap two independent files as one operation, u139
uses a recoverable transaction rather than claiming impossible pair-level atomicity:

1. acquire an exclusive, owner-only sibling transaction marker;
2. render both files in a sibling temporary directory;
3. verify schema, mandatory labels, forbidden fields, modes, and the shared id;
4. fsync both files and their directory;
5. preserve any existing valid pair in an owner-only sibling backup;
6. promote both prepared files with `os.replace` while updating marker phase; and
7. fsync the output directory, verify the promoted pair, then remove backup/marker.

Any caught failure restores the complete old pair before returning non-zero.

### AC-3.6 Interrupted-process recovery

When a transaction marker exists, a new run performs recovery before reading input.
It may finish promotion only from a complete prepared pair whose ids match, or roll
back only from a complete backup pair whose ids match. If current, prepared, or
backup projections disagree, automatic recovery refuses the pair and preserves the
owner-only evidence for operator action; it never selects one file by mtime.

### AC-3.7 Concurrent-run exclusion

The transaction marker is created with exclusive-create semantics and held with a
non-blocking POSIX advisory lock. If a marker remains after process death, recovery
opens it with no-follow/owner/mode checks and must acquire the same lock before
inspection. A second live process cannot parse or write the same output target.
Marker metadata contains only schema version, phase, relative managed names, and
expected snapshot id—never an input path/value.

### AC-3.8 CLI completion semantics

The manual runner returns:

- `0` for a valid normal/partial/warming-up pair or a byte-identical no-op;
- `2` for manifest/path/permission/replacement-policy rejection with no new pair;
- `3` after committing a valid diagnostic-only insufficient pair; and
- `4` for transaction/write/recovery failure.

The CLI prints one redacted summary line and does not expose a private-derived
traceback by default.

## 4. Numeric and Serialization Reproducibility

### AC-4.1 Decimal calculation boundary

NAV values are converted to `Decimal` from their shortest lossless cell-value text.
Simple returns, SPY excess returns, drawdown ratios, percentile midranks, weight
renormalization, and rank scores use a local decimal context of precision 34 with
`ROUND_HALF_EVEN`. Booleans, non-finite values, and non-positive NAV remain invalid.

### AC-4.2 Transcendental float boundary

Binary float is used only for daily `log`, sample standard deviation, and `sqrt(252)`
in realized volatility. The resulting finite float is converted with Python's
shortest round-trip decimal representation before returning to `Decimal`. No other
metric or rank calculation silently crosses the float boundary.

### AC-4.3 Snapshot quantization

Every available snapshot metric ratio and rank score is quantized to exactly ten
decimal places using `Decimal("0.0000000001")` and `ROUND_HALF_EVEN`. Negative zero
is canonicalized to positive zero. Missing values remain JSON `null` plus their
approved missing reason and are never serialized as zero.

### AC-4.4 Report display precision

Return, excess-return, acceleration, volatility, and drawdown displays multiply the
stored ratio by 100 and round half-even to two decimals. Returns/volatility/drawdown
use `%`; excess return and acceleration use percentage-point (`pp`) labels. Rank
score displays four decimals. Formatting never changes machine values.

### AC-4.5 Canonical JSON and Markdown bytes

JSON is UTF-8, LF-only, key-ordered by the fixed schema, uses canonical decimal
strings, and ends with one newline. Markdown is UTF-8, LF-only, follows the approved
component/row order, and ends with one newline. Neither projection contains wall
clock, host, platform, process id, locale, absolute path, or unordered-container
iteration.

### AC-4.6 Shared snapshot id

The id is `sha256:` plus the lowercase SHA-256 hex digest of canonical snapshot JSON
bytes computed without the `snapshot_id` member. That id is then added to the JSON
projection and the single report marker. Verification recomputes the digest rather
than trusting either embedded value.

### AC-4.7 Stable ordering

Manifest processing uses fixed universe order with SPY last; diagnostics use issue
code/ticker/metric order; records use rank descending then fixed universe order;
ties and missing ranks never depend on mapping/set iteration. Repeated identical
input produces byte-identical projections on each supported platform.

### AC-4.8 Numeric property tests

Property-based tests cover return/excess identities, adjacent non-overlapping 5D
acceleration, volatility non-negativity, drawdown range `[-1, 0]`, tied midranks,
rank range `[0, 1]`, neutral-band hysteresis, quantization idempotence, and JSON
round-trip. Fixed golden vectors pin the float-to-decimal boundary.

## 5. Portability, Architecture, and Usability

### AC-5.1 Supported platform

u139 supports CPython 3.11+ on macOS and Linux POSIX filesystems only. Windows,
network filesystems without reliable owner/mode/replace/fsync semantics, containers
without verifiable current-user ownership, and mobile/browser execution are outside
the u139 guarantee and fail before workbook reads where detectable.

### AC-5.2 Component boundary

`sector_dashboard` may import shared `models` and private standard/runtime libraries.
It does not import or register with `sources`, `briefing`, `publisher`, `notifier`, or
the scheduled orchestrator. Input parsing, pure calculation, and rendering remain
separate modules as fixed by the code-generation plan.

### AC-5.3 Dependency boundary

The only new runtime dependency is `openpyxl>=3.1,<4`. Existing `defusedxml` remains
the XML-safety dependency. No pandas, NumPy, SciPy, xlrd, browser automation,
database, lock package, logging framework, or vendor SDK is added.

### AC-5.4 Explicit manual operation

The runner requires `--manifest` and `--output-dir` with no implicit path, discovery,
download, or repository-relative default. `--replace` is opt-in. Help text labels the
command private/NAV-only and says it is not actual market OHLCV or public evidence.

### AC-5.5 Accessible private report

All state and sign information is conveyed by headings, text, identifiers, and
symbols rather than color alone. Tables have stable text headers; missing values
include reasons; English identifiers accompany Korean regime labels on first use.

### AC-5.6 Existing behavior compatibility

Importing Investo without `openpyxl` is not a supported installed state after the
dependency is added, but importing/running existing briefing paths must not open an
XLSX, initialize u139, change source counts, or alter generated output. u139 remains
manual and opt-in.

## 6. Verification and Drift Gates

### AC-6.1 Synthetic fixtures only

All committed workbook tests generate minimal schema-equivalent XLSX files. No State
Street filename, workbook byte, daily NAV row, input fingerprint, private report, or
operator path is committed or uploaded as CI evidence.

### AC-6.2 Parser and state matrix

Focused tests cover exact manifest identity; path rejection; header variants;
ascending/descending/interior disorder; duplicate/invalid date; invalid/formula
without value NAV; SPY failure; mixed as-of; all four coverage states; every metric
missing reason; all regimes; and 0/5/10/15/20 bps sensitivity.

### AC-6.3 Resource-adversary matrix

Tests cover oversize compressed/uncompressed totals, ratio over 100:1, too many ZIP
members/sheets/cells, encrypted/traversal/duplicate members, misleading worksheet
dimensions, and explicit workbook close on every success/failure path. Rejections
are bounded and redacted.

### AC-6.4 Transaction fault injection

Fault injection at every render/fsync/backup/promote/verify phase proves: the old
valid pair survives caught failure; interrupted complete prepared or backup pairs can
recover; mismatched ids fail closed; different output needs `--replace`; identical
output is a byte-preserving no-op; and concurrent marker acquisition is exclusive.

### AC-6.5 Privacy and public-boundary guard

Tests scan logs, exceptions, artifacts, temporary state, and `git diff` for sentinel
private paths/values. Negative import/registry tests prove no source, pipeline,
publisher, notifier, Pages, or Telegram integration was added.

### AC-6.6 Quality gates

Implementation closeout runs focused u139 tests, full pytest, ruff, format check,
strict mypy, the no-paid-API guard, `git diff --check`, unresolved-placeholder scan,
and `mkdocs build --strict`. Any unrelated pre-existing failure is reproduced from
the pre-u139 commit and recorded rather than hidden.

### AC-6.7 Operator-local smoke evidence

The final handoff records one operator-local twelve-workbook smoke result using only
redacted counts, coverage, as-of date, runtime, peak memory, and output-pair hash.
Neither input nor private output is committed, uploaded, pasted into the audit log,
or used to claim public readiness.

## Requirement Trace

| Requirement | NFR acceptance coverage |
| --- | --- |
| NFR-002 zero paid API/service path | AC-1.5, AC-5.3, AC-6.6 |
| NFR-003 failure isolation/recovery | AC-3.1-AC-3.8, AC-6.4 |
| NFR-005 bounded execution | AC-2.1-AC-2.7 |
| NFR-006 deterministic/PBT verification | AC-4.1-AC-4.8, AC-6.2-AC-6.4 |
| NFR-008 public-data compliance boundary | AC-1.1-AC-1.7, AC-5.4, AC-6.1, AC-6.5, AC-6.7 |
| US-010 private core-radar validation | AC-2.5, AC-3.2-AC-3.4, AC-4.3-AC-4.7, AC-5.5 |
