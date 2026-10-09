# u164 business rules

1. Snapshot permission is absent for an explicit historical target date. Legacy/direct collection defaults remain date-filtered.
2. Live eligibility is `receipt - 6h <= provider_as_of <= receipt`; updates during HTTP are permitted. No timestamp backdating or future tolerance.
3. Current price must be finite, positive and non-boolean. Optional change/high/low/volume/cap are omitted if malformed/non-finite; nonnegative metrics may retain a real zero. Unknown change never becomes flat.
4. Preserve actual published_at and metadata: live_snapshot, price_as_of, observed_at, report_target_date. Public text explicitly says 조회 시점 가격, with actual UTC time; 24h metrics are rolling metrics, not report-date closes.
5. Missing optional values never suppress an otherwise valid price or become fabricated ranges in visual/watchpoint/summary output.
6. No extra network request, paid endpoint, provider fallback, source-count change or relaxed content gate. Optional free Demo header support is isolated from Pro APIs; credential and GHA operational verification remain separate.
