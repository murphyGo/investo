"""Public endpoint scopes and source slots use actual independently owned spans."""

import pytest

from investo.models.enrichment import SLOT_REQUIRED_FIELDS, EndpointScope, SourceSlotQualification
from investo.models.event_evidence import evidence_document_from_item, make_event_context_document
from investo.models.items import NormalizedItem
from investo.sources.event_evidence import map_source_slot_context
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
