"""Fresh listing identity and actual receive clocks stay private and bounded."""

import asyncio
import base64
import hashlib
import io
import json
import logging
import re
import subprocess
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import probe_dart_event_evidence as probe

FILING = "20260902000001"
CORP = "00000001"
SECRET = "SYNTHETIC_DART_CREDENTIAL_NEVER_EMIT"
FIXTURE = Path(__file__).parents[2] / "fixtures/dart_document/cb-correction-6.4.xml"


def listing_case():
    return {
        "status": "000",
        "message": "정상",
        "page_no": 1,
        "page_count": 100,
        "total_count": 1,
        "total_page": 1,
        "list": [
            {
                "corp_code": CORP,
                "corp_name": "가람상사",
                "corp_cls": "K",
                "report_nm": "[기재정정]주요사항보고서(전환사채권 발행결정)",
                "rcept_no": FILING,
                "rcept_dt": FILING[:8],
            }
        ],
    }


def archive_case(xml=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(FILING + ".xml", FIXTURE.read_bytes() if xml is None else xml)
    return output.getvalue()


async def run_case(handler, *, filing=FILING, corp=CORP, credential=SECRET):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await probe.probe_qualification(
            client, filing_no=filing, corp_code=corp, credential=credential
        )


async def test_fresh_listing_and_zip_bind_five_slots_with_actual_ordered_clocks(caplog):
    caplog.set_level(logging.DEBUG)
    requests = []
    payload = listing_case()
    document = archive_case()
    listing_raw = json.dumps(payload).encode()
    previous = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}

    def handler(request):
        requests.append(request)
        assert request.headers["accept-encoding"] == "identity"
        assert request.url.host == "opendart.fss.or.kr" and request.url.scheme == "https"
        if request.url.path == "/api/list.json":
            assert dict(request.url.params) == {
                "crtfc_key": SECRET,
                "corp_code": CORP,
                "bgn_de": FILING[:8],
                "end_de": FILING[:8],
                "last_reprt_at": "N",
                "page_no": "1",
                "page_count": "100",
            }
            return httpx.Response(200, content=listing_raw)
        assert request.url.path == "/api/document.xml"
        assert dict(request.url.params) == {"crtfc_key": SECRET, "rcept_no": FILING}
        return httpx.Response(200, content=document)

    receipt, private = await run_case(handler)
    assert len(requests) == receipt["request_count"] == 2
    assert receipt["status"] == "validated" and receipt["elapsed_seconds"] < 20
    assert receipt["historical_filing_current_response"] is True
    assert receipt["source_slot_verified"] is receipt["runtime_preparation_verified"] is False
    assert receipt["activation_ready"] is receipt["publication_committed"] is False
    assert receipt["notification_sent"] is False
    assert receipt["field_ref_counts"] == {
        "issuer": 1,
        "action": 3,
        "action_status": 4,
        "action_terms": 16,
        "filing_locator": 1,
    }
    assert receipt["xml_roundtrips"] == 29
    assert receipt["published_precision"] == "date"
    assert receipt["occurred_precision"] == receipt["announced_precision"] == "unknown"
    clocks = [
        datetime.fromisoformat(value)
        for value in (
            receipt["listing_started_at"],
            receipt["listing_received_at"],
            receipt["document"]["request_started_at"],
            receipt["document"]["received_at"],
        )
    ]
    assert clocks == sorted(clocks) and all(
        clock.utcoffset().total_seconds() == 0 for clock in clocks
    )
    assert base64.b64decode(private["listing.json"]["response_base64"]) == listing_raw
    assert base64.b64decode(private["document.json"]["zip_base64"]) == document
    assert receipt["listing_sha256"] == hashlib.sha256(listing_raw).hexdigest()
    assert receipt["document"]["response_sha256"] == hashlib.sha256(document).hexdigest()
    received = private["parser.json"]["context"]["time"]["received_at"]
    assert received["precision"] == "exact"
    assert datetime.fromisoformat(received["value"]) == clocks[-1]
    assert SECRET not in json.dumps(receipt) + json.dumps(private) + caplog.text
    assert "가람상사" not in json.dumps(receipt, ensure_ascii=False)
    assert {name: logging.getLogger(name).level for name in previous} == previous


