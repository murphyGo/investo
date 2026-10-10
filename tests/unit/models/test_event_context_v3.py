"""V3 source, span, role, time and interpretation invariants."""

import hashlib
from datetime import date, timedelta, timezone

import pytest
from pydantic import ValidationError

from investo.models.event_config import EventGenerationPolicy
from investo.models.event_context import (
    ContextDiagnostic,
    ContextRef,
    EventContextDocument,
    EventTimeContext,
    EventTimeValue,
    EvidenceChunk,
    MeaningContext,
    ReactionContext,
)
from investo.models.event_evidence import make_event_context_document, make_evidence_document
from tests._helpers.event_context_v3 import NOW, document, draft, ref


@pytest.mark.parametrize("start,end", [(-1, 1), (0, 0), (2, 1), (0, 241), (True, 2), (0, "2")])
def test_context_span_is_strict_and_bounded(start: object, end: object) -> None:
    with pytest.raises(ValidationError):
        ContextRef.model_validate(
            dict(
                document_id="a" * 64, revision_id="b" * 64, chunk_id="c" * 64, start=start, end=end
            )
        )


def test_chunk_hash_roles_and_deep_immutability() -> None:
    doc = document()
    chunk = doc.chunks[0]
    with pytest.raises(ValidationError):
        EvidenceChunk.model_validate({**chunk.model_dump(), "text": "substituted source"})
    with pytest.raises(ValidationError):
        EvidenceChunk.model_validate({**chunk.model_dump(), "role": "invented"})
    with pytest.raises(ValidationError):
        chunk.role = "reaction"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EventContextDocument.model_validate({**doc.model_dump(), "chunks": [chunk] * 5})
    assert chunk.text not in repr(chunk)


@pytest.mark.parametrize(
    "value,precision",
    [
        (None, "exact"),
        (NOW.replace(tzinfo=None), "exact"),
        (date(2026, 10, 10), "unknown"),
        (NOW, "date"),
        (None, "date"),
    ],
)
def test_time_precision_cannot_be_invented(value: object, precision: str) -> None:
    with pytest.raises(ValidationError):
        EventTimeValue.model_validate(dict(value=value, precision=precision))


def test_source_date_and_publication_are_not_occurrence_copies() -> None:
    doc = document()
    assert doc.time.occurred_at.value is None and doc.time.announced_at.value is None
    evidence = make_evidence_document(
        source_name="official",
        title="A decision",
        url="https://example.com/time",
        published_at=NOW,
        received_at=NOW,
        published_date=date(2026, 10, 10),
        event_time=date(2026, 10, 9),
        event_time_basis="source_date",
    )
    converted = make_event_context_document(evidence)
    assert type(converted.time.occurred_at.value) is date
    assert converted.time.occurred_at.value == date(2026, 10, 9)
    assert converted.time.published_at.precision == "date"
    assert converted.time.occurred_at.source_refs
    assert (
        EventTimeValue(value=NOW.astimezone(timezone(timedelta(hours=9))), precision="exact").value
        == NOW
    )
    with pytest.raises(ValidationError):
        EventTimeContext(occurred_at=EventTimeValue(value=NOW, precision="exact"))


def test_numeric_metric_identity_requires_source_evidence() -> None:
    fact = draft(document()).facts[0]
    with pytest.raises(ValidationError):
        type(fact).model_validate({**fact.model_dump(), "metric_refs": []})


def test_unknown_meaning_and_reaction_do_not_make_claims() -> None:
    r = ref(document(), "Acme")
    with pytest.raises(ValidationError):
        MeaningContext(mode="unavailable", text="new claim", refs=(r,))
    with pytest.raises(ValidationError):
        MeaningContext(mode="conditional", text="may affect revenue", refs=(r,))
    with pytest.raises(ValidationError):
        ReactionContext(status="observed", attribution="coincidence_only", text="rose", refs=(r,))
    with pytest.raises(ValidationError):
        ReactionContext(status="unavailable", attribution="source_reported", text="rose")
    assert ReactionContext(status="unavailable", attribution="unavailable").text is None


def test_observed_reaction_requires_window_and_compared_refs() -> None:
    doc = document()
    baseline, value = ref(doc, "1200"), ref(doc, "2%")
    reaction = ReactionContext(
        status="observed",
        attribution="coincidence_only",
        asset_id="ACME",
        window_start=NOW - timedelta(hours=1),
        window_end=NOW,
        observed_at=NOW,
        baseline_ref=baseline,
        value_ref=value,
        text="Observed move; cause unconfirmed.",
        refs=(baseline, value),
    )
    assert reaction.attribution == "coincidence_only"
    with pytest.raises(ValidationError):
        ReactionContext.model_validate(
            {**reaction.model_dump(), "window_start": NOW + timedelta(hours=1)}
        )


def test_role_chunks_must_match_source_and_metadata_ignores_secrets() -> None:
    evidence = make_evidence_document(
        source_name="official", title="Acme", published_at=NOW, received_at=NOW
    )
    with pytest.raises(ValueError, match="exact source locator"):
        make_event_context_document(evidence, role_chunks=(("meaning", "fake", "title:0:4"),))
    converted = make_event_context_document(
        evidence, metadata={"API_KEY": "PRIVATE_SENTINEL", "fact_metric": "revenue"}
    )
    assert "PRIVATE_SENTINEL" not in converted.model_dump_json()
    assert "fact_metric" in converted.chunks[-1].text
    assert (
        hashlib.sha256(converted.chunks[-1].text.encode()).hexdigest()
        == converted.chunks[-1].text_sha256
    )


def test_diagnostics_are_closed_and_never_raw_model_text() -> None:
    with pytest.raises(ValidationError):
        ContextDiagnostic.model_validate(
            dict(field="source raw text", rule_code="new error", attempt=1)
        )


def test_schema_policy_preserves_legacy_default_and_denies_unready_v3() -> None:
    policy = EventGenerationPolicy.from_env({})
    assert policy.document_schema == 2 and policy.mode == "off"
    assert EventGenerationPolicy(mode="active").for_segment("crypto").mode == "shadow"
    assert EventGenerationPolicy(mode="active").v2_segments == ("domestic-equity", "us-equity")
    with pytest.raises(ValueError, match="u169"):
        EventGenerationPolicy(mode="preview", document_schema=3).validate_capabilities()
    with pytest.raises(ValueError, match="u172"):
        EventGenerationPolicy(mode="active", document_schema=3).validate_capabilities()
    for mode in ("off", "shadow"):
        EventGenerationPolicy(mode=mode, document_schema=3).validate_capabilities()  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EventGenerationPolicy.from_env({"INVESTO_EVENT_DOCUMENT_SCHEMA": "not a schema"})
