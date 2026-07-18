"""Image-candidate ledger + recurrence index for harvested feed images (u137).

Step 1 persists the u136 ``image_*`` raw_metadata harvest as a
date-keyed JSONL ledger (FD Contract #1, E1, R2/R3/R4). Step 2 adds the
recurrence index (Contract #2, E2, R5, I5-I7) and the read-side of the
rights state machine (Contract #3, E5, R6/R7, I8/I9/I14): the index
mirrors clearance-directory file existence into ``rights_state`` but
never writes under ``clearances/`` — state transitions are
operator-file-only. Step 3 adds the quadruple-gated fetch +
content-addressed binary store (Contract #4, E4, R8, I10-I13), reusing
the u19 fetch machinery and the u24 provenance sidecar system (TS-1 /
TS-2 — no private re-implementation, no parallel schema).

Legal posture (R1): **metadata-everything, binaries-only-with-
clearance** (I17). Every candidate's default rights state is
``metadata-only``; a default run (no clearance files, no env opt-in)
stores exactly zero binaries (AC-137.2).

Module boundary (R10): called by the orchestrator only. Imports are
limited to ``investo.models`` (shared), ``investo._internal`` (shared
primitives), and sibling ``investo.visuals`` modules — never
``sources`` / ``briefing`` / ``publisher`` / ``notifier``.

Design choices (2026-07-18, Step 1):

* **I1 self-verifying records** — ``ImageCandidateRecord`` recomputes
  ``sha256(normalize(image_url))`` in a model validator, so a ledger row
  whose ``candidate_id`` does not match its URL cannot exist (neither
  freshly built nor parsed back during merge-rewrite). ``normalize`` is
  exactly R2: lowercase scheme + lowercase host, fragment stripped,
  path / query / port byte-exact.
* **Sanitization split (ratified divergence from the I2/R4 "every
  string field" wording)** — ``item_title`` / ``image_credit`` /
  ``image_mime`` / ``source_name`` / ``segment`` pass
  :func:`sanitize_provenance_text` (u27 STRICT chokepoint) via field
  validators. ``candidate_id`` and the two URL fields do NOT: the
  STRICT policy redacts 64-char hex strings, ``?k=v`` query strings and
  long URL path runs (verified 2026-07-18 against the real recorded
  Yonhap image URL), so rewriting them would break the I1/I9 hash
  identity the whole registry addresses by. R13 is held for those
  fields by *fail-closed screening* instead: a candidate whose image or
  item URL carries any current :data:`SECRET_ENV_VARS` value or a
  :func:`scan_for_leak` hit is dropped entirely (counted in the
  report), never partially redacted. ``candidate_id`` is additionally
  locked to ``^[0-9a-f]{64}$`` and is only ever produced locally by
  :func:`candidate_id_for_url`.
* **R3 merge-rewrite** — read existing date file (if any), merge by
  ``candidate_id`` with existing-row-wins, sort candidate_id-lexical,
  serialize with fixed key order (pydantic model field order via
  ``model_dump_json``), atomically rewrite via the shared
  :func:`investo._internal._io.write_atomic`. Re-running the same
  inputs yields a byte-identical file (I4). An empty merge writes
  nothing — imageless runs leave no ledger file.
* **Unparseable existing rows** are dropped with one WARNING each and
  surfaced in the report (``invalid_existing_dropped``) rather than
  raising: a wedged date file would otherwise permanently disable
  candidate accumulation for that date, and preserving a row we cannot
  re-serialize deterministically would break I4. R3's "never drops
  earlier rows" holds for every valid row.
* **No wall clock** (I3/R3) — ``collected_on`` comes only from the
  ``target_date`` parameter; this module never reads ``datetime.now``.

Step 2 design choices (2026-07-18):

* **Derived-only full rebuild (I6)** — :func:`update_index` rescans
  every date ledger under the root plus the clearances directory and
  rewrites ``index.json`` from scratch; the index carries no state that
  is not derivable from those inputs, so placement/removal of operator
  files is reflected on the next run with no migration logic.
* **``seen_count`` = distinct ledger dates (R5)** — the v1 "자주 쓰이는
  이미지" signal counts the number of date files carrying the
  candidate, not per-run row totals. The ledger date is the file's
  ``YYYY-MM-DD`` stem (Step 1 stamps ``collected_on`` equal to it).
* **Rights mirror, fail-closed (I7/I8/I9)** — ``blocked`` marker wins
  over a coexisting manifest; a clearance manifest counts as valid only
  when it parses as a u19 :class:`ExternalAssetManifest` with
  ``kind="explicit-license"`` (E3 — no parallel schema) AND its
  ``source_url`` hashes to the ``{candidate_id}`` filename stem (I9 —
  a clearance for URL A can never authorize URL B). Anything else
  degrades to ``metadata-only`` with one WARN and an
  ``invalid_clearances`` count; the CI gate (Step 5) is the RED
  enforcement. I9 hashing uses ``str(manifest.source_url)`` — pydantic's
  ``HttpUrl`` round-trip lowercases the host, which the R2
  normalization does anyway.
* **I14** — this module only ever *reads* ``clearances/``; no code path
  creates, modifies, or deletes files there.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from investo._internal._io import write_atomic, write_atomic_bytes
from investo._internal.redaction import SECRET_ENV_VARS, scan_for_leak
from investo.models import NormalizedItem
from investo.models.segments import MarketSegment
from investo.visuals.assets import read_image_dimensions
from investo.visuals.external_image import fetch_manifest_image
from investo.visuals.policy import (
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    allowed_external_image_hosts,
    assert_external_asset_allowed,
    assert_external_image_host_allowed,
    external_image_scraping_enabled,
)
from investo.visuals.provenance import (
    build_external_provenance,
    sanitize_provenance_text,
    write_manifest,
)

_logger = logging.getLogger(__name__)

# Contract #1 ledger root: archive/_meta/image_candidates/{YYYY}/{date}.jsonl.
# Injected as a parameter everywhere so tests write under tmp_path and the
# orchestrator (Step 4) can bind its patched archive root.
DEFAULT_LEDGER_ROOT: Final[Path] = Path("archive") / "_meta" / "image_candidates"

_ITEM_TITLE_MAX: Final[int] = 160  # I2 — post-sanitization cap
_IMAGE_CREDIT_MAX: Final[int] = 240  # u136 cap, re-applied post-sanitization
_IMAGE_URL_MAX: Final[int] = 1000  # u136 harvest cap, carried verbatim

_ALLOWED_URL_SCHEMES: Final[tuple[str, ...]] = ("http", "https")


def normalize_image_url(url: str) -> str:
    """Normalize ``url`` for candidate identity, exactly per R2 / I1.

    Lowercase scheme, lowercase host, strip the fragment; path / query /
    port (and any userinfo) are preserved byte-exact. No query
    reordering, no trailing-slash trimming, no tracking-param stripping
    — v1 identity is URL-hash equality only.
    """

    parts = urlsplit(url)
    netloc = parts.netloc
    if "@" in netloc:
        # Preserve userinfo byte-exact; lowercase only the host[:port]
        # part (digits in a port are unaffected by ``lower()``).
        userinfo, _, hostport = netloc.rpartition("@")
        netloc = f"{userinfo}@{hostport.lower()}"
    else:
        netloc = netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, ""))


def candidate_id_for_url(image_url: str) -> str:
    """Return the sha256-hex candidate id for ``image_url`` (I1 / R2)."""

    return hashlib.sha256(normalize_image_url(image_url).encode("utf-8")).hexdigest()


class ImageCandidateRecord(BaseModel):
    """One harvested image reference — one ledger JSONL line (E1).

    Field order is the serialization key order (I4); do not reorder.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_url: str = Field(min_length=1, max_length=_IMAGE_URL_MAX)
    source_name: str = Field(min_length=1, max_length=100)
    segment: str = Field(min_length=1, max_length=40)
    item_url: str = Field(min_length=1)
    item_title: str = Field(min_length=1, max_length=_ITEM_TITLE_MAX)
    image_width: int | None = None
    image_height: int | None = None
    image_mime: str | None = Field(default=None, max_length=100)
    image_credit: str | None = Field(default=None, max_length=_IMAGE_CREDIT_MAX)
    collected_on: date

    @field_validator("source_name", "segment", "item_title")
    @classmethod
    def _sanitize_required_text(cls, value: str) -> str:
        # I2 / R4 — u27 STRICT chokepoint. Applied before the length
        # constraints (pydantic runs field validators after constraint
        # checks on input, so the builder pre-caps; this validator is
        # the belt-and-braces chokepoint for any construction path).
        return sanitize_provenance_text(value)

    @field_validator("image_mime", "image_credit")
    @classmethod
    def _sanitize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return sanitize_provenance_text(value)

    @field_validator("image_url", "item_url")
    @classmethod
    def _require_public_http_url(cls, value: str) -> str:
        # NOT rewritten by the sanitizer (see module docstring); shape-
        # guarded instead. Secret screening happens fail-closed in the
        # builder (_url_is_secret_free) before a record is constructed.
        if urlsplit(value).scheme not in _ALLOWED_URL_SCHEMES:
            raise ValueError("URL must be http(s)")
        return value

    @model_validator(mode="after")
    def _verify_candidate_identity(self) -> ImageCandidateRecord:
        # I1 — a row whose id does not hash-match its URL cannot exist.
        expected = candidate_id_for_url(self.image_url)
        if self.candidate_id != expected:
            raise ValueError(
                f"candidate_id {self.candidate_id!r} does not match "
                f"sha256(normalize(image_url)) {expected!r}"
            )
        return self


