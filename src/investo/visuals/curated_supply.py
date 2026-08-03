"""Offline rights-evidence graph for newly filed curated images (U-146).

The workbench can prepare an exact-file Commons review packet, but it cannot
approve or file an asset.  CI separately verifies an operator-authored
decision and exact-byte links through the committed library and registry.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Literal
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.visuals.policy import ExternalAssetManifest

if TYPE_CHECKING:
    from investo.visuals.curated import CuratedAsset, RegistryEntry

RIGHTS_DIR_NAME: Final[str] = "_rights"
LEGACY_V0_FILENAME: Final[str] = "legacy-v0.json"
SNAPSHOT_FILENAME: Final[str] = "source-snapshot.json"
EVIDENCE_FILENAME: Final[str] = "rights-evidence.json"
DECISION_FILENAME: Final[str] = "operator-decision.json"
PACKET_FILENAME: Final[str] = "review-packet.json"
PACKET_BINARY_STEM: Final[str] = "candidate"

_HEX40_RE: Final[str] = r"^[0-9a-f]{40}$"
_HEX32_RE: Final[str] = r"^[0-9a-f]{32}$"
_HEX64_RE: Final[str] = r"^[0-9a-f]{64}$"
_ASSET_ID_RE: Final[str] = r"^[a-z0-9][a-z0-9-]{0,63}$"
_MIN_WIDTH: Final[int] = 600
_MIN_HEIGHT: Final[int] = 338
_ALLOWED_MIME: Final[frozenset[str]] = frozenset({"image/jpeg", "image/png"})
_CLEAN_LICENSES: Final[Mapping[str, Literal["public-domain", "cc0"]]] = {
    "public domain": "public-domain",
    "cc0": "cc0",
}
_BLOCKER_CODES: Final[frozenset[str]] = frozenset(
    {
        "NO_LICENSE_EVIDENCE",
        "SOURCE_POLICY_METADATA_ONLY",
        "MISSING_REVISION",
        "MISSING_DIMENSIONS",
        "TOO_SMALL",
        "LICENSE_CONTRADICTION",
        "RESTRICTION_SIGNAL",
        "BINARY_MISMATCH",
    }
)
_EMBEDDED_RESTRICTION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:trademark|personality rights|copyright violation|non-free|fair use)",
    flags=re.IGNORECASE,
)
_EMBEDDED_PUBLIC_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:https?:)?//[^\s\"'<>]+",
    flags=re.IGNORECASE,
)

LEGACY_V0_ASSET_IDS: Final[frozenset[str]] = frozenset(
    {
        "bitcoin",
        "cryptocurrency",
        "ethereum",
        "federal-reserve",
        "inflation",
        "jerome-powell",
        "kevin-warsh",
        "korea-market",
        "kospi",
        "macro",
        "scott-bessent",
        "stock-market-chart",
        "us-equity-market",
        "us-president",
        "wall-street",
    }
)
# Updated only when the initial 15-entry exact-byte seal is intentionally
# replaced by an evidence-backed migration, never to grandfather new assets.
LEGACY_V0_SHA256: Final[str] = "c9fd1f4bcd584e9f851003a5130908d066141a779db4297a5945b352fc1d9758"


class CuratedSupplyError(ValueError):
    """Raised when a review packet or committed rights graph is invalid."""


Category = Literal["person", "topic", "asset"]
Assessment = Literal["READY_FOR_REVIEW", "BLOCKED"]
BlockerCode = Literal[
    "NO_LICENSE_EVIDENCE",
    "SOURCE_POLICY_METADATA_ONLY",
    "MISSING_REVISION",
    "MISSING_DIMENSIONS",
    "TOO_SMALL",
    "LICENSE_CONTRADICTION",
    "RESTRICTION_SIGNAL",
    "BINARY_MISMATCH",
]


class CuratedRightsEvidence(BaseModel):
    """Exact-file source and selected binary evidence, never an approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["curated-rights-evidence-v1"] = "curated-rights-evidence-v1"
    asset_id: str = Field(pattern=_ASSET_ID_RE)
    category: Category
    provider: Literal["wikimedia-commons-exact-file"] = "wikimedia-commons-exact-file"
    source_page_url: HttpUrl
    file_title: str = Field(min_length=6, max_length=240)
    page_id: int = Field(gt=0)
    page_revision_id: int | None = Field(default=None, gt=0)
    structured_data_revision_id: int | None = Field(default=None, gt=0)
    structured_license_ids: tuple[str, ...] = ()
    structured_copyright_status_ids: tuple[str, ...] = ()
    image_timestamp: datetime | None
    original_sha1: str | None = Field(default=None, pattern=_HEX40_RE)
    variant_kind: Literal["original", "thumbnail"]
    binary_url: HttpUrl
    binary_relpath: str
    binary_sha256: str = Field(pattern=_HEX64_RE)
    provider_binary_etag_md5: str | None = Field(default=None, pattern=_HEX32_RE)
    binary_mime: Literal["image/jpeg", "image/png"]
    binary_width: int = Field(gt=0)
    binary_height: int = Field(gt=0)
    snapshot_relpath: str
    snapshot_sha256: str = Field(pattern=_HEX64_RE)
    provider_license_name: str = Field(max_length=80)
    manifest_license: Literal["public-domain", "cc0"] | None
    license_url: HttpUrl | None
    author_plaintext: str = Field(max_length=160)
    copyrighted: bool | None
    restrictions: tuple[str, ...] = ()
    embedded_restriction_signals: tuple[str, ...] = ()
    verified_on: date
    assessment: Assessment
    blocker_codes: tuple[BlockerCode, ...] = ()

    @model_validator(mode="after")
    def _validate_state(self) -> CuratedRightsEvidence:
        _validate_relative_path(self.binary_relpath, field="binary_relpath")
        _validate_relative_path(self.snapshot_relpath, field="snapshot_relpath")
        blockers = tuple(dict.fromkeys(self.blocker_codes))
        if blockers != self.blocker_codes or any(code not in _BLOCKER_CODES for code in blockers):
            raise ValueError("blocker_codes must be unique closed-set values")
        if self.assessment == "READY_FOR_REVIEW":
            if blockers:
                raise ValueError("READY_FOR_REVIEW requires no blocker_codes")
            if self.manifest_license is None:
                raise ValueError("READY_FOR_REVIEW requires a clean manifest_license")
            if (
                self.page_revision_id is None
                or self.structured_data_revision_id is None
                or self.image_timestamp is None
            ):
                raise ValueError("READY_FOR_REVIEW requires revision and image timestamp")
            if self.original_sha1 is None or not self.author_plaintext.strip():
                raise ValueError("READY_FOR_REVIEW requires source hash and author")
            if self.restrictions or self.embedded_restriction_signals:
                raise ValueError("READY_FOR_REVIEW requires no restriction signals")
        elif not blockers:
            raise ValueError("BLOCKED requires at least one blocker_code")
        return self


