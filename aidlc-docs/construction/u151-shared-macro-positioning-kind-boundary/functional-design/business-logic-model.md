# Business Logic Model — u151 shared-macro-positioning-kind-boundary

**Date**: 2026-09-08
**Status**: Complete — validated at Step 7; final user approval recorded 2026-09-08T04:17:23Z.
**Provenance**: Reconstructed design, not byte-exact recovery; see the [plan](../../plans/u151-shared-macro-positioning-kind-boundary-functional-design-plan.md).
**Traceability**: US-002/003/005; FR-002/008/013/015; NFR-003/005/006/007-R13; DEBT-076.

## 1. Purpose and boundary

A weekly contract position is not evidence of an oil price, Treasury yield or
policy event. Exclude the existing CFTC positioning producer from the three
shared classifiers and core thesis signals, without removing its source items
or legitimate delayed positioning rows. This is bounded producer exclusion,
not a universal financial taxonomy or an LLM causality detector.

Existing u60 thresholds/ranking, u74 cause gating, u107 routing/row ownership,
u124 thesis decisions and u144 finalizer/seals remain authoritative.
No new source, endpoint, fee, dependency, key, retry, schedule or public DTO.

## 2. Inputs, outputs and owners

| Boundary | Input | Output / owner |
|---|---|---|
| Source routing | Existing valid NormalizedItem occurrences per segment | Original routed tuples remain unchanged |
| Shared classification | Routed item, producer identity, existing matcher | Eligible per-key candidates; orchestrator |
| Selection | Candidates grouped by key and distinct segments | Sorted selected key/title pairs; u60 |
| Shared projections | Final selected pairs only | Typed key frozenset and existing display block |
| Thesis evidence | Eligible occurrences and selected keys | At most one core signal per occurrence/segment |
| Thesis decision | Signals and active segments | Existing strong/data_limited/omit policy |
| Cause-map | Nonempty block, typed keys, independent allowlist | Existing emitted/suppressed decision |
| Final document | Existing original sources and context snapshots | Sealed Markdown and derived notification summary |

## 3. Shared classification and selection

1. At the common matcher entry used by both detection and thesis collection,
   reject `source_name == "cftc-cot-positioning"` before title/category/metadata
   matching. Misleading oil/FOMC/rates titles and missing metadata cannot
   override producer identity.
2. For every other routed occurrence, collect candidates for **all** matching
   existing keys. The Q2 one-signal rule does not apply here.
3. Require at least two **distinct segments** for a key, not two items or
   sources. Existing routing of the same observation into two segments may
   satisfy this rule; do not add an independent-source requirement.
4. For `ust_yield` only, require a matching eligible candidate from
   `treasury-rates` or `fred-macro`. Their mere presence without matching
   does not satisfy the prerequisite. Do not add this guard to oil/FOMC.
5. Select the minimum representative by the unchanged tuple
   `(source_rank, category_rank, title_rank, source_name, title, segment)`.
6. Sort final selected pairs by key: `fomc, oil, ust_yield`.
7. Derive both `detected_macro_keys` and `shared_macro_block` from those
   final pairs, never from raw hits or thesis signal winners.

No candidate yields no selected pair. No selected pairs yields an empty
typed key set and the existing absent block. Retain every selected key even
if Q2 leaves it with no thesis signal winner.

## 4. Thesis evidence and decision

For each eligible routed item in each segment, visit only the final selected
keys in canonical order. Emit a single signal for the first matching key,
then stop; emit none when there is no selected match. CFTC emits none.

A signal keeps existing fields: segment, key, `tier="core"`,
existing evidence label, and `source_ids=(item.source_name,)`. Sort signals
by `(key, segment, evidence_label, source_ids)`. No set iteration order may
choose the winner. Do not narrow the shared generic `DailyThesisSignal.key`
model globally; constrain this producer.

| Selected keys | Item matches | Thesis result |
|---|---|---|
| fomc, oil | fomc and oil | One fomc signal |
| oil | fomc and oil | One oil signal |
| ust_yield | fomc and oil | No signal |
| All three | CFTC title matching all | No signal |

Keep u124 decision semantics: fewer than two active segments means `omit`;
a shared core key with support in at least two active segments yields the
existing `strong` decision; otherwise `data_limited`. The daily decision
can name fewer keys than the full selected set. Its existing global cause
allowlist is not replaced by the context-specific cause-map allowlist.

CFTC-only routed segments can still be active and receive data-limited
fallback. The design does not ban every CFTC word or remove every thesis line.

## 5. Copy, prompt and survivor lifecycle

`compute_bundle_context` builds the model once from original routed inputs.
Market close-state selection and prompt source lists still see those original
items; classification filtering must not replace the routed tuples.

`with_self_pending` changes only its existing segment-state projection and
preserves typed keys. Explicit minimal prompt serialization keeps its current
field selection, not a new whole-model dump. Its existing block-presence
`is not None` test is separate from cause-map's nonempty-block truth test.

