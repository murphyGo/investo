"""Explicit schedule permission reaches the shared owner without v1 fallback."""

import hashlib
from dataclasses import replace

import httpx
import pytest
from pydantic import ValidationError
from scripts import probe_dart_preparation as probe

from investo.briefing.event_context import prepare_context_documents
from investo.models.enrichment import DartEnrichmentTrace, DartTransportQualification
from investo.sources._dart_document import SCHEDULE_PARSER_VERSION
from investo.sources._dart_evidence import prepare_dart_item
from tests.unit.orchestrator.test_dart_preparation_probe import install_mock, streamed
from tests.unit.orchestrator.test_dart_preparation_u184 import (
    SECRET,
    listing_case,
    permissions,
    run_case,
)
from tests.unit.sources.test_dart_document_u173 import FILING, NOW, archive_case, item_case
from tests.unit.sources.test_dart_schedule_u173 import FIXTURE


def schedule_permissions():
    policy, qualification, matrix = permissions()
    record = next(row for row in matrix.records if row.source_name == "dart-disclosure")
    record = record.model_copy(update={"parser_version": SCHEDULE_PARSER_VERSION})
    matrix = matrix.model_copy(
        update={
            "records": tuple(
                record if row.source_name == "dart-disclosure" else row for row in matrix.records
            )
        }
    )
    transport = qualification.dart.model_copy(
        update={
            "parser_version": SCHEDULE_PARSER_VERSION,
            "slot_qualification_sha256": hashlib.sha256(
                matrix.model_dump_json().encode()
            ).hexdigest(),
        }
    )
    qualification = qualification.model_copy(update={"dart": transport})
    return replace(policy, qualification_sha256=qualification.policy_hash), qualification, matrix


def schedule_handler(seen, *, remark="코", price_form=False):
    def respond(request):
        seen.append(request)
        if request.url.path == "/api/list.json":
            return httpx.Response(200, json=listing_case(rm=remark))
        return httpx.Response(
            200, content=archive_case(None if price_form else FIXTURE.read_text())
        )

    return respond


async def test_explicit_schedule_permission_reaches_shared_native_context(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = schedule_permissions()
    seen = []
    result = await run_case(
        schedule_handler(seen), policy=policy, qualification=qualification, matrix=matrix
    )
    assert result.request_count == len(seen) == 2
    assert not result.items[0].event_input_blocked
    outcome = result.outcomes[0]
    assert outcome.status == "enriched" and outcome.dart.parser_version == SCHEDULE_PARSER_VERSION
    (native,) = prepare_context_documents(result.items, received_at=NOW, article_passages=True)
    assert (
        outcome.dart.native_context_sha256
        == hashlib.sha256(native.model_dump_json().encode()).hexdigest()
    )
    assert "PYM_DT_before" in result.items[0].event_evidence.detail_excerpt
    assert "PYM_DT_after" in result.items[0].event_evidence.detail_excerpt


@pytest.mark.parametrize("profile", ["price", "schedule"])
async def test_wrong_form_never_falls_back_to_another_parser(monkeypatch, profile):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    policy, qualification, matrix = (
        schedule_permissions() if profile == "schedule" else permissions()
    )
    seen = []
    result = await run_case(
        schedule_handler(seen, price_form=profile == "schedule"),
        policy=policy,
        qualification=qualification,
        matrix=matrix,
    )
    assert len(seen) == 2 and result.items[0].event_input_blocked
    assert result.outcomes[0].reason == "evidence_invalid"
    assert result.outcomes[0].dart.parser_version == qualification.dart.parser_version


async def test_schedule_matrix_cannot_authorize_price_transport_or_reverse(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    p, q, m = permissions()
    sp, sq, sm = schedule_permissions()
    for policy, qualification, matrix in [(p, q, sm), (sp, sq, m)]:
        result = await run_case(
            lambda request: pytest.fail("unqualified HTTP"),
            policy=policy,
            qualification=qualification,
            matrix=matrix,
        )
        assert result.request_count == 0 and result.outcomes[0].reason == "unqualified"


@pytest.mark.parametrize("remark", ["정", "철", "?"])
async def test_schedule_latest_status_blocks_before_xml(monkeypatch, remark):
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)
    p, q, m = schedule_permissions()
    seen = []
    result = await run_case(
        schedule_handler(seen, remark=remark), policy=p, qualification=q, matrix=m
    )
    assert len(seen) == 1 and result.items[0].event_input_blocked
    assert result.outcomes[0].dart.parser_version == SCHEDULE_PARSER_VERSION


def test_transport_and_trace_support_only_two_explicit_versions():
    _, qualification, _ = permissions()
    for version in ("auto", "dart-cb-schedule-6.4-v2", "SYNTHETIC_SECRET"):
        with pytest.raises(ValidationError):
            DartTransportQualification.model_validate(
                {**qualification.dart.model_dump(), "parser_version": version}
            )
        with pytest.raises(ValidationError):
            DartEnrichmentTrace(parser_version=version)


async def test_internal_unknown_parser_does_not_spend_http():
    async def forbidden(*args):
        pytest.fail("unsupported parser opened HTTP")

    item, reason, trace = await prepare_dart_item(
        item_case(), forbidden, forbidden_token=b"", parser_version="unknown"
    )
    assert item.event_input_blocked and reason == "parser_unsupported" and trace.requests == 0


async def test_schedule_probe_uses_selected_matrix_and_never_publishes(monkeypatch):
    _, qualification, matrix = schedule_permissions()
    loaded = []

    def load_policy(path):
        loaded.append(path.name)
        return qualification

    def load_matrix(path):
        loaded.append(path.name)
        return matrix

    monkeypatch.setattr(probe, "load_enrichment_qualification", load_policy)
    monkeypatch.setattr(probe, "load_source_slot_qualification", load_matrix)

    def respond(request):
        if request.url.path == "/api/document.xml":
            return streamed(archive_case(FIXTURE.read_text()))
        return streamed(listing_case())

    install_mock(monkeypatch, respond)
    manifest, files = await probe.rehearse(
        filing=FILING, corp="00000001", credential=SECRET, parser_profile="schedule"
    )
    assert loaded == [
        "event_dart_schedule_preview_qualification.json",
        "event_dart_schedule_slot_qualification.json",
    ]
    assert manifest["status"] == "completed" and manifest["request_count"] == 3
    assert manifest["enriched_count"] == manifest["native_context_count"] == 1
    assert manifest["parser_profile"] == "schedule" and len(files) == 4
    assert not any(
        manifest[k]
        for k in (
            "model_call_count",
            "runtime_qualified",
            "activation_ready",
            "publication_committed",
            "notification_sent",
        )
    )


async def test_probe_profile_mismatch_is_rejected_before_collection(monkeypatch):
    _, qualification, matrix = permissions()
    monkeypatch.setattr(probe, "load_enrichment_qualification", lambda path: qualification)
    monkeypatch.setattr(probe, "load_source_slot_qualification", lambda path: matrix)
    install_mock(monkeypatch, lambda request: pytest.fail("profile mismatch opened HTTP"))
    manifest, files = await probe.rehearse(
        filing=FILING, corp="00000001", credential=SECRET, parser_profile="schedule"
    )
    assert not files and manifest["request_count"] == 0
    assert manifest["reason"] == "qualification_invalid"
