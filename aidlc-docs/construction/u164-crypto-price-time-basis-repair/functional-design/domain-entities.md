# u164 domain entities

| Entity | Contract |
| --- | --- |
| FetchWindow | Existing immutable half-open report interval plus optional aware UTC price_snapshot_at permission/reference |
| CoinGecko normalized price | Existing NormalizedItem, true provider published_at, positive price and optional metrics; string metadata records as-of/receipt/report-date |
| SourceOutcome / SegmentCoverage | Existing successful item count/latest timestamp and crypto core six-hour health; no new healthy substitute |
| PriceSnapshotRow | Existing price display with optional change, time-basis/as-of annotation for live prices |
| Watchpoint candidate / SnapshotEntry | Current price can stand alone; optional change and explicit live basis/as-of propagate to display |

The run context retains explicit-date origin via existing news_replay, preventing live snapshot permission in historical collection. No source-specific routing is added to the orchestrator.
