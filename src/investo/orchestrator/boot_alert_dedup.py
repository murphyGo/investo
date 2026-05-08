"""u31 Step 2 — bounded dedup for boot-failure operator alerts.

When the cron run cannot construct a working pipeline (config error,
top-level programmer exception), :func:`investo.__main__._attempt_boot_alert`
sends an operator alert. Without dedup, a stuck misconfiguration pages
the operator on every cron firing — useful the first time, noise after
that.

This module persists a tiny JSON ledger of recent boot-alert
fingerprints and exposes :func:`should_alert` so the boot path can ask
"have I already paged on this exact failure within the dedup window?".
The ledger is plain text (one JSON object per file write — last-write
wins) so an operator can ``rm`` it to force the next alert.

Storage:

* Path resolved from the env var :data:`OPERATOR_STATE_DIR_ENV`
  (default ``archive/_meta/operator_state``). Operator runs may
  override it (e.g. to a GHA cache mount) without code change.
* The ledger is :data:`_LEDGER_FILENAME` inside that directory.
* The dedup window is :data:`_DEDUP_WINDOW_DAYS` days; entries older
  than the window are dropped on every read.
* Fingerprint = ``(error_type, hash(error_message))``. Two crashes
  with the same type and message are deduped; a different message
  (even one substring different) re-pages.

Pure-ish: every public function takes an explicit ``now_utc`` and
``state_path`` so callers can drive deterministic tests. The default
arguments resolve the production paths.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

_logger = logging.getLogger(__name__)

OPERATOR_STATE_DIR_ENV: Final[str] = "INVESTO_OPERATOR_STATE_DIR"
_DEFAULT_STATE_DIR: Final[Path] = Path("archive/_meta/operator_state")
_LEDGER_FILENAME: Final[str] = "boot_alerts.json"
_DEDUP_WINDOW_DAYS: Final[int] = 14
# Hard cap so a hostile error message (e.g. multi-MB stack trace) cannot
# bloat the ledger or feed an unintentionally long fingerprint key.
_FINGERPRINT_MESSAGE_MAX: Final[int] = 1024


@dataclass(frozen=True, slots=True)
class _BootAlertEntry:
    fingerprint: str
    last_emitted_at: datetime


def resolve_state_dir() -> Path:
    """Resolve the operator-state directory from env / default."""
    raw = os.environ.get(OPERATOR_STATE_DIR_ENV, "").strip()
    return Path(raw) if raw else _DEFAULT_STATE_DIR


def resolve_ledger_path() -> Path:
    """Resolve the full ledger file path."""
    return resolve_state_dir() / _LEDGER_FILENAME


def fingerprint_for(error_type: str, error_message: str) -> str:
    """Compute a stable fingerprint key for (type, message)."""
    truncated = (error_message or "")[:_FINGERPRINT_MESSAGE_MAX]
    digest = hashlib.sha256(truncated.encode("utf-8", errors="replace")).hexdigest()[:32]
    return f"{error_type}:{digest}"


def should_alert(
    *,
    error_type: str,
    error_message: str,
    now_utc: datetime,
    state_path: Path | None = None,
) -> bool:
    """Return True iff the (type, message) has not paged inside the window."""
    path = state_path if state_path is not None else resolve_ledger_path()
    fp = fingerprint_for(error_type, error_message)
    entries = _load_entries(path, now_utc=now_utc)
    return all(entry.fingerprint != fp for entry in entries)


def record_alert(
    *,
    error_type: str,
    error_message: str,
    now_utc: datetime,
    state_path: Path | None = None,
) -> None:
    """Persist that (type, message) just paged the operator."""
    path = state_path if state_path is not None else resolve_ledger_path()
    fp = fingerprint_for(error_type, error_message)
    entries = [entry for entry in _load_entries(path, now_utc=now_utc) if entry.fingerprint != fp]
    entries.append(_BootAlertEntry(fingerprint=fp, last_emitted_at=now_utc))
    _save_entries(path, entries)


def _load_entries(path: Path, *, now_utc: datetime) -> list[_BootAlertEntry]:
    """Load and prune entries older than :data:`_DEDUP_WINDOW_DAYS`."""
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else []
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("[boot_alert_dedup] could not load ledger: %s", exc)
        return []
    if not isinstance(data, list):
        return []
    horizon = now_utc - timedelta(days=_DEDUP_WINDOW_DAYS)
    out: list[_BootAlertEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        fp = item.get("fingerprint")
        ts = item.get("last_emitted_at")
        if not isinstance(fp, str) or not isinstance(ts, str):
            continue
        try:
            parsed_ts = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if parsed_ts < horizon:
            continue
        out.append(_BootAlertEntry(fingerprint=fp, last_emitted_at=parsed_ts))
    return out


def _save_entries(path: Path, entries: list[_BootAlertEntry]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialised = [
            {"fingerprint": entry.fingerprint, "last_emitted_at": entry.last_emitted_at.isoformat()}
            for entry in entries
        ]
        path.write_text(json.dumps(serialised, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        _logger.warning("[boot_alert_dedup] could not save ledger: %s", exc)


__all__ = [
    "OPERATOR_STATE_DIR_ENV",
    "fingerprint_for",
    "record_alert",
    "resolve_ledger_path",
    "resolve_state_dir",
    "should_alert",
]
