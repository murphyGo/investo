"""Offline, closed-form evidence for the existing DART disclosure source.

No fetch or capability registration happens here. An approved private ZIP and
its listing item are required; unknown forms remain unsupported.
"""

from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
import zlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Protocol, cast
from zoneinfo import ZoneInfo

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from investo.models.event_context import ContextRef, EventContextDocument
from investo.models.event_evidence import (
    evidence_clock_utc,
    make_event_context_document,
    make_evidence_document,
    normalize_evidence_text,
)
from investo.models.items import NormalizedItem


class Element(Protocol):
    """The read-only tree interface supplied by the defusedxml parser."""

    tag: str
    attrib: dict[str, str]

    def __iter__(self) -> Iterator[Element]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> Element: ...
    def itertext(self) -> Iterator[str]: ...
    def iter(self, tag: str | None = None) -> Iterator[Element]: ...
    def findall(self, path: str) -> list[Element]: ...


PARSER_VERSION = "dart-cb-correction-6.4-v1"
MAX_BYTES = 500 * 1024
_FORM = "주요사항보고서(전환사채권발행결정)"
_NUMBER = re.compile(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?")


class DartDocumentError(ValueError):
    """Only closed diagnostics cross the private source boundary."""


@dataclass(frozen=True, slots=True)
class DartXmlBinding:
    name: str
    path: str = field(repr=False)
    value: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class DartDocumentEvidence:
    item: NormalizedItem = field(repr=False)
    context: EventContextDocument = field(repr=False)
    field_refs: Mapping[str, tuple[ContextRef, ...]] = field(repr=False)
    xml_bindings: tuple[DartXmlBinding, ...] = field(repr=False)
    response_sha256: str
    xml_sha256: str
    parser_version: str = PARSER_VERSION


def _text(node: Element) -> str:
    return " ".join(normalize_evidence_text("".join(node.itertext())).split())


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", normalize_evidence_text(text))


def _one(nodes: list[Element]) -> Element:
    if len(nodes) != 1:
        raise DartDocumentError("dart.field_missing" if not nodes else "dart.field_ambiguous")
    return nodes[0]


def _read_xml(data: bytes, filename: str, forbidden_token: bytes) -> tuple[Element, bytes]:
    if not data or len(data) > MAX_BYTES:
        raise DartDocumentError("dart.byte_limit")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if not 1 <= len(members) <= 16 or sum(m.file_size for m in members) > MAX_BYTES:
                raise DartDocumentError("dart.byte_limit")
            if len({m.filename.casefold() for m in members}) != len(members) or any(
                m.flag_bits & 1
                or m.orig_filename != m.filename
                or "\x00" in m.orig_filename
                or m.is_dir()
                or m.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                or stat.S_ISLNK(m.external_attr >> 16)
                or PurePosixPath(m.filename).is_absolute()
                or ".." in PurePosixPath(m.filename).parts
                or "\\" in m.filename
                for m in members
            ):
                raise DartDocumentError("dart.archive_invalid")
            if len(members) != 1 or members[0].filename != filename:
                raise DartDocumentError("dart.source_mismatch")
            with archive.open(members[0]) as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise DartDocumentError("dart.byte_limit")
        # This version supports the captured UTF-8 form only; unknown encodings
        # never become opaque text that bypasses credential or field checks.
        decoded = raw.decode("utf-8-sig")
        if "\x00" in decoded:
            raise DartDocumentError("dart.xml_invalid")
        encoding = re.match(r"\s*<\?xml\b[^?]*encoding\s*=\s*[\"']([^\"']+)", decoded)
        if encoding and encoding[1].casefold() not in {"utf-8", "utf8"}:
            raise DartDocumentError("dart.xml_invalid")
        if forbidden_token and forbidden_token in raw:
            raise DartDocumentError("dart.credential_echo")
        root = cast(
            Element,
            fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True),
        )
        pending = [(root, 0)]
        count = 0
        secret = forbidden_token.decode("utf-8") if forbidden_token else ""
        while pending:
            node, depth = pending.pop()
            count += 1
            if depth > 256 or count > 20000:
                raise DartDocumentError("dart.xml_limit")
            if secret and any(
                secret in value for value in (node.tag, *node.attrib, *node.attrib.values())
            ):
                raise DartDocumentError("dart.credential_echo")
            pending.extend((child, depth + 1) for child in node)
        if secret and secret in "".join(root.itertext()):
            raise DartDocumentError("dart.credential_echo")
        return root, raw
    except DartDocumentError:
        raise
    except (
        zipfile.BadZipFile,
        RuntimeError,
        ParseError,
        DefusedXmlException,
        LookupError,
        UnicodeError,
        zlib.error,
        OSError,
    ):
        raise DartDocumentError("dart.xml_invalid") from None