@dataclass(frozen=True, slots=True)
class LedgerWriteReport:
    """Outcome counts for one :func:`append_candidates` run.

    ``candidates_written`` counts rows newly added by this run;
    ``existing_preserved`` counts pre-existing rows carried through the
    merge-rewrite (existing-row-wins). A byte-idempotent re-run over
    identical inputs therefore reports ``candidates_written == 0``.
    ``screened_skipped`` counts fail-closed drops: missing item URL,
    secret-bearing URL (R13 screening), or record validation failure.
    """

    ledger_path: Path
    items_seen: int
    imageless_skipped: int
    duplicates_skipped: int
    screened_skipped: int
    candidates_written: int
    existing_preserved: int
    invalid_existing_dropped: int


def ledger_path_for(target_date: date, *, ledger_root: Path = DEFAULT_LEDGER_ROOT) -> Path:
    """Return the date ledger path (Contract #1 / R3 layout)."""

    return ledger_root / f"{target_date.year:04d}" / f"{target_date.isoformat()}.jsonl"


def append_candidates(
    target_date: date,
    routed_items: Mapping[MarketSegment, Sequence[NormalizedItem]],
    *,
    ledger_root: Path = DEFAULT_LEDGER_ROOT,
) -> LedgerWriteReport:
    """Merge this run's image candidates into the date ledger (R3, I4).

    ``routed_items`` is the pipeline's post-routing mapping (segment →
    items); mapping insertion order defines the deterministic same-run
    dedup order (first item carrying a ``candidate_id`` wins). Items
    without the u136 ``image_url`` raw_metadata key are skipped — the
    ledger never invents candidates.

    Write mode is merge-rewrite with existing-row-wins, candidate_id-
    sorted rows, fixed key order, atomic replace. Re-runs over the same
    inputs are byte-idempotent; nothing is written when the merge is
    empty.
    """

    items_seen = 0
    imageless_skipped = 0
    duplicates_skipped = 0
    screened_skipped = 0
    run_rows: dict[str, ImageCandidateRecord] = {}

    for segment, items in routed_items.items():
        for item in items:
            items_seen += 1
            raw_image_url = item.raw_metadata.get("image_url")
            if not isinstance(raw_image_url, str) or not raw_image_url:
                imageless_skipped += 1
                continue
            record = _record_from_item(
                item,
                segment=segment,
                image_url=raw_image_url,
                target_date=target_date,
            )
            if record is None:
                screened_skipped += 1
                continue
            if record.candidate_id in run_rows:
                duplicates_skipped += 1
                continue
            run_rows[record.candidate_id] = record

    path = ledger_path_for(target_date, ledger_root=ledger_root)
    existing_rows, invalid_existing_dropped = _read_existing_rows(path)

    # Merge-rewrite, existing-row-wins (R3): a later run may add new
    # candidates but never mutates or drops earlier valid rows.
    merged: dict[str, ImageCandidateRecord] = dict(run_rows)
    merged.update(existing_rows)
    candidates_written = len(merged) - len(existing_rows)

    if merged:
        lines = [merged[cid].model_dump_json() for cid in sorted(merged)]
        write_atomic(path, "\n".join(lines) + "\n")

    return LedgerWriteReport(
        ledger_path=path,
        items_seen=items_seen,
        imageless_skipped=imageless_skipped,
        duplicates_skipped=duplicates_skipped,
        screened_skipped=screened_skipped,
        candidates_written=candidates_written,
        existing_preserved=len(existing_rows),
        invalid_existing_dropped=invalid_existing_dropped,
    )


