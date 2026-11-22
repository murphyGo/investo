"""Invented v2 contracts exercise full after/current binding and native coverage."""

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
from defusedxml.ElementTree import fromstring, tostring

from investo._internal.event_context import resolve_context_ref
from investo.models.event_evidence import make_event_context_document, normalize_evidence_text
from investo.sources._dart_document import DartDocumentError, _text
from investo.sources._dart_terms_document import _ranges, parse_dart_terms_document
from tests.unit.sources.test_dart_document_u173 import NOW, archive_case, item_case

FIXTURE = Path(__file__).parents[2] / "fixtures/dart_document/cb-terms-correction-6.4.xml"
FILING = "20260903000002"


def parse_case(text=None, *, item=None, data=None, **kwargs):
    payload = data or archive_case(text or FIXTURE.read_bytes(), name=FILING + ".xml")
    return parse_dart_terms_document(
        item or item_case(rcept_no=FILING, rcept_dt=FILING[:8]),
        payload,
        response_sha256=hashlib.sha256(payload).hexdigest(),
        received_at=NOW,
        **kwargs,
    )


def tree():
    return fromstring(FIXTURE.read_bytes(), forbid_dtd=True, forbid_entities=True)


def correction_rows(root):
    table = next(
        table
        for table in root.findall("./BODY/LIBRARY/CORRECTION/TABLE")
        if table.find("./THEAD") is not None
    )
    return table.findall("./TBODY/TR")


def after(root, index):
    return correction_rows(root)[index][3]


def field(root, code):
    attribute = "AUNIT" if code.endswith("_DT") else "ACODE"
    return next(
        node
        for node in root.findall("./BODY/SECTION-1")[0].iter()
        if node.attrib.get(attribute) == code
    )


def test_full_contract_fields_and_all_note_nodes_survive_native_factory():
    result = parse_case()
    context = make_event_context_document(
        result.item.event_evidence,
        metadata=result.item.raw_metadata,
        item=result.item,
        article_passages=True,
    )
    assert context.model_dump_json() == result.context.model_dump_json()
    assert result.parser_version == "dart-cb-terms-correction-6.4-v2"
    assert set(result.field_refs) == {
        "issuer",
        "action",
        "action_status",
        "action_terms",
        "filing_locator",
    }
    assert all(1 <= len(refs) <= 16 for refs in result.field_refs.values())
    assert len(result.xml_bindings) == 154
    paragraphs = result.item.event_evidence.detail_excerpt.splitlines()
    assert 1 < len(paragraphs) <= 6 and all(len(value) <= 1200 for value in paragraphs)
    assert len(result.item.event_evidence.detail_excerpt) <= 3600
    terms = "".join(
        resolve_context_ref(ref, (context,)) for ref in result.field_refs["action_terms"]
    )
    assert terms == "".join(paragraphs)
    for code in ("INT_GV_MTH", "RTN_MTH", "OPT_FCT"):
        assert _text(field(tree(), code)) in terms
    assert "주2) 정정후" in terms and "합성 계약 주석 8" in terms
    assert "합성 종전 주석" not in terms
    assert resolve_context_ref(result.field_refs["filing_locator"][0], (context,)) == FILING


def test_every_xml_path_attribute_and_value_roundtrips_to_synthetic_source():
    root = tree()
    result = parse_case()
    for binding in result.xml_bindings:
        path, _, attribute = binding.path.partition("/@")
        node = root.find(path.removeprefix("DOCUMENT/"))
        assert node is not None
        value = node.attrib[attribute] if attribute else "".join(node.itertext())
        assert " ".join(normalize_evidence_text(value).split()) == binding.value


@pytest.mark.parametrize(
    "code,index", [("EXP_DT", 0), ("INT_GV_MTH", 1), ("RTN_MTH", 2), ("OPT_FCT", 4), ("PYM_DT", 5)]
)
def test_one_sided_after_value_changes_are_not_current_terms(code, index):
    root = tree()
    after(root, index).text = "합성 다른 값"
    with pytest.raises(DartDocumentError, match="correction_mismatch"):
        parse_case(tostring(root))


