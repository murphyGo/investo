# Step 2.6 Rendered-Markdown Architecture Guard

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The existing production AST scanner now records every direct canonical
`Briefing(rendered_markdown=...)` construction and every direct
`model_copy(update=...)` replacement whose literal dictionary or `dict(...)`
call contains `rendered_markdown`.

The exact ordered compatibility allowlist contains seven executable sites:

1. the generated `Briefing` construction in `briefing.pipeline._finalize_briefing`;
2. the phase-one presentation and body-evidence owners in
   `publisher.public_document`;
3. the typed supplement adapter in `publisher.public_document`;
4. the legacy internal reader collaborator in `publisher.segment_reader_format`;
5. the visual preparation producer in `visuals.assets`; and
6. the single final compatibility copy in
   `publisher.public_document._seal_document`.

The list is exact, so a new direct production site, a removed migration site,
or a second seal copy fails the architecture test. AST traversal covers only
executable syntax, which excludes the legacy chart usage example stored in a
module docstring. Synthetic regressions pin literal-dict and `dict(...)`
updates while proving unrelated `model_copy` fields are ignored.

This guard is deliberately bounded as Contract 8 requires. It does not claim
to recover arbitrary semantic string transforms or update dictionaries passed
through variables. The adjacent Step 1 guard still expects zero production
sealed-writer calls before the Step 5 switch; production is not yet connected
to the finalizer or sealed writer.

## Validation

- architecture suite: 10 passed;
- architecture + assembly + incident + writer regression set: 40 passed;
- Ruff check and Ruff format check: passed;
- strict mypy for the changed test module: passed;
- fresh-eyes review: approved after one format-only correction.
