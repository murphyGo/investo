"""Public endpoint scopes and source slots use actual independently owned spans."""

import hashlib
import subprocess

import pytest

from investo.models.enrichment import (
    SLOT_REQUIRED_FIELDS,
    EndpointScope,
    SourceSlotParserCapture,
    SourceSlotParserSample,
    SourceSlotQualification,
    SourceSlotQualificationSet,
)
from investo.models.event_evidence import evidence_document_from_item, make_event_context_document
from investo.models.items import NormalizedItem
from investo.sources.event_evidence import map_source_slot_context, replay_source_slot_capture
from tests._helpers.event_context_v3 import NOW, ref


def slot_case(url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"):
    required = SLOT_REQUIRED_FIELDS["earnings.reported_actual"]
    row = SourceSlotQualification(
        source_name="sec-company-facts",
        slot_id="earnings.reported_actual",
        access_kind="structured_api",
        endpoint_scope=EndpointScope(host="data.sec.gov", path_prefix="/api/xbrl/companyfacts/"),
        official_discovery_url="https://data.sec.gov/api/xbrl/companyfacts/",
        checked_at=NOW,
        source_code_sha="a" * 40,
        status="verified",
        reason_codes=("time.unknown", "runtime.not_verified"),
        access_evidence_hash="b" * 64,
        rights_evidence_url="https://www.sec.gov/files/about/webmaster-faq.htm",
        rights_scope="synthetic fixture only",
        schema_fixture_sha256="c" * 64,
        parser_version="synthetic-v1",
        required_slots=required,
        verified_slots=required,
        missing_slots=(),
        chunk_roles=("identity", "fact"),
        public_locator_basis="filing_locator",
    )
    item = NormalizedItem(
        source_name="sec-company-facts",
        category="news",
        title="Acme",
        summary="Acme revenue actual 1200 USD FY2026 0000000001-26-000001",
        url=url,
        published_at=NOW,
    )
    doc = make_event_context_document(
        evidence_document_from_item(item, received_at=NOW), metadata=item.raw_metadata, item=item
    )
    fields = {
        key: (ref(doc, value),)
        for key, value in dict(
            issuer="Acme",
            metric="revenue",
            actual_value="1200",
            unit="USD",
            period="FY2026",
            filing_locator="0000000001-26-000001",
        ).items()
    }
    return item, row, fields


def test_all_required_slots_are_source_owned_with_unknown_time_preserved():
    item, row, fields = slot_case()
    result = map_source_slot_context(item, row, received_at=NOW, field_refs=fields)
    assert result.time.occurred_at.precision == "unknown"
    assert row.activation_ready is False


@pytest.mark.parametrize(
    "url",
    [
        "https://data.sec.gov:444/api/xbrl/companyfacts/CIK0000000001.json",
        "https://:SYNTHETIC@data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json",
        "https://data.sec.gov/api/xbrl/companyfacts/%252e%252e/private.json",
        "https://data.sec.gov/api/xbrl/companyfacts/file.json?unqualified=1",
        "https://data.sec.gov/not-qualified/file.json",
    ],
    ids=["port", "credentials", "encoded-escape", "query", "path"],
)
def test_lookalike_or_escaped_locator_is_not_qualified(url):
    with pytest.raises(ValueError):
        item, row, fields = slot_case(url)
        map_source_slot_context(item, row, received_at=NOW, field_refs=fields)


def test_reusing_title_for_all_fields_and_missing_fields_are_not_complete():
    item, row, fields = slot_case()
    with pytest.raises(ValueError, match=r"slot.required_missing"):
        map_source_slot_context(
            item, row, received_at=NOW, field_refs={f: fields["issuer"] for f in fields}
        )
    with pytest.raises(ValueError, match=r"slot.required_missing"):
        map_source_slot_context(
            item,
            row,
            received_at=NOW,
            field_refs={f: r for f, r in fields.items() if f != "period"},
        )


def parser_capture_case():
    item, row, fields = slot_case()
    document = map_source_slot_context(item, row, received_at=NOW, field_refs=fields)
    row = row.model_copy(
        update={
            "schema_fixture_sha256": hashlib.sha256(document.model_dump_json().encode()).hexdigest()
        }
    )
    matrix = SourceSlotQualificationSet(records=(row,))
    policy_hash = hashlib.sha256(matrix.model_dump_json().encode()).hexdigest()
    sample = SourceSlotParserSample(
        slot_id=row.slot_id,
        item=item,
        received_at=NOW,
        context_sha256=hashlib.sha256(document.model_dump_json().encode()).hexdigest(),
        field_refs=fields,
    )
    return SourceSlotParserCapture(qualification_sha256=policy_hash, samples=(sample,)), matrix


def test_private_parser_capture_replays_exact_fields_without_runtime_promotion():
    capture, matrix = parser_capture_case()
    result = replay_source_slot_capture(
        capture, matrix, qualification_sha256=capture.qualification_sha256
    )
    assert result == (("sec-company-facts", "earnings.reported_actual", 6),)
    assert matrix.records[0].runtime_probe_status == "not_run"
    assert matrix.records[0].activation_ready is False


@pytest.mark.parametrize(
    "change", ["policy", "context", "foreign_refs", "missing_field", "blocked"]
)
def test_stale_or_forged_parser_capture_is_rejected(change):
    capture, matrix = parser_capture_case()
    sample = capture.samples[0]
    policy = capture.qualification_sha256
    if change == "policy":
        policy = "d" * 64
    elif change == "context":
        sample = sample.model_copy(update={"context_sha256": "d" * 64})
    elif change == "foreign_refs":
        fields = dict(sample.field_refs)
        fields["metric"] = (fields["metric"][0].model_copy(update={"revision_id": "d" * 64}),)
        sample = sample.model_copy(update={"field_refs": fields})
    elif change == "missing_field":
        sample = sample.model_copy(
            update={"field_refs": {k: v for k, v in sample.field_refs.items() if k != "period"}}
        )
    else:
        row = matrix.records[0].model_copy(
            update={"status": "blocked", "reason_codes": ("access.denied",)}
        )
        matrix = matrix.model_copy(update={"records": (row,)})
    capture = capture.model_copy(update={"samples": (sample,)})
    with pytest.raises(ValueError):
        replay_source_slot_capture(capture, matrix, qualification_sha256=policy)


def test_recomputed_hash_cannot_replace_the_approved_parser_fixture():
    capture, matrix = parser_capture_case()
    sample = capture.samples[0]
    item = sample.item.model_copy(update={"summary": sample.item.summary.replace("1200", "1300")})
    doc = make_event_context_document(
        evidence_document_from_item(item, received_at=NOW), metadata=item.raw_metadata, item=item
    )
    fields = {
        key: (ref(doc, "1300" if key == "actual_value" else value),)
        for key, value in dict(
            issuer="Acme",
            metric="revenue",
            actual_value="1200",
            unit="USD",
            period="FY2026",
            filing_locator="0000000001-26-000001",
        ).items()
    }
    replaced = sample.model_copy(
        update={
            "item": item,
            "field_refs": fields,
            "context_sha256": hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="capture_fixture_mismatch"):
        replay_source_slot_capture(
            capture.model_copy(update={"samples": (replaced,)}),
            matrix,
            qualification_sha256=capture.qualification_sha256,
        )


@pytest.mark.parametrize(
    "change", [None, "public", "mode", "symlink", "symlink_loop", "oversized", "raw_error"]
)
def test_capture_cli_reads_only_bounded_ignored_private_files(tmp_path, monkeypatch, change):
    from scripts import check_event_source_slots as checker

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=5)
    (tmp_path / ".gitignore").write_text("private/\n")
    monkeypatch.setattr(checker, "__file__", str(tmp_path / "scripts/check_event_source_slots.py"))
    capture, matrix = parser_capture_case()
    manifest = tmp_path / "policy.json"
    manifest.write_text(matrix.model_dump_json())
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "capture.json"
    path.write_text(capture.model_dump_json())
    path.chmod(0o600)
    if change == "public":
        path = tmp_path / "public.json"
        path.write_text(capture.model_dump_json())
        path.chmod(0o600)
    elif change == "mode":
        path.chmod(0o644)
    elif change == "symlink":
        path = private / "link.json"
        path.symlink_to(private / "capture.json")
    elif change == "symlink_loop":
        path = private / "loop.json"
        path.symlink_to(path)
    elif change == "oversized":
        path.write_bytes(b"x" * (1024 * 1024 + 1))
    elif change == "raw_error":
        path.write_text('{"private": "PRIVATE_CAPTURE_SENTINEL"}')
    if change is None:
        assert checker.check_private_capture(path, manifest) == (
            ("sec-company-facts", "earnings.reported_actual", 6),
        )
    else:
        with pytest.raises(ValueError):
            checker.check_private_capture(path, manifest)
