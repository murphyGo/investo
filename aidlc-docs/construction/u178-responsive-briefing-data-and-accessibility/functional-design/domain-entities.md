# u178 Domain entities

Existing DataConfidenceCardInput, MarketSnapshotCardInput, PriceSnapshotCardInput/Row, WatchlistRelevanceCardInput/Row remain frozen and unchanged. VisualMarkdownBlock placement_key/markdown/artifact_ids remains unchanged. html_by_kind is Mapping[str,str]|None local presentation input, not stored financial data. PublicDocumentSupplement and PublicDocumentLayout reader_visible visual region preserve exact existing owner. No new enum, second source count calculation or time provenance DTO.

| kind | HTML | missing/failure | artifacts |
|---|---|---|---|
| confidence | canonical status/counts/public reasons, closed details | raw source diagnostics omitted, notice points to diagnostic section | existing pairedSVG+manifest |
| market | full public conclusion/driver/caution | existing builder fallbacks | same |
| price | <=12 exact rows, label/source/time notice and optional fields | no card if existing builder returnsNone; optional strings unknown | same |
| watchlist | configured/default/matches,<=5 rows/sourceHttpUrl | explicit unconfigured/no direct matches | same |

All HTML+fallback bytes stay one visual supplement. No extra artifact ID/binary assets are introduced.
