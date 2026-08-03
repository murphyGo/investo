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
    RegistryEntry,
    SemanticAlias,
    assert_registry_integrity,
    default_registry,
    load_library,
    select_curated_asset,
)
from investo.visuals.image_selection import build_image_narrative_context
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


def _context(text: str, *, segment: str = "us-equity") -> object:
    markdown = (
        "# 시황\n"
        f"> **오늘의 결론**: {text}\n"
        f"> **핵심 동인**: {text}\n\n"
        "## ② 전일 핵심 이슈\n\n"
        f"### 첫 이슈\n\n{text}\n\n"
        "### 둘째 이슈\n\n후속 내용\n\n"
        "## ③ 섹터/수급 동향\n"
    )
    return build_image_narrative_context(segment, markdown)  # type: ignore[arg-type]


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
            key="asset:bitcoin",
            asset_ids=("bitcoin",),
            segment_affinity=frozenset({"crypto"}),
            aliases=(SemanticAlias("Bitcoin", 10),),
        ),
    )
    with pytest.raises(CuratedLibraryError, match="unknown asset id"):
        assert_registry_integrity(registry, library)


def test_orphan_filed_asset_fails(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "asset", "bitcoin")
    library = load_library(tmp_path)
    with pytest.raises(CuratedLibraryError, match="orphan curated assets"):
        assert_registry_integrity((), library)


def test_seed_registry_integrity_against_seed_library() -> None:
    # The committed seed library + default registry must be internally consistent.
    from investo.visuals.curated import LIBRARY_ROOT

    repo_root = Path(__file__).resolve().parents[3]
    library = load_library(repo_root / LIBRARY_ROOT)
    assert assert_registry_integrity(default_registry(), library) == []
    # 2026-08-03: all seed keys are filed with license-verified binaries.
    # load_library() has already applied the full clearance gate here;
    # this pins the operator-facing steady state: no deferred stragglers.
    assert all(asset.state == "filed" for asset in library.values())
    assert len(library) == 19


# --------------------------------------------------------------------------- #
# Selection — determinism + segment awareness (R5 / R6) — Step 3
# --------------------------------------------------------------------------- #


def _crypto_library(tmp_path: Path) -> dict[str, CuratedAsset]:
    _file_clean_png(tmp_path / "asset", "bitcoin")
    return load_library(tmp_path)


def test_select_powell_on_named_primary_story(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "jerome-powell")
    library = load_library(tmp_path)
    context = _context("Jerome Powell signals patience at the meeting")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.asset is not None
    assert selection.matched_key == "person:jerome-powell"


def test_generic_fomc_evidence_selects_topic_not_powell(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "jerome-powell")
    _file_clean_png(tmp_path / "topic", "federal-reserve")
    library = load_library(tmp_path)
    context = _context("FOMC rate decision moved Treasury yields")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.asset is not None
    assert selection.matched_key == "topic:federal-reserve"


def test_current_warsh_fomc_story_never_selects_powell(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "kevin-warsh")
    _file_clean_png(tmp_path / "person", "jerome-powell")
    _file_clean_png(tmp_path / "topic", "federal-reserve")
    library = load_library(tmp_path)
    context = _context("Kevin Warsh chaired the FOMC rate decision")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.matched_key == "person:kevin-warsh"
    assert selection.asset is not None
    assert selection.asset.asset_id == "kevin-warsh"


def test_named_bessent_story_selects_bessent_portrait(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "scott-bessent")
    _file_clean_png(tmp_path / "topic", "macro")
    library = load_library(tmp_path)
    context = _context("Scott Bessent discussed the Treasury market outlook")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.matched_key == "person:scott-bessent"
    assert selection.asset is not None
    assert selection.asset.asset_id == "scott-bessent"


@pytest.mark.parametrize(
    ("asset_id", "text", "expected_key"),
    [
        ("kevin-warsh", "케빈 워시가 연준 통화정책을 설명했다", "person:kevin-warsh"),
        ("scott-bessent", "스콧 베선트가 미 국채 시장을 설명했다", "person:scott-bessent"),
    ],
)
def test_korean_named_current_official_selects_portrait(
    tmp_path: Path,
    asset_id: str,
    text: str,
    expected_key: str,
) -> None:
    _file_clean_png(tmp_path / "person", asset_id)
    library = load_library(tmp_path)
    selection = select_curated_asset("us-equity", _context(text), library, default_registry())
    assert selection.matched_key == expected_key
    assert selection.asset is not None
    assert selection.asset.asset_id == asset_id