class CuratedOperatorDecision(BaseModel):
    """Approved-only filing decision authored outside the workbench."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["curated-operator-decision-v1"] = "curated-operator-decision-v1"
    asset_id: str = Field(pattern=_ASSET_ID_RE)
    decision: Literal["approved"] = "approved"
    reviewed_on: date
    reviewed_by: str = Field(min_length=1, max_length=80)
    evidence_sha256: str = Field(pattern=_HEX64_RE)
    binary_sha256: str = Field(pattern=_HEX64_RE)
    manifest_sha256: str = Field(pattern=_HEX64_RE)
    binary_relpath: str
    manifest_relpath: str
    registry_key: str = Field(min_length=3, max_length=120)
    file_identity_confirmed: Literal[True]
    license_scope_confirmed: Literal[True]
    subject_relevance_confirmed: Literal[True]
    non_copyright_restrictions_reviewed: Literal[True]
    endorsement_risk_reviewed: Literal[True]
    notes: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _validate_paths(self) -> CuratedOperatorDecision:
        _validate_relative_path(self.binary_relpath, field="binary_relpath")
        _validate_relative_path(self.manifest_relpath, field="manifest_relpath")
        return self


class LegacyCuratedEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(pattern=_ASSET_ID_RE)
    category: Category
    binary_relpath: str
    binary_sha256: str = Field(pattern=_HEX64_RE)
    manifest_relpath: str
    manifest_sha256: str = Field(pattern=_HEX64_RE)

    @model_validator(mode="after")
    def _validate_paths(self) -> LegacyCuratedEntry:
        _validate_relative_path(self.binary_relpath, field="binary_relpath")
        _validate_relative_path(self.manifest_relpath, field="manifest_relpath")
        return self


class LegacyCuratedSeal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["curated-rights-legacy-v0"] = "curated-rights-legacy-v0"
    sealed_on: date
    entries: tuple[LegacyCuratedEntry, ...]

    @model_validator(mode="after")
    def _validate_entries(self) -> LegacyCuratedSeal:
        ids = tuple(entry.asset_id for entry in self.entries)
        if len(ids) != len(set(ids)):
            raise ValueError("legacy-v0 contains duplicate asset ids")
        if frozenset(ids) != LEGACY_V0_ASSET_IDS:
            raise ValueError("legacy-v0 must contain exactly the original 15 asset ids")
        return self


class CuratedReviewPacket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["curated-review-packet-v1"] = "curated-review-packet-v1"
    asset_id: str = Field(pattern=_ASSET_ID_RE)
    status: Literal["READY_FOR_REVIEW"] = "READY_FOR_REVIEW"
    snapshot_filename: Literal["source-snapshot.json"] = "source-snapshot.json"
    snapshot_sha256: str = Field(pattern=_HEX64_RE)
    evidence_filename: Literal["rights-evidence.json"] = "rights-evidence.json"
    evidence_sha256: str = Field(pattern=_HEX64_RE)
    binary_filename: str
    binary_sha256: str = Field(pattern=_HEX64_RE)
    prohibited_outputs: tuple[str, ...] = (
        "operator-decision.json",
        "*.manifest.json",
        "registry",
        "u137-clearance",
    )


@dataclass(frozen=True, slots=True)
class CuratedRightsGraphReport:
    legacy_assets: int
    evidence_backed_assets: int
    deferred_assets: int


def strict_json_load(path: Path) -> object:
    """Load JSON while rejecting duplicate object keys."""

    def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CuratedSupplyError("JSON contains a duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CuratedSupplyError("rights JSON is unreadable") from exc


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Return deterministic producer bytes; verifiers still hash stored bytes."""

    payload = model.model_dump(mode="json")
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def prepare_commons_evidence(
    *,
    asset_id: str,
    category: Category,
    expected_title: str,
    snapshot_path: Path,
    binary_path: Path,
    verified_on: date,
    variant_kind: Literal["original", "thumbnail"] = "thumbnail",
) -> CuratedRightsEvidence:
    """Assess one saved Commons API response and exact local binary."""

    snapshot_payload = strict_json_load(snapshot_path)
    if not isinstance(snapshot_payload, dict):
        raise CuratedSupplyError("Commons snapshot root must be an object")
    _assert_no_secret_json(snapshot_payload)
    imageinfo_payload = snapshot_payload.get("imageinfo_response", snapshot_payload)
    structured_payload = snapshot_payload.get("structured_data_response")
    if not isinstance(imageinfo_payload, dict):
        raise CuratedSupplyError("Commons imageinfo response must be an object")
    try:
        query = imageinfo_payload["query"]
        pages = query["pages"]
        if not isinstance(pages, list) or len(pages) != 1:
            raise CuratedSupplyError("Commons snapshot must contain one exact file page")
        page = pages[0]
        if not isinstance(page, dict):
            raise CuratedSupplyError("Commons page is malformed")
        title = _required_text(page, "title")
        if title != expected_title or not title.startswith("File:"):
            raise CuratedSupplyError("Commons snapshot title does not match the expected file")
        page_id = _required_int(page, "pageid")
        revisions = page.get("revisions")
        revision = revisions[0] if isinstance(revisions, list) and revisions else {}
        revision_id = revision.get("revid") if isinstance(revision, dict) else None
        if not isinstance(revision_id, int) or revision_id <= 0:
            revision_id = None
        imageinfos = page.get("imageinfo")
        if not isinstance(imageinfos, list) or len(imageinfos) != 1:
            raise CuratedSupplyError("Commons snapshot must contain one imageinfo record")
        info = imageinfos[0]
        if not isinstance(info, dict):
            raise CuratedSupplyError("Commons imageinfo is malformed")
    except (KeyError, TypeError) as exc:
        raise CuratedSupplyError("Commons snapshot shape is incomplete") from exc

    extmetadata = info.get("extmetadata")
    if not isinstance(extmetadata, dict):
        extmetadata = {}
    license_name = _metadata_text(extmetadata, "LicenseShortName")
    manifest_license = _CLEAN_LICENSES.get(license_name.casefold())
    license_url_text = _metadata_text(extmetadata, "LicenseUrl")
    author = _plain_text(_metadata_text(extmetadata, "Artist"))
    restrictions_text = _plain_text(_metadata_text(extmetadata, "Restrictions"))
    restrictions = (restrictions_text,) if restrictions_text else ()
    categories = _metadata_text(extmetadata, "Categories")
    embedded = tuple(
        sorted(
            {match.group(0).casefold() for match in _EMBEDDED_RESTRICTION_RE.finditer(categories)}
        )
    )
    copyrighted_text = _metadata_text(extmetadata, "Copyrighted").casefold()
    copyrighted = (
        True if copyrighted_text == "true" else False if copyrighted_text == "false" else None
    )

    structured_revision_id: int | None = None
    structured_license_ids: tuple[str, ...] = ()
    structured_status_ids: tuple[str, ...] = ()
    if isinstance(structured_payload, dict):
        entities = structured_payload.get("entities")
        entity = entities.get(f"M{page_id}") if isinstance(entities, dict) else None
        if isinstance(entity, dict):
            candidate_revision = entity.get("lastrevid")
            if isinstance(candidate_revision, int) and candidate_revision > 0:
                structured_revision_id = candidate_revision
            statements = entity.get("statements")
            if isinstance(statements, dict):
                structured_license_ids = _statement_qids(statements.get("P275"))
                structured_status_ids = _statement_qids(statements.get("P6216"))

    url_key = "url" if variant_kind == "original" else "thumburl"
    width_key = "width" if variant_kind == "original" else "thumbwidth"
    height_key = "height" if variant_kind == "original" else "thumbheight"
    binary_url = _required_text(info, url_key)
    if urlsplit(binary_url).hostname != "upload.wikimedia.org":
        raise CuratedSupplyError("Commons binary URL host is invalid")
    snapshot_width = info.get(width_key)
    snapshot_height = info.get(height_key)
    mime = _required_text(info, "mime")
    original_sha1 = info.get("sha1")
    if not isinstance(original_sha1, str) or re.fullmatch(_HEX40_RE, original_sha1) is None:
        original_sha1 = None
    timestamp = _parse_datetime(info.get("timestamp"))

    try:
        content = binary_path.read_bytes()
    except OSError as exc:
        raise CuratedSupplyError("candidate binary is unreadable") from exc
    from investo.visuals.assets import read_image_dimensions, validate_visual_binary

    try:
        validate_visual_binary(binary_path)
    except Exception as exc:
        raise CuratedSupplyError("candidate binary failed the curated binary gate") from exc
    actual_dimensions = read_image_dimensions(content, binary_path.suffix.lower())
    binary_sha256 = hashlib.sha256(content).hexdigest()
    binary_sha1 = hashlib.sha1(content, usedforsecurity=False).hexdigest()
    binary_md5 = hashlib.md5(content, usedforsecurity=False).hexdigest()
    actual_mime = _mime_for_suffix(binary_path.suffix.lower())

    provider_binary_etag_md5: str | None = None
    capture = snapshot_payload.get("capture")
    binary_response = capture.get("binary_response") if isinstance(capture, dict) else None
    if isinstance(binary_response, dict):
        candidate_etag = binary_response.get("etag_md5")
        if isinstance(candidate_etag, str) and re.fullmatch(_HEX32_RE, candidate_etag):
            provider_binary_etag_md5 = candidate_etag

    blockers: list[BlockerCode] = []
    if manifest_license is None:
        blockers.append("NO_LICENSE_EVIDENCE")
    if revision_id is None or timestamp is None or original_sha1 is None:
        blockers.append("MISSING_REVISION")
    if (
        not isinstance(snapshot_width, int)
        or not isinstance(snapshot_height, int)
        or actual_dimensions is None
    ):
        blockers.append("MISSING_DIMENSIONS")
        width, height = actual_dimensions or (1, 1)
    else:
        width, height = actual_dimensions
        if (width, height) != (snapshot_width, snapshot_height):
            blockers.append("BINARY_MISMATCH")
    if width < _MIN_WIDTH or height < _MIN_HEIGHT:
        blockers.append("TOO_SMALL")
    if mime not in _ALLOWED_MIME or actual_mime != mime:
        blockers.append("BINARY_MISMATCH")
    if variant_kind == "original":
        if original_sha1 is None or binary_sha1 != original_sha1:
            blockers.append("BINARY_MISMATCH")
    elif binary_response is None:
        blockers.append("SOURCE_POLICY_METADATA_ONLY")
    else:
        response_url = binary_response.get("url")
        response_length = binary_response.get("content_length")
        if (
            response_url != binary_url
            or response_length != len(content)
            or provider_binary_etag_md5 is None
            or provider_binary_etag_md5 != binary_md5
        ):
            blockers.append("BINARY_MISMATCH")
    if manifest_license == "public-domain" and copyrighted is True:
        blockers.append("LICENSE_CONTRADICTION")
    if structured_revision_id is None:
        blockers.append("SOURCE_POLICY_METADATA_ONLY")
    elif revision_id is not None and structured_revision_id != revision_id:
        blockers.append("LICENSE_CONTRADICTION")
    if manifest_license == "cc0":
        if not structured_license_ids or not structured_status_ids:
            blockers.append("SOURCE_POLICY_METADATA_ONLY")
        elif set(structured_license_ids) != {"Q6938433"} or set(structured_status_ids) != {
            "Q88088423"
        }:
            blockers.append("LICENSE_CONTRADICTION")
    elif manifest_license == "public-domain":
        allowed_status = {"Q19652", "Q88088423"}
        if not structured_status_ids:
            blockers.append("SOURCE_POLICY_METADATA_ONLY")
        elif not set(structured_status_ids).issubset(allowed_status):
            blockers.append("LICENSE_CONTRADICTION")
        if structured_license_ids and set(structured_license_ids) != {"Q6938433"}:
            blockers.append("LICENSE_CONTRADICTION")
    if restrictions or embedded:
        blockers.append("RESTRICTION_SIGNAL")
    if not author:
        blockers.append("NO_LICENSE_EVIDENCE")
    blockers = list(dict.fromkeys(blockers))

    source_page_url = "https://commons.wikimedia.org/wiki/" + quote(
        title.replace(" ", "_"), safe=":()_-"
    )
    evidence = CuratedRightsEvidence(
        asset_id=asset_id,
        category=category,
        source_page_url=source_page_url,
        file_title=title,
        page_id=page_id,
        page_revision_id=revision_id,
        structured_data_revision_id=structured_revision_id,
        structured_license_ids=structured_license_ids,
        structured_copyright_status_ids=structured_status_ids,
        image_timestamp=timestamp,
        original_sha1=original_sha1,
        variant_kind=variant_kind,
        binary_url=binary_url,
        binary_relpath=f"{category}/{asset_id}{binary_path.suffix.lower()}",
        binary_sha256=binary_sha256,
        provider_binary_etag_md5=provider_binary_etag_md5,
        binary_mime=actual_mime,
        binary_width=width,
        binary_height=height,
        snapshot_relpath=f"{RIGHTS_DIR_NAME}/{asset_id}/{SNAPSHOT_FILENAME}",
        snapshot_sha256=_sha256_path(snapshot_path),
        provider_license_name=license_name,
        manifest_license=manifest_license,
        license_url=license_url_text or None,
        author_plaintext=author,
        copyrighted=copyrighted,
        restrictions=restrictions,
        embedded_restriction_signals=embedded,
        verified_on=verified_on,
        assessment="BLOCKED" if blockers else "READY_FOR_REVIEW",
        blocker_codes=tuple(blockers),
    )
    _assert_no_secret_values(
        source_page_url,
        binary_url,
        license_name,
        license_url_text,
        author,
        *restrictions,
        *embedded,
    )
    return evidence


