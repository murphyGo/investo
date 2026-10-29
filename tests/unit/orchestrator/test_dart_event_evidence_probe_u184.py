"""Synthetic qualification probes cannot publish source bytes or credentials."""

import base64
import io
import json
import logging
import re
import subprocess
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import probe_dart_event_evidence as probe

FILING = "20260101000001"
SECRET = "SYNTHETIC_DART_CREDENTIAL_NEVER_EMIT"
XML = b"<DOCUMENT><BODY><P>Synthetic disclosure text.</P></BODY></DOCUMENT>"
UNKNOWN_ENCODING = b'<?xml version="1.0" encoding="unknown-encoding"?><d/>'


def archive_bytes(xml=XML, name="document.xml"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, xml)
    return buffer.getvalue()


def test_bounded_zip_is_structural_evidence_without_slot_qualification():
    result = probe.inspect_document(archive_bytes())
    assert result == {"xml_files": 1, "expanded_bytes": len(XML), "xml_nodes": 3}


@pytest.mark.parametrize("name", ["../document.xml", "/document.xml", "a\\document.xml", "x.html"])
def test_archive_members_cannot_escape_or_introduce_other_formats(name):
    with pytest.raises(ValueError):
        probe.inspect_document(archive_bytes(name=name))


def test_archive_cannot_select_a_decompressor_with_a_large_dictionary():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_LZMA) as archive:
        archive.writestr("document.xml", XML)
    with pytest.raises(ValueError, match="member_invalid"):
        probe.inspect_document(buffer.getvalue())


@pytest.mark.parametrize(
    "xml",
    [
        b"<not-well-formed>",
        UNKNOWN_ENCODING,
        b'<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><d>&x;</d>',
        b"<d>" * 258 + b"</d>" * 258,
        b"<d>" + b"<n/>" * 20001 + b"</d>",
        b"<d>" + b"x" * probe.MAX_BYTES + b"</d>",
    ],
)
def test_xml_entities_depth_node_count_and_expanded_size_are_bounded(xml):
    with pytest.raises(ValueError):
        probe.inspect_document(archive_bytes(xml))


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16-le", "utf-16-be"])
@pytest.mark.parametrize("content", [f"<!--{SECRET}--><d/>", f'<d key="{SECRET}"/>'])
def test_encoded_credentials_in_compressed_xml_are_not_captured(encoding, content):
    declaration = f'<?xml version="1.0" encoding="{encoding}"?>'
    with pytest.raises(ValueError, match="credential_echo"):
        probe.inspect_document(
            archive_bytes((declaration + content).encode(encoding)), forbidden_token=SECRET.encode()
        )


@pytest.mark.parametrize("credential", ["", SECRET])
async def test_only_one_fixed_endpoint_is_used_and_no_credential_is_reported(caplog, credential):
    caplog.set_level(logging.DEBUG)
    previous = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}
    seen = []

    def handler(request):
        seen.append(request)
        assert str(request.url).startswith("https://opendart.fss.or.kr/api/document.xml?")
        assert dict(request.url.params) == {"crtfc_key": SECRET, "rcept_no": FILING}
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, content=archive_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        receipt, raw = await probe.probe_document(client, filing_no=FILING, credential=credential)
    assert len(seen) == bool(credential)
    assert receipt["request_count"] == len(seen)
    assert receipt["source_slot_verified"] is False and receipt["activation_ready"] is False
    assert (raw is not None) == bool(credential)
    assert SECRET not in json.dumps(receipt) + caplog.text
    assert {name: logging.getLogger(name).level for name in previous} == previous


@pytest.mark.parametrize(
    "failure",
    ["redirect", "http", "xml", "xml_encoding", "zip_encoding", "echo", "zip_echo", "gzip", "size"],
)
async def test_unavailable_unsafe_or_credential_echo_responses_never_retain_raw(failure):
    seen = 0

    def handler(request):
        nonlocal seen
        seen += 1
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com/private"})
        if failure == "http":
            return httpx.Response(403, text=SECRET)
        if failure == "xml":
            return httpx.Response(200, content=b"<broken>")
        if failure == "xml_encoding":
            return httpx.Response(200, content=UNKNOWN_ENCODING)
        if failure == "zip_encoding":
            return httpx.Response(200, content=archive_bytes(UNKNOWN_ENCODING))
        if failure == "echo":
            return httpx.Response(200, text=f"<result><message>{SECRET}</message></result>")
        if failure == "zip_echo":
            return httpx.Response(200, content=archive_bytes(f"<d>{SECRET}</d>".encode()))
        if failure == "gzip":
            import gzip

            return httpx.Response(
                200, content=gzip.compress(XML), headers={"content-encoding": "gzip"}
            )
        return httpx.Response(200, content=b"x" * (probe.MAX_BYTES + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        receipt, raw = await probe.probe_document(client, filing_no=FILING, credential=SECRET)
    assert seen == 1 and raw is None and receipt["status"] == "blocked"
    assert SECRET not in json.dumps(receipt)


def test_private_output_is_ignored_exclusive_and_files_are_owner_only(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=5)
    (tmp_path / ".gitignore").write_text(".tmp/\n")
    monkeypatch.setattr(probe, "__file__", str(tmp_path / "scripts/probe.py"))
    output = probe.private_output(tmp_path / ".tmp/private-probe")
    assert output.stat().st_mode & 0o777 == 0o700
    probe._write(output / "document.json", {"zip_base64": base64.b64encode(XML).decode()})
    assert (output / "document.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        probe.private_output(tmp_path / "public")
    with pytest.raises(FileExistsError):
        probe.private_output(output)


def test_workflow_has_one_source_secret_and_ciphertext_only_manual_retention():
    path = Path(__file__).resolve().parents[3] / "ops/private-runtime/dart-event-evidence-probe.yml"
    raw = path.read_text()
    config = yaml.load(raw, Loader=yaml.BaseLoader)
    assert set(config["on"]) == {"workflow_dispatch"}
    assert config["permissions"] == {"contents": "read"}
    assert re.findall(r"secrets\.([A-Z_]+)", raw) == ["OPENDART_API_KEY"]
    job = config["jobs"]["probe"]
    assert "github.event.repository.private == true" in job["if"]
    steps = job["steps"]
    names = [s.get("name", "") for s in steps]
    assert names.index("Validate recipient encryption before source credentials") < names.index(
        "Fetch one bounded document"
    )
    uploads = [s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1 and uploads[0]["with"]["path"].endswith(".sealed")
    assert uploads[0]["with"]["retention-days"] == "1"
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
        if "run" in step:
            assert "${{ inputs." not in step["run"]
            subprocess.run(["bash", "-n"], input=step["run"], text=True, check=True, timeout=5)
