# NFR Requirements - `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Source**: `aidlc-docs/construction/plans/u144-public-document-finalization-contract-code-generation-plan.md`

These requirements make the new public-document boundary measurable. ACs are
`AC-1.1` through `AC-6.4`.

---

## NFR-1 Determinism and Idempotence

### AC-1.1 Byte determinism

Identical generated briefings and identical explicit finalization context
produce byte-equal Markdown, equal SHA-256 digests, equal block outcomes, and
equal warning/issue ordering.

Pinned by repeat-call unit tests for clean, data-limited, repaired, and optional
block-fallback bundles.

### AC-1.2 Stable ordering

Segment order follows `SEGMENT_ORDER`; issue codes are unique/sorted; block
outcomes follow first affected block order with stable code ordering. Input
mapping iteration order cannot change output.

Region IDs/spans follow the exhaustive FD `RegionSpec` priority and the active
pass's typed `PublicRegionExpectation`. Replacing one region and re-indexing
retains that expectation and leaves every unaffected region ID/order stable.
Each survivor retry recomputes the active daily-thesis decision from the same
base context and active tuple. `BundleContext is None` deterministically stays
`None`, disables thesis/cause expectations, and never calls the redecision
helper.

### AC-1.3 Supported idempotence

Every existing idempotent producer remains idempotent under the canonical
chain: no duplicate nav, disclaimer, macro/indicator/channel/cause/thesis,
visual/chart/carryover, watchpoint, diagnostic, or summary block appears on a
same-date rerun.

The production API may reject E5 as an input rather than re-finalize it; either
behavior must be explicit and tested. It must never silently double-transform.

### AC-1.4 No implicit time/state

Finalization performs no `datetime.now`, `date.today`, environment reads,
randomness, locale lookup, filesystem read/write, network call, sleep, or
subprocess call. All required date/evidence state is supplied explicitly.

## NFR-2 Integrity and Immutability

### AC-2.1 True terminal gate

All text-producing transforms finish before terminal validation. An AST/call-
graph regression test detects production Markdown mutation after validation or
seal.

### AC-2.2 Sealed byte integrity

`write_finalized_document` recomputes SHA-256 and rejects any mismatch before
destination-path mutation. A tampered test document leaves an existing file
byte-identical and creates no new file.

### AC-2.3 Required safety invariants remain blocking

Numeric-anchor contradictions, entity-fact contradictions, residual P0
compliance language, required-structure failure, and disclaimer failure cannot
be converted to optional omission or reader-safe vague copy.

### AC-2.4 Archive/index consistency

The final Markdown used for archive write is the same Markdown consumed by
evidence accounting, site-index/OG summary extraction, quality snapshot, replay,
and notification-summary derivation. Default segmented notifier consumes the E5
DTO whose conclusion/watchlist derive from those bytes and whose coverage
fields derive from E1. It checks mapping key/segment/date identity, accepts no
`Briefing`, and has no generated `market_summary` fallback. Tests compare
digests/exact strings across handoffs, exercise the sealed watchlist and typed
failed-coverage branch, and inject unsafe generated summary text to prove it
cannot escape. Missing or unsafe canonical conclusion is detected during
terminal validation, blocks that survivor attempt, and therefore participates
in fixed-point navigation/thesis recomputation before sealing.

## NFR-3 Graceful Degradation and Atomicity

### AC-3.1 Presentation defects degrade locally

A repairable surface issue or malformed optional block is repaired,
replaced, or omitted according to the fixed policy without dropping its market
segment. Required `## ⑥` is body-replaced, not omitted. Marker-backed optional
omission retains an empty wrapper and contributes no E5 artifact. Multiple
findings in one region are grouped and resolved once by the fixed precedence.
The outcome is recorded.

### AC-3.2 Bounded fallback

No block is repaired/replaced/omitted more than once per call. A failed
replacement or unmapped issue fails closed; there is no unbounded loop or LLM
retry.

### AC-3.3 Atomic valid-subset publication

In default segmented mode, reader-facing archive/index/quality writes and their
git staging begin only after every expected segment has a typed
final/generation-absent/trust-blocked outcome and at least one E5 is sealed.
The surviving one-to-three documents and their derived pages/assets are
promoted and committed in one existing transaction. Zero survivors or E8
produces zero new/changed **public destination** artifacts. Existing private
operational state files are outside E5/E6 and keep their current best-effort
lifecycle.

Current visual/chart files and any future file-backed carryover created before
E6 exist only under a run-owned temporary staging root; current text-only
carryover performs no file I/O. Tests snapshot public destinations, verify
staging is removed on every exit, and use promotion/write/quality-failure spies
to prove pre-git rollback. Once existing commit/push begins, `PublisherGitError`
keeps its current no-Pages/operator-recovery semantics; u144 does not promise
git-history compensation or byte rollback of a possibly created local commit.

Every supplement artifact ID resolves to one same-segment typed descriptor;
every E5 freezes non-omitted survivor IDs; E6 manifest equals their ordered
union. Blocked, absent, or explicitly omitted descriptors are never promoted.

### AC-3.4 Content and delivery partial are distinguishable

Publish success plus notification failure remains `PipelineStatus.PARTIAL` and
exit 0 when content is complete. A one/two-document committed E6 is
`PipelineStatus.PARTIAL`, `content_completeness=partial`, and exit 2; content
severity wins if notification also fails. Zero documents/E8 is `FAILED` and
exit 1. Tests pin all cases.