def write_pending_review_packet(
    *,
    evidence: CuratedRightsEvidence,
    snapshot_path: Path,
    binary_path: Path,
    output_dir: Path,
    repo_root: Path,
) -> Path:
    """Atomically write a non-approving review packet outside the repository."""

    if evidence.assessment != "READY_FOR_REVIEW":
        raise CuratedSupplyError("blocked evidence cannot produce a ready review packet")
    _assert_output_outside_repo(output_dir, repo_root=repo_root)
    if output_dir.exists():
        raise CuratedSupplyError("review output already exists")
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=parent))
    binary_name = f"{PACKET_BINARY_STEM}{binary_path.suffix.lower()}"
    try:
        snapshot_bytes = snapshot_path.read_bytes()
        binary_bytes = binary_path.read_bytes()
        if hashlib.sha256(snapshot_bytes).hexdigest() != evidence.snapshot_sha256:
            raise CuratedSupplyError("snapshot changed after evidence preparation")
        if hashlib.sha256(binary_bytes).hexdigest() != evidence.binary_sha256:
            raise CuratedSupplyError("binary changed after evidence preparation")
        evidence_bytes = canonical_json_bytes(evidence)
        (temp / SNAPSHOT_FILENAME).write_bytes(snapshot_bytes)
        (temp / binary_name).write_bytes(binary_bytes)
        (temp / EVIDENCE_FILENAME).write_bytes(evidence_bytes)
        packet = CuratedReviewPacket(
            asset_id=evidence.asset_id,
            snapshot_sha256=hashlib.sha256(snapshot_bytes).hexdigest(),
            evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
            binary_filename=binary_name,
            binary_sha256=hashlib.sha256(binary_bytes).hexdigest(),
        )
        (temp / PACKET_FILENAME).write_bytes(canonical_json_bytes(packet))
        os.replace(temp, output_dir)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return output_dir


