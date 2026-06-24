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
