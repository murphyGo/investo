"""Private bounded DART collection rehearsal through the shared preparation seam."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import httpx

from investo._internal.redaction import install_secret_log_filters
from investo.briefing.event_context import prepare_context_documents
from investo.models.enrichment import EnrichmentPolicy
from investo.orchestrator.event_evidence import prepare_event_evidence
from investo.sources._dart_document import MAX_BYTES, _read_xml
from investo.sources._dart_evidence import _unique_object, dart_identity
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.event_evidence import (
    _dart_transport_allowed,
    load_enrichment_qualification,
    load_source_slot_qualification,
)

MAX_RECORDING_BYTES = 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


def private_output(path: Path) -> Path:
    path = path.absolute()
    if (
        not path.is_relative_to(ROOT / ".tmp")
        or any(part.is_symlink() for part in (path, *path.parents))
        or not path.resolve().is_relative_to(ROOT / ".tmp")
        or subprocess.run(
            ["git", "check-ignore", "-q", "--", str(path / "manifest.json")],
            cwd=ROOT,
            capture_output=True,
            timeout=5,
        ).returncode
        != 0
    ):
        raise ValueError("preparation.private_path")
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path


def write_private(path: Path, payload: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(payload, handle, ensure_ascii=True)


class RecordingStream(httpx.AsyncByteStream):
    def __init__(
        self, inner: httpx.AsyncByteStream, record: dict[str, Any], owner: RecordingTransport
    ) -> None:
        self.inner, self.record, self.owner = inner, record, owner

    async def __aiter__(self) -> AsyncIterator[bytes]:
        data = bytearray()
        async for chunk in self.inner:
            if (
                len(data) + len(chunk) > MAX_BYTES
                or self.owner.bytes + len(chunk) > MAX_RECORDING_BYTES
            ):
                raise httpx.ReadError("bounded diagnostic response")
            self.owner.bytes += len(chunk)
            data.extend(chunk)
            yield chunk
        self.record["raw"] = bytes(data)

    async def aclose(self) -> None:
        await self.inner.aclose()


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.inner = httpx.AsyncHTTPTransport(retries=0)
        self.records: list[dict[str, Any]] = []
        self.bytes = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            len(self.records) >= 6
            or request.url.scheme != "https"
            or request.url.host != "opendart.fss.or.kr"
            or request.url.path not in {"/api/list.json", "/api/document.xml"}
        ):
            raise httpx.RequestError("bounded diagnostic endpoint")
        keys = {
            "corp_code",
            "bgn_de",
            "end_de",
            "last_reprt_at",
            "page_no",
            "page_count",
            "rcept_no",
        }
        if set(request.url.params) - keys - {"crtfc_key"}:
            raise httpx.RequestError("bounded diagnostic parameters")
        record: dict[str, Any] = {
            "path": request.url.path,
            "parameters": {key: value for key, value in request.url.params.items() if key in keys},
            "started_at": datetime.now(UTC).isoformat(),
            "http_status": None,
            "raw": None,
        }
        self.records.append(record)
        response = await self.inner.handle_async_request(request)
        record["http_status"] = response.status_code
        response.stream = RecordingStream(
            cast(httpx.AsyncByteStream, response.stream), record, self
        )
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


async def rehearse(
    *,
    filing: str,
    corp: str,
    credential: str,
    parser_version: Literal["v1", "v2"] = "v1",
    parser_profile: Literal["price", "schedule"] = "price",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One collection GET and at most two two-GET candidates, all within20s/6."""
    manifest: dict[str, Any] = {
        "status": "blocked",
        "request_count": 0,
        "enrichment_request_count": 0,
        "model_call_count": 0,
        "runtime_qualified": False,
        "activation_ready": False,
        "publication_committed": False,
        "notification_sent": False,
        "original_filing": filing if re.fullmatch(r"[0-9]{14}", filing) else None,
        "discovered_filing": None,
        "parser_profile": parser_profile if parser_profile in {"price", "schedule"} else "unknown",
    }
    if not re.fullmatch(r"[0-9]{14}", filing) or not re.fullmatch(r"[0-9]{8}", corp):
        return {**manifest, "reason": "input_invalid"}, {}
    if (
        parser_version not in {"v1", "v2"}
        or parser_profile not in {"price", "schedule"}
        or (parser_profile == "schedule" and parser_version != "v1")
    ):
        return {**manifest, "reason": "input_invalid"}, {}
    if not credential:
        return {**manifest, "reason": "credential_missing"}, {}
    try:
        first = datetime.strptime(filing[:8], "%Y%m%d").date()
    except ValueError:
        return {**manifest, "reason": "input_invalid"}, {}
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    if first > today or today - first > timedelta(days=31):
        return {**manifest, "reason": "collection_window_invalid"}, {}
    try:
        qualification = load_enrichment_qualification(
            ROOT
            / (
                "ops/event_dart_schedule_preview_qualification.json"
                if parser_profile == "schedule"
                else "ops/event_dart_preview_qualification.json"
                if parser_version == "v1"
                else "ops/event_dart_v2_preview_qualification.json"
            )
        )
        matrix = load_source_slot_qualification(
            ROOT
            / (
                "ops/event_dart_schedule_slot_qualification.json"
                if parser_profile == "schedule"
                else "ops/event_source_slot_qualification.json"
                if parser_version == "v1"
                else "ops/event_dart_v2_slot_qualification.json"
            )
        )
        expected = (
            "dart-cb-schedule-6.4-v1"
            if parser_profile == "schedule"
            else "dart-cb-correction-6.4-v1"
            if parser_version == "v1"
            else "dart-cb-terms-correction-6.4-v2"
        )
        if (
            qualification.dart is None
            or qualification.dart.parser_version != expected
            or not _dart_transport_allowed(qualification, matrix)
        ):
            raise ValueError("preparation.unqualified")
    except (OSError, ValueError):
        return {
            **manifest,
            "reason": "qualification_invalid" if parser_profile == "schedule" else "unqualified",
        }, {}
    install_secret_log_filters(
        (
            "httpx",
            "httpcore.connection",
            "httpcore.http11",
            "httpcore.http2",
            "httpcore.proxy",
            "httpcore.socks",
        )
    )
    transport = RecordingTransport()
    began = monotonic()
    try:
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False
        ) as client:
            async with asyncio.timeout(20):
                async with asyncio.timeout(8):
                    async with client.stream(
                        "GET",
                        "https://opendart.fss.or.kr/api/list.json",
                        params={
                            "crtfc_key": credential,
                            "corp_code": corp,
                            "bgn_de": filing[:8],
                            "end_de": today.strftime("%Y%m%d"),
                            "last_reprt_at": "N",
                            "page_no": "1",
                            "page_count": "100",
                        },
                        headers={"Accept-Encoding": "identity"},
                        timeout=8,
                    ) as response:
                        if (
                            response.status_code != 200
                            or response.headers.get("content-encoding", "identity").casefold()
                            != "identity"
                        ):
                            raise ValueError("collection.unavailable")
                        await response.aread()
                payload = json.loads(
                    response.content.decode("utf-8-sig"), object_pairs_hook=_unique_object
                )
                if not isinstance(payload, dict):
                    raise ValueError("collection.invalid")
                if credential in json.dumps(payload, ensure_ascii=False):
                    raise ValueError("collection.invalid")
                totals = DartDisclosureAdapter._pagination(payload, 1)
                entries = payload.get("list")
                if (
                    payload.get("status") != "000"
                    or totals is None
                    or totals[1] != 1
                    or not isinstance(entries, list)
                    or not 1 <= len(entries) <= 100
                    or len(entries) != totals[0]
                ):
                    raise ValueError("collection.incomplete")
                if any(
                    not DartDisclosureAdapter._well_formed_entry(entry)
                    or entry["corp_code"] != corp
                    or not filing[:8] <= entry["rcept_dt"] <= today.strftime("%Y%m%d")
                    for entry in entries
                ):
                    raise ValueError("collection.identity")
                targets = [entry for entry in entries if entry["rcept_no"] == filing]
                if len(targets) != 1:
                    raise ValueError("collection.target_missing")
                original = DartDisclosureAdapter()._normalize_entry(targets[0], date_precision=True)
                if original is None:
                    raise ValueError("collection.item_invalid")
                candidates = []
                for entry in entries:
                    if entry["rcept_no"] == filing:
                        continue
                    remark = entry.get("rm")
                    if not isinstance(remark, str) or set(remark) - set("유코채넥공연"):
                        continue
                    item = DartDisclosureAdapter()._normalize_entry(entry, date_precision=True)
                    if item is not None:
                        try:
                            dart_identity(item)
                            candidates.append(item)
                        except ValueError:
                            pass
                candidates.sort(key=lambda item: str(item.raw_metadata["rcept_no"]), reverse=True)
                items = (original, *candidates[:1])
                manifest["discovered_filing"] = (
                    candidates[0].raw_metadata["rcept_no"] if candidates else None
                )
                policy = EnrichmentPolicy(
                    mode="preview",
                    article_passages=True,
                    max_requests=5,
                    max_excerpt_chars=qualification.dart.max_projection_chars,
                    preview_sources=("dart-disclosure",),
                    qualification_sha256=qualification.policy_hash,
                )
                prepared = await prepare_event_evidence(
                    items,
                    (),
                    policy=policy,
                    qualification=qualification,
                    received_at=datetime.now(UTC),
                    deadline=began + 20,
                    client=client,
                    slot_qualification=matrix,
                )
                native = prepare_context_documents(
                    tuple(item for item in prepared.items if not item.event_input_blocked),
                    received_at=datetime.now(UTC),
                    article_passages=True,
                )
                enriched = [trace for trace in prepared.outcomes if trace.status == "enriched"]
                if (
                    len(enriched) != len(native)
                    or {trace.document_id for trace in enriched}
                    != {context.document_id for context in native}
                    or any(
                        trace.dart is None
                        or trace.dart.native_context_sha256
                        != hashlib.sha256(context.model_dump_json().encode()).hexdigest()
                        for context in native
                        for trace in enriched
                        if trace.document_id == context.document_id
                    )
                ):
                    raise ValueError("native.context_mismatch")
                for record in transport.records:
                    raw = record.pop("raw")
                    if raw is None:
                        continue
                    if record["path"] == "/api/document.xml":
                        _read_xml(
                            raw, record["parameters"]["rcept_no"] + ".xml", credential.encode()
                        )
                    else:
                        decoded = json.loads(
                            raw.decode("utf-8-sig"), object_pairs_hook=_unique_object
                        )
                        if credential in json.dumps(decoded, ensure_ascii=False):
                            raise ValueError("recording.invalid")
                    record.update(
                        response_base64=base64.b64encode(raw).decode(),
                        response_sha256=hashlib.sha256(raw).hexdigest(),
                    )
                files = {
                    "http-recording.json": transport.records,
                    "input-items.json": [item.model_dump(mode="json") for item in items],
                    "prepared-items.json": prepared.model_dump(mode="json"),
                    "native-contexts.json": [context.model_dump(mode="json") for context in native],
                }
                if (
                    sum(
                        len(json.dumps(value, ensure_ascii=True).encode())
                        for value in files.values()
                    )
                    > 2 * 1024 * 1024 - 16384
                ):
                    raise ValueError("recording.byte_limit")
                if (
                    len(transport.records) != 1 + prepared.request_count
                    or len(transport.records) > 6
                ):
                    raise ValueError("preparation.request_count")
                elapsed = round(monotonic() - began, 6)
                if elapsed >= 20:
                    raise ValueError("preparation.deadline")
                manifest.update(
                    status="completed",
                    reason="independent_review_pending",
                    request_count=len(transport.records),
                    collection_request_count=1,
                    enrichment_request_count=prepared.request_count,
                    input_count=len(items),
                    enriched_count=sum(not item.event_input_blocked for item in prepared.items),
                    blocked_count=sum(item.event_input_blocked for item in prepared.items),
                    native_context_count=len(native),
                    outcomes=[row.model_dump(mode="json") for row in prepared.outcomes],
                    elapsed_seconds=elapsed,
                    qualification_sha256=qualification.policy_hash,
                )
                return manifest, files
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        httpx.HTTPError,
        TimeoutError,
        RecursionError,
    ):
        return {
            **manifest,
            "status": "blocked",
            "reason": "preparation_unavailable",
            "enriched_count": 0,
            "native_context_count": 0,
            "request_count": len(transport.records),
            "elapsed_seconds": round(monotonic() - began, 6),
        }, {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filing-no", required=True)
    parser.add_argument("--corp-code", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--parser-profile", choices=("price", "schedule"), default="price")
    parser.add_argument("--parser-version", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    try:
        output = private_output(args.output_dir)
        manifest, files = asyncio.run(
            rehearse(
                filing=args.filing_no,
                corp=args.corp_code,
                credential=os.environ.get("OPENDART_API_KEY", "").strip(),
                parser_version=args.parser_version,
                parser_profile=args.parser_profile,
            )
        )
        for name, payload in files.items():
            write_private(output / name, payload)
        write_private(output / "manifest.json", manifest)
        print(json.dumps(manifest, sort_keys=True))
        return 0 if manifest["status"] == "completed" else 1
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired):
        print('{"status":"blocked","reason":"preparation_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