def validate_curated_rights_graph(
    *,
    library_root: Path,
    library: Mapping[str, CuratedAsset],
    registry: Sequence[RegistryEntry],
) -> CuratedRightsGraphReport:
    """Verify legacy and evidence-backed filing graphs against exact files."""

    rights_root = library_root / RIGHTS_DIR_NAME
    legacy_path = rights_root / LEGACY_V0_FILENAME
    if _sha256_path(legacy_path) != LEGACY_V0_SHA256:
        raise CuratedSupplyError("legacy-v0 seal digest mismatch")
    legacy = LegacyCuratedSeal.model_validate(strict_json_load(legacy_path))
    legacy_by_id = {entry.asset_id: entry for entry in legacy.entries}

    registry_by_asset: dict[str, str] = {}
    for entry in registry:
        for asset_id in entry.asset_ids:
            if asset_id in registry_by_asset:
                raise CuratedSupplyError("asset is owned by more than one registry key")
            registry_by_asset[asset_id] = entry.key

    legacy_count = 0
    evidence_count = 0
    deferred_count = 0
    expected_rights_dirs: set[str] = set()
    for asset_id, asset in sorted(library.items()):
        if asset.state == "deferred":
            deferred_count += 1
            continue
        if asset.path is None:
            raise CuratedSupplyError("filed curated asset has no binary path")
        if asset_id in legacy_by_id:
            _validate_legacy_entry(
                entry=legacy_by_id[asset_id],
                asset=asset,
                library_root=library_root,
            )
            legacy_count += 1
            continue
        expected_rights_dirs.add(asset_id)
        _validate_new_filing(
            asset_id=asset_id,
            asset=asset,
            library_root=library_root,
            registry_key=registry_by_asset.get(asset_id),
        )
        evidence_count += 1

    root_paths = tuple(rights_root.iterdir())
    if any(path.is_symlink() for path in root_paths):
        raise CuratedSupplyError("rights root contains a symbolic link")
    actual_rights_dirs = {
        path.name for path in root_paths if path.is_dir() and not path.name.startswith(".")
    }
    if actual_rights_dirs != expected_rights_dirs:
        raise CuratedSupplyError("rights artifacts do not match evidence-backed filed assets")
    root_entries = {path.name for path in root_paths}
    if root_entries != expected_rights_dirs | {LEGACY_V0_FILENAME}:
        raise CuratedSupplyError("rights root contains an unexpected artifact")
    for asset_id in expected_rights_dirs:
        rights_dir = rights_root / asset_id
        entries = tuple(rights_dir.iterdir())
        if any(path.is_symlink() for path in entries):
            raise CuratedSupplyError("rights directory contains a symbolic link")
        children = {path.name for path in entries if path.is_file()}
        directories = tuple(path for path in entries if path.is_dir())
        if children != {SNAPSHOT_FILENAME, EVIDENCE_FILENAME, DECISION_FILENAME} or directories:
            raise CuratedSupplyError("rights directory shape is not closed")
    current_legacy_ids = frozenset(library) & LEGACY_V0_ASSET_IDS
    if current_legacy_ids != LEGACY_V0_ASSET_IDS or legacy_count != len(LEGACY_V0_ASSET_IDS):
        raise CuratedSupplyError("legacy-v0 assets are not all present")
    return CuratedRightsGraphReport(
        legacy_assets=legacy_count,
        evidence_backed_assets=evidence_count,
        deferred_assets=deferred_count,
    )


