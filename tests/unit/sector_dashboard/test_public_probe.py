"""Production-path, no-write, closed-output and workflow qualification tests."""

from __future__ import annotations

import importlib.util
import io
import json
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from pydantic import ValidationError

import investo.sector_dashboard.public_probe as probe
from investo.models.market_calendar import is_trading_day
from investo.models.sector_public import FreshnessState, PublicSourceIssueCode
from investo.sector_dashboard.hf_data import HF_API_BASE

_ROOT = Path(__file__).resolve().parents[3]
_TARGET = date(2026, 9, 25)
_SECRET = "secret-probe-sentinel-12345"
_CAPABILITY = "signed-capability-sentinel-67890"


def _parquet(*, count: int = 64, end: date = _TARGET) -> bytes:
    days = []
    cursor = end
    while len(days) < count:
        if is_trading_day("us-equity", cursor):
            days.append(datetime.combine(cursor, datetime.min.time()))
        cursor -= timedelta(days=1)
    days.reverse()
    prices = [100.0 + i * 0.1 for i in range(count)]
    table = pa.table(
        {
            "datetime": pa.array(days, type=pa.timestamp("ns")),
            "Open": pa.array(prices, type=pa.float64()),
            "High": pa.array([p + 1 for p in prices], type=pa.float64()),
            "Low": pa.array([p - 1 for p in prices], type=pa.float64()),
            "Close": pa.array(prices, type=pa.float64()),
            "Volume": pa.array([1000] * count, type=pa.int64()),
            "source": pa.array(["iex"] * count, type=pa.large_string()),
        }
    )
    output = io.BytesIO()
    pq.write_table(table, output)
    return output.getvalue()


def _transport(
    calls: list[str], *, body: bytes, failure: str | None = None, status: int = 404
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        ticker = request.url.path.rsplit("/", 1)[1]
        if ticker == failure:
            return httpx.Response(status, text=_SECRET + _CAPABILITY)
        if "/download-token/" in request.url.path:
            assert request.headers["X-API-Key"] == _SECRET
            return httpx.Response(
                200, json={"url": f"{HF_API_BASE}/download/{ticker}?token={_CAPABILITY}"}
            )
        assert "x-api-key" not in request.headers
        return httpx.Response(
            200, content=body, headers={"Content-Type": "application/octet-stream"}
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("count", "end", "failure", "status", "qualified", "successes"),
    [
        (64, _TARGET, None, 200, True, 11),
        (64, _TARGET, "XLK", 404, False, 10),
        (64, _TARGET, "SPY", 401, False, 0),
        (32, _TARGET, None, 200, False, 11),
        (5, _TARGET, None, 200, False, 11),
        (64, date(2026, 9, 24), None, 200, False, 11),
    ],
)
async def test_full_pipeline_qualifies_only_complete_fresh_data_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    end: date,
    failure: str | None,
    status: int,
    qualified: bool,
    successes: int,
) -> None:
    monkeypatch.chdir(tmp_path)
    initial_paths = set(tmp_path.rglob("*"))
    monkeypatch.setenv("HF_DATA_API_KEY", _SECRET)
    calls: list[str] = []
    async with httpx.AsyncClient(
        transport=_transport(
            calls, body=_parquet(count=count, end=end), failure=failure, status=status
        )
    ) as client:
        result = await probe.probe_public_sector(
            client, environ={"HF_DATA_API_KEY": _SECRET}, target_date=_TARGET
        )
    assert (result.status == "qualified") is qualified
    assert result.successful_symbol_count == successes
    assert result.request_count == len(calls)
    assert result.failed_request_count == (1 if failure else 0)
    assert set(tmp_path.rglob("*")) == initial_paths
    encoded = result.model_dump_json()
    assert _SECRET not in encoded and _CAPABILITY not in encoded
    assert "https://" not in encoded and '"Close"' not in encoded
    if failure == "SPY":
        assert len(calls) == 1
        assert PublicSourceIssueCode.AUTH_REJECTED in result.reason_codes
    if qualified:
        assert result.comparable_sector_count == 10
        assert result.freshness is FreshnessState.FRESH
        assert result.request_count == result.successful_response_count == 22
        assert result.snapshot_id is not None


@pytest.mark.asyncio
async def test_missing_key_makes_zero_requests() -> None:
    calls: list[str] = []
    async with httpx.AsyncClient(transport=_transport(calls, body=b"")) as client:
        result = await probe.probe_public_sector(client, environ={}, target_date=_TARGET)
    assert not calls
    assert result.status == "blocked"
    assert PublicSourceIssueCode.AUTH_CONFIGURATION in result.reason_codes


