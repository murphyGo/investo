"""DART (전자공시시스템) 한국 기업공시 어댑터 — u41.

OpenDART list.json (https://opendart.fss.or.kr/api/list.json) 응답을 받아
국내 상장사 4 대 카테고리 공시를 :class:`NormalizedItem` 으로 정규화한다.
페르소나 #5 (국내) 가 P0 으로 지목한 갈증의 70% 를 해소하는 어댑터.

Design choices (audit log 2026-05-10):

* **API host** — 공식 호스트는 ``opendart.fss.or.kr`` (FSS, 금융감독원).
  Plan 본문에 등장하는 ``opendart.fsc.go.kr`` 는 오타. 라이브 녹화에서
  확인.
* **Category — Literal mismatch** (Plan DoD 결정사항):
  :data:`investo.models.items.Category` 는 ``Literal["news","price","macro",
  "calendar","earnings"]`` 라 ``"disclosure"`` 가 없다. 이 어댑터는
  ``category="news"`` (의미상 가장 가까운 값) 으로 적재하고,
  ``raw_metadata["subcategory"]`` 에 4 카테고리 (``buyback`` / ``dividend``
  / ``capital_change`` / ``ownership_change``) 를 박아 추적성을 보존한다.
  ``Category`` enum 확장은 별 unit 으로 분리 — TECH-DEBT 후보.
* **API key required** (R13) — ``OPENDART_API_KEY`` 누락 시
  :class:`SourceFetchError(transient=False)`. 키 값은 메시지 / raw_metadata /
  로그 어디에도 박지 않는다. ``_internal/redaction.py::SECRET_ENV_VARS`` 에
  사전 등록되어 있어 실수로 인쇄돼도 redact 됨.
* **Status code mapping** — OpenDART 의 ``status`` 필드:

  * ``"000"`` — 정상.
  * ``"013"`` — 조회 데이터 없음 (정상 운영, 빈 list 반환).
  * ``"010"`` / ``"011"`` — 인증키 미등록/사용불가 → ``transient=False``.
  * ``"020"`` — 사용한도 초과 → ``transient=True`` (재시도).
  * ``"100"`` — 필드 잘못됨 (URL 파라미터 오류) → ``transient=False``.
  * ``"800"`` / ``"900"`` — 시스템 점검/정의되지 않은 오류 → ``transient=True``.
  * 기타 → ``transient=True``.
* **Window** (R7 strict) — KST 영업일 ``[target 00:00, target+1d 00:00) KST``
  반영. ``rcept_dt`` 가 YYYYMMDD 일자만 카리므로 09:00 KST 로 가정 (영업
  시작 시각) 후 UTC 변환.
* **Subcategory mapping** — ``report_nm`` 의 키워드로 분류:

  * ``buyback`` — ``자기주식`` / ``자사주``
  * ``dividend`` — ``현금ㆍ현물배당`` / ``현금배당`` / ``주식배당``
  * ``capital_change`` — ``유상증자`` / ``무상증자`` / ``감자`` /
    ``전환사채`` / ``신주인수권부사채``
  * ``ownership_change`` — ``최대주주변경`` / ``주식등의대량보유`` /
    ``특정증권``
  * 매칭 안 되는 보고서는 드롭 (저신호 항목 — 분기보고서, 감사보고서, 약관 등).

* **URL** — 보고서 뷰어 ``http://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}``.
  https 가 아니지만 dart.fss.or.kr 는 https 도 지원하므로 https 사용.

Pins:

* Plan u41 DoD — 4 카테고리 분류, S 티어, R10 fixture, R13 키 위생.
* AC-3.6 / R13 — missing/empty ``OPENDART_API_KEY`` → ``SourceFetchError(transient=False)``.
* R7 — KST window strict 반영.
* R8 — ``raw_metadata`` 평면 dict[str,str].
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, time
from typing import Any, ClassVar, Final
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._sanitize import strip_html
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_KST = ZoneInfo("Asia/Seoul")
_ENV_KEY = "OPENDART_API_KEY"

# Subcategory mapping — first match wins. Order matters: more-specific
# patterns first (e.g. ``자기주식`` before fall-through). Each tuple
# member is checked as a substring on the cleaned ``report_nm`` (after
# strip_html + .strip()).
_SUBCATEGORY_KEYWORDS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("buyback", ("자기주식", "자사주")),
    ("dividend", ("현금ㆍ현물배당", "현금배당", "주식배당")),
    (
        "capital_change",
        ("유상증자", "무상증자", "감자", "전환사채", "신주인수권부사채"),
    ),
    ("ownership_change", ("최대주주변경", "주식등의대량보유", "특정증권")),
)

# OpenDART status code → fetch outcome.
# ``ok`` — return the parsed list (which itself may be empty for 013).
# ``empty`` — non-error empty result; return ``[]``.
# ``terminal`` — raise ``SourceFetchError(transient=False)``.
# ``transient`` — raise ``SourceFetchError(transient=True)`` (the
# aggregator may apply a wider retry policy in a future iteration; for
# now the per-fetch retry helper has already exhausted its budget by the
# time this layer runs).
_STATUS_OK: Final[str] = "000"
_STATUS_EMPTY: Final[str] = "013"
_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"010", "011", "100"})
_TRANSIENT_STATUSES: Final[frozenset[str]] = frozenset({"020", "800", "900"})


@register
class DartDisclosureAdapter:
    """OpenDART 공시 목록 어댑터.

    ``corp_cls`` 가 ``"Y"`` (KOSPI) / ``"K"`` (KOSDAQ) / ``"N"`` (코넥스)
    인 항목 중, 4 대 카테고리 키워드에 매칭되는 보고서만 정규화한다.
    그 외 corp_cls (E — ETC) 와 매칭되지 않는 보고서는 드롭 — 페르소나
    #5 가 정의한 핵심 정보 갈증 범위에 들지 않음.
    """

    name: ClassVar[str] = "dart-disclosure"
    category: ClassVar[Category] = "news"

    _ENDPOINT: ClassVar[str] = "https://opendart.fss.or.kr/api/list.json"
    _PAGE_COUNT: ClassVar[int] = 100
    _MAX_ITEMS: ClassVar[int] = 30

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        # R13: read at fetch-time. Missing → SourceFetchError(transient=False).
        # The error message names the env var (NOT any partial key value).
        api_key = os.environ.get(_ENV_KEY, "").strip()
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=(f"{_ENV_KEY} not set; {self.name} adapter will not run"),
                transient=False,
                cause=None,
            )

        bgn_de, end_de = self._window_to_yyyymmdd(window)
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={
                "crtfc_key": api_key,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_no": "1",
                "page_count": str(self._PAGE_COUNT),
            },
        )
        payload = parse_json_response(
            response,
            source_name=self.name,
            message=f"malformed JSON from {self._ENDPOINT}",
            append_exc=False,
        )

        if not isinstance(payload, dict):
            raise SourceFetchError(
                source_name=self.name,
                message="non-object OpenDART response",
                transient=False,
            )

        status = str(payload.get("status", "")).strip()
        message = str(payload.get("message", "")).strip()
        if status in _TERMINAL_STATUSES:
            # Sanitize message — never echo the API key. The DART error
            # messages themselves do not reflect the key, but we name the
            # status code only.
            raise SourceFetchError(
                source_name=self.name,
                message=f"OpenDART status {status} ({message or 'no message'})",
                transient=False,
            )
        if status in _TRANSIENT_STATUSES:
            raise SourceFetchError(
                source_name=self.name,
                message=f"OpenDART status {status} ({message or 'no message'})",
                transient=True,
            )
        if status == _STATUS_EMPTY:
            return []
        if status != _STATUS_OK:
            # Defense-in-depth — unknown status code → terminal.
            raise SourceFetchError(
                source_name=self.name,
                message=f"OpenDART unknown status {status} ({message or 'no message'})",
                transient=False,
            )

        raw_list = payload.get("list")
        if not isinstance(raw_list, list):
            return []

        items: list[NormalizedItem] = []
        for entry in raw_list:
            normalized = self._normalize_entry(entry)
            if normalized is None:
                continue
            if window.contains(normalized.published_at):
                items.append(normalized)

        # Stable order — most-recent first (rcept_no is monotonically
        # increasing within a day so this approximates publication order).
        items.sort(key=lambda i: i.published_at, reverse=True)
        return items[: self._MAX_ITEMS]

    @staticmethod
    def _window_to_yyyymmdd(window: FetchWindow) -> tuple[str, str]:
        """Map the UTC :class:`FetchWindow` to OpenDART ``YYYYMMDD`` bounds.

        OpenDART's ``bgn_de`` / ``end_de`` are inclusive KST date bounds.
        For a single-day publish window the start and end are the same
        KST trading date.
        """
        kst_target = window.target_date
        date_str = kst_target.strftime("%Y%m%d")
        return date_str, date_str

    def _normalize_entry(self, entry: Any) -> NormalizedItem | None:
        if not isinstance(entry, dict):
            return None
        report_nm_raw = entry.get("report_nm")
        rcept_no = entry.get("rcept_no")
        rcept_dt = entry.get("rcept_dt")
        corp_name = entry.get("corp_name")
        corp_code = entry.get("corp_code")
        corp_cls = entry.get("corp_cls", "")
        if not isinstance(report_nm_raw, str) or not isinstance(rcept_no, str):
            return None
        if not isinstance(rcept_dt, str) or len(rcept_dt) != 8:
            return None
        if not isinstance(corp_name, str) or not corp_name.strip():
            return None
        if not isinstance(corp_code, str) or not corp_code.strip():
            return None
        if not isinstance(corp_cls, str):
            return None

        # Some DART titles carry trailing whitespace runs; strip_html
        # also normalizes any HTML the upstream might emit (defense-
        # in-depth — list.json titles are plain text today).
        report_nm = strip_html(report_nm_raw).strip()
        if not report_nm:
            return None

        subcategory = self._classify(report_nm)
        if subcategory is None:
            return None

        try:
            published_at = self._parse_rcept_dt(rcept_dt)
        except ValueError:
            return None

        title = f"[DART] {corp_name.strip()} - {report_nm}"
        # Truncate title at 140 chars to keep prompt-bounded.
        if len(title) > 140:
            title = title[:140]
        summary = f"{report_nm} (접수번호 {rcept_no})"
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

        raw_metadata: dict[str, str] = {
            "corp_code": corp_code.strip(),
            "corp_name": corp_name.strip(),
            "report_nm": report_nm,
            "rcept_no": rcept_no.strip(),
            "rcept_dt": rcept_dt.strip(),
            "subcategory": subcategory,
        }
        stock_code = entry.get("stock_code")
        if isinstance(stock_code, str) and stock_code.strip():
            raw_metadata["stock_code"] = stock_code.strip()
        if corp_cls.strip():
            raw_metadata["corp_cls"] = corp_cls.strip()

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None

    @staticmethod
    def _classify(report_nm: str) -> str | None:
        """Return the subcategory tag, or ``None`` if no keyword matches."""
        for subcategory, keywords in _SUBCATEGORY_KEYWORDS:
            if any(kw in report_nm for kw in keywords):
                return subcategory
        return None

    @staticmethod
    def _parse_rcept_dt(rcept_dt: str) -> datetime:
        """Parse ``YYYYMMDD`` reception date to KST 09:00 → UTC.

        OpenDART list.json carries the date only (no time). 09:00 KST is
        the conventional KRX trading-open anchor — using midnight would
        push every same-day disclosure out of the strict R7 window
        (window start = 00:00 KST, but a midnight stamp lands ON the
        boundary; 09:00 sits comfortably inside the half-open window).
        """
        year = int(rcept_dt[0:4])
        month = int(rcept_dt[4:6])
        day = int(rcept_dt[6:8])
        kst_dt = datetime(year, month, day, tzinfo=_KST).replace(hour=time(9, 0).hour, minute=0)
        return kst_dt.astimezone(UTC)