def _grid(table: Element) -> list[list[Element]]:
    """Expand only a bounded, complete correction table; no first-number scan."""
    rows = table.findall("./THEAD/TR") + table.findall("./TBODY/TR")
    if not 2 <= len(rows) <= 32:
        raise DartDocumentError("dart.correction_mismatch")
    cells: dict[tuple[int, int], Element] = {}
    for row, tr in enumerate(rows):
        column = 0
        for cell in tr:
            if cell.tag not in {"TH", "TD"}:
                raise DartDocumentError("dart.correction_mismatch")
            while (row, column) in cells:
                column += 1
            try:
                down = int(cell.attrib.get("ROWSPAN", "1"))
                across = int(cell.attrib.get("COLSPAN", "1"))
            except ValueError:
                raise DartDocumentError("dart.correction_mismatch") from None
            if (
                not (1 <= down <= 32 and 1 <= across <= 4)
                or row + down > len(rows)
                or column + across > 4
            ):
                raise DartDocumentError("dart.correction_mismatch")
            for r in range(row, row + down):
                for c in range(column, column + across):
                    if (r, c) in cells:
                        raise DartDocumentError("dart.correction_mismatch")
                    cells[r, c] = cell
            column += across
    if set(cells) != {(r, c) for r in range(len(rows)) for c in range(4)}:
        raise DartDocumentError("dart.correction_mismatch")
    return [[cells[r, c] for c in range(4)] for r in range(len(rows))]


