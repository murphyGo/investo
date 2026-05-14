# u58 Crypto-Regulation Policy Sources — Code Generation Summary

**Date**: 2026-05-14
**Unit**: u58 crypto-regulation-policy-sources
**Status**: Complete (8/8 steps)
**FR**: FR-001 / FR-002 / FR-008 reuse; no new FR registered.

## Goal

Prevent official U.S. crypto-policy events, such as CLARITY Act markup,
digital-asset market-structure bills, and stablecoin legislation, from being
dropped before the crypto briefing generation path sees them.

## Key Deliverables

- `sources/official_policy.py` adds three official-source adapters:
  `congress-gov-bill-actions`, `senate-banking-policy`, and
  `house-financial-services-policy`.
- Congress.gov is optional-key only through `CONGRESS_API_KEY`; missing or
  rejected keys produce sanitized source failures without leaking query strings
  or configured key values.
- Senate Banking uses official configured watch URLs for HTML hearing/release
  pages, with fixture coverage for the 2026-05-14 CLARITY executive session and
  the 2026-05-12 market-structure bill-text release.
- House Financial Services consumes the official `news/rss.aspx` feed and
  filters non-crypto committee news before emitting normalized items.
- Official policy items stamp primitive metadata:
  `policy_priority=crypto_regulation`, `official_source=true`, `bill_id`,
  `committee`, and `event_type`.
- Segment routing now sends official crypto-policy metadata to `crypto` even
  when the title/body lacks BTC, ETH, price, or ticker terms.
- LLM candidate selection preserves official crypto-regulation items before the
  generic news cap, while keeping the global cap bounded.
- Stage prompts now allow source-backed regulation/legislation events to become
  crypto core issues when market-structure relevant, without legal advice,
  passage odds, token-winner claims, price-impact promises, or trading
  instructions.

## Tests

- `tests/unit/sources/test_official_policy.py` covers success, no-key, 403,
  empty actions/feed, malformed JSON/XML, selector-missing, and crypto filtering.
- `tests/unit/briefing/test_segments_exclusivity.py` covers source-name and
  metadata-based crypto routing.
- `tests/unit/briefing/test_pipeline_unit.py` covers candidate preservation
  before the 96-item generic cap.
- `tests/unit/_internal/test_redaction.py` covers `CONGRESS_API_KEY` in the
  shared secret catalog.
- `tests/integration/test_pipeline.py` expectation updated to the current visual
  asset contract: SVG assets plus manifest sidecars are counted.

## Quality Gate

| Gate | Result |
|------|--------|
| `uv run ruff check .` | clean |
| changed-file `ruff format --check` | clean |
| `uv run mypy --strict src/` | 127 source files, 0 issues |
| targeted u58 + integration tests | 154 passed |
| `uv run pytest -q` | 2326 passed |
| `uv run mkdocs build --strict` | clean |

Full `uv run ruff format --check .` is blocked by four pre-existing
out-of-scope files: `src/investo/orchestrator/pipeline.py`,
`src/investo/publisher/reader_format.py`,
`tests/unit/orchestrator/test_run_pipeline.py`, and
`tests/unit/visuals/test_assets.py`.

## Files

**New**:
- `src/investo/sources/official_policy.py`
- `tests/unit/sources/test_official_policy.py`
- `tests/unit/sources/fixtures/api/official-policy/*`

**Modified**:
- `src/investo/sources/{__init__,aggregator,tiers}.py`
- `src/investo/briefing/{segments,pipeline,prompts}.py`
- `src/investo/_internal/redaction.py`
- `docs/tech-env.md`
- u58-related tests and AIDLC evidence files.
