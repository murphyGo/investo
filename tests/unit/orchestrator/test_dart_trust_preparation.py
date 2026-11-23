"""Explicit trust diagnostics use fresh discovery and the shared HTTP owner."""

import json
from pathlib import Path

import pytest
from scripts import probe_dart_preparation as probe

from tests.unit.orchestrator import test_dart_preparation_probe as helpers
from tests.unit.orchestrator.test_dart_preparation_u184 import SECRET, listing_case
from tests.unit.sources.test_dart_document_u173 import archive_case
from tests.unit.sources.test_dart_trust_document import FILING, FIXTURE, NOW, trust_item


@pytest.mark.parametrize("second", [False, True])
async def test_trust_rehearsal_rediscovers_current_identity_and_replays_native(monkeypatch, second):
    first = trust_item()
    newer = first.model_copy()
    if second:
        entry = listing_case(first)["list"][0]
        entry["rcept_no"] = "20261123000002"
        newer = probe.DartDisclosureAdapter()._normalize_entry(entry, date_precision=True)
    payload = listing_case(first)
    if second:
        payload["list"].append(listing_case(newer)["list"][0])
        payload["total_count"] = 2
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path == "/api/list.json":
            return helpers.streamed(payload)
        filing = request.url.params["rcept_no"]
        return helpers.streamed(archive_case(FIXTURE.read_text(), name=filing + ".xml"))

    monkeypatch.setattr(helpers, "NOW", NOW)
    helpers.install_mock(monkeypatch, respond)
    manifest, files = await probe.rehearse(
        filing=FILING, corp="00000001", credential=SECRET, parser_profile="trust-termination"
    )
    assert manifest["status"] == "completed"
    assert manifest["request_count"] == len(calls) == (5 if second else 3)
    assert manifest["enriched_count"] == manifest["native_context_count"] == 1 + int(second)
    assert manifest["model_call_count"] == 0 and not manifest["activation_ready"]
    assert manifest["parser_profile"] == "trust-termination"
    assert manifest["discovered_filing"] == ("20261123000002" if second else None)
    assert calls[0].url.params["last_reprt_at"] == "N"
    assert all(
        r.url.params["last_reprt_at"] == "Y" for r in calls[1:] if r.url.path == "/api/list.json"
    )
    assert SECRET not in json.dumps(files)
    assert all(
        o["dart"]["parser_version"] == "dart-trust-termination-6.2-v1"
        for o in files["prepared-items.json"]["outcomes"]
    )


async def test_trust_v2_is_rejected_before_credentials_or_http(monkeypatch):
    monkeypatch.setattr(probe, "RecordingTransport", lambda: pytest.fail("invalid profile HTTP"))
    manifest, files = await probe.rehearse(
        filing=FILING,
        corp="00000001",
        credential=SECRET,
        parser_profile="trust-termination",
        parser_version="v2",
    )
    assert manifest["reason"] == "input_invalid" and manifest["request_count"] == 0 and not files


async def test_trust_policy_mismatch_is_rejected_before_discovery(monkeypatch):
    class FixedClock(probe.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is None else NOW.astimezone(tz)

    monkeypatch.setattr(probe, "datetime", FixedClock)
    monkeypatch.setattr(probe, "RecordingTransport", lambda: pytest.fail("unqualified HTTP"))
    monkeypatch.setattr(probe, "_dart_transport_allowed", lambda *args: False)
    manifest, files = await probe.rehearse(
        filing=FILING, corp="00000001", credential=SECRET, parser_profile="trust-termination"
    )
    assert manifest["reason"] == "qualification_invalid" and not files


def test_private_workflow_admits_only_explicit_v1_trust_profile():
    text = (Path(__file__).parents[3] / "ops/private-runtime/dart-preparation.yml").read_text()
    assert "options: [price, schedule, trust-termination]" in text
    assert '[[ "$PARSER_PROFILE" == "price" || "$DART_PARSER_VERSION" == "v1" ]]' in text
    assert "REVIEWED_DART_PREPARATION_SHA" in text and "retention-days: 1" in text