def _record_from_item(
    item: NormalizedItem,
    *,
    segment: MarketSegment,
    image_url: str,
    target_date: date,
) -> ImageCandidateRecord | None:
    """Build one E1 record, or ``None`` on a fail-closed screen/validity drop."""

    if item.url is None:
        # E1 requires the carrying article URL; an item without one
        # cannot be persisted as provenance-complete.
        return None
    item_url = str(item.url)
    if not _url_is_secret_free(image_url) or not _url_is_secret_free(item_url):
        # R13 screening (see module docstring): drop entirely — never
        # persist a partially-redacted URL that would break I1 identity.
        _logger.warning(
            "image candidate dropped: secret-shaped content in URL "
            "(source_name=%s) — URL withheld from this log line",
            item.source_name,
        )
        return None

    width = item.raw_metadata.get("image_width")
    height = item.raw_metadata.get("image_height")
    mime = item.raw_metadata.get("image_mime")
    credit = item.raw_metadata.get("image_credit")

    title = sanitize_provenance_text(item.title)[:_ITEM_TITLE_MAX]
    credit_text: str | None = None
    if isinstance(credit, str) and credit:
        credit_text = sanitize_provenance_text(credit)[:_IMAGE_CREDIT_MAX]

    try:
        return ImageCandidateRecord(
            candidate_id=candidate_id_for_url(image_url),
            image_url=image_url,
            source_name=item.source_name,
            segment=segment,
            item_url=item_url,
            item_title=title,
            # bool is an int subclass — exclude it from the int fields.
            image_width=width if isinstance(width, int) and not isinstance(width, bool) else None,
            image_height=(
                height if isinstance(height, int) and not isinstance(height, bool) else None
            ),
            image_mime=mime if isinstance(mime, str) and mime else None,
            image_credit=credit_text,
            collected_on=target_date,
        )
    except ValidationError:
        _logger.warning(
            "image candidate dropped: record validation failed (source_name=%s)",
            item.source_name,
        )
        return None


