"""Validated daily native exchange flows shared by collection and rendering."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext

_AMOUNT = re.compile(r"\d{1,30}(?:\.\d{1,30})?", re.ASCII)
_STATUSES = {"flash": "잠정", "reviewed": "검토됨", "revised": "수정됨"}


def utc_time(raw: object) -> datetime:
    """Parse an explicit UTC instant; never infer a timezone."""
    if not isinstance(raw, str) or len(raw) > 40:
        raise ValueError("invalid UTC timestamp")
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ExchangeFlow:
    asset: str
    day: date
    inflow: str
    outflow: str
    inflow_status: str
    outflow_status: str
    inflow_updated_at: datetime
    outflow_updated_at: datetime
    collected_at: datetime
    as_of: datetime

    def __post_init__(self) -> None:
        if self.asset not in {"btc", "eth"}:
            raise ValueError("unsupported asset")
        for value in (self.inflow, self.outflow):
            if not isinstance(value, str) or not _AMOUNT.fullmatch(value):
                raise ValueError("invalid native amount")
        if self.inflow_status not in _STATUSES or self.outflow_status not in _STATUSES:
            raise ValueError("unknown review status")
        for instant in (
            self.inflow_updated_at,
            self.outflow_updated_at,
            self.collected_at,
            self.as_of,
        ):
            if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
                raise ValueError("timestamp must be UTC")
        end = datetime.combine(self.day + timedelta(days=1), time.min, UTC)
        if not end <= self.inflow_updated_at <= self.as_of <= self.collected_at:
            raise ValueError("inflow not available at cutoff")
        if not end <= self.outflow_updated_at <= self.as_of:
            raise ValueError("outflow not available at cutoff")
        if not timedelta(0) <= self.as_of - end <= timedelta(days=3):
            raise ValueError("daily flow outside freshness bound")

    @property
    def netflow(self) -> str:
        # Inputs are <=30 integer +30 fractional digits. 64 preserves the
        # complete aligned subtraction regardless of ambient Decimal context.
        with localcontext() as context:
            context.prec = 64
            value = Decimal(self.inflow) - Decimal(self.outflow)
        if value.is_zero():
            return "0"
        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    @property
    def status_label(self) -> str:
        return f"유입 {_STATUSES[self.inflow_status]} / 유출 {_STATUSES[self.outflow_status]}"

    @property
    def available_at(self) -> datetime:
        return max(self.inflow_updated_at, self.outflow_updated_at)

    def metadata(self) -> dict[str, str]:
        return {
            "indicator": "exchange_flows",
            "asset": self.asset,
            "observation_date": self.day.isoformat(),
            "inflow_native": self.inflow,
            "outflow_native": self.outflow,
            "netflow_native": self.netflow,
            "inflow_status": self.inflow_status,
            "outflow_status": self.outflow_status,
            "inflow_updated_at": self.inflow_updated_at.isoformat(),
            "outflow_updated_at": self.outflow_updated_at.isoformat(),
            "collected_at": self.collected_at.isoformat(),
            "as_of": self.as_of.isoformat(),
        }

    @classmethod
    def from_metadata(cls, meta: Mapping[str, object]) -> ExchangeFlow:
        def field(key: str) -> str:
            value = meta.get(key)
            if not isinstance(value, str):
                raise ValueError("missing flow metadata")
            return value

        result = cls(
            asset=field("asset"),
            day=date.fromisoformat(field("observation_date")),
            inflow=field("inflow_native"),
            outflow=field("outflow_native"),
            inflow_status=field("inflow_status"),
            outflow_status=field("outflow_status"),
            inflow_updated_at=utc_time(field("inflow_updated_at")),
            outflow_updated_at=utc_time(field("outflow_updated_at")),
            collected_at=utc_time(field("collected_at")),
            as_of=utc_time(field("as_of")),
        )
        if result.netflow != field("netflow_native"):
            raise ValueError("netflow does not match inputs")
        return result
