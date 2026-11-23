"""Closed v2 contract-terms correction, separate from the immutable v1 form."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from types import MappingProxyType
from typing import cast
from zoneinfo import ZoneInfo

from investo.models.event_context import ContextRef
from investo.models.event_evidence import (
    evidence_clock_utc,
    make_event_context_document,
    make_evidence_document,
)
from investo.models.items import NormalizedItem
from investo.sources._dart_document import (
    MAX_BYTES,
    DartDocumentError,
    DartDocumentEvidence,
    DartXmlBinding,
    Element,
    _compact,
    _date_value,
    _grid,
    _one,
    _read_xml,
    _text,
)
from investo.sources.dart_disclosure import DartDisclosureAdapter

PARSER_VERSION = "dart-cb-terms-correction-6.4-v2"
MAX_PROJECTION = 3600
_FORM = "주요사항보고서(전환사채권발행결정)"
_ROWS = (
    "5.사채만기일",
    "6.이자지급방법",
    "7.원금상환방법",
    "9.전환에관한사항-전환청구기간",
    "9-1.옵션에관한사항",
    "12.납입일",
    "23.기타투자판단에참고할사항",
)
_LABELS = {
    "DNM_SUM": "2.사채의권면(전자등록)총액(원)",
    "EXE_PRC": "전환가액(원/주)",
    "STK_CNT": "주식수",
    "STK_RT": "주식총수대비비율(%)",
    "MIN_PRC": "최저조정가액(원)",
    "EXP_DT": _ROWS[0],
    "PYM_DT": _ROWS[5],
    "DRC_DT": "17.이사회결의일(결정일)",
    "INT_GV_MTH": _ROWS[1],
    "RTN_MTH": _ROWS[2],
    "OPT_FCT": _ROWS[4],
    "SB_BGN_DT": "시작일",
    "SB_END_DT": "종료일",
}
_NUMBER = re.compile(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?")
_DATES = re.compile(r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일")
_NUMBERS = re.compile(r"\d[\d,.]*(?:\s*(?:억원|백만원|개월|원|주|%|bp|년|월|일|회))?")


def _ranges(text: str) -> tuple[tuple[int, int], ...]:
    """Cover a whole literal without bisecting a number, date, unit or word."""
    protected = [match.span() for pattern in (_DATES, _NUMBERS) for match in pattern.finditer(text)]
    result = []
    start = 0
    while len(text) - start > 240:
        ends = [
            index + 1
            for index in range(start, start + 240)
            if text[index].isspace()
            and not any(left < index + 1 < right for left, right in protected)
        ]
        if not ends:
            raise DartDocumentError("dart.context_budget")
        end = ends[-1]
        result.append((start, end))
        start = end
    if start < len(text):
        result.append((start, len(text)))
    return tuple(result)


def _table_signature(table: Element) -> tuple[tuple[tuple[str, str, str, str], ...], ...]:
    if [node.tag for node in table] not in (["TBODY"], ["COLGROUP", "TBODY"]):
        raise DartDocumentError("dart.correction_mismatch")
    for node in table.iter():
        if (
            node.tag in {"TABLE", "COLGROUP", "COL", "TBODY", "TR"} and (node.text or "").strip()
        ) or (node is not table and (node.tail or "").strip()):
            raise DartDocumentError("dart.correction_mismatch")
    for group in table.findall("./COLGROUP"):
        if any(node.tag != "COL" or len(node) for node in group):
            raise DartDocumentError("dart.correction_mismatch")
    body = _one(table.findall("./TBODY"))
    if any(node.tag != "TR" for node in body):
        raise DartDocumentError("dart.correction_mismatch")
    rows = table.findall("./TBODY/TR")
    # This version qualifies the observed two-header/eight-payment-row form.
    expected = (
        (("2", "1"), ("1", "2"), ("2", "1"), ("2", "1")),
        (("1", "1"), ("1", "1")),
        *(((("1", "1"),) * 5,) * 8),
    )
    if len(rows) != len(expected):
        raise DartDocumentError("dart.correction_mismatch")
    signature = []
    for row, shape in zip(rows, expected, strict=True):
        cells = list(row)
        if len(cells) != len(shape):
            raise DartDocumentError("dart.correction_mismatch")
        values = []
        for cell, (down, across) in zip(cells, shape, strict=True):
            if (
                cell.tag != "TD"
                or cell.attrib.get("ROWSPAN", "1") != down
                or cell.attrib.get("COLSPAN", "1") != across
                or not _text(cell)
                or len(_text(cell)) > 180
                or any(delimiter in _text(cell) for delimiter in ("|", ";"))
            ):
                raise DartDocumentError("dart.correction_mismatch")
            values.append((cell.tag, down, across, _text(cell)))
        signature.append(tuple(values))
    headers = [_compact(cell[3]) for cell in signature[0]]
    subheaders = [cell[3] for cell in signature[1]]
    if headers != ["구분", "조기상환청구기간", "조기상환지급일", "조기상환율"] or subheaders != [
        "FROM",
        "TO",
    ]:
        raise DartDocumentError("dart.schema_unsupported")
    return tuple(signature)


def _table_projection(table: Element) -> str:
    rows = _table_signature(table)
    head, subhead = rows[:2]
    header = (
        head[0][3],
        head[1][3] + "/" + subhead[0][3],
        head[1][3] + "/" + subhead[1][3],
        head[2][3],
        head[3][3],
    )
    return "; ".join(
        [" | ".join(header)] + [" | ".join(cell[3] for cell in row) for row in rows[2:]]
    )


def _notes(correction: Element, section: Element, row: list[Element]) -> tuple[Element, ...]:
    before, after = "주1) 정정전", "주2) 정정후"
    if _text(row[2]) != before or _text(row[3]) != after:
        raise DartDocumentError("dart.correction_mismatch")
    children = list(correction)
    direct = list(section)
    if (
        (correction.text or "").strip()
        or (section.text or "").strip()
        or any((node.tail or "").strip() for node in [*children, *direct])
    ):
        raise DartDocumentError("dart.correction_mismatch")

    def empty_paragraph(node: Element) -> bool:
        return node.tag == "P" and not len(node) and not _text(node)

    markers = [
        (index, node, re.match(r"주\d+\)\s*정정[전후]", _text(node)))
        for index, node in enumerate(children)
        if node.tag == "P" and re.match(r"주\d+\)\s*정정[전후]", _text(node))
    ]
    if len(markers) != 2 or [match[0] for _, _, match in markers if match] != [before, after]:
        raise DartDocumentError("dart.correction_mismatch")
    before_index, after_index = (entry[0] for entry in markers)
    if before_index >= after_index:
        raise DartDocumentError("dart.correction_mismatch")
    end = [i for i in range(after_index + 1, len(children)) if children[i].tag == "PGBRK"]
    if (
        len(end) != 1
        or len(children[end[0]])
        or _text(children[end[0]])
        or any(not empty_paragraph(node) for node in children[end[0] + 1 :])
    ):
        raise DartDocumentError("dart.correction_mismatch")
    corrected = tuple(node for node in children[after_index : end[0]] if not empty_paragraph(node))
    headers = [i for i, node in enumerate(direct) if _compact(_text(node)) == _ROWS[6]]
    if len(headers) != 1 or direct[headers[0]].tag != "TABLE":
        raise DartDocumentError("dart.correction_mismatch")
    header_rows = direct[headers[0]].findall("./TBODY/TR")
    if len(header_rows) != 1 or len(header_rows[0]) != 1 or header_rows[0][0].tag != "TD":
        raise DartDocumentError("dart.correction_mismatch")
    stops = [i for i in range(headers[0] + 1, len(direct)) if direct[i].tag == "TABLE-GROUP"]
    if not stops:
        raise DartDocumentError("dart.correction_mismatch")
    current = tuple(node for node in direct[headers[0] + 1 : stops[0]] if not empty_paragraph(node))
    expected_tags = ["P"] * 7 + ["TABLE", "P"]
    if [node.tag for node in corrected] != expected_tags or [
        node.tag for node in current
    ] != expected_tags:
        raise DartDocumentError("dart.correction_mismatch")
    for index, (old, new) in enumerate(zip(corrected, current, strict=True)):
        text = _text(old)
        expected = text[len(after) :].lstrip() if index == 0 else text
        if old.tag != new.tag or old.tag not in {"P", "TABLE"} or expected != _text(new):
            raise DartDocumentError("dart.correction_mismatch")
        if old.tag == "TABLE" and _table_signature(old) != _table_signature(new):
            raise DartDocumentError("dart.correction_mismatch")
    return corrected + current


def _parse(
    item: NormalizedItem,
    data: bytes,
    *,
    response_sha256: str,
    received_at: datetime,
    forbidden_token: bytes,
) -> DartDocumentEvidence:
    received_at = evidence_clock_utc(received_at)
    raw_metadata = item.raw_metadata
    normalized = DartDisclosureAdapter()._normalize_entry(
        raw_metadata, date_precision=raw_metadata.get("published_at_precision") == "date"
    )
    if (
        not data
        or len(data) > MAX_BYTES
        or len(forbidden_token) > 4096
        or not re.fullmatch(r"[0-9a-f]{64}", response_sha256)
        or hashlib.sha256(data).hexdigest() != response_sha256
        or normalized is None
        or item.source_name != "dart-disclosure"
        or item.category != "news"
        or any(
            getattr(item, key) != getattr(normalized, key)
            for key in ("title", "summary", "url", "published_at", "raw_metadata")
        )
        or any(not isinstance(value, str) or len(value) > 300 for value in raw_metadata.values())
    ):
        raise DartDocumentError("dart.source_mismatch")
    metadata = cast(dict[str, str], raw_metadata)
    filing, corp = metadata["rcept_no"], metadata["corp_code"]
    if (
        not re.fullmatch(r"[0-9]{14}", filing)
        or not re.fullmatch(r"[0-9]{8}", corp)
        or metadata["rcept_dt"] != filing[:8]
        or _compact(metadata["report_nm"]) != "[기재정정]" + _FORM
        or (forbidden_token and forbidden_token.decode() in " ".join(metadata.values()))
    ):
        raise DartDocumentError("dart.source_mismatch")
    root, raw = _read_xml(data, filing + ".xml", forbidden_token)
    document = _one(root.findall("./DOCUMENT-NAME"))
    version = _one(root.findall("./FORMULA-VERSION"))
    company = _one(root.findall("./COMPANY-NAME"))
    correction = _one(root.findall("./BODY/LIBRARY/CORRECTION"))
    if (
        root.tag != "DOCUMENT"
        or document.attrib.get("ACODE") != "11324"
        or _compact(_text(document)) != _FORM
        or _text(version) != "6.4"
        or version.attrib.get("ADATE") != "20260723"
        or company.attrib.get("AREGCIK") != corp
        or re.sub(r"^(?:\(주\)|주식회사)|(?:\(주\)|주식회사)$", "", _compact(_text(company)))
        != re.sub(r"^(?:\(주\)|주식회사)|(?:\(주\)|주식회사)$", "", _compact(metadata["corp_name"]))
    ):
        raise DartDocumentError("dart.schema_unsupported")
    parents = {child: parent for parent in root.iter() for child in parent}

    def ancestor(node: Element, tag: str) -> Element:
        while node is not root and node.tag != tag:
            node = parents[node]
        return node

    def path(node: Element) -> str:
        parts = []
        while node is not root:
            parent = parents[node]
            siblings = [value for value in parent if value.tag == node.tag]
            parts.append(f"{node.tag}[{siblings.index(node) + 1}]")
            node = parent
        return "DOCUMENT/" + "/".join(reversed(parts))

    values: list[tuple[str, str]] = []
    bindings: list[DartXmlBinding] = []

    def bind(name: str, node: Element) -> str:
        value = _text(node)
        if not value or len(value) > 1200:
            raise DartDocumentError("dart.context_budget")
        bindings.append(DartXmlBinding(name, path(node), value))
        return value

    def add(name: str, node: Element) -> str:
        value = bind(name, node)
        values.append((name, value))
        return value

    add("issuer", company)
    add("action", document)
    title = _one(correction.findall("./TITLE"))
    if _compact(_text(title)) != "정정신고(보고)":
        raise DartDocumentError("dart.schema_unsupported")
    add("correction", title)
    tables = correction.findall("./TABLE")
    day = _one(tables[0].findall("./TBODY/TR[2]/TD")) if tables else _one([])
    publication = normalized.published_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    if (
        _date_value(day) != publication
        or publication > received_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    ):
        raise DartDocumentError("dart.source_mismatch")
    add("correction_date", day)
    original = [
        row[1]
        for table in tables
        for row in table.findall("./TBODY/TR")
        if len(row) == 2 and _compact(_text(row[0])) == "2.정정대상공시서류의최초제출일:"
    ]
    original_day = _one(original)
    if _date_value(original_day) > publication:
        raise DartDocumentError("dart.source_mismatch")
    add("original_submission_date", original_day)
    sections = root.findall("./BODY/SECTION-1")
    fields = {}
    for name in ("SEQ_NO", "PL_KND", *_LABELS, "CRT_RSN", "CRT_PLN"):
        tag, attribute = ("TU", "AUNIT") if name.endswith("_DT") else ("TE", "ACODE")
        fields[name] = _one(
            [
                node
                for section in sections
                for node in section.iter(tag)
                if node.attrib.get(attribute) == name
            ]
        )
        add(name, fields[name])
    main = ancestor(fields["DNM_SUM"], "TABLE")
    section = ancestor(main, "SECTION-1")
    if any(ancestor(fields[name], "TABLE") is not main for name in ("SEQ_NO", "PL_KND", *_LABELS)):
        raise DartDocumentError("dart.source_mismatch")
    if any(
        ancestor(fields[name], "SECTION-1") is not section for name in ("CRT_RSN", "CRT_PLN")
    ) or ancestor(fields["CRT_RSN"], "TABLE") is not ancestor(fields["CRT_PLN"], "TABLE"):
        raise DartDocumentError("dart.source_mismatch")
    sequence = _text(fields["SEQ_NO"])
    if (
        not sequence.isascii()
        or not sequence.isdigit()
        or not _text(fields["PL_KND"]).startswith(f"제{sequence}회 ")
    ):
        raise DartDocumentError("dart.source_mismatch")
    for name, expected in _LABELS.items():
        node = fields[name]
        labels = [value for value in parents[node] if value.tag == "TD"]
        label = labels[-1] if labels else _one([])
        if _compact(_text(label)) != expected:
            raise DartDocumentError("dart.schema_unsupported")
        add(name + "_label", label)
        if name.endswith("_DT"):
            _date_value(node)
        elif name in {"DNM_SUM", "EXE_PRC", "STK_CNT", "STK_RT", "MIN_PRC"} and (
            not _text(node).isascii() or _NUMBER.fullmatch(_text(node)) is None
        ):
            raise DartDocumentError("dart.schema_unsupported")
    begin_row, end_row = parents[fields["SB_BGN_DT"]], parents[fields["SB_END_DT"]]
    rows = list(parents[begin_row])
    group_labels = [
        node for node in begin_row if node.tag == "TD" and _compact(_text(node)) == "전환청구기간"
    ]
    if (
        len(group_labels) != 1
        or group_labels[0].attrib.get("ROWSPAN") != "2"
        or rows.index(end_row) != rows.index(begin_row) + 1
    ):
        raise DartDocumentError("dart.source_mismatch")
    bind("conversion_group", group_labels[0])
    if not (
        _date_value(fields["DRC_DT"]) <= publication
        and _date_value(fields["DRC_DT"])
        <= _date_value(fields["PYM_DT"])
        <= _date_value(fields["EXP_DT"])
        and _date_value(fields["SB_BGN_DT"])
        <= _date_value(fields["SB_END_DT"])
        <= _date_value(fields["EXP_DT"])
    ):
        raise DartDocumentError("dart.source_mismatch")
    if "정정" not in _text(fields["CRT_RSN"]) or not _text(fields["CRT_PLN"]).endswith("발행 예정"):
        raise DartDocumentError("dart.schema_unsupported")
    grids = [
        table
        for table in tables
        if [_compact(_text(node)) for node in table.findall("./THEAD/TR/TH")]
        == ["항목", "정정사유", "정정전", "정정후"]
    ]
    changed = _grid(_one(grids))[1:]
    if tuple(_compact(_text(row[0])) for row in changed) != _ROWS:
        raise DartDocumentError("dart.correction_mismatch")
    for row, name in zip(
        (changed[0], changed[1], changed[2], changed[4], changed[5]),
        ("EXP_DT", "INT_GV_MTH", "RTN_MTH", "OPT_FCT", "PYM_DT"),
        strict=True,
    ):
        if _text(row[3]) != _text(fields[name]):
            raise DartDocumentError("dart.correction_mismatch")
    if (
        _text(changed[3][3])
        != f"시작일 : {_text(fields['SB_BGN_DT'])}종료일 : {_text(fields['SB_END_DT'])}"
    ):
        raise DartDocumentError("dart.correction_mismatch")
    for index, row in enumerate(changed):
        bind(f"corrected_row_{index}", row[3])
    notes = _notes(correction, section, changed[6])
    for index, node in enumerate(notes):
        bind(f"note23_{index}", node)
        if node.tag == "TABLE":
            for row_index, table_row in enumerate(node.findall("./TBODY/TR")):
                for cell_index, cell in enumerate(table_row):
                    bind(f"note23_{index}_{row_index}_{cell_index}", cell)
    for index, node in enumerate(notes[:9]):
        value = _table_projection(node) if node.tag == "TABLE" else _text(node)
        values.append((f"NOTE23_{index}", value))
    if any(
        value != sequence
        for value in re.findall(r"제\s*(\d+)\s*회", " ".join(value for _, value in values))
    ):
        raise DartDocumentError("dart.source_mismatch")
    bindings.append(DartXmlBinding("issuer_code", path(company) + "/@AREGCIK", corp))
    return _context(item, values, bindings, raw, response_sha256, received_at)


def _context(
    item: NormalizedItem,
    values: list[tuple[str, str]],
    bindings: list[DartXmlBinding],
    raw: bytes,
    response_sha256: str,
    received_at: datetime,
) -> DartDocumentEvidence:
    metadata = cast(dict[str, str], item.raw_metadata)
    paragraphs: list[str] = []
    current = ""
    used = 0
    positions = {}
    for name, value in values:
        line = f"{name}: {value}"
        if len(line) > 1200:
            raise DartDocumentError("dart.context_budget")
        if current and len(current) + 1 + len(line) > 1200:
            paragraphs.append(current)
            used += len(current) + 1
            current = ""
        separator = " " if current else ""
        start = used + len(current) + len(separator) + len(name) + 2
        positions[name] = (start, start + len(value))
        current += separator + line
    paragraphs.append(current)
    projection = "\n".join(paragraphs)
    if len(paragraphs) > 6 or len(projection) > MAX_PROJECTION:
        raise DartDocumentError("dart.context_budget")
    evidence = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary or "",
        detail_excerpt=projection,
        url=str(item.url),
        published_at=item.published_at,
        received_at=received_at,
        published_date=date.fromisoformat(
            metadata["rcept_dt"][:4]
            + "-"
            + metadata["rcept_dt"][4:6]
            + "-"
            + metadata["rcept_dt"][6:8]
        ),
        source_tier="official",
    ).model_copy(update={"evidence_budget_limited": True})
    if evidence.detail_excerpt != projection:
        raise DartDocumentError("dart.context_budget")
    updated = item.model_copy(update={"event_evidence": evidence})
    context = make_event_context_document(
        evidence, metadata=item.raw_metadata, item=updated, article_passages=True
    )
    chunks = []
    for chunk in context.chunks:
        if chunk.source_locator.startswith("detail_excerpt:"):
            _, raw_start, raw_end = chunk.source_locator.split(":")
            chunks.append((int(raw_start), int(raw_end), chunk))
    if len(chunks) != len(paragraphs) or [chunk.text for _, _, chunk in chunks] != paragraphs:
        raise DartDocumentError("dart.context_budget")

    def ref(start: int, end: int) -> ContextRef:
        choices = [(left, chunk) for left, right, chunk in chunks if left <= start < end <= right]
        if len(choices) != 1:
            raise DartDocumentError("dart.context_budget")
        left, chunk = choices[0]
        return ContextRef(
            document_id=context.document_id,
            revision_id=context.revision_id,
            chunk_id=chunk.chunk_id,
            start=start - left,
            end=end - left,
        )

    groups = {
        "issuer": ("issuer",),
        "action": ("action", "SEQ_NO", "PL_KND"),
        "action_status": ("correction", "CRT_RSN", "CRT_PLN", "correction_date"),
    }
    refs = {
        name: tuple(
            ref(start + a, start + b)
            for key in keys
            for start, end in (positions[key],)
            for a, b in _ranges(projection[start:end])
        )
        for name, keys in groups.items()
    }
    refs["action_terms"] = tuple(
        ref(left + a, left + b) for left, _, chunk in chunks for a, b in _ranges(chunk.text)
    )
    summary = next(chunk for chunk in context.chunks if chunk.source_locator.startswith("summary:"))
    filing = metadata["rcept_no"]
    start = summary.text.index(filing)
    refs["filing_locator"] = (
        ContextRef(
            document_id=context.document_id,
            revision_id=context.revision_id,
            chunk_id=summary.chunk_id,
            start=start,
            end=start + len(filing),
        ),
    )
    if any(not 1 <= len(group) <= 16 for group in refs.values()):
        raise DartDocumentError("dart.context_budget")
    return DartDocumentEvidence(
        updated,
        context,
        MappingProxyType(refs),
        tuple(bindings),
        response_sha256,
        hashlib.sha256(raw).hexdigest(),
        PARSER_VERSION,
    )


def parse_dart_terms_document(
    item: NormalizedItem,
    data: bytes,
    *,
    response_sha256: str,
    received_at: datetime,
    forbidden_token: bytes = b"",
) -> DartDocumentEvidence:
    """A reviewed version is explicit; invalid v1 input never triggers this parser."""
    try:
        return _parse(
            item,
            data,
            response_sha256=response_sha256,
            received_at=received_at,
            forbidden_token=forbidden_token,
        )
    except DartDocumentError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, EOFError):
        raise DartDocumentError("dart.source_mismatch") from None
