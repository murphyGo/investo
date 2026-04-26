# Technical Debt Registry

## Summary

| Priority | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 2 | 2026-04-27 |
| Low | 0 | - |

---

## Active Items

### Critical Priority

_No critical items._

### High Priority

_No high priority items._

### Medium Priority

#### DEBT-001: `Briefing` model lacks `disclaimer ∈ rendered_markdown` invariant

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3)
- **Reference**: NFR-004 (compliance / disclaimer enforcement)
- **Description**: The `Briefing` pydantic model permits a state where `disclaimer` text is not actually present in `rendered_markdown`. Today the only enforcement is `publisher.verify_disclaimer` (called pre-publish). Defense-in-depth would shift the guarantee one layer earlier — into the data model — so the bug class becomes impossible by construction.
- **Suggested Fix**: Add a `model_validator(mode="after")` on `Briefing` that asserts `self.disclaimer.strip() in self.rendered_markdown`. Trade-off: rejects ambiguous test fixtures that pass section text without re-running the rendering pipeline. Either weaken the check (substring of the disclaimer's first line) or update fixtures to always pass full rendered markdown.
- **Effort**: ~30 min including fixing fixtures
- **Priority Reasoning**: Medium — not yet a real bug because the publisher guard exists, but if anyone ever bypasses the publisher path (e.g., direct unit-tests, future replays, ADR'd alternate flow), the guard disappears.

#### DEBT-002: No date sanity bounds on `target_date` / `published_at` (project-wide)

- **Created**: 2026-04-27
- **Source**: Code review of `src/investo/models/briefing.py` (Step 3); same pattern in `items.py`
- **Reference**: US-005 (scheduled execution), FR-006 (archival)
- **Description**: `Briefing.target_date`, `BriefingNotification.target_date`, and `NormalizedItem.published_at` accept any valid date — including far-future (`date(2206, 4, 27)`) or pre-epoch values. A typo upstream would commit nonsensical archive paths or stamp items with bad timestamps.
- **Suggested Fix**: Add sanity bounds at the **orchestrator** boundary (`resolve_target_date`) rather than in the models, since the models are also used in historical replays where wider bounds may be needed. Concrete check: `2024-01-01 ≤ target_date ≤ today + 1`. For Source Adapters, reject items whose `published_at` is more than 30 days in the future.
- **Effort**: ~15 min in u5 orchestrator; ~10 min in u1 sources base.
- **Priority Reasoning**: Medium — defensive only; would catch upstream typos but does not currently block any real flow.

### Low Priority

_No low priority items._

---

## Resolved Items

_No resolved items yet._

---

*Managed by `/tech-debt` skill. Run `/tech-debt add` to add new items.*
