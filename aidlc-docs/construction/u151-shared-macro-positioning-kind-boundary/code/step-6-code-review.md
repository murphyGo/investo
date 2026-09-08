# Independent cumulative code review — u151 Step 6

**Date**: 2026-09-08
**Reviewer**: read-only `u151_step6_review`, separate from implementation.
**Result**: Pass — no new Critical/High/Medium/Low finding.
**Closure judgment**: six ACs/five DoDs are technically satisfied; DEBT-076
may close after the main full gate. That gate passed before registry closure.
**Scope**: local Code Generation, not cross-check/integration/production.

## Full-file scope

All 13 cumulative Python files (5,492 lines) were fully read, not just their
diffs. The reviewer also read all four approved FD artifacts, CG plan,
unit DoDs/debt entry, Step 4/5 boundary records and final summary draft.

- `src/investo/models/bundle_context.py`
- `src/investo/orchestrator/bundle_context.py`
- `src/investo/publisher/cross_market_cause_map.py`
- `tests/_helpers/bundle_context_u151.py`
- `tests/integration/test_bundle_reconciliation.py`
- `tests/unit/models/test_bundle_context_allowlist.py`
- `tests/unit/orchestrator/test_bundle_context.py`
- `tests/unit/briefing/test_bundle_context_transport_u151.py`
- `tests/unit/publisher/test_cross_market_cause_map.py`
- `tests/unit/publisher/test_bundle_context_transport_u151.py`
- `tests/unit/publisher/test_daily_thesis_owner_u144.py`
- `tests/unit/publisher/test_public_document_types_u144.py`
- `tests/unit/publisher/test_shared_macro_positioning_regression_u151.py`

## Verdict

| Category | Result | Evidence |
|---|---|---|
| Correctness | Pass | Exact common producer exclusion, selected pair projections, canonical first-selected-match |
| Safety | Pass | Existing bounded/redacted logs, original inputs and terminal seal preserved |
| Reliability | Pass | Unknown/null rejection, legacy/None/minimal separation, original-signal survivors and existing gates |
| Maintainability | Pass | Removed label mirrors; typed three-key contract across only three production owners |
| Test Coverage | Pass | Six ACs, real three-segment finalizer, copy/prompt boundaries, ten properties and four hash seeds |

## Protocols applied

| Protocol | Trigger / result |
|---|---|
| Security Boundary | Source/model/log boundaries; fixed list-argument hash-seed subprocess with check=True and 20-second timeout; no new secret/raw payload sink |
| Data Integrity | Snapshot/survivor/terminal seal and original-input preservation; no new durable-write/recovery policy |
| Error Contract | Model validation and existing finalizer typed errors; no swallowed exception or reclassification |
| Memory | Per-call candidate/signal collections, at most three-key expansion; no long-lived cache/accumulator |
| Performance | Three-key bounded inner loop and unchanged ranking/signal sorting; CFTC short-circuits before matching |
| Resource Lifecycle | Bounded synchronous subprocess and managed test reads/fixtures; no production resource acquisition |
| Concurrency | N/A for changed logic: no new task/thread/lock or shared concurrent mutation |

The reviewer evaluated the full applicable protocol checklists. Unchanged
durable storage/auth/pool subcases are N/A, not claims of whole-system audit.

## Independent validation

- Focused cumulative/policy suite: **394 passed in 14.88s**.
- Properties rerun: **10 passed, 297 deselected in 4.56s**.
- PBT statistics: **500 passing generated examples, zero failures**;
  64 internal invalid draws are reported separately, not failed tests.
- Cumulative 13-file Ruff/check+format: Pass.
- Source/typed test/helper mypy: **261 files Pass**.
- `git diff --check`: Pass.

The independent module-boundary/no-paid-policy tests are included in the
394-case run. A separate no-SDK/no-paid guard command failed on uv cache
permissions, then waited for escalation until the review turn was interrupted
after 788.9s. It is **not** an independent guard Pass. The main agent had
already executed both guards successfully in the same checkout; its results
satisfy the full gate. No test defect or Python change resulted from this delay.

Main-owned full gate: **5,204 passed in 304.88s**; full Ruff/format, source
mypy, all policy guards and strict MkDocs/Material Pass. These results are
explicitly not presented as independently duplicated by the reviewer.

Exact independent commands (both exit 0):

```sh
uv run python -m pytest tests/integration/test_bundle_reconciliation.py tests/unit/models/test_bundle_context_allowlist.py tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_cross_market_cause_map.py tests/unit/publisher/test_daily_thesis_owner_u144.py tests/unit/publisher/test_public_document_types_u144.py tests/unit/briefing/test_bundle_context_transport_u151.py tests/unit/publisher/test_bundle_context_transport_u151.py tests/unit/publisher/test_shared_macro_positioning_regression_u151.py tests/unit/_internal/test_module_boundary.py tests/unit/sources/test_no_paid_apis.py -q
uv run python -m pytest tests/unit/models/test_bundle_context_allowlist.py tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_cross_market_cause_map.py tests/unit/publisher/test_bundle_context_transport_u151.py tests/unit/briefing/test_bundle_context_transport_u151.py tests/unit/publisher/test_shared_macro_positioning_regression_u151.py -k property --hypothesis-show-statistics -q
```

## AC and PBT reconciliation

AC-151.1..6 all Pass. Every CFTC group/title/valid scalar defect is excluded
from shared/core evidence; thresholds/UST/rank are preserved. Selected pair
projections and canonical one-signal behavior agree. Relabel/legacy/dedup/
forbidden controls and actual finalizer delayed rows pass. Equivalent inputs
are compared under fixed original drafts/state/row order; hash seeds and
canonical field JSON do not depend on set iteration.

| Property group | Tests | Passing generated examples |
|---|---|---|
| Model JSON and orchestrator preservation/permutations/subsets | 4 | 160 |
| Cause partition/relabel and injection | 2 | 160 |
| Publisher transport and minimal prompt | 2 | 120 |
| Real finalized rows/repeat and equivalent candidates | 2 | 60 |

Partial-enforcement PBT-02/03/07/08/09: Compliant. All ten properties use seed
15120260908, failure notes, default shrinking and ordinary pytest discovery.
The finalizer's finite one-second deadline follows recorded cold-run
investigation; it does not disable shrinking or suppress failures.
No blocking PBT finding. The full ten-rule matrix is in the
[implementation summary](summary.md).

## Findings, checklist and debt

Critical/High/Medium/Low: **none newly introduced by u151**.
No new u151 TECH-DEBT candidate. DEBT-076 closure is recommended.

Verified: shared candidate/thesis eligibility and original routing,
typed-key transport, gates/legacy distinction, logging, terminal ownership,
PBT oracles/reproduction, project module/no-paid rules and scoped changes.
No SDK/LLM/source/API/Telegram/disclaimer owner change; no trust-gate bypass.
The exact source-identity exclusion is the approved existing producer
contract, not a new adapter or universal taxonomy.

The existing arbitrary sealed-input glossary replay limitation, MappingProxy
whole-JSON non-guarantee and 13 baseline fixture mypy diagnostics remain
explicitly outside the passing scopes. The summary draft makes no false
production/global Build and Test claim; its pending placeholders can now
be replaced by actual completion.

Main recorded local closure at 2026-09-08T11:24:45Z; no reviewer code/document edit,
commit, live source/LLM/pipeline invocation, deployment or send.
