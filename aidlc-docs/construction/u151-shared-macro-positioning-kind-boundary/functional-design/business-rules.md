# Business Rules — u151 shared-macro-positioning-kind-boundary

**Date**: 2026-09-08
**Status**: Complete — validated at Step 7; final user approval recorded 2026-09-08T04:17:23Z.
**Scope**: Eight fixed contracts in the [Code Generation plan](../../plans/u151-shared-macro-positioning-kind-boundary-code-generation-plan.md).
**Provenance**: Reconstructed from the retained design record; see the [Functional Design plan](../../plans/u151-shared-macro-positioning-kind-boundary-functional-design-plan.md).

## BR-151-01 — Producer identity excludes positioning

Exact `source_name == "cftc-cot-positioning"` rejects all three shared
matchers and thesis evidence before category, title or metadata checks.
Energy/rates/crypto groups, absent groups and misleading FOMC/oil/UST titles
are equally excluded. Keep original routed items, not a filtered replacement.
Other producers retain u60 eligibility; no universal taxonomy is introduced.

## BR-151-02 — Preserve qualification prerequisites

Count distinct eligible segments per key. CFTC contributes zero segments,
regardless of its item count. The same eligible observation routed to two
segments is allowed; no independent-source count is added.

| Eligible evidence | Extra prerequisite | Outcome |
|---|---|---|
| Oil/FOMC in one segment plus any CFTC items | None | Not shared |
| Oil/FOMC in at least two segments | None | Select representative |
| UST in at least two segments, no matching canonical source | Canonical missing | Suppress UST key |
| UST in at least two segments with matching treasury-rates/fred-macro | Canonical satisfied | Select representative |

A canonical-source item that does not match UST is not qualifying evidence.

## BR-151-03 — Preserve ranking and all-key selection

Collect all eligible per-key candidates before applying Q2. Select the
minimum existing rank tuple: source rank, category rank, title rank,
source name, title, segment. Sort selected pairs `fomc, oil, ust_yield`.
Both typed keys and rendered shared block project exactly these final pairs.
A raw hit or a thesis winner is not the source of the full selected set.

## BR-151-04 — Closed typed transport

Add `SharedMacroKey = Literal["fomc", "oil", "ust_yield"]` and
`detected_macro_keys: frozenset[SharedMacroKey] = frozenset()`.
Omission/default empty means no proven cause-map keys. Normal validation
rejects unknown values and null; duplicate valid values collapse as a set.
Ordinary JSON serializes this field as a unique canonical sorted array.
Copy sites retain validated values and must not inject unchecked invalid
updates. Do not globally override model copying or tighten generic thesis keys.

## BR-151-05 — Q2=A, one selected first-match signal

One eligible routed item per segment emits at most one core signal. Inspect
only final selected keys in `fomc, oil, ust_yield` order; stop at first match.

| Producer / item matches | Final selected keys | Signal |
|---|---|---|
| Eligible, FOMC and oil | fomc, oil | fomc only |
| Eligible, FOMC and oil | oil | oil only |
| Eligible, oil and UST | oil, ust_yield | oil only |
| Eligible, oil and UST | ust_yield | ust_yield only |
| Eligible, FOMC and oil | Empty or ust_yield | None |
| CFTC, any title | Any selected subset | None |

Keep `tier=core`, existing evidence labels and producer identity source IDs.
Sort final signals by key, segment, evidence label, source IDs. Do not emit
all matches, shrink shared keys/block or modify representative ranking.

## BR-151-06 — Preserve thesis decision semantics

The existing u124 owner chooses omit with fewer than two active segments,
strong with at least two active supporting segments for a qualifying core
key, otherwise data_limited. Its selected thesis key can be narrower than
the shared-key set. Keep its global cause allowlist and decision ranking.
CFTC-only active segments may receive data_limited; removing positioning
promotion is not a demand to erase every thesis line or CFTC mention.

## BR-151-07 — Typed cause-map with independent gating

Map oil to geopolitical_oil_macro, and FOMC/UST to fed_policy_event.
Deduplicate; output oil cause then Fed cause. global_systemic_risk stays dormant.

| Block | Typed keys | Allowed causes | Result |
|---|---|---|---|
| None or empty | Any valid subset | Any | No candidate, emission or suppression |
| Nonempty | Empty | Any | No candidate, emission or suppression |
| Nonempty | oil | Oil allowed | Emit oil cause |
| Nonempty | fomc, ust_yield | Fed allowed | Emit Fed once |
| Nonempty | All three | Both allowed | Emit oil, then Fed |
| Nonempty | oil | Oil forbidden | Suppress oil, render nothing |
| Relabeled nonempty block | Same keys | Same allowlist | Same decision |

A forbidden mapped candidate is suppressed, never demoted into prose.
No Korean string parser, new cause type or change to wording/injection shape.

