"""Closed 6.2 treasury-stock trust termination decision; no completion inference."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from types import MappingProxyType
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
    _one,
    _read_xml,
    _text,
)
from investo.sources.dart_disclosure import DartDisclosureAdapter

PARSER_VERSION = "dart-trust-termination-6.2-v1"
REPORT_NAME = "주요사항보고서(자기주식취득신탁계약해지결정)"
_NUMBER = re.compile(r"(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)")
# Row and column ownership are as important as the provider's field codes.
_FIELDS = {
    "CLN_PRC_PRE": (0, "TE", "1.계약금액(원)", "해지전"),
    "CLN_PRC_AFT": (1, "TE", "1.계약금액(원)", "해지후"),
    "CNL_BGN": (2, "TU", "2.해지전계약기간", "시작일"),
    "CNL_END": (3, "TU", "2.해지전계약기간", "종료일"),
    "CNL_PPS": (4, "TE", "3.해지목적", None),
    "CNL_ORG": (5, "TE", "4.해지기관", None),
    "CNL_SCH": (6, "TU", "5.해지예정일자", None),
    "DEC_DATE": (11, "TU", "7.이사회결의일(결정일)", None),
    "CNL_OSTK": (15, "TE", "8.해지예정주식(주)", "보통주식"),
    "CNL_ESTK": (16, "TE", "8.해지예정주식(주)", "기타주식"),
}


def _grid(table: Element) -> list[list[Element]]:
    if [node.tag for node in table] not in (["TBODY"], ["COLGROUP", "TBODY"]):
        raise DartDocumentError("dart.schema_unsupported")
    body = _one(table.findall("./TBODY"))
    if len(body) != 17 or any(node.tag != "TR" for node in body):
        raise DartDocumentError("dart.schema_unsupported")
    occupied: dict[tuple[int, int], Element] = {}
    for row, node in enumerate(body):
        col = 0
        for cell in node:
            while (row, col) in occupied:
                col += 1
            down = int(cell.attrib.get("ROWSPAN", "1"))
            across = int(cell.attrib.get("COLSPAN", "1"))
            if (
                cell.tag not in {"TD", "TE", "TU"}
                or not 1 <= down <= 4
                or not 1 <= across <= 3
                or row + down > 17
                or col + across > 6
            ):
                raise DartDocumentError("dart.schema_unsupported")
            for y in range(row, row + down):
                for x in range(col, col + across):
                    if (y, x) in occupied:
                        raise DartDocumentError("dart.schema_unsupported")
                    occupied[y, x] = cell
            col += across
    if len(occupied) != 17 * 6:
        raise DartDocumentError("dart.schema_unsupported")
    return [[occupied[y, x] for x in range(6)] for y in range(17)]


def _parse(
    item: NormalizedItem,
    data: bytes,
    *,
    response_sha256: str,
    received_at: datetime,
    forbidden_token: bytes,
) -> DartDocumentEvidence:
    received_at = evidence_clock_utc(received_at)
    metadata = item.raw_metadata
    normalized = DartDisclosureAdapter()._normalize_entry(
        metadata, date_precision=metadata.get("published_at_precision") == "date"
    )
    if (
        not data
        or len(data) > MAX_BYTES
        or len(forbidden_token) > 4096
        or hashlib.sha256(data).hexdigest() != response_sha256
        or normalized is None
        or item.source_name != "dart-disclosure"
        or item.category != "news"
        or any(
            getattr(item, key) != getattr(normalized, key)
            for key in ("title", "summary", "url", "published_at", "raw_metadata")
        )
        or any(not isinstance(value, str) or len(value) > 300 for value in metadata.values())
    ):
        raise DartDocumentError("dart.source_mismatch")
    filing, corp = str(metadata.get("rcept_no", "")), str(metadata.get("corp_code", ""))
    if (
        not re.fullmatch(r"[0-9]{14}", filing)
        or not re.fullmatch(r"[0-9]{8}", corp)
        or metadata.get("rcept_dt") != filing[:8]
        or _compact(str(metadata.get("report_nm", ""))) != REPORT_NAME
        or (forbidden_token and forbidden_token.decode() in " ".join(map(str, metadata.values())))
    ):
        raise DartDocumentError("dart.source_mismatch")
    root, raw = _read_xml(data, filing + ".xml", forbidden_token)
    document = _one(root.findall("./DOCUMENT-NAME"))
    version = _one(root.findall("./FORMULA-VERSION"))
    company = _one(root.findall("./COMPANY-NAME"))

    def company_name(value: str) -> str:
        return re.sub(r"^(?:\(주\)|주식회사)|(?:\(주\)|주식회사)$", "", _compact(value))

    if (
        root.tag != "DOCUMENT"
        or document.attrib.get("ACODE") != "11335"
        or _compact(_text(document)) != REPORT_NAME
        or _text(version) != "6.2"
        or version.attrib.get("ADATE") != "20260723"
        or company.attrib.get("AREGCIK") != corp
        or company_name(_text(company)) != company_name(str(metadata.get("corp_name", "")))
        or root.findall(".//CORRECTION")
    ):
        raise DartDocumentError("dart.schema_unsupported")
    parents = {child: parent for parent in root.iter() for child in parent}
    group = _one(root.findall(".//TABLE-GROUP[@ACLASS='TBL_ACQ_CNL']"))
    table = _one(group.findall("./TABLE"))
    section = parents[group]
    title = _one(section.findall("./TITLE"))
    if section.tag != "SECTION-1" or _compact(_text(title)) != "자기주식취득신탁계약해지결정":
        raise DartDocumentError("dart.schema_unsupported")
    grid = _grid(table)
    values: list[tuple[str, Element, str]] = []

    def add(name: str, node: Element) -> None:
        text = _text(node)
        if not text or len(text) > 240:
            raise DartDocumentError("dart.context_budget")
        values.append((name, node, text))

    add("issuer", company)
    add("action", document)
    add("decision", title)
    fields = {}
    for code, (row, tag, label, sublabel) in _FIELDS.items():
        attr = "ACODE" if tag == "TE" else "AUNIT"
        node = _one(
            [n for n in root.iter() if code in (n.attrib.get("ACODE"), n.attrib.get("AUNIT"))]
        )
        if (
            node.tag != tag
            or node.attrib.get(attr) != code
            or (
                tag == "TU" and re.fullmatch(r"[0-9]{8}", node.attrib.get("AUNITVALUE", "")) is None
            )
            or any(grid[row][col] is not node for col in (3, 4, 5))
            or grid[row][0].tag != "TD"
            or any(grid[row][col] is not grid[row][0] for col in range(2 if sublabel else 3))
            or (sublabel and grid[row][2].tag != "TD")
            or _compact(_text(grid[row][0])) != label
            or (sublabel and _compact(_text(grid[row][2])) != sublabel)
        ):
            raise DartDocumentError("dart.schema_unsupported")
        fields[code] = node
        add(code + "_label", grid[row][0])
        if sublabel:
            add(code + "_kind", grid[row][2])
        add(code, node)
    for code in ("CLN_PRC_PRE", "CLN_PRC_AFT", "CNL_OSTK", "CNL_ESTK"):
        value = _text(fields[code])
        if not _NUMBER.fullmatch(value) and not (code != "CLN_PRC_PRE" and value == "-"):
            raise DartDocumentError("dart.schema_unsupported")
    dates = {
        code: _date_value(fields[code]) for code in ("CNL_BGN", "CNL_END", "CNL_SCH", "DEC_DATE")
    }
    cover = _one(
        [s for s in root.findall(".//SECTION-1") if s is not section and bool(s.findall("./TITLE"))]
    )
    cover_day = _one(
        [
            n
            for n in cover.findall("./TABLE/TBODY/TR/TD")
            if re.fullmatch(r"\d{4}년\d{1,2}월\d{1,2}일", _compact(_text(n)))
        ]
    )
    publication = normalized.published_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    if (
        _date_value(cover_day) != publication
        or publication > received_at.astimezone(ZoneInfo("Asia/Seoul")).date()
        or not dates["CNL_BGN"] <= dates["DEC_DATE"] <= dates["CNL_END"]
        or not dates["DEC_DATE"] <= publication
        or dates["CNL_SCH"] < dates["DEC_DATE"]
    ):
        raise DartDocumentError("dart.source_mismatch")
    add("filing_date", cover_day)
    children = list(section)
    heading = _one(
        [
            n
            for n in children
            if n.tag == "TABLE" and _compact(_text(n)) == "9.기타투자판단에참고할사항"
        ]
    )
    following = children[children.index(heading) + 1 :]
    end = next((i for i, n in enumerate(following) if n.tag == "TABLE-GROUP"), None)
    if (
        end is None
        or following[end].attrib.get("ACLASS") != "TBL_OWN_STK"
        or children.index(group) >= children.index(heading)
    ):
        raise DartDocumentError("dart.schema_unsupported")
    notes = [n for n in following[:end] if _text(n)]
    note = _one(notes)
    if note.tag != "P":
        raise DartDocumentError("dart.schema_unsupported")
    add("notes", note)
    projection = "\n".join(f"{name}: {value}" for name, _, value in values)
    if len(projection) > 1200:
        raise DartDocumentError("dart.context_budget")
    updated_metadata = {
        **metadata,
        "published_at_precision": "date",
        "published_date": publication.isoformat(),
    }
    evidence = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary or "",
        detail_excerpt=projection,
        url=str(item.url),
        published_at=item.published_at,
        published_date=publication,
        received_at=received_at,
        source_tier="official",
    ).model_copy(update={"evidence_budget_limited": True})
    updated = item.model_copy(update={"raw_metadata": updated_metadata, "event_evidence": evidence})
    context = make_event_context_document(evidence, metadata=updated_metadata, item=updated)
    chunk = next(c for c in context.chunks if c.source_locator.startswith("detail_excerpt:"))
    positions = {}
    cursor = 0
    for name, _, value in values:
        start = cursor + len(name) + 2
        positions[name] = ContextRef(
            document_id=context.document_id,
            revision_id=context.revision_id,
            chunk_id=chunk.chunk_id,
            start=start,
            end=start + len(value),
        )
        cursor = start + len(value) + 1
    summary = next(c for c in context.chunks if c.source_locator.startswith("summary:"))
    start = summary.text.index(filing)
    groups = {
        "issuer": ("issuer",),
        "action": ("action",),
        "action_status": (
            "decision",
            "DEC_DATE_label",
            "DEC_DATE",
            "CNL_SCH_label",
            "CNL_SCH",
            "CNL_PPS_label",
            "CNL_PPS",
            "notes",
            "filing_date",
            "CNL_BGN_label",
            "CNL_BGN_kind",
            "CNL_BGN",
            "CNL_END_kind",
            "CNL_END",
        ),
        "action_terms": (
            "CLN_PRC_PRE_label",
            "CLN_PRC_PRE_kind",
            "CLN_PRC_PRE",
            "CLN_PRC_AFT_kind",
            "CLN_PRC_AFT",
            "CNL_ORG_label",
            "CNL_ORG",
            "CNL_OSTK_label",
            "CNL_OSTK_kind",
            "CNL_OSTK",
            "CNL_ESTK_kind",
            "CNL_ESTK",
        ),
    }
    refs = {name: tuple(positions[key] for key in keys) for name, keys in groups.items()}
    refs["filing_locator"] = (
        ContextRef(
            document_id=context.document_id,
            revision_id=context.revision_id,
            chunk_id=summary.chunk_id,
            start=start,
            end=start + len(filing),
        ),
    )

    def path(node: Element) -> str:
        parts = []
        while node is not root:
            parent = parents[node]
            siblings = [child for child in parent if child.tag == node.tag]
            parts.append(f"{node.tag}[{siblings.index(node) + 1}]")
            node = parent
        return "DOCUMENT/" + "/".join(reversed(parts))

    bindings = tuple(DartXmlBinding(name, path(node), value) for name, node, value in values)
    bindings += (DartXmlBinding("issuer_code", path(company) + "/@AREGCIK", corp),)
    return DartDocumentEvidence(
        updated,
        context,
        MappingProxyType(refs),
        bindings,
        response_sha256,
        hashlib.sha256(raw).hexdigest(),
        PARSER_VERSION,
    )


def parse_dart_trust_document(
    item: NormalizedItem,
    data: bytes,
    *,
    response_sha256: str,
    received_at: datetime,
    forbidden_token: bytes = b"",
) -> DartDocumentEvidence:
    """No live permission; return only exact source literals or a closed error."""
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
