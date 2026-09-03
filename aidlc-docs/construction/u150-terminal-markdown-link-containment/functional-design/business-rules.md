# Business Rules - `u150 terminal-markdown-link-containment`

**Date**: 2026-09-03
**Status**: Approved for Code Generation on 2026-09-03
**Source**: approved answers `A / B / A / A / A`; u150 business logic model; u112 surface-quality contract; u144 R8-R13; u149 numeric-only containment contract

These rules are binding and listed in decision order. They supersede only u144's behavior for `markdown.href_ellipsis` and `markdown.unmatched_link`. All other u144/u149 rules remain authoritative.

## R1. One canonical owner detects and transforms link defects

`investo._internal.surface_quality` remains the sole owner of both link issue codes, the existing link-shape matchers, and target-specific transformation.

- No second regex family, Markdown parser, AST, URL resolver, reference graph, or finalizer-local target matcher is allowed.
- Policy receives only a closed shape class from the canonical owner; policy does not inspect link syntax or target text.
- The scanner may hold matched evidence transiently in memory, but a shape signal, finalization outcome, log, workflow summary, fixture derived from production, or public artifact may not retain that evidence.
- Synthetic tests use reserved fictional values such as `example.invalid`; production link targets or blocked Markdown are never reconstructed into fixtures.

## R2. Link classification precedes every link-target mutation

The exact projected region body is scanned and classified before any helper changes either link code.

- The pre-mutation snapshot is the sole input to grouping and disposition selection.
- A whole-document call may retain legacy non-link cosmetic repairs, but it may not transform `markdown.href_ellipsis` or `markdown.unmatched_link` before the owned-region decision.
- After the selected region action, link residue is scanned read-only. No whole-document link repair runs as a second cosmetic pass.
- A stale, missing, overlapping, or multiply owned region mapping fails closed; no text search is used to reacquire a finding.

## R3. The link-shape set is closed

The only u150 shape classes are:

1. `inline_link` — closed `[label](target)` syntax;
2. `image` — closed `![alt](target)` syntax;
3. `autolink` — closed `<target>` syntax;
4. `reference_definition` — line-level `[reference-id]: target` syntax;
5. `incomplete_inline` — every unmatched construct on the line is accepted by the existing recoverable-fragment owner and a read-only trial of the pure transform closes the unmatched-link predicate without changing unrelated bytes;
6. `unmatched_residual` — the line is mixed, overlapping, only partially covered, or otherwise remains structurally unsafe after classification.

Each non-overlapping closed invalid-target occurrence produces one shaped `markdown.href_ellipsis` finding in stable line and span order. `markdown.unmatched_link` remains one whole-line structural finding. Repeated issue codes are deduplicated only after every shape contributes to region policy. Any registered link code that cannot be assigned one of the six known classes fails closed; it is never guessed into a recoverable class.

## R4. Recoverable transformations have exact outputs

When a region's selected action is `repair`, transformations are composed from its original body and preserve all bytes outside the exact matched span.

| Shape | Eligibility | Exact output |
| --- | --- | --- |
| `inline_link` | Target contains `...` or `…` | Captured label bytes only; remove opening/closing link syntax and the complete target. |
| `image` | Target contains `...` or `…` | Escaped plain alt text only; remove image/link syntax and the complete target. |
| `autolink` | Target contains `...` or `…` | Empty string; surrounding bytes remain unchanged. |
| `incomplete_inline` | Every unmatched construct is canonically covered and a read-only trial closes the line predicate | Captured label bytes only; remove each accepted incomplete opener and target suffix. |
| `reference_definition` | Never repairable | No line-level output; use R6/R7 disposition. |
| `unmatched_residual` | Never repairable | No delimiter stripping; use R6 disposition. |

Image alt escaping is deterministic: first encode `&`, `<`, and `>` as HTML entities, then prefix a backslash before each literal backslash, backtick, `*`, `_`, `[`, `]`, `(`, `)`, or `!`. Escaping performs no whitespace normalization, translation, truncation, or target recovery.

Every occurrence selected for one `repair` action is transformed left to right from the same original region body. The operation preserves the original newline sequence and is byte-idempotent. An empty label/alt produces an empty span, not invented reader text.

## R5. Protected and unchanged content is explicit

The link transform does not alter:

- valid link targets;
- inline code or fenced code;
- collapsed diagnostics;
- canonical or short disclaimer text;
- Markdown tables, including the anchor table;
- a region whose projection policy is not reader-visible;
- any clean sibling region.

A link finding assigned to header, navigation, anchor table, diagnostics, disclaimer, an unowned span, or an invalid layout is a trust/invariant failure and maps to `block_segment`. “Protected” means “not a repair target,” not “safe to bypass terminal validation.”

## R6. The link shape and region matrix is exhaustive

This table covers every u144 `PublicBlockKind`. `Recoverable closed` means `inline_link`, `image`, or `autolink`; `recoverable incomplete` means `incomplete_inline`; `reference definition` and `unmatched residual` are the two unrecoverable classes. The lookup is shape-aware by construction rather than a coarse code policy followed by a special-case override.

