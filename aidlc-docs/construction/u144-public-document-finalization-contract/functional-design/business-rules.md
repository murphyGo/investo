# Business Rules - `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Source**: `aidlc-docs/construction/plans/u144-public-document-finalization-contract-code-generation-plan.md`

Rules are binding and listed in lifecycle order. Entity/invariant references
point to `domain-entities.md`.

---

## R1. One publisher boundary owns public-document finalization

`publisher.public_document.finalize_public_bundle()` is the only default
production transition from generated `Briefing` objects to publishable segment
documents.

- Orchestrator supplies E1 and consumes E6.
- `segment_reader_format`, visual/chart/carryover injectors, and existing gates
  are collaborators beneath that boundary.
- No second finalizer, parallel scanner, or LLM copy-edit path is introduced.

## R2. Generated and finalized artifacts are distinct

`Briefing` returned by u2 is a generated draft. It is not authority for the
bytes ultimately written after post-generation formatting.

- The archive-byte authority is E5 `FinalizedPublicDocument.briefing.rendered_markdown`.
- Existing section fields are copied into the final compatibility briefing;
  the finalizer changes only the rendered public artifact unless an existing
  bounded helper already owns a section-derived summary field.
- Writer APIs reject E2 drafts.

## R3. Phase order is fixed and monotonic

The top-level order is:

1. assemble every text-producing block;
2. project typed internal states to public language;
3. repair/fallback bounded presentation defects;
4. validate read-only;
5. seal.

An implementation may keep the current necessary compliance scan both before
and after watchpoint rendering inside the assembly phase. It may not move the
terminal public projection ahead of a text producer.

## R4. All current late mutations move before projection and validation

The finalizer must own, directly or through a declared collaborator:

- visual-link, chart, and carryover supplement placement;
- anchor-table replacement and numeric-anchor repair/gate preparation;
- reader-format structural passes;
- shared macro, crypto indicator, channel anchor, cause-map, and daily-thesis
  injection;
- watchpoint normalization/rendering;
- segment navigation;
- canonical and first-viewport disclaimers;
- first-viewport reflow and summary repair;
- rendered-body evidence counting and body-used counter rendering.

The corresponding mutations are removed from `_stage_publish_segments()`.

On every survivor pass, the active segment tuple is sent through the single
pure `_internal.daily_thesis_decision.redecide_daily_thesis_for_active_segments`
owner. Cross-segment validation and injection use that active decision, never
the original three-segment decision after a block.

## R5. Public projection runs after every producer

The u108 public-language projection is the last semantic text transformation.

- `normalize_data_limited_reader_copy` must not run inside an earlier generic
  reader-format chain and then assume later producers are safe.
- Every replacement/fallback block is projected before full-document repair.
- `public_quality_language.py` remains the only public wording map.
- Adding a new public producer requires placing it in the documented assembly
  call graph before projection. The bounded architecture test guards direct
  production mutation/construction sites; code review remains responsible for
  semantic transforms hidden inside helpers.

The canonical production API is
`publisher.reader_format.public_projection.project_public_markdown(layout, *, limitation_reasons) -> PublicDocumentLayout`.
It is newline-preserving and byte-idempotent, projects reader-visible table
rows, and protects only fenced code, collapsed `수집/품질 진단`, structured
metadata, and the exact canonical disclaimer. The one-argument
`_internal.project_public_quality_language()` remains a fragment wording
helper; it is never called on the entire Markdown document.

## R6. Prompts and renderers must not deliberately emit forbidden public labels

The Stage-2 data-limited prompt must request reader-safe limitation prose, not
the raw label `데이터 부족`.

Watchpoint/card defaults must represent absence as `None`/typed reason until
projection. The following are forbidden as public producer defaults:

- `[데이터부족]`
- `데이터부족`
- `데이터 부족`
- `상방 데이터 부족`
- `하방 데이터 부족`
- `관심 영향 데이터 부족`
- `확인 소스 미상`

