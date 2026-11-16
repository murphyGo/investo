"""Slot evidence remains independent from body permissions and live recovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from investo.models.enrichment import (
    SLOT_REQUIRED_FIELDS,
    EndpointScope,
    SourceQualification,
    SourceSlotQualification,
    SourceSlotQualificationSet,
)
from investo.sources.event_evidence import load_source_slot_qualification
from tests._helpers.event_context_v3 import NOW


def blocked(slot="policy.monetary_decision", source="fomc-rss"):
    return SourceSlotQualification(
        source_name=source,
        slot_id=slot,
        access_kind="official_body",
        checked_at=NOW,
        source_code_sha="a" * 40,
        status="blocked",
        reason_codes=("access.not_verified",),
        required_slots=SLOT_REQUIRED_FIELDS[slot],
        missing_slots=SLOT_REQUIRED_FIELDS[slot],
    )


@pytest.mark.parametrize("slot", tuple(SLOT_REQUIRED_FIELDS))
def test_all_named_slots_allow_honest_unknown_evidence(slot):
    row = blocked(slot)
    assert row.status == "blocked" and row.activation_ready is False
    assert row.runtime_probe_status == "not_run"
    assert row.missing_slots == row.required_slots
    assert row.endpoint_scope is None


@pytest.mark.parametrize(
    "patch",
    [
        {"status": "verified"},
        {"reason_codes": ()},
        {"required_slots": (), "missing_slots": ()},
        {"activation_ready": True},
        {"source_name": None},
        {"proposed_source_name": "new-source"},
        {"runtime_probe_status": "verified"},
        {"source_code_sha": "main"},
        {"official_discovery_url": "https://127.0.0.1/private"},
        {"reason_codes": ("raw error containing private data",)},
    ],
)
def test_forged_or_unbound_evidence_is_rejected(patch):
    with pytest.raises(ValidationError):
        SourceSlotQualification.model_validate({**blocked().model_dump(), **patch})


@pytest.mark.parametrize(
    "host,path",
    [
        ("127.0.0.1", "/"),
        ("localhost", "/"),
        ("service.internal", "/"),
        ("federalreserve.gov", "/a/%2e%2e/private"),
        ("federalreserve.gov", "//private"),
        ("user@federalreserve.gov", "/"),
    ],
)
def test_scope_cannot_be_a_private_or_escaped_endpoint(host, path):
    with pytest.raises(ValidationError):
        EndpointScope(host=host, path_prefix=path)


def test_duplicate_matrix_and_source_masquerade_fail(tmp_path: Path):
    row = blocked()
    with pytest.raises(ValidationError):
        SourceSlotQualificationSet(records=(row, row))
    path = tmp_path / "matrix.json"
    path.write_text(
        SourceSlotQualificationSet(records=(blocked(source="unknown-source"),)).model_dump_json()
    )
    with pytest.raises(ValueError, match="qualification unavailable"):
        load_source_slot_qualification(path)
    path.write_bytes(b"x" * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="qualification unavailable"):
        load_source_slot_qualification(path)


def test_current_matrix_keeps_scoped_board_and_historical_dart_facts_inactive():
    from investo.models.enrichment import EVENT_ENRICHMENT_ACTIVE_READY

    path = Path(__file__).resolve().parents[3] / "ops/event_source_slot_qualification.json"
    result = load_source_slot_qualification(path)
    assert len(result.records) == 8
    assert {r.slot_id for r in result.records} == set(SLOT_REQUIRED_FIELDS)
    assert {r.source_name for r in result.records if r.status == "verified"} == {
        "fomc-rss",
        "fed-speech-rss",
        "dart-disclosure",
    }
    assert all(
        not r.activation_ready and r.runtime_probe_status == "not_run" for r in result.records
    )
    dart = next(row for row in result.records if row.source_name == "dart-disclosure")
    assert dart.parser_version == "dart-cb-correction-6.4-v1"
    assert dart.verified_slots == dart.required_slots and not dart.missing_slots
    assert "historical" in dart.rights_scope and "completion" in dart.rights_scope
    assert EVENT_ENRICHMENT_ACTIVE_READY is False


def test_dart_viewer_identity_metadata_does_not_grant_live_body_permission():
    from investo._internal.source_specs import SOURCE_SPECS_BY_NAME

    assert SOURCE_SPECS_BY_NAME["dart-disclosure"].evidence_domains == frozenset({"dart.fss.or.kr"})
    with pytest.raises(ValidationError) as caught:
        SourceQualification(
            source_name="dart-disclosure",  # type: ignore[arg-type]
            checked_at=NOW,
            official_discovery_url="https://dart.fss.or.kr/dsaf001/main.do",
            allowed_host="dart.fss.or.kr",
            allowed_path="/dsaf001/",
            content_type="text/html",
            public_rights_basis="synthetic identity permission is not a body qualification",
            extraction_selector_version="fed-article-body-v1",
            fixture_sha256="a" * 64,
            status="qualified",
            reason="synthetic rejected request",
        )
    assert any(error["loc"] == ("source_name",) for error in caught.value.errors())


@pytest.mark.parametrize(
    "host,path",
    [("opendart.fss.or.kr", "/api/document.xml"), ("foreign.example", "/dsaf001/main.do")],
)
def test_dart_slot_loader_accepts_only_qualified_viewer_provenance(tmp_path, host, path):
    manifest = Path(__file__).resolve().parents[3] / "ops/event_source_slot_qualification.json"
    matrix = load_source_slot_qualification(manifest)
    records = tuple(
        row.model_copy(
            update={
                "endpoint_scope": EndpointScope(host=host, path_prefix=path),
                "official_discovery_url": f"https://{host}{path}",
            }
        )
        if row.source_name == "dart-disclosure"
        else row
        for row in matrix.records
    )
    target = tmp_path / "foreign-provenance.json"
    target.write_text(matrix.model_copy(update={"records": records}).model_dump_json())
    with pytest.raises(ValueError, match="qualification unavailable"):
        load_source_slot_qualification(target)