def test_generic_official_roles_do_not_select_new_portraits(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "kevin-warsh")
    _file_clean_png(tmp_path / "person", "scott-bessent")
    library = load_library(tmp_path)
    context = _context("The Fed Chair met the Treasury Secretary")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.asset is None


def test_powell_name_in_link_destination_is_not_person_evidence(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "jerome-powell")
    library = load_library(tmp_path)
    context = _context(
        "[Kevin Warsh policy history](https://news.example.com/jerome-powell-history)"
    )
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.asset is None


def test_generic_president_role_does_not_select_trump_portrait(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "us-president")
    library = load_library(tmp_path)
    context = _context("The President met advisers at the White House")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.asset is None


def test_named_trump_story_can_select_trump_portrait(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "us-president")
    library = load_library(tmp_path)
    context = _context("Donald Trump announced a new trade policy")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.matched_key == "person:us-president"


def test_select_bitcoin_on_crypto_segment(tmp_path: Path) -> None:
    library = _crypto_library(tmp_path)
    context = _context("Bitcoin rallies past resistance", segment="crypto")
    selection = select_curated_asset("crypto", context, library, default_registry())
    assert selection.asset is not None
    assert selection.matched_key == "asset:bitcoin"


def test_selection_is_byte_stable(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "jerome-powell")
    library = load_library(tmp_path)
    context = _context("Powell speaks about policy")
    a = select_curated_asset("us-equity", context, library, default_registry())
    b = select_curated_asset("us-equity", context, library, default_registry())
    assert a == b


def test_specific_driver_alias_outranks_broad_market_alias(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "topic", "market")
    _file_clean_png(tmp_path / "topic", "data-center")
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key="topic:market",
            asset_ids=("market",),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias("미국 증시", 30),),
        ),
        RegistryEntry(
            key="topic:data-center",
            asset_ids=("data-center",),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias("데이터센터", 0),),
        ),
    )
    context = _context("미국 증시는 데이터센터 투자 확대를 반영했다")
    selection = select_curated_asset("us-equity", context, library, registry)
    assert selection.matched_key == "topic:data-center"
    assert selection.semantic_rank == 0


def test_dated_kospi_chart_requires_explicit_history_context(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "topic", "kospi")
    _file_clean_png(tmp_path / "topic", "kospi-history")
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key="topic:kospi",
            asset_ids=("kospi",),
            segment_affinity=frozenset({"domestic-equity"}),
            aliases=(SemanticAlias("KOSPI", 10), SemanticAlias("코스피", 10)),
        ),
        RegistryEntry(
            key="topic:kospi-history",
            asset_ids=("kospi-history",),
            segment_affinity=frozenset({"domestic-equity"}),
            aliases=(
                SemanticAlias("KOSPI history", 0),
                SemanticAlias("코스피 장기 추이", 0),
            ),
        ),
    )
    current = select_curated_asset(
        "domestic-equity",
        _context("KOSPI rose in today's session", segment="domestic-equity"),
        library,
        registry,
    )
    historical = select_curated_asset(
        "domestic-equity",
        _context("KOSPI history shows a long cycle", segment="domestic-equity"),
        library,
        registry,
    )
    current_long_term = select_curated_asset(
        "domestic-equity",
        _context("코스피 장기 투자자 수급을 점검한다", segment="domestic-equity"),
        library,
        registry,
    )
    assert current.asset is not None and current.asset.asset_id == "kospi"
    assert current_long_term.asset is not None
    assert current_long_term.asset.asset_id == "kospi"
    assert historical.asset is not None
    assert historical.asset.asset_id == "kospi-history"


def test_bitcoin_miner_requires_explicit_mining_context(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "asset", "bitcoin")
    _file_clean_png(tmp_path / "asset", "bitcoin-miner")
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key="asset:bitcoin",
            asset_ids=("bitcoin",),
            segment_affinity=frozenset({"crypto"}),
            aliases=(SemanticAlias("Bitcoin", 10),),
        ),
        RegistryEntry(
            key="topic:bitcoin-mining",
            asset_ids=("bitcoin-miner",),
            segment_affinity=frozenset({"crypto"}),
            aliases=(SemanticAlias("Bitcoin mining", 0),),
        ),
    )
    generic = select_curated_asset(
        "crypto",
        _context("Bitcoin ETF inflows increased", segment="crypto"),
        library,
        registry,
    )
    mining = select_curated_asset(
        "crypto",
        _context("Bitcoin mining hashrate increased", segment="crypto"),
        library,
        registry,
    )
    assert generic.asset is not None and generic.asset.asset_id == "bitcoin"
    assert mining.asset is not None and mining.asset.asset_id == "bitcoin-miner"


