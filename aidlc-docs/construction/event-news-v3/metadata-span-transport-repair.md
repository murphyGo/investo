# Source metadata span transport repair

## Actual trigger

Private manual run `40121638323` at public source `29978b46e5d11ce03499a664d9f68565422f65ad`
sealed domestic and crypto schema-three documents with `source_limited` availability and zero
terminal events. US classification failed twice with `context.fact_invalid`. Both encrypted
model recordings were complete. Local replay through the unchanged classifier located the
  failure in exact source-metadata field binding: all four required items had valid actual,
period and status references, while every metric and unit reference was shifted by minus
one codepoint on attempt one and plus one codepoint on attempt two. No private text or
economic values are included in this receipt.

## Bounded change and acceptance criteria

The existing v3 context buffer carries source-owned metadata value spans beside each
document. Each chunk entry identifies the chunk and maps a metadata field to its exact
zero-based, end-exclusive `[start, end]` pair. Document/revision identifiers remain in the
existing context. This is a transport aid; model output continues to use full `ContextRef`
objects and the existing ownership, field-role, required-actual and finalization gates.

- [x] Derive spans from the same metadata-field boundary owner used by validation; preserve
  document bytes, identity and revision. Offer only spans allowed by the 1–240-codepoint
  reference bound.
- [x] Include every span-map byte in the existing 24KiB Stage 1 budget, keeping mandatory
  item reservation, contiguous transmitted IDs, source caps and whole-row deferral.
- [x] Tell Stage 1 to copy these exact coordinates; never infer missing values, repair
  returned references, relax field roles, add provider calls or enlarge time/token budgets.
- [x] Verify Unicode/escaped metadata, duplicate literal values in different fields,
  wrong-field and shifted-span rejection, required overflow and unchanged legacy behavior.
- [x] Replay private failed classifications locally using only the supplied exact metadata
  coordinates as a diagnostic counterfactual; report it separately from fresh model output.
- [ ] Obtain independent read-only review and exact-commit CI, then run the existing
  nonpublishing US private preview with the same recipient and default-off recording.

Actual human corpus acceptance, source-slot qualification, viewport, performance and
scheduled observation gates remain pending. Manual previews do not advance those counts.

## Local evidence

Focused tests: **94 PASS (7.22s)**, including the 57-case native replay and context
budget/handoff/reference gates. Ruff/format 776 files and mypy 328 source files passed.
The tests verify unchanged context serialization/revision, Unicode and JSON escapes,
identical text belonging to distinct metadata fields, blank/overlong-span exclusion,
copied references reaching the classifier, shifted/wrong-field/missing-unit rejection,
whole-row deferral and required overflow.

Independent read-only QA: **201 PASS (12.58s)**, Ruff/format/diff passed, no open P1/P2.
Additional probes cover nine Unicode/escape/key-like-value cases and equal literals in
different fields. Wrong-field, foreign-revision and unknown-chunk references remain rejected.

The local coordinate-only counterfactual used the complete encrypted US recordings.
The resulting buffer was 24,154 bytes, below the unchanged 24,576-byte cap, and retained
all four mandatory documents. On attempt two, replacing only eight shifted metric/unit
coordinates with their supplied map entries made the unchanged classifier pass. Attempt
one still failed after twelve coordinate replacements because it used `series_id` as a
subject metadata field; the existing field-role gate correctly rejected it. Stage 1 now
also states that `series_id`/`macro_label` are metric fields, with subject text available
in title/summary. There is no automatic response repair in production code.

This counterfactual is a diagnosis, not a fresh model success, human annotation or accepted
corpus case. The previous run remains failed with two valid source-limited sibling outputs.
