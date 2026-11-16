"""One private DART document qualification probe; never generate or publish."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import stat
import subprocess
import zipfile
import zlib
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from time import monotonic

import httpx
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from investo._internal.event_context import resolve_context_ref
from investo.models.event_evidence import normalize_evidence_text
from investo.sources._dart_document import DartDocumentError, parse_dart_document
from investo.sources.dart_disclosure import DartDisclosureAdapter

MAX_BYTES = 500 * 1024
MAX_FILES = 16
_ENDPOINT = "https://opendart.fss.or.kr/api/document.xml"
_LIST_ENDPOINT = "https://opendart.fss.or.kr/api/list.json"
_API_CODES = {"010", "011", "012", "013", "014", "020", "100", "101", "800", "900", "901"}


def inspect_document(data: bytes, *, forbidden_token: bytes = b"") -> dict[str, object]:
    """Bound compressed and expanded data; inspect structure without inferring facts."""
    if not data or len(data) > MAX_BYTES:
        raise ValueError("document.byte_limit")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= MAX_FILES:
                raise ValueError("document.member_limit")
            if any(
                entry.flag_bits & 1
                or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                or entry.is_dir()
                or PurePosixPath(entry.filename).is_absolute()
                or ".." in PurePosixPath(entry.filename).parts
                or "\\" in entry.filename
                or not entry.filename.casefold().endswith(".xml")
                or stat.S_ISLNK(entry.external_attr >> 16)
                for entry in entries
            ):
                raise ValueError("document.member_invalid")
            if sum(entry.file_size for entry in entries) > MAX_BYTES:
                raise ValueError("document.expanded_limit")
            expanded = nodes = 0
            for entry in entries:
                with archive.open(entry) as handle:
                    raw = handle.read(MAX_BYTES - expanded + 1)
                expanded += len(raw)
                if expanded > MAX_BYTES:
                    raise ValueError("document.expanded_limit")
                # Preserve no key in comments, names or processing instructions,
                # including XML encodings whose bytes differ from UTF-8.
                if forbidden_token and any(
                    forbidden_token.decode().encode(encoding) in raw
                    for encoding in ("utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be")
                ):
                    raise ValueError("document.credential_echo")
                root = fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                if forbidden_token and forbidden_token.decode() in "".join(root.itertext()):
                    raise ValueError("document.credential_echo")
                pending = [(root, 0)]
                while pending:
                    node, depth = pending.pop()
                    nodes += 1
                    if depth > 256 or nodes > 20000:
                        raise ValueError("document.xml_limit")
                    if forbidden_token and any(
                        forbidden_token.decode() in value
                        for value in (node.tag, *node.attrib.keys(), *node.attrib.values())
                    ):
                        raise ValueError("document.credential_echo")
                    pending.extend((child, depth + 1) for child in node)
    except (
        zipfile.BadZipFile,
        RuntimeError,
        ParseError,
        DefusedXmlException,
        LookupError,
        zlib.error,
    ) as exc:
        raise ValueError("document.invalid") from exc
    return {"xml_files": len(entries), "expanded_bytes": expanded, "xml_nodes": nodes}


async def probe_document(
    client: httpx.AsyncClient, *, filing_no: str, credential: str
) -> tuple[dict[str, object], bytes | None]:
    """One fixed-host GET, no redirects/retries; no credential-bearing errors escape."""
    if not re.fullmatch(r"[0-9]{14}", filing_no):
        raise ValueError("document.filing_invalid")
    receipt: dict[str, object] = {
        "filing_no": filing_no,
        "request_count": 0,
        "source_slot_verified": False,
        "activation_ready": False,
        "publication_committed": False,
        "notification_sent": False,
    }
    if not credential:
        return {**receipt, "status": "blocked", "reason": "credential_missing"}, None
    # This is a dedicated, single-source diagnostic process. HTTPX request logs
    # otherwise contain its required query credential even with a safe client.
    levels = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}
    for name in levels:
        logging.getLogger(name).setLevel(logging.CRITICAL)
    receipt["request_count"] = 1
    started = monotonic()
    receipt["request_started_at"] = datetime.now(UTC).isoformat()
    try:
        async with asyncio.timeout(20):
            async with client.stream(
                "GET",
                _ENDPOINT,
                params={"crtfc_key": credential, "rcept_no": filing_no},
                headers={"Accept-Encoding": "identity"},
                timeout=8,
                follow_redirects=False,
            ) as response:
                receipt["http_status"] = response.status_code
                if response.status_code != 200:
                    return {**receipt, "status": "blocked", "reason": "http_unavailable"}, None
                if response.headers.get("content-encoding", "identity").casefold() != "identity":
                    return {**receipt, "status": "blocked", "reason": "content_encoding"}, None
                chunks = bytearray()
                stream = (
                    response.aiter_bytes(chunk_size=16384)
                    if response.is_stream_consumed
                    else response.aiter_raw(chunk_size=16384)
                )
                async for chunk in stream:
                    if len(chunks) + len(chunk) > MAX_BYTES:
                        return {**receipt, "status": "blocked", "reason": "byte_limit"}, None
                    chunks.extend(chunk)
                receipt["received_at"] = datetime.now(UTC).isoformat()
                receipt["elapsed_seconds"] = round(monotonic() - started, 6)
        data = bytes(chunks)
        if credential.encode() in data:
            return {**receipt, "status": "blocked", "reason": "credential_echo"}, None
        receipt.update(response_bytes=len(data), response_sha256=hashlib.sha256(data).hexdigest())
        if not data.startswith(b"PK"):
            try:
                root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                code = root.findtext("status")
            except (ParseError, DefusedXmlException, ValueError, LookupError):
                code = None
            return {
                **receipt,
                "status": "blocked",
                "reason": "provider_error",
                "provider_code": code if code in _API_CODES else "other",
            }, None
        receipt.update(inspect_document(data, forbidden_token=credential.encode()))
        return {**receipt, "status": "captured", "reason": "parser_qualification_pending"}, data
    except (httpx.HTTPError, TimeoutError, ValueError, OSError):
        return {**receipt, "status": "blocked", "reason": "request_or_document_invalid"}, None
    finally:
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("listing.json_invalid")
        result[key] = value
    return result


async def _fetch_listing(
    client: httpx.AsyncClient,
    *,
    filing_no: str,
    corp_code: str,
    credential: str,
    receipt: dict[str, object],
) -> tuple[dict[str, object], bytes]:
    receipt["request_count"] = 1
    receipt["listing_started_at"] = datetime.now(UTC).isoformat()
    async with client.stream(
        "GET",
        _LIST_ENDPOINT,
        params={
            "crtfc_key": credential,
            "corp_code": corp_code,
            "bgn_de": filing_no[:8],
            "end_de": filing_no[:8],
            "last_reprt_at": "N",
            "page_no": "1",
            "page_count": "100",
        },
        headers={"Accept-Encoding": "identity"},
        timeout=8,
        follow_redirects=False,
    ) as response:
        receipt["listing_http_status"] = response.status_code
        if response.status_code != 200:
            raise ValueError("listing.http_unavailable")
        if response.headers.get("content-encoding", "identity").casefold() != "identity":
            raise ValueError("listing.content_encoding")
        data = bytearray()
        stream = (
            response.aiter_bytes(chunk_size=16384)
            if response.is_stream_consumed
            else response.aiter_raw(chunk_size=16384)
        )
        async for chunk in stream:
            if len(data) + len(chunk) > MAX_BYTES:
                raise ValueError("listing.byte_limit")
            data.extend(chunk)
        receipt["listing_received_at"] = datetime.now(UTC).isoformat()
    raw = bytes(data)
    payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    if credential in json.dumps(payload, ensure_ascii=False):
        raise ValueError("listing.credential_echo")
    if not isinstance(payload, dict) or payload.get("status") != "000":
        raise ValueError("listing.provider_error")
    if DartDisclosureAdapter._pagination(payload, 1) is None:
        raise ValueError("listing.pagination_invalid")
    entries = payload.get("list")
    if (
        str(payload["total_page"]) != "1"
        or not isinstance(entries, list)
        or not 1 <= len(entries) <= 100
        or len(entries) != int(payload["total_count"])
    ):
        raise ValueError("listing.incomplete")
    if any(
        not DartDisclosureAdapter._well_formed_entry(entry)
        or entry["corp_code"] != corp_code
        or entry["rcept_dt"] != filing_no[:8]
        for entry in entries
    ) or len({entry["rcept_no"] for entry in entries}) != len(entries):
        raise ValueError("listing.identity_invalid")
    matches = [entry for entry in entries if entry["rcept_no"] == filing_no]
    if len(matches) != 1:
        raise ValueError("listing.target_missing")
    remark = matches[0].get("rm", "")
    if not isinstance(remark, str):
        raise ValueError("listing.identity_invalid")
    receipt.update(
        listing_bytes=len(raw),
        listing_sha256=hashlib.sha256(raw).hexdigest(),
        listing_entries=len(entries),
        listing_follow_up=(
            "withdrawn"
            if "철" in remark
            else "superseded"
            if "정" in remark
            else "none"
            if not remark.strip()
            else "other"
        ),
    )
    return matches[0], raw


async def probe_qualification(
    client: httpx.AsyncClient, *, filing_no: str, corp_code: str, credential: str
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Fresh responses for one historical filing; never enable the live source."""
    receipt: dict[str, object] = {
        "filing_no": filing_no,
        "request_count": 0,
        "status": "blocked",
        "source_slot_verified": False,
        "runtime_preparation_verified": False,
        "activation_ready": False,
        "publication_committed": False,
        "notification_sent": False,
        "historical_filing_current_response": True,
    }
    if not re.fullmatch(r"[0-9]{14}", filing_no) or not re.fullmatch(r"[0-9]{8}", corp_code):
        return {**receipt, "reason": "qualification.input_invalid"}, {}
    try:
        datetime.strptime(filing_no[:8], "%Y%m%d")
    except ValueError:
        return {**receipt, "reason": "qualification.input_invalid"}, {}
    if not credential:
        return {**receipt, "reason": "credential_missing"}, {}
    levels = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}
    for name in levels:
        logging.getLogger(name).setLevel(logging.CRITICAL)
    started = monotonic()
    try:
        async with asyncio.timeout(20):
            async with asyncio.timeout(8):
                entry, listing = await _fetch_listing(
                    client,
                    filing_no=filing_no,
                    corp_code=corp_code,
                    credential=credential,
                    receipt=receipt,
                )
            item = DartDisclosureAdapter()._normalize_entry(entry, date_precision=True)
            if item is None:
                raise ValueError("qualification.item_invalid")
            receipt["request_count"] = 2
            async with asyncio.timeout(8):
                document_receipt, raw = await probe_document(
                    client, filing_no=filing_no, credential=credential
                )
            receipt["document"] = document_receipt
            if raw is None:
                receipt["reason"] = "qualification.document_blocked"
                return receipt, {}
            received = datetime.fromisoformat(str(document_receipt["received_at"]))
            clocks = [
                datetime.fromisoformat(str(value))
                for value in (
                    receipt["listing_started_at"],
                    receipt["listing_received_at"],
                    document_receipt["request_started_at"],
                    document_receipt["received_at"],
                )
            ]
            if clocks != sorted(clocks):
                raise ValueError("qualification.clock_invalid")
            before = item.model_dump_json()
            result = parse_dart_document(
                item,
                raw,
                response_sha256=str(document_receipt["response_sha256"]),
                received_at=received,
                forbidden_token=credential.encode(),
            )
            if before != item.model_dump_json():
                raise ValueError("qualification.item_mutated")
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml = archive.read(f"{filing_no}.xml")
            tree = fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
            for binding in result.xml_bindings:
                path, _, attribute = binding.path.partition("/@")
                node = tree.find(path.removeprefix("DOCUMENT/"))
                if node is None:
                    raise ValueError("qualification.binding_invalid")
                value = node.attrib[attribute] if attribute else "".join(node.itertext())
                if " ".join(normalize_evidence_text(value).split()) != binding.value:
                    raise ValueError("qualification.binding_invalid")
            for refs in result.field_refs.values():
                for ref in refs:
                    resolve_context_ref(ref, (result.context,))
            private: dict[str, dict[str, object]] = {
                "listing.json": {"response_base64": base64.b64encode(listing).decode()},
                "document.json": {"zip_base64": base64.b64encode(raw).decode()},
                "parser.json": {
                    "item": result.item.model_dump(mode="json"),
                    "context": result.context.model_dump(mode="json"),
                    "field_refs": {
                        slot: [ref.model_dump(mode="json") for ref in refs]
                        for slot, refs in result.field_refs.items()
                    },
                    "xml_bindings": [asdict(binding) for binding in result.xml_bindings],
                },
            }
            if credential in json.dumps(private, ensure_ascii=False):
                raise ValueError("qualification.credential_echo")
            if result.item.event_evidence is None or monotonic() - started >= 20:
                raise ValueError("qualification.budget_or_evidence_invalid")
            receipt.update(
                status="validated",
                reason="qualification.decision_pending",
                parser_version=result.parser_version,
                xml_sha256=result.xml_sha256,
                field_ref_counts={slot: len(refs) for slot, refs in result.field_refs.items()},
                xml_roundtrips=len(result.xml_bindings),
                projection_chars=len(result.item.event_evidence.detail_excerpt),
                context_sha256=hashlib.sha256(
                    result.context.model_dump_json().encode()
                ).hexdigest(),
                published_precision=result.context.time.published_at.precision,
                occurred_precision=result.context.time.occurred_at.precision,
                announced_precision=result.context.time.announced_at.precision,
            )
            return receipt, private
    except DartDocumentError as exc:
        code = str(exc) if re.fullmatch(r"dart\.[a-z_]+", str(exc)) else "dart.invalid"
        receipt.update(status="blocked", reason="qualification.parser_rejected", parser_code=code)
        return receipt, {}
    except (
        httpx.HTTPError,
        TimeoutError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        RecursionError,
    ):
        receipt.update(status="blocked", reason="qualification.input_or_fetch_invalid")
        return receipt, {}
    finally:
        receipt["elapsed_seconds"] = round(monotonic() - started, 6)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)