@pytest.mark.asyncio
async def test_projection_exception_never_escapes_with_sensitive_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(*args: object) -> None:
        raise RuntimeError(_SECRET + _CAPABILITY)

    monkeypatch.setattr(probe, "render_public_sector_projection", reject)
    async with httpx.AsyncClient(transport=_transport([], body=_parquet())) as client:
        result = await probe.probe_public_sector(
            client, environ={"HF_DATA_API_KEY": _SECRET}, target_date=_TARGET
        )
    assert result.reason_codes == (probe.ProbeIssueCode.INTERNAL,)
    assert result.successful_symbol_count == 11
    assert result.failed_symbol_count == 0
    assert _SECRET not in result.model_dump_json()
    assert _CAPABILITY not in result.model_dump_json()


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 25, 19, 59, tzinfo=UTC), date(2026, 9, 24)),
        (datetime(2026, 9, 25, 20, 0, tzinfo=UTC), _TARGET),
        (datetime(2026, 9, 27, 1, tzinfo=UTC), _TARGET),
        (datetime(2026, 9, 7, 21, tzinfo=UTC), date(2026, 9, 4)),
        (datetime(2026, 11, 27, 17, 59, tzinfo=UTC), date(2026, 11, 25)),
        (datetime(2026, 11, 27, 18, 0, tzinfo=UTC), date(2026, 11, 27)),
        (datetime(2026, 12, 24, 17, 59, tzinfo=UTC), date(2026, 12, 23)),
        (datetime(2026, 12, 24, 18, 0, tzinfo=UTC), date(2026, 12, 24)),
        (datetime(2026, 7, 2, 17, 30, tzinfo=UTC), date(2026, 7, 1)),
    ],
)
def test_completed_market_date(now: datetime, expected: date) -> None:
    assert probe.resolve_probe_target_date(now) == expected


@pytest.mark.parametrize("now", [datetime(2026, 9, 25), datetime(2027, 1, 1, 12, tzinfo=UTC)])
def test_unknown_calendar_and_naive_clock_fail_closed(now: datetime) -> None:
    with pytest.raises(ValueError):
        probe.resolve_probe_target_date(now)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["collection", "cpu"])
async def test_measured_resource_overrun_never_qualifies(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    from types import SimpleNamespace

    wall_ticks = iter([0.0, 120.001 if phase == "collection" else 0.001, 120.002])
    cpu_ticks = iter([0.0, 30.001 if phase == "cpu" else 0.001])
    monkeypatch.setattr(
        probe,
        "time",
        SimpleNamespace(monotonic=lambda: next(wall_ticks), process_time=lambda: next(cpu_ticks)),
    )
    async with httpx.AsyncClient(transport=_transport([], body=_parquet())) as client:
        result = await probe.probe_public_sector(
            client, environ={"HF_DATA_API_KEY": _SECRET}, target_date=_TARGET
        )
    assert result.status == "blocked"
    assert result.reason_codes == (probe.ProbeIssueCode.RESOURCE,)
    assert result.successful_symbol_count == 11


@pytest.mark.asyncio
async def test_previous_session_cannot_qualify_after_early_close() -> None:
    target = probe.resolve_probe_target_date(datetime(2026, 11, 27, 19, tzinfo=UTC))
    async with httpx.AsyncClient(
        transport=_transport([], body=_parquet(end=date(2026, 11, 25)))
    ) as client:
        result = await probe.probe_public_sector(
            client, environ={"HF_DATA_API_KEY": _SECRET}, target_date=target
        )
    assert result.status == "blocked"
    assert PublicSourceIssueCode.FRESHNESS in result.reason_codes


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "u145_public_cli", _ROOT / "scripts/build_sector_dashboard_public.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "args", [[], ["--write"], ["--api-key", _SECRET], ["--target-date", "2020-01-01"]]
)
def test_cli_rejects_unapproved_arguments_without_echo(
    args: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _cli().main(args) == 2
    output = capsys.readouterr()
    assert output.err == ""
    assert _SECRET not in output.out
    assert json.loads(output.out)["reason_codes"] == ["probe.arguments"]


@pytest.mark.parametrize("payload", [_SECRET, _CAPABILITY + "?token=abc", "x" * 5000])
def test_cli_output_gate_and_summary_reject_sensitive_or_oversized_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: str,
) -> None:
    module = _cli()

    async def fake() -> tuple[str, int]:
        return payload, 0

    monkeypatch.setattr(module, "_probe", fake)
    monkeypatch.setenv("HF_DATA_API_KEY", _SECRET)
    summary = tmp_path / "summary"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    previous = logging.root.manager.disable
    try:
        assert module.main(["--probe-only"]) == 2
    finally:
        logging.disable(previous)
    text = capsys.readouterr().out + summary.read_text()
    assert _SECRET not in text and _CAPABILITY not in text
    assert "probe.output" in text