@pytest.mark.parametrize("code", ["SB_BGN_DT", "SB_END_DT"])
def test_conversion_interval_requires_both_dates_and_encoded_values(code):
    root = tree()
    field(root, code).attrib["AUNITVALUE"] = "20000101"
    with pytest.raises(DartDocumentError):
        parse_case(tostring(root))
    root = tree()
    after(root, 3).text = "시작일 : 2027년 09월 05일종료일 : 2029년 09월 03일"
    with pytest.raises(DartDocumentError, match="correction_mismatch"):
        parse_case(tostring(root))


@pytest.mark.parametrize(
    "mode",
    [
        "missing_marker",
        "wrong_pointer",
        "duplicate_marker",
        "extra_after",
        "current_missing",
        "current_changed",
        "duplicate_header",
        "table_changed",
        "table_span_both",
    ],
)
def test_note_pointer_resolves_full_unique_after_block_and_current_section(mode):
    root = tree()
    correction = root.find("./BODY/LIBRARY/CORRECTION")
    section = root.find("./BODY/SECTION-1")
    current = [node for node in section if node.tag == "P"]
    corrected = next(
        node for node in correction if node.tag == "P" and _text(node).startswith("주2) 정정후")
    )
    if mode == "missing_marker":
        corrected.text = corrected.text.replace("주2) 정정후", "")
    elif mode == "wrong_pointer":
        after(root, 6).text = "주1) 정정전"
    elif mode == "duplicate_marker":
        correction.insert(list(correction).index(corrected), deepcopy(corrected))
    elif mode == "extra_after":
        correction.insert(
            list(correction).index(corrected) + 1, fromstring("<P>합성 추가 조건</P>")
        )
    elif mode == "current_missing":
        section.remove(current[0])
    elif mode == "current_changed":
        current[0].text = "합성 변경된 조건"
    elif mode == "duplicate_header":
        header = next(node for node in section if _text(node).startswith("23."))
        section.append(deepcopy(header))
    elif mode == "table_changed":
        table = next(
            node
            for node in section
            if node.tag == "TABLE" and len(node.findall("./TBODY/TR")) == 10
        )
        table.findall("./TBODY/TR")[-1][-1].text = "90.00%"
    else:
        for container in (correction, section):
            tables = [
                node
                for node in container
                if node.tag == "TABLE" and len(node.findall("./TBODY/TR")) == 10
            ]
            for table in tables:
                table.findall("./TBODY/TR")[0][0].attrib["ROWSPAN"] = "1"
    with pytest.raises(DartDocumentError):
        parse_case(tostring(root))


@pytest.mark.parametrize(
    "mode",
    [
        "unknown_row",
        "duplicate_row",
        "other_series",
        "moved_field",
        "conversion_group",
        "complete_issuance",
        "oversized_projection",
        "unbreakable_term",
    ],
)
def test_unknown_ambiguous_foreign_or_oversized_inputs_close(mode):
    root = tree()
    section = root.find("./BODY/SECTION-1")
    rows = correction_rows(root)
    if mode == "unknown_row":
        rows[0][0].text = "합성 알 수 없는 항목"
    elif mode == "duplicate_row":
        rows[1][0].text = rows[0][0].text
    elif mode in {"other_series", "oversized_projection", "unbreakable_term"}:
        for code, index in (("INT_GV_MTH", 1), ("RTN_MTH", 2), ("OPT_FCT", 4)):
            value = (
                "제2회 합성 계약"
                if mode == "other_series"
                else ("x" * 300 if mode == "unbreakable_term" else "합성 계약 조건 " * 100)
            )
            field(root, code).text = value
            after(root, index).text = value
    elif mode == "moved_field":
        node = field(root, "RTN_MTH")
        parent = next(node_parent for node_parent in section.iter() if node in list(node_parent))
        parent.remove(node)
        section.find("./LIBRARY/TABLE-GROUP/TABLE/TBODY/TR").append(node)
    elif mode == "conversion_group":
        cell = next(node for node in section.iter("TD") if _text(node) == "전환청구기간")
        cell.attrib["ROWSPAN"] = "1"
    else:
        field(root, "CRT_PLN").text = "발행 완료"
    with pytest.raises(DartDocumentError):
        parse_case(tostring(root))


