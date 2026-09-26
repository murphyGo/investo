"""E8 truthful denominators and private/public diagnostic boundaries."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investo.models.event_quality import (
    EventCoverage,
    EventStageReceipt,
    EventTraceEntry,
    aggregate_published_event_coverage,
    parse_public_event_coverage,
)


def test_unknown_zero_and_observed_omission_are_distinct() -> None:
    unknown = EventCoverage()
    zero = EventCoverage(selected_count=0, terminal_event_count=0, qualified_event_count=0)
    missing = EventCoverage(selected_count=2, terminal_event_count=0, qualified_event_count=0)
    assert unknown.omitted_count is unknown.selection_coverage is unknown.qualified_coverage is None
    assert zero.omitted_count == 0
    assert zero.selection_coverage is zero.qualified_coverage is None
    assert missing.omitted_count == 2
    assert missing.selection_coverage == missing.qualified_coverage == 0
    assert EventCoverage(selected_count=2, qualified_event_count=0).qualified_coverage is None


def test_limited_events_are_terminal_but_not_qualified() -> None:
    coverage = EventCoverage(
        selected_count=3,
        terminal_event_count=2,
        qualified_event_count=1,
        details_limited_count=1,
        summary_event_count=2,
        state="detail_limited",
    )
    assert coverage.selection_coverage == 2 / 3
    assert coverage.qualified_coverage == 1 / 3
    assert coverage.omitted_count == 1


@pytest.mark.parametrize("status", ["failed", "not_run"])
def test_uncompleted_receipt_cannot_claim_zero(status: str) -> None:
    with pytest.raises(ValidationError, match="unknown count"):
        EventStageReceipt.model_validate({"stage": "classified", "status": status, "count": 0})


def test_private_receipts_are_never_publicly_serialized() -> None:
    receipt = EventStageReceipt(
        stage="selected",
        status="completed",
        count=1,
        trace=(EventTraceEntry(hash_id="a" * 24, stage="selected", source_name="synthetic-feed"),),
    )
    coverage = EventCoverage(selected_count=1, receipts=(receipt,))
    serialized = coverage.model_dump_json()
    assert "receipts" not in serialized
    assert "synthetic-feed" not in serialized
    assert "a" * 24 not in serialized
    with pytest.raises(ValidationError):
        receipt.count = 2  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EventTraceEntry(hash_id="raw article", stage="selected")
    with pytest.raises(ValidationError):
        EventTraceEntry(hash_id="a" * 24, stage="selected", source_name="https://secret.test")


@pytest.mark.parametrize(
    "values",
    [
        {"selected_count": True},
        {"selected_count": -1},
        {"selected_count": 1, "terminal_event_count": 2},
        {"terminal_event_count": 1, "qualified_event_count": 1, "details_limited_count": 1},
        {"selected_count": 1, "omitted_count": 0},
        {"reasons": ["private prose"]},
        {"issue_codes": ["event.raw-secret"]},
    ],
)
def test_invalid_public_counts_and_arbitrary_text_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EventCoverage.model_validate(values)


def test_remote_aggregate_excludes_unknown_failed_and_unconfirmed_segments() -> None:
    valid = EventCoverage(
        selected_count=2,
        terminal_event_count=2,
        qualified_event_count=1,
        details_limited_count=1,
        state="detail_limited",
    )
    result = aggregate_published_event_coverage(
        {
            "us-equity": valid,
            "domestic-equity": EventCoverage(state="classification_unavailable"),
            "crypto": valid,
        },
        remote_confirmed_segments=("us-equity", "domestic-equity"),
    )
    assert result.included_segments == ("us-equity",)
    assert result.excluded_segments == ("crypto", "domestic-equity")
    assert result.selected_count == 2
    assert result.selection_coverage == 1
    assert result.qualified_coverage == 0.5
    # Notifications have no authority to change the remote-confirmed result.
    assert result == aggregate_published_event_coverage(
        {
            "crypto": valid,
            "domestic-equity": EventCoverage(state="classification_unavailable"),
            "us-equity": valid,
        },
        remote_confirmed_segments=("domestic-equity", "us-equity"),
    )


def test_empty_and_known_zero_remote_denominators_stay_unknown_rates() -> None:
    empty = aggregate_published_event_coverage({"crypto": None}, remote_confirmed_segments=())
    zero = aggregate_published_event_coverage(
        {
            "crypto": EventCoverage(
                selected_count=0,
                terminal_event_count=0,
                qualified_event_count=0,
                state="no_qualifying_event",
            )
        },
        remote_confirmed_segments=("crypto",),
    )
    assert empty.selected_count is None
    assert empty.excluded_segments == ("crypto",)
    assert zero.selected_count == 0 and zero.included_segments == ("crypto",)
    assert empty.selection_coverage is zero.selection_coverage is None


def test_public_roundtrip_rejects_forged_rates_and_private_trace() -> None:
    coverage = EventCoverage(selected_count=2, terminal_event_count=1, qualified_event_count=1)
    raw = coverage.model_dump(mode="json")
    assert parse_public_event_coverage({"crypto": raw}) == {"crypto": coverage}
    raw["selection_coverage"] = 1
    assert parse_public_event_coverage({"crypto": raw}) is None
    raw = coverage.model_dump(mode="json")
    raw["receipts"] = []
    assert parse_public_event_coverage({"crypto": raw}) is None


@pytest.mark.parametrize(
    "contradiction",
    [
        {"reasons": ("hard_trust_blocked",)},
        {"issue_codes": ("event.fact_unsupported",)},
        {"reasons": ("classification_unavailable",)},
        {"reasons": ("source_unavailable",)},
        {"reasons": ("detail_limited",)},
        {"unsupported_count": 1},
    ],
)
def test_hard_or_degraded_evidence_cannot_be_labeled_qualified(
    contradiction: dict[str, object],
) -> None:
    legitimate = EventCoverage(
        selected_count=1,
        terminal_event_count=1,
        qualified_event_count=1,
        state="qualified",
    )
    raw = legitimate.model_dump(mode="json") | contradiction
    assert parse_public_event_coverage({"crypto": raw}) is None
    forged = legitimate.model_copy(update=contradiction)
    result = aggregate_published_event_coverage(
        {"crypto": forged},
        remote_confirmed_segments=("crypto",),
    )
    assert result.included_segments == () and result.excluded_segments == ("crypto",)
    assert result.selection_coverage is result.qualified_coverage is None


def test_hard_blocked_known_numerator_is_rejected_but_all_reasons_are_retained() -> None:
    with pytest.raises(ValidationError, match="terminal counts"):
        EventCoverage(selected_count=1, terminal_event_count=1, state="hard_trust_blocked")
    coverage = EventCoverage(
        selected_count=1,
        state="hard_trust_blocked",
        reasons=("hard_trust_blocked", "source_limited", "finalization_unavailable"),
        issue_codes=("event.fact_unsupported",),
    )
    assert set(coverage.reasons) == {
        "hard_trust_blocked",
        "source_limited",
        "finalization_unavailable",
    }
    assert coverage.selection_coverage is coverage.qualified_coverage is None
