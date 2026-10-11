# u177 Domain entities

Reuse frozen SegmentBundleState unchanged: segment/target_date/generated/href/fallback_date/fallback_href. CoverageStatus|None is canonical current-version quality; no new enum or duplicate state/dataclass. Inputs are existing sealed Briefing consumers; summary is the existing projected conclusion, quality the existing parsed status. HomeCard is transient presentation, not persisted DTO/sidecar. Future `terminal_summaries: Mapping[MarketSegment,str]|None` and `terminal_quality_labels: Mapping[MarketSegment,str]|None` are exact plain presentation fields from the u171 adapter, not a semantic v3 model. Production wiring belongs to u171 when its canonical model exists.

Home gate reuses CanonicalQualitySnapshot and ConsistencyFinding. New mismatch codes remain within the existing quality gate registry/rollback path, not new severity policy. No snapshot recalculation or publish ordering change beyond state-build before home render.