| Public block kind | Recoverable closed | Recoverable incomplete | Reference definition | Unmatched residual |
| --- | --- | --- | --- | --- |
| `header` | `block_segment` | `block_segment` | `block_segment` | `block_segment` |
| `navigation` | `block_segment` | `block_segment` | `block_segment` | `block_segment` |
| `first_viewport` | `repair` | `repair` | `replace_block` | `replace_block` |
| `visual` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` |
| `anchor_table` | `block_segment` | `block_segment` | `block_segment` | `block_segment` |
| `shared_macro` | `replace_block` | `replace_block` | `replace_block` | `replace_block` |
| `crypto_indicators` | `replace_block` | `replace_block` | `replace_block` | `replace_block` |
| `channel_anchors` | `replace_block` | `replace_block` | `replace_block` | `replace_block` |
| `cause_map` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` |
| `daily_thesis` | `replace_block` | `replace_block` | `replace_block` | `replace_block` |
| `carryover` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` |
| `chart` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` | `omit_optional_block` |
| `section_body` | `repair` | `repair` | `replace_block` | `replace_block` |
| `watchpoints` | `replace_block` | `replace_block` | `replace_block` | `replace_block` |
| `diagnostics` | `block_segment` | `block_segment` | `block_segment` | `block_segment` |
| `disclaimer` | `block_segment` | `block_segment` | `block_segment` | `block_segment` |

The matrix is a total lookup. An unregistered issue, block kind, or shape combination defaults to `block_segment` and must fail the policy exhaustiveness test.

## R7. Reference definitions are unrecoverable region signals

`reference_definition` supersedes the earlier draft rule that deleted only the definition line.

- The target and definition line are never emitted through a line-level repair result.
- First-viewport and section-body owners select `replace_block` directly.
- Watchpoints and optional augmentations use the exact R6 closed lookup.
- Header, navigation, anchor-table, diagnostics, disclaimer, and unowned occurrences fail closed.
- No same-region or cross-region definition/use resolution is performed.
- Reference uses elsewhere are not changed merely because their definition was rejected; each region is evaluated only from its own canonical findings.

## R8. Replacement and omission reuse existing owners only

u150 adds no reader-facing fallback sentence.

| Block | Action | Existing owner or preservation rule |
| --- | --- | --- |
| `first_viewport` | Replace body | Existing registered first-viewport safe body. |
| `section_body` | Replace body | Existing registered section-body safe body; preserve the required H2. |
| `watchpoints` | Replace body | `PUBLIC_WATCHPOINT_LIMITED_TEXT`; preserve `## ⑥`. |
| `shared_macro` | Replace body | `PUBLIC_SHARED_MACRO_LIMITED_TEXT`. |
| `crypto_indicators` | Replace body | `PUBLIC_INDICATOR_LIMITED_TEXT`. |
| `channel_anchors` | Replace body | `PUBLIC_CHANNEL_ANCHOR_LIMITED_TEXT`. |
| `daily_thesis` | Replace body | `PUBLIC_DAILY_THESIS_LIMITED_TEXT`. |
| `visual`, `chart`, `carryover` | Omit body/artifact | Preserve the empty supplement marker shell and promote no asset. |
| `cause_map` | Omit | Remove only the optional owned line. |

Required regions are never omitted. A requested replacement without a registered existing safe body is an unreachable policy error and fails closed with `document.fallback_unavailable`; it does not synthesize copy.

## R9. One region receives one strongest action

Findings are grouped by canonical `region_id` before mutation. Within a group:

- issue codes are sorted and unique;
- shape classes are evaluated without target/evidence data;
- every finding contributes exactly one R6 disposition;
- one strongest disposition is selected with exact precedence:

`block_segment > omit_optional_block > replace_block > repair > record_warning`

The selected action consumes the region's original body. A `replace_block` caused by one finding prevents all repairable findings in that region from running first. Duplicate attempts for one region fail as `document.fallback_repeat`. Successful mutation records exactly one redacted `PublicBlockOutcome`; replacement records `replaced`, omission records `omitted`, repair records `repaired`, and warning-only records `kept`.

## R10. A failed action never receives a second presentation attempt

After all selected actions are applied in canonical region order:

1. existing public projection runs over the candidate;
2. the layout is re-indexed;
3. the canonical scanner runs read-only;
4. every terminal hard gate runs read-only.

An actionable residual link code does not trigger delimiter stripping, another target transform, a broader region replacement, a survivor-loop repair, or post-seal editing. A canonical replacement that itself creates a link defect fails closed under the same rule.

## R11. Simultaneous hard defects retain full authority

For an indexable layout, the bounded presentation action occurs before the unchanged exhaustive terminal snapshot. The snapshot includes required structure, numeric anchors, entity facts, compliance, public language, first-viewport summary, canonical and short disclaimers, surface quality, and notification-summary derivation.

