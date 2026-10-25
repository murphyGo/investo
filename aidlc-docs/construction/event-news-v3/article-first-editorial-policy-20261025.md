# Article-first editorial policy

## User decision

Keep a section for each event. Prefer integrated news prose rather than a repeated
event/background/meaning/reaction questionnaire. Choose paragraphs, lists or separate
elements according to the subject; use structured elements only when they improve reading.
The user supplied this editorial decision directly on 2026-10-25.

## Stage decision

- Functional Design: bounded presentation refinement specified here and in C4 before code.
  No separate discovery/approval cycle: the user explicitly approved article-first prose
  and topic-dependent presentation. Existing u169/u171 evidence/content contracts apply.
- NFR Requirements: reuse existing source ownership, fact/time/causal proof, 24KiB/16KiB
  context, CLI-only budgets, R10/R13 and sole finalizer. No new external access, cost,
  operational activation, public projection field or source-data policy.
- Authorization: existing development/isolated worktree/commit-push instructions persist.

## Design and bounds

The private article retains separately validated factual/background/meaning/reaction
evidence. These are validation roles, not mandatory reader headings. A small optional
display plan groups and orders those existing texts into paragraph, plain bullet or
explicitly labeled list blocks. Plain bullets do not force evidence-role labels.
Blocks contain role references, never a second unchecked text field or model-written HTML.
Every populated text role is displayed exactly once; omitted/unavailable roles cannot be
requested. An absent plan defaults to prose. Sources and unavailable evidence stay truthful.

Default output: event headline followed by coherent prose paragraphs. No repeated blank
meaning/reaction rows. Numeric facts and missing-from-prose facts remain deterministic
supporting details; source timing, uncertainty and conditional assumptions remain available.
Coincidence-only reaction retains its explicit causal limitation. Conditional interpretation
retains mechanism/assumptions as a useful separate note. Severity/source-limited availability
is not removed. Public semantic projection, notification and frozen historical reader shapes
are unchanged; Markdown hashes capture the new presentation.

The original pre-presentation hard scan renders every fact as ordinary text even when
the reader chooses a table/collapsed supporting details. Presentation cannot exploit
the compliance scanner's table masking. Native numeric containment uses renderer-owned
field offsets rather than visible role labels, and edits only authorized optional
meaning/reaction spans. Primary facts and overlapping claims stay protected. After
containment, the display plan removes only the unavailable role.

When validated event digests exist, the short edition overview is prose. Missing digests
do not create a second list repeating each event headline. Source/time/limits remain
discoverable below each article; collection-limited availability remains visible.

## Acceptance and work

- [x] Add bounded display blocks and reject duplicate, missing, unknown or unavailable roles.
- [x] Make prose the default renderer; support optional lists and mixed event layouts.
- [x] Preserve every required fact, conditional qualifier, source/time limit and survivor rule.
- [x] Update generation policy: article-first writing, internal evidence roles, no filler fields.
- [x] Add meaningful native finalizer/rendering/compatibility and hard-negative tests.
- [x] Produce and open updated historical source-backed developer reference examples,
  clearly separate from current automatic producer/human acceptance.
- [x] Independent QA with no open P1/P2; local regression/static/policy/docs checks.
- [x] Exact-source full CI, scoped commit/push and remote delivery evidence.

Implementation `35d1dcca3391d9194c88ce404d492e1a88c937ca` was pushed to main and
the scoped feature branch. [Exact-source quality run](https://github.com/murphyGo/investo/actions/runs/40202461444)
passed 7,451 tests / one existing skip, all static/policy/docs checks and 29 client tests.
The reviewed preview pin uses that exact implementation; production pin/mode are unchanged.
See [delivery evidence](../../../docs/sessions/2026-10-25-event-v3-article-prose.md).

Actual daily content/source/HTTP/viewport/performance/cutover gates remain pending. This
editorial change does not assert that the thin automatic preview became content-rich.