Publisher snapshots defensively freeze the existing dictionary-backed fields
and preserve the new frozenset. An active-survivor pass filters original
signals and reuses u124 redecision; it does not reroute, rematch or reselect
macros, and it keeps the base shared keys/block. An explicit absent context
stays `None`. Numeric minimal-document containment deliberately removes
semantic context; do not restore keys or thesis into that branch.
No after-seal mutation or alternate notification derivation is added.

## 6. Typed cause-map and legacy compatibility

| Typed key | Candidate cause |
|---|---|
| oil | geopolitical_oil_macro |
| fomc | fed_policy_event |
| ust_yield | fed_policy_event |

Deduplicate and preserve existing output order: oil cause, then Fed cause.
`global_systemic_risk` remains dormant even if allowed.

Require a nonempty shared block **and** at least one mapped typed key.
Then independently apply `cross_market_core_allowed`; forbidden candidates
are suppressed, not converted to background prose. Missing evidence means
no candidate, not a suppressed candidate. Preserve CauseMapDecision shape
and wording/injection semantics.

Q1=A: a legacy nonempty block with omitted/default-empty keys may display
but yields no cause-map line. Never parse Korean labels as evidence. Keys
without a block do not synthesize one. Do not add a cross-field model error
for legacy display-only contexts or reset caller-supplied thesis decisions.

## 7. Positioning preservation and diagnostics

Retain u107 US/crypto group allowlists, cap of three rows, net contracts,
percent of open interest, as-of/release dates and `주간 지연`. Add no domestic
positioning row. Missing/blank/non-string required fields are omitted under
the existing renderer's string-presence rule; do not invent general numeric
or date validation. See BR-151-10 for the exact malformed-string boundary.

Log rejection through the existing bounded, redacted candidate logger with
reason `positioning_not_shared_macro`. No new raw metadata, URL, full payload,
secret, or public issue code. Title preview stays bounded and redacted.

## 8. Acceptance scenarios

| Scenario | Required result | AC |
|---|---|---|
| Any CFTC group with title matching all three keys | No shared candidate or core signal | AC-151.1 |
| One eligible oil segment plus many CFTC occurrences | No shared oil qualification | AC-151.2 |
| Two eligible segments, including valid UST prerequisite where needed | Existing threshold and rank preserved | AC-151.2/3 |
| Overlap across selected-key subsets | One canonical signal without losing selected keys | AC-151.3/6 |
| Rename shared display labels, retain keys | Same cause decision | AC-151.4 |
| Legacy block / empty keys; forbidden mapped cause | Display only / suppression, respectively | AC-151.4 |
| Three finalized segments with valid delayed positioning | No deterministic promotion; rows/dates/lag remain | AC-151.5 |
| Equivalent candidate permutations / hash seeds | Same selected evidence, keys, signals and causes | AC-151.6 |

## 9. Testable Properties

| Component | Category | Planned property / boundary |
|---|---|---|
| Eligibility | Invariant | CFTC contributes zero candidates/signals across valid domain fixtures |
| Selection | Invariant, Commutativity | Equivalent candidate permutation preserves threshold, representative and ordered pairs |
| Thesis producer | Invariant | Zero-or-one selected-key signal per occurrence; canonical first match |
| Typed model | Round-trip, Invariant | Ordinary context JSON restores equivalent values; closed keys and canonical key array |
| Cause-map | Invariant, Easy verification | Label changes cannot change candidates; emitted/suppressed partition mapped causes |
| Copy/survivor | Invariant | Keys preserved; only active signals influence existing redecision |
| Final composition | Idempotence, Invariant | Controlled repeated rendering preserves bytes and safe delayed rows |

Partial PBT applies to pure functions and serialization. Use structured
NormalizedItem/BundleContext strategies, valid scalar metadata defects,
selected-key subsets, overlap cases, permutations and hash-seed checks.
Preserved rank/decision example cases provide an oracle boundary, not a new
optimized algorithm. Induction is not applicable: no recursive algorithm.
No PBT properties identified for unchanged network/delivery I/O; no new
stateful service. Markdown rendering and minimal prompt projection are lossy,
so they do not promise an inverse.

Full rendered-byte equivalence requires fixed draft content, active segments,
market-state inputs and positioning row order. Inserting a first CFTC item
into an empty segment may change active membership; global pipeline
invariance under such insertion is **not** claimed.

## 10. Handoff

Rules: [business-rules.md](business-rules.md).
Entities: [domain-entities.md](domain-entities.md).
Review: [design-validation.md](design-validation.md).
Properties carry into [Code Generation](../../plans/u151-shared-macro-positioning-kind-boundary-code-generation-plan.md).
The user's `진행시켜` after final presentation approved this design and
Code Generation Step 1. See the code plan for current implementation progress;
this document is a design contract, not runtime acceptance. DEBT-076 remains open.