def _url_is_secret_free(url: str) -> bool:
    """R13 fail-closed URL screen (module docstring — sanitize split).

    Rejects a URL carrying any current secret env-var value or a
    :func:`scan_for_leak` hit (the URL-context-aware detector designed
    for link-bearing text — legitimate long CDN path runs pass; token /
    JWT / email shapes fail).
    """

    for name in SECRET_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value and value in url:
            return False
    return scan_for_leak(url) is None


def _read_existing_rows(path: Path) -> tuple[dict[str, ImageCandidateRecord], int]:
    """Parse the existing date ledger; unparseable lines drop with WARN."""

    if not path.exists():
        return {}, 0
    rows: dict[str, ImageCandidateRecord] = {}
    invalid = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = ImageCandidateRecord.model_validate_json(line)
        except (ValidationError, json.JSONDecodeError):
            invalid += 1
            _logger.warning(
                "image candidate ledger %s line %d unparseable — dropped from merge",
                path,
                line_number,
            )
            continue
        # First occurrence wins if a (hand-edited) file carries dupes.
        rows.setdefault(record.candidate_id, record)
    return rows, invalid


# ---------------------------------------------------------------------------
# Step 2 — recurrence index + rights-state mirror (Contract #2/#3 read-side)
# ---------------------------------------------------------------------------

_INDEX_FILENAME: Final[str] = "index.json"
_CLEARANCES_DIRNAME: Final[str] = "clearances"

# E5 — the only recognized rights states. The clearances directory
# encodes the state; code only reads it (I14).
ImageRightsState = Literal["metadata-only", "cleared", "blocked"]