def _validate_legacy_entry(
    *, entry: LegacyCuratedEntry, asset: CuratedAsset, library_root: Path
) -> None:
    if asset.path is None or entry.category != asset.category:
        raise CuratedSupplyError("legacy asset category/path mismatch")
    binary = _confined_path(library_root, entry.binary_relpath)
    manifest = _confined_path(library_root, entry.manifest_relpath)
    expected_manifest = asset.path.with_name(f"{asset.asset_id}.manifest.json")
    if binary != asset.path.resolve() or manifest != expected_manifest.resolve():
        raise CuratedSupplyError("legacy asset moved from its sealed path")
    if _sha256_path(binary) != entry.binary_sha256:
        raise CuratedSupplyError("legacy binary digest mismatch")
    if _sha256_path(manifest) != entry.manifest_sha256:
        raise CuratedSupplyError("legacy manifest digest mismatch")


def _validate_new_filing(
    *,
    asset_id: str,
    asset: CuratedAsset,
    library_root: Path,
    registry_key: str | None,
) -> None:
    if asset.path is None:
        raise CuratedSupplyError("evidence-backed filing has no binary")
    rights_dir = library_root / RIGHTS_DIR_NAME / asset_id
    snapshot = rights_dir / SNAPSHOT_FILENAME
    evidence_path = rights_dir / EVIDENCE_FILENAME
    decision_path = rights_dir / DECISION_FILENAME
    snapshot_payload = strict_json_load(snapshot)
    evidence_payload = strict_json_load(evidence_path)
    decision_payload = strict_json_load(decision_path)
    _assert_no_secret_json(snapshot_payload)
    _assert_no_secret_json(evidence_payload)
    _assert_no_secret_json(decision_payload)
    evidence = CuratedRightsEvidence.model_validate(evidence_payload)
    decision = CuratedOperatorDecision.model_validate(decision_payload)
    if evidence.asset_id != asset_id or decision.asset_id != asset_id:
        raise CuratedSupplyError("rights graph asset id mismatch")
    if evidence.assessment != "READY_FOR_REVIEW" or evidence.blocker_codes:
        raise CuratedSupplyError("filed asset evidence is not review-ready")
    if decision.registry_key != registry_key or registry_key is None:
        raise CuratedSupplyError("approved filing is not registry-reachable")
    if _confined_path(library_root, evidence.snapshot_relpath) != snapshot.resolve():
        raise CuratedSupplyError("evidence snapshot path mismatch")
    binary = _confined_path(library_root, evidence.binary_relpath)
    manifest_path = asset.path.with_name(f"{asset.asset_id}.manifest.json")
    if binary != asset.path.resolve():
        raise CuratedSupplyError("evidence binary path mismatch")
    if decision.binary_relpath != evidence.binary_relpath:
        raise CuratedSupplyError("decision binary path mismatch")
    if _confined_path(library_root, decision.manifest_relpath) != manifest_path.resolve():
        raise CuratedSupplyError("decision manifest path mismatch")
    if _sha256_path(snapshot) != evidence.snapshot_sha256:
        raise CuratedSupplyError("snapshot digest mismatch")
    if _sha256_path(binary) != evidence.binary_sha256:
        raise CuratedSupplyError("binary digest does not match evidence")
    if _sha256_path(evidence_path) != decision.evidence_sha256:
        raise CuratedSupplyError("evidence digest does not match decision")
    if _sha256_path(binary) != decision.binary_sha256:
        raise CuratedSupplyError("binary digest does not match decision")
    if _sha256_path(manifest_path) != decision.manifest_sha256:
        raise CuratedSupplyError("manifest digest does not match decision")
    if asset.category != evidence.category:
        raise CuratedSupplyError("evidence category mismatch")
    manifest: ExternalAssetManifest = asset.manifest
    if _normalized_url(str(manifest.source_url)) != _normalized_url(str(evidence.source_page_url)):
        raise CuratedSupplyError("manifest source does not match evidence")
    if manifest.license != evidence.manifest_license:
        raise CuratedSupplyError("manifest license does not match evidence")
    if manifest.author != evidence.author_plaintext:
        raise CuratedSupplyError("manifest author does not match evidence")
    if manifest.fetched_on != decision.reviewed_on or evidence.verified_on != decision.reviewed_on:
        raise CuratedSupplyError("review/fetch dates do not match")
    reproduced = prepare_commons_evidence(
        asset_id=asset_id,
        category=asset.category,
        expected_title=evidence.file_title,
        snapshot_path=snapshot,
        binary_path=binary,
        verified_on=evidence.verified_on,
        variant_kind=evidence.variant_kind,
    )
    if reproduced != evidence:
        raise CuratedSupplyError("stored evidence does not reproduce from snapshot and binary")
    _assert_no_secret_values(
        decision.reviewed_by,
        decision.registry_key,
        decision.notes,
        evidence.author_plaintext,
        str(evidence.source_page_url),
        str(evidence.binary_url),
    )


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CuratedSupplyError("required Commons text field is missing")
    return value.strip()


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value <= 0:
        raise CuratedSupplyError("required Commons integer field is missing")
    return value


