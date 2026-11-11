"""Independent synthetic DART form: corrected columns, owners and unsafe XML."""

import hashlib
import io
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from investo._internal.event_context import resolve_context_ref
from investo.models.enrichment import SLOT_REQUIRED_FIELDS, EndpointScope, SourceSlotQualification
from investo.sources._dart_document import MAX_BYTES, DartDocumentError, parse_dart_document
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.event_evidence import map_source_slot_context

FIXTURE = Path(__file__).parents[2] / "fixtures/dart_document/cb-correction-6.4.xml"
FILING = "20260902000001"
NOW = datetime(2026, 9, 3, tzinfo=UTC)


def item_case(**changes):
    entry = dict(
        corp_code="00000001",
        corp_name="가람상사",
        report_nm="[기재정정]주요사항보고서(전환사채권 발행결정)",
        rcept_no=FILING,
        rcept_dt="20260902",
        corp_cls="K",
    )
    entry.update(changes)
    item = DartDisclosureAdapter()._normalize_entry(entry, date_precision=True)
    assert item is not None
    return item


def archive_case(text=None, *, name=FILING + ".xml", compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr(name, FIXTURE.read_bytes() if text is None else text)
    return buffer.getvalue()


def parse_case(text=None, *, item=None, data=None, **kwargs):
    data = archive_case(text) if data is None else data
    return parse_dart_document(
        item or item_case(),
        data,
        response_sha256=hashlib.sha256(data).hexdigest(),
        received_at=NOW,
        **kwargs,
    )


def text_fixture():
    return FIXTURE.read_text()


def resolved(result, key):
    return tuple(resolve_context_ref(ref, (result.context,)) for ref in result.field_refs[key])


def test_current_issue_and_corrected_columns_have_five_exact_source_slots():
    original = item_case()
    before = original.model_dump_json()
    result = parse_case(item=original)
    assert set(result.field_refs) == set(SLOT_REQUIRED_FIELDS["domestic.disclosure_action"])
    assert resolved(result, "issuer") == ("(주)가람상사",)
    assert "제3회 무보증 사모 전환사채" in resolved(result, "action")
    assert "일정에 따라 발행 예정" in resolved(result, "action_status")
    terms = resolved(result, "action_terms")
    assert "100,000" in terms and "10" in terms and "10,000" in terms and "2.50" in terms
    assert "전환가액 (원/주)" in terms and "7" in terms
    assert "12" not in terms and "8,333" not in terms and "999,999" not in terms
    assert resolved(result, "filing_locator") == (FILING,)
    assert len(result.field_refs["action_terms"]) == 16
    assert original.model_dump_json() == before
    assert result.item.title == original.title and result.item.summary == original.summary
    assert result.context.time.published_at.precision == "date"
    assert result.context.time.occurred_at.precision == "unknown"
    assert result.context.evidence_budget_limited
    assert len(result.item.event_evidence.detail_excerpt) <= 1200
    assert "가람상사" not in repr(result)
    assert "100,000" not in repr(result.xml_bindings[5])


def test_real_shared_slot_factory_retains_context_and_exact_refs():
    result = parse_case()
    required = SLOT_REQUIRED_FIELDS["domestic.disclosure_action"]
    row = SourceSlotQualification(
        source_name="dart-disclosure",
        slot_id="domestic.disclosure_action",
        access_kind="structured_api",
        endpoint_scope=EndpointScope(
            host="dart.fss.or.kr", path_prefix="/dsaf001/main.do", query_keys=("rcpNo",)
        ),
        official_discovery_url="https://dart.fss.or.kr/dsaf001/main.do",
        checked_at=NOW,
        source_code_sha="a" * 40,
        status="verified",
        reason_codes=("runtime.not_verified",),
        access_evidence_hash="b" * 64,
        rights_evidence_url="https://opendart.fss.or.kr/intro/main.do",
        rights_scope="synthetic self-check only; no live source qualification",
        schema_fixture_sha256=hashlib.sha256(result.context.model_dump_json().encode()).hexdigest(),
        parser_version=result.parser_version,
        required_slots=required,
        verified_slots=required,
        missing_slots=(),
        chunk_roles=("identity", "fact", "background"),
        time_precision="date",
        public_locator_basis="listing receipt bound to captured XML member and digest",
    )
    mapped = map_source_slot_context(
        result.item, row, received_at=NOW, field_refs=result.field_refs
    )
    assert mapped == result.context


@pytest.mark.parametrize(
    "old,new",
    [
        ('ACODE="11324"', 'ACODE="99999"'),
        (">6.4<", ">6.5<"),
        ('ADATE="20260723"', 'ADATE="20260724"'),
        ('AREGCIK="00000001"', 'AREGCIK="00000002"'),
        ('ACODE="EXE_PRC">10<', 'ACODE="EXE_PRC">12<'),
        ('ACODE="STK_CNT">10,000<', 'ACODE="STK_CNT">8,333<'),
        ('ACODE="STK_RT">2.50<', 'ACODE="STK_RT">2.08<'),
        ('ACODE="MIN_PRC">7<', 'ACODE="MIN_PRC">8<'),
        (">일정에 따라 발행 예정<", ">발행 완료<"),
        ('AUNITVALUE="20260905"', 'AUNITVALUE="20260906"'),
        ("전환가액 (원/주)", "전환가액 (USD/주)"),
        (">12. 납입일<", ">17. 이사회결의일(결정일)<"),
        (">정 정 전<", ">정 정 후<"),
        ('ROWSPAN="3"', 'ROWSPAN="99"'),
        ('ROWSPAN="3"', 'ROWSPAN="0"'),
        (">9. 전환에 관한사항- 전환가액<", ">발행 완료<"),
    ],
)
def test_different_schema_identity_units_dates_or_correction_columns_are_rejected(old, new):
    text = text_fixture()
    assert old in text
    with pytest.raises(DartDocumentError, match=r"^dart\."):
        parse_case(text.replace(old, new))


@pytest.mark.parametrize("field", ["DNM_SUM", "EXE_PRC", "STK_CNT", "CRT_PLN", "CRT_RSN"])
def test_missing_and_duplicated_required_fields_are_never_chosen_by_first_match(field):
    text = text_fixture()
    start = text.index(f'<TE ACODE="{field}">')
    end = text.index("</TE>", start) + len("</TE>")
    node = text[start:end]
    for changed in (text.replace(node, ""), text.replace(node, node + node)):
        with pytest.raises(DartDocumentError):
            parse_case(changed)


@pytest.mark.parametrize(
    "name",
    ["../" + FILING + ".xml", "/" + FILING + ".xml", "other.xml", FILING + ".XML", "a\\b.xml"],
)
def test_only_the_requested_single_exact_xml_member_is_supported(name):
    with pytest.raises(DartDocumentError):
        parse_case(data=archive_case(name=name))


def test_unknown_compression_multiple_members_and_symlinks_are_rejected():
    for compression in (zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA):
        with pytest.raises(DartDocumentError):
            parse_case(data=archive_case(compression=compression))
    for duplicate in (True, False):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(FILING + ".xml", FIXTURE.read_bytes())
            if duplicate:
                with pytest.warns(UserWarning, match="Duplicate name"):
                    z.writestr(FILING + ".xml", b"<root/>")
            else:
                z.writestr("other.xml", b"<root/>")
        with pytest.raises(DartDocumentError):
            parse_case(data=buf.getvalue())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        entry = zipfile.ZipInfo(FILING + ".xml")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(entry, FIXTURE.read_bytes())
    with pytest.raises(DartDocumentError):
        parse_case(data=buf.getvalue())


@pytest.mark.parametrize(
    "text",
    [
        '<!DOCTYPE DOCUMENT [<!ENTITY x "SYNTHETIC">]><DOCUMENT>&x;</DOCUMENT>',
        '<!DOCTYPE DOCUMENT SYSTEM "https://example.invalid/data"><DOCUMENT/>',
        '<?xml version="1.0" encoding="unknown"?><DOCUMENT/>',
        "<DOCUMENT>" + "<a>" * 257 + "</a>" * 257 + "</DOCUMENT>",
        "<DOCUMENT>" + "<a/>" * 20000 + "</DOCUMENT>",
    ],
)
def test_unsafe_xml_encoding_entities_and_tree_budgets_fail_closed(text):
    with pytest.raises(DartDocumentError):
        parse_case(text)


def test_raw_and_expanded_byte_budgets_are_checked_without_parsing_large_inputs():
    with pytest.raises(DartDocumentError, match="byte_limit"):
        parse_case(data=b"x" * (MAX_BYTES + 1))
    with pytest.raises(DartDocumentError, match="byte_limit"):
        parse_case("<DOCUMENT>" + "x" * MAX_BYTES + "</DOCUMENT>")


@pytest.mark.parametrize("location", ["comment", "value", "attribute"])
def test_supplied_secret_echo_is_closed_and_never_printed(location):
    token = "SYNTHETIC_CREDENTIAL_NOT_REAL"
    text = text_fixture()
    addition = {
        "comment": f"<!--{token}-->",
        "value": f"<P>{token}</P>",
        "attribute": f'<P data="{token}"/>',
    }[location]
    with pytest.raises(DartDocumentError) as error:
        parse_case(text.replace("<BODY>", "<BODY>" + addition), forbidden_token=token.encode())
    assert token not in str(error.value)


@pytest.mark.parametrize(
    "change",
    [
        {"rcept_no": "20260902000002"},
        {"corp_code": "00000002"},
        {"corp_name": "다른회사"},
        {"rcept_dt": "20260903"},
        {"fact_status": "actual"},
        {"published_date": "2026-09-03"},
    ],
)
def test_listing_identifiers_clocks_and_injected_fact_metadata_do_not_cross_bind(change):
    item = item_case()
    item = item.model_copy(update={"raw_metadata": {**item.raw_metadata, **change}})
    with pytest.raises(DartDocumentError):
        parse_case(item=item)


def test_response_digest_url_and_original_listing_are_immutable_inputs():
    data = archive_case()
    with pytest.raises(DartDocumentError):
        parse_dart_document(item_case(), data, response_sha256="f" * 64, received_at=NOW)
    for values in (
        {"url": "https://opendart.fss.or.kr/api/document.xml"},
        {"title": "Other"},
        {"summary": "Other"},
        {"source_name": "other"},
    ):
        with pytest.raises(DartDocumentError):
            parse_case(item=item_case().model_copy(update=values))
    result = parse_case()
    with pytest.raises(TypeError):
        result.field_refs["issuer"] = ()
    assert parse_case().context == result.context
    assert parse_case().xml_bindings == result.xml_bindings


@pytest.mark.parametrize("span", ["-1", "0", "5", "x"])
def test_invalid_correction_colspan_does_not_change_column_ownership(span):
    with pytest.raises(DartDocumentError):
        parse_case(text_fixture().replace("<TH>항 목</TH>", f'<TH COLSPAN="{span}">항 목</TH>'))


def test_duplicate_correction_headers_and_incomplete_rows_are_not_guessed():
    text = text_fixture()
    start = text.index("<TABLE>\n        <THEAD>")
    end = text.index("</TABLE>", start) + len("</TABLE>")
    duplicate = text[:end] + text[start:end] + text[end:]
    with pytest.raises(DartDocumentError):
        parse_case(duplicate)
    with pytest.raises(DartDocumentError):
        parse_case(text.replace("<TD>8</TD><TD>7</TD>", "<TD>7</TD>"))


def test_status_fields_cannot_be_borrowed_from_another_body_section():
    text = text_fixture()
    block = '<TR><TD>향후계획</TD><TE ACODE="CRT_PLN">일정에 따라 발행 예정</TE></TR>'
    text = text.replace(block, "")
    text = text.replace(
        "<TITLE>기발행 다른 차수</TITLE>", "<TITLE>기발행 다른 차수</TITLE>" + block
    )
    with pytest.raises(DartDocumentError):
        parse_case(text)


def test_duplicate_terms_in_a_different_bond_series_never_override_current_issue():
    text = text_fixture().replace('<TE ACODE="BAL_AMT">', '<TE ACODE="DNM_SUM">')
    with pytest.raises(DartDocumentError):
        parse_case(text)


def test_other_table_or_amount_unit_cannot_be_used_for_current_issue_terms():
    text = text_fixture().replace('<TE ACODE="EXE_PRC">10</TE>', "")
    text = text.replace(
        "<TITLE>기발행 다른 차수</TITLE>",
        "<TITLE>기발행 다른 차수</TITLE><TABLE><TR><TD>전환가액 (원/주)</TD>"
        '<TE ACODE="EXE_PRC">10</TE></TR></TABLE>',
    )
    with pytest.raises(DartDocumentError):
        parse_case(text)
    with pytest.raises(DartDocumentError):
        parse_case(text_fixture().replace("총액 (원)", "총액 (USD)"))


def test_wrong_clock_and_unrecognized_metadata_have_closed_errors():
    data = archive_case()
    with pytest.raises(DartDocumentError) as error:
        parse_dart_document(
            item_case(),
            data,
            response_sha256=hashlib.sha256(data).hexdigest(),
            received_at=datetime(2026, 9, 3),
        )
    assert str(error.value).startswith("dart.")
    for values in (
        {"rcept_no": 123},
        {"stock_code": "x" * 301},
        {"meaning": "SYNTHETIC_RAW_POISON"},
    ):
        with pytest.raises(DartDocumentError) as error:
            parse_case(
                item=item_case().model_copy(
                    update={"raw_metadata": {**item_case().raw_metadata, **values}}
                )
            )
        assert "SYNTHETIC_RAW_POISON" not in str(error.value)


def test_metadata_echo_utf16_xml_and_broken_crc_are_rejected():
    token = b"SYNTHETIC_ONLY"
    with pytest.raises(DartDocumentError):
        parse_case(
            item=item_case().model_copy(
                update={"raw_metadata": {**item_case().raw_metadata, "stock_code": token.decode()}}
            ),
            forbidden_token=token,
        )
    with pytest.raises(DartDocumentError):
        parse_case(text_fixture().encode("utf-16"))
    data = bytearray(archive_case(compression=zipfile.ZIP_STORED))
    data[data.index(b"<?xml") + 15] ^= 1
    with pytest.raises(DartDocumentError):
        parse_case(data=bytes(data))


def test_character_referenced_secret_echo_is_detected_after_safe_xml_parsing():
    text = text_fixture().replace("<BODY>", "<BODY><P>SYNTHETIC&#95;TOKEN</P>")
    with pytest.raises(DartDocumentError):
        parse_case(text, forbidden_token=b"SYNTHETIC_TOKEN")


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"])
def test_bomless_wide_xml_cannot_bypass_utf8_or_comment_secret_check(encoding):
    text = text_fixture().replace('encoding="UTF-8"', 'encoding="UTF-16"')
    text = text.encode("ascii", "xmlcharrefreplace").decode("ascii")
    text = text.replace("<BODY>", "<BODY><!--SYNTHETIC_TOKEN-->")
    with pytest.raises(DartDocumentError):
        parse_case(text.encode(encoding), forbidden_token=b"SYNTHETIC_TOKEN")


def test_every_projection_and_corrected_column_binding_resolves_back_to_xml():
    from defusedxml.ElementTree import fromstring

    from investo.models.event_evidence import normalize_evidence_text

    root = fromstring(
        FIXTURE.read_bytes(), forbid_dtd=True, forbid_entities=True, forbid_external=True
    )
    result = parse_case()
    assert len(result.xml_bindings) == 29
    for binding in result.xml_bindings:
        node_path, _, attribute = binding.path.partition("/@")
        node = root.find(node_path.removeprefix("DOCUMENT/"))
        assert node is not None, binding.name
        raw = node.attrib[attribute] if attribute else "".join(node.itertext())
        assert " ".join(normalize_evidence_text(raw).split()) == binding.value


def test_nul_suffix_in_original_zip_member_name_is_not_the_requested_filing():
    name = FILING + ".xmlXhidden.xml"
    data = archive_case(name=name, compression=zipfile.ZIP_STORED)
    data = data.replace(name.encode(), name.replace("X", "\x00").encode())
    with pytest.raises(DartDocumentError):
        parse_case(data=data)


@pytest.mark.parametrize(
    "change",
    [
        {"event_date": "2026-09-04"},
        {"event_time_basis": "exact"},
        {"published_at_precision": "exact"},
        {"published_timezone": "UTC"},
    ],
)
def test_listing_date_precision_cannot_be_silently_upgraded_or_reassociated(change):
    item = item_case()
    with pytest.raises(DartDocumentError):
        parse_case(item=item.model_copy(update={"raw_metadata": {**item.raw_metadata, **change}}))


@pytest.mark.parametrize(
    "modifier", ["", "[철회]", "[검토중]", "[첨부정정]", "[정정]", "[기재정정][철회]"]
)
def test_only_the_supported_listing_correction_status_can_bind_to_the_xml(modifier):
    report = modifier + "주요사항보고서(전환사채권 발행결정)"
    with pytest.raises(DartDocumentError):
        parse_case(item=item_case(report_nm=report))