def test_old_version_bytes_and_old_form_stay_separate():
    path = Path(__file__).parents[3] / "src/investo/sources/_dart_document.py"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "8bae1c71b79f26b22391679c4c9ebfed1ad574135c02c91f75298426346ae166"
    )
    original = FIXTURE.with_name("cb-correction-6.4.xml").read_bytes()
    with pytest.raises(DartDocumentError):
        parse_case(original)


def test_refs_do_not_split_dates_numbers_or_units():
    text = "합성 조건 " * 30 + "2026 년 09 월 03 일 100,000 원 " + "합성 조건 " * 40
    ranges = _ranges(text)
    assert "".join(text[a:b] for a, b in ranges) == text
    assert all(b - a <= 240 for a, b in ranges)
    assert any("2026 년 09 월 03 일" in text[a:b] for a, b in ranges)
    assert any("100,000 원" in text[a:b] for a, b in ranges)


def test_row_number_adjacent_to_year_cannot_hide_protected_date():
    text = "x " * 112 + "1" + "2026 년 09 월 03 일 " + "y " * 100
    refs = _ranges(text)
    assert any("2026 년 09 월 03 일" in text[a:b] for a, b in refs)


def test_all_projection_date_and_number_unit_boundaries_are_protected():
    import re

    from investo.sources._dart_terms_document import _DATES, _NUMBERS

    result = parse_case()
    for chunk in result.context.chunks:
        spans = [
            match.span() for pattern in (_DATES, _NUMBERS) for match in pattern.finditer(chunk.text)
        ]
        for ref in result.field_refs["action_terms"]:
            if ref.chunk_id != chunk.chunk_id:
                continue
            assert not any(a < ref.start < b or a < ref.end < b for a, b in spans)
    assert " | " in result.item.event_evidence.detail_excerpt
    assert re.search(r"NOTE23_\d+:.*\|", result.item.event_evidence.detail_excerpt)


def test_note_table_uses_logical_five_column_headers_and_exact_data_cells():
    from investo.sources._dart_terms_document import _table_projection

    table = next(
        node
        for node in tree().find("./BODY/SECTION-1")
        if node.tag == "TABLE" and len(node.findall("./TBODY/TR")) == 10
    )
    rows = _table_projection(table).split("; ")
    assert rows[0].split(" | ") == [
        "구분",
        "조기상환 청구기간/FROM",
        "조기상환 청구기간/TO",
        "조기상환 지급일",
        "조기상환율",
    ]
    assert [row.split(" | ") for row in rows[1:]] == [
        [_text(cell) for cell in row] for row in table.findall("./TBODY/TR")[2:]
    ]


@pytest.mark.parametrize("change", ["header", "delimiter"])
def test_same_invalid_table_in_both_blocks_is_not_a_qualified_note(change):
    root = tree()
    for container in (root.find("./BODY/LIBRARY/CORRECTION"), root.find("./BODY/SECTION-1")):
        for table in [
            node
            for node in container
            if node.tag == "TABLE" and len(node.findall("./TBODY/TR")) == 10
        ]:
            rows = table.findall("./TBODY/TR")
            if change == "header":
                rows[0][-1].text = "합성 다른 지표"
            else:
                rows[-1][0].text = "1 | 2"
    with pytest.raises(DartDocumentError):
        parse_case(tostring(root))
