# Business Logic Model - `u150 terminal-markdown-link-containment`

**Date**: 2026-09-03
**Status**: Approved for Code Generation on 2026-09-03
**Source**: approved answers `A / B / A / A / A`; u112 canonical surface scanner; u144 R8-R12 public-document finalization contract; u149 numeric-only containment boundary; u150 Code Generation fixed contracts

This model amends only u144's presentation-repair and terminal-diagnostic flow for `markdown.href_ellipsis` and `markdown.unmatched_link`. The canonical lifecycle remains:

`generated -> assembled -> projected -> repaired -> validated -> sealed`

No second finalizer, Markdown parser, URL resolver, network lookup, LLM retry, or post-seal mutation is introduced.

## 1. Business boundary

The business outcome is the smallest safe containment of a generated link-target defect:

- a recoverable visible label or image alt text survives without its target;
- a target-only autolink disappears;
- an invalid reference definition is never repaired line by line and instead selects one action for its owning region;
- a residual malformed fragment replaces only an eligible owned region body;
- a protected, unowned, structurally unsafe, or still-invalid result fails closed;
- every numeric, entity, compliance, summary, disclaimer, required-structure, notification-summary, seal, and security gate retains its existing authority.

Presentation containment changes bytes only before terminal validation. A successful link-only containment keeps the segment eligible to seal. A non-presentation hard defect cannot become degradable merely because a link action also occurred.

## 2. Inputs, outputs, and ownership

| Concept | Input or output | Contract |
| --- | --- | --- |
| Projected draft | Input | Exact pre-containment Markdown and u144 phase identity. |
| Public document layout | Input and output | Canonical, non-overlapping owned regions with stable block kinds and projection policies. |
| Canonical surface findings | Input to policy | Scanner-owned issue codes and transient evidence; u150 does not create a parallel detector. |
| Closed link-shape class | Input to policy | Shape name only; no target, line text, source payload, or secret crosses into an outcome. |
| Region disposition | Internal decision | Exactly one strongest action for one region, chosen before mutation. |
| Public block outcome | Output for a completed action | One redacted repaired/replaced/omitted/kept record per acted-on region. |
| Terminal issue codes | Failure output | Sorted unique bounded codes; residual link failures add `document.fallback_exhausted` and their exact scanner codes. |
| Validated draft | Success output | Re-indexed, read-only-terminal-validated Markdown ready for the existing seal. |

Only canonical u144 region ownership permits mutation. A finding that maps to zero regions, multiple regions, a stale span, or a protected exact region is never repaired through a document-wide text search.

## 3. Ordered containment call sequence

| Order | Business operation | Mutation allowed | Result |
| --- | --- | --- | --- |
| 1 | Receive the `projected` draft and validate date, segment, phase, and region expectation identity. | No | Eligible projected layout or invariant failure. |
| 2 | Index the exact projected bytes and scan each canonical owned surface with the existing scanner. | No | Pre-mutation owned finding snapshot. |
| 3 | Classify each scanner-owned link finding into the closed shape set. | No | Recoverable shape, unrecoverable reference definition, or residual unmatched shape. |
| 4 | Group findings by `region_id`, derive each requested disposition, and select the strongest once. | No | One immutable region decision in canonical region order. |
| 5 | Apply that decision to the region's original body and record at most one redacted outcome. | Yes, once per region | Repaired, replaced, omitted, warning-only, or block candidate. |
| 6 | Reapply the existing public projection boundary and re-index the changed layout. | Deterministic projection only | Candidate terminal layout. |
| 7 | Rescan the candidate read-only and collect every unchanged terminal hard gate. | No | Exhaustive terminal snapshot, including residual surface codes. |
| 8 | Add bounded fallback diagnostics when an actionable link code remains, then block or advance. | No | `trust_blocked` with bounded codes, or `validated`. |
| 9 | Use the unchanged u144/u149 seal, survivor fixed point, writer, Telegram, and Pages flow. | Seal only after validation | Final document bundle and existing delivery status. |

The pre-mutation snapshot is mandatory. A target transform may not run before the shape-aware region decision, because doing so would erase the information needed to recognize an invalid reference definition. Existing non-link cosmetic repair may share the region action, but it cannot mutate a link finding before Step 4 selects the region's sole disposition.

## 4. Closed link-shape action flow

The canonical scanner remains the only detector. Within its already-matched link family, it reports one bounded shape class used by the policy path.

