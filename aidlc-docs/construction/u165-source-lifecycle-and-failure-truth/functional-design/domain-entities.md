# u165 domain entities

| Entity | Extension / invariant |
| --- | --- |
| SourceSpec | default_enabled and optional bounded disabled_reason; fixed evidence_domains metadata for generic public link accounting; existing tier/window/routing/news opt-in unchanged |
| SourceSkipReason | region_denied, access_denied, endpoint_removed, upstream_unavailable, operator_disabled; stable Korean labels |
| SourceOutcome | adds skipped and skip_reason with strict zero/no-attempt fields; old ok/zero/failed unchanged |
| SegmentCoverage | configured/targeted versus attempted/skipped counts; all-core-bad still includes skipped |
| CollectionReport / SourceWindowCoverage | disabled outcomes remain explicit; no collection item or source observation coverage from a skipped adapter |
| Coverage history / KPIs / digest | same-date latest record wins; optional new counts/reasons preserve old ledgers; no false100% from all-skipped; per-date configured/skipped/failed/zero cohort preserves numerator/denominator on canonical rerun reconciliation |
| BEA child result | successful item or valid empty versus typed request/schema error; remaining budget and completed successes retained |

No new source identity, storage service, provider adapter or mutable cross-run quarantine state.