- A link action cannot remove, downgrade, or rename a non-presentation code.
- Domestic numeric-only handling remains exclusively u149 and is eligible only under its complete-code-set contract.
- US/crypto numeric findings remain fail-closed.
- A pre-index structure failure blocks immediately; link or numeric co-codes are not fabricated without safe ownership.
- No terminal validator mutates Markdown.

## R12. Residual diagnostic codes are bounded and complete

If an actionable link finding remains after the one allowed action, the final failure tuple is the sorted unique union of:

1. `document.fallback_exhausted`;
2. the exact residual canonical scanner codes;
3. any simultaneous non-presentation terminal hard codes.

If link residue is absent, `document.fallback_exhausted` is absent. A warning-only code does not cause fallback exhaustion.

Residual failure surfaces may contain only target date, segment, phase, and issue codes. They may not contain evidence text, evidence length derived from the target, line numbers tied to blocked Markdown, line contents, URLs, target hashes, Markdown, source payloads, prompt content, exception text, or secrets. Existing successful `PublicBlockOutcome.region_id` is not added to residual failure output.

## R13. Determinism and idempotence are mandatory

For equal projected bytes, layout expectation, and finalizer context:

- shape classes, group order, dispositions, outcome order, issue codes, candidate bytes, and seal digest are equal;
- input mapping order and finding order do not change the result;
- every transform is independent of wall clock, locale, environment, network, randomness, and LLM output beyond the supplied Markdown;
- applying the pure recoverable transform twice produces the same bytes as once;
- a successfully contained candidate contains no scanner-owned invalid target;
- valid link lines and unrelated/protected bytes remain byte-identical.

## R14. Segment, bundle, and delivery semantics remain unchanged

- An eligible link-only defect that clears through R6 cannot by itself produce `generation_absent` or `trust_blocked`.
- Protected, unowned, non-replaceable, policy-unavailable, or residual link defects remain legitimate `trust_blocked` outcomes.
- A new block restarts the u144 survivor loop from original generated drafts; transformed bytes are never re-input.
- Three sealed documents keep complete content, Telegram, Pages, and exit 0.
- One or two survivors keep valid-subset publication, explicit absence navigation, Pages dispatch, operator alert, and exit 2.
- Zero survivors keep no-public-write failure and exit 1.
- Notification-only failure with complete content remains delivery-only partial and exit 0.

## R15. Example and partial-PBT coverage is required

Example tests must cover:

- every R3 shape with ASCII and Unicode labels/alt text and both `...` and `…` targets;
- multiple invalid links on one line and multiple findings in one region;
- all 16 R6 block kinds and total-policy fallback;
- reference-definition no-repair/no-cross-region behavior;
- required H2, `## ⑥`, sibling-region, optional marker, staged-artifact, and seal preservation;
- a recoverable action that clears and an injected residual that yields R12 codes;
- link plus numeric/entity/compliance/disclaimer/structure/notification-summary failures;
- log, outcome, workflow-summary, exception, and representation negative checks for R12-forbidden fields.

Under the project's partial Property-Based Testing opt-in, domain-valid strategies cover recoverable inline/image/autolink/incomplete shapes, valid links, Unicode reader text, and region-safe surrounding bytes. Properties are valid-link byte stability, invalid-target absence, byte idempotence, deterministic ordering, and scanner/repair closure. Shrinking and reproducible examples remain enabled. Lossy invalid-target removal is not a round-trip property, and stateful PBT is not added.

## R16. Production qualification is exact and evidence-bounded

Before production replay:

- characterize run metadata for `32784998097`, `33035060796`, `33146560495`, `33238048642`, `33344214754`, and clean comparison `33457514796` without reconstructing blocked prose;
- pass focused scanner/policy/finalizer/orchestrator tests, full pytest, Ruff, format, strict mypy, policy guards, lock validation, strict MkDocs, and diff/whitespace checks;
- retain the completed u149 production evidence as the numeric non-regression prerequisite.

After explicit production approval, replay target dates 2026-08-27 and 2026-08-28 through the existing workflow. Each replay must prove:

- all three segment outcomes are document-bearing and pipeline exit is 0;
- archive commit/push succeeds and the chained Pages run succeeds for the exact publish SHA;
- Telegram returns its successful delivery result;
- all three live segment archive URLs return HTTP 200;
- committed Markdown and live HTML contain no canonical-scanner invalid link target;
- logs, summaries, outcomes, and artifacts contain no blocked target/evidence leakage.

Generation variability does not replace fixture coverage: if a replay does not naturally reproduce a historical link defect, R15 synthetic fixtures remain the proof of the containment branch. A genuine unrelated hard gate still fails closed and must be reported separately rather than weakening R11.

## R17. Explicit non-goals

u150 does not change valid-link rendering, citation count, source attribution, visual supplement URLs, Telegram URL construction, Pages routing, prompt templates, LLM retries, source collection, numeric thresholds, entity/compliance/disclaimer/summary rules, historical archive files, dependencies, secrets, environment flags, or infrastructure.