_RIGHTS_METADATA_ONLY: Final[ImageRightsState] = "metadata-only"
_RIGHTS_CLEARED: Final[ImageRightsState] = "cleared"
_RIGHTS_BLOCKED: Final[ImageRightsState] = "blocked"


class RecurrenceIndexEntry(BaseModel):
    """One ``index.json`` entry (E2). Field order = serialization order (I6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    first_seen: date
    last_seen: date
    seen_count: int = Field(ge=1)
    sources: tuple[str, ...]
    rights_state: ImageRightsState


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Outcome counts for one :func:`update_index` run (R5)."""

    index_path: Path
    ledger_dates_scanned: int
    candidates_indexed: int
    metadata_only: int
    cleared: int
    blocked: int
    invalid_clearances: int
    invalid_ledger_rows: int


def index_path_for(*, ledger_root: Path = DEFAULT_LEDGER_ROOT) -> Path:
    """Return the recurrence index path (Contract #2 / R5 layout)."""

    return ledger_root / _INDEX_FILENAME


def clearances_dir_for(*, ledger_root: Path = DEFAULT_LEDGER_ROOT) -> Path:
    """Return the operator clearance directory (Contract #3 / R6 layout)."""

    return ledger_root / _CLEARANCES_DIRNAME


def update_index(
    target_date: date,
    *,
    ledger_root: Path = DEFAULT_LEDGER_ROOT,
) -> IndexReport:
    """Rebuild ``index.json`` from every date ledger + the clearances dir.

    Derived-only full rebuild (I6): recurrence facts come from the date
    ledgers; ``rights_state`` mirrors clearance-directory file existence
    at write time (I7, ``blocked`` wins) and is never a source of truth
    (I14). The rewrite is atomic (I5) and byte-deterministic (sorted
    ``candidate_id`` keys, fixed entry key order). ``target_date`` is
    run context for the summary log only — no persisted value reads it
    or the wall clock (I3/R5).

    Nothing is written when there are no ledgers and no pre-existing
    index (mirrors the Step 1 empty-merge behavior); an existing index
    is refreshed even to empty so removals stay reflected.
    """

    appearances: dict[str, set[date]] = {}
    sources: dict[str, set[str]] = {}
    ledger_dates = 0
    invalid_ledger_rows = 0

    for ledger_file in sorted(ledger_root.glob("[0-9][0-9][0-9][0-9]/*.jsonl")):
        try:
            ledger_date = date.fromisoformat(ledger_file.stem)
        except ValueError:
            _logger.warning(
                "image candidate ledger %s has a non-date filename — skipped from index",
                ledger_file,
            )
            continue
        ledger_dates += 1
        rows, invalid = _read_existing_rows(ledger_file)
        invalid_ledger_rows += invalid
        for cid, record in rows.items():
            appearances.setdefault(cid, set()).add(ledger_date)
            sources.setdefault(cid, set()).add(record.source_name)

    clearances_dir = clearances_dir_for(ledger_root=ledger_root)
    entries: dict[str, RecurrenceIndexEntry] = {}
    counts = {_RIGHTS_METADATA_ONLY: 0, _RIGHTS_CLEARED: 0, _RIGHTS_BLOCKED: 0}
    invalid_clearances = 0
    for cid in sorted(appearances):
        dates = appearances[cid]
        rights_state, clearance_invalid = _mirror_rights_state(cid, clearances_dir)
        if clearance_invalid:
            invalid_clearances += 1
        counts[rights_state] += 1
        entries[cid] = RecurrenceIndexEntry(
            first_seen=min(dates),
            last_seen=max(dates),
            seen_count=len(dates),  # R5 — distinct ledger dates
            sources=tuple(sorted(sources[cid])),
            rights_state=rights_state,
        )

    path = index_path_for(ledger_root=ledger_root)
    if entries or path.exists():
        payload = {cid: entry.model_dump(mode="json") for cid, entry in entries.items()}
        write_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    _logger.info(
        "image candidate index rebuilt target_date=%s candidates=%d cleared=%d "
        "blocked=%d invalid_clearances=%d",
        target_date.isoformat(),
        len(entries),
        counts[_RIGHTS_CLEARED],
        counts[_RIGHTS_BLOCKED],
        invalid_clearances,
    )
    return IndexReport(
        index_path=path,
        ledger_dates_scanned=ledger_dates,
        candidates_indexed=len(entries),
        metadata_only=counts[_RIGHTS_METADATA_ONLY],
        cleared=counts[_RIGHTS_CLEARED],
        blocked=counts[_RIGHTS_BLOCKED],
        invalid_clearances=invalid_clearances,
        invalid_ledger_rows=invalid_ledger_rows,
    )


