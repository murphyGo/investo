"""Tests for the u86 curated context-asset library (load / clearance / selection)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from investo.models import NormalizedItem
from investo.visuals.curated import (
    CuratedAsset,
    CuratedLibraryError,
    CuratedSelection,
    RegistryEntry,
    assert_registry_integrity,
    default_registry,
    load_library,
    select_curated_asset,
)
from investo.visuals.policy import (
    CURATED_DEFERRAL_MARKER,
    EXTERNAL_IMAGE_SCRAPING_ENABLED,
    ExternalAssetManifest,
    assert_curated_asset_allowed,
    is_curated_license_clean,
)
from tests.unit.visuals._image_bytes import VALID_PNG_BYTES


def _manifest_payload(
    *,
    license_name: str = "public-domain",
    allowed_use: str = "public republish on Pages + Telegram",
    source_url: str = "https://commons.wikimedia.org/wiki/File:Example.png",
    attribution: str = "Example attribution",
    author: str = "Example author",
) -> dict[str, str]:
    return {
        "kind": "curated-licensed",
        "source_url": source_url,
        "license": license_name,
        "attribution": attribution,
        "author": author,
        "fetched_on": "2026-05-28",
        "allowed_use": allowed_use,
    }


def _write_manifest(folder: Path, asset_id: str, payload: dict[str, str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{asset_id}.manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_clean_png(folder: Path, asset_id: str, **manifest_kwargs: str) -> None:
    _write_manifest(folder, asset_id, _manifest_payload(**manifest_kwargs))
    (folder / f"{asset_id}.png").write_bytes(VALID_PNG_BYTES)


def _defer(folder: Path, asset_id: str, *, via_marker_file: bool = False) -> None:
    if via_marker_file:
        _write_manifest(folder, asset_id, _manifest_payload())
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{asset_id}.deferred").write_text("", encoding="utf-8")
    else:
        _write_manifest(
            folder,
            asset_id,
            _manifest_payload(allowed_use=f"{CURATED_DEFERRAL_MARKER} — basis pending"),
        )


def _item(title: str, *, summary: str = "", category: str = "news") -> NormalizedItem:
    return NormalizedItem(
        source_name="test-source",
        category=category,  # type: ignore[arg-type]
        title=title,
        summary=summary or None,
        url="https://example.com/x",
        published_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        raw_metadata={},
    )


# --------------------------------------------------------------------------- #
# Clearance (R2 / R3 / R4) — Step 1
# --------------------------------------------------------------------------- #


def test_scraping_stays_disabled() -> None:
    assert EXTERNAL_IMAGE_SCRAPING_ENABLED is False


def test_assert_curated_allowed_with_scraping_disabled() -> None:
    manifest = ExternalAssetManifest.model_validate(_manifest_payload())
    # Must NOT raise even though scraping is disabled (R4).
    assert_curated_asset_allowed(manifest)


def test_assert_curated_rejects_missing_manifest() -> None:
    with pytest.raises(Exception):  # noqa: B017 - ExternalAssetPolicyError
        assert_curated_asset_allowed(None)


def test_assert_curated_rejects_disallowed_license() -> None:
    manifest = ExternalAssetManifest.model_validate(
        _manifest_payload(license_name="all-rights-reserved")
    )
    with pytest.raises(Exception):  # noqa: B017
        assert_curated_asset_allowed(manifest)


def test_assert_curated_rejects_wrong_kind() -> None:
    payload = _manifest_payload()
    payload["kind"] = "explicit-license"
    manifest = ExternalAssetManifest.model_validate(payload)
    with pytest.raises(Exception):  # noqa: B017
        assert_curated_asset_allowed(manifest)


@pytest.mark.parametrize(
    "token",
    ["public-domain", "PD", "CC0", "cc0-1.0", "Unsplash", "unsplash-license", "Pexels"],
)
def test_clean_license_tokens(token: str) -> None:
    assert is_curated_license_clean(token)


@pytest.mark.parametrize("token", ["all-rights-reserved", "getty", "ap-photo", "rights-managed"])
def test_dirty_license_tokens(token: str) -> None:
    assert not is_curated_license_clean(token)


# --------------------------------------------------------------------------- #
# Library load + state machine (R1 / R8 / E5) — Step 2
# --------------------------------------------------------------------------- #


def test_load_filed_asset(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "asset", "bitcoin")
    library = load_library(tmp_path)
    assert library["bitcoin"].state == "filed"
    assert library["bitcoin"].path is not None


def test_load_deferred_via_allowed_use_marker(tmp_path: Path) -> None:
    _defer(tmp_path / "asset", "ethereum")
    library = load_library(tmp_path)
    assert library["ethereum"].state == "deferred"
    assert library["ethereum"].path is None


def test_load_deferred_via_marker_file(tmp_path: Path) -> None:
    _defer(tmp_path / "topic", "wall-street", via_marker_file=True)
    library = load_library(tmp_path)
    assert library["wall-street"].state == "deferred"


def test_silent_empty_is_invalid(tmp_path: Path) -> None:
    # Manifest present, no binary, no deferral marker -> (invalid) -> RED.
    _write_manifest(tmp_path / "topic", "kospi", _manifest_payload())
    with pytest.raises(CuratedLibraryError, match="silent empty"):
        load_library(tmp_path)


def test_binary_without_manifest_is_invalid(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    folder.mkdir(parents=True)
    (folder / "orphan.png").write_bytes(VALID_PNG_BYTES)
    with pytest.raises(CuratedLibraryError, match="no sibling manifest"):
        load_library(tmp_path)


def test_disallowed_license_filed_is_invalid(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "asset", "bitcoin", license_name="all-rights-reserved")
    with pytest.raises(CuratedLibraryError, match="not cleared"):
        load_library(tmp_path)


def test_over_budget_binary_is_invalid(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    _write_manifest(folder, "bitcoin", _manifest_payload())
    oversized = VALID_PNG_BYTES + b"\x00" * (600 * 1024)
    (folder / "bitcoin.png").write_bytes(oversized)
    with pytest.raises(CuratedLibraryError, match="budget"):
        load_library(tmp_path)


def test_binary_plus_deferral_marker_is_invalid(tmp_path: Path) -> None:
    folder = tmp_path / "asset"
    _file_clean_png(folder, "bitcoin", allowed_use=f"{CURATED_DEFERRAL_MARKER} — oops")
    with pytest.raises(CuratedLibraryError, match="both a binary and a deferral"):
        load_library(tmp_path)


def test_unknown_category_is_invalid(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "weird", "bitcoin")
    with pytest.raises(CuratedLibraryError, match="unknown category"):
        load_library(tmp_path)


def test_missing_root_is_empty_library(tmp_path: Path) -> None:
    assert load_library(tmp_path / "absent") == {}


# --------------------------------------------------------------------------- #
# Secret hygiene (R7 / AC-1.6) — Step 2
# --------------------------------------------------------------------------- #


def test_manifest_with_secret_is_rejected(tmp_path: Path) -> None:
    # A Telegram-bot-token-shaped value in attribution must be rejected.
    secret = "123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR"
    _file_clean_png(tmp_path / "asset", "bitcoin", attribution=secret)
    with pytest.raises(CuratedLibraryError, match="secret"):
        load_library(tmp_path)


# --------------------------------------------------------------------------- #
# Registry integrity (I8) — Step 3
# --------------------------------------------------------------------------- #


def test_dangling_registry_id_fails(tmp_path: Path) -> None:
    library: dict[str, CuratedAsset] = {}
    registry = (
        RegistryEntry(
            key="asset:bitcoin", asset_ids=("bitcoin",), segment_affinity=frozenset({"crypto"})
        ),
    )
    with pytest.raises(CuratedLibraryError, match="unknown asset id"):
        assert_registry_integrity(registry, library)


def test_orphan_filed_asset_warns_not_fails(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "asset", "bitcoin")
    library = load_library(tmp_path)
    orphans = assert_registry_integrity((), library)
    assert orphans == ["bitcoin"]


def test_seed_registry_integrity_against_seed_library() -> None:
    # The committed seed library + default registry must be internally consistent.
    from investo.visuals.curated import LIBRARY_ROOT

    repo_root = Path(__file__).resolve().parents[3]
    library = load_library(repo_root / LIBRARY_ROOT)
    assert_registry_integrity(default_registry(), library)
    # All seeds ship deferred in this unit.
    assert all(asset.state == "deferred" for asset in library.values())


# --------------------------------------------------------------------------- #
# Selection — determinism + segment awareness (R5 / R6) — Step 3
# --------------------------------------------------------------------------- #


def _crypto_library(tmp_path: Path) -> dict[str, CuratedAsset]:
    _file_clean_png(tmp_path / "asset", "bitcoin")
    return load_library(tmp_path)


def test_select_powell_on_fomc_evidence(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "jerome-powell")
    library = load_library(tmp_path)
    items = (_item("Powell signals patience at FOMC", summary="rate decision ahead"),)
    selection = select_curated_asset("us-equity", items, library, default_registry())
    assert selection.asset is not None
    assert selection.matched_key == "person:jerome-powell"


def test_select_bitcoin_on_crypto_segment(tmp_path: Path) -> None:
    library = _crypto_library(tmp_path)
    items = (_item("Bitcoin rallies past resistance", summary="BTC up"),)
    selection = select_curated_asset("crypto", items, library, default_registry())
    assert selection.asset is not None
    assert selection.matched_key == "asset:bitcoin"


def test_selection_is_byte_stable(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "jerome-powell")
    library = load_library(tmp_path)
    items = (_item("Powell speaks", summary="FOMC"),)
    a = select_curated_asset("us-equity", items, library, default_registry())
    b = select_curated_asset("us-equity", items, library, default_registry())
    assert a == b


def test_segment_affinity_excludes_candidate(tmp_path: Path) -> None:
    # Bitcoin is crypto-only; a us-equity segment must not select it.
    library = _crypto_library(tmp_path)
    items = (_item("Bitcoin in the news", summary="BTC"),)
    selection = select_curated_asset("us-equity", items, library, default_registry())
    assert selection.asset is None


def test_empty_segment_selects_nothing(tmp_path: Path) -> None:
    library = _crypto_library(tmp_path)
    selection = select_curated_asset("crypto", (), library, default_registry())
    assert selection.asset is None


def test_deferred_key_is_not_selectable(tmp_path: Path) -> None:
    # bitcoin is deferred -> even on a matching crypto segment, selection is None.
    _defer(tmp_path / "asset", "bitcoin")
    library = load_library(tmp_path)
    items = (_item("Bitcoin rallies", summary="BTC up"),)
    selection = select_curated_asset("crypto", items, library, default_registry())
    assert selection.asset is None


def test_no_match_returns_clean_none() -> None:
    selection = select_curated_asset("crypto", (), {}, default_registry())
    assert selection == CuratedSelection(asset=None)
