from datetime import datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from investo.models.insights import (
    InsightRunOutcome,
    InsightTime,
    SourceInsightEnvelope,
    ValidatedInsightModule,
    canonical_bytes,
    public_href,
)
from investo.models.items import NormalizedItem
from investo.models.results import PipelineResult, PipelineStatus
from tests._helpers.insights import NOW, capture, metric, module, qualification


@pytest.mark.parametrize("value", [True, False, "NaN", "Infinity", "-Infinity", "x", "1" * 65, 1.2])
def test_invalid_numeric_input_is_rejected(value):
    with pytest.raises(ValidationError):
        metric(value=value)


@given(
    st.decimals(
        allow_nan=False, allow_infinity=False, min_value=-100000, max_value=100000, places=8
    )
)
def test_decimal_round_trip(value):
    row = metric(value=value)
    assert type(row).model_validate_json(row.model_dump_json()).value == value


def test_negative_rate_is_valid_and_immutable():
    row = metric(value="-1.25")
    assert row.value == Decimal("-1.25")
    with pytest.raises(ValidationError):
        row.value = Decimal(1)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(basis="source_response", precision="exact", exact_at=datetime(2026, 1, 1)),
        dict(basis="effective_date", precision="date", local_date=NOW.date()),
        dict(basis="period", precision="month", period="2026-13"),
        dict(
            basis="source_response", precision="date", local_date=NOW.date(), source_timezone="UTC"
        ),
        dict(basis="collection_window", precision="exact", exact_at=NOW),
    ],
)
def test_time_does_not_invent_clock(kwargs):
    with pytest.raises(ValidationError):
        InsightTime(**kwargs)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,test",
        "http://example.invalid/",
        "https://user:secret@example.invalid/",
        "https://example.invalid/?api_key=secret",
        "https://example.invalid/#fragment",
    ],
)
def test_public_links_fail_closed(url):
    with pytest.raises(ValueError):
        public_href(url)


def test_permission_axes_are_separate():
    projected = module(qualifications=(qualification(public_git_history_allowed=False),))
    assert not projected.metrics and "rights_unverified" in projected.reasons
    with pytest.raises(ValidationError):
        qualification(evidence_hrefs=())


def test_envelope_never_serializes_into_item_or_prompt():
    base = NormalizedItem(
        source_name="bybit-derivatives", category="macro", title="legacy", published_at=NOW
    )
    private = base.model_copy(update={"insight_envelope": capture().envelopes[0]})
    assert private.model_dump_json() == base.model_dump_json()
    assert private.model_dump() == base.model_dump()
    assert "insight_envelope" not in private.model_dump(include={"insight_envelope"})
    assert NormalizedItem.model_validate_json(private.model_dump_json()).insight_envelope is None


def test_result_omits_default_and_confirmed_requires_receipt():
    base = PipelineResult(target_date=NOW.date(), status=PipelineStatus.FAILED, duration_seconds=0)
    assert "insights" not in base.model_dump_json()
    with pytest.raises(ValidationError):
        InsightRunOutcome(mode="active", modules=("macro",), status="remote_confirmed")


def test_snapshot_hash_is_checked_on_read():
    projected = module()
    assert ValidatedInsightModule.model_validate_json(canonical_bytes(projected)) == projected
    payload = projected.model_dump(mode="json")
    payload["snapshot_id"] = "0" * 64
    with pytest.raises(ValidationError):
        ValidatedInsightModule.model_validate(payload)


def test_envelope_owner_mismatch_rejected():
    with pytest.raises(ValidationError):
        SourceInsightEnvelope(source_name="wrong", metrics=(metric(),))


@given(
    st.decimals(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False, places=4)
)
def test_history_streaming_json_matches_canonical_and_round_trips(value):
    import json

    from investo.models.insights import canonical_bytes, read_insight_history
    from investo.orchestrator.insights_projection import update_history

    projected = module(metric(value=value))
    history = update_history(projected, None, (qualification(),))
    encoded = canonical_bytes(history)
    expected = json.dumps(
        history.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert encoded == expected
    assert read_insight_history(encoded) == history


def test_history_canonical_reader_rejects_pretty_or_duplicate_keys():
    import json

    from investo.models.insights import canonical_bytes, read_insight_history
    from investo.orchestrator.insights_projection import update_history

    history = update_history(module(), None, (qualification(),))
    with pytest.raises(ValueError):
        read_insight_history(json.dumps(history.model_dump(mode="json"), indent=2).encode())
    encoded = canonical_bytes(history)
    with pytest.raises(ValueError):
        read_insight_history(
            encoded.replace(b'"schema_version":1}', b'"schema_version":1,"schema_version":1}')
        )
