"""Bounded private recording of only the shared preparation's DART responses."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import httpx

from investo.sources._dart_document import _read_xml
from investo.sources._dart_evidence import _unique_object

MAX_DART_CAPTURE_BYTES = 192 * 1024


class _Stream(httpx.AsyncByteStream):
    def __init__(
        self, stream: httpx.AsyncByteStream, owner: DartCapture, record: dict[str, object]
    ) -> None:
        self.stream = stream
        self.owner = owner
        self.record = record

    async def __aiter__(self) -> AsyncIterator[bytes]:
        body = bytearray()
        complete = False
        try:
            async for chunk in self.stream:
                if len(chunk) > MAX_DART_CAPTURE_BYTES - self.owner.total:
                    self.owner.invalid = True
                    raise httpx.ReadError("private capture limit exceeded")
                self.owner.total += len(chunk)
                body.extend(chunk)
                yield chunk
            complete = True
        finally:
            if not complete or (self.owner.token and self.owner.token in body):
                self.owner.invalid = True
            elif not self.owner.invalid:
                self.owner.finish(self.record, bytes(body))

    async def aclose(self) -> None:
        await self.stream.aclose()


class DartCapture(httpx.AsyncBaseTransport):
    def __init__(self, token: bytes, delegate: httpx.AsyncBaseTransport | None = None) -> None:
        self.delegate = delegate or httpx.AsyncHTTPTransport(trust_env=False)
        self.token = token
        self.total = 0
        self.expanded = 0
        self.invalid = False
        self.records: list[dict[str, object]] = []

    def finish(self, record: dict[str, object], body: bytes) -> None:
        try:
            encoding = record["content_encoding"]
            if encoding in {"gzip", "deflate"}:
                decoder = zlib.decompressobj(31 if encoding == "gzip" else zlib.MAX_WBITS)
                body = decoder.decompress(body, MAX_DART_CAPTURE_BYTES + 1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError("capture.encoding")
            elif encoding != "identity":
                raise ValueError("capture.encoding")
            if len(body) > MAX_DART_CAPTURE_BYTES - self.expanded:
                raise ValueError("capture.size")
            if record["path"] == "/api/document.xml":
                params = cast(dict[str, str], record["parameters"])
                _read_xml(body, params.get("rcept_no", "") + ".xml", self.token)
            else:
                decoded = json.loads(body.decode("utf-8-sig"), object_pairs_hook=_unique_object)
                if self.token and self.token.decode() in json.dumps(decoded, ensure_ascii=False):
                    raise ValueError("capture.credential_echo")
            self.expanded += len(body)
        except (ValueError, UnicodeError, RecursionError, zlib.error):
            self.invalid = True
            return
        record.update(
            received_at=datetime.now(UTC).isoformat(),
            representation="http_decoded_body",
            response_sha256=hashlib.sha256(body).hexdigest(),
            response_base64=base64.b64encode(body).decode("ascii"),
        )
        self.records.append(record)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.delegate.handle_async_request(request)
        if request.url.host != "opendart.fss.or.kr" or request.url.path not in {
            "/api/list.json",
            "/api/document.xml",
        }:
            return response
        record: dict[str, object] = {
            "path": request.url.path,
            "parameters": {
                key: value
                for key, value in request.url.params.multi_items()
                if key
                in {
                    "corp_code",
                    "rcept_no",
                    "bgn_de",
                    "end_de",
                    "page_no",
                    "page_count",
                    "last_reprt_at",
                    "pblntf_detail_ty",
                    "sort",
                    "sort_mth",
                }
            },
            "http_status": response.status_code,
            "content_encoding": response.headers.get("content-encoding", "identity").lower(),
        }
        if response.is_stream_consumed or not isinstance(response.stream, httpx.AsyncByteStream):
            self.invalid = True
            return response
        response.stream = _Stream(response.stream, self, record)
        return response

    def validate(self) -> None:
        if self.invalid or len(self.records) > 6:
            raise ValueError("preview.dart_capture_invalid")

    async def aclose(self) -> None:
        await self.delegate.aclose()
