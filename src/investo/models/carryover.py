"""Carryover (event-level lifecycle) models for u52.

The u52 unit adds a *structured* day-over-day continuity surface on top
of u34's narrative continuity layer. While u34 surfaces the previous
N=5 trading-days' conclusion / driver text into the Stage 2 prompt for
free-form bridging, u52 lifts individual carryover *events* (earnings
previews, FOMC events, geopolitics, macro releases, disclosure items)
into a deterministic markdown table that:

* the LLM reads as Stage 2 input (so it can cite resolved items in §②
  and acknowledge unresolved items in §⑥);
* the orchestrator renders into a "## Watchlist Carryover" markdown
  block (single source of truth — LLM-invented rows are overridden).

Two pydantic v2 frozen models live here:

* :class:`CarryoverItem` — one event in transit between briefings.
  ``event_type`` is a closed Literal set of 6 categories; a 7th
  category being needed would escalate to its own unit. ``status``
  is also a closed Literal of 3 values mapped to Korean labels via
  :func:`status_label_kr`.
* :class:`BriefingCarryover` — per-segment container of resolved and
  unresolved carryover items, plus the actual walk-back depth used.

Both models forbid extra fields, are frozen + use slots, and live in
``models/`` (the foundation layer) so every consumer — parser,
renderer, prompt builder, orchestrator wire-through — imports them
from a single place (project-rule #3 module boundary).
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

# Closed set — 6 categories. Adding a 7th requires a separate unit
# (event_type taxonomy expansion) so this Literal stays stable and the
# regex classifier in ``briefing.carryover_parser`` cannot silently
# diverge from the model surface.
CarryoverEventType = Literal[
    "earnings",
    "fed",
    "geopolitics",
    "macro",
    "disclosure",
    "other",
]

# Closed set — 3 lifecycle states. Korean rendering labels are looked
# up via :func:`status_label_kr` so the model itself stays language-
# agnostic and the renderer owns the user-facing localization.
CarryoverStatus = Literal["resolved", "unresolved", "carried_over"]

# Korean labels for the Watchlist Carryover markdown table.
_STATUS_LABELS_KR: Final[dict[CarryoverStatus, str]] = {
    "resolved": "확인됨",
    "unresolved": "미확인",
    "carried_over": "이월",
}


def status_label_kr(status: CarryoverStatus) -> str:
    """Return the user-facing Korean label for a ``status`` value.

    Pure mapping; ``status`` is type-checked at call sites via the
    Literal alias. Used by the publisher renderer and the prompt
    formatter so both surfaces emit the same labels.
    """
    return _STATUS_LABELS_KR[status]


class CarryoverItem(BaseModel):
    """One carryover event in transit between daily briefings.

    Fields:
        event_type: closed-set category (see :data:`CarryoverEventType`).
        ticker_or_topic: free-form short identifier (≤ 64 chars) — for
            earnings it is typically the ticker (``ARM``); for fed /
            macro it is the event name (``FOMC 의사록``,
            ``CPI 발표``). Never empty.
        originated_date: the publish date of the briefing where this
            event was first mentioned (e.g. yesterday's §⑥ watch
            point or a lookahead-table row).
        expected_date: the date the event resolves (e.g. earnings
            announcement date, FOMC meeting date). ``None`` when the
            timing is open-ended.
        status: lifecycle position — ``resolved`` (today's candidates
            include a substring match for ``ticker_or_topic``),
            ``unresolved`` (still pending), ``carried_over`` (the
            ``expected_date`` is in the future relative to today).
        note: optional one-liner extra context (≤ 120 chars). Reserved
            for human-readable hints the parser extracted from the
            originating §⑥ list-item body. ``None`` when no note.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: CarryoverEventType
    ticker_or_topic: str = Field(min_length=1, max_length=64)
    originated_date: date
    expected_date: date | None = None
    status: CarryoverStatus
    note: str | None = Field(default=None, max_length=120)


class BriefingCarryover(BaseModel):
    """Per-segment carryover bundle for one briefing run.

    Returned by the archive parser and threaded into the Stage 2
    prompt + publisher renderer chain. Both lists are tuples so the
    model stays hashable / immutable.

    Fields:
        prior_resolved: items whose ``status == "resolved"``.
        prior_unresolved: items whose ``status in {"unresolved",
            "carried_over"}``. Emitted in the order received; each
            item's status is rendered via ``status_label_kr``.
        lookback_days: actual number of trading days the parser walked
            back (≤ ``INVESTO_CARRYOVER_LOOKBACK_DAYS``, clamped to
            ``[1, 7]``). May be ``0`` for the empty-context case.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    prior_resolved: tuple[CarryoverItem, ...] = ()
    prior_unresolved: tuple[CarryoverItem, ...] = ()
    lookback_days: int = Field(ge=0, le=7)

    @property
    def is_empty(self) -> bool:
        """Return ``True`` when both lists are empty.

        Orchestrator uses this to short-circuit the renderer + prompt
        injection — an empty carryover skips the "## Watchlist
        Carryover" block entirely (matches u34's "no recent context"
        behavior for first-publish / fresh-repo).
        """
        return not self.prior_resolved and not self.prior_unresolved


__all__ = [
    "BriefingCarryover",
    "CarryoverEventType",
    "CarryoverItem",
    "CarryoverStatus",
    "status_label_kr",
]
