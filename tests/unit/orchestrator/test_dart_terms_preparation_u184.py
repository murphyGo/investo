"""Explicit v2 grants must survive the same owner and real native factory."""

import hashlib
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from investo.briefing.event_context import prepare_context_documents
from investo.models.enrichment import (
    DartTransportQualification,
    EnrichmentPolicy,
    EnrichmentQualification,
    SourceSlotParserCapture,
    SourceSlotParserSample,
    SourceSlotQualificationSet,
)
from investo.orchestrator.event_evidence import prepare_event_evidence
from investo.sources._dart_terms_document import PARSER_VERSION, parse_dart_terms_document
from investo.sources.event_evidence import (
    load_enrichment_qualification,
    load_source_slot_qualification,
    map_source_slot_context,
    replay_source_slot_capture,
)
from tests.unit.orchestrator.test_dart_preparation_u184 import SECRET, listing_case
from tests.unit.sources.test_dart_document_u173 import NOW, archive_case, item_case
from tests.unit.sources.test_dart_terms_document_u173 import FILING, FIXTURE, parse_case

ROOT = Path(__file__).parents[3]


def permissions():
    original = load_source_slot_qualification(ROOT / "ops/event_source_slot_qualification.json")
    row = next(row for row in original.records if row.source_name == "dart-disclosure")
    parsed = parse_case()
    row = row.model_copy(
        update={
            "parser_version": PARSER_VERSION,
            "source_code_sha": "1" * 40,
            "schema_fixture_sha256": hashlib.sha256(
                parsed.context.model_dump_json().encode()
            ).hexdigest(),
            "context_contract_version": 2,
            "rights_scope": "Synthetic v2 tests only.",
        }
    )
    matrix = SourceSlotQualificationSet(records=(row,))
    record = DartTransportQualification(
        status="approved",
        checked_at=NOW,
        parser_version=PARSER_VERSION,
        projection_version="dart-field-paragraph-v2",
        max_projection_chars=3600,
        slot_qualification_sha256=hashlib.sha256(matrix.model_dump_json().encode()).hexdigest(),
        source_code_sha=row.source_code_sha,
        fixture_sha256=row.schema_fixture_sha256,
        rights_scope=row.rights_scope,
        private_retention_basis="Synthetic private v2 test.",
    )
    qualification = EnrichmentQualification(dart=record)
    policy = EnrichmentPolicy(
        mode="preview",
        article_passages=True,
        max_excerpt_chars=3600,
        preview_sources=("dart-disclosure",),
        qualification_sha256=qualification.policy_hash,
    )
    return policy, qualification, matrix


async def run_case(handler, *, policy=None, qualification=None, matrix=None, item=None):
    defaults = permissions()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await prepare_event_evidence(
            (item or item_case(rcept_no=FILING, rcept_dt=FILING[:8]),),
            (),
            policy=policy or defaults[0],
            qualification=qualification or defaults[1],
            slot_qualification=matrix or defaults[2],
            received_at=NOW,
            client=client,
        )


async def test_explicit_v2_shared_owner_keeps_all_native_paragraphs_and_actual_clock(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    item = item_case(rcept_no=FILING, rcept_dt=FILING[:8])
    raw = archive_case(FIXTURE.read_bytes(), name=FILING + ".xml")
    requests = []

    def handler(request):
        requests.append(request)
        return (
            httpx.Response(200, json=listing_case(item))
            if request.url.path.endswith("list.json")
            else httpx.Response(200, content=raw)
        )

    result = await run_case(handler)
    assert result.request_count == len(requests) == 2
    trace = result.outcomes[0].dart
    assert result.outcomes[0].status == "enriched" and trace.parser_version == PARSER_VERSION
    assert not result.items[0].event_input_blocked
    parsed = parse_dart_terms_document(
        item,
        raw,
        response_sha256=hashlib.sha256(raw).hexdigest(),
        received_at=trace.document_received_at,
    )
    native = prepare_context_documents(result.items, received_at=NOW, article_passages=True)
    assert len(native) == 1 and native[0].model_dump_json() == parsed.context.model_dump_json()
    assert (
        trace.native_context_sha256
        == hashlib.sha256(native[0].model_dump_json().encode()).hexdigest()
    )
    assert trace.native_context_sha256 != permissions()[1].dart.fixture_sha256
    assert len(result.items[0].event_evidence.detail_excerpt.splitlines()) > 1
    assert all(SECRET not in value.model_dump_json() for value in result.items)


def test_variant_capture_reuses_generic_native_contract_without_changing_legacy_hashes():
    _, _, matrix = permissions()
    parsed = parse_case()
    context = map_source_slot_context(
        parsed.item, matrix.records[0], received_at=NOW, field_refs=parsed.field_refs
    )
    assert context.model_dump_json() == parsed.context.model_dump_json()
    digest = hashlib.sha256(matrix.model_dump_json().encode()).hexdigest()
    capture = SourceSlotParserCapture(
        qualification_sha256=digest,
        samples=(
            SourceSlotParserSample(
                slot_id="domestic.disclosure_action",
                item=parsed.item,
                received_at=NOW,
                context_sha256=matrix.records[0].schema_fixture_sha256,
                field_refs=parsed.field_refs,
            ),
        ),
    )
    assert replay_source_slot_capture(capture, matrix, qualification_sha256=digest) == (
        ("dart-disclosure", "domestic.disclosure_action", 5),
    )
    canonical = load_source_slot_qualification(ROOT / "ops/event_source_slot_qualification.json")
    assert (
        hashlib.sha256(canonical.model_dump_json().encode()).hexdigest()
        == "8b8d0d64f956a31212647b5616b4d8c071becfdcb3b92d91f25cb7fddde9787c"
    )
    assert all("context_contract_version" not in row.model_dump() for row in canonical.records)
    assert (
        load_enrichment_qualification(
            ROOT / "ops/event_dart_preview_qualification.json"
        ).policy_hash
        == "28190c88280f3b0da9f3c547fdfaeb4f1e7c5c7f9bcf57792b4bdd84773d2f51"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("projection_version", "dart-field-paragraph-v1"),
        ("parser_version", "unknown"),
        ("slot_qualification_sha256", "0" * 64),
    ],
)
async def test_forged_v2_grants_are_closed_before_http(monkeypatch, field, value):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions()
    qualification = qualification.model_copy(
        update={"dart": qualification.dart.model_copy(update={field: value})}
    )
    policy = replace(policy, qualification_sha256=qualification.policy_hash)

    def forbidden(request):
        pytest.fail("unapproved v2 opened HTTP")

    result = await run_case(forbidden, policy=policy, qualification=qualification, matrix=matrix)
    assert result.request_count == 0 and result.items[0].event_input_blocked


