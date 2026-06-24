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

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import ValidationError

from investo._internal.redaction import RedactionPolicy, redact_text
from investo._internal.watchlist_matching import match_term_with_aliases as _match_term_with_aliases
from investo.models import NormalizedItem
from investo.models.segments import MarketSegment
from investo.models.watchlist import WatchlistTermKind
from investo.visuals.policy import (
    CURATED_DEFERRAL_MARKER,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    assert_curated_asset_allowed,
)

CuratedAssetState = Literal["filed", "deferred"]

# Default committed library root. Lives at the repo run-time/committed
# asset domain (parallel to ``archive/``), NOT under ``docs/`` or
# ``aidlc-docs/``.
LIBRARY_ROOT: Final[Path] = Path("assets/library")
_ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset({".png", ".jpg", ".jpeg", ".svg"})
_ALLOWED_CATEGORIES: Final[frozenset[str]] = frozenset({"person", "topic", "asset"})
_MANIFEST_SUFFIX: Final[str] = ".manifest.json"
_DEFERRED_SUFFIX: Final[str] = ".deferred"

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
class RegistryEntry:
    """An entity/topic → asset_ids mapping with segment affinity (E3)."""

    key: str
    asset_ids: tuple[str, ...]
    segment_affinity: frozenset[str]


@dataclass(frozen=True, slots=True)
class CuratedSelection:
    """The deterministic per-segment selection result (E4)."""

    asset: CuratedAsset | None
    matched_key: str | None = None
    match_reason: str = "no-match"


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
    """Assert every registry asset_id resolves; return orphan (unregistered) ids.

    A dangling registry id (no library entry) is a gate failure (I8 /
    R8). An orphan filed asset (in the library, never referenced) is
    allowed but never selectable — returned as a warning list, not a
    failure.
    """
    referenced: set[str] = set()
    for entry in registry:
        for asset_id in entry.asset_ids:
            if asset_id not in library:
                raise CuratedLibraryError(
                    f"registry key {entry.key!r} references unknown asset id {asset_id!r}"
                )
            referenced.add(asset_id)
    return sorted(asset_id for asset_id in library if asset_id not in referenced)


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

# The key namespace's term used for matching is the slug after the
# ``namespace:`` prefix, with hyphens treated as a phrase. We additionally
# match a human alias map so e.g. ``person:jerome-powell`` matches
# "Powell" / "파월" / "FOMC". The matcher reuses u64 boundary primitives.
_KEY_ALIASES: Final[Mapping[str, tuple[str, ...]]] = {
    "person:jerome-powell": ("Powell", "파월", "Jerome Powell", "Fed Chair", "FOMC", "연준 의장"),
    "person:us-president": ("President", "White House", "대통령", "백악관"),
    "topic:federal-reserve": (
        "Federal Reserve",
        "Fed",
        "FOMC",
        "연준",
        "기준금리",
        "rate decision",
    ),
    "topic:wall-street": ("Wall Street", "NYSE", "월스트리트", "S&P 500", "Dow", "Nasdaq"),
    "topic:us-equity-market": ("US stocks", "equities", "미국 증시", "trading floor"),
    "topic:stock-market-chart": ("market chart", "rally", "selloff", "증시"),
    "asset:bitcoin": ("Bitcoin", "BTC", "비트코인"),
    "asset:ethereum": ("Ethereum", "ETH", "이더리움"),
    "topic:cryptocurrency": ("crypto", "cryptocurrency", "blockchain", "가상자산", "암호화폐"),
    "topic:kospi": ("KOSPI", "코스피", "KRX", "Korea market", "한국 증시"),
    "topic:korea-market": ("KOSPI", "코스피", "Korea", "한국 증시"),
    "topic:inflation": ("inflation", "CPI", "PCE", "물가", "인플레이션"),
    "topic:macro": ("macro", "GDP", "unemployment", "거시", "경기"),
}

# Registry-priority order. Earlier = higher priority (R5 tie-break). The
# index in this tuple is the deterministic registry priority.
_REGISTRY_PRIORITY: Final[tuple[str, ...]] = (
    "person:jerome-powell",
    "person:us-president",
    "asset:bitcoin",
    "asset:ethereum",
    "topic:federal-reserve",
    "topic:wall-street",
    "topic:us-equity-market",
    "topic:cryptocurrency",
    "topic:stock-market-chart",
    "topic:inflation",
    "topic:macro",
    "topic:kospi",
    "topic:korea-market",
)


