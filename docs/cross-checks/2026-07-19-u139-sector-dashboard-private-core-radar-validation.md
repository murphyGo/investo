# Cross-Check: u139 sector-dashboard-private-core-radar-validation

**Scope**: u139 private/manual NAV core-radar validation
**Date**: 2026-07-19
**Checked by**: Codex with independent fresh-eyes review
**Pre-u139 baseline**: `d19daf0`
**Implementation head**: `79dc4ee`

---

## Summary

| Status | Count | Percentage |
|---|---:|---:|
| Complete | 43 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **43** | **100%** |

**Overall Compliance**: 100% for the u139 scope.

FR-022's first four private-domain criteria are complete. Its public provider,
public coverage/freshness, Phase 2 flow, and post-web Telegram criteria remain
deliberately outside u139 and continue under u140/future units; they are not waived
or counted as u139 gaps.

## Requirement Scope

| Requirement | Status | Evidence |
|---|---|---|
| FR-022 private fixed universe | Complete | `models/sector.py`; `test_fixed_universe_identity_and_order` |
| FR-022 deterministic NAV metrics/regimes | Complete | `sector_dashboard/metrics.py`, `regime.py`; metric/regime PBT suites |
| FR-022 local XLSX and NAV-only labels | Complete | `private_input.py`, `private_render.py`, manual runner; focused suite and smoke |
| FR-022 raw/private public-boundary | Complete | path/log/artifact guards and empty public diff sentinel |
| NFR-002 zero paid service path | Complete | no-paid guard; no network/source imports |
| NFR-003 failure isolation/recovery | Complete | per-workbook isolation and phase fault-injection suites |
| NFR-005 bounded execution | Complete | ZIP/shape bounds; 5.583 s and 104.03 MiB benchmark |
| NFR-006 deterministic/PBT verification | Complete | 126 focused tests including Hypothesis and transaction faults |
| NFR-008 public-data compliance boundary | Complete | private-only path, labels, negative integration and public sentinel |
| US-010 private core-radar validation | Complete | normal 11/11 local synthetic run and deterministic report pair |

## Acceptance Criteria Matrix

| Criterion | Status | Evidence |
|---|---|---|
| AC-1.1 Private path boundary | Complete | `read_private_workbook_manifest`; `test_path_rejection_is_terminal_redacted_and_precedes_workbook_open`; four-location CLI matrix |
| AC-1.2 Symlink and file-type boundary | Complete | hardlink/path-swap/symlink tests in `test_private_input.py` and `test_private_render.py` |
| AC-1.3 Raw-input non-retention | Complete | `test_projection_contains_no_unapproved_private_or_public_claim_surface`; zero forbidden report/key hits; no committed workbook |
| AC-1.4 Redacted observability | Complete | malformed workbook and CLI error tests; output contains only stable status fields |
| AC-1.5 Zero network and zero service cost | Complete | two AST import guards plus no-paid-API check |
| AC-1.6 Owner-only output | Complete | owner/mode tests; smoke output directory `0700`, files `0600` |
| AC-1.7 Public-surface non-interference | Complete | negative integration guard; public diff hash unchanged; clean isolated tree |
| AC-2.1 ZIP size envelope | Complete | compressed/uncompressed/member/ratio ceiling tests |
| AC-2.2 ZIP structural safety | Complete | traversal, duplicate, encryption, malformed package, relationship, and defused-XML tests |
| AC-2.3 Workbook shape envelope | Complete | worksheet/cell-record limits and misleading-dimension tests |
| AC-2.4 Lazy sequential handling | Complete | `test_workbooks_are_opened_and_closed_strictly_sequentially` |
| AC-2.5 Runtime budget | Complete | 12 x 6,000 x 4 observed-shape run: 5.583 s, limit 10.0 s |
| AC-2.6 Peak-memory budget | Complete | same run: 104.03 MiB peak RSS, limit 256 MiB |
| AC-2.7 Bounded temporary state | Complete | caught-fault, cleanup, partial-marker, and managed-directory recovery tests |
| AC-3.1 Per-workbook failure isolation | Complete | `test_one_invalid_sector_is_isolated_and_yields_partial_redacted_bundle` |
| AC-3.2 Deterministic incomplete output | Complete | coverage-surface, warming-up, and insufficient-claim suppression tests |
| AC-3.3 Pair integrity | Complete | canonical pair, shared-id, at-rest validation, and mismatch rejection tests |
| AC-3.4 Idempotency and explicit replacement | Complete | commit idempotency/replace test; repeated smoke reports `no-op` with unchanged hashes |
| AC-3.5 Recoverable two-file transaction | Complete | fault injection at render/fsync/backup/promote/verify phases |
| AC-3.6 Interrupted-process recovery | Complete | complete/mismatched prepared, backup, rollback, cleanup, and evidence-disagreement tests |
| AC-3.7 Concurrent-run exclusion | Complete | live-lock/exclusive-marker tests; ratified bounded candidate/backup projection anchors authenticate recovery without private input metadata |
| AC-3.8 CLI completion semantics | Complete | CLI exit-state matrix and redacted transaction/argument failures |
| AC-4.1 Decimal calculation boundary | Complete | fixed formula vectors and Decimal property tests |
| AC-4.2 Transcendental float boundary | Complete | realized-volatility golden vector |
| AC-4.3 Snapshot quantization | Complete | model quantization/negative-zero/idempotence tests |
| AC-4.4 Report display precision | Complete | observed report scan: 11 ranks at four decimals and 77 metric cells at two decimals with `%`/`pp` units |
| AC-4.5 Canonical JSON and Markdown bytes | Complete | projection idempotence/round-trip PBT and exact pair validation |
| AC-4.6 Shared snapshot id | Complete | canonical pair and verifier tests; repeated smoke snapshot id unchanged |
| AC-4.7 Stable ordering | Complete | model ordering PBT, fixed-universe order, deterministic diagnostic/record tests |
| AC-4.8 Numeric property tests | Complete | return/excess, acceleration, tied midrank, rank bound, volatility/drawdown, hysteresis PBT |
| AC-5.1 Supported platform | Complete | explicit POSIX runtime gate; smoke executed on supported macOS POSIX |
| AC-5.2 Component boundary | Complete | AST and reverse-reference tests; no public-pipeline registration |
| AC-5.3 Dependency boundary | Complete | only `openpyxl>=3.1,<4` added; no-paid and lockfile review passed |
| AC-5.4 Explicit manual operation | Complete | required CLI arguments, private/NAV-only help, opt-in `--replace` tests |
| AC-5.5 Accessible private report | Complete | text headings/identifiers, stable tables, explicit missing reasons, no color dependency |
| AC-5.6 Existing behavior compatibility | Complete | full suite: 3550 passed with only 2 baseline-identical failures; focused u139: 126 passed; source/public integration negative guard |
| AC-6.1 Synthetic fixtures only | Complete | tests generate XLSX at runtime; git tracks no spreadsheet/private output |
| AC-6.2 Parser and state matrix | Complete | exact universe/schema/date/NAV/order/as-of/SPY/coverage/missing-reason/policy suite |
| AC-6.3 Resource-adversary matrix | Complete | ZIP/OOXML/shape/path-race/close-lifecycle adversary suite |
| AC-6.4 Transaction fault injection | Complete | full journal/pair/path-swap/hardlink/cleanup fault suite |
| AC-6.5 Privacy and public-boundary guard | Complete | log/artifact/import/registry/reverse-reference/public-diff scans |
| AC-6.6 Quality gates | Complete | focused/full pytest, Ruff, format, strict mypy, no-paid, diff, placeholder, strict MkDocs |
| AC-6.7 Operator-local smoke evidence | Complete | redacted 12-workbook benchmark, runtime/RSS/as-of/coverage/pair hashes only |

