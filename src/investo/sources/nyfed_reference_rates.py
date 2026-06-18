"""NY Fed reference-rates adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_NY = ZoneInfo("America/New_York")
_PUBLISH_TIME = time(8, 0)
_BASE_URL = "https://markets.newyorkfed.org/api/rates"
_RETRY_CONFIG = RetryConfig(timeout_s=10.0, retries=1, backoffs=(1.0,), total_budget_s=20.0)


@dataclass(frozen=True, slots=True)
class _RateConfig:
    code: str
    market: str
    label: str


_RATE_CONFIGS: tuple[_RateConfig, ...] = (
    _RateConfig("sofr", "secured", "SOFR"),
    _RateConfig("effr", "unsecured", "EFFR"),
    _RateConfig("obfr", "unsecured", "OBFR"),
    _RateConfig("bgcr", "secured", "BGCR"),
    _RateConfig("tgcr", "secured", "TGCR"),
)


@register
class NyfedReferenceRatesAdapter:
    """Adapter for NY Fed SOFR/EFFR/OBFR/BGCR/TGCR latest observations."""

    name: ClassVar[str] = "nyfed-reference-rates"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        return await gather_with_error_isolation(
            (self._fetch_one(client, config, window) for config in _RATE_CONFIGS),
            source_name=self.name,
        )

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        config: _RateConfig,
        window: FetchWindow,
    ) -> NormalizedItem | None:
        url = f"{_BASE_URL}/{config.market}/{config.code}/last/1.json"
        response = await retry_get(
            client,
            url,
            source_name=self.name,
            config=_RETRY_CONFIG,
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed NY Fed JSON for {config.label}",
        )
        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"non-object NY Fed response for {config.label}",
                transient=False,
            )
        rows = payload.get("refRates")
        if not isinstance(rows, list) or not rows:
            raise SourceFetchError(
                source_name=self.name,
                message=f"empty NY Fed rates for {config.label}",
                transient=False,
            )
        row = rows[0]
        if not isinstance(row, dict):
            return None
        try:
            return _row_to_item(
                row, config=config, source_name=self.name, target_date=window.target_date
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            return None


def _row_to_item(
    row: dict[str, Any],
    *,
    config: _RateConfig,
    source_name: str,
    target_date: date,
) -> NormalizedItem:
    effective_date = date.fromisoformat(str(row["effectiveDate"]))
    if effective_date > target_date:
        raise ValueError("NY Fed rate is after target date")
    rate = float(row["percentRate"])
    volume = float(row["volumeInBillions"])
    published_at = datetime.combine(effective_date, _PUBLISH_TIME, tzinfo=_NY).astimezone(UTC)
    title = f"NY Fed {config.label} {effective_date.isoformat()}: {rate:.2f}%"
    summary = (
        f"{config.label}: {rate:.2f}% on ${volume:.0f}B volume; official NY Fed reference rate"
    )
    metadata = {
        "rate_code": config.label,
        "effective_date": effective_date.isoformat(),
        "as_of_date": effective_date.isoformat(),
        "percent_rate": format_float(rate),
        "volume_billions_usd": format_float(volume),
        "units": "percent; USD billions",
        "source_lag_days": str((target_date - effective_date).days),
        "data_frequency": "daily",
        "delayed_data_label": "official reference rate, published after the effective date",
    }
    for source_key, metadata_key in (
        ("percentPercentile1", "percentile_1"),
        ("percentPercentile25", "percentile_25"),
        ("percentPercentile75", "percentile_75"),
        ("percentPercentile99", "percentile_99"),
        ("targetRateFrom", "target_rate_from"),
        ("targetRateTo", "target_rate_to"),
    ):
        value = row.get(source_key)
        if value not in (None, ""):
            metadata[metadata_key] = format_float(float(str(value)))
    revision = str(row.get("revisionIndicator") or "").strip()
    if revision:
        metadata["revision_indicator"] = revision
    return NormalizedItem(
        source_name=source_name,
        category="macro",
        title=title,
        summary=summary,
        url=f"{_BASE_URL}/{config.market}/{config.code}",
        published_at=published_at,
        raw_metadata=metadata,
    )
