# u174–u179 bounded UI runtime delivery

The user requested push and deployment on 2026-10-10. This branch applies the completed UI units to the previously reviewed production runtime `4e0dc424a65d075a4437e08d849e7b667f2764c2`. The source unit commits remain on `codex/ui-development-20261010` (`2734c3af`). Public main and the private runtime have separate rollout boundaries.

The bounded patch adds the calendar build hook, chart sidecar/theme repair, shared navigation and styles, canonical home cards, readable structured data before sealing, and monthly archive discovery. It includes meaningful UI and rollback tests plus Node 22 client checks in Quality. Approved sector Markdown, JSON and scoped CSS from public main `ea402465` are copied as static navigation targets; no sector provider or builder is introduced.

The original runtime source/model/LLM/enrichment/sector code, dependencies, lock, and daily workflow are unchanged. The old number-emphasis implementation is retained; only the new structured HTML cards skip cosmetic wrapping. Existing public-document trust and seal checks remain active. Historical briefing bodies and sidecar assets are unchanged; only index pages are regenerated.

Independent code review: APPROVE, no P1/P2. Local publisher/visuals/site/seal tests: 2,226 passed in 179.46 seconds. Ruff and format (689 files), strict mypy (292 source files), four policy guards, strict MkDocs, Material/calendar contracts, and Node 22 client behavior (29 tests) pass. Publication/pipeline rollback regression: 131 passed in 199.68 seconds. Exact-SHA remote Quality remains a separate gate; production pin promotion requires its success and an idle runtime.

Rollback restores `REVIEWED_CODE_SHA` to `4e0dc424a65d075a4437e08d849e7b667f2764c2`. Existing segment, news-window, enrichment, source, and schema modes are preserved. No manual briefing or notification is dispatched as part of this delivery. Live site and pin readback evidence are recorded in the public integration closeout after deployment.