def _date_value(node: Element) -> date:
    text = _text(node)
    match = re.fullmatch(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if match is None:
        raise DartDocumentError("dart.schema_unsupported")
    try:
        value = date(*(int(v) for v in match.groups()))
    except ValueError:
        raise DartDocumentError("dart.schema_unsupported") from None
    encoded = node.attrib.get("AUNITVALUE")
    if encoded is not None and encoded != value.strftime("%Y%m%d"):
        raise DartDocumentError("dart.source_mismatch")
    return value


def _parse_document(
    item: NormalizedItem,
    data: bytes,
    *,
    response_sha256: str,
    received_at: datetime,
    forbidden_token: bytes = b"",
) -> DartDocumentEvidence:
    """Preserve a listing while binding five slots to one corrected XML form.

    The caller supplies a captured response digest, not a URL or credentials.
    No live source permission or operational qualification is granted.
    """
    if not data or len(data) > MAX_BYTES:
        raise DartDocumentError("dart.byte_limit")
    received_at = evidence_clock_utc(received_at)
    evidence_clock_utc(item.published_at)
    metadata = item.raw_metadata

    def listing_text(key: str) -> str:
        value = metadata.get(key)
        if not isinstance(value, str) or not value:
            raise DartDocumentError("dart.source_mismatch")
        return value

    filing = listing_text("rcept_no")
    corp = listing_text("corp_code")
    company_name = listing_text("corp_name")
    report_name = listing_text("report_nm")
    allowed_metadata = {
        "corp_code",
        "corp_name",
        "report_nm",
        "rcept_no",
        "rcept_dt",
        "subcategory",
        "stock_code",
        "corp_cls",
        "published_at_precision",
        "published_date",
        "published_timezone",
        "event_date",
        "event_time_basis",
    }
    if (
        item.source_name != "dart-disclosure"
        or item.category != "news"
        or not metadata.keys() <= allowed_metadata
        or any(not isinstance(value, str) or len(value) > 300 for value in metadata.values())
        or not re.fullmatch(r"[0-9]{14}", filing)
        or not re.fullmatch(r"[0-9]{8}", corp)
        or metadata.get("rcept_dt") != filing[:8]
        or str(item.url) != f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing}"
        or item.title != f"[DART] {company_name} - {report_name}"[:140]
        or item.summary != f"{report_name} (접수번호 {filing})"
        or not re.fullmatch(r"[0-9a-f]{64}", response_sha256)
        or hashlib.sha256(data).hexdigest() != response_sha256
        or len(forbidden_token) > 4096
    ):
        raise DartDocumentError("dart.source_mismatch")
    if forbidden_token and forbidden_token.decode("utf-8") in " ".join(
        (item.title, item.summary or "", *(str(value) for value in metadata.values()))
    ):
        raise DartDocumentError("dart.credential_echo")
    try:
        publication_day = date.fromisoformat(f"{filing[:4]}-{filing[4:6]}-{filing[6:8]}")
    except ValueError:
        raise DartDocumentError("dart.source_mismatch") from None
    if metadata.get("published_date", publication_day.isoformat()) != publication_day.isoformat():
        raise DartDocumentError("dart.source_mismatch")
    if (
        metadata.get("event_date", publication_day.isoformat()) != publication_day.isoformat()
        or metadata.get("published_at_precision", "date") != "date"
        or metadata.get("published_timezone", "Asia/Seoul") != "Asia/Seoul"
        or metadata.get("event_time_basis", "source_date") != "source_date"
    ):
        raise DartDocumentError("dart.source_mismatch")
    if (
        item.published_at.astimezone(ZoneInfo("Asia/Seoul")).date() != publication_day
        or publication_day > received_at.astimezone(ZoneInfo("Asia/Seoul")).date()
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
        or _compact(report_name) != "[기재정정]" + _FORM
    ):
        raise DartDocumentError("dart.schema_unsupported")

    def company_key(value: str) -> str:
        return re.sub(r"^(?:\(주\)|주식회사)|(?:\(주\)|주식회사)$", "", _compact(value))

    if company_key(_text(company)) != company_key(company_name):
        raise DartDocumentError("dart.source_mismatch")
    parents = {child: parent for parent in root.iter() for child in parent}

    def path(node: Element) -> str:
        parts = []
        while node is not root:
            parent = parents[node]
            siblings = [child for child in parent if child.tag == node.tag]
            parts.append(f"{node.tag}[{siblings.index(node) + 1}]")
            node = parent
        return "DOCUMENT/" + "/".join(reversed(parts))

    values: list[tuple[str, Element, str]] = []

    def add(name: str, node: Element) -> str:
        value = _text(node)
        if not value or len(value) > 180:
            raise DartDocumentError("dart.context_budget")
        values.append((name, node, value))
        return value

    add("issuer", company)
    add("action", document)
    correction_title = _one(correction.findall("./TITLE"))
    if _compact(_text(correction_title)) != "정정신고(보고)":
        raise DartDocumentError("dart.schema_unsupported")
    add("correction", correction_title)
    correction_tables = correction.findall("./TABLE")
    correction_day = (
        _one(correction_tables[0].findall("./TBODY/TR[2]/TD")) if correction_tables else _one([])
    )
    if _date_value(correction_day) != publication_day:
        raise DartDocumentError("dart.source_mismatch")
    add("correction_date", correction_day)
    original_date_rows = [
        list(tr)
        for table in correction_tables
        for tr in table.findall("./TBODY/TR")
        if len(tr) == 2 and _compact(_text(tr[0])) == "2.정정대상공시서류의최초제출일:"
    ]
    if len(original_date_rows) != 1:
        raise DartDocumentError("dart.field_ambiguous")
    _date_value(original_date_rows[0][1])
    add("original_submission_date", original_date_rows[0][1])
    # Require unique ACODEs across the body, excluding historical correction
    # tables. The main issue identifiers and terms must share the same table.
    body_sections = root.findall("./BODY/SECTION-1")
    fields: dict[str, Element] = {}
    for name in (
        "SEQ_NO",
        "PL_KND",
        "DNM_SUM",
        "EXE_PRC",
        "STK_CNT",
        "STK_RT",
        "MIN_PRC",
        "CRT_RSN",
        "CRT_PLN",
    ):
        fields[name] = _one(
            [n for s in body_sections for n in s.iter("TE") if n.attrib.get("ACODE") == name]
        )
        add(name, fields[name])

    def ancestor(node: Element, tag: str) -> Element:
        while node is not root and node.tag != tag:
            node = parents[node]
        return node

    main = ancestor(fields["DNM_SUM"], "TABLE")
    if any(
        ancestor(fields[n], "TABLE") is not main
        for n in ("SEQ_NO", "PL_KND", "EXE_PRC", "STK_CNT", "STK_RT", "MIN_PRC")
    ):
        raise DartDocumentError("dart.source_mismatch")
    if (
        ancestor(fields["CRT_RSN"], "SECTION-1") is not ancestor(main, "SECTION-1")
        or ancestor(fields["CRT_PLN"], "SECTION-1") is not ancestor(main, "SECTION-1")
        or ancestor(fields["CRT_RSN"], "TABLE") is not ancestor(fields["CRT_PLN"], "TABLE")
    ):
        raise DartDocumentError("dart.source_mismatch")
    sequence = _text(fields["SEQ_NO"])
    if (
        not sequence.isascii()
        or not sequence.isdigit()
        or not _text(fields["PL_KND"]).startswith(f"제{sequence}회 ")
    ):
        raise DartDocumentError("dart.source_mismatch")
    for name in ("DNM_SUM", "EXE_PRC", "STK_CNT", "STK_RT", "MIN_PRC"):
        if not _text(fields[name]).isascii() or _NUMBER.fullmatch(_text(fields[name])) is None:
            raise DartDocumentError("dart.schema_unsupported")
        labels = [n for n in parents[fields[name]] if n.tag == "TD"]
        if not labels:
            raise DartDocumentError("dart.field_missing")
        label = labels[-1]
        expected = {
            "DNM_SUM": "2.사채의권면(전자등록)총액(원)",
            "EXE_PRC": "전환가액(원/주)",
            "STK_CNT": "주식수",
            "STK_RT": "주식총수대비비율(%)",
            "MIN_PRC": "최저조정가액(원)",
        }
        if _compact(_text(label)) != expected[name]:
            raise DartDocumentError("dart.schema_unsupported")
        add(name + "_label", label)
    # A correction must retain its own explicit state. This parser does not
    # turn the completed filing decision into completed issuance/payment.
    if "정정" not in _text(fields["CRT_RSN"]) or not _text(fields["CRT_PLN"]).endswith("발행 예정"):
        raise DartDocumentError("dart.schema_unsupported")
    tables = [
        t
        for t in correction.findall("./TABLE")
        if [_compact(_text(n)) for n in t.findall("./THEAD/TR/TH")]
        == ["항목", "정정사유", "정정전", "정정후"]
    ]
    grid = _grid(_one(tables))
    changed = {_compact(_text(row[0])): row for row in grid[1:]}
    supported_rows = {
        "9.전환에관한사항-전환가액",
        "-최저조정가액",
        "-전환에따라발행할주식",
        "【미상환주권관련사채권에관한사항】",
    }
    if len(changed) != len(grid) - 1 or not changed.keys() <= supported_rows:
        raise DartDocumentError("dart.correction_mismatch")
    price = [row for label, row in changed.items() if label == "9.전환에관한사항-전환가액"]
    floor = [row for label, row in changed.items() if label == "-최저조정가액"]
    shares = [row for label, row in changed.items() if label == "-전환에따라발행할주식"]
    if len(price) != 1 or len(floor) != 1 or len(shares) != 1:
        raise DartDocumentError("dart.correction_mismatch")
    share_after = re.fullmatch(
        r"-\s*주식수\s*:\s*([0-9,]+)\s*-\s*주식총수대비비율\(%\)\s*:\s*([0-9.]+)",
        _text(shares[0][3]),
    )
    if (
        _text(price[0][3]) != _text(fields["EXE_PRC"])
        or _text(floor[0][3]) != _text(fields["MIN_PRC"])
        or share_after is None
        or share_after[1] != _text(fields["STK_CNT"])
        or share_after[2] != _text(fields["STK_RT"])
    ):
        raise DartDocumentError("dart.correction_mismatch")
    for name in ("DRC_DT", "PYM_DT", "EXP_DT"):
        node = _one([n for n in main.iter("TU") if n.attrib.get("AUNIT") == name])
        _date_value(node)
        add(name, node)
        labels = [n for n in parents[node] if n.tag == "TD"]
        if not labels:
            raise DartDocumentError("dart.field_missing")
        expected_date_labels = {
            "DRC_DT": "17.이사회결의일(결정일)",
            "PYM_DT": "12.납입일",
            "EXP_DT": "5.사채만기일",
        }
        if _compact(_text(labels[-1])) != expected_date_labels[name]:
            raise DartDocumentError("dart.schema_unsupported")
        add(name + "_label", labels[-1])
    projection = "\n".join(f"{name}: {value}" for name, _, value in values)
    if len(projection) > 1200:
        raise DartDocumentError("dart.context_budget")
    updated_metadata = {
        **metadata,
        "published_at_precision": "date",
        "published_date": publication_day.isoformat(),
    }
    evidence = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary or "",
        detail_excerpt=projection,
        url=str(item.url),
        published_at=item.published_at,
        published_date=publication_day,
        received_at=received_at,
        source_tier="official",
    )
    evidence = evidence.model_copy(update={"evidence_budget_limited": True})
    updated = item.model_copy(update={"raw_metadata": updated_metadata, "event_evidence": evidence})
    context = make_event_context_document(evidence, metadata=updated_metadata, item=updated)
    chunk = next(c for c in context.chunks if c.source_locator.startswith("detail_excerpt:"))
    positions: dict[str, ContextRef] = {}
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
    locator = ContextRef(
        document_id=context.document_id,
        revision_id=context.revision_id,
        chunk_id=summary.chunk_id,
        start=start,
        end=start + len(filing),
    )
    terms = ("DNM_SUM", "EXE_PRC", "STK_CNT", "STK_RT", "MIN_PRC", "DRC_DT", "PYM_DT", "EXP_DT")
    groups = {
        "issuer": ("issuer",),
        "action": ("action", "SEQ_NO", "PL_KND"),
        "action_status": ("correction", "CRT_RSN", "CRT_PLN", "correction_date"),
        "action_terms": tuple(key for name in terms for key in (name, name + "_label")),
    }
    refs = {name: tuple(positions[key] for key in keys) for name, keys in groups.items()}
    refs["filing_locator"] = (locator,)
    bindings = tuple(DartXmlBinding(name, path(node), value) for name, node, value in values)
    bindings += (
        DartXmlBinding("issuer_code", path(company) + "/@AREGCIK", corp),
        DartXmlBinding("corrected_price", path(price[0][3]), _text(price[0][3])),
        DartXmlBinding("corrected_floor", path(floor[0][3]), _text(floor[0][3])),
        DartXmlBinding("corrected_shares", path(shares[0][3]), _text(shares[0][3])),
    )
    return DartDocumentEvidence(
        updated,
        context,
        MappingProxyType(refs),
        bindings,
        response_sha256,
        hashlib.sha256(raw).hexdigest(),
    )


def parse_dart_document(
    item: NormalizedItem,
    data: bytes,
    *,
    response_sha256: str,
    received_at: datetime,
    forbidden_token: bytes = b"",
) -> DartDocumentEvidence:
    """Offline parser; invalid source values never become raw exception details."""
    try:
        return _parse_document(
            item,
            data,
            response_sha256=response_sha256,
            received_at=received_at,
            forbidden_token=forbidden_token,
        )
    except DartDocumentError:
        raise
    except (ValueError, TypeError, EOFError):
        raise DartDocumentError("dart.source_mismatch") from None