@pytest.mark.parametrize(
    ("asset_id", "key", "text", "alias"),
    [
        ("gold", "asset:gold", "금 가격이 안전자산 수요로 올랐다", "금 가격"),
        (
            "renewable-grid",
            "topic:clean-energy",
            "재생에너지 투자가 전력망 수요를 키웠다",
            "재생에너지",
        ),
    ],
)
def test_specific_new_topic_assets_are_reachable(
    tmp_path: Path,
    asset_id: str,
    key: str,
    text: str,
    alias: str,
) -> None:
    category = "asset" if key.startswith("asset:") else "topic"
    _file_clean_png(tmp_path / category, asset_id)
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key=key,
            asset_ids=(asset_id,),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias(alias, 0),),
        ),
    )
    selection = select_curated_asset("us-equity", _context(text), library, registry)
    assert selection.asset is not None
    assert selection.asset.asset_id == asset_id
    assert selection.semantic_rank == 0


def test_same_rank_uses_earliest_reader_visible_alias_not_registry_order(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "person", "powell")
    _file_clean_png(tmp_path / "topic", "wall-street")
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key="person:powell",
            asset_ids=("powell",),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias("Jerome Powell", 10),),
        ),
        RegistryEntry(
            key="topic:wall-street",
            asset_ids=("wall-street",),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias("S&P 500", 10),),
        ),
    )
    context = _context("S&P 500 변동 뒤 Jerome Powell 발언이 이어졌다")
    selection = select_curated_asset("us-equity", context, library, registry)
    assert selection.matched_key == "topic:wall-street"
    assert selection.semantic_offset is not None


def test_digest_variant_reaches_every_filed_asset_and_is_stable(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "asset", "bitcoin-a")
    _file_clean_png(tmp_path / "asset", "bitcoin-b")
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key="asset:bitcoin",
            asset_ids=("bitcoin-a", "bitcoin-b"),
            segment_affinity=frozenset({"crypto"}),
            aliases=(SemanticAlias("Bitcoin", 10),),
        ),
    )
    selected: set[str] = set()
    for ordinal in range(100):
        context = _context(f"Bitcoin 시나리오 {ordinal}", segment="crypto")
        first = select_curated_asset("crypto", context, library, registry)
        second = select_curated_asset("crypto", context, library, registry)
        assert first == second
        assert first.variant_contract == "narrative-key-digest-mod-v1"
        assert first.variant_count == 2
        assert first.variant_index in {0, 1}
        assert first.asset is not None
        selected.add(first.asset.asset_id)
    assert selected == {"bitcoin-a", "bitcoin-b"}


def test_registry_rejects_same_rank_alias_ambiguity(tmp_path: Path) -> None:
    _file_clean_png(tmp_path / "topic", "one")
    _file_clean_png(tmp_path / "topic", "two")
    library = load_library(tmp_path)
    registry = (
        RegistryEntry(
            key="topic:one",
            asset_ids=("one",),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias("shared", 10),),
        ),
        RegistryEntry(
            key="topic:two",
            asset_ids=("two",),
            segment_affinity=frozenset({"us-equity"}),
            aliases=(SemanticAlias("SHARED", 10),),
        ),
    )
    with pytest.raises(CuratedLibraryError, match="ambiguous"):
        assert_registry_integrity(registry, library)


def test_segment_affinity_excludes_candidate(tmp_path: Path) -> None:
    # Bitcoin is crypto-only; a us-equity segment must not select it.
    library = _crypto_library(tmp_path)
    context = _context("Bitcoin in the news")
    selection = select_curated_asset("us-equity", context, library, default_registry())
    assert selection.asset is None


def test_empty_segment_selects_nothing(tmp_path: Path) -> None:
    library = _crypto_library(tmp_path)
    context = build_image_narrative_context("crypto", "# empty")
    selection = select_curated_asset("crypto", context, library, default_registry())
    assert selection.asset is None


def test_deferred_key_is_not_selectable(tmp_path: Path) -> None:
    # bitcoin is deferred -> even on a matching crypto segment, selection is None.
    _defer(tmp_path / "asset", "bitcoin")
    library = load_library(tmp_path)
    context = _context("Bitcoin rallies", segment="crypto")
    selection = select_curated_asset("crypto", context, library, default_registry())
    assert selection.asset is None


def test_no_match_returns_clean_none() -> None:
    context = build_image_narrative_context("crypto", "# empty")
    selection = select_curated_asset("crypto", context, {}, default_registry())
    assert selection.asset is None
    assert selection.narrative_sha256 == context.narrative_sha256
