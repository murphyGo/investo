# Surface Issue Disposition Baseline

**Unit**: u144 public-document-finalization-contract
**Frozen**: 2026-07-21
**Executable owner**: `src/investo/publisher/_public_document_policy.py`

## Current scanner inventory

The AST exhaustiveness test finds 13 static `SurfaceQualityIssue.code` values in
`investo._internal.surface_quality`. Scanner regexes remain with that existing
owner. The u144 policy table contains only owned-block disposition policy. A
new scanner code fails the AST equality; adding it only to the registry still
fails table construction until an explicit policy branch is authored.

| Issue code | Header | First viewport | Required reader-visible body | Watchpoints | Optional/conditional augmentation |
|---|---|---|---|---|---|
| `bad_token.bulganghanseong` | repair | repair | repair | repair | repair |
| `korean.bad_particle.mingamdo_eul` | repair | repair | repair | repair | repair |
| `ellipsis.dangling_line` | record warning | repair | record warning | record warning | closed optional-block lookup |
| `trace.fragment` | block segment | repair | block segment | block segment | closed optional-block lookup |
| `watermark.window_bracket` | replace header block | replace first-viewport block | block segment | block segment | block segment |
| `markdown.broken_numeric_bold` | repair | repair | repair | repair | repair |
| `markdown.href_ellipsis` | block segment | repair | block segment | block segment | closed optional-block lookup |
| `summary.truncated_mid_token` | block segment | replace first-viewport block | block segment | block segment | block segment |
| `watchlist.matcher_reason.public` | block segment | block segment | block segment | replace watchpoint body | block segment |
| `markdown.unmatched_link` | block segment | repair | block segment | block segment | closed optional-block lookup |
| `glossary.collision.forbidden_pair` | repair | repair | repair | repair | repair |
| `public_diagnostic.raw_label` | block if residual after projection | block if residual after projection | block if residual after projection | replace after projection | projection then closed optional-block lookup |
| `template.repeated_phrase` | block segment | record warning | block segment | block segment | block segment |

Every row is expanded across all 16 `PublicBlockKind` values in the executable
mapping. Protected `diagnostics`, unknown codes, and otherwise unreachable
code/block pairs fail closed with `block_segment`.

## Optional/conditional block lookup

| Block | Disposition |
|---|---|
| `visual` | `omit_optional_block` |
| `chart` | `omit_optional_block` |
| `carryover` | `omit_optional_block` |
| `cause_map` | `omit_optional_block` |
| `shared_macro` | `replace_block` |
| `crypto_indicators` | `replace_block` |
| `channel_anchors` | `replace_block` |
| `daily_thesis` | `replace_block` |
| `watchpoints` | `replace_block` |

The first eight entries are the optional/conditional augmentation lookup used
by generic optional-region rules. `watchpoints` is a required region and uses
its replacement only for the two dedicated watchpoint rules
(`watchlist.matcher_reason.public` and `public_diagnostic.raw_label`); generic
ellipsis/trace/link rules retain their required-body disposition there.

No code/block pair has more than one disposition. The later containment step
will group all findings by region and apply the strongest single disposition;
this baseline does not execute repair or replacement itself.
