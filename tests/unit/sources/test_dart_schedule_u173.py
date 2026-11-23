"""Schedule corrections bind all changed conditions without expanding live access."""

import hashlib
from pathlib import Path

import pytest
from defusedxml.ElementTree import fromstring
from hypothesis import given, settings
from hypothesis import strategies as st

from investo._internal.event_context import resolve_context_ref
from investo.models.event_evidence import normalize_evidence_text
from investo.sources._dart_document import (
    PARSER_VERSION,
    SCHEDULE_PARSER_VERSION,
    DartDocumentError,
    parse_dart_document,
    parse_dart_schedule_document,
)
from investo.sources._dart_evidence import dart_runtime_evidence
from tests.unit.sources.test_dart_document_u173 import NOW, archive_case, item_case, parse_case

FIXTURE = Path(__file__).parents[2] / "fixtures/dart_document/cb-schedule-6.4.xml"


def parse_schedule(text=None, **kwargs):
    data = archive_case(FIXTURE.read_text() if text is None else text)
    return parse_dart_schedule_document(
        item_case(),
        data,
        response_sha256=hashlib.sha256(data).hexdigest(),
        received_at=NOW,
        **kwargs,
    )


def check_bindings(text, result):
    root = fromstring(text, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    for binding in result.xml_bindings:
        path, _, attribute = binding.path.partition("/@")
        node = root.find(path.removeprefix("DOCUMENT/"))
        assert node is not None, binding.name
        raw = node.attrib[attribute] if attribute else "".join(node.itertext())
        assert " ".join(normalize_evidence_text(raw).split()) == binding.value
    assert all(
        resolve_context_ref(ref, (result.context,)) is not None
        for refs in result.field_refs.values()
        for ref in refs
    )


def test_schedule_has_versioned_source_bound_dates_and_limited_native_projection():
    result = parse_schedule()
    assert result.parser_version == SCHEDULE_PARSER_VERSION != PARSER_VERSION
    assert len(result.field_refs) == 5
    assert max(map(len, result.field_refs.values())) <= 16
    terms = [
        resolve_context_ref(ref, (result.context,)) for ref in result.field_refs["action_terms"]
    ]
    assert "2026년 09월 05일" in terms and "2026년 09월 15일" in terms
    assert "2029년 09월 05일" in terms and "2029년 09월 15일" in terms
    assert any("시작일" in text and "종료일" in text for text in terms)
    assert "10" not in terms and "10,000" not in terms  # Unchanged conversion prices/shares.
    check_bindings(FIXTURE.read_text(), result)
    native = dart_runtime_evidence(result)
    assert native.item.event_evidence.evidence_budget_limited
    assert len(native.item.event_evidence.detail_excerpt) <= 1200
    assert "청구 조건 A" not in native.item.event_evidence.detail_excerpt
    assert native.item.title == item_case().title and native.item.summary == item_case().summary
    assert native.context.time.occurred_at.precision == "unknown"
    for slot, refs in native.field_refs.items():
        assert tuple(resolve_context_ref(r, (native.context,)) for r in refs) == tuple(
            resolve_context_ref(r, (result.context,)) for r in result.field_refs[slot]
        )


def test_default_live_parser_does_not_fall_back_to_schedule_version():
    data = archive_case(FIXTURE.read_text())
    with pytest.raises(DartDocumentError, match=r"dart\.correction_mismatch"):
        parse_dart_document(
            item_case(), data, response_sha256=hashlib.sha256(data).hexdigest(), received_at=NOW
        )
    assert parse_case().parser_version == PARSER_VERSION
    with pytest.raises(DartDocumentError):
        parse_schedule(
            Path(__file__)
            .parents[2]
            .joinpath("fixtures/dart_document/cb-correction-6.4.xml")
            .read_text()
        )


@pytest.mark.parametrize(
    "old,new",
    [
        ('ACODE="INT_GV_MTH">2026년', 'ACODE="INT_GV_MTH">2027년'),
        ('ACODE="RTN_MTH">2029년', 'ACODE="RTN_MTH">2030년'),
        ('ACODE="OPT_FCT">2027년', 'ACODE="OPT_FCT">2028년'),
        ('AUNITVALUE="20270915"', 'AUNITVALUE="20270916"'),
        ('AUNITVALUE="20290815"', 'AUNITVALUE="20290816"'),
        ('AUNITVALUE="20260915"', 'AUNITVALUE="20260916"'),
        ('AUNITVALUE="20290915"', 'AUNITVALUE="20290916"'),
        (">6. 이자지급방법<", ">다른 조건<"),
        (">시작일<", ">종료일<"),
        (">정 정 후<", ">정 정 전<"),
        ('ROWSPAN="7"', 'ROWSPAN="8"'),
        (">주2) 정정후<", ">주1) 정정전<"),
        ("주2) 정정후 예시", "주3) 정정후 예시"),
        ("일정에 따라 발행 예정", "발행 완료"),
        ("2027년 09월 15일종료일 : 2029년", "2030년 09월 15일종료일 : 2029년"),
        ("2027년 09월 05일종료일 : 2029년", "2027년 02월 30일종료일 : 2029년"),
    ],
)
def test_inconsistent_current_terms_labels_dates_and_status_are_rejected(old, new):
    text = FIXTURE.read_text()
    assert old in text
    with pytest.raises(DartDocumentError, match=r"^dart\."):
        parse_schedule(text.replace(old, new))


@pytest.mark.parametrize("code", ["INT_GV_MTH", "RTN_MTH", "OPT_FCT", "SB_BGN_DT", "SB_END_DT"])
def test_required_schedule_fields_are_unique_and_owned_by_main_table(code):
    text = FIXTURE.read_text()
    tag, attr = ("TU", "AUNIT") if code.startswith("SB_") else ("TE", "ACODE")
    start = text.index(f'<{tag} {attr}="{code}"')
    end = text.index(f"</{tag}>", start) + len(f"</{tag}>")
    element = text[start:end]
    for mutated in (
        text.replace(element, ""),
        text.replace(element, element + element),
        text.replace(element, "").replace(
            "</BODY>", f"<SECTION-1><TABLE>{element}</TABLE></SECTION-1></BODY>"
        ),
    ):
        with pytest.raises(DartDocumentError):
            parse_schedule(mutated)


@pytest.mark.parametrize(
    "label",
    [
        "5. 사채만기일",
        "6. 이자지급방법",
        "7. 원금상환방법",
        "9. 전환에 관한사항- 전환청구기간",
        "9-1. 옵션에 관한 사항",
        "12. 납입일",
        "23. 기타 투자판단에 참고할 사항",
    ],
)
def test_each_correction_row_is_required_and_unknown_rows_are_rejected(label):
    text = FIXTURE.read_text()
    for replacement in (
        "지원되지 않는 항목",
        "12. 납입일" if label != "12. 납입일" else "5. 사채만기일",
    ):
        with pytest.raises(DartDocumentError):
            parse_schedule(text.replace(f"<TD>{label}</TD>", f"<TD>{replacement}</TD>", 1))


@pytest.mark.parametrize(
    "part", ["청구 조건 A", "청구 조건 B", "조건이 충족된 경우에만", "예시 날짜"]
)
def test_note_content_must_match_in_full_not_just_first_paragraph(part):
    text = FIXTURE.read_text()
    with pytest.raises(DartDocumentError):
        parse_schedule(text.replace(part, "다른 조건", 1))


def test_note_order_table_shape_and_scope_cannot_be_flattened_away():
    text = FIXTURE.read_text()
    for mutated in (
        text.replace(
            "<TD>예시 회차</TD><TD>예시 날짜</TD>", '<TD COLSPAN="2">예시 회차예시 날짜</TD>', 1
        ),
        text.replace("<P>가. 예시 지급일</P>", "<P>가. 예시 지급일</P><P>추가 조건</P>", 1),
        text.replace(
            "<P>가. 예시 지급일</P>\n      <P>청구 조건 A를 확인해야 한다.</P>",
            "<P>청구 조건 A를 확인해야 한다.</P>\n      <P>가. 예시 지급일</P>",
            1,
        ),
        text.replace(
            "<PGBRK/>", "<P>주2) 정정후 예시 조기상환 조건을 적용할 예정이다.</P><PGBRK/>"
        ),
        text.replace("<TD>23. 기타 투자판단에 참고할 사항</TD></TR>", "<TD>다른 주석</TD></TR>"),
    ):
        with pytest.raises(DartDocumentError):
            parse_schedule(mutated)


def test_new_entrypoint_reuses_archive_and_secret_guards():
    with pytest.raises(DartDocumentError):
        parse_schedule('<!DOCTYPE DOCUMENT [<!ENTITY x "unsafe">]><DOCUMENT>&x;</DOCUMENT>')
    with pytest.raises(DartDocumentError, match=r"dart\.credential_echo") as error:
        parse_schedule(
            FIXTURE.read_text().replace("<BODY>", "<BODY><!--SYNTHETIC_TOKEN-->"),
            forbidden_token=b"SYNTHETIC_TOKEN",
        )
    assert "SYNTHETIC_TOKEN" not in str(error.value)


@pytest.mark.parametrize(
    "boundary",
    [
        "<PGBRK/><P>위 일정은 취소되어 적용하지 않는다.</P>",
        "<PGBRK>위 일정은 취소되어 적용하지 않는다.</PGBRK>",
        "<PGBRK><P>추가 조건</P></PGBRK>",
        "<PGBRK/><UNKNOWN/>",
        "<UNKNOWN/><PGBRK/>",
        "<PGBRK/>위 일정은 취소되어 적용하지 않는다.",
    ],
)
def test_pagebreak_does_not_discard_conditions_or_unknown_elements(boundary):
    with pytest.raises(DartDocumentError):
        parse_schedule(FIXTURE.read_text().replace("<PGBRK/>", boundary))


def test_equal_preorder_text_does_not_hide_different_note_table_structure():
    text = FIXTURE.read_text()
    table = (
        "<TABLE><TBODY><TR><TD>예시 회차</TD><TD>예시 날짜</TD></TR>"
        "<TR><TD>1</TD><TD>2027년 09월 15일</TD></TR></TBODY></TABLE>"
    )
    proper = "<TABLE><TBODY><TR><TD>X</TD><TD/></TR><TR/></TBODY></TABLE>"
    nested = "<TABLE><TBODY><TR><TD>X</TD><TD/><TR/></TR></TBODY></TABLE>"
    assert text.count(table) == 2
    text = text.replace(table, proper, 1).replace(table, nested, 1)
    with pytest.raises(DartDocumentError):
        parse_schedule(text)


@pytest.mark.parametrize("location", ["note", "body", "correction_parent", "section_parent"])
def test_unwrapped_note_conditions_are_not_discarded(location):
    text = FIXTURE.read_text()
    if location in {"note", "body"}:
        marker = "<P>가. 예시 지급일</P>"
        index = text.index(marker) if location == "note" else text.rindex(marker)
        index += len(marker)
        text = text[:index] + "위 일정은 취소되어 적용하지 않는다." + text[index:]
    else:
        tag = "<CORRECTION>" if location == "correction_parent" else "<SECTION-1>"
        text = text.replace(tag, tag + "위 일정은 취소되어 적용하지 않는다.", 1)
    with pytest.raises(DartDocumentError):
        parse_schedule(text)


@given(st.integers(min_value=6, max_value=28))
@settings(max_examples=23)
def test_generated_valid_days_preserve_all_xml_and_native_refs(day):
    text = FIXTURE.read_text().replace("월 15일", f"월 {day:02}일")
    for prefix in ("202609", "202709", "202908", "202909"):
        text = text.replace(prefix + "15", prefix + f"{day:02}")
    result = parse_schedule(text)
    check_bindings(text, result)
    assert parse_schedule(text).context == result.context
    native = dart_runtime_evidence(result)
    assert len(native.item.event_evidence.detail_excerpt) <= 1200
    assert all(len(refs) <= 16 for refs in native.field_refs.values())


@given(st.integers(min_value=1, max_value=28).filter(lambda day: day != 15))
@settings(max_examples=27)
def test_generated_body_only_payment_changes_never_override_correction(day):
    text = FIXTURE.read_text().replace(
        'AUNITVALUE="20260915">2026년 09월 15일',
        f'AUNITVALUE="202609{day:02}">2026년 09월 {day:02}일',
    )
    with pytest.raises(DartDocumentError):
        parse_schedule(text)
