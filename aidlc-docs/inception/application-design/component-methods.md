# Component Methods: Investo

**Date**: 2026-04-27
**Note**: Method signatures + I/O types만 (high-level). 상세 비즈니스 규칙(예: 두 단계 prompt의 정확한 분류 키, retry 횟수, backoff 계수)은 Construction phase의 Functional Design에서 정의.

---

## models — Common Types

```python
from datetime import date, datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, HttpUrl

Category = Literal["news", "price", "macro", "calendar", "earnings"]

class NormalizedItem(BaseModel):
    source_name: str
    category: Category
    title: str
    summary: str | None = None
    url: HttpUrl | None = None
    published_at: datetime
    raw_metadata: dict[str, str | int | float] = {}

class Briefing(BaseModel):
    target_date: date
    market_summary: str            # ① 요약
    key_issues: str                # ② 전일 핵심 이슈
    sector_flow: str               # ③ 섹터/수급 동향
    indicators_events: str         # ④ 지표·이벤트
    notable_tickers: str           # ⑤ 주요 종목
    today_watch: str               # ⑥ 오늘의 관전 포인트
    disclaimer: str                # ⑦ 면책조항 (코드로 자동 삽입)
    rendered_markdown: str         # 7섹션 통합 markdown

class BriefingNotification(BaseModel):
    target_date: date
    summary_text: str              # ≤ 4096자
    site_url: HttpUrl

class FailureContext(BaseModel):
    stage: Literal["collect", "generate", "publish", "notify_briefing"]
    error_type: str
    error_message: str
    traceback_excerpt: str | None = None
    occurred_at: datetime

class SendResult(BaseModel):
    ok: bool
    error: str | None = None
    message_id: int | None = None

class PipelineStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"   # 게시 성공 + notify briefing 실패 등
    FAILED = "failed"     # 게시 자체 실패

class PipelineResult(BaseModel):
    target_date: date
    status: PipelineStatus
    stages: dict[str, str]         # stage_name -> "ok" / "skipped" / "failed: reason"
    duration_seconds: float
    briefing_url: HttpUrl | None = None
```

---

## C1: sources

```python
from typing import Protocol

class SourceAdapter(Protocol):
    name: str
    category: Category

    async def fetch(self, target_date: date) -> list[NormalizedItem]: ...
    # raises: SourceFetchError (handled by fetch_all to allow degradation)

# Plugin registry
def register(adapter_cls: type[SourceAdapter]) -> type[SourceAdapter]: ...
def list_sources() -> list[SourceAdapter]: ...

# Aggregator
async def fetch_all(target_date: date) -> list[NormalizedItem]:
    """Concurrent gather over all registered adapters with per-source
    failure isolation. Failed sources contribute empty list + log entry."""
```

신규 소스 통합 절차 (US-008): `sources/<source_name>.py` 신규 파일에서
`SourceAdapter` 구현체 정의 + `@register` 데코레이터 적용 → 자동 인식.

---

## C2: briefing

```python
async def generate_briefing(
    items: list[NormalizedItem],
    target_date: date,
) -> Briefing:
    """Two-stage prompt:
       1) classify_and_summarize(items) -> ClassifiedItems
       2) compose_briefing(classified, target_date) -> rendered markdown
       Then: rendered = rendered + DISCLAIMER (코드로 append).
       raises: BriefingGenerationError (after retries exhausted)"""

# Internal helpers (export 가능, but not part of stable public surface)
def build_classification_prompt(items: list[NormalizedItem], target_date: date) -> str: ...
def build_briefing_prompt(classified: "ClassifiedItems", target_date: date) -> str: ...

def call_claude_code(
    prompt: str,
    system: str | None = None,
    timeout_seconds: int = 120,
) -> str:
    """subprocess.run(['claude', '-p', prompt, ...]) wrapper.
       Auth via CLAUDE_CODE_OAUTH_TOKEN env (GitHub Secrets).
       raises: ClaudeCodeError on non-zero exit."""

DISCLAIMER: str  # 모듈 상수 — 면책조항 본문

def append_disclaimer(rendered: str) -> str:
    """Idempotent: 이미 disclaimer가 끝에 있으면 추가 X."""
```

---

## C3: publisher

```python
ARCHIVE_ROOT: Path = Path("archive")  # archive/YYYY/MM/YYYY-MM-DD.md

def archive_path(target_date: date) -> Path: ...

def write_briefing(briefing: Briefing, target_date: date) -> Path:
    """Writes rendered_markdown to archive_path(target_date).
       Overwrites existing (history retained via git).
       raises: PublisherIOError"""

def verify_disclaimer(briefing_md: str) -> bool:
    """Checks disclaimer boilerplate substring presence.
       Returns False if missing — caller blocks publish."""

def commit_and_push(
    message: str,
    files: list[Path],
    *,
    retries: int = 2,
) -> None:
    """git add <files> && git commit -m <message> && git push origin <branch>.
       raises: PublisherGitError after retries exhausted."""
```

---

## C4: notifier

