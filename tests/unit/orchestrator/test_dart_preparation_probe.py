"""The private rehearsal uses the production seam without publication or retargeting."""

import base64
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import probe_dart_preparation as probe

from tests.unit.orchestrator.test_dart_preparation_u184 import SECRET, listing_case
from tests.unit.sources.test_dart_document_u173 import FILING, NOW, archive_case, item_case


def install_mock(monkeypatch, handler):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is None else NOW.astimezone(tz)

    original = probe.RecordingTransport.__init__

    def construct(self):
        original(self)
        self.inner = httpx.MockTransport(handler)

    monkeypatch.setattr(probe.RecordingTransport, "__init__", construct)
    monkeypatch.setattr(probe, "datetime", FixedClock)
    monkeypatch.setenv("OPENDART_API_KEY", SECRET)


def streamed(payload):
    raw = json.dumps(payload).encode() if isinstance(payload, dict) else payload
    return httpx.Response(200, stream=httpx.ByteStream(raw))


async def test_collection_and_two_candidates_rehearse_old_rejection_and_native_success(monkeypatch):
    newer = item_case(rcept_no="20260902000002")

    def respond(request):
        if request.url.path == "/api/document.xml":
            assert request.url.params["rcept_no"] == "20260902000002"
            return streamed(archive_case(name="20260902000002.xml"))
        if request.url.params["last_reprt_at"] == "N":
            payload = listing_case(rm="정")
            payload["list"].append(listing_case(newer)["list"][0])
            payload["total_count"] = 2
            return streamed(payload)
        return streamed(listing_case(newer))

    install_mock(monkeypatch, respond)
    manifest, files = await probe.rehearse(filing=FILING, corp="00000001", credential=SECRET)
    assert manifest["status"] == "completed" and manifest["request_count"] == 4
    assert manifest["collection_request_count"] == 1 and manifest["enrichment_request_count"] == 3
    assert (
        manifest["original_filing"] == FILING and manifest["discovered_filing"] == "20260902000002"
    )
    assert (
        manifest["blocked_count"]
        == manifest["enriched_count"]
        == manifest["native_context_count"]
        == 1
    )
    assert not any(
        manifest[key]
        for key in (
            "activation_ready",
            "runtime_qualified",
            "model_call_count",
            "publication_committed",
            "notification_sent",
        )
    )
    assert len(files["http-recording.json"]) == 4
    for record in files["http-recording.json"]:
        assert SECRET not in json.dumps(record)
        assert base64.b64decode(record["response_base64"])
    assert "dart-disclosure" in json.dumps(files["prepared-items.json"])


async def test_missing_key_invalid_window_or_bad_input_makes_no_requests(monkeypatch):
    def forbidden(request):
        pytest.fail("invalid rehearsal opened HTTP")

    install_mock(monkeypatch, forbidden)
    for filing, corp, key in [
        (FILING, "00000001", ""),
        (SECRET, "00000001", SECRET),
        ("20260101000001", "00000001", SECRET),
    ]:
        manifest, files = await probe.rehearse(filing=filing, corp=corp, credential=key)
        assert not files and manifest["request_count"] == 0 and SECRET not in json.dumps(manifest)


async def test_compressed_collection_is_rejected_before_body_read(monkeypatch):
    class ForbiddenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail("compressed collection was consumed")
            yield b""

    install_mock(
        monkeypatch,
        lambda request: httpx.Response(
            200, headers={"content-encoding": "gzip"}, stream=ForbiddenStream()
        ),
    )
    manifest, files = await probe.rehearse(filing=FILING, corp="00000001", credential=SECRET)
    assert manifest["status"] == "blocked" and manifest["request_count"] == 1 and not files


@pytest.mark.parametrize("raw", [b"[]", b"true", b'"not an object"'])
async def test_non_object_collection_is_a_closed_failure(monkeypatch, raw):
    install_mock(monkeypatch, lambda request: streamed(raw))
    manifest, files = await probe.rehearse(filing=FILING, corp="00000001", credential=SECRET)
    assert manifest["status"] == "blocked" and manifest["request_count"] == 1 and not files


async def test_late_cpu_deadline_cannot_leave_a_completed_receipt(monkeypatch):
    import time

    baseline = time.monotonic()
    calls = iter([baseline, baseline + 21, baseline + 21])
    monkeypatch.setattr(probe, "monotonic", lambda: next(calls))

    def respond(request):
        if request.url.params["last_reprt_at"] == "N":
            return streamed(listing_case(rm="정"))
        return streamed({"status": "013"})

    install_mock(monkeypatch, respond)
    manifest, files = await probe.rehearse(filing=FILING, corp="00000001", credential=SECRET)
    assert manifest["status"] == "blocked" and manifest["elapsed_seconds"] == 21
    assert manifest["enriched_count"] == 0 and not files


def test_private_output_is_exclusive_and_owner_only(monkeypatch, tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=5)
    (tmp_path / ".gitignore").write_text(".tmp/\n")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    path = probe.private_output(tmp_path / ".tmp/probe")
    probe.write_private(path / "manifest.json", {"status": "synthetic"})
    assert path.stat().st_mode & 0o777 == 0o700
    assert (path / "manifest.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        probe.private_output(path)
    with pytest.raises(ValueError):
        probe.private_output(tmp_path / "public")


def test_workflow_is_manual_pinned_secret_scoped_and_ciphertext_only():
    root = Path(__file__).parents[3]
    raw = (root / "ops/private-runtime/dart-preparation.yml").read_text()
    config = yaml.load(raw, Loader=yaml.BaseLoader)
    assert set(config["on"]) == {"workflow_dispatch"} and config["permissions"] == {
        "contents": "read"
    }
    assert set(re.findall(r"vars\.([A-Z_]+)", raw)) == {"REVIEWED_DART_PREPARATION_SHA"}
    assert re.findall(r"secrets\.([A-Z_]+)", raw) == ["OPENDART_API_KEY"]
    job = config["jobs"]["probe"]
    steps = job["steps"]
    assert "github.event.repository.private == true" in job["if"]
    names = [step.get("name") for step in steps]
    assert names.index("Validate recipient encryption before source credentials") < names.index(
        "Rehearse shared DART preparation"
    )
    uploads = [
        step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    assert (
        len(uploads) == 1
        and uploads[0]["with"]["path"].endswith(".sealed")
        and uploads[0]["with"]["retention-days"] == "1"
    )
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
        if "run" in step:
            assert "${{ inputs." not in step["run"]
            subprocess.run(["bash", "-n"], input=step["run"], text=True, check=True, timeout=5)
