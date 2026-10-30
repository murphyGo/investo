"""Daily network counts; observation cutoff is not a historical data vintage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

from investo.models.exchange_flows import utc_time

ACTIVITY_METRICS = {"AdrActCnt": "활성 주소 수", "TxCnt": "거래 건수"}
_COUNT = re.compile(r"(?:0|[1-9][0-9]{0,17})", re.ASCII)


def activity_count(value: object) -> str:
    if not isinstance(value, str) or not _COUNT.fullmatch(value):
        raise ValueError("invalid network count")
    return value


@dataclass(frozen=True, slots=True)
class NetworkActivity:
    asset: str
    metric: str
    day: date
    value: str
    previous_seven: tuple[str, ...]
    collected_at: datetime
    as_of: datetime

    def __post_init__(self) -> None:
        if self.asset not in {"btc", "eth"} or self.metric not in ACTIVITY_METRICS:
            raise ValueError("unsupported network metric")
        activity_count(self.value)
        if not isinstance(self.previous_seven, tuple) or len(self.previous_seven) not in {0, 7}:
            raise ValueError("comparison requires seven complete daily counts")
        for value in self.previous_seven:
            activity_count(value)
        if type(self.day) is not date:
            raise ValueError("invalid observation day")
        for instant in (self.collected_at, self.as_of):
            if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
                raise ValueError("timestamp must be UTC")
        end = datetime.combine(self.day + timedelta(days=1), time.min, UTC)
        if not end <= self.as_of <= self.collected_at:
            raise ValueError("observation period not completed at cutoff")
        if self.as_of - end > timedelta(days=3):
            raise ValueError("network activity outside freshness bound")

    @property
    def previous_mean(self) -> str | None:
        if not self.previous_seven:
            return None
        with localcontext() as context:
            context.prec = 32
            mean = sum(Decimal(value) for value in self.previous_seven) / Decimal(7)
            return format(mean.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), ",.1f")

    def metadata(self) -> dict[str, str]:
        return {
            "indicator": "network_activity",
            "asset": self.asset,
            "metric": self.metric,
            "observation_date": self.day.isoformat(),
            "count": self.value,
            "previous_seven": ",".join(self.previous_seven),
            "collected_at": self.collected_at.isoformat(),
            "as_of": self.as_of.isoformat(),
        }

    @classmethod
    def from_metadata(cls, meta: Mapping[str, object]) -> NetworkActivity:
        def field(key: str) -> str:
            value = meta.get(key)
            if not isinstance(value, str) or len(value) > 140:
                raise ValueError("invalid activity metadata")
            return value

        if field("indicator") != "network_activity":
            raise ValueError("invalid activity indicator")
        previous = field("previous_seven")
        return cls(
            asset=field("asset"),
            metric=field("metric"),
            day=date.fromisoformat(field("observation_date")),
            value=field("count"),
            previous_seven=tuple(previous.split(",")) if previous else (),
            collected_at=utc_time(field("collected_at")),
            as_of=utc_time(field("as_of")),
        )