@pytest.mark.parametrize(
    "filing,corp,credential",
    [
        ("invalid", CORP, SECRET),
        (FILING, "123", SECRET),
        ("20261301000001", CORP, SECRET),
        (FILING, CORP, ""),
    ],
)
async def test_invalid_input_or_missing_key_makes_zero_requests(filing, corp, credential):
    def handler(request):
        pytest.fail("HTTP must not run")

    receipt, private = await run_case(handler, filing=filing, corp=corp, credential=credential)
    assert receipt["status"] == "blocked" and receipt["request_count"] == 0 and not private


@pytest.mark.parametrize(
    "failure",
    [
        "redirect",
        "http",
        "gzip",
        "oversize",
        "malformed",
        "duplicate_key",
        "nested",
        "secret",
        "encoded_secret",
        "status",
        "pages",
        "count",
        "bool_page",
        "wrong_company",
        "wrong_date",
        "missing_target",
        "duplicate_target",
        "non_object",
        "empty",
        "bad_entry",
    ],
)
async def test_listing_failure_stops_before_document_and_keeps_no_raw(failure, caplog):
    caplog.set_level(logging.DEBUG)
    calls = []
    payload = listing_case()
    if failure == "status":
        payload["status"] = "013"
    if failure == "pages":
        payload.update(total_count=101, total_page=2)
    if failure == "count":
        payload["total_count"] = 2
    if failure == "bool_page":
        payload["page_no"] = True
    if failure == "wrong_company":
        payload["list"][0]["corp_code"] = "00000002"
    if failure == "wrong_date":
        payload["list"][0]["rcept_dt"] = "20260901"
    if failure == "missing_target":
        payload["list"][0]["rcept_no"] = "20260902000002"
    if failure == "duplicate_target":
        payload["list"] *= 2
        payload["total_count"] = 2
    if failure == "empty":
        payload["list"] = []
    if failure == "bad_entry":
        payload["list"][0]["report_nm"] = None
    if failure in {"secret", "encoded_secret"}:
        payload["message"] = SECRET
    raw = json.dumps(payload).encode()
    if failure == "encoded_secret":
        raw = raw.replace(SECRET.encode(), "".join(f"\\u{ord(c):04x}" for c in SECRET).encode())
    if failure == "non_object":
        raw = b"[]"
    if failure == "malformed":
        raw = b"{"
    if failure == "duplicate_key":
        raw = b'{"status":"013",' + raw[1:]
    if failure == "nested":
        raw = b"[" * 2000 + b"0" + b"]" * 2000
    if failure == "oversize":
        raw = b"x" * (probe.MAX_BYTES + 1)

    def handler(request):
        calls.append(request)
        assert request.url.path == "/api/list.json"
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com/unsafe"})
        return httpx.Response(
            403 if failure == "http" else 200,
            content=raw,
            headers={"content-encoding": "gzip"} if failure == "gzip" else {},
        )

    receipt, private = await run_case(handler)
    assert len(calls) == receipt["request_count"] == 1
    assert receipt["status"] == "blocked" and not private
    assert receipt["elapsed_seconds"] >= 0
    assert SECRET not in json.dumps(receipt) + caplog.text


@pytest.mark.parametrize("failure", ["timeout", "http", "parser", "secret", "redirect"])
async def test_document_failure_is_closed_at_two_calls(failure, caplog):
    caplog.set_level(logging.DEBUG)
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/api/list.json":
            return httpx.Response(200, json=listing_case())
        if failure == "timeout":
            raise httpx.ReadTimeout(SECRET, request=request)
        if failure == "http":
            return httpx.Response(403, text=SECRET)
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com/unsafe"})
        xml = FIXTURE.read_bytes()
        if failure == "parser":
            xml = xml.replace(b'ACODE="11324"', b'ACODE="11325"')
        if failure == "secret":
            xml = xml.replace(b"<DOCUMENT", b"<!--" + SECRET.encode() + b"--><DOCUMENT")
        return httpx.Response(200, content=archive_case(xml))

    receipt, private = await run_case(handler)
    assert len(calls) == receipt["request_count"] == 2
    assert receipt["status"] == "blocked" and not private
    assert receipt["elapsed_seconds"] >= 0
    assert SECRET not in json.dumps(receipt) + caplog.text


