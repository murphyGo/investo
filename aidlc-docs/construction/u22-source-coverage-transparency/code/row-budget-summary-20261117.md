# u22 data-confidence row budget — implementation and validation

## Result

The card builder now fits the renderer's four visible rows. The logged 3 failed / 7 zero / 2 skipped / 16 ok combination previously generated thirteen rows and raised a Pydantic `too_long` error. It now produces four rows containing every present status and the healthy adapter count. The variant excluding the three new healthy macro adapters also succeeds (normal count 13).

Base: public main `6d526e9b07641cf60f91de148f0217e3d9b22e48`, isolated branch `codex/card-overflow-20261117`. Implementation is local; no new commit, deployment, production pin change, or publication dispatch occurred.

## Implementation

- `src/investo/visuals/cards.py`: share the visible row budget, preserve individual rows when at most four, compact overflow by status, retain singleton details and the healthy summary, and bound derived details to 160 characters.
- `src/investo/visuals/render.py`: consume the same visible budget while retaining legacy direct-input truncation. The twelve-row input schema remains compatible.
- Counts use readable labels (`수집 실패 소스 3개`, `0건 반환 소스 7개`, `비활성 소스 2개`, `정상 16개`). Existing public-language projection stays unchanged. Each aggregated non-ok reason is marked `대표`.
- `tests/unit/visuals/test_data_confidence_row_budget.py`: 20 regression, boundary, large-input, privacy, XML, and asset-integration cases. These are synthetic source-outcome inputs, not provider payload fixtures.

Original source outcomes, coverage decisions, item/source counts, reason codes, and complete diagnostic paths are unchanged. No new external calls, dependencies, SDK, infrastructure, or publication policy. Domestic classification/finalizer errors and upstream availability remain outside this fix.

## Build and test

| Check | Result |
|---|---|
| New tests + existing card/render/asset tests | 76 passed |
| All visuals + coverage model/briefing + orchestrator + pipeline integration + module boundaries | **590 passed in 72.72 s**, no skips/failures |
| Changed-file Ruff lint and formatting | Pass |
| Mypy on both changed source files | Pass |
| Whitespace diff check | Pass |
| Independent code review | Pass; no findings or technical debt |
| Independent enumeration of status counts 0..5 | 1,296 combinations passed |
| Logged source-outcome replay | Both observed and three-sources-removed cases produce four rows |

Reproduction command from repository root, with the existing Python 3.11 environment and Node 22 on PATH (Cairo available through `/opt/homebrew/lib` on this Mac):

```sh
PYTHONPATH=src python -m pytest -q \
  tests/unit/visuals tests/unit/models/test_coverage.py \
  tests/unit/briefing/test_segments.py tests/unit/briefing/test_coverage_badge.py \
  tests/unit/briefing/test_render_coverage_badge.py \
  tests/unit/orchestrator/test_run_pipeline.py \
  tests/unit/orchestrator/test_skipped_pipeline_u165.py \
  tests/unit/_internal/test_module_boundary.py tests/integration/test_pipeline.py
ruff check src/investo/visuals/cards.py src/investo/visuals/render.py tests/unit/visuals/test_data_confidence_row_budget.py
ruff format --check src/investo/visuals/cards.py src/investo/visuals/render.py tests/unit/visuals/test_data_confidence_row_budget.py
mypy src/investo/visuals/cards.py src/investo/visuals/render.py
```

The asset test runs the actual `prepare_segment_visual_assets` path with synthetic outcomes and an existing-valid briefing shape. It checks light/dark SVG, dimensions, provenance, inserted relative links, status counts, and disclaimer. No network or LLM is needed. It does not execute the production publisher. A repository-wide suite was not run for this bounded repair; the selected tests cover the affected projection and its integration paths.

## Replay and appearance evidence

Sanitized replay summary: `row-budget-replay-20261117.json` next to this file. The private job log from run `43143375754` remains outside tracked artifacts. Source names, categories, statuses, returned counts, and skip reasons were reconstructed; failure text was replaced with `Recorded source failure`. The replay's aggregate coverage object is constructed for projection testing, not a reconstruction of normalized items or full classification.

Local evidence directory: `.tmp/card-overflow-20261117/` contains `related-tests.xml`, `related-tests.log`, `replay.py`, `replay-result.json`, and light/dark SVG/PNG previews. Both themes were visually inspected: all four status labels/counts and the disclaimer fit without overlap in the replay. Cairo's default font resolution lacked Korean glyphs; inspection previews substituted the installed AppleGothic font only during local rasterization. Production SVG font declarations remain unchanged. The browser tool was unavailable, so this is local rendering QA, not deployed-browser validation.

## Limits and release handoff

Detailed diagnostics retain every adapter; the small card deliberately shows one representative per aggregated status. This prevents the observed source-row overflow but does not claim to make every possible visual-input error recoverable. Fresh production completion must be verified after a separately requested commit/deployment. Existing upstream and domestic article-quality failures are independent.

See `row-budget-review-20261117.md` and `docs/cross-checks/2026-11-17-u22-data-confidence-row-budget.md` for independent review and requirement traceability.
