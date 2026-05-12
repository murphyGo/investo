"""u52 — pydantic model invariants for carryover types.

Pins:

* :class:`CarryoverItem` is frozen + ``extra="forbid"`` + closed Literal
  values for ``event_type`` and ``status``.
* :class:`BriefingCarryover` exposes the ``is_empty`` helper used by
  the orchestrator + publisher renderer to short-circuit insertion.
* :func:`status_label_kr` covers every member of
  :data:`CarryoverStatus`.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from investo.models import (
    BriefingCarryover,
    CarryoverItem,
    status_label_kr,
)


def _item(**overrides: object) -> CarryoverItem:
    base: dict[str, object] = {
        "event_type": "earnings",
        "ticker_or_topic": "ARM",
        "originated_date": date(2026, 5, 6),
        "expected_date": date(2026, 5, 7),
        "status": "resolved",
        "note": None,
    }
    base.update(overrides)
    return CarryoverItem(**base)  # type: ignore[arg-type]


def test_carryover_item_frozen_rejects_mutation() -> None:
    item = _item()
    with pytest.raises(ValidationError):
        item.ticker_or_topic = "AAPL"  # type: ignore[misc]


def test_carryover_item_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        CarryoverItem(
            event_type="earnings",
            ticker_or_topic="ARM",
            originated_date=date(2026, 5, 6),
            status="resolved",
            unknown_field="x",  # type: ignore[call-arg]
        )


def test_carryover_item_rejects_off_set_event_type() -> None:
    with pytest.raises(ValidationError):
        CarryoverItem(
            event_type="esg",  # type: ignore[arg-type]
            ticker_or_topic="ARM",
            originated_date=date(2026, 5, 6),
            status="resolved",
        )


def test_carryover_item_rejects_off_set_status() -> None:
    with pytest.raises(ValidationError):
        CarryoverItem(
            event_type="earnings",
            ticker_or_topic="ARM",
            originated_date=date(2026, 5, 6),
            status="pending",  # type: ignore[arg-type]
        )


def test_carryover_item_rejects_empty_topic() -> None:
    with pytest.raises(ValidationError):
        CarryoverItem(
            event_type="earnings",
            ticker_or_topic="",
            originated_date=date(2026, 5, 6),
            status="resolved",
        )


def test_carryover_item_rejects_oversize_topic() -> None:
    with pytest.raises(ValidationError):
        CarryoverItem(
            event_type="other",
            ticker_or_topic="X" * 65,
            originated_date=date(2026, 5, 6),
            status="unresolved",
        )


def test_carryover_item_expected_date_optional() -> None:
    item = _item(expected_date=None, status="unresolved")
    assert item.expected_date is None


def test_briefing_carryover_is_empty_helper() -> None:
    empty = BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=0)
    assert empty.is_empty is True
    populated = BriefingCarryover(
        prior_resolved=(_item(),),
        prior_unresolved=(),
        lookback_days=1,
    )
    assert populated.is_empty is False


def test_briefing_carryover_clamps_lookback_days() -> None:
    # 8 > MAX_LOOKBACK_DAYS=7 — pydantic Field(le=7) rejects it.
    with pytest.raises(ValidationError):
        BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=8)
    # Negative is also out of range (ge=0).
    with pytest.raises(ValidationError):
        BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=-1)


def test_status_label_kr_covers_all_members() -> None:
    assert status_label_kr("resolved") == "확인됨"
    assert status_label_kr("unresolved") == "미확인"
    assert status_label_kr("carried_over") == "이월"
