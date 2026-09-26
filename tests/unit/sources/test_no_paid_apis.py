"""Tests for ``scripts/check_no_paid_apis.py`` (the CI cost guard).

Pins NFR-002 AC-2.2: the cost guard runs and exits 0 on the current
sources tree (v1 has no paid-API references), and exits 1 with a
clear message when the blocklist is populated and matches.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "check_no_paid_apis.py"


def _load_script_module() -> ModuleType:
    """Load the script as a module so tests can introspect / patch it."""

    spec = importlib.util.spec_from_file_location("check_no_paid_apis", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_hf_adapter(extra: str = "") -> str:
    return (
        'HF_API_BASE = "https://api.hfdatalibrary.com/v1"\n'
        'HF_API_HOST = "api.hfdatalibrary.com"\n'
        'HF_API_KEY_ENV = "HF_DATA_API_KEY"\n'
        "HF_TOKEN_QUERY = (\n"
        '    ("timeframe", "daily"),\n'
        '    ("format", "parquet"),\n'
        '    ("version", "clean"),\n'
        ")\n"
        "async def _request_bounded(client, url):\n"
        '    request = client.build_request("GET", url, headers={}, timeout=None)\n'
        "    return await client.send(\n"
        "        request, stream=True, auth=None, follow_redirects=False\n"
        "    )\n"
        "async def _fetch_ticker_once(client, ticker, api_key, budget, config):\n"
        "    token_body = await _request_bounded(\n"
        "        client, _token_url(ticker), api_key=api_key,\n"
        "        accept=_TOKEN_MEDIA_TYPE, expected_media_type=_TOKEN_MEDIA_TYPE,\n"
        "        response_limit=config.token_response_limit, budget=budget, config=config,\n"
        "    )\n"
        "    signed_url = _parse_token(token_body, ticker)\n"
        "    parquet_body = await _request_bounded(\n"
        "        client, signed_url, api_key=None,\n"
        "        accept=_PARQUET_MEDIA_TYPE, expected_media_type=_PARQUET_MEDIA_TYPE,\n"
        "        response_limit=config.parquet_response_limit, budget=budget, config=config,\n"
        "    )\n"
        "    return parquet_body\n"
        f"{extra}"
    )


def test_script_exists() -> None:
    assert _SCRIPT.exists(), f"missing CI cost guard: {_SCRIPT}"


def test_subprocess_invocation_passes_on_current_sources() -> None:
    # The committed blocklist is non-empty; current sources still avoid
    # paid-first providers.
    # The subprocess form is what CI executes.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"check_no_paid_apis.py failed unexpectedly:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_find_offenders_returns_empty_on_clean_sources() -> None:
    script = _load_script_module()
    assert script.find_offenders() == []


def test_blocklist_is_non_empty() -> None:
    script = _load_script_module()
    assert script.BLOCKLIST
    assert script.HF_REQUIRED_ASSIGNMENTS
    assert {"api.hfdatalibrary.com"} == script.HF_ALLOWED_DOMAIN_LITERALS


def test_find_offenders_detects_match_when_blocklist_populated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Verify the detection mechanism actually works by patching in a
    # pattern that matches the live FOMC adapter. Without this test,
    # the empty-blocklist path could silently regress.
    script = _load_script_module()
    monkeypatch.setattr(script, "BLOCKLIST", [r"federalreserve\.gov"])

    offenders = script.find_offenders()
    assert offenders, "blocklist with federalreserve.gov should match fomc_rss.py"
    assert any("fomc_rss.py" in str(off[0]) for off in offenders)


@pytest.mark.parametrize(
    "text",
    [
        "import blpapi\n",
        "host = 'https://api.refinitiv.com/data'\n",
        "token = os.environ['FACTSET_API_KEY']\n",
        "provider = 'Nasdaq Data Link'\n",
        "import quandl\n",
        "name = 'Morningstar Direct'\n",
    ],
)
def test_find_offenders_detects_paid_first_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
) -> None:
    script = _load_script_module()
    fake_sources = tmp_path / "sources"
    fake_sources.mkdir()
    (fake_sources / "paid.py").write_text(text, encoding="utf-8")
    monkeypatch.setattr(script, "SOURCES_ROOT", fake_sources)

    offenders = script.find_offenders()
    assert offenders


def test_find_offenders_allows_current_free_public_provider_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_sources = tmp_path / "sources"
    fake_sources.mkdir()
    (fake_sources / "free.py").write_text(
        "FRED_API_KEY = 'free official key env var allowed'\n"
        "BEA_API_KEY = 'free official key env var allowed'\n"
        "url = 'https://fred.stlouisfed.org/'\n"
        "url2 = 'https://api.stlouisfed.org/fred/series/observations'\n"
        "url3 = 'https://apps.bea.gov/api/data/'\n"
        "url4 = 'https://data.sec.gov/submissions/'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "SOURCES_ROOT", fake_sources)

    assert script.find_offenders() == []


def test_hf_adapter_contract_rejects_fallback_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter("url = 'https://query1.finance.yahoo.com/v8/chart/SPY'\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any("yahoo" in offender[2] or "yahoo" in offender[3] for offender in offenders)


def test_hf_adapter_contract_rejects_unknown_second_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter("SECONDARY_HOST = 'api.tiingo.com'\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any("tiingo" in offender[2] for offender in offenders)


def test_hf_adapter_contract_rejects_constructed_second_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter('SECONDARY = "https:" + "//" + "api" + "." + "tiingo" + "." + "com"\n'),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any(offender[2] == "constructed URL/domain" for offender in offenders)


@pytest.mark.parametrize(
    "extra",
    [
        'SECONDARY = "".join(("https:", "//", "api", ".", "tiingo", ".", "com"))\n',
        'SECONDARY = f"https://api.tiingo.com"\n',
        'HF_API_BASE = "".join(("https://", "api.hfdatalibrary.com", "/v1"))\n',
    ],
)
def test_hf_adapter_contract_rejects_constructed_or_reassigned_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: str,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(_minimal_hf_adapter(extra), encoding="utf-8")
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    assert script.find_offenders()


def test_hf_adapter_contract_rejects_unapproved_internal_provider_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter("from investo.sector_dashboard.alt import provider\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any("investo.sector_dashboard.alt" in offender[2] for offender in offenders)


def test_hf_adapter_contract_rejects_additional_network_sink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter(
            "async def fallback(client, request):\n    await client.send(request)\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any(offender[2] == "send" for offender in offenders)


def test_hf_adapter_contract_rejects_additional_request_call_site(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter(
            "async def hidden(client, dynamic_url, budget, config):\n"
            "    return await _request_bounded(\n"
            "        client, url=dynamic_url, api_key=None,\n"
            "        accept=_PARQUET_MEDIA_TYPE, expected_media_type=_PARQUET_MEDIA_TYPE,\n"
            "        response_limit=config.parquet_response_limit, budget=budget, config=config,\n"
            "    )\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any(offender[2] == "_request_bounded call sites" for offender in offenders)


@pytest.mark.parametrize(
    "extra",
    [
        (
            "from httpx import AsyncClient\n"
            "async def fetch_backup(url):\n"
            "    async with AsyncClient() as backup_client:\n"
            "        return await backup_client.get(url)\n"
        ),
        (
            "import httpx as hx\n"
            "async def fetch_backup(url):\n"
            "    async with hx.AsyncClient() as backup_client:\n"
            "        return await backup_client.get(url)\n"
        ),
    ],
)
def test_hf_adapter_contract_rejects_adapter_owned_http_clients(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: str,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(_minimal_hf_adapter(extra), encoding="utf-8")
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any(offender[2] in {"get", "AsyncClient", "httpx", "hx"} for offender in offenders)


@pytest.mark.parametrize(
    "extra",
    [
        (
            "async def hidden(client, url):\n"
            "    sender = client.send\n"
            '    outbound = httpx.Request("GET", url)\n'
            "    return await sender(outbound)\n"
        ),
        ("async def hidden(url):\n    requester = httpx.get\n    return await requester(url)\n"),
        ('async def hidden(url):\n    return await getattr(httpx, "get")(url)\n'),
    ],
)
def test_hf_adapter_contract_rejects_indirect_network_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: str,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(_minimal_hf_adapter(extra), encoding="utf-8")
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any(
        offender[3]
        in {
            "adapter-owned HTTP request forbidden",
            "indirect network-capable method reference forbidden",
            "reflective network access forbidden",
        }
        for offender in offenders
    )


@pytest.mark.parametrize(
    "extra",
    [
        "requester = _request_bounded\n",
        'requester = globals()["_request_bounded"]\n',
        'requester = httpx.__dict__["get"]\n',
    ],
)
def test_hf_adapter_contract_rejects_reflective_or_aliased_request_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: str,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(_minimal_hf_adapter(extra), encoding="utf-8")
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    assert script.find_offenders()


def test_hf_adapter_contract_requires_fixed_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        _minimal_hf_adapter("selected = runtime_config.base_url\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert any(offender[2] == "base_url" for offender in offenders)


def test_hf_adapter_contract_cannot_pin_identity_in_comments_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    fake_adapter = tmp_path / "hf_data.py"
    fake_adapter.write_text(
        "# HF_API_BASE = 'https://api.hfdatalibrary.com/v1'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "HF_ADAPTER_PATH", fake_adapter)

    offenders = script.find_offenders()
    assert len(offenders) >= len(script.HF_REQUIRED_ASSIGNMENTS)
