# u95 Workflow And Enrichment Critical Path Budget — NFR Addendum

## Scope

This addendum covers setup caching and best-effort enrichment budgets on the daily briefing critical path. It does not change cron triggers, permissions, paid-service policy, prompt content, generated markdown layout, or visual licensing.

## NFR-001 Performance

- GitHub Actions uses uv cache keyed by `uv.lock`.
- GitHub Actions uses Node setup with npm cache for the Claude Code CLI install step.
- Market-anchor history fetch is bounded by `INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S`, defaulting to `8.0` seconds.
- Visual asset preparation is bounded by `INVESTO_VISUAL_PREP_CONCURRENCY`, accepted values `1`, `2`, `3`, defaulting to `1`.

## NFR-002 Zero Cost

- No new paid service, external worker, cache server, or secret is introduced.
- Caching uses GitHub Actions built-in cache support only.
- OpenAI visual opt-in remains controlled by the existing `INVESTO_OPENAI_VISUALS` guard.

## NFR-003 Graceful Degradation

- Market-anchor timeout or fetch failure returns empty anchors and empty history so segment generation can continue.
- Domestic KR close-only anchors from collected items remain available after Yahoo-history degradation.
- Visual prep failure remains a text-only publish path and does not fail the pipeline.
- Visual prep result ordering is reassembled by `SEGMENT_ORDER`.

## NFR-007 Secret Handling

- Workflow caching does not add cache-specific credentials.
- Runtime logs include elapsed/degraded reason for anchor fetches and invalid env warnings only.
- No prompt text, OAuth token, Telegram token, chat ID, or source secret is logged.

## Validation

- `uv run --extra dev pytest tests/unit/orchestrator tests/unit/sources tests/unit/publisher -q`
- `uv run --extra dev pytest tests/integration/test_pipeline.py -q`
- `uv run --extra dev ruff check src/investo/orchestrator tests/unit/orchestrator tests/unit/sources tests/unit/publisher tests/integration/test_pipeline.py`
- `uv run --extra dev mypy src`
