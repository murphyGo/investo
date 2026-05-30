"""Tests for ``scripts/check_curated_assets.py`` (the u86 license-clearance gate).

Pins AC-1.2: the gate passes on the seed library (deferred keys allowed),
fails on an unmanifested binary, fails on a silent empty, and passes on an
explicit-deferred fixture. Also pins the excluded-category rejection (R3 /
AC-1.3) at the clearance layer.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from investo.visuals.curated import CuratedLibraryError, load_library
from tests.unit.visuals._image_bytes import VALID_PNG_BYTES

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_curated_assets.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_curated_assets", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(folder: Path, asset_id: str, **over: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "curated-licensed",
        "source_url": "https://commons.wikimedia.org/wiki/File:X.png",
        "license": "public-domain",
        "attribution": "Example",
        "author": "Example author",
        "fetched_on": "2026-05-28",
        "allowed_use": "public republish",
    }
    payload.update(over)
    (folder / f"{asset_id}.manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_script_exists() -> None:
    assert _SCRIPT.exists()


def test_gate_passes_on_seed_library_subprocess() -> None:
    # The committed all-deferred seed library passes (exit 0) — what CI runs.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, f"gate failed:\n{result.stdout}\n{result.stderr}"


def test_gate_passes_on_explicit_deferred(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    _manifest(folder, "bitcoin", allowed_use="not-yet-available — basis pending")
    script = _load_script()
    exit_code, _messages = script.check(tmp_path)
    assert exit_code == 0


def test_gate_passes_on_filed(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    _manifest(folder, "bitcoin")
    (folder / "bitcoin.png").write_bytes(VALID_PNG_BYTES)
    script = _load_script()
    exit_code, _messages = script.check(tmp_path)
    assert exit_code == 0


def test_gate_fails_on_unmanifested_binary(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    folder.mkdir(parents=True)
    (folder / "orphan.png").write_bytes(VALID_PNG_BYTES)
    script = _load_script()
    exit_code, messages = script.check(tmp_path)
    assert exit_code == 1
    assert any("manifest" in m for m in messages)


def test_gate_fails_on_silent_empty(tmp_path: Path) -> None:
    folder = tmp_path / "topic"
    _manifest(folder, "kospi")  # manifest, no binary, no deferral marker
    script = _load_script()
    exit_code, messages = script.check(tmp_path)
    assert exit_code == 1
    assert any("silent empty" in m for m in messages)


def test_gate_fails_on_disallowed_license(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    _manifest(folder, "bitcoin", license="all-rights-reserved")
    (folder / "bitcoin.png").write_bytes(VALID_PNG_BYTES)
    script = _load_script()
    exit_code, messages = script.check(tmp_path)
    assert exit_code == 1
    assert any("not cleared" in m for m in messages)


# --------------------------------------------------------------------------- #
# Excluded-category rejection (R3 / AC-1.3) — one per category
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "license_token",
    [
        "ap-photo",  # news-article photo
        "reddit-meme",  # community meme
        "nike-trademark",  # corporate trademark logo
        "paparazzi-unofficial",  # unofficial photo of a real person
    ],
)
def test_excluded_categories_rejected(tmp_path: Path, license_token: str) -> None:
    folder = tmp_path / "asset"
    _manifest(folder, "bitcoin", license=license_token)
    (folder / "bitcoin.png").write_bytes(VALID_PNG_BYTES)
    with pytest.raises(CuratedLibraryError):
        load_library(tmp_path)
