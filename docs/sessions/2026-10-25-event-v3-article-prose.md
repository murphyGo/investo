# Event v3 article-first presentation

The user approved per-event sections and requested integrated news prose as the default,
with topic-dependent paragraphs, lists and supporting elements rather than a repeated
event/background/meaning/reaction template. This amends FR-024 and C4 within u169/u171.

## Implementation

Private `EventArticle.display_blocks` groups/orders already-validated text roles, with
paragraph/plain bullets/explicit labeled-list choices. Every populated role appears once;
unknown, missing, duplicate or unavailable parts are rejected. No second free-text field,
model-written HTML or public projection field was added. Existing responses default to
prose. Generation instructions treat the roles as evidence metadata, not a reader outline.

Required facts remain deterministic. `show_facts` can expose a table when useful; the
default keeps supporting facts/time/limits in expandable details. Collection limits remain
visible. Conditional mechanisms/assumptions and coincidence-only causal limits are retained.
Verified digests form a prose overview; missing digests do not repeat every event headline.

The sole finalizer scans all original facts as ordinary text before presentation, so table
masking/collapsed details cannot suppress compliance findings. Native numeric containment
uses renderer-owned field offsets, preserving primary facts and removing only authorized
optional context. Display blocks are reconciled after containment. Fact subjects are
resolved from their source refs, including subjects distinct from event actors.

## Validation and preview evidence

Independent QA found and closed a renderer `KeyError` for a separate fact subject. Its
final bounded review reported no open P1/P2, 151 focused tests and independent layout,
protected-fact and containment cases. Local broader integration/compatibility selection
passed 190 tests; later focused coverage also includes all three list/prose styles,
table/collapsed hard findings and protected claims sharing a paragraph with optional text.
Final follow-up QA independently passed 28 tests and six additional synthetic E1 cases,
with no new open P1/P2 after the three display styles and punctuation were finalized.
Ruff/mypy and strict docs checks are recorded separately from final exact-source CI.

Final local checks: 28 article/layout/containment regressions passed (1.35s), Ruff check
and format passed (823 files), mypy passed (346 source files), strict MkDocs built in
7.99s, policy/assets/theme/calendar guards passed, and chart client tests passed 29/29.
The broader 190-test selection additionally covers native finalization, claim boundaries,
content quality, context handoff and legacy generation. Exact-source full-suite results
belong to the delivered commit's GitHub `quality` check rather than the authored preview.

Updated local reference examples reuse the same qualified historical Fed/CFTC snapshots
and source dates (2026-09-16 / 2026-09-24). One uses default integrated prose; the FAQ case
uses prose plus plain bullets without role labels. Both pass native authored two-stage
replay and the sole finalizer. Their Markdown hashes are respectively
`16fa9e3c7797f7fbe758ce0f4415ba2eb616bd7abea01465c9b15167468bb857` and
`1cb69c98e16fc32d756f215be8068136c6be846ebfa5cdd37ce5f186c4e08b14`.
The page has two case sections and zero forced role labels in its main reader content.

These are explicitly developer-authored historical reference examples: zero live model
calls, zero new HTTP requests and all publication/notification/production-write flags false.
They do not increment actual producer/human corpus/source-slot/scheduled acceptance.
Raw source and reference artifacts remain local and ignored. Browser viewport acceptance
is not claimed from HTTP/DOM checks or opening Chrome.

## Delivery and exact-source CI

Implementation `35d1dcca3391d9194c88ce404d492e1a88c937ca` was pushed to main and
`codex/event-v3-article-prose-20261025`; both exact remote refs were confirmed.
[Quality run 40202461444](https://github.com/murphyGo/investo/actions/runs/40202461444)
completed successfully: **7,451 passed / one existing skip in 775.89s**, Ruff/format
823 files, mypy 346 sources, Node 29/29, policy/assets/theme/calendar guards and strict
MkDocs 8.75s. Final closeout only adds delivery documentation; the tested application,
tests, scripts, source policies and build/workflow trees remain identical to this commit.

On 2026-10-26 KST, `REVIEWED_EVENT_PREVIEW_SHA` was updated from `154b57a2` to the exact
tested implementation above and read back. Production `REVIEWED_CODE_SHA` remains
`0025497d4280d9bd72bcafd04ffafe026b8ad6fc` and `INVESTO_EVENT_BRIEFING_MODE=active`
continues the existing schema-two path. No new automatic producer run was dispatched.
The local reference is available at <http://127.0.0.1:54606/>; this process-local URL
does not establish viewport or production content acceptance.

## Boundaries

No active schema-three rollout, body HTTP permission, production pin, source activation,
model/provider budget, secret/auth policy or frozen sidecar schema was changed. Older
published Markdown is not rewritten. Actual automatic content readiness, human review,
viewport, source, performance and cutover gates remain pending.

Design and acceptance: [article-first policy](../../aidlc-docs/construction/event-news-v3/article-first-editorial-policy-20261025.md).
