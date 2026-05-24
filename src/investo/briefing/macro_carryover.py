"""JSONL persistence for u59 macro lifecycle carryover state."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from investo.models import MacroLifecycleEvent

DEFAULT_MACRO_CARRYOVER_PATH: Final[Path] = Path("archive/_meta/macro_event_carryover.jsonl")


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
    "load_macro_lifecycle_events",
    "upsert_macro_lifecycle_snapshot",
]
