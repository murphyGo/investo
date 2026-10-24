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
- [ ] Independent read-only QA, exact-source CI and final same-source market previews.

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
