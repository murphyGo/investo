# Tech Stack Decisions: `u139 sector-dashboard-private-core-radar-validation`

**Date**: 2026-07-18
**Status**: Complete — approved 2026-07-18
**Parent NFR**: `nfr-requirements.md`

## Decision Summary

| ID | Decision | Binding choice |
| --- | --- | --- |
| TS-1 | XLSX parser | `openpyxl>=3.1,<4`, read-only/data-only, no links/VBA |
| TS-2 | Archive/XML preflight | stdlib `zipfile` + existing `defusedxml` |
| TS-3 | Numeric engine | stdlib `decimal`, `math`, `statistics` |
| TS-4 | Domain validation | existing pydantic v2 models and immutable typed values |
| TS-5 | Private transaction | `pathlib`, `os`, `fcntl`, `tempfile`, `hashlib`; marker + recovery |
| TS-6 | Projections | stdlib `json` + deterministic Markdown renderer |
| TS-7 | Verification | pytest, Hypothesis, fault injection, synthetic XLSX |
| TS-8 | Platform | CPython 3.11+ on macOS/Linux POSIX only |

## TS-1. XLSX Parsing with openpyxl

Add exactly one runtime dependency:

```toml
"openpyxl>=3.1,<4"
```

Open every workbook with:

```python
load_workbook(
    filename,
    read_only=True,
    data_only=True,
    keep_links=False,
    keep_vba=False,
)
```

The workbook is explicitly closed in `finally`. Read-only mode is selected for lazy,
bounded traversal; `data_only=True` reads the value cached when Excel last calculated
a formula, so a formula without a materialized value remains invalid under FD R8;
`keep_links=False` avoids retaining cached external-workbook content. The parser does
not evaluate formulas or follow links.

Official basis:

- [openpyxl optimized read-only mode](https://openpyxl.readthedocs.io/en/stable/optimized.html)
- [openpyxl `load_workbook` parameters](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html)
- [openpyxl PyPI metadata and MIT license](https://pypi.org/project/openpyxl/)

The accepted range pins the stable 3.1 API family while excluding a future breaking
major version. Dependency lock output is regenerated during Code Generation.

## TS-2. ZIP and XML Safety Before openpyxl

Use stdlib `zipfile` to inspect archive metadata without extracting it. Enforce AC-2.1
and AC-2.2 before invoking openpyxl. Count worksheet/cell records with bounded
streaming XML through the already-installed `defusedxml`; do not trust worksheet
dimension declarations as an allocation bound.

This layered boundary is mandatory because the openpyxl project explicitly advises
installing `defusedxml` for XML entity-expansion attacks. `defusedxml` does not replace
ZIP compressed/uncompressed/ratio/member limits, so both controls remain. No lxml or
custom general-purpose OOXML parser is added.

## TS-3. Decimal-First Numeric Engine

Use:

- `decimal.Decimal`, `localcontext(prec=34)`, and `ROUND_HALF_EVEN` for NAV, simple
  ratios, excess, drawdown, percentile, weight, rank, and quantization;
- `math.log`, `math.sqrt`, and `statistics.stdev` only for realized volatility; and
- `Decimal(repr(result))` for the shortest round-trip float-to-decimal bridge.

Do not add NumPy, pandas, SciPy, or a custom Decimal transcendental implementation.
The small fixed universe does not justify their dependency and memory surface.

## TS-4. Existing Typed Domain Stack

Use existing pydantic v2 conventions for external manifest/projection validation and
immutable dataclass/pydantic value objects for the approved E1-E21 contracts. Pure
metric/regime functions consume typed series and have no filesystem or rendering
dependency. Closed literals/enums preserve the approved coverage, regime, and missing
reason vocabularies.

The NFR layer adds one projection-integrity field, `snapshot_id`; it does not add raw
input fields to `SectorDashboardSnapshot`.

## TS-5. Recoverable POSIX File Transaction

Use only stdlib filesystem primitives:

- `pathlib.Path.resolve`, `lstat`, and `stat` for resolved path/type/owner checks;
- `os.open` with exclusive/no-follow flags where available for owner-only managed
  files;
- `tempfile.mkdtemp` in the resolved output parent for prepared/backup directories;
- `fcntl.flock` for a non-blocking POSIX lock held on the transaction marker;
- `os.chmod`, `os.fsync`, and `os.replace` for mode, durability, and single-file
  promotion; and
- `hashlib.sha256` for input fingerprint and shared snapshot id.

An exclusive-create sibling transaction marker serializes writers and records a
small phase machine. No third-party lock library or database is introduced. The
implementation and documentation must call this a **recoverable pair transaction**,
not a two-file atomic rename.

Managed temporary names are derived from the output directory name plus a random
nonce, never from an input filename or ticker value. Marker content uses relative
managed names plus bounded projection anchors only: candidate/backup snapshot ids
and candidate/backup report SHA-256 digests. It contains no private input path,
value, row, fingerprint, or projection body. This TS-5 clarification was ratified at
closeout on 2026-07-19 with the AC-3.7 amendment after recovery fault injection
proved that one expected id cannot authenticate both projections and the rollback
pair.

## TS-6. Canonical JSON and Markdown

Use stdlib `json` with an explicitly ordered projection; do not depend on generic
`default=str`. Decimal/date conversion is schema-owned. Markdown uses small pure
component renderers in the FD C1-C8 order. No template engine, browser, JavaScript,
SVG/chart library, web framework, or public-site integration is added.

`snapshot_id` is calculated from canonical JSON without the id field, then embedded
as a top-level JSON field immediately after `schema_version` and exactly one Markdown
marker, `<!-- snapshot_id: sha256:<64-lowercase-hex> -->`, inside PrivateMethodNote.
Both projections are validated before promotion.

## TS-7. Test and Benchmark Stack

Reuse pytest and Hypothesis. Test XLSX files are created at runtime with openpyxl from
synthetic dates/NAVs and removed by pytest temporary-directory cleanup. Where a
malformed ZIP/XML shape cannot be emitted through openpyxl, build the smallest
synthetic OOXML/ZIP byte package needed for that case; never mutate or commit provider
bytes.

Verification layers:

1. pure unit/PBT tests for metrics, rank, regime, ordering, and serialization;
2. synthetic workbook parser and resource-adversary tests;
3. path/permission/log privacy tests;
4. transaction phase fault injection and recovery tests;
5. observed-shape local time/RSS benchmark; and
6. existing full repository quality gates.

The private runner itself is not scheduled in GitHub Actions. Synthetic unit tests
may run in normal repository CI and require no private data or secret.

## TS-8. Supported Runtime

Guarantee CPython 3.11+ on local macOS and Linux POSIX filesystems. Exact owner/mode,
exclusive-create, fsync, and replace semantics are part of correctness, so Windows
and filesystems that cannot verify them are rejected rather than supported on a
best-effort basis.

The CLI performs platform/capability checks before workbook reads. No platform-specific
branch may weaken AC-1.6 or AC-3.3-AC-3.7.

## Dependency and License Delta

| Package | Change | License | Runtime role |
| --- | --- | --- | --- |
| `openpyxl>=3.1,<4` | add | MIT | local XLSX read-only parser |
| `defusedxml>=0.7` | existing | PSF-derived | bounded XML preflight |
| pydantic v2 | existing | MIT | typed contracts/projection validation |
| pytest/Hypothesis | existing dev | MIT/MPL-2.0 | deterministic and property tests |

There is no new service, secret, paid API, native binary, database, background
daemon, or public asset.

## Rejected Alternatives

### Direct OOXML parser

Rejected. Implementing relationships, shared strings, styles, dates, cached formula
values, and worksheet variants directly creates a much larger correctness/security
surface than u139 needs. Stdlib ZIP inspection remains only the safety preflight.

### Operator CSV conversion

Rejected. It transfers schema/date/precision ambiguity to an undocumented manual
step and weakens reproducibility of the validation.

### pandas/NumPy

Rejected. They are unnecessary for twelve small time series and materially increase
install and memory cost.

### Float-only calculations

Rejected. Default float serialization does not meet the selected deterministic
ratio/rank precision contract.

### Decimal transcendental implementation

Rejected. A custom logarithm/square-root implementation is high-risk; the narrow,
golden-tested float boundary is sufficient.

### Always overwrite or version every run

Rejected. Always-overwrite weakens operator control; unbounded version directories
add private retention. Byte-identical no-op plus explicit `--replace` is the selected
policy.

### Windows best-effort permissions

Rejected. u139 requires verified owner-only modes and recoverable POSIX replacement;
a warning-only ACL substitute does not meet the private-output contract.