## NFR-4 Public Language, Observability, and Security

### AC-4.1 Zero raw public diagnostic leakage

All reader-visible regions in all three finalized segment fixtures contain zero
u108 forbidden raw labels. Protected collapsed diagnostics retain the expected
raw counters/state where existing contracts require them.

### AC-4.2 Current incident regression

The exact structural shape that caused run `29707052598`—a watchpoint row with
only part of its fields usable—finalizes without `public_diagnostic.raw_label`
and without dropping crypto.

The regression also asserts that the renderer returns a typed limited/rendered
outcome with valid card count/reason invariants; projection does not infer the
state from Korean text.

### AC-4.3 Bounded operator logs

Degradation/failure logs contain date, segment, phase/block, disposition,
sorted codes, and bounded counts only. Tests inject token-, chat-id-, URL-, and
raw-Markdown-shaped values and prove they do not appear in log messages or
structured extras.

### AC-4.4 GitHub visibility

Step summary and `$GITHUB_OUTPUT` report expected/finalized/published counts,
`publication_committed`, content completeness, and bounded finalization codes.
The workflow dispatches Pages for committed exit-0/exit-2 results, then
re-emits exit 2 so content-partial is red. E8 returns exit 1. A
notification-only partial remains exit 0 under the existing delivery contract.

## NFR-5 Performance and Resource Use

### AC-5.1 In-process bounded complexity

Finalization is linear in document size times the fixed documented pass count
and at most `len(SEGMENT_ORDER)` survivor passes. It performs no external I/O
and holds at most original drafts plus the current immutable layout/replacement
strings for each segment.

### AC-5.2 Benchmark budget

Add `scripts/benchmark_public_document_finalizer.py` with fixed options
`--segments 3 --bytes-per-segment 204800 --warmup 1 --iterations 5`. It builds
deterministic clean fixtures, runs one unmeasured warm-up, records each
`time.perf_counter_ns` duration, and records isolated-process peak RSS using
`resource.getrusage` with Linux/macOS unit normalization. It prints JSON with
Python/platform, input digest, median/max duration, and peak RSS delta.

The benchmark is informational and is not a wall-clock CI pass/fail gate,
because shared runners are heterogeneous. The unit code summary must record
the exact command and result; peak RSS delta above 64 MiB or a 200 KiB median
more than 3.0x the same-run 100 KiB median blocks closeout pending copy-
amplification review. Functional CI instead pins the fixed-point pass bound and
forbids I/O/LLM/subprocess calls inside the finalizer.

### AC-5.3 No new dependency or runtime service

Implementation uses stdlib plus existing in-tree packages. No Markdown parser,
LLM SDK/API, database, cache service, secret, or scheduled job is added.

## NFR-6 Compatibility, Testing, and Operations

### AC-6.1 Import-boundary compatibility

No publisher/briefing/notifier sibling import is introduced. Orchestrator may
import the publisher finalizer; publisher may import models/_internal. Existing
u114 AST boundary tests remain green.

### AC-6.2 Existing owner compatibility

u100/u108/u112/u123/u127 retain one canonical scanner, wording map, repair set,
evidence counter, and summary predicate. A repository search/test proves no
duplicated table or helper was introduced.

### AC-6.3 Test coverage

Minimum new coverage includes:

- lifecycle transition and seal tests;
- current/previous incident fixtures;
- optional-block fallback and hard-block matrices;
- exhaustive `RegionSpec` indexing/replacement, empty/non-empty anchor,
  marker-shell omission, and watchpoint-result contracts;
- complete/partial/zero-survivor fixed point and atomic valid-subset publish;
- active-survivor daily-thesis recomputation, `None -> None`, and neutral import
  ownership;
- run-owned asset staging, promotion, cleanup, pre-git rollback, and explicit
  existing git-failure semantics;
- sealed notification DTO identity/date, coverage, watchlist, missing-summary,
  and no-generated-summary-fallback cases;
- writer tamper/no-write behavior;
- production no-post-seal-mutation architecture test;
- property tests for phrase/Markdown/optional-field combinations;
- pipeline status and GitHub summary behavior.

### AC-6.4 Production closeout

The unit is not complete until:

1. exact-date replay for `2026-07-17` reports `ok=3 failed=0` and publishes all
   three archive paths;
2. commit/push succeeds;
3. internal status is `success` unless notification alone fails;
4. separate Pages workflow succeeds;
5. one additional normal-date replay/scheduled run remains green.

---

## Validation Commands

```bash
uv run --extra dev pytest \
  tests/unit/publisher/test_public_document.py \
  tests/unit/publisher/test_segment_reader_surface_quality.py \
  tests/unit/publisher/test_watchpoint_matrix.py \
  tests/unit/publisher/test_writer.py \
  tests/unit/orchestrator/test_run_pipeline.py \
  tests/unit/orchestrator/test_main.py \
  tests/integration/test_briefing_reader_format.py \
  tests/integration/test_bundle_reconciliation.py \
  tests/integration/test_pipeline.py
uv run --extra dev pytest
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run --extra dev mypy src
uv run python scripts/check_no_paid_apis.py
uv run --extra docs mkdocs build --strict
git diff --check

uv run python scripts/benchmark_public_document_finalizer.py \
  --segments 3 --bytes-per-segment 204800 --warmup 1 --iterations 5
```
