from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import zipfile
from contextlib import suppress
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.models.coverage import SourceCollectionReport
from investo.models.enrichment import EnrichmentResult
from investo.orchestrator._event_preview_capture import MAX_DART_CAPTURE_BYTES, DartCapture
from tests.unit.orchestrator import test_event_preview_script as preview_helpers

script = preview_helpers.script
repository = preview_helpers.repository


@pytest.mark.parametrize(
    ("profile", "version", "expected"),
    [
        ("price", "v1", "dart-cb-correction-6.4-v1"),
        ("price", "v2", "dart-cb-terms-correction-6.4-v2"),
        ("schedule", "v1", "dart-cb-schedule-6.4-v1"),
    ],
)
async def test_profile_uses_reviewed_matrix_before_collection(
    script, repository, monkeypatch, profile, version, expected
):
    calls = []

    async def collect(*args, **kwargs):
        calls.append("collect")
        return SourceCollectionReport(items=(), outcomes=())

    async def prepare(*args, **kwargs):
        calls.append("prepare")
        assert kwargs["qualification"].dart.parser_version == expected
        (row,) = [
            r for r in kwargs["slot_qualification"].records if r.source_name == "dart-disclosure"
        ]
        assert row.parser_version == expected
        return EnrichmentResult(items=())

    class StopAfterPreparationError(Exception):
        pass

    async def anchors(*args, **kwargs):
        raise StopAfterPreparationError

    monkeypatch.setattr(script, "collect_sources", collect)
    monkeypatch.setattr(script, "prepare_event_evidence", prepare)
    monkeypatch.setattr(script, "_load_market_anchors_for_run", anchors)
    with pytest.raises(StopAfterPreparationError):
        await script.run_preview(
            target_date=date(2026, 11, 23),
            segment="domestic-equity",
            output_dir=Path(".tmp/preview"),
            repository_root=repository,
            observed_at=datetime(2026, 11, 23, tzinfo=UTC),
            document_schema=3,
            article_profile="article_v2",
            official_body_preview=True,
            dart_body_preview=True,
            dart_parser_profile=profile,
            dart_parser_version=version,
        )
    assert calls == ["collect", "prepare"]


async def test_bad_profile_policy_rejected_without_collection(script, repository, monkeypatch):
    monkeypatch.setattr(script, "_dart_transport_allowed", lambda *args: False)

    async def forbidden(*args, **kwargs):
        pytest.fail("unqualified policy reached collection")

    monkeypatch.setattr(script, "collect_sources", forbidden)
    with pytest.raises(script.PreviewInputError):
        await script.run_preview(
            target_date=date(2026, 11, 23),
            segment="domestic-equity",
            output_dir=Path(".tmp/preview"),
            repository_root=repository,
            document_schema=3,
            article_profile="article_v2",
            official_body_preview=True,
            dart_body_preview=True,
            dart_parser_profile="schedule",
        )
    assert not (repository / ".tmp/preview").exists()


@pytest.mark.parametrize("extra", [[], ["--dart-parser-version", "v2"]])
def test_schedule_requires_body_and_unambiguous_version(script, extra):
    args = [
        "--target-date",
        "2026-11-23",
        "--segment",
        "domestic-equity",
        "--output-dir",
        ".tmp/preview",
        "--dart-parser-profile",
        "schedule",
    ]
    if extra:
        args += [
            "--document-schema",
            "3",
            "--article-profile",
            "article_v2",
            "--official-body-preview",
            "--dart-body-preview",
            *extra,
        ]
    with pytest.raises(script.PreviewInputError):
        script._parse_args(args)


async def test_dart_capture_records_bytes_without_token_or_headers():
    body = b'{"status":"013"}'
    transport = DartCapture(
        b"PRIVATE_TEST_KEY",
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, stream=httpx.ByteStream(body), headers={"x-private": "HIDDEN"}
            )
        ),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={"crtfc_key": "PRIVATE_TEST_KEY", "corp_code": "01234567", "last_reprt_at": "Y"},
        )
        assert response.content == body
    transport.validate()
    (record,) = transport.records
    assert base64.b64decode(record["response_base64"]) == body
    assert record["response_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["parameters"] == {"corp_code": "01234567", "last_reprt_at": "Y"}
    assert "PRIVATE_TEST_KEY" not in json.dumps(record) and "HIDDEN" not in json.dumps(record)


@pytest.mark.parametrize(
    "body", [b"KEY_ECHO", b"x" * (MAX_DART_CAPTURE_BYTES + 1)], ids=["echo", "overflow"]
)
async def test_dart_capture_rejects_echo_and_overflow_without_retaining_body(body):
    transport = DartCapture(
        b"KEY_ECHO",
        httpx.MockTransport(lambda request: httpx.Response(200, stream=httpx.ByteStream(body))),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with suppress(httpx.ReadError):
            await client.get("https://opendart.fss.or.kr/api/document.xml")
    with pytest.raises(ValueError, match=r"preview\.dart_capture_invalid"):
        transport.validate()
    assert transport.records == []


async def test_capture_does_not_record_unrelated_source():
    capture = DartCapture(
        b"", httpx.MockTransport(lambda request: httpx.Response(200, text="body"))
    )
    async with httpx.AsyncClient(transport=capture) as client:
        await client.get("https://www.federalreserve.gov/newsevents/pressreleases/example.htm")
    capture.validate()
    assert capture.records == [] and capture.total == 0


@pytest.mark.parametrize("kind", ["json-escape", "zip-xml", "zip-entity", "duplicate-json"])
async def test_decoded_credential_or_ambiguous_json_is_never_retained(kind):
    token = b"SECRET_KEY"
    path = "/api/list.json"
    body = b'{"message":"\\u0053ECRET_KEY"}'
    if kind.startswith("zip-"):
        path = "/api/document.xml"
        packed = io.BytesIO()
        with zipfile.ZipFile(packed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            value = "SECRET_KEY" if kind == "zip-xml" else "&#83;ECRET_KEY"
            archive.writestr("20261123000001.xml", f"<DOCUMENT><P>{value}</P></DOCUMENT>")
        body = packed.getvalue()
    elif kind == "duplicate-json":
        body = b'{"message":"SECRET_KEY","message":"safe"}'
    capture = DartCapture(
        token,
        httpx.MockTransport(lambda request: httpx.Response(200, stream=httpx.ByteStream(body))),
    )
    async with httpx.AsyncClient(transport=capture) as client:
        await client.get("https://opendart.fss.or.kr" + path, params={"rcept_no": "20261123000001"})
    with pytest.raises(ValueError, match=r"preview\.dart_capture_invalid"):
        capture.validate()
    assert capture.records == []


async def test_http_encoding_is_decoded_before_hashing_and_secret_checks():
    body = b'{"status":"013"}'
    encoded = gzip.compress(body)
    capture = DartCapture(
        b"SECRET_KEY",
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(encoded)
            )
        ),
    )
    async with httpx.AsyncClient(transport=capture) as client:
        assert (await client.get("https://opendart.fss.or.kr/api/list.json")).content == body
    capture.validate()
    (record,) = capture.records
    assert record["representation"] == "http_decoded_body"
    assert record["response_sha256"] == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("content", [b'{"value":"SECRET_KEY"}', b'{"value":"\\u0053ECRET_KEY"}'])
def test_private_snapshot_rejects_source_credential_before_writing(
    script, tmp_path, monkeypatch, content
):
    monkeypatch.setenv("OPENDART_API_KEY", "SECRET_KEY")
    with pytest.raises(script.PreviewInputError):
        script._write_private(tmp_path, "source-evidence.json", content)
    assert not list(tmp_path.iterdir())