def _mirror_rights_state(cid: str, clearances_dir: Path) -> tuple[ImageRightsState, bool]:
    """Mirror clearance-file existence into a rights state (I7/I8/I9).

    Returns ``(state, clearance_invalid)`` where ``clearance_invalid``
    flags a present-but-unusable manifest (fail-closed to
    ``metadata-only``). Read-only — never touches the files (I14).
    """

    if (clearances_dir / f"{cid}.blocked").exists():
        # I7 — blocked wins over any coexisting manifest (fail-safe).
        return _RIGHTS_BLOCKED, False
    manifest, invalid = _load_valid_clearance(cid, clearances_dir)
    if manifest is not None:
        return _RIGHTS_CLEARED, False
    return _RIGHTS_METADATA_ONLY, invalid


def _load_valid_clearance(
    cid: str, clearances_dir: Path
) -> tuple[ExternalAssetManifest | None, bool]:
    """Load + validate the clearance manifest for ``cid`` (E3, I8, I9).

    Returns ``(manifest, invalid)``: a valid manifest with
    ``invalid=False``; ``(None, False)`` when the file simply does not
    exist; ``(None, True)`` + one WARN when the file exists but is
    unparseable, has the wrong ``kind``, or fails the I9 URL-identity
    hash. Shared by the index mirror (Step 2) and the fetch path
    (Step 3), which re-checks the file truth per I8/I9 rather than
    trusting the index (I7 — the index is never a source of truth).
    """

    manifest_path = clearances_dir / f"{cid}.manifest.json"
    if not manifest_path.exists():
        return None, False
    try:
        manifest = ExternalAssetManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (ValidationError, OSError, UnicodeDecodeError):
        _logger.warning(
            "clearance manifest for candidate %s is unparseable — treated as metadata-only",
            cid,
        )
        return None, True
    if manifest.kind != "explicit-license":
        # E3 — the per-candidate clearance contract is explicit-license
        # only; curated-licensed manifests belong to the u86 library.
        _logger.warning(
            "clearance manifest for candidate %s has kind=%r (expected 'explicit-license') "
            "— treated as metadata-only",
            cid,
            manifest.kind,
        )
        return None, True
    if candidate_id_for_url(str(manifest.source_url)) != cid:
        # I9 — a clearance authored for URL A never authorizes URL B.
        _logger.warning(
            "clearance manifest for candidate %s has a source_url that does not hash to "
            "the candidate id — treated as metadata-only",
            cid,
        )
        return None, True
    return manifest, False


# ---------------------------------------------------------------------------
# Step 3 — quadruple-gated fetch + content-addressed store (Contract #4)
# ---------------------------------------------------------------------------

# Contract #4 store root: assets/images/{candidate_id[:2]}/{candidate_id}{ext}.
DEFAULT_STORE_ROOT: Final[Path] = Path("assets") / "images"

# The _extension_for_image output set (I11) — the only extensions the
# store may ever contain (also the I10 existence-probe set).
_STORE_EXTENSIONS: Final[tuple[str, ...]] = (".png", ".jpg")

_CONTENT_TYPE_FOR_EXTENSION: Final[dict[str, Literal["image/png", "image/jpeg"]]] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
}

_STORE_CARD_KIND: Final[str] = "external-context-image"


