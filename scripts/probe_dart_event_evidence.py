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
from pathlib import Path, PurePosixPath

import httpx
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

MAX_BYTES = 500 * 1024
MAX_FILES = 16
_ENDPOINT = "https://opendart.fss.or.kr/api/document.xml"
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
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[0-9]{14}", args.filing_no):
            raise ValueError("document.filing_invalid")
        output = private_output(args.output_dir)

        async def run() -> tuple[dict[str, object], bytes | None]:
            async with httpx.AsyncClient(trust_env=False) as client:
                return await probe_document(
                    client,
                    filing_no=args.filing_no,
                    credential=os.environ.get("OPENDART_API_KEY", "").strip(),
                )

        receipt, data = asyncio.run(run())
        if data is not None:
            _write(output / "document.json", {"zip_base64": base64.b64encode(data).decode()})
        _write(output / "manifest.json", receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0 if data is not None else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print(json.dumps({"status": "blocked", "reason": "probe_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
