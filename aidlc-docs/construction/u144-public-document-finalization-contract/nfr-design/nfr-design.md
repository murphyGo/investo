# NFR Design - `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Source**: `../nfr-requirements/nfr-requirements.md`

This design fixes the non-functional mechanisms that span the pure finalizer,
filesystem transaction, CLI exit mapping, and GitHub workflow. It adds no
service, secret, paid API, or persisted schema.

---

## 1. Pure finalizer boundary

`finalize_public_bundle()` receives only E1 values and performs no I/O, clock,
environment, network, subprocess, or random access. The orchestrator supplies
the timezone-aware entity observation instant already associated with the run.

The survivor algorithm is bounded:

```text
maximum passes = len(SEGMENT_ORDER) = 3
each pass starts from original generated Briefing values
one pass may add one or more trust_blocked outcomes
BundleContext None stays None; otherwise redecide + validate active thesis
no new blockers => seal the active subset
no active segment => E8 before public writes
```

Presentation findings covered by the exhaustive disposition table cannot enter
the blocked set. This distinction prevents today's wording defect from being
misclassified as a missing market segment.

## 2. RunArtifactStaging

The orchestrator owns one context-managed temporary directory for the run.

```python
@dataclass(frozen=True, slots=True)
class StagedArtifact:
    artifact_id: str
    segment: MarketSegment
    kind: PublicSupplementKind
    relative_public_path: PurePosixPath
    staged_path: Path
    sha256: str

@contextmanager
def run_artifact_staging(target_date: date) -> Iterator[Path]: ...
```

Rules:

- current visual/chart file helpers and any future file-backed carryover helper
  receive the staging root explicitly; current text-only carryover does not;
- a staged path must resolve beneath that root;
- a relative public path cannot be absolute and cannot contain `..`;
- writers return the full descriptor and digest after closing the file;
- supplements reference artifact IDs; finalizer preflight enforces same-segment
  referential integrity and path/ID shape without reading files;
- marker-backed omission keeps an empty marker shell and an E7 outcome;
- each E5 freezes its non-omitted surviving artifact IDs and E6 promotion
  manifest equals their ordered union;
- no public destination is created before E6;
- the context manager removes staging on success, E8, cancellation, or any
  later exception.

After E6, the existing publish transaction takes its destination snapshot,
rechecks staging-root ownership and staged digests, promotes only the E6
manifest, writes sealed Markdown and derived index/quality files, then commits.
Promotion/write/quality failure invokes the existing destination rollback
before the staging context exits. Once commit/push begins, existing
`PublisherGitError` semantics apply: staging still cleans, Pages is not
dispatched, and operator recovery is required; no automatic local-history
rewrite or byte-rollback promise is added.

## 3. Seal and destination integrity

`write_finalized_document()` verifies in this order before destination
mutation:

1. target date and segment;
2. `sha256(final briefing.rendered_markdown)` equals E5 digest;
3. archive path matches target date/segment;
4. canonical and short disclaimer invariants pass.

Index, OG, quality, and replay code receive the same sealed string or E5
compatibility briefing. Default segmented notification instead receives E5
`PublicNotificationSummary`, derived/validated from final-layout
conclusion/watchlist plus E1 typed coverage as the last terminal-validation
step, with URLs and existing typed lookahead/price inputs supplied separately.
The validated E2 draft stores the DTO and seal only copies it; a derivation
failure returns a trust block to the survivor fixed point. The notifier checks
DTO key/segment/date identity and cannot accept a `Briefing`, read generated
`Briefing.market_summary`, or select fallback prose. Consumers may derive
artifacts but cannot return a new E5. The only production construction of a
final compatibility `Briefing` is the module-private seal factory.

## 4. CLI result model

Add a backward-compatible result field:

```python
ContentCompleteness = Literal["complete", "partial", "none"]

class PipelineResult(...):
    content_completeness: ContentCompleteness = "complete"
    segment_outcomes: tuple[SegmentFinalizationOutcome, ...] = ()
    publication_committed: bool = False
```

Exit mapping:

| Public result | Notification | Status | Exit |
|---|---|---|---|
| 3/3 committed | success | `SUCCESS` | 0 |
| 3/3 committed | failed | `PARTIAL` | 0 |
| 1/3 or 2/3 committed | either | `PARTIAL` | 2 |
| 0/3 or E8 before commit | not run | `FAILED` | 1 |

Content completeness, not the overloaded `PipelineStatus.PARTIAL` value, owns
the exit-0/exit-2 distinction.

Before returning, `__main__` writes bounded outputs to `$GITHUB_OUTPUT` when
the variable is available:

```text
pipeline_status=success|partial|failed
content_completeness=complete|partial|none
publication_committed=true|false
expected_segments=3
finalized_segments=0..3
published_segments=0..3
```

No Markdown, URL query, token, chat ID, or raw exception text enters outputs.

## 5. `daily-briefing.yml` control flow

The existing pipeline step becomes a shell wrapper with `id: pipeline`:

```bash
set +e
uv run python -m investo
pipeline_rc=$?
echo "process_exit_code=$pipeline_rc" >> "$GITHUB_OUTPUT"
exit 0
```

`__main__` writes the remaining outputs to the same file. The wrapper itself is
green so later control flow can inspect the committed result.

The existing Pages dispatch step runs only when:

```text
steps.pipeline.outputs.publication_committed == 'true'
```

A final `if: always()` step exits with the captured `process_exit_code`. Blank,
non-numeric, or values outside `0|1|2` fail closed as exit 1. Therefore:

- normal/notifier-only partial commits dispatch Pages and end green;
- content-partial commits dispatch Pages and then end red with exit 2;
- no-commit failures skip Pages and end red with exit 1.

Workflow tests parse YAML and pin step IDs, conditions, and final assertion.

## 6. Performance measurement

`scripts/benchmark_public_document_finalizer.py` runs in a fresh process. It
uses deterministic clean documents, one warm-up, five timed iterations, and
platform-normalized `resource.getrusage` peak RSS. It emits machine-readable
JSON and never runs in the default pytest suite.

Closeout records both 100 KiB and 200 KiB results. A 200/100 median ratio above
3.0 or peak RSS delta above 64 MiB blocks completion for investigation; absolute
wall-clock time is informational because local and hosted runners differ.

## 7. Verification matrix

| Failure point | Expected public destination | Staging | Exit/Pages |
|---|---|---|---|
| presentation fallback succeeds | valid commit | cleaned | 0, Pages |
| one trust block, siblings valid | partial commit + absence UX | cleaned | 2, Pages then red |
| zero survivors/E8 | unchanged | cleaned | 1, no Pages |
| staged digest mismatch | rollback/unchanged | cleaned | 1, no Pages |
| archive/index/quality write failure | rollback/unchanged | cleaned | 1, no Pages |
| git commit/push failure | existing `PublisherGitError` state; no rollback claim after git begins | cleaned | 1, no Pages; operator recovery |
| notifier failure after complete commit | committed | cleaned | 0, Pages |