def _metadata_text(metadata: Mapping[str, object], key: str) -> str:
    field = metadata.get(key)
    if not isinstance(field, dict):
        return ""
    value = field.get("value")
    return str(value).strip() if value is not None else ""


def _plain_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split())


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _statement_qids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    qids: set[str] = set()
    for statement in value:
        if not isinstance(statement, dict):
            continue
        if statement.get("rank") not in {"normal", "preferred"}:
            continue
        mainsnak = statement.get("mainsnak")
        if not isinstance(mainsnak, dict) or mainsnak.get("snaktype") != "value":
            continue
        datavalue = mainsnak.get("datavalue")
        item = datavalue.get("value") if isinstance(datavalue, dict) else None
        qid = item.get("id") if isinstance(item, dict) else None
        if isinstance(qid, str) and re.fullmatch(r"Q[1-9][0-9]*", qid):
            qids.add(qid)
    return tuple(sorted(qids))


def _mime_for_suffix(suffix: str) -> Literal["image/jpeg", "image/png"]:
    if suffix == ".jpg":
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    raise CuratedSupplyError("candidate binary extension is unsupported")


def _sha256_path(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CuratedSupplyError("required rights file is unreadable") from exc


def _validate_relative_path(value: str, *, field: str) -> None:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"{field} must be a normalized relative POSIX path")


