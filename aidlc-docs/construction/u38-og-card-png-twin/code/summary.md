# u38 og-card-png-twin Code Summary

**Date**: 2026-05-09
**Status**: Complete

## Implementation

- Chose the Python-side `cairosvg` path and added it as a runtime dependency.
- `write_og_card()` now writes `site_docs/assets/og-card.svg`, `site_docs/assets/og-card.png`, and both provenance manifest sidecars as one returned publish set.
- The orchestrator now snapshots and commits the SVG/PNG OG asset pair plus sidecars during segmented publish.
- `overrides/main.html` now advertises PNG as the primary `og:image` with width/height/type metadata and retains SVG as a secondary `og:image:secure_url`.
- The daily briefing workflow installs `libcairo2` / `libcairo2-dev` and preflights `cairosvg.svg2png` before running the pipeline.
- DEBT-058 moved to resolved items.

## Verification

- `uv run pytest tests/unit/visuals/test_og_card.py tests/unit/orchestrator/test_run_pipeline.py -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy --strict src/`
- `uv run pytest -q`
- `uv run mkdocs build --strict`

External Telegram / Slack / X / LinkedIn unfurl screenshots were not captured in this local session; the structural OG tags and generated PNG asset are pinned by automated tests and `mkdocs build --strict`.