Raw operator labels remain permitted in collapsed diagnostics and structured
metadata according to u108 protected-region rules.

The production renderer is
`render_watchpoint_matrix_result(...) -> WatchpointRenderResult`. A limited
result contributes typed `watchpoint_unavailable` to E2; no downstream code
infers it from rendered Korean strings. The legacy string-returning API has no
default segmented call site.

## R7. Existing truth and policy owners remain authoritative

u144 does not loosen or clone:

- numeric anchor assertions;
- entity fact claims;
- compliance/advice language;
- summary rejection;
- disclaimer verification;
- surface issue detection;
- evidence accounting.

Each existing owner is invoked through its typed API in the phase that matches
its behavior. A gate that rewrites is a repair-phase collaborator; a terminal
validator is read-only.

## R8. Presentation defects degrade at the smallest safe boundary

Use this exhaustive current surface policy table. `required` means header,
navigation, first viewport, section body (including the required watchpoint
section), or disclaimer; `optional` means the E3
visual/chart/carryover/cause-map/indicator augmentation regions.

| Current issue code | Owned region | Disposition |
|---|---|---|
| `bad_token.bulganghanseong` | any reader-visible | `repair` with existing token replacement |
| `korean.bad_particle.mingamdo_eul` | any reader-visible | `repair` with existing particle replacement |
| `ellipsis.dangling_line` | first viewport | `repair`; drop the dangling suffix/empty line |
| `ellipsis.dangling_line` | optional | exact `optional_block_disposition(block)` below |
| `ellipsis.dangling_line` | required body | `record_warning` after existing repair; it cannot silently delete required prose |
| `trace.fragment` | first viewport | `repair` with existing trace-fragment removal |
| `trace.fragment` | optional | exact `optional_block_disposition(block)` below |
| `trace.fragment` | required body | `block_segment` if residual after repair |
| `watermark.window_bracket` | first viewport/header | `replace_block` from the existing typed watermark owner |
| `markdown.broken_numeric_bold` | any reader-visible | `repair` with existing numeric emphasis repair |
| `markdown.href_ellipsis` | first viewport | `repair` by preserving visible label and removing the incomplete target |
| `markdown.href_ellipsis` | optional | exact `optional_block_disposition(block)` below |
| `markdown.href_ellipsis` | required body | `block_segment` if residual |
| `summary.truncated_mid_token` | first viewport | `replace_block` with the existing canonical safe summary fallback |
| `watchlist.matcher_reason.public` | watchpoints | `replace_block` with the shared public-safe watchpoint note |
| `watchlist.matcher_reason.public` | any other region | `block_segment` |
| `markdown.unmatched_link` | first viewport | `repair` with the existing visible-text unwrap |
| `markdown.unmatched_link` | optional | exact `optional_block_disposition(block)` below |
| `markdown.unmatched_link` | required body | `block_segment` if residual |
| `glossary.collision.forbidden_pair` | any reader-visible | `repair` through the existing glossary collision owner; residual => `block_segment` |
| `public_diagnostic.raw_label` | watchpoints | phase-2 projection; residual => `replace_block` with shared watchpoint limitation copy |
| `public_diagnostic.raw_label` | another optional region | phase-2 projection; residual => exact `optional_block_disposition(block)` below |
| `public_diagnostic.raw_label` | required reader-visible region | phase-2 projection; residual => `block_segment` |
| `template.repeated_phrase` | first viewport | `record_warning`; u144 does not invent a rewrite |
| unknown issue code or blocking finding without one owned region | any | `block_segment` and fail the exhaustiveness/ownership test |

Every degradation records E3 outcome data. The original invalid text is not
logged or retained in the public artifact.

The referenced optional/conditional block policy is a closed lookup, not an
implementation choice:

| Block | One disposition | Body/fallback owner |
|---|---|---|
| `visual` | `omit_optional_block` | preserve empty supplement marker shell; promote no asset |
| `chart` | `omit_optional_block` | preserve empty supplement marker shell; promote no asset |
| `carryover` | `omit_optional_block` | preserve empty supplement marker shell; promote no asset |
| `cause_map` | `omit_optional_block` | remove the optional single line |
| `shared_macro` | `replace_block` | `_internal.public_quality_language.PUBLIC_SHARED_MACRO_LIMITED_TEXT` |
| `crypto_indicators` | `replace_block` | `_internal.public_quality_language.PUBLIC_INDICATOR_LIMITED_TEXT` |
| `channel_anchors` | `replace_block` | `_internal.public_quality_language.PUBLIC_CHANNEL_ANCHOR_LIMITED_TEXT` |
| `daily_thesis` | `replace_block` | `_internal.public_quality_language.PUBLIC_DAILY_THESIS_LIMITED_TEXT` |
| `watchpoints` | `replace_block` | `_internal.public_quality_language.PUBLIC_WATCHPOINT_LIMITED_TEXT`; preserve `## ⑥` |

No reachable `(issue_code, block)` pair maps to both replace and omit. The
exhaustiveness test expands the issue table through this lookup and asserts one
E7 disposition per pair.

## R9. Truth, safety, and required structure fail closed

The following cannot be repaired by deletion or vague wording:

- unsupported precise numeric claim;
- verified entity-role/fact contradiction;
- residual P0 compliance or investment-advice language;
- missing canonical or short disclaimer after deterministic insertion;
- missing, duplicate, or unparseable required segment sections;
- an issue code without an explicit E7 policy;
- digest/date/segment mismatch at writer boundary.

Any such finding produces a typed E6 `trust_blocked` outcome for the affected
segment. It raises E8 only when no segment survives or the invariant is
bundle-wide/programmer-level.

## R10. Fallback is bounded and deterministic

- Findings are grouped by `region_id` before action. Issue codes are unique and
  sorted, dispositions are resolved once, and precedence is exactly
  `block_segment > omit_optional_block > replace_block > repair > record_warning`.
- At most one repair/replacement/omission is attempted per affected region,
  even when it contains multiple findings. Repair receives the entire grouped
  finding tuple. A residual after that one attempt fails the segment with
  `document.fallback_exhausted`; it does not trigger a second cosmetic pass.
- The same input and context produce byte-equal output, outcome order, issue
  code order, and digest.
- No LLM call, retry loop, random choice, locale lookup, or wall-clock value is
  used.
- If the replacement itself fails a terminal gate, the affected segment fails
  closed.

## R11. Segmented public content preserves u63/u94 partial publication

Production segmented mode expects all values in `SEGMENT_ORDER`.

- A known missing generated input is an E1 `generation_failed` absence.
- A non-degradable finding is an E6 `trust_blocked` outcome.
- Presentation defects covered by R8 may not create either absence state.
- The finalizer restarts from original generated drafts after a newly discovered
  trust block so u63 navigation is rendered from the final survivor/absence
  set. The fixed point is bounded to `len(SEGMENT_ORDER)` passes.
- A non-empty finalized subset is published in one transaction. Zero survivors
  raises E8 before public writes.
- This preserves the later u63/u94 contract and supersedes only the unsafe
  surface-error catch/drop mechanism in the orchestrator.

## R12. Pipeline status distinguishes content failure from delivery failure

- Successful E6 + successful write/commit + successful notification →
  `SUCCESS`.
- Complete E6/write/commit + notification failure → delivery-only `PARTIAL`,
  `content_completeness=complete`, exit 0.
- One/two-document E6/write/commit → content `PARTIAL`,
  `content_completeness=partial`, exit 2, operator alert, explicit u63 absence
  navigation; content-partial severity wins if notification also fails.
- Zero survivors or E8 bundle/programmer failure → `FAILED`, exit 1, operator
  alert, no public commit.
