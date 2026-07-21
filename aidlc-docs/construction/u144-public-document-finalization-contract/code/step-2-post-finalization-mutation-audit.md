# Step 2.5 Post-finalization Mutation Audit

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The production tree contains no `Briefing.model_copy(update={"rendered_markdown": ...})`
call after E5 finalization. The remaining
executable sites are all before the terminal boundary:

1. visual preparation builds pre-finalization supplement Markdown;
2. `segment_reader_format` is an assembly collaborator;
3. publisher phase-one presentation and body-evidence helpers run before
   terminal validation;
4. the typed supplement adapter runs before finalization;
5. `_seal_document` performs the one design-required compatibility-briefing
   copy while constructing E5 from the validated layout.

The apparent hit in `publisher/charts.py` is a module-docstring example, not
an executable call. No other production `model_copy` call updates
`rendered_markdown`. `FinalizedPublicDocument` is otherwise only read by the
digest-verifying sealed writer, and the default production call count for
`write_finalized_document()` remains zero until the planned Step 5 switch.
This is a pre-switch call-graph verification; it does not claim that the
production finalizer or sealed writer is connected. Step 5 must connect the
phase-one helpers before or inside finalization and repeat this verification.

This checklist item required no additional runtime edit: Step 2.1 had already
removed the direct publish-stage copies and moved their algorithms behind
publisher-owned phase-one helpers; Steps 2.2 and 2.3 placed reader and
supplement mutations on the same pre-finalization side. Adding another
compatibility rewrite here would recreate the boundary the unit removes.
Step 2.6 separately freezes these exact sites with the planned AST allowlist.

Validation: the production call graph was re-audited with both the exact
`rendered_markdown` pattern and all `.model_copy(` calls. The existing sealed
construction/writer/phase-one suite passed 33 tests, and strict mypy passed for
the five involved source files. Fresh-eyes review independently passed 69
focused architecture/assembly/type/writer tests and approved the no-code
closure as the honest bounded result of the already-landed mutation moves.
