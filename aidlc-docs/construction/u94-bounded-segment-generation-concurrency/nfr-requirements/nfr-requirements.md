# u94 Bounded Segment Generation Concurrency — NFR Addendum

## Scope

This addendum covers the runtime and safety constraints for bounded intra-generate segment fanout. It does not change source collection, publish, notify, prompt content, Claude timeout policy, or retry policy.

## NFR-001 Runtime

- `INVESTO_SEGMENT_GENERATION_CONCURRENCY` controls only domestic/US/crypto segment generation inside `GenerateStage`.
- Accepted values are `1`, `2`, and `3`.
- Default is `1` for controlled rollout and behavior-compatible serial execution.
- Invalid values fall back to `1` and emit one warning.
- Top-level stages remain sequential: collect completes before generate; publish and notify wait until segment generation and reader-format work finish.

## NFR-003 Graceful Degradation

- `BriefingGenerationError` remains isolated per segment.
- A failed segment does not block successful sibling segments from publishing.
- If every segment fails, `_stage_generate_segments` raises the first `SEGMENT_ORDER` failure, preserving prior all-failed behavior.
- Programmer errors are not swallowed by concurrency; they are re-raised after `asyncio.gather(..., return_exceptions=True)`.
- Result dictionaries are reassembled in `SEGMENT_ORDER`, not task completion order.

## NFR-007 Subprocess And Secret Safety

- u94 does not change Claude CLI invocation, environment variables passed to subprocesses, prompt construction, or retry budget.
- The concurrency implementation logs only segment labels, stage, attempt count, env-key validity, and timing already surfaced by u92.
- It does not log prompt text, OAuth tokens, Telegram tokens, chat IDs, or source URLs.

## Validation

- `uv run --extra dev pytest tests/unit/orchestrator -q`
- `uv run --extra dev pytest tests/integration/test_pipeline.py -q`
- `uv run --extra dev ruff check src/investo/orchestrator tests/unit/orchestrator`
- `uv run --extra dev mypy src`