## Deterministic and Manual Evidence

| Evidence | Result |
|---|---|
| Focused suite | 126 passed |
| Full suite | 3550 passed, 2 baseline-identical DEBT-081 failures |
| Pre-u139 reproduction | Same 2 failures at `d19daf0` |
| Benchmark | 5.583 seconds; 104.03 MiB peak RSS |
| Coverage | `normal`, 11/11, as of 2026-07-17 |
| Snapshot id, repeated | `sha256:1f2a08f1e9ed9e3bd9b88f5e07ecdb52b41ebac522c11032f0bc3d8e400747b6` |
| Pair hash, repeated | `24161ffb238b9fabbe640a4e221cb301884657d13a976bf051dbfceafb3859ac` |
| Public diff sentinel, before/after | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Forbidden output paths | repository root, archive, site docs, tracked fixtures: exit 2 before input read |
| Required/forbidden projection scan | 5/5 labels; 0 forbidden report terms; 0 forbidden JSON keys |
| Display precision scan | 11 rows; 77 metric cells at two decimals; ranks at four decimals |

The pair evidence hash uses the explicit framing
`sha256(snapshot.json bytes + one NUL byte + report.md bytes)`. The benchmark ran on
CPython 3.11, supported macOS, and local storage. The production path is
single-process/sequential, so it does not consume extra host cores; its 104.03-MiB
absolute peak RSS is a conservative upper bound on the AC-2.6 above-baseline value.

## Quality Gate Detail

- Ruff check and format check passed.
- `mypy --strict src` passed over 232 source files.
- `scripts/check_no_paid_apis.py` passed.
- `git diff --check` passed.
- Unresolved-placeholder scan found no implementation placeholder; only the explicit
  compatibility catches for `NotImplementedError` and the NFR scan wording matched.
- `mkdocs build --strict` passed after the isolated full-test fixture changes were
  restored to clean `79dc4ee`.
- The two full-suite failures are exactly DEBT-081 and reproduce at `d19daf0`; they
  are recorded, not hidden or deselected from the reported full run.

## Project Rule Compliance

| Rule | Status | Evidence |
|---|---|---|
| No Anthropic SDK / LLM path | Complete | u139 imports no LLM module and makes no subprocess LLM call |
| Module DAG | Complete | `sector_dashboard` imports shared models only; no source/briefing/publisher/notifier/orchestrator dependency |
| Zero-cost principle | Complete | no network, secret, vendor SDK, or paid API; no-paid guard passed |
| Disclaimer/publisher behavior | Complete | existing briefing/publisher paths untouched |
| Telegram channel separation | Complete | notifier and Telegram paths untouched; no sector message added |
| Plugin interface | Complete | no source adapter or registry entry added |
| Public-data boundary | Complete | NAV/private labels mandatory; public authorization fields and claims forbidden |

## QA Verdict

**APPROVE**

No Critical, High, Medium, or Low u139 compliance gap remains. DEBT-081 is a
baseline-identical repository-wide test debt and is not caused by this unit.
The closeout review found and resolved one documentation-only Medium mismatch by
ratifying AC-3.7/TS-5's bounded candidate/backup projection anchors; no runtime code
change was needed.

## Proposed Actions

- No development-plan addition.
- No new TECH-DEBT item.
- Mark u139 Code Generation and cross-check complete.
- Keep u140 blocked until its independent public OHLCV source gate passes.