- Optional visual failure may produce text-only documents and a stage note; it
  does not authorize missing segment content.

GitHub step summary includes expected/finalized/published counts and content
completeness. `daily-briefing.yml` captures the process rc, dispatches Pages
when a public commit exists, and then re-emits rc 1/2; content-partial is never
green.

## R13. Final validators are read-only

Once E2 enters `validated`:

- no repair helper is called;
- no `Briefing.model_copy(update={"rendered_markdown": ...})` is called;
- no navigation, disclaimer, summary, evidence, visual, index, or notifier code
  modifies the sealed Markdown;
- a validator that needs mutation is reclassified into the repair phase.

## R14. Writer verifies the seal before I/O

`write_finalized_document()` verifies E5 digest, date, segment, and disclaimer
before path creation or atomic write.

- On mismatch, destination bytes are untouched.
- The existing `write_atomic` and rollback behavior remain in force after the
  seal passes.
- The legacy `write_briefing()` path may remain for unsegmented compatibility,
  but default segmented production cannot call it.

## R14a. Pre-finalization assets are staged, not public

Current visual/chart file producers and any future file-backed carryover write
only beneath a run-owned temporary root and return E1 `StagedArtifact` values
plus supplement Markdown that references artifact IDs. Current text-only
carryover performs no file I/O. They do not touch archive/site public
destinations before E6.

E5 freezes each survivor's non-omitted artifact IDs, and E6 contains the exact
typed promotion manifest equal to their ordered union. After E6 construction, the
existing publish transaction verifies root ownership/digests, promotes only the
manifest, writes sealed documents and derived pages, then invokes the existing
git commit/push boundary. Promotion/write/quality failure before git restores
the destination snapshot; every exit removes the staging root. The current
`PublisherGitError` behavior after commit/push begins is preserved: no Pages
dispatch, bounded operator failure, and no claim that a possibly created local
commit is byte-rolled-back. Git history compensation is outside u144.

## R15. Public consumers are read-only

Site index, OG cards, quality/evidence consumers, replay, and notifier summary
may consume E5 or its final `Briefing` view. They may derive other artifacts but
cannot return a modified segment document.

Quality consistency remains a defensive cross-artifact gate after side-surface
generation; it does not rewrite E5.

Default segmented notification consumes only E5 `PublicNotificationSummary`
plus orchestrator-provided URLs and existing typed lookahead/price inputs. Its
conclusion and optional watchlist are extracted from validated layout bytes;
coverage status/label come from E1 typed coverage. Missing/unsafe conclusion
hard-blocks the segment. The notifier validates DTO key/segment/date identity,
may format or UTF-16-bound those values, but cannot select replacement prose.
The default segmented path accepts no `Briefing` and cannot fall back to
generated `Briefing.market_summary`; legacy unsegmented behavior is explicitly
outside this contract.

## R16. Diagnostics are bounded and redacted

Degradation logs contain only target date, segment, block, disposition, sorted
issue codes, and bounded counts. Failure logs may add phase, exception type,
and redacted/bounded preview length.

Do not log:

- full generated/final Markdown;
- full raw source payloads;
- secret-bearing URLs;
- environment values;
- Telegram/OpenAI/Claude credentials;
- original text of an omitted block.

## R17. Existing and planned issue units retain narrow ownership

- u130 numeric-level quarantine remains in the numeric gate.
- u131 sentence bounding remains the shared producer algorithm.
- u133 registry-source routing remains upstream.
- u134 callout/counter composition remains producer behavior.
- u135 signal-value resolution/card synthesis remains watchpoint content logic.

If any lands after u144, it must use the assembly/finalization boundary and
cannot add a post-seal mutation. u135 and u144 must not be implemented in
parallel without explicit file/contract coordination.

## R18. No long-lived dual finalization path

Characterization may compare old/new paths in tests, but production switches
once. No environment flag keeps both paths active after closeout; two live paths
would recreate the ordering drift u144 is intended to remove.
