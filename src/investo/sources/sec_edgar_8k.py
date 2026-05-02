"""SEC EDGAR 8-K filings Atom adapter — first compliance-header source.

Implements the algorithm from
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L6.6 and ``business-rules.md`` R14 (added 2026-05-01 — Extension #2).

Design choices (audit log 2026-05-01T04:00:00Z):

* **R14 source-mandated User-Agent**: SEC's fair-access policy
  (https://www.sec.gov/os/accessing-edgar-data) requires every request
  to carry a UA that identifies the requester (project + contact). A
  generic UA (default httpx, ``Mozilla/5.0``) is rate-limited or 403'd.
  The compliance string lives as ``SecEdgar8kAdapter._USER_AGENT`` —
  it is **not a secret** (it identifies us publicly), so it does not
  belong in :mod:`_config` (which is for R12 user overrides) or in any
  env var.
* **Atom 1.0 with default namespace**: ElementTree namespace-prefix
  syntax ``"{http://www.w3.org/2005/Atom}entry"`` is used everywhere;
  string-substitution namespace stripping is brittle to future Atom
  extensions (``media:content``, etc.) and is forbidden.
* **Bytes-not-text into the parser**: SEC declares
  ``<?xml version="1.0" encoding="ISO-8859-1" ?>`` on its Atom feed.
  Calling ``defusedxml.ElementTree.fromstring`` on ``response.content``
  (bytes) honours the declared encoding; ``response.text`` would
  pre-decode using HTTP-header heuristics and break the handshake.
* **Strict R7** — SEC publishes 8-Ks intraday on weekdays; weekends
  are empty by design, no R11 relaxation.
* **Accession-number extraction**: parsed from the HTML-stripped
  summary body via ``r"AccNo:\\s*(\\S+)"``. The Atom ``<id>`` element
  also carries the accession number canonically, but the summary
  regex is strictly simpler and the FD does not require canonical
  parsing — both yield the same string for every entry observed.
* **Item-code extraction**: ``r"Item \\d+\\.\\d+"`` against the same
  HTML-stripped summary body, joined comma-separated for
  ``raw_metadata.items`` (empty string when no items found —
  defensive; entry still emitted per L6.6 edge-case rule).

Pins NFR-007 ACs:

* AC-7.2 — title and summary HTML stripped via :mod:`_sanitize`
* AC-7.3 — items with non-http/https URLs are dropped (not stored)
* AC-7.4 — ``<updated>`` parsed to a tz-aware UTC datetime
* AC-7.6 — XML parsed via ``defusedxml`` (never stdlib ElementTree)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, ClassVar, Final
from urllib.parse import urlparse

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ATOM_NS: Final[str] = "{http://www.w3.org/2005/Atom}"

_TITLE_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^8-K\s*-\s*(?P<name>.+?)\s*\((?P<cik>\d+)\)\s*\(.+?\)\s*$"
)
_ITEM_CODE_REGEX: Final[re.Pattern[str]] = re.compile(r"Item \d+\.\d+")
_ACCESSION_REGEX: Final[re.Pattern[str]] = re.compile(r"AccNo:\s*(\S+)")

_ALLOWED_SCHEMES = ("http", "https")


@register
class SecEdgar8kAdapter:
    """Adapter for the SEC EDGAR 8-K Atom feed (FD L6.6, R14).

    Stateless per FD R3 — no per-call state and the shared
    :class:`httpx.AsyncClient` is injected by the aggregator.
    """

    name: ClassVar[str] = "sec-edgar-8k"
    category: ClassVar[Category] = "news"
    _FEED_URL: ClassVar[str] = (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
        "&type=8-K&company=&dateb=&owner=include&count=40&output=atom"
    )
    # R14 — fair-access compliance header. Public identifier of the
    # requester; NOT a secret. SEC documents the policy at
    # https://www.sec.gov/os/accessing-edgar-data — missing or generic
    # UA returns 403 / rate-limits the IP. Kept out of _config.py
    # because that module is for R12 user overrides.
    _USER_AGENT: ClassVar[str] = "investo investo@example.com"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        # R14: compliance UA on every request — passed via headers,
        # never inline-overridden on ``client.get``.
        response = await retry_get(
            client,
            self._FEED_URL,
            source_name=self.name,
            headers={"User-Agent": self._USER_AGENT},
        )
        # Bytes (response.content) — let the parser honour the declared
        # ISO-8859-1 encoding. Passing response.text would pre-decode
        # via HTTP-header guessing and break the handshake.
        try:
            root = fromstring(response.content)
        except ParseError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed XML: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        items: list[NormalizedItem] = []
        for entry in root.iter(f"{_ATOM_NS}entry"):
            normalized = self._normalize_entry(entry)
            if normalized is None:
                continue
            if window.contains(normalized.published_at):
                items.append(normalized)
        return items

    def _normalize_entry(self, entry: Any) -> NormalizedItem | None:
        # ``entry`` is an :class:`xml.etree.ElementTree.Element` returned
        # by the safe ``defusedxml`` parser. Typed ``Any`` to avoid
        # importing the stdlib XML module under ``src/investo/sources``
        # (NFR-007 AC-7.6 grep).
        title_raw = (entry.findtext(f"{_ATOM_NS}title") or "").strip()
        updated_raw = (entry.findtext(f"{_ATOM_NS}updated") or "").strip()

        # `<link rel="alternate" href="...">` — namespace-aware lookup.
        link_href: str | None = None
        for link_elem in entry.findall(f"{_ATOM_NS}link"):
            if link_elem.get("rel") == "alternate":
                href = link_elem.get("href")
                if href:
                    link_href = href.strip()
                    break

        if not title_raw or not updated_raw or not link_href:
            return None

        # AC-7.3: only http/https URLs accepted.
        if urlparse(link_href).scheme not in _ALLOWED_SCHEMES:
            return None

        # Title parse: extract company name + CIK from
        # ``"8-K - Company Name (0000320193) (Filer)"``. On regex miss,
        # drop the entry — defensive against schema changes.
        title_match = _TITLE_REGEX.match(title_raw)
        if title_match is None:
            return None
        company = title_match.group("name").strip()
        cik = title_match.group("cik")
        if not company or not cik:
            return None

        # AC-7.4: <updated> is ISO 8601 with offset (e.g.
        # ``"2026-04-30T17:30:48-04:00"``). ``datetime.fromisoformat``
        # handles offsets natively in 3.11+. Naive results (defensive
        # — SEC always emits an offset, but a future format slip
        # without offset would parse naive) are dropped.
        try:
            published = datetime.fromisoformat(updated_raw)
        except (TypeError, ValueError):
            return None
        if published.tzinfo is None:
            return None
        published_utc = published.astimezone(UTC)

        # Summary body — HTML-strip, then extract Item codes &
        # accession number via regex.
        summary_raw = entry.findtext(f"{_ATOM_NS}summary") or ""
        summary_text = strip_html(summary_raw)

        item_codes = _ITEM_CODE_REGEX.findall(summary_text)
        items_joined = ",".join(item_codes)

        accession_match = _ACCESSION_REGEX.search(summary_text)
        accession_no = accession_match.group(1) if accession_match else ""

        # Final shapes per L6.6 mapping.
        title = strip_html(f"8-K: {company} (CIK {cik})")
        if not title:
            return None
        summary: str | None = summary_text or None
        if summary and len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "accession_no": accession_no,
            "filer_cik": cik,
            "form_type": "8-K",
            "items": items_joined,
        }

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=link_href,
                published_at=published_utc,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            # Per-entry pydantic rejection (e.g. URL host issues that
            # passed the scheme guard but failed HttpUrl validation).
            return None