| Detected shape | Recoverability | Region action contribution | Exact visible result when repair is selected |
| --- | --- | --- | --- |
| Inline link `[label](invalid-target)` | Recoverable | `repair` | Plain `label`; target absent. |
| Image `![alt](invalid-target)` | Recoverable | `repair` | Escaped plain alt text; image syntax and target absent. |
| Autolink `<invalid-target>` | Recoverable by safe removal | `repair` | Empty string. |
| Reference definition `[reference-id]: invalid-target` | Unrecoverable | Shape override from Section 5 | No line-level rewrite. |
| Incomplete inline fragment matched by the existing recoverable-fragment owner | Recoverable | `repair` | Plain visible label; incomplete target absent. |
| Other residual `markdown.unmatched_link` | Unrecoverable | Region replacement or fail-closed disposition from Section 5 | No delimiter-stripping retry. |

The transform neither guesses nor completes targets. It does not fetch a URL, follow a redirect, inspect another region, or retain a target substring in output or outcome data. Valid targets, inline code, fenced code, diagnostics, tables governed by a protected contract, and disclaimer text remain outside this transform.

Reference-style uses in other regions are not joined to the invalid definition. Each other region is evaluated only from its own canonical findings. This prevents an unbounded document graph and makes the result independent of definition/use order.

## 5. Shape-aware region disposition

Non-link findings retain the existing `(issue_code, block_kind)` disposition. Each u150 link finding instead receives one exhaustive `(issue_code, block_kind, link_shape)` disposition before mutation. This is necessary both for an unrecoverable `reference_definition` and for distinguishing a recoverable `incomplete_inline` line from `unmatched_residual`.

| Finding class | First viewport | Section body | Watchpoints | Optional augmentation | Header, navigation, anchor table, diagnostics, disclaimer, or unowned |
| --- | --- | --- | --- | --- | --- |
| Recoverable `markdown.href_ellipsis` | `repair` | `repair` | `replace_block` | Existing closed optional lookup | `block_segment` |
| Recoverable `markdown.unmatched_link` incomplete inline | `repair` | `repair` | `replace_block` | Existing closed optional lookup | `block_segment` |
| Reference definition override | `replace_block` | `replace_block` | `replace_block` | Existing closed optional lookup | `block_segment` |
| Residual `markdown.unmatched_link` | `replace_block` | `replace_block` | `replace_block` | Existing closed optional lookup | `block_segment` |

The optional lookup remains u144's exact block policy: visuals, charts, carryover, and cause-map regions are omitted; shared macro, crypto indicator, channel anchor, daily thesis, and watchpoint regions use their existing replacement owner. Required regions are never omitted. A replacement is allowed only when that block already has an approved canonical limitation body; an unavailable fallback produces `document.fallback_unavailable` and fails closed rather than inventing new text.

When one region contains multiple findings, the existing precedence remains:

`block_segment > omit_optional_block > replace_block > repair > record_warning`

Therefore a region containing both a recoverable inline link and an invalid reference definition is replaced once. The inline link is not repaired first.

## 6. One-action region lifecycle

For every grouped region decision:

1. Read the body from the pre-mutation owned-region snapshot.
2. Reject a duplicate `region_id` attempt as `document.fallback_repeat`.
3. Apply exactly one selected disposition:
   - `repair`: apply all eligible target-specific transforms to the original body in one deterministic composition;
   - `replace_block`: replace only `content_start:content_end` with the block's existing safe body;
   - `omit_optional_block`: use the existing marker-preserving optional omission;
   - `record_warning`: keep bytes and record only the bounded code;
   - `block_segment`: perform no mutation and carry the bounded codes to terminal failure routing.
4. Preserve the canonical heading or marker shell. Section replacement retains its H2; watchpoint replacement retains `## ⑥`; sibling regions remain byte-identical.
5. Record no more than one `PublicBlockOutcome` for a successfully acted-on region. Replacement is recorded as `replaced`, never as `repaired`.

There is no repair-then-replace sequence, second delimiter-stripping pass, fallback recursion, or search for the same text elsewhere. Repeated execution on already-contained bytes is byte-idempotent because invalid targets are absent and canonical replacement bodies do not create link findings.

## 7. Terminal closure and simultaneous hard defects

After the one region-action pass, the layout crosses public projection and re-indexing once more. Terminal evaluation is read-only and collects the unchanged hard-gate families over the resulting candidate:

1. required document structure;
2. numeric anchor assertions, including u149's exclusive domestic numeric path;
3. entity fact contradictions;
4. compliance language;
5. public-language leakage;
6. first-viewport summary quality;
7. canonical and short disclaimers;
8. canonical surface quality;
9. notification-summary derivation;
10. seal/date/segment invariants at the existing boundary.

