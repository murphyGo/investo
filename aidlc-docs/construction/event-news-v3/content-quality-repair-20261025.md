# Event v3 content-quality repair

## Trigger and evidence

The user opened the actual US preview and reported that it contains limitation notices
and little material to judge. Successful generation is insufficient for reader acceptance.
Human review remains pending; this output is not a normal positive acceptance case.

Actual run `40125141798`, source `817b356c`, routed 174 US items but transmitted only ten
Stage 1 documents: four FRED observations and six calendar items. The 24,154-byte buffer
contained zero news documents. The input selector reserved news before its 96-row cap, but
that reservation was lost at the later 24KiB context budget. Domestic transmitted 17 source
documents; crypto 16. All three outputs were source-limited.

Independent synthetic review also found two text-fact proof defects: ordinary positive
announcement/signing/approval/launch language cannot express status under the marker-only
validator, while `reported` elsewhere in a chunk can incorrectly bless a future, negative,
quoted or different-subject action. Korean subject detection additionally mistakes ordinary
topics and verb modifiers for entity names. These findings are implementation defects.

## Stage decision

This repairs the already approved u167/u168/u169 contracts C2–C4 and reader-quality goals;
no new product state, source provider, generation stage or operational activation is added.
Use the existing proof/reference models, sole finalizer and private preview. Source clause
support will be documented before implementation. Existing NFR cost/privacy/24KiB/16KiB,
source rights and activation gates remain intact. Earlier commit/push/development
authorization continues to apply. Original dirty work and the prior preview are preserved.

## Acceptance criteria and work

- [x] Preserve source-confirmed mandatory releases, then prioritize nonscheduled news/event evidence
  ahead of optional calendars and reference data at the actual Stage 1 byte budget. Preserve
  stable item remapping, source bounds and whole-row deferral; do not add article quotas.
- [x] Keep recurring observations without a source-confirmed new release optional and in
  reference panels when selected. An inferred observation does not consume a mandatory
  event slot; explicit required-release flags and release metadata remain protected.
- [x] Accept source-proven text actions through a shared deterministic assertion frame:
  same subject, performed/uttered action and object/value, with positive evidence. Reject
  unhandled future/negative/conditional/quotation/attribution frames at parser, canonical
  and finalizer boundaries. No inferred `actual` metadata or general verb whitelist bypass.
- [x] Distinguish Korean grammar/common concepts from actual new entity names while
  retaining unsupported names, numbers, roles and source ownership failures.
- [ ] Verify representative normal news plus hard negatives and the existing native57,
  required-actual, schema-two/shadow, budget and no-public-I/O regressions. Independent QA
  must have no open P1/P2 in the delivered scope.
- [ ] Produce a fresh real private preview containing source-backed normal news and its
  explanation, inspect the visible result and provide a readable local page. Record actual
  content limitations honestly; do not substitute a sealed empty document for this check.
- [ ] Complete appropriate static/full/policy/docs checks, scoped commits/push and exact
  remote confirmation. Update state and evidence without marking human/slot/release gates
  complete.

## Boundaries

No live production pin, schema-three active capability, source-body access gate, paid API,
extra LLM stage or scheduled-observation count changes. Private source/model text remains
in ignored encrypted/local artifacts. Public evidence contains closed counts, codes and
hashes. A fresh preview is developer validation; human annotation and scoring stay human.

## Assertion proof and presentation

Native nonnumeric facts use closed affirmative English/Korean subject-action-value
frames in one source clause (at most 240 codepoints). Predicate, subject and value
must resolve literally; status proof is that whole assertion or its performed verb.
Unsupported nested reporting, quotations, future/negative actuals and numeric-as-text
values fail closed. A narrowly labeled explicit completed/cancelled state row retains
the native replay contract; a status marker alone cannot invent a launch or agreement.

Article changes and digests preserve source actors, values, modality and the specific
semantic action. Closed Korean verb translations are permitted; cancellation/completion,
increase/decrease and unveiling/launch are distinct. The same bounded action check covers
background/meaning/reaction text. Numeric results alone do not prove a direction or action.
Arbitrary free paraphrases remain unsupported. This is a deliberately bounded proof,
not a general language understanding guarantee or human editorial acceptance.

Canonical nonnumeric values retain a tagged semantic-action discriminator plus a bounded
hash of their source value; the reader still receives the literal `original_value`.
Opposite actions therefore change the fact hash in the same fact slot, allowing conflict
or correction handling rather than silently becoming repeat evidence. Story resolution
reads only closed tagged action keys. Existing explicit state-value replay receipts retain
their original representation.

The current runtime production pin was independently advanced by concurrent insights work
to `0025497d`; it is preserved. Only the isolated event preview pin may be updated here.