## BR-151-08 — Q1=A, display-only legacy compatibility

A nonempty legacy block with omitted/default-empty keys stays displayable
but contributes no deterministic cause-map evidence. Do not add a cross-field
validation failure or silently infer keys. Keys alone never create a block.
This rule does not reconstruct or reset an explicitly provided legacy thesis
decision. Constructor fixtures that mean proven evidence must supply keys.

## BR-151-09 — Preserve copy and containment boundaries

Self-pending copies, publisher defensive snapshots and survivor projections
preserve validated typed keys. Snapshot MappingProxyType fields are an
internal representation, not a new JSON-round-trip promise. Survivor
redecision filters original signals and reuses the existing owner; never
reroute/rematch/reselect shared keys or replace its decision policy.
Explicit None stays None. Minimal numeric containment intentionally drops
semantic context; do not restore it. Minimal prompt projection remains explicit.

## BR-151-10 — Preserve delayed positioning rows exactly within existing policy

Retain US/crypto group allowlists, original order and cap of three rows, net
contracts, percent OI, as-of/release dates and `주간 지연`. No new domestic row.
Keep original source tuples and prompt inputs.

The baseline `_meta` returns a field only if it is a nonblank string.
Missing, blank or non-string required values omit a row under the existing
renderer. A nonblank but semantically malformed numeric/date string is
**not guaranteed to be omitted**: this owner does not parse every value/date.
This clarification preserves current behavior, not a new validation policy.

Synthetic missing/malformed metadata must remain valid under NormalizedItem's
flat scalar contract. Do not use nested objects or booleans that the base
model rejects, or relax that model to make a positioning fixture constructible.

## BR-151-11 — Bounded existing diagnostics

Use the existing candidate logger with `positioning_not_shared_macro`.
Preserve bounded/redacted title preview and hash behavior; add no raw
metadata, URL, full payload, secrets or public diagnostic surface.
No new error, retry or source-health classification is introduced.

## BR-151-12 — Preserve terminal and scope contracts

No change to trust gates, seals, notification DTO, fallback dispositions,
source collection/routing, scheduling, network, dependency, cost or public
publication. No post-seal edits, arbitrary LLM paragraph rewriting or
historical backfill. DEBT-076 closes only after implementation validation.

## Testable Properties

| Component | Category | Obligation |
|---|---|---|
| Producer eligibility | Invariant | Every valid CFTC fixture yields no candidate/core signal |
| Candidate selection | Commutativity, Invariant | Controlled permutations preserve thresholds, rank and full selected set |
| Signal production | Invariant, Easy verification | Zero-or-one canonical selected match per routed occurrence |
| Model serialization | Round-trip, Invariant | Equivalent ordinary context after JSON; closed keys and sorted array |
| Cause-map | Invariant | Relabel resilience, deduplication and disjoint emitted/suppressed outputs |
| Context copies | Invariant | New field retained; surviving original signals only |
| Finalized output | Idempotence, Invariant | Fixed inputs repeat; legitimate delayed rows remain |

No recursive induction or new stateful service. Preserved rank/decision
examples form the oracle boundary. No PBT properties identified for unchanged
I/O/delivery; lossy rendering and minimal prompts have no inverse.
Full-byte permutation comparisons fix drafts, active/market-state inputs and
positioning row order. Adding CFTC to an empty segment can change activity;
do not assert global pipeline invariance under that change.
Partial PBT and structured seeded generators are planned, not executed.

## Acceptance and fixed-contract traceability

| AC | Rules |
|---|---|
| AC-151.1 | BR-151-01, BR-151-11 |
| AC-151.2 | BR-151-01, BR-151-02, BR-151-03 |
| AC-151.3 | BR-151-03, BR-151-04, BR-151-05, BR-151-06 |
| AC-151.4 | BR-151-04, BR-151-07, BR-151-08 |
| AC-151.5 | BR-151-09, BR-151-10, BR-151-12 |
| AC-151.6 | BR-151-03, BR-151-04, BR-151-05, BR-151-09, BR-151-12 |

| Fixed contract | Rules |
|---|---|
| FC-1 | BR-151-04 |
| FC-2 | BR-151-01 |
| FC-3 | BR-151-01, BR-151-02, BR-151-05, BR-151-10 |
| FC-4 | BR-151-03, BR-151-04 |
| FC-5 | BR-151-07 |
| FC-6 | BR-151-08 |
| FC-7 | BR-151-11 |
| FC-8 | BR-151-05, BR-151-06 |

## Handoff

[Business logic](business-logic-model.md), [entities](domain-entities.md) and
[validation](design-validation.md) were reconciled at Step 7. Final design
approval is recorded from the subsequent `진행시켜`; Code Generation
Step 1 is authorized. Runtime acceptance is not claimed by this design record.
