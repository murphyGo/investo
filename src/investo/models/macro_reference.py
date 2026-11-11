"""Bounded reference observations; retrieval time is never a release timestamp."""

from __future__ import annotations

import calendar
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from investo.models.exchange_flows import utc_time

NEW_YORK = ZoneInfo("America/New_York")
MACRO_REFERENCES = {
    "treasury-tga-balance": (
        "TGA 잔액",
        "백만 USD",
        "https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/operating-cash-balance",
        10,
    ),
    "nyfed-gscpi": (
        "Global Supply Chain Pressure Index (GSCPI)",
        "표준편차",
        "https://www.newyorkfed.org/research/policy/gscpi",
        75,
    ),
    "ofr-financial-stress": (
        "OFR Financial Stress Index",
        "지수",
        "https://www.financialresearch.gov/financial-stress-index/",
        10,
    ),
}
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?", re.ASCII)


def macro_number(value: object, *, cash: bool = False) -> str:
    if not isinstance(value, str) or not _NUMBER.fullmatch(value):
        raise ValueError("invalid macro observation")
    number = Decimal(value)
    if cash:
        if not value.isascii() or not value.isdigit():
            raise ValueError("invalid cash balance")
    elif abs(number) > 100:
        raise ValueError("index outside supported bounds")
    return value


@dataclass(frozen=True, slots=True)
class MacroObservation:
    source_name: str
    observation_date: date
    value: str
    collected_at: datetime
    as_of: datetime
    release_vintage: str = ""

    def __post_init__(self) -> None:
        if self.source_name not in MACRO_REFERENCES:
            raise ValueError("unsupported macro reference")
        macro_number(self.value, cash=self.source_name == "treasury-tga-balance")
        if type(self.observation_date) is not date:
            raise ValueError("invalid observation date")
        for instant in (self.collected_at, self.as_of):
            if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
                raise ValueError("timestamp must be UTC")
        cutoff_day = self.as_of.astimezone(NEW_YORK).date()
        age = (cutoff_day - self.observation_date).days
        if self.as_of > self.collected_at or not 1 <= age <= MACRO_REFERENCES[self.source_name][3]:
            raise ValueError("observation outside freshness/cutoff bound")
        if self.source_name == "nyfed-gscpi":
            if not re.fullmatch(r"20[0-9]{2}-(?:0[1-9]|1[0-2])", self.release_vintage):
                raise ValueError("invalid release vintage")
            vintage = date.fromisoformat(self.release_vintage + "-01")
            day = self.observation_date
            if day.day != calendar.monthrange(day.year, day.month)[1]:
                raise ValueError("GSCPI observation must be month-end")
            if not day < vintage <= cutoff_day:
                raise ValueError("release vintage outside cutoff")
        elif self.release_vintage:
            raise ValueError("release vintage not supplied by source")

    @property
    def url(self) -> str:
        return MACRO_REFERENCES[self.source_name][2]

    def metadata(self) -> dict[str, str]:
        return {
            "indicator": "macro_reference",
            "reference_source": self.source_name,
            "observation_date": self.observation_date.isoformat(),
            "value": self.value,
            "unit": MACRO_REFERENCES[self.source_name][1],
            "collected_at": self.collected_at.isoformat(),
            "as_of": self.as_of.isoformat(),
            "release_vintage": self.release_vintage,
        }

    @classmethod
    def from_metadata(cls, meta: Mapping[str, object]) -> MacroObservation:
        def field(key: str) -> str:
            value = meta.get(key)
            if not isinstance(value, str) or len(value) > 80:
                raise ValueError("invalid macro metadata")
            return value

        if field("indicator") != "macro_reference":
            raise ValueError("invalid reference indicator")
        result = cls(
            source_name=field("reference_source"),
            observation_date=date.fromisoformat(field("observation_date")),
            value=field("value"),
            collected_at=utc_time(field("collected_at")),
            as_of=utc_time(field("as_of")),
            release_vintage=field("release_vintage"),
        )
        if field("unit") != MACRO_REFERENCES[result.source_name][1]:
            raise ValueError("unexpected macro unit")
        return result
