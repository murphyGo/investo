"""Image-candidate ledger for harvested feed images (u137 Step 1).

Persists the u136 ``image_*`` raw_metadata harvest as a date-keyed JSONL
ledger — the first artifact of the u137 registry (FD Contract #1, E1,
R2/R3/R4). Later steps add the recurrence index (E2), the rights state
machine (E5), and the license-gated binary store (E4); none of that
lives here yet.

Legal posture (R1): the ledger is **metadata only**. Nothing in this
module fetches, stores, or licenses any binary; every candidate's
implicit rights state is ``metadata-only``.

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
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from investo._internal._io import write_atomic
from investo._internal.redaction import SECRET_ENV_VARS, scan_for_leak
from investo.models import NormalizedItem
from investo.models.segments import MarketSegment
from investo.visuals.provenance import sanitize_provenance_text

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


__all__ = [
    "DEFAULT_LEDGER_ROOT",
    "ImageCandidateRecord",
    "LedgerWriteReport",
    "append_candidates",
    "candidate_id_for_url",
    "ledger_path_for",
    "normalize_image_url",
]