def _confined_path(root: Path, relpath: str) -> Path:
    _validate_relative_path(relpath, field="rights path")
    root_resolved = root.resolve()
    path = (root_resolved / relpath).resolve()
    if path != root_resolved and root_resolved not in path.parents:
        raise CuratedSupplyError("rights path escapes the curated library")
    return path


def _assert_output_outside_repo(output_dir: Path, *, repo_root: Path) -> None:
    output = output_dir.resolve()
    repo = repo_root.resolve()
    if output == repo or repo in output.parents or output in repo.parents:
        raise CuratedSupplyError("review output must be outside the repository")


def _assert_no_secret_values(*values: str) -> None:
    for value in values:
        if redact_text(value, policy=RedactionPolicy.STRICT) != value:
            raise CuratedSupplyError("rights metadata contains a secret-shaped value")


def _assert_no_secret_json(value: object, *, field: str | None = None) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_secret_json(key)
            _assert_no_secret_json(item, field=key)
        return
    if isinstance(value, list):
        for item in value:
            _assert_no_secret_json(item, field=field)
        return
    digest_patterns = {
        "binary_sha256": _HEX64_RE,
        "etag_md5": _HEX32_RE,
        "evidence_sha256": _HEX64_RE,
        "manifest_sha256": _HEX64_RE,
        "original_sha1": _HEX40_RE,
        "provider_binary_etag_md5": _HEX32_RE,
        "sha1": _HEX40_RE,
        "snapshot_sha256": _HEX64_RE,
    }
    if not isinstance(value, str) or (
        field in digest_patterns and re.fullmatch(digest_patterns[field], value)
    ):
        return
    if _is_allowlisted_public_url(value):
        _assert_public_url_secret_free(value)
        return
    scan_value = value
    for match in _EMBEDDED_PUBLIC_URL_RE.finditer(value):
        raw_url = html.unescape(match.group(0))
        absolute_url = f"https:{raw_url}" if raw_url.startswith("//") else raw_url
        if _is_allowlisted_public_url(absolute_url):
            _assert_public_url_secret_free(absolute_url)
            scan_value = scan_value.replace(match.group(0), "")
    _assert_no_secret_values(scan_value)


