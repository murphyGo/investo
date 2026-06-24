"""Compatibility pins for u114 shared-domain contract ownership."""

from __future__ import annotations


def test_time_state_briefing_reexport_is_model_contract() -> None:
    import investo.briefing.time_state as briefing_time_state
    import investo.models.time_state as model_time_state

    assert briefing_time_state.TimeState is model_time_state.TimeState


def test_segment_coverage_briefing_reexport_is_model_contract() -> None:
    import investo.briefing.segments as briefing_segments
    import investo.models.segments as model_segments

    assert briefing_segments.SegmentCoverage is model_segments.SegmentCoverage


def test_market_anchor_briefing_reexport_is_model_contract() -> None:
    import investo.briefing.market_anchor as briefing_anchor
    import investo.models.market_anchor as model_anchor

    assert briefing_anchor.MarketAnchor is model_anchor.MarketAnchor
    assert briefing_anchor.anchor_label is model_anchor.anchor_label


def test_watchlist_dtos_briefing_reexport_model_contracts() -> None:
    import investo.briefing.watchlist as briefing_watchlist
    import investo.briefing.watchlist_impact as briefing_impact
    import investo.models.watchlist as model_watchlist

    assert briefing_watchlist.WatchlistImpact is model_watchlist.WatchlistImpact
    assert briefing_watchlist.WatchlistMatch is model_watchlist.WatchlistMatch
    assert briefing_impact.RejectedCandidate is model_watchlist.RejectedCandidate
    assert briefing_impact.WatchlistImpactCenter is model_watchlist.WatchlistImpactCenter


def test_extract_and_prefix_compatibility_reexports() -> None:
    import investo._internal.briefing_extract as internal_extract
    import investo.briefing.extract as briefing_extract
    import investo.briefing.summary_quality as summary_quality

    assert briefing_extract.extract_conclusion is internal_extract.extract_conclusion
    assert briefing_extract.CONCLUSION_PREFIX is internal_extract.CONCLUSION_PREFIX
    assert briefing_extract.DRIVER_PREFIX is internal_extract.DRIVER_PREFIX
    assert briefing_extract.CAUTION_PREFIX is internal_extract.CAUTION_PREFIX
    assert briefing_extract.WATERMARK_PREFIX is internal_extract.WATERMARK_PREFIX
    assert summary_quality.CONCLUSION_PREFIX is internal_extract.CONCLUSION_PREFIX


def test_core_fact_metadata_key_source_compatibility() -> None:
    import investo.models.core_fact as model_core_fact
    import investo.sources._core_fact_map as source_core_fact

    assert source_core_fact.CORE_FACT_METADATA_PREFIX is model_core_fact.CORE_FACT_METADATA_PREFIX
    assert source_core_fact.core_fact_metadata_key is model_core_fact.core_fact_metadata_key
    assert model_core_fact.core_fact_metadata_key("spx_close") == "core_fact:spx_close"
