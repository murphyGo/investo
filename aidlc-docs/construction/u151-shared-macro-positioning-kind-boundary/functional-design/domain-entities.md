# Domain Entities — u151 shared-macro-positioning-kind-boundary

**Date**: 2026-09-08
**Status**: Complete — validated at Step 7; final user approval recorded 2026-09-08T04:17:23Z.
**Provenance**: Reconstructed design; see the [plan](../../plans/u151-shared-macro-positioning-kind-boundary-functional-design-plan.md).

## 1. Entity catalog

| Entity | Role | u151 change |
|---|---|---|
| SharedMacroKey | Closed shared evidence vocabulary | New literal alias |
| NormalizedItem / routed occurrence | Existing source evidence per segment | No schema/routing change; producer exclusion at matcher |
| _SharedMacroCandidate / selected pair tuple | Transient rank and final shared selection | Same ranking, eligible inputs only |
| BundleContext | Cross-component same-run snapshot | One additive detected_macro_keys field |
| MarketStateSummary | Segment close-state | Unchanged |
| DailyThesisSignal | Existing core evidence input | Canonical one-key producer; generic schema unchanged |
| DailyThesisDecision / SegmentDailyThesisInput | Existing u124 result and rendering input | Unchanged decision algorithm and shapes |
| CauseMapDecision | Emitted/suppressed types and display | Same shape; typed input replaces labels |
| PublicDocumentContext / sealed outputs | Snapshot, survivor passes and final delivery | Preserve keys in copies; no DTO/seal change |

No database, new service, source API or persistent state machine is introduced.

## 2. New typed field and normal validation

The model contract belongs in `src/investo/models/bundle_context.py`:

```python
SharedMacroKey = Literal["fomc", "oil", "ust_yield"]
detected_macro_keys: frozenset[SharedMacroKey] = frozenset()
```

The two lines specify a design addition, not implemented application code.

| Input at normal model validation | Expected result |
|---|---|
| Field omitted | Empty frozenset |
| Empty supported collection | Empty frozenset |
| Valid key subset | Corresponding frozenset |
| Duplicate valid keys in accepted collection | Collapse duplicates |
| Unknown value, including a cause ID | Validation error |
| Translated label or differently cased key | Validation error |
| Explicit null | Validation error; field is not optional |

Do not turn unknown values into an empty default or infer keys from labels.
An unchecked `model_copy(update=...)` is not normal validation; owners may
carry forward validated values but must not inject invalid field contents.
No global model_copy override or global tightening of generic thesis key
strings is in scope.

## 3. BundleContext field ownership

| Field | Meaning | Preservation rule |
|---|---|---|
| bundle_id | Existing run identity | Unchanged |
| target_kst_date | Existing target date | Unchanged |
| segments | Existing dictionary of market-state summaries | Original routed close-state inputs |
| shared_macro_block | Existing optional rendered display | Same final selected pairs; legacy display permitted |
| detected_macro_keys | New selected evidence set | Only final qualified keys; default empty |
| cross_market_core_allowed | Existing allowed cause types | Independent cause-map gate |
| daily_thesis_signals | Existing signal tuple | Same eligibility, canonical one-match producer |
| daily_thesis_decision | Existing u124 decision | Same policy; not forced equal to full selected set |

For newly computed contexts, the shared block and typed keys derive from the
same selected pairs. This is a producer invariant, **not** a cross-field
validator rejecting legacy display-only contexts.
Frozen models are not deeply immutable dictionaries; preserve existing
defensive snapshot ownership, not a global immutability refactor.

## 4. Evidence relationships and cardinalities

A NormalizedItem may already occur in multiple routed segments. Qualification
counts distinct eligible segments, not distinct source identities. Original
source lists are retained. Metadata defects used by synthetic fixtures must
stay inside the existing flat strict string/integer/float model boundary;
missing or non-string scalar fields may exercise renderer omission without
inventing nested objects or relaxing validation.

Each eligible occurrence can yield candidates for multiple keys. Per-key
selection requires two eligible segments; UST additionally needs matching
treasury-rates/fred-macro evidence. A candidate retains the existing rank
tuple fields. Final selected pairs contain zero to three unique keys in
canonical order and are the sole source of keys/display projections.

For thesis, each eligible occurrence produces zero or one signal, selecting
the first matching final selected key. Generic signal key/tier fields remain
strings; the new producer is narrower. A decision may choose one strong key
or no key; it is not a second full selected-key registry.

