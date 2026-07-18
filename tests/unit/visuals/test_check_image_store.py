"""Tests for ``scripts/check_image_store.py`` (the u137 license-compliance gate).

Pins Contract #6 / AC-1.1 / AC-1.2 / AC-1.3: the clean paired store —
built by the REAL Step 3 machinery (``fetch_cleared_candidates``) so the
gate provably accepts what the store writer produces — passes; the
binding green states (empty store / metadata-only-everything / blocked
marker without binary) pass; and every failure class fails with its own
distinct, actionable message: orphan binary, orphan sidecar,
clearance-less binary, content-hash mismatch, per-file and store-total
budget breaches, unrecognized extension, I9 hash-mismatched clearance,
unparseable clearance, and an R13 secret-pattern hit (which must name
the pattern, never the secret value).

All roots are ``tmp_path``-injected via the script's ``check(store_root,
ledger_root)`` seam (same convention as ``test_check_curated_assets``).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from investo.models import NormalizedItem
from investo.visuals.image_library import (
    append_candidates,
    candidate_id_for_url,
    clearances_dir_for,
    fetch_cleared_candidates,
    read_index,
    store_binary_path,
    store_sidecar_path,
    update_index,
)
from investo.visuals.policy import ExternalAssetManifest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_image_store.py"

_TARGET = date(2026, 7, 16)
_URL = "https://img.yna.co.kr/photo/reuters/gate-test.jpg"

# Minimal valid PNG (64x48) clearing the u19 100-byte floor.
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    + (13).to_bytes(4, "big")
    + b"IHDR"
    + (64).to_bytes(4, "big")
    + (48).to_bytes(4, "big")
    + b"\x08\x06\x00\x00\x00"
    + b"\x00" * 100
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_image_store", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item() -> NormalizedItem:
    return NormalizedItem(
        source_name="yonhap-market",
        category="news",
        title="게이트 테스트 기사",
        url="https://www.yna.co.kr/view/GATE001",
        published_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
        raw_metadata={"image_url": _URL, "image_mime": "image/jpeg"},
    )


def _write_clearance(registry: Path, *, source_url: str = _URL, body: str | None = None) -> str:
    cid = candidate_id_for_url(_URL)
    path = clearances_dir_for(ledger_root=registry) / f"{cid}.manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if body is not None:
        path.write_text(body, encoding="utf-8")
        return cid
    manifest = ExternalAssetManifest(
        kind="explicit-license",
        source_url=source_url,  # type: ignore[arg-type]
        license="CC BY 4.0",
        attribution="Example Agency / CC BY 4.0",
        author="Example Agency",
        fetched_on=_TARGET,
        allowed_use="Public redistribution with attribution",
    )
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return cid


def _registry_only(tmp_path: Path) -> tuple[Path, Path]:
    """Ledger + index, no clearances, no store (metadata-only-everything)."""
    registry = tmp_path / "image_candidates"
    store = tmp_path / "assets" / "images"
    append_candidates(_TARGET, {"domestic-equity": [_item()]}, ledger_root=registry)
    update_index(_TARGET, ledger_root=registry)
    return store, registry


def _clean_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    """Build a fully paired store via the real Step 3 fetch machinery."""
    store, registry = _registry_only(tmp_path)
    cid = _write_clearance(registry)
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    monkeypatch.delenv("INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS", raising=False)

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=_PNG_BYTES)

    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        report = fetch_cleared_candidates(
            read_index(ledger_root=registry),
            ledger_root=registry,
            store_root=store,
            client=client,
        )
    assert report.stored == 1  # fixture sanity
    monkeypatch.delenv("INVESTO_EXTERNAL_IMAGE_ASSETS", raising=False)
    return store, registry, cid


# ---------------------------------------------------------------------------
# Green states (AC-1.2 binding)
# ---------------------------------------------------------------------------


def test_script_exists() -> None:
    assert _SCRIPT.exists()


def test_gate_passes_on_committed_repo_subprocess() -> None:
    # What CI runs: the committed repo (store absent/empty) passes.
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, f"gate failed:\n{result.stdout}\n{result.stderr}"


def test_empty_store_passes(tmp_path: Path) -> None:
    script = _load_script()
    exit_code, messages = script.check(tmp_path / "assets" / "images", tmp_path / "registry")
    assert exit_code == 0
    assert any("image store OK" in m for m in messages)


def test_metadata_only_everything_passes(tmp_path: Path) -> None:
    # Ledgers + index present, zero binaries, zero clearances — the
    # default posture (I17) is green: the gate polices the store, not
    # the operator's clearance backlog.
    store, registry = _registry_only(tmp_path)
    script = _load_script()
    exit_code, _messages = script.check(store, registry)
    assert exit_code == 0


def test_blocked_marker_without_binary_passes(tmp_path: Path) -> None:
    store, registry = _registry_only(tmp_path)
    cid = candidate_id_for_url(_URL)
    marker = clearances_dir_for(ledger_root=registry) / f"{cid}.blocked"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    script = _load_script()
    exit_code, _messages = script.check(store, registry)
    assert exit_code == 0


def test_clean_paired_store_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The gate accepts exactly what the Step 3 store writer produces.
    store, registry, _cid = _clean_store(tmp_path, monkeypatch)
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 0
    assert any("1 binaries, 1 sidecars" in m for m in messages)


# ---------------------------------------------------------------------------
# Failure classes — one distinct message each
# ---------------------------------------------------------------------------


def test_binary_without_sidecar_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, registry, cid = _clean_store(tmp_path, monkeypatch)
    store_sidecar_path(store_binary_path(cid, ".png", store_root=store)).unlink()
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("no provenance sidecar (I12)" in m for m in messages)


def test_orphan_sidecar_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, registry, cid = _clean_store(tmp_path, monkeypatch)
    store_binary_path(cid, ".png", store_root=store).unlink()
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("orphan sidecar" in m for m in messages)


def test_binary_without_clearance_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, registry, cid = _clean_store(tmp_path, monkeypatch)
    (clearances_dir_for(ledger_root=registry) / f"{cid}.manifest.json").unlink()
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("no clearance manifest (R7/AC-1.2)" in m for m in messages)


def test_content_sha_mismatch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, registry, cid = _clean_store(tmp_path, monkeypatch)
    binary = store_binary_path(cid, ".png", store_root=store)
    binary.write_bytes(binary.read_bytes() + b"\x00tampered")
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("content_sha256 does not match" in m for m in messages)


def test_per_file_budget_breach_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, registry, cid = _clean_store(tmp_path, monkeypatch)
    binary = store_binary_path(cid, ".png", store_root=store)
    binary.write_bytes(_PNG_BYTES + b"\x00" * 2_000_001)
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("per-file budget breach" in m and "AC-1.1" in m for m in messages)


def test_store_total_budget_breach_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The clean store trips a shrunken total budget — avoids writing
    # 50 MB in a unit test; the constant is the injection seam.
    store, registry, _cid = _clean_store(tmp_path, monkeypatch)
    script = _load_script()
    script._STORE_TOTAL_BUDGET_BYTES = 100
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("store total budget breach" in m and "AC-1.1" in m for m in messages)


def test_unrecognized_extension_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, registry, cid = _clean_store(tmp_path, monkeypatch)
    (store / cid[:2] / f"{cid}.gif").write_bytes(b"GIF89a" + b"\x00" * 100)
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("unrecognized store entry" in m for m in messages)


def test_hash_mismatched_clearance_fails_even_without_binary(tmp_path: Path) -> None:
    # I9 / AC-1.2 — RED even when nothing was stored for it.
    store, registry = _registry_only(tmp_path)
    _write_clearance(registry, source_url="https://img.example.com/other.jpg")
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("does not hash to the candidate id (I9)" in m for m in messages)


def test_unparseable_clearance_fails_even_without_binary(tmp_path: Path) -> None:
    store, registry = _registry_only(tmp_path)
    _write_clearance(registry, body="{broken json")
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("unparseable (I8, fail-closed)" in m for m in messages)


def test_r13_secret_hit_fails_and_names_pattern_not_value(tmp_path: Path) -> None:
    # AC-1.3 — a GitHub-PAT-shaped value injected into a ledger goes
    # RED; the message names the pattern, never the secret itself.
    store, registry = _registry_only(tmp_path)
    secret = "ghp_" + "a1B2" * 9  # 36-char PAT body
    ledger = registry / "2026" / "2026-07-16.jsonl"
    ledger.write_text(
        ledger.read_text(encoding="utf-8") + f'{{"note": "{secret}"}}\n',
        encoding="utf-8",
    )
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 1
    assert any("R13 secret-pattern hit" in m and "github_pat" in m for m in messages)
    assert all(secret not in m for m in messages)


def test_r13_scan_tolerates_bare_hex_digests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The ratified digest exemption: candidate ids / content hashes in
    # sidecars, ledgers, and the index are 64-hex values the generic
    # long-base64 pattern would flag — the clean store must stay green.
    store, registry, _cid = _clean_store(tmp_path, monkeypatch)
    script = _load_script()
    exit_code, messages = script.check(store, registry)
    assert exit_code == 0, messages
