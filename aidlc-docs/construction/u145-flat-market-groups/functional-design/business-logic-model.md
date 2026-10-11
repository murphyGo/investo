# Flat radar business logic and entities

The approved product presents a flat fourteen-group radar by default and retains
the original eleven-sector market overview through a view switch. Category filters
affect visible rows, bars and regime chips only. Rankings and scales retain their
view-specific complete-universe basis; the denominator is always visible.

Entities: fixed additional asset identity (three ETF/eight equity), validated price
series, fourteen fixed group identities/definitions, source-neutral price metrics,
group regime, group rank, derived group bundle and existing public snapshot/pair.
Industry and theme are explicit metadata. Hardware has `representative_basket` kind;
M7 has `theme` kind. No group is described as a disjoint partition of XLK or all stocks.

One collection obtains SPY first, then fixed ETF/equity prices under one budget.
The original eleven-sector computation remains independently valid. Additional
groups require the exact same final64 SPY sessions, with no missing date, fill or
substitution. Hardware requires every member and uses the arithmetic mean of the
eight daily simple returns, compounded into a synthetic price index. It is daily
equal-weight, dividend-reinvestment excluded, no fund/transaction-cost simulation.

Each group uses the shared 1/5/21/63-session price metrics and 10bps hysteresis regime.
Reused sector groups carry identical original metrics/regime. Flat ranking applies
the existing 5/21/63 weights/midrank policy to the fourteen groups, minimum8 comparable
groups and two horizons. Overview ranks keep their eleven-sector basis. Ties use
the fixed identity order; volume never enters calculation.

Schema3 embeds the derived group bundle in the existing snapshot; schema2 excludes
the new field completely. Canonical deterministic identity covers both views in
schema3. Existing two-file transaction, last-good and exact-path git staging remain.
Unavailable new groups have closed reasons and no metrics/regime/rank. Hardware
suppresses as a whole if one member is unavailable. Usable original coverage can
still promote with explicit group partial status/exit2. Parent benchmark/date/history,
resource, corrupt pair or projection failure blocks promotion or preserves last-good.
