# Step 3.3 Typed Watchpoint Result

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The default segmented reader chain now calls
`render_watchpoint_matrix_result()` directly. The legacy string-returning
renderer delegates to the typed API for compatibility tests and has zero
production call sites.

The phase-1 reader collaborator reports each immutable
`WatchpointRenderResult` between the existing raw-prose compliance scan and the
rendered-card compliance scan. The concrete E2 reader assembly handler requires
exactly one matching result, accumulates its ordered unique limitation reasons,
reindexes the resulting Markdown, and only then advances
`generated -> assembled`. A limited watchpoint therefore carries
`watchpoint_unavailable` through the subsequent projection without parsing its
Korean public copy.

## Fresh-eyes correction

The first implementation exposed an optional observer and added an E2
accumulator, but no production-source assembly owner connected the two. Review
correctly rejected that version. The corrected
`_assemble_phase_one_reader_draft()` makes the observer mandatory on the E2
path and fails closed on a missing, duplicate, wrong-segment, or rewritten-key
result. The generated-to-assembled-to-projected integration regression pins the
connection. The old orchestrator dict path remains only until the Step 5
sealed-finalizer switch.

## Architecture and validation

The AST production scanner recognizes direct imports, renamed imports, module
aliases, and the local compatibility facade. It requires zero legacy renderer
calls and exactly the typed segmented call plus the facade delegation.

- focused watchpoint/lifecycle/assembly/projection/architecture set: 115 passed;
- publisher plus reader integration suite: 629 passed;
- orchestrator suite: 378 passed;
- pipeline integration: 9 passed;
- Ruff check and format check: passed;
- strict mypy for changed source modules: passed;
- scoped diff check: passed;
- fresh-eyes re-review: 104 focused tests passed, approved.
