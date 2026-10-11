# ADR 0001: Flat market observation groups alongside the sector overview

Date: 2026-10-10. Status: accepted within the user-approved u145 follow-up.

The eleven-sector radar obscures semiconductor/software/hardware differences, while M7
crosses GICS sector boundaries. Users requested a flat detailed comparison and kept the
market overview. ETF holdings cannot be treated as disjoint subdivisions of XLK.

We retain original SectorTicker/private NAV identities and eleven-sector metrics unchanged.
Separate closed MarketGroupId/AdditionalAssetTicker definitions own the fourteen industry,
representative and theme rows. They reuse source-neutral derived price calculations,
but keep distinct ranking denominators and fixed identity ties.

SMH/XSW/MAGS supply qualified ETF observations. A pure hardware ETF was not qualified;
XTH is liquidated. The hardware view explicitly compounds daily equal-weight returns of
eight fixed representative stocks, with every member/session required and no missing fill.
It is not a complete industry, investable ETF or dividend-reinvested return series.

Schema3 embeds both views in the original hashed JSON/Markdown pair, preserving the existing
recoverable two-file transaction and backward-compatible schema2 reader/serialization.
No second store, JavaScript API fetch, provider, dependency or private-fixture route is added.
Display-only filters preserve calculation scale/ranks and no-JS accessibility.

One bounded23-asset collection shares the original36-attempt/resource policy. Missing new
groups may produce honest partial output with exit2; failed parent gates hold the entire
prior pair. Five exact-code production-adapter probes qualify the expanded universe before
activation. Source permission remains unverified under the existing u145 exception;
Browser acceptance remains waived rather than replaced by supplemental QA.

Alternatives rejected: inventing private-sector identities for additional tickers; silently
treating ETF returns as XLK components; reallocating weights when a basket member is missing;
filter-dependent recalculation; a new provider/raw public dataset or independent group store.
Exact group scope can change only through a versioned registry/contracts/qualification update.