async def test_old_context_contract_cannot_authorize_v2(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions()
    matrix = matrix.model_copy(
        update={"records": (matrix.records[0].model_copy(update={"context_contract_version": 1}),)}
    )
    qualification = qualification.model_copy(
        update={
            "dart": qualification.dart.model_copy(
                update={
                    "slot_qualification_sha256": hashlib.sha256(
                        matrix.model_dump_json().encode()
                    ).hexdigest()
                }
            )
        }
    )
    policy = replace(policy, qualification_sha256=qualification.policy_hash)

    def forbidden(request):
        pytest.fail("wrong context contract opened HTTP")

    result = await run_case(forbidden, policy=policy, qualification=qualification, matrix=matrix)
    assert result.request_count == 0 and result.items[0].event_input_blocked


def test_v1_caps_cannot_expand_and_v2_requires_named_projection():
    record = permissions()[1].dart.model_dump()
    for updates in [
        dict(parser_version="dart-cb-correction-6.4-v1"),
        dict(projection_version="dart-field-paragraph-v1"),
        dict(max_projection_chars=3601),
    ]:
        with pytest.raises(ValidationError):
            DartTransportQualification.model_validate({**record, **updates})


async def test_v2_does_not_fall_back_to_valid_v1_form(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    item = item_case()
    raw = archive_case()

    def handler(request):
        return (
            httpx.Response(200, json=listing_case(item))
            if request.url.path.endswith("list.json")
            else httpx.Response(200, content=raw)
        )

    result = await run_case(handler, item=item)
    assert result.request_count == 2 and result.items[0].event_input_blocked
    assert result.outcomes[0].dart.parser_version == PARSER_VERSION
    assert result.outcomes[0].status == "enrichment_unavailable"


async def test_cap_rejects_whole_v2_projection_without_truncation(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = permissions()
    policy = replace(policy, max_excerpt_chars=1200)
    item = item_case(rcept_no=FILING, rcept_dt=FILING[:8])

    def handler(request):
        return (
            httpx.Response(200, json=listing_case(item))
            if request.url.path.endswith("list.json")
            else httpx.Response(
                200, content=archive_case(FIXTURE.read_bytes(), name=FILING + ".xml")
            )
        )

    result = await run_case(handler, policy=policy, qualification=qualification, matrix=matrix)
    assert result.request_count == 2 and result.items[0].event_input_blocked
    assert result.items[0].event_evidence is None


def test_preview_v2_requires_explicit_native_official_dart_selection():
    from scripts.preview_event_briefing import PreviewInputError, _parse_args

    base = [
        "--target-date",
        "2026-09-03",
        "--segment",
        "domestic-equity",
        "--output-dir",
        ".tmp/v2",
        "--document-schema",
        "3",
        "--article-profile",
        "article_v2",
        "--dart-parser-version",
        "v2",
    ]
    with pytest.raises(PreviewInputError):
        _parse_args(base)
    args = _parse_args([*base, "--official-body-preview", "--dart-body-preview"])
    assert args.dart_parser_version == "v2"
