"""Fiscal Service DTS Table I: validated daily TGA closing cash balance."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.models.macro_reference import NEW_YORK, MacroObservation, macro_number
from investo.sources._macro_reference import reference_cutoff, reference_item, reference_json
from investo.sources._registry import register
from investo.sources._retry import RetryConfig, retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

ENDPOINT = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v1/accounting/dts/operating_cash_balance"
)
ACCOUNTS = (
    "Treasury General Account (TGA) Opening Balance",
    "Total TGA Deposits (Table II)",
    "Total TGA Withdrawals (Table II) (-)",
    "Treasury General Account (TGA) Closing Balance",
)


@register
class TreasuryTgaBalanceAdapter:
    name: ClassVar[str] = "treasury-tga-balance"
    category: ClassVar[Category] = "macro"

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        as_of = reference_cutoff(window)
        last_day = as_of.astimezone(NEW_YORK).date() - timedelta(days=1)
        response = await retry_get(
            client,
            ENDPOINT,
            source_name=self.name,
            params={
                "sort": "-record_date",
                "page[size]": "32",
                "filter": f"record_date:lte:{last_day}",
            },
            headers={"User-Agent": "Investo/1.0 (+https://murphygo.github.io/investo)"},
            config=RetryConfig(retries=1, total_budget_s=30, max_response_bytes=64 * 1024),
        )
        payload = reference_json(response, self.name)
        try:
            if not isinstance(payload, dict):
                raise ValueError("invalid object")
            rows, meta = payload["data"], payload["meta"]
            if not isinstance(rows, list) or len(rows) > 32:
                raise ValueError("row cap")
            if (
                meta["dataTypes"]["open_today_bal"] != "CURRENCY0"
                or meta["dataFormats"]["open_today_bal"] != "$1,000,000"
            ):
                raise ValueError("unit changed")
            dated = [(date.fromisoformat(row["record_date"]), row) for row in rows]
            days = [day for day, _ in dated if day <= last_day]
            if not days or (last_day - max(days)).days >= 10:
                return []
            latest = max(days)
            values: dict[str, str] = {}
            for day, row in dated:
                if day != latest or row.get("account_type") not in ACCOUNTS:
                    continue
                if row.get("table_nbr") != "I":
                    raise ValueError("unexpected table")
                account = row["account_type"]
                value = macro_number(row.get("open_today_bal"), cash=True)
                if account in values and values[account] != value:
                    raise ValueError("conflicting account")
                values[account] = value
            opening, deposits, withdrawals, closing = (int(values[key]) for key in ACCOUNTS)
            if opening + deposits - withdrawals != closing:
                raise ValueError("inconsistent cash balance")
            observation = MacroObservation(
                self.name, latest, str(closing), datetime.now(UTC), as_of
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise SourceFetchError(
                self.name, "invalid TGA balance schema", transient=False
            ) from exc
        return [reference_item(observation)]
