"""Synthetic, independently valued trust termination form and closed transport."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from investo._internal.event_context import resolve_context_ref
from investo.sources._dart_document import DartDocumentError
from investo.sources._dart_evidence import (
    DartRequestError,
    DartResponse,
    dart_identity,
    dart_runtime_evidence,
    prepare_dart_item,
)
from investo.sources._dart_trust_document import (
    _FIELDS,
    PARSER_VERSION,
    REPORT_NAME,
    parse_dart_trust_document,
)
from investo.sources.event_evidence import _candidates
from tests.unit.sources.test_dart_document_u173 import archive_case, item_case
from tests.unit.sources.test_dart_schedule_u173 import check_bindings

FIXTURE = Path(__file__).parents[2] / "fixtures/dart_document/trust-termination-6.2.xml"
FILING = "20261123000001"
NOW = datetime(2026, 11, 23, 7, tzinfo=UTC)


def trust_item(**changes):
    return item_case(report_nm=REPORT_NAME, rcept_no=FILING, rcept_dt="20261123", **changes)


def parse(text=None, **changes):
    data = archive_case(text or FIXTURE.read_text(), name=FILING + ".xml")
    kwargs = dict(response_sha256=hashlib.sha256(data).hexdigest(), received_at=NOW)
    kwargs.update(changes)
    return parse_dart_trust_document(trust_item(), data, **kwargs)


def test_literal_decision_terms_and_scheduled_custody_survive_native_refs():
    original = trust_item().model_dump_json()
    parsed = parse()
    check_bindings(FIXTURE.read_text(), parsed)
    native = dart_runtime_evidence(parsed)
    assert set(native.field_refs) == {
        "issuer",
        "action",
        "action_status",
        "action_terms",
        "filing_locator",
    }
    assert max(map(len, native.field_refs.values())) <= 16
    assert parsed.parser_version == PARSER_VERSION
    assert native.context.time.occurred_at.precision == "unknown"
    assert native.context.time.published_at.precision == "date"
    assert native.item.event_evidence.evidence_budget_limited
    assert len(native.item.event_evidence.detail_excerpt) <= 1200
    for slot, refs in native.field_refs.items():
        assert [resolve_context_ref(ref, (native.context,)) for ref in refs] == [
            resolve_context_ref(ref, (parsed.context,)) for ref in parsed.field_refs[slot]
        ]
    text = native.item.event_evidence.detail_excerpt
    assert "해지 후" in text and "CLN_PRC_AFT: -" in text
    assert "300,000,000" in text and "20,000" in text
    assert "입고될 예정" in text and "해지예정주식(주)" in text
    assert "소각" not in text and "별도 보유" not in text and "해지 완료" not in text
    assert trust_item().model_dump_json() == original


@pytest.mark.parametrize(
    "old,new",
    [
        ('ACODE="11335"', 'ACODE="11334"'),
        (">6.2<", ">6.3<"),
        ('ADATE="20260723"', 'ADATE="20260724"'),
        ('AREGCIK="00000001"', 'AREGCIK="00000002"'),
        ("주식회사 가람상사", "주식회사 다른회사"),
        (">자기주식취득 신탁계약 해지 결정<", ">자기주식취득 신탁계약 해지 완료<"),
        ("1. 계약금액(원)", "1. 계약금액(백만원)"),
        (">해지 전<", ">해지 후<"),
        (">시작일<", ">종료일<"),
        ("8. 해지예정주식(주)", "8. 소각예정주식(주)"),
        ("5. 해지예정일자", "5. 해지완료일자"),
        ("300,000,000", "300,00,000"),
        ("300,000,000", "-"),
        ("300,000,000", "-300"),
        ('AUNITVALUE="20261124"', 'AUNITVALUE="20261125"'),
        ("2026년 11월 24일", "2026년 02월 30일"),
        ('AUNITVALUE="20261124"', 'AUNITVALUE="20261122"'),
        ('ROWSPAN="2"', 'ROWSPAN="3"'),
        ('COLSPAN="3"', 'COLSPAN="4"'),
        ("</DOCUMENT>", "<CORRECTION/></DOCUMENT>"),
        ("TBL_OWN_STK", "OTHER_TABLE"),
    ],
)
def test_changed_schema_units_status_dates_and_ownership_fail_closed(old, new):
    text = FIXTURE.read_text()
    assert old in text
    with pytest.raises(DartDocumentError, match=r"^dart\."):
        parse(text.replace(old, new))


@pytest.mark.parametrize("code", list(_FIELDS))
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "moved"])
def test_all_field_codes_are_unique_and_belong_to_their_table_row(code, mutation):
    text = FIXTURE.read_text()
    _, tag, _, _ = _FIELDS[code]
    attr = "ACODE" if tag == "TE" else "AUNIT"
    start = text.index(f'<{tag} {attr}="{code}"')
    end = text.index(f"</{tag}>", start) + len(f"</{tag}>")
    field = text[start:end]
    text = text.replace(field, field + field if mutation == "duplicate" else "")
    if mutation == "moved":
        text = text.replace("</DOCUMENT>", field + "</DOCUMENT>")
    with pytest.raises(DartDocumentError, match=r"^dart\."):
        parse(text)


@pytest.mark.parametrize("value", ["0", "1,000"])
def test_after_amount_and_other_share_values_remain_literal(value):
    text = FIXTURE.read_text().replace(
        'ACODE="CLN_PRC_AFT" COLSPAN="3">-', f'ACODE="CLN_PRC_AFT" COLSPAN="3">{value}'
    )
    result = parse(text)
    assert f"CLN_PRC_AFT: {value}" in result.item.event_evidence.detail_excerpt


def test_secret_xml_attack_wrong_clock_digest_and_budget_are_rejected():
    text = FIXTURE.read_text()
    for changed, kwargs in (
        (text.replace("가상증권", "SECRET_KEY"), {"forbidden_token": b"SECRET_KEY"}),
        (text.replace("가상증권", "&#83;ECRET_KEY"), {"forbidden_token": b"SECRET_KEY"}),
        (text.replace("<DOCUMENT>", '<!DOCTYPE DOCUMENT [<!ENTITY a "hidden">]><DOCUMENT>'), {}),
        (text.replace("가상증권", "가" * 241), {}),
        (text, {"received_at": NOW - timedelta(days=1)}),
        (text, {"response_sha256": "f" * 64}),
    ):
        with pytest.raises(DartDocumentError, match=r"^dart\."):
            parse(changed, **kwargs)


def test_explicit_profile_identity_and_quota_have_no_fallback():
    item = trust_item()
    assert dart_identity(item, PARSER_VERSION) == (FILING, "00000001")
    with pytest.raises(DartRequestError):
        dart_identity(item)
    with pytest.raises(DartRequestError):
        dart_identity(item_case(), PARSER_VERSION)
    candidates = _candidates(
        [item_case(), item], 1, {}, include_dart=True, dart_parser_version=PARSER_VERSION
    )
    assert len(candidates) == 1 and candidates[0].item == item


async def test_shared_preparation_preserves_latest_check_and_native_slots():
    item = trust_item()
    entry = {
        k: v
        for k, v in item.raw_metadata.items()
        if k
        not in {
            "subcategory",
            "published_at_precision",
            "published_date",
            "published_timezone",
            "event_date",
            "event_time_basis",
        }
    }
    listing = json.dumps(
        {
            "status": "000",
            "total_count": 1,
            "total_page": 1,
            "page_no": 1,
            "page_count": 100,
            "list": [{**entry, "rm": "코"}],
        }
    ).encode()
    data = archive_case(FIXTURE.read_text(), name=FILING + ".xml")
    calls = []

    async def request(kind, params):
        calls.append((kind, params))
        return DartResponse(listing if kind == "listing" else data, NOW)

    prepared, reason, trace = await prepare_dart_item(
        item, request, forbidden_token=b"", parser_version=PARSER_VERSION
    )
    assert reason is None and not prepared.event_input_blocked
    assert trace.requests == 2 and trace.latest_status == "as_observed"
    assert calls[0][1]["last_reprt_at"] == "Y"
    assert calls[1][1] == {"rcept_no": FILING}
    assert prepared.event_evidence is not None


async def test_default_parser_blocks_trust_without_http():
    async def request(*args):
        pytest.fail("unsupported form reached HTTP")

    item, reason, trace = await prepare_dart_item(trust_item(), request, forbidden_token=b"")
    assert item.event_input_blocked and reason == "parser_unsupported" and trace.requests == 0


@pytest.mark.parametrize("remark", ["정", "철", "?"])
async def test_changed_or_ambiguous_latest_entry_blocks_before_document(remark):
    item = trust_item()
    calls = []

    async def request(kind, params):
        calls.append(kind)
        entry = {**item.raw_metadata, "rm": remark}
        return DartResponse(
            json.dumps(
                {
                    "status": "000",
                    "total_page": 1,
                    "page_no": 1,
                    "page_count": 100,
                    "total_count": 1,
                    "list": [entry],
                }
            ).encode(),
            NOW,
        )

    prepared, reason, trace = await prepare_dart_item(
        item, request, forbidden_token=b"", parser_version=PARSER_VERSION
    )
    assert calls == ["listing"] and prepared.event_input_blocked
    assert reason in {"superseded", "withdrawn", "latest_unavailable"} and trace.requests == 1


def test_matching_date_literals_cannot_hide_reversed_period_or_past_termination():
    text = FIXTURE.read_text()
    for old, new in (("20270410", "20260410"), ("20261124", "20261122")):
        changed = text.replace(old, new).replace(
            f"{old[:4]}년 {old[4:6]}월 {old[6:]}일", f"{new[:4]}년 {new[4:6]}월 {new[6:]}일"
        )
        with pytest.raises(DartDocumentError):
            parse(changed)


def test_value_duplicate_with_wrong_attribute_is_ambiguous():
    text = FIXTURE.read_text().replace(
        "</DOCUMENT>", '<P AUNIT="CLN_PRC_PRE">different table</P></DOCUMENT>'
    )
    with pytest.raises(DartDocumentError):
        parse(text)


@pytest.mark.parametrize("value", ["20261010", "20270410", "20261124", "20261123"])
def test_machine_date_is_mandatory_for_each_tu(value):
    with pytest.raises(DartDocumentError):
        parse(FIXTURE.read_text().replace(f' AUNITVALUE="{value}"', ""))
