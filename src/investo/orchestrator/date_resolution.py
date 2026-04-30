"""KST cron-time → US trading-day mapping (US-005, AC-005-1 ~ AC-005-3).

The GitHub Actions schedule fires twice per week:

* KST 평일 07:00 (Mon-Fri morning) — for the prior US trading session
* KST 토요일 09:00 — for Friday's US trading session

In both cases the **target date** is the most recent KST weekday that
the US market closed on, walking back from the current KST calendar
date.

Per ``weekday_only_us_close=True`` (default), the function guarantees
the returned date is a weekday (Mon-Fri); on Mondays this means
skipping the weekend back to Friday. Set ``False`` to return ``kst_today
- 1 day`` raw — useful only for manual ``workflow_dispatch`` runs that
want to inspect a specific cron-fire's behavior, never for the
production cron path.

US public holidays (Thanksgiving, July 4, Memorial Day, etc.) are
**deliberately not consulted** (per Q3=A in u5 NFR Requirements +
``tech-stack-decisions.md`` TS-4 / TS-10): adding
``pandas_market_calendars`` would bring transitive ``pandas`` +
``numpy`` dependencies (~tens of MB) for a 1-person zero-cost tool
where the operator can manually re-run on the ~10 affected days per
year. Holiday-day pipelines naturally surface as empty-collect →
``EmptyCollectError`` → operator alert (per AC-003-2).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Asia/Seoul has been a fixed UTC+9 offset since 1988; no DST and no
# scheduled future transitions. Re-binding the ZoneInfo once at import
# time avoids repeated tz-database lookups per call.
_KST = ZoneInfo("Asia/Seoul")


def resolve_target_date(
    now_utc: datetime,
    *,
    weekday_only_us_close: bool = True,
) -> date:
    """Map a UTC instant to the corresponding US trading-day target date.

    Parameters
    ----------
    now_utc:
        The cron fire time as a timezone-aware UTC ``datetime``. A naive
        ``datetime`` raises ``ValueError`` at the type boundary because
        the date arithmetic depends on knowing the offset (the cron
        schedule is anchored in KST, but the input from ``datetime
        .now(UTC)`` arrives in UTC).
    weekday_only_us_close:
        When ``True`` (default; matches the production cron path), the
        returned date is always a weekday — Mondays roll back to Friday,
        Sundays (if reached via manual trigger) walk back to Friday too.
        When ``False``, returns ``kst_today - 1 day`` raw.

    Returns
    -------
    date
        The KST calendar date of the target US trading session. Always
        ``< kst_today``.

    Raises
    ------
    ValueError
        If ``now_utc`` is naive (no tzinfo). Cron-driven date math is
        unforgiving of naive datetimes — fail loudly at the boundary.
    """
    if now_utc.tzinfo is None:
        # Mirrors the existing guard in ``models._validators.ensure_tz_aware``;
        # we don't import that helper to keep ``orchestrator`` independent of
        # ``models`` validators outside of the schema-level usage.
        raise ValueError(
            "resolve_target_date requires a timezone-aware datetime; "
            "got naive datetime — pass datetime.now(UTC) or equivalent"
        )

    kst_now = now_utc.astimezone(_KST)
    target = kst_now.date() - timedelta(days=1)

    if not weekday_only_us_close:
        return target

    # ``weekday()`` returns Mon=0 .. Sun=6. Walk back while landing on
    # Saturday (5) or Sunday (6); a single iteration covers Sat→Fri,
    # two iterations cover Sun→Fri. Bounded loop — at most 2 steps.
    while target.weekday() >= 5:
        target -= timedelta(days=1)

    return target
