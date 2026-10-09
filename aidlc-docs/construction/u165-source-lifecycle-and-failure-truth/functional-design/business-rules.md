# u165 business rules

1. SourceSpec is the sole activation/default registry. Default-disable Binance region_denied, CNBC access_denied, Yahoo news endpoint_removed, FSC policy upstream_unavailable and Naver flows endpoint_removed; retain all names/specs.
2. Exact case-sensitive known names only in INVESTO_SOURCE_ENABLE/DISABLE. Reject unknown names or overlap before source requests. Operator disable reason is operator_disabled; explicit enable removes a default skip only for that run.
3. Skipped outcome:0 items, enum reason, no failure_reason, transient, latest_item_at or elapsed attempt. Attempted outcomes forbid skip reason; historic three states remain readable.
4. Configured=attempted+skipped. Successful/zero/failed sums describe attempts only. Every skipped reason stays visible; sparse valid zero remains distinct from unavailable transport.
5. All-core-skipped is missing capability, never normal. Missing required categories/macro remain missing. No successful/full observation receipt or cursor advancement comes from a skip.
6. Naver all-child request errors fail; valid empty/partial data remain valid; programmer/system exceptions propagate.
7. BEA entire adapter≤60s including retries, with remaining child deadlines. Completed rows survive expiry; no completed successful response plus errors fails. Raw API errors/URLs/keys are not logged.
8. Existing rights/activation/registry/count/core rules are preserved. No proxy, paid fallback, synthetic actual or automatic persistent quarantine.

9. Disabled Yahoo price cannot invoke its history context loader or be rebuilt as ok from same-run history. Skipped domestic provenance remains unavailable.
10. Public diagnostic records preserve actually healthy siblings of skipped providers. Generic link accounting and canonical/replay recounters use the same closed source identities/reasons; fenced/unknown diagnostic values cannot suppress evidence.
11. Current-day canonical reconciliation replaces the complete source measurement cohort including failure numerator and attempted denominator. Historic/manual inputs without per-day attribution retain conservative floors.