def private_output(path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    path = path.absolute()
    if (
        not path.is_relative_to(root / ".tmp")
        or any(part.is_symlink() for part in (path, *path.parents))
        or not path.resolve().is_relative_to(root / ".tmp")
        or subprocess.run(
            ["git", "check-ignore", "-q", "--", str(path / "manifest.json")],
            cwd=root,
            check=False,
            capture_output=True,
            timeout=5,
        ).returncode
        != 0
    ):
        raise ValueError("document.private_path_invalid")
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path


def _write(path: Path, payload: dict[str, object]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(payload, handle, ensure_ascii=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filing-no", required=True)
    parser.add_argument("--qualify", action="store_true")
    parser.add_argument("--corp-code", default="")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[0-9]{14}", args.filing_no):
            raise ValueError("document.filing_invalid")
        output = private_output(args.output_dir)

        async def run() -> tuple[dict[str, object], bytes | None, dict[str, dict[str, object]]]:
            async with httpx.AsyncClient(trust_env=False) as client:
                if args.qualify:
                    receipt, private = await probe_qualification(
                        client,
                        filing_no=args.filing_no,
                        corp_code=args.corp_code,
                        credential=os.environ.get("OPENDART_API_KEY", "").strip(),
                    )
                    return receipt, None, private
                receipt, data = await probe_document(
                    client,
                    filing_no=args.filing_no,
                    credential=os.environ.get("OPENDART_API_KEY", "").strip(),
                )
                return receipt, data, {}

        receipt, data, private = asyncio.run(run())
        for name, payload in private.items():
            _write(output / name, payload)
        if data is not None:
            _write(output / "document.json", {"zip_base64": base64.b64encode(data).decode()})
        _write(output / "manifest.json", receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0 if data is not None or private else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print(json.dumps({"status": "blocked", "reason": "probe_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
