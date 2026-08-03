"""Curated context-asset library — load, clearance, and selection (u86).

A pre-curated, pre-verified, *committed* local image library mapped by
entity / topic keys, drawn from at briefing-generation time. There is
**no runtime scraping** (``EXTERNAL_IMAGE_SCRAPING_ENABLED`` stays
``False`` and is never read on this path — R4 / AC-1.5); the library is
read from pre-cleared local files only.

Design choices / pins
----------------------
* Reuses, never rebuilds:
  - ``visuals/policy.py`` ``ExternalAssetManifest`` with the new
    ``kind="curated-licensed"`` literal (E2 / TS-2 — no parallel
    manifest type) and :func:`assert_curated_asset_allowed`.
  - ``visuals/assets.py`` PNG / JPEG / SVG signature + dimension gate
    (TS-1 — no pillow, no new parser).
  - ``visuals/provenance.py`` for the provenance caption + manifest
    write (single secret-redaction chokepoint, R7 / AC-1.6).
  - ``briefing/watchlist.py`` matcher primitives for entity extraction
    (R6 — no new fuzzy matcher).
* Deterministic selection: no wall-clock, no RNG, no hash-order (R5).
* Deferred-asset state machine (E5 / R8): a registered key may lack a
  committed binary only under an explicit marker; silent empties are
  ``(invalid)`` and fail the gate.

The CI gate lives in ``scripts/check_curated_assets.py`` (TS-3) and
calls :func:`load_library` over the committed root.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

from pydantic import ValidationError

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.models.segments import MarketSegment
from investo.visuals.policy import (
    CURATED_DEFERRAL_MARKER,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    assert_curated_asset_allowed,
)


class _NarrativeContext(Protocol):
    hero_markdown: str
    narrative_sha256: str


CuratedAssetState = Literal["filed", "deferred"]

# Default committed library root. Lives at the repo run-time/committed
# asset domain (parallel to ``archive/``), NOT under ``docs/`` or
# ``aidlc-docs/``.
LIBRARY_ROOT: Final[Path] = Path("assets/library")
_ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset({".png", ".jpg", ".jpeg", ".svg"})
_ALLOWED_CATEGORIES: Final[frozenset[str]] = frozenset({"person", "topic", "asset"})
_MANIFEST_SUFFIX: Final[str] = ".manifest.json"
_DEFERRED_SUFFIX: Final[str] = ".deferred"
_HEX64_RE: Final[str] = r"^[0-9a-f]{64}$"

# AC-1.1 — storage budget. Raster ≤ 500 KB, SVG ≤ 64 KB per asset;
# total library footprint ≤ 20 MB across all filed assets.
_MAX_RASTER_BYTES: Final[int] = 500 * 1024
_MAX_SVG_BYTES: Final[int] = 64 * 1024
_MAX_TOTAL_BYTES: Final[int] = 20 * 1024 * 1024


class CuratedLibraryError(ValueError):
    """Raised when the curated library fails clearance / load (gate RED)."""


@dataclass(frozen=True, slots=True)
class CuratedAsset:
    """A single committed (or deferred) library entry (E1)."""

    asset_id: str
    category: str
    manifest: ExternalAssetManifest
    state: CuratedAssetState
    path: Path | None  # None iff state == "deferred"


@dataclass(frozen=True, slots=True)
class SemanticAlias:
    """One reader-visible alias with an explicit semantic specificity rank."""

    text: str
    rank: int


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """An entity/topic → asset_ids mapping with segment affinity (E3)."""

    key: str
    asset_ids: tuple[str, ...]
    segment_affinity: frozenset[str]
    aliases: tuple[SemanticAlias, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticMatch:
    """Bounded alias evidence used for deterministic candidate ordering."""

    key: str
    alias: str
    rank: int
    offset: int
    registry_order: int
    alias_order: int


@dataclass(frozen=True, slots=True)
class CuratedSelection:
    """The deterministic per-segment selection result (E4)."""

    asset: CuratedAsset | None
    matched_key: str | None = None
    match_reason: str = "no-match"
    narrative_sha256: str | None = None
    semantic_rank: int | None = None
    semantic_offset: int | None = None
    variant_contract: str | None = None
    variant_index: int | None = None
    variant_count: int = 0


# ---------------------------------------------------------------------------
# Library load + clearance (build time / CI)
# ---------------------------------------------------------------------------


def manifest_path_for(asset_path: Path) -> Path:
    """Return the curated manifest sidecar path (``{stem}.manifest.json``)."""
    return asset_path.with_name(f"{asset_path.stem}{_MANIFEST_SUFFIX}")


def load_library(root: Path = LIBRARY_ROOT) -> dict[str, CuratedAsset]:
    """Walk ``root``, classify + clear every entry, return ``{asset_id: CuratedAsset}``.

    Raises :class:`CuratedLibraryError` on the first invalid entry
    (R1 / R8 / AC-1.2). Deferred entries pass. An empty / missing root
    is a valid (empty) library.
    """
    if not root.exists():
        return {}
    assets: dict[str, CuratedAsset] = {}
    total_bytes = 0
    for manifest_path in sorted(root.rglob(f"*{_MANIFEST_SUFFIX}")):
        asset_id = manifest_path.name.removesuffix(_MANIFEST_SUFFIX)
        category = manifest_path.parent.name
        if category not in _ALLOWED_CATEGORIES:
            raise CuratedLibraryError(
                f"curated asset {asset_id!r} in unknown category folder {category!r}"
            )
        manifest = _read_curated_manifest(manifest_path, asset_id=asset_id)
        _assert_no_secret_manifest(manifest, asset_id=asset_id)
        binary_path = _find_binary(manifest_path.parent, asset_id)
        deferred = _is_deferred(manifest_path.parent, asset_id, manifest)

        if binary_path is None:
            if not deferred:
                raise CuratedLibraryError(
                    f"curated asset {asset_id!r} has a manifest but no binary and no "
                    f"explicit deferral marker (silent empty rejected — R8)"
                )
            if asset_id in assets:
                raise CuratedLibraryError(f"duplicate curated asset id {asset_id!r}")
            assets[asset_id] = CuratedAsset(
                asset_id=asset_id,
                category=category,
                manifest=manifest,
                state="deferred",
                path=None,
            )
            continue

        if deferred:
            raise CuratedLibraryError(
                f"curated asset {asset_id!r} has both a binary and a deferral marker"
            )
        try:
            assert_curated_asset_allowed(manifest)
        except ExternalAssetPolicyError as exc:
            raise CuratedLibraryError(f"curated asset {asset_id!r} not cleared: {exc}") from exc
        total_bytes += _assert_binary_within_budget(binary_path, asset_id=asset_id)
        if asset_id in assets:
            raise CuratedLibraryError(f"duplicate curated asset id {asset_id!r}")
        assets[asset_id] = CuratedAsset(
            asset_id=asset_id,
            category=category,
            manifest=manifest,
            state="filed",
            path=binary_path,
        )

    _assert_no_orphan_binaries(root, assets)
    if total_bytes > _MAX_TOTAL_BYTES:
        raise CuratedLibraryError(
            f"curated library total footprint {total_bytes} exceeds {_MAX_TOTAL_BYTES} bytes"
        )
    return assets


def assert_registry_integrity(
    registry: Sequence[RegistryEntry],
    library: Mapping[str, CuratedAsset],
) -> list[str]:
    """Fail closed on every ambiguous, dangling, duplicate, or orphan mapping."""

    referenced: dict[str, str] = {}
    seen_keys: set[str] = set()
    seen_aliases: dict[tuple[str, int, str], str] = {}
    for entry in registry:
        if entry.key in seen_keys:
            raise CuratedLibraryError(f"duplicate registry key {entry.key!r}")
        seen_keys.add(entry.key)
        if not entry.asset_ids:
            raise CuratedLibraryError(f"registry key {entry.key!r} has no asset ids")
        if not entry.aliases:
            raise CuratedLibraryError(f"registry key {entry.key!r} has no semantic aliases")
        if not entry.segment_affinity:
            raise CuratedLibraryError(f"registry key {entry.key!r} has no segment affinity")
        local_asset_ids: set[str] = set()
        for asset_id in entry.asset_ids:
            if asset_id in local_asset_ids:
                raise CuratedLibraryError(
                    f"registry key {entry.key!r} repeats asset id {asset_id!r}"
                )
            local_asset_ids.add(asset_id)
            if asset_id not in library:
                raise CuratedLibraryError(
                    f"registry key {entry.key!r} references unknown asset id {asset_id!r}"
                )
            previous_key = referenced.get(asset_id)
            if previous_key is not None:
                raise CuratedLibraryError(
                    f"asset id {asset_id!r} is referenced by both {previous_key!r} "
                    f"and {entry.key!r}"
                )
            referenced[asset_id] = entry.key
        local_aliases: set[tuple[int, str]] = set()
        for alias in entry.aliases:
            normalized = alias.text.strip().casefold()
            if not normalized or alias.rank < 0:
                raise CuratedLibraryError(
                    f"registry key {entry.key!r} has an invalid semantic alias"
                )
            local_identity = (alias.rank, normalized)
            if local_identity in local_aliases:
                raise CuratedLibraryError(
                    f"registry key {entry.key!r} repeats alias {alias.text!r}"
                )
            local_aliases.add(local_identity)
            for segment in entry.segment_affinity:
                identity = (segment, alias.rank, normalized)
                previous_key = seen_aliases.get(identity)
                if previous_key is not None and previous_key != entry.key:
                    raise CuratedLibraryError(
                        f"semantic alias {alias.text!r} rank {alias.rank} is ambiguous "
                        f"for segment {segment!r}: {previous_key!r} vs {entry.key!r}"
                    )
                seen_aliases[identity] = entry.key
    orphans = sorted(asset_id for asset_id in library if asset_id not in referenced)
    if orphans:
        raise CuratedLibraryError("orphan curated assets are not selectable: " + ", ".join(orphans))
    return []


def _read_curated_manifest(manifest_path: Path, *, asset_id: str) -> ExternalAssetManifest:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CuratedLibraryError(f"curated asset {asset_id!r} manifest unreadable: {exc}") from exc
    try:
        return ExternalAssetManifest.model_validate(payload)
    except ValidationError as exc:
        raise CuratedLibraryError(f"curated asset {asset_id!r} manifest invalid: {exc}") from exc


def _assert_no_secret_manifest(manifest: ExternalAssetManifest, *, asset_id: str) -> None:
    """Reject any manifest field whose text carries a secret shape (R7 / AC-1.6)."""
    fields = (
        str(manifest.source_url),
        manifest.license,
        manifest.attribution,
        manifest.author,
        manifest.allowed_use,
    )
    for value in fields:
        if redact_text(value, policy=RedactionPolicy.STRICT) != value:
            raise CuratedLibraryError(
                f"curated asset {asset_id!r} manifest contains a secret-shaped value (R7)"
            )


def _find_binary(folder: Path, asset_id: str) -> Path | None:
    for ext in sorted(_ALLOWED_EXTENSIONS):
        candidate = folder / f"{asset_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def _is_deferred(folder: Path, asset_id: str, manifest: ExternalAssetManifest) -> bool:
    if (folder / f"{asset_id}{_DEFERRED_SUFFIX}").exists():
        return True
    return CURATED_DEFERRAL_MARKER in manifest.allowed_use


def _assert_binary_within_budget(binary_path: Path, *, asset_id: str) -> int:
    """Validate signature + dimensions + byte budget; return byte size (AC-1.1 / R4)."""
    # Reuse the existing assets.py signature/dimension gate (TS-1) — no
    # new parser, and the binary-only variant so we do not require a
    # generated provenance sidecar (curated assets carry a separate
    # ``.manifest.json``).
    from investo.visuals.assets import VisualAssetError, validate_visual_binary

    if binary_path.suffix not in _ALLOWED_EXTENSIONS:
        raise CuratedLibraryError(
            f"curated asset {asset_id!r} has unsupported format {binary_path.suffix!r}"
        )
    size = binary_path.stat().st_size
    cap = _MAX_SVG_BYTES if binary_path.suffix == ".svg" else _MAX_RASTER_BYTES
    if size > cap:
        raise CuratedLibraryError(
            f"curated asset {asset_id!r} is {size} bytes, over the {cap}-byte budget"
        )
    try:
        validate_visual_binary(binary_path)
    except VisualAssetError as exc:
        raise CuratedLibraryError(
            f"curated asset {asset_id!r} failed binary/dimension gate: {exc}"
        ) from exc
    return size


def _assert_no_orphan_binaries(root: Path, assets: Mapping[str, CuratedAsset]) -> None:
    """Reject a binary that has no sibling manifest (R1)."""
    known_paths = {asset.path for asset in assets.values() if asset.path is not None}
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix not in _ALLOWED_EXTENSIONS:
            continue
        if candidate in known_paths:
            continue
        # Manifest-less binary, or a binary whose manifest sidecar is absent.
        raise CuratedLibraryError(f"curated binary {candidate.name!r} has no sibling manifest (R1)")


# ---------------------------------------------------------------------------
# Entity extraction + deterministic selection (generation time)
# ---------------------------------------------------------------------------


# Semantic aliases are explicit registry metadata. Person entries contain
# names only: a role/institution term can select a topic asset, never a
# specific office-holder portrait (U-141 R4).
def _alias(text: str, rank: int) -> SemanticAlias:
    return SemanticAlias(text=text, rank=rank)


_KEY_ALIASES: Final[Mapping[str, tuple[SemanticAlias, ...]]] = {
    "person:kevin-warsh": (
        _alias("Kevin Warsh", 10),
        _alias("Kevin M. Warsh", 10),
        _alias("Warsh", 10),
        _alias("케빈 워시", 10),
    ),
    "person:scott-bessent": (
        _alias("Scott Bessent", 10),
        _alias("Scott K. Bessent", 10),
        _alias("Bessent", 10),
        _alias("스콧 베선트", 10),
        _alias("베선트", 10),
    ),
    "person:jerome-powell": (
        _alias("Jerome Powell", 10),
        _alias("Powell", 10),
        _alias("제롬 파월", 10),
        _alias("파월", 10),
    ),
    "person:us-president": (
        _alias("Donald Trump", 10),
        _alias("Donald J. Trump", 10),
        _alias("Trump", 10),
        _alias("도널드 트럼프", 10),
        _alias("트럼프", 10),
    ),
    "topic:federal-reserve": (
        _alias("Federal Reserve", 10),
        _alias("Fed", 10),
        _alias("FOMC", 10),
        _alias("연준", 10),
        _alias("기준금리", 10),
        _alias("rate decision", 10),
    ),
    "topic:wall-street": (
        _alias("NYSE", 10),
        _alias("S&P 500", 10),
        _alias("Dow", 10),
        _alias("Nasdaq", 10),
        _alias("Wall Street", 20),
        _alias("월스트리트", 20),
    ),
    "topic:us-equity-market": (
        _alias("trading floor", 20),
        _alias("US stocks", 30),
        _alias("equities", 30),
        _alias("미국 증시", 30),
    ),
    "topic:stock-market-chart": (
        _alias("market chart", 40),
        _alias("rally", 40),
        _alias("selloff", 40),
        _alias("증시", 40),
    ),
    "asset:bitcoin": (
        _alias("Bitcoin", 10),
        _alias("BTC", 10),
        _alias("비트코인", 10),
    ),
    "topic:bitcoin-mining": (
        _alias("Bitcoin mining", 0),
        _alias("Bitcoin miner", 0),
        _alias("ASIC", 0),
        _alias("hashrate", 0),
        _alias("비트코인 채굴", 0),
        _alias("비트코인 채굴기", 0),
        _alias("해시레이트", 0),
    ),
    "asset:ethereum": (
        _alias("Ethereum", 10),
        _alias("ETH", 10),
        _alias("이더리움", 10),
    ),
    "topic:cryptocurrency": (
        _alias("blockchain", 20),
        _alias("crypto", 20),
        _alias("cryptocurrency", 20),
        _alias("가상자산", 20),
        _alias("암호화폐", 20),
    ),
    "topic:kospi": (
        _alias("KOSPI", 10),
        _alias("코스피", 10),
        _alias("KRX", 10),
    ),
    "topic:kospi-history": (
        _alias("KOSPI history", 0),
        _alias("historical KOSPI", 0),
        _alias("역대 코스피", 0),
        _alias("코스피 장기 추이", 0),
        _alias("코스피 장기 시계열", 0),
        _alias("코스피 역사", 0),
    ),
    "topic:korea-market": (
        _alias("Korea market", 20),
        _alias("한국 증시", 30),
        _alias("국내 증시", 30),
    ),
    "topic:inflation": (
        _alias("CPI", 10),
        _alias("PCE", 10),
        _alias("inflation", 10),
        _alias("물가", 10),
        _alias("인플레이션", 10),
    ),
    "topic:macro": (
        _alias("GDP", 10),
        _alias("unemployment", 10),
        _alias("macro", 40),
        _alias("거시", 40),
        _alias("경기", 40),
    ),
    "topic:semiconductor": (
        _alias("semiconductor", 0),
        _alias("AI chip", 0),
        _alias("반도체", 0),
        _alias("HBM", 0),
        _alias("파운드리", 0),
    ),
    "topic:data-center": (
        _alias("data center", 0),
        _alias("datacenter", 0),
        _alias("데이터센터", 0),
        _alias("AI infrastructure", 0),
        _alias("AI 인프라", 0),
    ),
    "topic:clean-energy": (
        _alias("clean energy", 0),
        _alias("renewable energy", 0),
        _alias("wind power", 0),
        _alias("청정에너지", 0),
        _alias("재생에너지", 0),
        _alias("풍력", 0),
    ),
    "asset:gold": (
        _alias("gold price", 0),
        _alias("gold futures", 0),
        _alias("bullion", 0),
        _alias("금값", 0),
        _alias("금 가격", 0),
        _alias("금 선물", 0),
    ),
}

_VARIANT_CONTRACT: Final[str] = "narrative-key-digest-mod-v1"


def select_curated_asset(
    segment: MarketSegment,
    context: _NarrativeContext,
    library: Mapping[str, CuratedAsset],
    registry: Sequence[RegistryEntry],
) -> CuratedSelection:
    """Deterministically select a filed curated asset for a segment (R5 / R6).

    Returns ``CuratedSelection(asset=None, ...)`` when nothing matches,
    every candidate is deferred, or the segment is empty / ambiguous —
    the caller falls through to the existing hero chain (R9).
    """
    by_key = {entry.key: entry for entry in registry}
    candidates: list[SemanticMatch] = []
    for registry_order, entry in enumerate(registry):
        if segment not in entry.segment_affinity:
            continue
        for alias_order, alias in enumerate(entry.aliases):
            offset = _semantic_alias_offset(context.hero_markdown, alias.text)
            if offset is None:
                continue
            candidates.append(
                SemanticMatch(
                    key=entry.key,
                    alias=alias.text,
                    rank=alias.rank,
                    offset=offset,
                    registry_order=registry_order,
                    alias_order=alias_order,
                )
            )

    if not candidates:
        return CuratedSelection(asset=None, narrative_sha256=context.narrative_sha256)

    candidates.sort(
        key=lambda match: (
            match.rank,
            match.offset,
            match.registry_order,
            match.alias_order,
            match.key,
        )
    )
    seen_keys: set[str] = set()
    for match in candidates:
        if match.key in seen_keys:
            continue
        seen_keys.add(match.key)
        entry = by_key[match.key]
        filed = tuple(
            asset
            for asset_id in entry.asset_ids
            if (asset := library.get(asset_id)) is not None and asset.state == "filed"
        )
        if not filed:
            continue
        if re.fullmatch(_HEX64_RE, context.narrative_sha256) is None:
            raise CuratedLibraryError("narrative digest is not a lowercase SHA-256 value")
        variant_payload = f"{context.narrative_sha256}\0{segment}\0{match.key}".encode()
        variant_digest = hashlib.sha256(variant_payload).hexdigest()
        variant_index = int(variant_digest, 16) % len(filed)
        return CuratedSelection(
            asset=filed[variant_index],
            matched_key=match.key,
            match_reason=(
                f"alias:{match.alias};scope=hero;rank={match.rank};offset={match.offset}"
            ),
            narrative_sha256=context.narrative_sha256,
            semantic_rank=match.rank,
            semantic_offset=match.offset,
            variant_contract=_VARIANT_CONTRACT,
            variant_index=variant_index,
            variant_count=len(filed),
        )
    return CuratedSelection(asset=None, narrative_sha256=context.narrative_sha256)


def _reader_visible_semantic_text(markdown: str) -> str:
    """Remove link destinations and raw HTML before semantic alias matching."""

    without_destinations = re.sub(r"\]\([^\n)]*\)", "]", markdown)
    without_autolinks = re.sub(r"<https?://[^>\n]+>", "", without_destinations)
    without_raw_urls = re.sub(r"https?://[^\s<>]+", "", without_autolinks)
    return re.sub(r"<[^>\n]+>", "", without_raw_urls)


def _semantic_alias_offset(markdown: str, alias: str) -> int | None:
    if not markdown:
        return None
    text = _reader_visible_semantic_text(markdown)
    if alias.isascii():
        match = re.search(
            rf"(?<![0-9A-Za-z]){re.escape(alias)}(?![0-9A-Za-z])",
            text,
            flags=re.IGNORECASE,
        )
        return match.start() if match is not None else None
    # Korean postpositions attach without whitespace; named/topic aliases are
    # explicit and sufficiently specific for a literal Unicode match.
    offset = text.casefold().find(alias.casefold())
    return offset if offset >= 0 else None


def default_registry() -> tuple[RegistryEntry, ...]:
    """Return the committed seed registry (E3) — segment-aware key mapping."""
    return _SEED_REGISTRY


def _entry(key: str, asset_ids: Iterable[str], affinity: Iterable[str]) -> RegistryEntry:
    return RegistryEntry(
        key=key,
        asset_ids=tuple(asset_ids),
        segment_affinity=frozenset(affinity),
        aliases=_KEY_ALIASES.get(key, ()),
    )


# Seed registry. ``segment_affinity`` gates candidacy (R6): crypto prefers
# asset:/crypto topics; us-equity prefers US topics/persons; domestic prefers
# KR topics; macro-driven content (Fed / inflation) is shared across the
# equity segments.
_SEED_REGISTRY: Final[tuple[RegistryEntry, ...]] = (
    _entry("person:kevin-warsh", ("kevin-warsh",), ("us-equity", "domestic-equity")),
    _entry("person:scott-bessent", ("scott-bessent",), ("us-equity", "domestic-equity")),
    _entry("person:jerome-powell", ("jerome-powell",), ("us-equity", "domestic-equity")),
    _entry("person:us-president", ("us-president",), ("us-equity",)),
    _entry("topic:federal-reserve", ("federal-reserve",), ("us-equity", "domestic-equity")),
    _entry("topic:wall-street", ("wall-street",), ("us-equity",)),
    _entry("topic:us-equity-market", ("us-equity-market",), ("us-equity",)),
    _entry("topic:stock-market-chart", ("stock-market-chart",), ("us-equity", "domestic-equity")),
    _entry("asset:bitcoin", ("bitcoin",), ("crypto",)),
    _entry("topic:bitcoin-mining", ("bitcoin-miner",), ("crypto",)),
    _entry("asset:ethereum", ("ethereum",), ("crypto",)),
    _entry("topic:cryptocurrency", ("cryptocurrency",), ("crypto",)),
    _entry("topic:kospi", ("kospi",), ("domestic-equity",)),
    _entry("topic:korea-market", ("korea-market",), ("domestic-equity",)),
    _entry("topic:inflation", ("inflation",), ("us-equity", "domestic-equity")),
    _entry("topic:macro", ("macro",), ("us-equity", "domestic-equity")),
    _entry(
        "topic:data-center",
        ("data-center-roof",),
        ("us-equity", "domestic-equity", "crypto"),
    ),
    _entry(
        "topic:clean-energy",
        ("renewable-grid",),
        ("us-equity", "domestic-equity"),
    ),
    _entry(
        "asset:gold",
        ("gold-bullion",),
        ("us-equity", "domestic-equity", "crypto"),
    ),
)


__all__ = [
    "LIBRARY_ROOT",
    "CuratedAsset",
    "CuratedAssetState",
    "CuratedLibraryError",
    "CuratedSelection",
    "RegistryEntry",
    "SemanticAlias",
    "SemanticMatch",
    "assert_registry_integrity",
    "default_registry",
    "load_library",
    "manifest_path_for",
    "select_curated_asset",
]
