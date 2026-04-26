"""FetchWindow — UTC time window covering a KST trading date.

Defined per ``aidlc-docs/construction/u1-sources/functional-design/``
(``domain-entities.md`` §E3, ``business-rules.md`` R7). Adapters use a
:class:`FetchWindow` to filter source data to the slice of time the
orchestrator is publishing for. KST (Asia/Seoul, fixed UTC+9, no DST)
is the trading-date frame; the window is expressed in UTC so adapters
never need to do per-source timezone bookkeeping.

This is an internal helper — not part of the package's public re-export
surface. Other units must not import it directly.

Boundary notes:

* :meth:`from_kst_date` only supports dates where the KST→UTC conversion
  and the +1-day arithmetic do not overflow Python's ``date`` range
  (roughly years 1 through 9999, exclusive at both extremes by one day).
  Out-of-range dates raise :class:`ValueError`.
* :class:`FetchWindow` is a frozen + slots dataclass. Construction
  invariants are enforced in ``__post_init__``. Round-tripping a
  :class:`FetchWindow` through ``copy.copy`` or ``pickle`` may bypass
  ``__post_init__`` (a Python implementation detail of frozen
  dataclasses); the codebase does not currently rely on either path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")


def _ensure_tz_aware(dt: datetime, *, label: str) -> None:
    """Raise ``ValueError`` if ``dt`` is naive or has a misbehaving tzinfo.

    Standard tzinfos (``UTC``, ``timezone(...)``, ``ZoneInfo(...)``)
    return a non-``None`` offset and never raise from ``utcoffset``.
    Custom subclasses can do either; we wrap to keep the error contract
    on this module a single ``ValueError`` surface.
    """

    if dt.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    try:
        offset = dt.tzinfo.utcoffset(dt)
    except Exception as exc:
        raise ValueError(f"{label} tzinfo failed to resolve offset: {exc}") from exc
    if offset is None:
        raise ValueError(f"{label} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class FetchWindow:
    """A half-open ``[start_utc, end_utc)`` UTC window for one KST trading date.

    ``target_date`` is kept as the original KST date for reference;
    ``start_utc`` and ``end_utc`` are derived from it via
    :meth:`from_kst_date`. The frozen + slots dataclass is the lightest
    container that gets us value-equality and immutability without
    pulling in pydantic's validator pipeline for an internal type.
    """

    start_utc: datetime
    end_utc: datetime
    target_date: date

    def __post_init__(self) -> None:
        # Both bounds must be tz-aware so the half-open comparison in
        # :meth:`contains` is unambiguous.
        _ensure_tz_aware(self.start_utc, label="start_utc")
        _ensure_tz_aware(self.end_utc, label="end_utc")
        if self.end_utc <= self.start_utc:
            raise ValueError("end_utc must be strictly after start_utc")

    @classmethod
    def from_kst_date(cls, target_date: date) -> FetchWindow:
        """Build a 24-hour window covering ``target_date`` in KST.

        Example: ``from_kst_date(date(2026, 4, 27))`` yields
        ``[2026-04-26 15:00 UTC, 2026-04-27 15:00 UTC)``.

        Raises ``ValueError`` if ``target_date`` is so close to the
        ``date.min`` / ``date.max`` boundary that KST→UTC conversion or
        ``+1 day`` arithmetic overflows.
        """

        try:
            start_kst = datetime.combine(target_date, time.min, tzinfo=_KST)
            end_kst = start_kst + timedelta(days=1)
            return cls(
                start_utc=start_kst.astimezone(UTC),
                end_utc=end_kst.astimezone(UTC),
                target_date=target_date,
            )
        except OverflowError as exc:
            raise ValueError(
                f"target_date out of supported range for KST window: {target_date}"
            ) from exc

    def contains(self, dt: datetime) -> bool:
        """Return whether ``dt`` falls in the window (half-open ``[start, end)``).

        Naive datetimes are rejected with ``ValueError`` — adapters must
        convert source timestamps to a tz-aware datetime before calling
        (R7). The half-open shape means adjacent windows tile a day
        without overlap or gap.
        """

        _ensure_tz_aware(dt, label="dt")
        return self.start_utc <= dt < self.end_utc
