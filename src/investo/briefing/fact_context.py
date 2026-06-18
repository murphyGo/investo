"""Verified fact bundle extraction and prompt rendering."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from investo.models import NormalizedItem
from investo.models.facts import FactId, FactSnapshot, VerifiedFactBundle

_logger = logging.getLogger(__name__)
_KNOWN_FACT_IDS: Final[tuple[FactId, ...]] = ("fed.current_chair",)
_FACT_CONTEXT_MAX_CHARS: Final[int] = 600


class VerifiedFactConflictError(RuntimeError):
    """Raised when same-run fresh fact snapshots disagree."""

    def __init__(self, fact_id: FactId, values: tuple[str, ...]) -> None:
        self.fact_id = fact_id
        self.values = values
        super().__init__(f"verified fact conflict fact_id={fact_id} values={','.join(values)}")


def build_verified_fact_bundle(
    items: list[NormalizedItem] | tuple[NormalizedItem, ...],
    target_date: date,
    now_utc: datetime,
) -> VerifiedFactBundle:
    """Build a bundle from source-emitted fact metadata."""

    _ensure_tz_aware(now_utc)
    by_id: dict[FactId, FactSnapshot] = {}
    for item in items:
        fact_id_raw = item.raw_metadata.get("fact_id")
        if fact_id_raw != "fed.current_chair":
            continue
        try:
            snapshot = _snapshot_from_item(item, target_date=target_date)
        except (ValidationError, ValueError, TypeError) as exc:
            _logger.warning(
                "[facts] invalid fact metadata source=%s fact_id=%s error=%s",
                item.source_name,
                fact_id_raw,
                exc,
            )
            continue
        if snapshot.expires_at <= now_utc:
            snapshot = snapshot.model_copy(update={"status": "stale"})
        existing = by_id.get(snapshot.fact_id)
        if existing is not None and _conflicts(existing, snapshot, now_utc):
            raise VerifiedFactConflictError(
                snapshot.fact_id,
                tuple(sorted({existing.value, snapshot.value})),
            )
        by_id[snapshot.fact_id] = snapshot
    return VerifiedFactBundle(target_date=target_date, facts=tuple(by_id.values()))


def render_fact_context_block(bundle: VerifiedFactBundle, now_utc: datetime) -> str:
    """Render the Stage 2 verified-facts block."""

    _ensure_tz_aware(now_utc)
    lines = ["## 검증된 현재 팩트"]
    fact = bundle.fresh("fed.current_chair", now_utc)
    if fact is None:
        lines.append("- fed.current_chair: unverified; do not name the current Fed chair")
    else:
        label = f" ({fact.label_ko})" if fact.label_ko else ""
        lines.append(
            f"- fed.current_chair: {fact.value}{label}, {fact.role}, "
            f"source={fact.source_name}, expires={fact.expires_at.isoformat()}"
        )
    rendered = "\n".join(lines)
    if len(rendered) > _FACT_CONTEXT_MAX_CHARS:
        return rendered[: _FACT_CONTEXT_MAX_CHARS - 1] + "…"
    return rendered


def fact_snapshot_jsonl_row(
    bundle: VerifiedFactBundle,
    *,
    target_date: date,
    observed_at: datetime,
    conflict_fact_ids: tuple[FactId, ...] = (),
) -> dict[str, object]:
    """Return a sanitized JSONL payload for operator diagnostics."""

    _ensure_tz_aware(observed_at)
    present = {fact.fact_id for fact in bundle.facts}
    stale = tuple(fact.fact_id for fact in bundle.facts if fact.status == "stale")
    return {
        "target_date": target_date.isoformat(),
        "observed_at": observed_at.isoformat(),
        "facts": [fact.model_dump(mode="json") for fact in bundle.facts],
        "missing_fact_ids": [fact_id for fact_id in _KNOWN_FACT_IDS if fact_id not in present],
        "stale_fact_ids": list(stale),
        "conflict_fact_ids": list(conflict_fact_ids),
    }


def append_fact_snapshot_jsonl(
    path: Path,
    bundle: VerifiedFactBundle,
    *,
    target_date: date,
    observed_at: datetime,
    conflict_fact_ids: tuple[FactId, ...] = (),
) -> Path:
    """Append one sanitized fact snapshot row."""

    row = fact_snapshot_jsonl_row(
        bundle,
        target_date=target_date,
        observed_at=observed_at,
        conflict_fact_ids=conflict_fact_ids,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def _snapshot_from_item(item: NormalizedItem, *, target_date: date) -> FactSnapshot:
    observed_at = item.published_at.astimezone(UTC)
    expires_at_raw = item.raw_metadata.get("fact_expires_at")
    if not isinstance(expires_at_raw, str):
        raise ValueError("missing fact_expires_at")
    expires_at = datetime.fromisoformat(expires_at_raw)
    status = str(item.raw_metadata.get("fact_status", "fresh"))
    if status not in {"fresh", "stale", "missing", "failed"}:
        raise ValueError(f"invalid fact_status: {status}")
    source_tier = str(item.raw_metadata.get("fact_source_tier", "S"))
    if source_tier not in {"S", "A", "B", "C"}:
        raise ValueError(f"invalid fact_source_tier: {source_tier}")
    return FactSnapshot(
        fact_id="fed.current_chair",
        value=str(item.raw_metadata["fact_value"]),
        label_ko=_optional_str(item.raw_metadata.get("fact_label_ko")),
        aliases=(),
        role=str(item.raw_metadata["fact_role"]),
        source_name=item.source_name,
        source_url=str(item.url) if item.url is not None else "",
        source_tier=source_tier,
        observed_at=observed_at,
        expires_at=expires_at,
        status=status,
        raw_evidence_label=str(item.raw_metadata["raw_evidence_label"]),
    )


def _conflicts(left: FactSnapshot, right: FactSnapshot, now_utc: datetime) -> bool:
    return (
        left.status == "fresh"
        and right.status == "fresh"
        and left.expires_at > now_utc
        and right.expires_at > now_utc
        and left.value != right.value
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _ensure_tz_aware(value: datetime) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")


__all__ = [
    "VerifiedFactConflictError",
    "append_fact_snapshot_jsonl",
    "build_verified_fact_bundle",
    "fact_snapshot_jsonl_row",
    "render_fact_context_block",
]