def test_evidence_rejects_forged_success_unknown_fields_and_counts() -> None:
    with pytest.raises(ValidationError):
        probe.PublicProbeEvidence(status="qualified", target_date=_TARGET)
    with pytest.raises(ValidationError):
        probe.PublicProbeEvidence(
            status="blocked", target_date=_TARGET, reason_codes=("provider secret",)
        )
    with pytest.raises(ValidationError):
        probe.PublicProbeEvidence(
            status="blocked",
            target_date=_TARGET,
            reason_codes=(probe.ProbeIssueCode.COVERAGE,),
            request_count=1,
        )


@pytest.mark.parametrize(
    ("field", "value", "accepted"),
    [
        ("snapshot_id", "sha256:" + "a" * 64, True),
        ("provider_body", "a" * 64, False),
        ("snapshot_id", "sha256:" + "a" * 65, False),
        ("snapshot_id", "sha256:" + "A" * 64, False),
        ("commit", "a" * 40, True),
        ("run_id", "33578785358", True),
        ("provider_body", "33578785358", False),
        ("commit", "a" * 41, False),
        ("run_id", "3" * 21, False),
    ],
)
def test_summary_hash_exception_is_field_and_shape_scoped(
    field: str,
    value: str,
    accepted: bool,
) -> None:
    text = json.dumps({field: value})
    result = _cli()._screen_summary(text)
    assert (result is not None) is accepted
    if result is not None:
        assert json.loads(result) == {field: value}


@pytest.mark.parametrize(
    ("field", "secret", "value"),
    [
        ("snapshot_id", "a" * 64, "sha256:" + "a" * 64),
        ("commit", "a" * 40, "a" * 40),
        ("run_id", "33578785358", "33578785358"),
    ],
)
def test_configured_secret_is_checked_before_hash_exception(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    secret: str,
    value: str,
) -> None:
    monkeypatch.setenv("HF_DATA_API_KEY", secret)
    assert _cli()._screen_summary(json.dumps({field: value})) is None


def test_escaped_configured_secret_cannot_bypass_hash_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_DATA_API_KEY", "c" * 64)
    text = '{"snapshot_id":"sha256:' + r"\u0063" * 64 + '"}'
    assert _cli()._screen_summary(text) is None


@pytest.mark.parametrize("valid_metadata", [True, False])
def test_cli_executes_real_pipeline_and_emits_only_verified_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    valid_metadata: bool,
) -> None:
    module = _cli()
    client_class = httpx.AsyncClient
    calls: list[str] = []
    transport = _transport(calls, body=_parquet())

    def create_client(**kwargs: object) -> httpx.AsyncClient:
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return client_class(transport=transport, **kwargs)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 9, 25, 22, tzinfo=UTC)

    monkeypatch.setattr(module.httpx, "AsyncClient", create_client)
    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setenv("HF_DATA_API_KEY", _SECRET)
    monkeypatch.setenv("GITHUB_SHA", "a" * 40 if valid_metadata else _SECRET)
    monkeypatch.setenv("GITHUB_RUN_ID", "33578785358" if valid_metadata else _CAPABILITY)
    summary = tmp_path / "summary"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    before = set(tmp_path.rglob("*"))
    previous = logging.root.manager.disable
    try:
        assert module.main(["--probe-only"]) == 0
    finally:
        logging.disable(previous)
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "qualified" and result["request_count"] == len(calls) == 22
    assert result["commit"] == ("a" * 40 if valid_metadata else None)
    assert result["run_id"] == ("33578785358" if valid_metadata else None)
    assert captured.out.strip() in summary.read_text()
    assert captured.err == ""
    assert _SECRET not in captured.out and _CAPABILITY not in captured.out
    assert set(tmp_path.rglob("*")) - before == {summary}


def test_probe_workflow_is_manual_read_only_and_secret_scoped() -> None:
    text = (_ROOT / ".github/workflows/sector-dashboard-probe.yml").read_text()
    workflow = yaml.safe_load(text)
    assert workflow.get("on", workflow.get(True)) == {"workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read"}
    assert "env" not in workflow
    assert len(workflow["jobs"]) == 1
    job = next(iter(workflow["jobs"].values()))
    assert "env" not in job and "permissions" not in job
    assert job["timeout-minutes"] == 10
    secret_steps = [s for s in job["steps"] if "HF_DATA_API_KEY" in s.get("env", {})]
    assert len(secret_steps) == 1
    assert secret_steps[0]["run"].endswith("build_sector_dashboard_public.py --probe-only")
    assert "persist-credentials: false" in text and "enable-cache: false" in text
    assert "uv sync --frozen --extra sector --no-dev" in text
    assert "benchmark_sector_dashboard_public.py" in text
    for forbidden in (
        "schedule:",
        "upload-artifact",
        "deploy-pages",
        "git push",
        "telegram",
        "daily-briefing",
    ):
        assert forbidden not in text.lower()
    assert not (_ROOT / "site_docs/sectors").exists()
    assert "sectors/" not in (_ROOT / "mkdocs.yml").read_text()
