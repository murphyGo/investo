# Domain entities and boundaries

| Entity | Identity / responsibility | Exposure |
| --- | --- | --- |
| AdditionalAssetTicker | Closed3 ETF +8 equity identities, separate from original SectorTicker | Symbol metadata only |
| MarketGroupDefinition | Fourteen fixed IDs, names, category, kind, members and honest measurement scope | Fixed labels |
| AdditionalParsedSet | In-memory success/failure partition of additional11 symbols | Never serialized as public snapshot |
| PublicPriceMetrics | Eleven derived scalar slots reused without imposing private sector identity | Derived public |
| PublicGroupRegime / PublicGroupRank | Source-neutral regime, independent14-group ranking constraints | Derived public |
| PublicMarketGroupRecord | Exact registry metadata plus complete or entirely suppressed observations | Derived public |
| PublicMarketGroupBundle | Exactly14 records, same date, validated coverage/denominators/tie order | Schema3 child |
| PublicSectorDashboardSnapshot | Existing11 records plus optional3-only group bundle, one hash | Canonical public pair |
| Radar view/filter state | Existing generated DOM visibility only | Browser-local; never affects data |

The collector owns bounded raw observations only for the current calculation. Snapshot ownership,
canonical projection, rollback/recovery store and repository publication remain existing separate
boundaries. Snapshot validators bind the ten shared groups to their overview values. Raw observations,
headers, URLs, provider text, account values and volume have no new public fields.
