"""Treasury auction calendar adapter — forward-looking coupon auction schedule.

Consumes the U.S. Treasury **Fiscal Data** "Upcoming Treasury Auctions"
dataset and emits one :class:`NormalizedItem` per scheduled *coupon*
auction whose ``auction_date`` falls inside the adapter's forward
lookahead window. Complements the two sibling lookahead adapters:
``fomc-calendar`` (policy decisions) and ``fred-economic-calendar``
(macro data prints). Auctions are the third leg of the U.S. rates
calendar — a weak 10-year or 30-year auction moves yields, and yields
move equities — so the "주요 일정" block reads more completely with
them present.

Distinct from the existing ``treasury-rates`` adapter, which consumes
the *backward-looking* daily yield-curve XML; that one publishes what
rates *did*, this one publishes which auctions are *about to price*.

Design choices (DEBT-067 phase A, 2026-07-19):

* **Endpoint / host choice** — ``api.fiscaldata.treasury.gov`` serves
  the dataset as unauthenticated JSON with a documented, typed schema
  (the response carries its own ``meta.dataTypes`` /
  ``meta.dataFormats`` contract). The same auction data is also served
  by ``www.treasurydirect.gov/TA_WS/securities/upcoming``, which is
  richer and fresher — but that host's ``robots.txt`` is a blanket
  ``User-agent: * / Disallow: /`` (verified live 2026-07-19), so it was
  rejected on crawl-permissiveness grounds. ``fiscaldata.treasury.gov``
  serves ``User-agent: * / Allow: /``. When the two disagree, we take
  the permissive host even at a data-quality cost.

* **Coupon-only filter** — the dataset is dominated by short bills
  (63 of 100 rows in the recorded snapshot are ``Bill``, plus 10
  ``CMB``). Bill auctions are routine cash management and effectively
  never move the market narrative; surfacing them would flood the
  briefing's 12-row lookahead sub-cap with noise and crowd out FOMC /
  CPI rows. The adapter therefore keeps only coupon-bearing types
  (``Note`` / ``Bond`` / ``TIPS Note`` / ``TIPS Bond`` / ``FRN Note``)
  by default. The list is operator-overridable via
  ``INVESTO_TREASURY_AUCTION_TYPES`` (R12) for anyone who does want the
  bill tape.

* **Forward-only** — the dataset is an accumulating archive rather than
  a rolling window (the recorded snapshot spans 2024-03 .. 2026-07 with
  gaps), so a forward filter is mandatory, not cosmetic. The adapter
  applies ``[target_date, target_date + N)`` against ``auction_date``.
  ``N`` comes from ``INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS`` (default
  30, clamped to ``[1, 180]``), mirroring ``fomc-calendar``.

  Because the upstream refresh cadence is visibly irregular, a stalled
  publisher yields zero forward rows rather than stale ones — the
  adapter degrades to empty, which is the NFR-003 behaviour we want.

* **Dedupe** — the archive can carry the same auction under more than
  one ``record_date`` snapshot (e.g. an initial announcement and a
  later revision). Rows are deduplicated on
  ``(cusip, auction_date)``, keeping the row with the most recent
  ``record_date`` so the freshest ``offering_amt`` wins.

* **scheduled_at** — UTC midnight on ``auction_date``. The dataset
  carries no auction *time* field (bidding closes at 11:30 / 13:00 ET
  depending on the security, but that is not in the payload), so the
  adapter keeps date-level granularity rather than inventing a
  wall-clock. This matches ``fomc-calendar``.

* **published_at** — UTC midnight on the *target date*, matching
  ``fomc-calendar`` / ``fred-economic-calendar`` /
  ``nasdaq-earnings-calendar`` so forward rows stay attached to the
  publish slice that emitted them instead of drifting forward.

* **offering_amt is nullable** — newly announced auctions carry the
  string sentinel ``"null"`` (not JSON ``null``) because the offering
  size is published in a later announcement. The adapter treats both
  the sentinel and a genuine ``None`` as "amount not yet announced" and
  omits the amount from the summary rather than rendering ``$null``.

* **Tier A** — Treasury is the issuer-of-record, but the Fiscal Data
  mirror lags the TreasuryDirect announcement wire by a day or two and
  its refresh cadence is irregular (see above), so it does not earn the
  tier ``S`` reserved for primary real-time regulator feeds.

* **Segment routing** — single-segment ``us-equity``. Auction supply is
  a U.S. rates story; crypto readers inherit rate context through the
  existing shared-source path rather than through per-auction rows.

* **No secrets** — the endpoint is unauthenticated. R13 is trivially
  satisfied: there is no env var to redact and no key in the URL.

* **R14 UA** — Fiscal Data advertises no strict UA policy; the adapter
  sends the project identity string per the R14 fair-access convention.

Pins:

* AC-7.4 — ``scheduled_at`` and ``published_at`` are tz-aware UTC.
* AC-7.6 — JSON path; no XML parsing, ``defusedxml`` not required.
* R7 (relaxed forward window per u35) — emits forward-scheduled rows
  outside the strict 24-hour publish window, kept compatible with the
  aggregator's ``_MAX_FUTURE_PUBLISHED_AT`` guard by the
  ``published_at = target_date midnight`` anchor.
* R10 — live recordings under
  ``tests/unit/sources/fixtures/api/treasury-auctions/`` (body +
  provenance ``meta.json`` with sha256), replayed via
  ``httpx.MockTransport``.
* R12 — ``INVESTO_TREASURY_AUCTION_TYPES`` +
  ``INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS`` overrides.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar, Final

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, parse_symbol_list
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

_ENV_LOOKAHEAD_DAYS: Final[str] = "INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS"
_DEFAULT_LOOKAHEAD_DAYS: Final[int] = 30
_LOOKAHEAD_MIN_DAYS: Final[int] = 1
_LOOKAHEAD_MAX_DAYS: Final[int] = 180

# R12 — operator override for which security types to surface. Defaults
# to coupon-bearing issues only; see the module docstring for why bills
# and CMBs are excluded.
_ENV_AUCTION_TYPES: Final[str] = "INVESTO_TREASURY_AUCTION_TYPES"
_DEFAULT_AUCTION_TYPES: Final[tuple[str, ...]] = (
    "NOTE",
    "BOND",
    "TIPS NOTE",
    "TIPS BOND",
    "FRN NOTE",
)

_USER_AGENT: Final[str] = "Investo/1.0 (+https://murphygo.github.io/investo)"

# Upstream sentinel for "offering size not yet announced". The dataset
# serialises it as the four-character string ``null``, not JSON null.
_NULL_SENTINEL: Final[str] = "null"

_LANDING_PAGE: Final[str] = (
    "https://fiscaldata.treasury.gov/datasets/upcoming-auctions/upcoming-auctions"
)


@register
class TreasuryAuctionsAdapter:
    """Adapter for the Treasury Fiscal Data upcoming-auctions dataset."""

    name: ClassVar[str] = "treasury-auctions"
    category: ClassVar[Category] = "calendar"

    _ENDPOINT: ClassVar[str] = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
        "/v1/accounting/od/upcoming_auctions"
    )
    # Sorted newest-auction-first so that, if the archive ever outgrows
    # the page size, the rows we lose are the oldest ones — which the
    # forward filter would have discarded anyway.
    _PARAMS: ClassVar[dict[str, str]] = {"sort": "-auction_date", "page[size]": "500"}

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params=dict(self._PARAMS),
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json, */*",
            },
        )
        try:
            payload = json.loads(response.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected object response, got {type(payload).__name__}",
                transient=False,
            )
        rows = payload.get("data")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected data list, got {type(rows).__name__}",
                transient=False,
            )

        keep_types = _resolve_auction_types()
        lookahead_days = _resolve_lookahead_days()
        target_published_at = datetime.combine(window.target_date, time.min, tzinfo=UTC)
        forward_end = window.target_date + timedelta(days=lookahead_days)

        # (cusip, auction_date) -> (record_date_sort_key, row). The
        # archive may hold several snapshots of the same auction; keep
        # the freshest so the newest offering_amt wins.
        deduped: dict[tuple[str, date], tuple[str, dict[str, Any]]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            security_type = _clean_str(row.get("security_type"))
            if not security_type or security_type.upper() not in keep_types:
                continue
            auction_date = _parse_date(_clean_str(row.get("auction_date")))
            if auction_date is None:
                continue
            if not (window.target_date <= auction_date < forward_end):
                continue
            cusip = _clean_str(row.get("cusip")) or ""
            record_date = _clean_str(row.get("record_date")) or ""
            key = (cusip, auction_date)
            existing = deduped.get(key)
            if existing is None or record_date >= existing[0]:
                deduped[key] = (record_date, row)

        items: list[NormalizedItem] = []
        for (_, auction_date), (_, row) in sorted(
            deduped.items(), key=lambda entry: (entry[0][1], entry[0][0])
        ):
            normalized = self._normalize_row(
                row,
                auction_date=auction_date,
                target_published_at=target_published_at,
            )
            if normalized is not None:
                items.append(normalized)
        return items

    def _normalize_row(
        self,
        row: dict[str, Any],
        *,
        auction_date: date,
        target_published_at: datetime,
    ) -> NormalizedItem | None:
        security_type = _clean_str(row.get("security_type"))
        if not security_type:
            return None
        security_term = _clean_str(row.get("security_term"))
        cusip = _clean_str(row.get("cusip"))
        reopening = _clean_str(row.get("reopening"))
        offering_amt = _clean_amount(row.get("offering_amt"))
        issue_date = _clean_str(row.get("issue_date"))
        announcement_date = _clean_str(row.get("announcemt_date"))

        descriptor = f"{security_term} {security_type}" if security_term else security_type
        title = f"{auction_date.isoformat()} — U.S. Treasury {descriptor} Auction"

        summary_parts: list[str] = [f"Treasury auction: {descriptor}."]
        if offering_amt is not None:
            summary_parts.append(f"Offering amount: ${offering_amt:,}.")
        else:
            summary_parts.append("Offering amount: not yet announced.")
        if reopening:
            summary_parts.append(f"Reopening: {reopening}.")
        if issue_date:
            summary_parts.append(f"Issue date: {issue_date}.")
        summary = " ".join(summary_parts)
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "security_type": security_type,
            "auction_date": auction_date.isoformat(),
        }
        if security_term:
            raw_metadata["security_term"] = security_term
        if cusip:
            raw_metadata["cusip"] = cusip
        if reopening:
            raw_metadata["reopening"] = reopening
        if offering_amt is not None:
            raw_metadata["offering_amt"] = str(offering_amt)
        if issue_date:
            raw_metadata["issue_date"] = issue_date
        if announcement_date:
            raw_metadata["announcement_date"] = announcement_date

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=_LANDING_PAGE,
                published_at=target_published_at,
                scheduled_at=datetime.combine(auction_date, time.min, tzinfo=UTC),
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _resolve_auction_types() -> frozenset[str]:
    """Read ``INVESTO_TREASURY_AUCTION_TYPES``, upper-cased for matching.

    Falls back to the coupon-only default when unset / blank. Values are
    compared case-insensitively against the dataset's ``security_type``.
    """
    return frozenset(
        value.upper() for value in parse_symbol_list(_ENV_AUCTION_TYPES, _DEFAULT_AUCTION_TYPES)
    )


def _resolve_lookahead_days() -> int:
    """Read ``INVESTO_TREASURY_AUCTION_LOOKAHEAD_DAYS`` and clamp to range.

    Default ``_DEFAULT_LOOKAHEAD_DAYS`` (30) when unset / blank /
    non-numeric / below the minimum; clamped down to
    ``_LOOKAHEAD_MAX_DAYS`` when too large. Every fallback logs one
    warning so an operator typo surfaces in the GHA log.
    """
    raw = os.environ.get(_ENV_LOOKAHEAD_DAYS, "").strip()
    if not raw:
        return _DEFAULT_LOOKAHEAD_DAYS
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "%s=%r invalid (non-numeric); using default=%d",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _DEFAULT_LOOKAHEAD_DAYS,
        )
        return _DEFAULT_LOOKAHEAD_DAYS
    if value < _LOOKAHEAD_MIN_DAYS:
        _logger.warning(
            "%s=%r below min=%d; using default=%d",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _LOOKAHEAD_MIN_DAYS,
            _DEFAULT_LOOKAHEAD_DAYS,
        )
        return _DEFAULT_LOOKAHEAD_DAYS
    if value > _LOOKAHEAD_MAX_DAYS:
        _logger.warning(
            "%s=%r above max=%d; clamping",
            _ENV_LOOKAHEAD_DAYS,
            raw,
            _LOOKAHEAD_MAX_DAYS,
        )
        return _LOOKAHEAD_MAX_DAYS
    return value


def _clean_str(value: Any) -> str | None:
    """Strip + HTML-strip a Fiscal Data field, ``None`` on empty."""
    if not isinstance(value, str):
        return None
    cleaned = strip_html(value).strip()
    return cleaned or None


def _clean_amount(value: Any) -> int | None:
    """Parse ``offering_amt``, treating the ``"null"`` sentinel as unset."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text == _NULL_SENTINEL:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_date(text: str | None) -> date | None:
    """Parse a Fiscal Data ``YYYY-MM-DD`` field, ``None`` when malformed."""
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