If no hard code remains, the draft advances to `validated`. If an actionable link finding remains, the final code set is the sorted unique union of:

- `document.fallback_exhausted`;
- the exact residual canonical scanner codes;
- any simultaneous non-presentation hard codes collected by the same terminal snapshot.

When containment clears the link findings but another hard gate fails, only the unchanged hard-gate code set is returned; `document.fallback_exhausted` is not added. This makes the link action unable to mask a numeric, entity, compliance, disclaimer, structure, or notification-summary failure.

Residual failure surfaces are limited to target date, segment, phase, and bounded issue codes. A successfully recorded `PublicBlockOutcome` may retain its existing canonical `region_id`, but residual errors do not add one. Evidence strings, line contents, URLs, Markdown, source payloads, and secrets never leave the scanner/repair boundary.

## 8. Survivor and publication behavior

The existing u144 survivor fixed point remains the sole bundle coordinator:

- a successfully contained link-only presentation defect remains a surviving sealed segment;
- a protected/unowned link defect, unavailable safe fallback, residual link defect, or simultaneous hard defect yields the existing `trust_blocked` segment outcome;
- a new block restarts from original generated drafts so navigation and cross-segment context describe the actual survivor set;
- transformed Markdown is never fed into another survivor pass;
- one or two surviving documents retain content-partial publish, Telegram/operator, Pages, and exit-2 semantics;
- zero survivors still fail before public writes;
- three validated documents retain complete publication and exit 0.

The phrase “link-only presentation defects cannot produce `trust_blocked`” applies to the eligible owned-region shapes with an available approved action. Protected, unowned, structurally invalid, or action-exhausted cases are trust/invariant failures and remain fail-closed.

## 9. State transitions

| Pre-mutation condition | One action | Terminal result |
| --- | --- | --- |
| No actionable link finding | None | Existing validation result; clean bytes unchanged. |
| Recoverable link shape in an eligible region | `repair` | `validated` when all terminal gates pass. |
| Invalid reference definition in an eligible replaceable region | `replace_block` | `validated` when replacement and all terminal gates pass. |
| Residual unmatched fragment in an eligible replaceable region | `replace_block` | `validated` when replacement and all terminal gates pass. |
| Link finding in an optional augmentation | Existing omit/replace lookup | `validated` when the resulting layout and artifact selection pass. |
| Link finding in a protected, unowned, overlapping, or non-replaceable required region | No mutation | `trust_blocked` with exact bounded codes. |
| Action leaves an actionable link finding | No second action | `trust_blocked` with `document.fallback_exhausted` plus residual codes. |
| Link action plus non-presentation hard defect | Link action once | `trust_blocked` with the original hard code set; residual link codes are added only if still present. |

## 10. Determinism and composition properties

- P1. Equal projected Markdown, layout expectation, and context produce byte-equal candidate Markdown, region outcomes, issue-code order, and final digest.
- P2. Every action reads original region bytes and each region receives at most one mutation and one outcome.
- P3. A repair exposes no invalid target substring and is byte-idempotent.
- P4. A replacement or omission preserves required shells, sibling bytes, and u144 staged-artifact selection semantics.
- P5. Finding order within a region cannot change the selected action because every full finding resolves independently before the fixed strongest-disposition precedence is applied; only the final redacted code tuple is deduplicated and sorted.
- P6. Mapping input order cannot change canonical region iteration or terminal issue-code order.
- P7. No presentation mutation occurs after terminal validation starts.
- P8. No shape classification or diagnostic output contains raw target/evidence data.
- P9. Valid links and unrelated clean regions remain byte-identical.
- P10. Partial-mode property tests apply to the pure transform, invalid-target absence, idempotence, and valid-link stability; no stateful PBT is introduced.

## 11. Compatibility and non-goals

- u112 retains the two canonical issue codes and detector ownership.
- u144 retains region indexing, phase transitions, outcomes, sealing, active-survivor restart, artifact promotion, notification DTO, and publish status.
- u149 remains the only domestic numeric containment/minimal-fallback path; u150 never handles `numeric.anchor_assertion` as a link fallback.
- u98/u110 retain watchpoint rendering and `PUBLIC_WATCHPOINT_LIMITED_TEXT`.
- Existing valid-link rendering, citations, source attribution, Telegram URLs, Pages routing, and historical archives are unchanged.
- No new public fallback sentence, dependency, secret, environment flag, persistence family, source, external request, or infrastructure component is added.

The detailed closed rules and exact entity amendments are completed in Functional Design Steps 5 and 6. This model fixes their control-flow boundary: classify before mutation, choose one owned-region action, revalidate read-only, then seal or fail closed.
