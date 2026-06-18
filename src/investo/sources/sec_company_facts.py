"""Bounded SEC submissions/companyfacts adapter for watchlist companies."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_USER_AGENT: Final[str] = "investo investo@example.com"
_ENV_COMPANIES: Final[str] = "INVESTO_SEC_COMPANY_CIKS"
_MAX_COMPANIES: Final[int] = 8
_ADAPTER_TOTAL_BUDGET_SECONDS: Final[float] = 20.0
_SEC_REQUEST_SPACING_SECONDS: Final[float] = 0.12
_LOGGER = logging.getLogger(__name__)
_DEFAULT_COMPANIES: Final[tuple[tuple[str, str], ...]] = (
    ("AAPL", "0000320193"),
    ("MSFT", "0000789019"),
    ("GOOGL", "0001652044"),
    ("META", "0001326801"),
    ("AMZN", "0001018724"),
    ("NVDA", "0001045810"),
    ("TSLA", "0001318605"),
)
_CONCEPTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("us-gaap", "Revenues", "revenue"),
    ("us-gaap", "NetIncomeLoss", "net_income"),
    ("us-gaap", "EarningsPerShareDiluted", "diluted_eps"),
    ("us-gaap", "Assets", "assets"),
    ("us-gaap", "Liabilities", "liabilities"),
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "operating_cash_flow"),
    ("dei", "EntityCommonStockSharesOutstanding", "shares_outstanding"),
)


@register
class SecCompanyFactsAdapter:
    """Adapter for bounded SEC company submissions and XBRL companyfacts."""

    name: ClassVar[str] = "sec-company-facts"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        try:
            return await asyncio.wait_for(
                self._fetch_companies(client, window),
                timeout=_ADAPTER_TOTAL_BUDGET_SECONDS,
            )
        except TimeoutError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"exceeded {_ADAPTER_TOTAL_BUDGET_SECONDS:g}s adapter budget",
                transient=True,
                cause=exc,
            ) from exc

    async def _fetch_companies(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        items: list[NormalizedItem] = []
        failures: list[SourceFetchError] = []
        request_started = False
        for ticker, cik in _configured_companies():
            try:
                if request_started:
                    await _sleep_between_sec_requests()
                request_started = True
                submission = await _get_json(
                    client,
                    f"https://data.sec.gov/submissions/CIK{cik}.json",
                    source_name=self.name,
                )
                await _sleep_between_sec_requests()
                facts = await _get_json(
                    client,
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                    source_name=self.name,
                )
            except SourceFetchError as exc:
                failures.append(exc)
                _LOGGER.warning(
                    "sec-company-facts company fetch failed ticker=%s cik=%s transient=%s",
                    ticker,
                    cik,
                    exc.transient,
                )
                continue
            item = self._normalize_company(
                ticker=ticker,
                cik=cik,
                submission=submission,
                facts=facts,
                published_at=window.start_utc,
            )
            if item is not None:
                items.append(item)
        if not items and failures:
            raise failures[0]
        return items

    def _normalize_company(
        self,
        *,
        ticker: str,
        cik: str,
        submission: Any,
        facts: Any,
        published_at: datetime,
    ) -> NormalizedItem | None:
        if not isinstance(submission, dict) or not isinstance(facts, dict):
            return None
        name = _clean_str(submission.get("name")) or ticker
        exchange = _first_str(submission.get("exchanges"))
        sic = _clean_str(submission.get("sic"))
        sic_description = _clean_str(submission.get("sicDescription"))
        latest_form, latest_filing_date = _latest_filing(submission)
        concept_values = _latest_concepts(facts)

        summary_parts: list[str] = []
        if exchange:
            summary_parts.append(f"exchange={exchange}")
        if latest_form and latest_filing_date:
            summary_parts.append(f"latest_filing={latest_form} {latest_filing_date}")
        summary_parts.extend(f"{key}={value}" for key, value in concept_values)
        summary = "; ".join(summary_parts) or None

        raw_metadata: dict[str, str] = {
            "ticker": ticker,
            "cik": cik,
            "official_source": "true",
        }
        if exchange:
            raw_metadata["exchange"] = exchange
        if sic:
            raw_metadata["sic"] = sic
        if sic_description:
            raw_metadata["sic_description"] = sic_description
        if latest_form:
            raw_metadata["latest_form"] = latest_form
        if latest_filing_date:
            raw_metadata["latest_filing_date"] = latest_filing_date

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=f"{ticker} SEC company facts: {name}",
                summary=summary,
                url=f"https://data.sec.gov/submissions/CIK{cik}.json",
                published_at=published_at.astimezone(UTC),
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


async def _get_json(client: httpx.AsyncClient, url: str, *, source_name: str) -> Any:
    response = await retry_get(
        client,
        url,
        source_name=source_name,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    return parse_json_response(response, source_name=source_name)


async def _sleep_between_sec_requests() -> None:
    if _SEC_REQUEST_SPACING_SECONDS > 0:
        await asyncio.sleep(_SEC_REQUEST_SPACING_SECONDS)


def _configured_companies() -> tuple[tuple[str, str], ...]:
    raw = os.environ.get(_ENV_COMPANIES, "").strip()
    if not raw:
        return _DEFAULT_COMPANIES[:_MAX_COMPANIES]
    companies: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        if ":" not in chunk:
            continue
        ticker_raw, cik_raw = chunk.split(":", 1)
        ticker = ticker_raw.strip().upper()
        cik_digits = "".join(ch for ch in cik_raw if ch.isdigit())
        if ticker and cik_digits:
            companies.append((ticker, cik_digits.zfill(10)))
    return tuple(companies[:_MAX_COMPANIES]) or _DEFAULT_COMPANIES[:_MAX_COMPANIES]


def _clean_str(value: Any) -> str:
    return strip_html(str(value or "")).strip()


def _first_str(value: Any) -> str:
    if isinstance(value, list) and value:
        return _clean_str(value[0])
    return _clean_str(value)


def _latest_filing(submission: dict[str, Any]) -> tuple[str, str]:
    recent = submission.get("filings", {}).get("recent")
    if not isinstance(recent, dict):
        return "", ""
    forms = recent.get("form")
    dates = recent.get("filingDate")
    if not isinstance(forms, list) or not isinstance(dates, list):
        return "", ""
    for form, filing_date in zip(forms, dates, strict=False):
        form_text = _clean_str(form)
        date_text = _clean_str(filing_date)
        if form_text and date_text:
            return form_text, date_text
    return "", ""


def _latest_concepts(facts: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    facts_by_taxonomy = facts.get("facts")
    if not isinstance(facts_by_taxonomy, dict):
        return ()
    values: list[tuple[str, str]] = []
    for taxonomy, concept, label in _CONCEPTS:
        taxonomy_obj = facts_by_taxonomy.get(taxonomy)
        if not isinstance(taxonomy_obj, dict):
            continue
        concept_obj = taxonomy_obj.get(concept)
        if not isinstance(concept_obj, dict):
            continue
        latest = _latest_unit_value(concept_obj.get("units"))
        if latest:
            values.append((label, latest))
    return tuple(values[: len(_CONCEPTS)])


def _latest_unit_value(units: Any) -> str:
    if not isinstance(units, dict):
        return ""
    candidates: list[dict[str, Any]] = []
    for entries in units.values():
        if isinstance(entries, list):
            candidates.extend(entry for entry in entries if isinstance(entry, dict))
    candidates.sort(
        key=lambda entry: str(entry.get("filed") or entry.get("end") or ""),
        reverse=True,
    )
    for entry in candidates:
        value = entry.get("val")
        end = _clean_str(entry.get("end"))
        if value is not None:
            return f"{value} ({end})" if end else str(value)
    return ""