@dataclass(frozen=True, slots=True)
class FetchReport:
    """Outcome counts for one :func:`fetch_cleared_candidates` run (R8).

    ``scraping_enabled=False`` short-circuits everything (gate 2 of
    I13): every other count is zero. ``cleared`` is the file-truth
    cleared set entering the gate chain; ``attempted`` counts actual
    HTTP fetches (``skipped_existing`` candidates never produce one —
    I10). ``fetch_failed`` covers HTTP errors and the signature /
    byte-cap / dimension validation rejections (I11 — nothing written).

    ``stored_paths`` (u137 Step 4) lists the binary + sidecar files
    written by THIS run — pre-existing (skipped) binaries are excluded
    — so the orchestrator can join exactly the new store outputs to the
    publish staging list (R9).
    """

    store_root: Path
    scraping_enabled: bool
    candidates_considered: int
    cleared: int
    invalid_clearances: int
    gate_blocked: int
    skipped_existing: int
    attempted: int
    fetch_failed: int
    stored: int
    stored_paths: tuple[Path, ...] = ()


def store_binary_path(
    candidate_id: str,
    extension: str,
    *,
    store_root: Path = DEFAULT_STORE_ROOT,
) -> Path:
    """Return the content-addressed store path (Contract #4 / E4 layout)."""

    return store_root / candidate_id[:2] / f"{candidate_id}{extension}"


def store_sidecar_path(binary_path: Path) -> Path:
    """Return the provenance sidecar path for a store binary (E4, TS-2 b)."""

    return binary_path.with_name(binary_path.name + ".provenance.json")


def read_index(*, ledger_root: Path = DEFAULT_LEDGER_ROOT) -> dict[str, RecurrenceIndexEntry]:
    """Load ``index.json`` into typed entries ({} when absent).

    Companion to :func:`update_index` for the Step 4 pipeline sequence
    (BLM §4: the fetch stage consumes the index the same run rebuilt).
    """

    path = index_path_for(ledger_root=ledger_root)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        cid: RecurrenceIndexEntry.model_validate(entry) for cid, entry in sorted(payload.items())
    }