def _is_allowlisted_public_url(value: str) -> bool:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    if parsed.hostname not in {"commons.wikimedia.org", "upload.wikimedia.org"}:
        return False
    allowed_query_keys = {
        "action",
        "format",
        "formatversion",
        "ids",
        "iiprop",
        "iiurlwidth",
        "prop",
        "redlink",
        "rvlimit",
        "rvprop",
        "titles",
        "title",
    }
    return all(key in allowed_query_keys for key, _item in parse_qsl(parsed.query))


def _assert_public_url_secret_free(value: str) -> None:
    parsed = urlsplit(value)
    _assert_secret_free_after_bounded_url_decode(parsed.path)
    _assert_secret_free_after_bounded_url_decode(parsed.fragment)
    for _key, item in parse_qsl(parsed.query, keep_blank_values=True):
        _assert_secret_free_after_bounded_url_decode(item)


def _assert_secret_free_after_bounded_url_decode(value: str) -> None:
    current = value
    for _decode_depth in range(4):
        _assert_no_secret_values(current)
        decoded = unquote(current)
        if decoded == current:
            return
        current = decoded
    raise CuratedSupplyError("public URL encoding depth exceeds the safety limit")


def _normalized_url(value: str) -> str:
    return value.rstrip("/")


__all__ = [
    "DECISION_FILENAME",
    "EVIDENCE_FILENAME",
    "LEGACY_V0_ASSET_IDS",
    "LEGACY_V0_FILENAME",
    "LEGACY_V0_SHA256",
    "PACKET_FILENAME",
    "RIGHTS_DIR_NAME",
    "SNAPSHOT_FILENAME",
    "CuratedOperatorDecision",
    "CuratedReviewPacket",
    "CuratedRightsEvidence",
    "CuratedRightsGraphReport",
    "CuratedSupplyError",
    "LegacyCuratedEntry",
    "LegacyCuratedSeal",
    "canonical_json_bytes",
    "prepare_commons_evidence",
    "strict_json_load",
    "validate_curated_rights_graph",
    "write_pending_review_packet",
]
