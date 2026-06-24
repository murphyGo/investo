# Code Summary: u109 domestic-anchor-sanity-quarantine

## Overview

Implemented a deterministic domestic anchor trust gate so untrusted Korean market exact values are withheld before public anchor, prose, chart, visual, quality, or Telegram surfaces consume them.

## Application Changes

- Added `src/investo/orchestrator/domestic_anchor_quarantine.py` with bounded registry normalization, candidate extraction, trust classification, and trusted item filtering.
- Updated `_build_kr_anchors_from_items()` to accept `target_date` and `source_outcomes`, and to emit only trusted KOSPI/KOSDAQ/USD-KRW anchors.
- Updated the segmented pipeline to pass source outcomes/target date into domestic anchor synthesis and to filter untrusted domestic registry price rows before Telegram market snapshots.
- Extended `publisher.anchor_assertion_gate` so exact Samsung Electronics and SK Hynix claims require trusted matching anchors.
- Added `QualitySnapshot.domestic_anchor_withheld_count` and `domestic_anchor_withheld_reasons` append-only fields, populated from u109 verdicts.

## Tests

- Added `tests/unit/orchestrator/test_domestic_anchor_quarantine.py`.
- Extended KR anchor, anchor assertion, quality history, notifier, visual, channel-anchor, and chart-sidecar coverage.
- Validation run: `uv run --extra dev pytest tests/unit/orchestrator/test_domestic_anchor_quarantine.py tests/unit/orchestrator/test_kr_anchors.py tests/unit/orchestrator/test_anchor_close_reconcile.py tests/unit/publisher/test_anchor_assertion_gate.py tests/unit/publisher/test_channel_anchor_block.py tests/unit/publisher/test_chart_sidecar.py tests/unit/visuals tests/unit/notifier/test_summary_extract.py tests/unit/notifier/test_summary.py tests/unit/briefing/test_quality_history.py` -> 295 passed.
- Validation run: scoped `ruff check` over changed source/test areas -> passed.
- Validation run: `uv run --extra dev mypy src` -> passed.

## Notes

- No new source adapter, external validation, network call, secret, dependency, workflow, database, or archive backfill was added.
- US and crypto anchor semantics remain unchanged.