| Shared key | Cause type |
|---|---|
| oil | geopolitical_oil_macro |
| fomc | fed_policy_event |
| ust_yield | fed_policy_event |

Cause candidates require a nonempty block as well as typed evidence.
Deduplicate them in oil/Fed order, then apply the existing context allowlist.
Missing evidence is distinct from forbidden evidence. global_systemic_risk
does not gain a producer.

## 5. Copy and finalization boundaries

| Boundary | Required behavior |
|---|---|
| compute_bundle_context construction | Supply all final selected keys |
| with_self_pending | Preserve keys while changing only existing self-state projection |
| Minimal prompt projection | Preserve its explicit fields; no full-model dump or new prompt field |
| _snapshot_bundle_context | Preserve keys; freeze existing dictionaries only |
| Active-survivor redecision | Filter original signals, reuse u124 owner, retain base keys/block |
| Explicit None / numeric minimal context | Keep None; never reconstruct semantic evidence |
| Final sealing / notification | Existing sealed Markdown and DTO derivation, no after-seal mutation |

Survivor handling does not reroute, rematch or reselect macros. The daily
decision uses only surviving eligible signals but may preserve a broader
base selected-key set. Snapshot MappingProxyType wrappers need not support
ordinary context JSON round-trip; that is not the new field's contract.

## 6. Serialization boundary

Stored type is frozenset. JSON-mode model dumping and model_dump_json emit
this field as a unique sorted key array. Ordinary BundleContext JSON parsing
restores semantic model equality, including typed keys.

| Stored key set | JSON field value |
|---|---|
| Empty | `[]` |
| oil | `["oil"]` |
| oil, fomc | `["fomc", "oil"]` |
| All three | `["fomc", "oil", "ust_yield"]` |

Do not claim whole-context byte canonicalization or a universal snapshot
JSON interface; only this sequence projection is canonicalized.
Explicit minimal prompts and lossy rendered Markdown are not invertible
serializers. Existing constructor fixtures that mean proven shared evidence
must explicitly set keys; display-only fixtures can keep default-empty keys.

## 7. Testable Properties

| Entity / operation | Category | Planned property |
|---|---|---|
| SharedMacroKey / BundleContext | Round-trip, Invariant | Valid subsets restore semantic equality; invalid keys/null rejected |
| Key JSON sequence | Invariant | Unique canonical order independent of set/hash iteration |
| Candidate / selected tuples | Commutativity, Invariant | Equivalent candidates preserve threshold/rank/selected evidence |
| Thesis signal producer | Invariant, Easy verification | At most one selected first-match per occurrence, no CFTC source |
| CauseMapDecision | Invariant | Relabel resilience, deduped ordered mapped/gated partition |
| Copies and survivors | Invariant | Keys preserved; original signal filtering and None branch maintained |
| Final output | Idempotence, Invariant | Fixed-input repeatability and valid delayed-row preservation |

Partial PBT: use structured model strategies with valid key subsets and
model-valid metadata defects, including empty collections and overlap cases.
Use seed `15120260908` per new property test with shrinking enabled; retain
minimal failing examples as regressions. Execution belongs to Code Generation.

No recursive induction or new stateful model. Existing rank/decision examples
are the reference/oracle boundary. No PBT properties identified for unchanged
I/O/delivery. Snapshot wrappers, minimal prompts and rendered Markdown have
no new inverse promise. For rendered-byte permutation properties, fix drafts,
active segments, market-state inputs and positioning row order; a new CFTC
item in an empty segment can still change activity.

| Acceptance | Entity evidence |
|---|---|
| AC-151.1 | Producer identity precedes metadata/title |
| AC-151.2 | Routed occurrences / distinct eligible segments |
| AC-151.3 | Selected pairs, BundleContext, narrower thesis signals |
| AC-151.4 | Closed keys and typed CauseMapDecision input |
| AC-151.5 | Copy/finalization boundaries, unchanged original source items |
| AC-151.6 | Canonical sequence, structured permutations and hash seeds |

## 8. Handoff

Read with [business logic](business-logic-model.md),
[business rules](business-rules.md) and [design validation](design-validation.md).
All implementation obligations carry into the
[Code Generation plan](../../plans/u151-shared-macro-positioning-kind-boundary-code-generation-plan.md).
Final user approval is recorded from the subsequent `진행시켜`;
Code Generation Step 1 is authorized. Runtime/production acceptance is not
claimed by this design record. DEBT-076 remains open.