def select_curated_asset(
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    library: Mapping[str, CuratedAsset],
    registry: Sequence[RegistryEntry],
) -> CuratedSelection:
    """Deterministically select a filed curated asset for a segment (R5 / R6).

    Returns ``CuratedSelection(asset=None, ...)`` when nothing matches,
    every candidate is deferred, or the segment is empty / ambiguous —
    the caller falls through to the existing hero chain (R9).
    """
    by_key = {entry.key: entry for entry in registry}
    candidates: list[tuple[int, str, str]] = []  # (priority, key, reason)
    for priority, key in enumerate(_REGISTRY_PRIORITY):
        entry = by_key.get(key)
        if entry is None:
            continue
        if segment not in entry.segment_affinity:
            continue
        reason = _match_registry_key(key, items)
        if reason is None:
            continue
        candidates.append((priority, key, reason))

    if not candidates:
        return CuratedSelection(asset=None)

    # Deterministic ordering (R5 / I12): registry priority, then key lexical.
    candidates.sort(key=lambda c: (c[0], c[1]))
    for _priority, key, reason in candidates:
        entry = by_key[key]
        for asset_id in entry.asset_ids:  # registry-ordered (I9)
            asset = library.get(asset_id)
            if asset is not None and asset.state == "filed":
                return CuratedSelection(asset=asset, matched_key=key, match_reason=reason)
    return CuratedSelection(asset=None)


def _match_registry_key(key: str, items: Sequence[NormalizedItem]) -> str | None:
    """Return a match reason if any item evidences ``key`` (reuse u64 matcher, R6)."""
    namespace, _, slug = key.partition(":")
    kind: WatchlistTermKind = "asset" if namespace == "asset" else "keyword"
    # The phrase form of the slug ("jerome-powell" -> "jerome powell") plus
    # the curated alias bundle for the key.
    primary_term = slug.replace("-", " ")
    aliases: Mapping[str, tuple[str, ...]] = {primary_term: _KEY_ALIASES.get(key, ())}
    for item in items:
        text_cf = f"{item.title} {item.summary or ''}".casefold()
        text_raw = f"{item.title} {item.summary or ''}"
        hit_term, _hit_alias, _confidence, reason = _match_term_with_aliases(
            term=primary_term,
            kind=kind,
            aliases=aliases,
            item=item,
            text_cf=text_cf,
            text_raw=text_raw,
            exact_only=False,
        )
        if hit_term is not None:
            return reason
        # Also try each alias as a standalone term (the alias bundle in
        # ``aliases`` only fires when keyed by ``primary_term``; a fresh
        # standalone scan catches aliases that are themselves the surface
        # form, e.g. matching "FOMC" without the slug appearing).
        for alias in _KEY_ALIASES.get(key, ()):
            alias_hit, _a, _c, _alias_reason = _match_term_with_aliases(
                term=alias,
                kind=kind,
                aliases={},
                item=item,
                text_cf=text_cf,
                text_raw=text_raw,
                exact_only=False,
            )
            if alias_hit is not None:
                return f"alias:{alias}"
    return None


def default_registry() -> tuple[RegistryEntry, ...]:
    """Return the committed seed registry (E3) — segment-aware key mapping."""
    return _SEED_REGISTRY


def _entry(key: str, asset_ids: Iterable[str], affinity: Iterable[str]) -> RegistryEntry:
    return RegistryEntry(
        key=key,
        asset_ids=tuple(asset_ids),
        segment_affinity=frozenset(affinity),
    )


# Seed registry. ``segment_affinity`` gates candidacy (R6): crypto prefers
# asset:/crypto topics; us-equity prefers US topics/persons; domestic prefers
# KR topics; macro-driven content (Fed / inflation) is shared across the
# equity segments.
_SEED_REGISTRY: Final[tuple[RegistryEntry, ...]] = (
    _entry("person:jerome-powell", ("jerome-powell",), ("us-equity", "domestic-equity")),
    _entry("person:us-president", ("us-president",), ("us-equity",)),
    _entry("topic:federal-reserve", ("federal-reserve",), ("us-equity", "domestic-equity")),
    _entry("topic:wall-street", ("wall-street",), ("us-equity",)),
    _entry("topic:us-equity-market", ("us-equity-market",), ("us-equity",)),
    _entry("topic:stock-market-chart", ("stock-market-chart",), ("us-equity", "domestic-equity")),
    _entry("asset:bitcoin", ("bitcoin",), ("crypto",)),
    _entry("asset:ethereum", ("ethereum",), ("crypto",)),
    _entry("topic:cryptocurrency", ("cryptocurrency",), ("crypto",)),
    _entry("topic:kospi", ("kospi",), ("domestic-equity",)),
    _entry("topic:korea-market", ("korea-market",), ("domestic-equity",)),
    _entry("topic:inflation", ("inflation",), ("us-equity", "domestic-equity")),
    _entry("topic:macro", ("macro",), ("us-equity", "domestic-equity")),
)


__all__ = [
    "LIBRARY_ROOT",
    "CuratedAsset",
    "CuratedAssetState",
    "CuratedLibraryError",
    "CuratedSelection",
    "RegistryEntry",
    "assert_registry_integrity",
    "default_registry",
    "load_library",
    "manifest_path_for",
    "select_curated_asset",
]