def fetch_cleared_candidates(
    index: Mapping[str, RecurrenceIndexEntry],
    *,
    ledger_root: Path = DEFAULT_LEDGER_ROOT,
    store_root: Path = DEFAULT_STORE_ROOT,
    client: httpx.Client | None = None,
) -> FetchReport:
    """Fetch + store binaries for cleared candidates only (R8, I13).

    The quadruple gate (I13) — every fetch requires ALL of:

    1. file-truth ``cleared`` rights state with a valid manifest
       (I8/I9 re-checked here; the index only supplies the candidate
       universe and is never trusted for rights — I7/I14, so a
       ``.blocked`` marker added after the index rebuild still blocks);
    2. ``external_image_scraping_enabled()`` env opt-in — checked first,
       zero-fetch report when off;
    3. ``assert_external_asset_allowed`` for the clearance manifest
       (invoked with the env-derived flag; the module-level
       ``EXTERNAL_IMAGE_SCRAPING_ENABLED`` default stays ``False``);
    4. ``assert_external_image_host_allowed`` (public host + optional
       ``INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS`` allowlist).

    ``metadata-only`` / ``blocked`` candidates produce zero fetch
    attempts under every combination of the other gates (AC-137.2).
    The store is content-addressed: an existing binary skips the fetch
    entirely and leaves the sidecar untouched (I10 — zero git churn).
    Validation reuses the u19 machinery (I11 — PNG/JPEG signature,
    100 B-2,000,000 B cap); failures store nothing + one WARN. The
    sidecar records ``content_sha256`` (bytes hash, distinct from the
    URL-hash id) and ``candidate_id`` (I12); its ``generated_at`` is
    the operator's ``fetched_on`` verification date at UTC midnight —
    never the wall clock (I3, BLM §6: sidecars are written once and
    never churned).
    """

    scraping_enabled = external_image_scraping_enabled()
    if not scraping_enabled:
        # Gate (2) — I13/I17: a default run stores exactly zero binaries.
        return FetchReport(
            store_root=store_root,
            scraping_enabled=False,
            candidates_considered=len(index),
            cleared=0,
            invalid_clearances=0,
            gate_blocked=0,
            skipped_existing=0,
            attempted=0,
            fetch_failed=0,
            stored=0,
        )

    clearances_dir = clearances_dir_for(ledger_root=ledger_root)
    cleared = 0
    invalid_clearances = 0
    gate_blocked = 0
    skipped_existing = 0
    attempted = 0
    fetch_failed = 0
    stored = 0
    stored_paths: tuple[Path, ...] = ()

    for cid in sorted(index):
        if (clearances_dir / f"{cid}.blocked").exists():
            # Gate (1) / I7 / I15 — blocked is permanent exclusion,
            # regardless of what the (possibly stale) index says.
            continue
        manifest, invalid = _load_valid_clearance(cid, clearances_dir)
        if manifest is None:
            if invalid:
                invalid_clearances += 1
            continue  # metadata-only — never a fetch candidate (I13)
        cleared += 1

        if any(
            store_binary_path(cid, ext, store_root=store_root).exists() for ext in _STORE_EXTENSIONS
        ):
            # I10 — content-addressed idempotency: no fetch, sidecar
            # untouched, zero git churn.
            skipped_existing += 1
            continue

        url = str(manifest.source_url)
        try:
            # Gates (3) + (4) — explicit per BLM §3 so a policy trip is
            # distinguishable from a network/validation failure.
            assert_external_asset_allowed(manifest, scraping_enabled=scraping_enabled)
            assert_external_image_host_allowed(url, allowed_hosts=allowed_external_image_hosts())
        except ExternalAssetPolicyError as exc:
            gate_blocked += 1
            _logger.warning("image store fetch blocked for candidate %s: %s", cid, exc)
            continue

        attempted += 1
        fetched = fetch_manifest_image(manifest, manifest.attribution, client=client)
        if fetched is None:
            # I11 / AC-1.1 — HTTP failure or signature/byte-cap
            # rejection; nothing written.
            fetch_failed += 1
            _logger.warning(
                "image store fetch failed or rejected for candidate %s — nothing stored",
                cid,
            )
            continue

        dimensions = read_image_dimensions(fetched.content, fetched.extension)
        if dimensions is None:
            fetch_failed += 1
            _logger.warning(
                "image store fetch for candidate %s has unreadable dimensions — nothing stored",
                cid,
            )
            continue

        binary_path = store_binary_path(cid, fetched.extension, store_root=store_root)
        write_atomic_bytes(binary_path, fetched.content)
        sidecar_manifest = build_external_provenance(
            # Canonical Contract #4 store address — the manifest
            # describes the store location, not an injected test root.
            asset_relative_path=f"assets/images/{cid[:2]}/{binary_path.name}",
            card_kind=_STORE_CARD_KIND,
            generated_at=datetime.combine(manifest.fetched_on, time(0), tzinfo=UTC),
            width=dimensions[0],
            height=dimensions[1],
            content_type=_CONTENT_TYPE_FOR_EXTENSION[fetched.extension],
            license_name=manifest.license,
            attribution=manifest.attribution,
            author=manifest.author,
            allowed_use=manifest.allowed_use,
            fetched_from_host=urlsplit(url).hostname or "",
            additional_metadata={
                # I12 — bytes hash, distinct from the URL-hash id.
                "content_sha256": hashlib.sha256(fetched.content).hexdigest(),
                "candidate_id": cid,
            },
        )
        sidecar_path = store_sidecar_path(binary_path)
        write_manifest(sidecar_manifest, binary_path, sidecar_path=sidecar_path)
        stored += 1
        stored_paths = (*stored_paths, binary_path, sidecar_path)

    return FetchReport(
        store_root=store_root,
        scraping_enabled=True,
        candidates_considered=len(index),
        cleared=cleared,
        invalid_clearances=invalid_clearances,
        gate_blocked=gate_blocked,
        skipped_existing=skipped_existing,
        attempted=attempted,
        fetch_failed=fetch_failed,
        stored=stored,
        stored_paths=stored_paths,
    )


__all__ = [
    "DEFAULT_LEDGER_ROOT",
    "DEFAULT_STORE_ROOT",
    "FetchReport",
    "ImageCandidateRecord",
    "ImageRightsState",
    "IndexReport",
    "LedgerWriteReport",
    "RecurrenceIndexEntry",
    "append_candidates",
    "candidate_id_for_url",
    "clearances_dir_for",
    "fetch_cleared_candidates",
    "index_path_for",
    "ledger_path_for",
    "normalize_image_url",
    "read_index",
    "store_binary_path",
    "store_sidecar_path",
    "update_index",
]
