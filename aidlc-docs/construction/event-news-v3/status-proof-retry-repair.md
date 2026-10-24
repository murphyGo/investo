# Classifier status-proof retry repair

Actual final-source domestic run `40124245399` (`d44a5df3`) classified on its first call
but failed post-validation. The complete encrypted one-call record reproduced
`identity.fact_unbound` in `normalize_fact_bindings`: one plain-source fact lacked
`status_refs`. Two other events had no facts and normalized successfully. The classifier
had accepted the incomplete fact, so its existing bounded retry owner could not correct it.

The native identity contract already requires source status proof for every fact. Check
that same condition in `parse_context_classification` using existing `context.status_unbound`,
before accepting the classification. The prompt states that unsupported fact status must
not be inferred; omitting a nonmandatory fact is allowed, while required actuals remain
mandatory. No actual/forecast/scheduled/opinion marker is added or weakened.

- [x] Reject missing status proof in the classifier and canonical owner consistently.
- [x] Verify retry to a source-proven fact, and omission of an unsupported optional fact,
  using the existing maximum attempts/provider budget. Required actual omission still fails.
- [x] Verify numeric/status/metadata-role/source identity gates and native57/legacy behavior.
- [x] Independent read-only QA, exact-source CI and final same-source market previews.

No source values, metadata status, labels or returned refs are synthesized by code. Missing
proof remains an error if the model cannot correct it within the existing attempt budget.
Human/slot/viewport/performance/production/scheduled gates remain unchanged.

The lower source/context validator and its limited-support characterization remain intact;
only accepting a model classification into native generation requires the existing canonical
status proof. Canonical normalization retains its original `identity.fact_unbound` check.

Local focused **124 PASS (11.67s)** covers the native57 replay, both text-fact retry paths,
all four status roles, canonical identity, reference and component-prose gates. The regression
first proves that the incomplete textual fact passes the lower context validator, remains
limited-support and fails canonical normalization. This distinguishes the actual gap from
numeric literal association, which already rejected absent proof. Replaying the actual
domestic response now produces `context.status_unbound` at classifier acceptance.

Independent read-only QA: **151 PASS (12.63s)**, Ruff/format/diff passed, no open P1/P2.
Removing only the new two-line guard in memory makes all six new regressions fail, proving
they detect the previously accepted text-fact gap. Source-proven actual/forecast/scheduled/
quoted-opinion positives, required actual rejection and lower limited/no-fact/legacy/shadow
behavior remain intact. No private text, keys, external calls or source edits were used.

Final source `817b356c75e7e7cf32235cd1b217707e2993e211` passed exact
[quality 40125122575](https://github.com/murphyGo/investo/actions/runs/40125122575):
7,123 passed, one skipped (765.72s), Node29 and all required guards. Same-source
[private run 40125141798](https://github.com/murphyGo/automation-runtime/actions/runs/40125141798)
sealed all three markets: domestic zero events / one call, US four events / two calls,
crypto zero events / three calls. Ciphertext, Markdown and recording hashes were checked.
All outputs remain source-limited and human pending; no publication or production-state
writes occurred. This completes the bounded repair, not human or operational acceptance.
