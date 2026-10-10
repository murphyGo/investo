# UI deployment checkpoint — 2026-10-10

User instruction: push and deploy the completed u174–u179 units. Original dirty root and documentation worktrees are preserved. Unit commits are merged with current public main `bb5711f9`, retaining the concurrent sector and source-bound v3 foundations. Independent integration review: APPROVE, no P1/P2. CSS loads u29, shared UI, then scoped sector styles.

Validation on this final integration tree: 257 UI/v3/publication/pipeline tests passed in 250.51 seconds; Ruff/format 735 files, strict mypy 308 source files, four policy guards, strict MkDocs, Material/calendar contracts, and Node 22 client checks (29) passed. Actual headless browser acceptance: 30 cases across six surfaces, 390/1440 widths, both themes, and six no-JavaScript 200% checks, all passed. Evidence is in `deployment-evidence/final-integration/`. The source hash manifest freezes application, tests, workflow, build config, and generated index inputs for later documentation-only closeout.

The earlier `ea402465` integration became stale when main advanced. Its 5,219 passing tests before interrupt and earlier browser metrics are excluded from this final integration gate. The original unit-development full 6,774 result remains unit construction evidence, not a substitute for the exact integration SHA's remote Quality.

Remote Quality must succeed on the exact merge candidate before main delivery. Pages success and actual HTTPS browser acceptance will then be recorded separately. UI deployment does not complete native v3 typed readers or event semantic/operational acceptance.

Future automatic publication uses the bounded runtime UI backport on `4e0dc424`, independently reviewed and validated. Runtime source/provider/model/dependency and daily workflow policies remain unchanged. Promotion changes only REVIEWED_CODE_SHA after its exact remote Quality succeeds and no private job is queued/running. Runtime rollback is `4e0dc424a65d075a4437e08d849e7b667f2764c2`. No manual briefing or notification is dispatched.