```python
class BriefingPublisher:
    """Public Telegram channel/group dispatcher (FR-004)."""
    def __init__(self, bot_token: str, channel_id: str, *, http: httpx.AsyncClient | None = None): ...

    async def send(self, payload: BriefingNotification) -> SendResult:
        """sendMessage (parse_mode=Markdown). Returns SendResult.
           Never raises for HTTP failures — encodes them in result.ok=False."""

class OperatorAlerter:
    """Operator-only 1:1 chat dispatcher (FR-007)."""
    def __init__(self, bot_token: str, operator_chat_id: str, *, http: httpx.AsyncClient | None = None): ...

    async def alert(self, failure: FailureContext) -> SendResult:
        """Sends formatted failure notice. Same non-raising contract as send()."""

def build_summary(briefing: Briefing, max_chars: int = 4096) -> str:
    """Compose channel summary with site link. Truncates safely if > max_chars."""
```

---

## C5: orchestrator

```python
async def run_pipeline(target_date: date | None = None) -> PipelineResult:
    """Resolve target_date (default: KST today's market-close-aware date).
       Stages with Q9=B graceful degradation policy applied.
       Always returns PipelineResult; raises only on programmer errors."""

async def main() -> int:
    """Module entrypoint:
       - Parse env (CLAUDE_CODE_OAUTH_TOKEN, TELEGRAM_BOT_TOKEN,
         TELEGRAM_BRIEFING_CHANNEL_ID, TELEGRAM_OPERATOR_CHAT_ID, SITE_URL_BASE)
       - run_pipeline()
       - Return exit code (0=ok or partial, 1=failed)
       - On failed: ensure OperatorAlerter was called"""

# Stage runners (internal — testable)
async def _stage_collect(target_date: date) -> list[NormalizedItem]: ...
async def _stage_generate(items: list[NormalizedItem], target_date: date) -> Briefing: ...
async def _stage_publish(briefing: Briefing, target_date: date) -> Path: ...
async def _stage_notify_briefing(briefing: Briefing, site_url: HttpUrl) -> SendResult: ...

# Date resolution
def resolve_target_date(now_utc: datetime, *, weekday_only_us_close: bool = True) -> date:
    """KST 평일 07:00 cron → 미국장 마감일(전일 KST). 토요일 09:00 → 금요일."""
```

---

## Method-to-Story Traceability

| Component.Method | Story AC tied |
|------------------|---------------|
| `sources.fetch_all` | US-001 (수집), US-008 (확장성) |
| `sources.register` | US-008 (plugin) |
| `briefing.generate_briefing` | US-002 (시황), US-009 (Claude Code only) |
| `briefing.append_disclaimer` | US-002 면책조항 AC, NFR-004 |
| `briefing.call_claude_code` | US-009 (CLI only, no anthropic SDK) |
| `publisher.write_briefing` | US-003, US-006 |
| `publisher.verify_disclaimer` | NFR-004 강제 (Q6 보강) |
| `publisher.commit_and_push` | US-006 (영구 보관) |
| `notifier.BriefingPublisher.send` | US-004 |
| `notifier.OperatorAlerter.alert` | US-007 |
| `orchestrator.run_pipeline` | US-005, NFR-001, NFR-003 |
| `orchestrator.resolve_target_date` | US-005 (KST 평일/주말 분기) |
| `sector_dashboard.load_private_nav_workbooks` | US-010 private validation, NFR-008 |
| `sector_dashboard.compute_sector_snapshot` | FR-022 deterministic radar |
| `sector_dashboard.render_private_validation` | US-010 private-only reader contract |

---

## 2026-07-18 Extension: C6 `sector_dashboard`

```python
def load_private_nav_workbooks(
    paths_by_ticker: Mapping[str, Path],
    *,
    expected_universe: SectorUniverse,
) -> SectorSeriesBundle:
    """Read operator-provided local XLSX files without network access.

    Rejects ticker mismatch, duplicate dates, malformed rows, and cross-ticker
    as-of mismatch. The caller owns the source files; raw bytes are not persisted.
    """

def compute_sector_snapshot(
    bundle: SectorSeriesBundle,
    *,
    target_date: date,
    benchmark_ticker: str = "SPY",
) -> SectorDashboardSnapshot:
    """Compute deterministic return, excess-return, acceleration, regime,
    volatility, drawdown, and coverage records from one canonical bundle."""

def classify_sector_regime(
    *,
    relative_strength_21d: Decimal,
    acceleration_5d: Decimal,
    neutral_band: Decimal,
) -> SectorRegime: ...

def render_private_validation(
    snapshot: SectorDashboardSnapshot,
    *,
    output_dir: Path,
) -> tuple[Path, ...]:
    """Render private validation artifacts outside archive/site_docs.

    Requires value_kind=NAV labels and omits unsupported volume/flow fields.
    """
```

Detailed neutral-band sensitivity, XLSX cell parsing, and fallback rules belong to
u139 Functional Design. No public source adapter method is defined until u140 accepts
a provider.
