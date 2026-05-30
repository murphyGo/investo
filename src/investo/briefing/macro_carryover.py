"""JSONL persistence + pure lifecycle transition for u59 macro carryover.

The transition (:func:`advance_macro_lifecycle`) is pure and deterministic:
it takes the prior loaded :class:`MacroLifecycleEvent`s, today's collected
macro :class:`NormalizedItem`s, and an explicit ``target_date`` (never the
wall clock), and returns the next snapshot keyed by ``event_key`` (never by
title substring matching).

Lifecycle rule implemented (from the plan "Macro Carryover Lifecycle"):

- A macro event observed today with no confirmed actual and whose
  ``scheduled_date`` is still in the future (``> target_date``) is
  ``scheduled``.
- On/after the release day (``scheduled_date <= target_date``) with no
  confirmed actual collected for that ``event_key`` today, the event is
  ``unresolved`` and carried forward to the next run.
- An ``actual`` print collected today for the ``event_key`` (a collected
  item whose ``macro_event_status == "actual"``) flips the event to
  ``confirmed``: ``confirmed_date`` is set to ``target_date`` and
  ``follow_up_until`` is set to ``target_date + 1 day`` (one follow-up day
  for market absorption / rate reaction).
- **Confirmation window**: one grace day after the scheduled release. An
  event still ``unresolved`` once ``target_date > scheduled_date + 1 day``
  (i.e. past the release day plus one grace day) becomes ``stale``.
- A ``confirmed`` event whose ``follow_up_until < target_date`` is DROPPED
  (omitted from the returned snapshot) unless it is reintroduced today.

Ordering is deterministic (sorted by ``event_key``). This module never
imports from the orchestrator; the orchestrator wires the transition.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from investo.models import MacroLifecycleEvent, NormalizedItem
from investo.models.macro import (
    macro_event_date,
    macro_event_key,
    macro_event_status,
)
from investo.models.macro_lifecycle import MacroLifecycleStatus
from investo.models.segments import MarketSegment

DEFAULT_MACRO_CARRYOVER_PATH: Final[Path] = Path("archive/_meta/macro_event_carryover.jsonl")

# Confirmation window: the release day plus one grace day. An event still
# ``unresolved`` after this window becomes ``stale``.
_CONFIRMATION_GRACE_DAYS: Final[int] = 1
# Keep one follow-up day after a confirmed actual for market absorption.
_FOLLOW_UP_DAYS: Final[int] = 1


class MacroCarryoverError(RuntimeError):
    """Raised when macro carryover state cannot be persisted."""


def load_macro_lifecycle_events(
    path: Path = DEFAULT_MACRO_CARRYOVER_PATH,
) -> tuple[MacroLifecycleEvent, ...]:
    """Load valid lifecycle events from JSONL, skipping corrupt rows."""
    if not path.exists():
        return ()
    events: list[MacroLifecycleEvent] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                    event_payload = payload.get("event") if isinstance(payload, dict) else None
                    events.append(MacroLifecycleEvent.model_validate(event_payload))
                except (json.JSONDecodeError, ValidationError, AttributeError):
                    continue
    except OSError as exc:
        raise MacroCarryoverError(f"could not read macro carryover state: {exc}") from exc
    return tuple(events)


def upsert_macro_lifecycle_snapshot(
    target_date: date,
    events: Sequence[MacroLifecycleEvent],
    *,
    path: Path = DEFAULT_MACRO_CARRYOVER_PATH,
) -> Path:
    """Replace the rows for ``target_date`` and keep other JSONL rows."""
    rows = _load_rows(path)
    target = target_date.isoformat()
    kept = [row for row in rows if row.get("target_date") != target]
    kept.extend(
        {
            "target_date": target,
            "event_key": event.event_key,
            "event": event.model_dump(mode="json"),
        }
        for event in events
    )
    kept.sort(key=lambda row: (str(row.get("target_date", "")), str(row.get("event_key", ""))))
    _write_rows_atomic(path, kept)
    return path


def advance_macro_lifecycle(
    prior_events: Sequence[MacroLifecycleEvent],
    collected_items: Sequence[NormalizedItem],
    target_date: date,
    *,
    segment_for: Callable[[NormalizedItem], MarketSegment] | None = None,
) -> tuple[MacroLifecycleEvent, ...]:
    """Return the next lifecycle snapshot for ``target_date``.

    Pure and deterministic. Joins today's collected macro items to prior
    state by ``event_key`` (never substring). ``segment_for`` maps a
    collected item to its routed segment (the orchestrator supplies the
    real router from ``segment_items``); when ``None`` a conservative
    ``us-equity`` default is used for newly observed events.
    """
    resolve_segment = segment_for or _default_segment_for

    prior_by_key: dict[str, MacroLifecycleEvent] = {ev.event_key: ev for ev in prior_events}

    # Collapse today's collected macro items by event_key. Keep the first
    # item seen for stable label/source/segment, but track whether any
    # collected item for the key carries an "actual" status.
    todays_items: dict[str, NormalizedItem] = {}
    confirmed_keys: set[str] = set()
    for item in collected_items:
        key = macro_event_key(item)
        if key is None:
            continue
        todays_items.setdefault(key, item)
        if macro_event_status(item) == "actual":
            confirmed_keys.add(key)

    next_by_key: dict[str, MacroLifecycleEvent] = {}

    # 1) Events observed today (scheduled / unresolved / confirmed).
    for key, item in todays_items.items():
        prior = prior_by_key.get(key)
        next_by_key[key] = _advance_observed_event(
            key,
            item,
            prior,
            target_date,
            confirmed=key in confirmed_keys,
            resolve_segment=resolve_segment,
        )

    # 2) Prior events not re-observed today: carry / stale / drop.
    for key, prior in prior_by_key.items():
        if key in next_by_key:
            continue
        carried = _carry_unobserved_event(prior, target_date)
        if carried is not None:
            next_by_key[key] = carried

    return tuple(next_by_key[key] for key in sorted(next_by_key))


def _advance_observed_event(
    event_key: str,
    item: NormalizedItem,
    prior: MacroLifecycleEvent | None,
    target_date: date,
    *,
    confirmed: bool,
    resolve_segment: Callable[[NormalizedItem], MarketSegment],
) -> MacroLifecycleEvent:
    label = _label_for(item, prior)
    source_name = item.source_name
    segment = prior.segment if prior is not None else resolve_segment(item)
    scheduled_date = _scheduled_date_for(item, prior)

    if confirmed:
        return MacroLifecycleEvent(
            event_key=event_key,
            label=label,
            source_name=source_name,
            segment=segment,
            status="confirmed",
            scheduled_date=scheduled_date,
            confirmed_date=target_date,
            follow_up_until=target_date + timedelta(days=_FOLLOW_UP_DAYS),
        )

    # A previously-confirmed event re-observed without a fresh actual stays
    # confirmed (do not regress to scheduled/unresolved).
    if prior is not None and prior.status == "confirmed":
        return prior.model_copy(update={"label": label, "scheduled_date": scheduled_date})

    if scheduled_date is not None and scheduled_date > target_date:
        return MacroLifecycleEvent(
            event_key=event_key,
            label=label,
            source_name=source_name,
            segment=segment,
            status="scheduled",
            scheduled_date=scheduled_date,
        )

    # Release day arrived (or no schedule date) but no confirmed actual.
    effective_schedule = scheduled_date or target_date
    status: MacroLifecycleStatus = (
        "stale" if _is_stale(effective_schedule, target_date) else "unresolved"
    )
    return MacroLifecycleEvent(
        event_key=event_key,
        label=label,
        source_name=source_name,
        segment=segment,
        status=status,
        scheduled_date=effective_schedule,
    )


def _carry_unobserved_event(
    prior: MacroLifecycleEvent,
    target_date: date,
) -> MacroLifecycleEvent | None:
    if prior.status == "confirmed":
        # Drop once the one follow-up day has elapsed.
        if prior.follow_up_until is not None and prior.follow_up_until < target_date:
            return None
        return prior

    if prior.status == "stale":
        return prior

    # scheduled / unresolved: advance toward unresolved/stale.
    scheduled_date = prior.scheduled_date or target_date
    if prior.status == "scheduled" and scheduled_date > target_date:
        return prior

    if _is_stale(scheduled_date, target_date):
        return prior.model_copy(update={"status": "stale", "scheduled_date": scheduled_date})
    return prior.model_copy(update={"status": "unresolved", "scheduled_date": scheduled_date})


def _is_stale(scheduled_date: date, target_date: date) -> bool:
    return target_date > scheduled_date + timedelta(days=_CONFIRMATION_GRACE_DAYS)


def _label_for(item: NormalizedItem, prior: MacroLifecycleEvent | None) -> str:
    metadata = item.raw_metadata
    for key in ("macro_event_label", "release_name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    if prior is not None:
        return prior.label
    return item.title[:120] or "macro event"


def _scheduled_date_for(item: NormalizedItem, prior: MacroLifecycleEvent | None) -> date | None:
    derived = macro_event_date(item)
    if derived is not None:
        return derived
    return prior.scheduled_date if prior is not None else None


def _default_segment_for(_item: NormalizedItem) -> MarketSegment:
    return "us-equity"


def _load_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for raw_line in fp:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError as exc:
        raise MacroCarryoverError(f"could not read macro carryover state: {exc}") from exc
    return rows


def _write_rows_atomic(path: Path, rows: Sequence[dict[str, object]]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise MacroCarryoverError(f"could not write macro carryover state: {exc}") from exc


__all__ = [
    "DEFAULT_MACRO_CARRYOVER_PATH",
    "MacroCarryoverError",
    "advance_macro_lifecycle",
    "load_macro_lifecycle_events",
    "upsert_macro_lifecycle_snapshot",
]
