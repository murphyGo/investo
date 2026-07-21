"""U144 sealed public-notification DTO contract tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from investo.models import PublicNotificationSummary
from investo.models.segments import DOMESTIC_EQUITY

_TARGET_DATE = date(2026, 7, 21)


def _summary(**updates: object) -> PublicNotificationSummary:
    values: dict[str, object] = {
        "segment": DOMESTIC_EQUITY,
        "target_date": _TARGET_DATE,
        "conclusion": "[관망] 확인된 결론",
        "coverage_status": "normal",
        "coverage_label": "정상",
        "watchlist": None,
    }
    values.update(updates)
    return PublicNotificationSummary(**values)  # type: ignore[arg-type]


def test_public_notification_summary_exports_closed_sealed_shape() -> None:
    summary = _summary(watchlist="AAPL: 실적 일정 확인")

    assert summary.segment == DOMESTIC_EQUITY
    assert summary.target_date == _TARGET_DATE
    assert summary.coverage_status == "normal"
    assert summary.coverage_label == "정상"
    assert summary.watchlist == "AAPL: 실적 일정 확인"


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"segment": "unknown"}, "known market segment"),
        ({"target_date": datetime(2026, 7, 21, tzinfo=UTC)}, "target_date must be date"),
        ({"conclusion": ""}, "non-empty cleaned single line"),
        ({"conclusion": " 트림 금지"}, "non-empty cleaned single line"),
        ({"conclusion": "첫 줄\n둘째 줄"}, "non-empty cleaned single line"),
        ({"coverage_status": "unknown"}, "known status"),
        ({"coverage_label": "부분"}, "must match coverage_status"),
        ({"watchlist": ""}, "non-empty cleaned single line"),
        ({"watchlist": "AAPL\nBTC"}, "non-empty cleaned single line"),
    ),
)
def test_public_notification_summary_rejects_incoherent_shared_values(
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        _summary(**updates)
