"""Preview-only, bounded discovery before the general DART item cutoff.

FR-001/u173: this adapter is deliberately not registered. Its coverage is
for B001 major reports and the explicitly selected parser, not all DART.
Body qualification remains the responsibility of shared DART preparation.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx

from investo.models import NormalizedItem
from investo.models.coverage import SourceFetchResult, SourceWindowCoverage
from investo.models.enrichment import DartParserVersion
from investo.sources._dart_document import MAX_BYTES
from investo.sources._dart_evidence import (
    DART_PARSER_VERSIONS,
    DartRequestError,
    _unique_object,
    dart_identity,
)
from investo.sources._window import FetchWindow
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.protocol import SourceFetchError


class DartDiscoveryAdapter(DartDisclosureAdapter):
    """One-run replacement; never mutate the singleton production adapter."""

    query_scope = "B001:selected_parser"
    _REQUEST_TIMEOUT_S = 8.0

    def __init__(
        self,
        parser_version: DartParserVersion,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if parser_version not in DART_PARSER_VERSIONS:
            raise ValueError("unsupported DART discovery parser")
        self.parser_version = parser_version
        self._transport = transport

    async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]:
        return list((await self.fetch_with_coverage(client, window)).items)

    async def fetch_with_coverage(
        self, client: httpx.AsyncClient, window: FetchWindow
    ) -> SourceFetchResult:
        # Own a fixed-host client so the general collector's environment and
        # redirect policy cannot route credential-bearing discovery requests.
        token = os.environ.get("OPENDART_API_KEY", "").strip()
        if not token:
            raise self._error("missing_key")
        expected_window = FetchWindow.from_kst_date(window.target_date)
        if (
            window.news_observation
            or window.start_utc != expected_window.start_utc
            or window.end_utc != expected_window.end_utc
        ):
            raise self._error("invalid_window")
        bounds = self._window_to_yyyymmdd(window)
        items: list[NormalizedItem] = []
        seen: set[str] = set()
        totals: tuple[int, int] | None = None
        pages = failures = 0
        capped = complete = False
        try:
            async with asyncio.timeout(self._WINDOW_BUDGET_S):
                async with httpx.AsyncClient(
                    transport=self._transport, follow_redirects=False, trust_env=False
                ) as discovery_client:
                    for page in range(1, self._MAX_PAGES + 1):
                        payload = await self._page(discovery_client, token, bounds, page)
                        pages += 1
                        if payload.get("status") == "013":
                            if (
                                page != 1
                                or payload.get("list") not in (None, [])
                                or any(
                                    key in payload
                                    and not (
                                        (type(payload[key]) is int and payload[key] == 0)
                                        or (type(payload[key]) is str and payload[key] == "0")
                                    )
                                    for key in ("total_count", "total_page")
                                )
                            ):
                                raise self._error("invalid_empty")
                            complete = True
                            break
                        if any(
                            type(payload.get(key)) not in (int, str)
                            or re.fullmatch(r"[0-9]{1,6}", str(payload[key])) is None
                            for key in ("page_no", "page_count", "total_count", "total_page")
                        ):
                            raise self._error("invalid_pagination")
                        current = self._pagination(payload, page)
                        entries = payload.get("list")
                        if (
                            current is None
                            or (totals is not None and totals != current)
                            or not isinstance(entries, list)
                            or len(entries)
                            != min(self._PAGE_COUNT, current[0] - (page - 1) * self._PAGE_COUNT)
                        ):
                            raise self._error("invalid_pagination")
                        page_ids: set[str] = set()
                        page_items: list[NormalizedItem] = []
                        # Validate the entire page before accepting any of it.
                        for entry in entries:
                            if (
                                not self._well_formed_entry(entry)
                                or re.fullmatch(r"[0-9]{14}", entry["rcept_no"]) is None
                                or re.fullmatch(r"[0-9]{8}", entry["corp_code"]) is None
                                or entry["corp_cls"] not in {"Y", "K", "N", "E"}
                                or not bounds[0] <= entry["rcept_dt"] <= bounds[1]
                                or entry["rcept_no"] in seen | page_ids
                            ):
                                raise self._error("invalid_entries")
                            page_ids.add(entry["rcept_no"])
                            item = self._normalize_entry(entry, date_precision=True)
                            if item is None:
                                if entry["corp_cls"] != "E" and self._classify(entry["report_nm"]):
                                    raise self._error("invalid_entries")
                                continue
                            try:
                                dart_identity(item, self.parser_version)
                            except DartRequestError:
                                continue
                            page_items.append(item)
                        totals = current
                        seen.update(page_ids)
                        items.extend(page_items)
                        if len(items) > self._MAX_ITEMS:
                            capped = True
                            break
                        if page == current[1]:
                            complete = len(seen) == current[0]
                            break
                        if page == self._MAX_PAGES:
                            capped = True
        except (SourceFetchError, TimeoutError) as exc:
            if not seen and not items:
                if isinstance(exc, SourceFetchError):
                    raise
                raise self._error("timeout", transient=True) from None
            failures += 1
        items.sort(key=lambda item: item.raw_metadata["rcept_no"], reverse=True)
        return SourceFetchResult(
            tuple(items[: self._MAX_ITEMS]),
            SourceWindowCoverage(
                self.name,
                window.start_utc,
                window.end_utc,
                pages=pages,
                cap_reached=capped,
                parse_failures=failures,
                completeness="full" if complete and not capped and not failures else "partial",
                basis="provider_pagination",
            ),
        )

    async def _page(
        self, client: httpx.AsyncClient, token: str, bounds: tuple[str, str], page: int
    ) -> dict[str, Any]:
        data = bytearray()
        try:
            async with asyncio.timeout(self._REQUEST_TIMEOUT_S):
                async with client.stream(
                    "GET",
                    self._ENDPOINT,
                    params={
                        "crtfc_key": token,
                        "bgn_de": bounds[0],
                        "end_de": bounds[1],
                        "pblntf_detail_ty": "B001",
                        "last_reprt_at": "N",
                        "sort": "date",
                        "sort_mth": "desc",
                        "page_no": str(page),
                        "page_count": str(self._PAGE_COUNT),
                    },
                    headers={"Accept-Encoding": "identity"},
                    timeout=self._REQUEST_TIMEOUT_S,
                ) as response:
                    if response.status_code != 200:
                        raise self._error("http_status", transient=response.status_code >= 500)
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise self._error("encoding")
                    async for chunk in response.aiter_bytes():
                        if len(chunk) > MAX_BYTES - len(data):
                            raise self._error("response_size")
                        data.extend(chunk)
        except (httpx.HTTPError, TimeoutError):
            raise self._error("transport", transient=True) from None
        try:
            payload = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object)
            if token in json.dumps(payload, ensure_ascii=False):
                raise ValueError
        except (ValueError, UnicodeError, RecursionError):
            raise self._error("invalid_response") from None
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("status"), str)
            or payload["status"] not in {"000", "013"}
        ):
            raise self._error("provider_status")
        return payload

    def _error(self, code: str, *, transient: bool = False) -> SourceFetchError:
        return SourceFetchError(
            source_name=self.name,
            message=f"DART discovery {code}",
            transient=transient,
        )