async def test_unknown_xml_locator_cannot_pass_even_if_parser_object_is_returned(monkeypatch):
    original = probe.parse_dart_document

    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        binding = replace(result.xml_bindings[0], path="DOCUMENT/MISSING[1]")
        return replace(result, xml_bindings=(binding, *result.xml_bindings[1:]))

    monkeypatch.setattr(probe, "parse_dart_document", altered)
    receipt, private = await run_case(
        lambda req: (
            httpx.Response(200, json=listing_case())
            if req.url.path == "/api/list.json"
            else httpx.Response(200, content=archive_case())
        )
    )
    assert receipt["status"] == "blocked" and not private


@pytest.mark.parametrize(
    "remark,status", [("", "none"), ("정", "superseded"), ("철", "withdrawn"), ("유", "other")]
)
async def test_followup_remark_is_retained_without_current_action_claim(remark, status):
    listing = listing_case()
    listing["list"][0]["rm"] = remark
    receipt, private = await run_case(
        lambda req: (
            httpx.Response(200, json=listing)
            if req.url.path == "/api/list.json"
            else httpx.Response(200, content=archive_case())
        )
    )
    assert receipt["status"] == "validated" and receipt["listing_follow_up"] == status
    raw = base64.b64decode(private["listing.json"]["response_base64"])
    assert json.loads(raw)["list"][0]["rm"] == remark
    assert receipt["historical_filing_current_response"] and not receipt["source_slot_verified"]


async def test_entire_get_has_a_wall_timeout_even_if_transport_keeps_progress(monkeypatch):
    original = asyncio.timeout
    monkeypatch.setattr(
        probe.asyncio, "timeout", lambda seconds: original(0.01 if seconds == 8 else 1)
    )
    calls = []

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(0.03)
        return httpx.Response(200, json=listing_case())

    receipt, private = await run_case(handler)
    assert len(calls) == receipt["request_count"] == 1
    assert receipt["status"] == "blocked" and not private


async def test_cpu_validation_cannot_overrun_shared_monotonic_budget(monkeypatch):
    clocks = iter([0, 0, 0, 21, 21])
    monkeypatch.setattr(probe, "monotonic", lambda: next(clocks))
    receipt, private = await run_case(
        lambda req: (
            httpx.Response(200, json=listing_case())
            if req.url.path == "/api/list.json"
            else httpx.Response(200, content=archive_case())
        )
    )
    assert receipt["status"] == "blocked" and not private and receipt["elapsed_seconds"] == 21


async def test_backwards_receive_clock_is_not_silently_replaced(monkeypatch):
    clocks = iter([datetime(2026, 11, 16, tzinfo=UTC)] * 3 + [datetime(2026, 11, 15, tzinfo=UTC)])

    class ReversedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(clocks)

    monkeypatch.setattr(probe, "datetime", ReversedClock)
    receipt, private = await run_case(
        lambda req: (
            httpx.Response(200, json=listing_case())
            if req.url.path == "/api/list.json"
            else httpx.Response(200, content=archive_case())
        )
    )
    assert receipt["status"] == "blocked" and not private


def test_manual_workflow_has_own_pin_and_ciphertext_only_retention():
    root = Path(__file__).parents[3]
    raw = (root / "ops/private-runtime/dart-source-qualification.yml").read_text()
    config = yaml.load(raw, Loader=yaml.BaseLoader)
    assert set(config["on"]) == {"workflow_dispatch"}
    assert config["permissions"] == {"contents": "read"}
    assert re.findall(r"secrets\.([A-Z_]+)", raw) == ["OPENDART_API_KEY"]
    assert set(re.findall(r"vars\.([A-Z_]+)", raw)) == {"REVIEWED_DART_QUALIFICATION_SHA"}
    job = config["jobs"]["probe"]
    assert "github.event.repository.private == true" in job["if"]
    steps = job["steps"]
    names = [step.get("name") for step in steps]
    assert names.index("Validate recipient encryption before source credentials") < names.index(
        "Validate one listing and document"
    )
    upload = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(upload) == 1 and upload[0]["with"]["path"].endswith(".sealed")
    assert upload[0]["with"]["retention-days"] == "1"
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
        if "run" in step:
            assert "${{ inputs." not in step["run"]
            subprocess.run(["bash", "-n"], input=step["run"], text=True, check=True, timeout=5)
