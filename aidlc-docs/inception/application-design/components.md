# Components: Investo

**Date**: 2026-04-27
**Source**: application-design-plan.md (all recommended) + execution-plan.md sketch

---

## Component Overview

6개의 1차 컴포넌트 + 1개의 공통 모듈(`models/`)로 구성. 모든 컴포넌트는 단일 Python 패키지 `investo` 안의 서브패키지.

```
investo/
├── models/         # 공통 pydantic 타입 (NormalizedItem, Briefing, ...)
├── sources/        # C1: Source Adapters (plugin)
├── briefing/       # C2: Briefing Generator (Claude Code CLI driver)
├── publisher/      # C3: Publisher (markdown archive + git commit)
├── notifier/       # C4: Notifier (BriefingPublisher + OperatorAlerter)
├── orchestrator/   # C5: Orchestrator (pipeline runner + entrypoint)
└── sector_dashboard/ # C6: deterministic sector radar + private validation
```

`mkdocs build` + GitHub Pages 배포는 GitHub Actions step으로 분리 (Q7=B) — Python 코드가 직접 호출하지 않음.

---

## C1: `sources` — Source Adapters

**Purpose**: 무료 공개 데이터 소스(뉴스, 시세, 거시 지표, 캘린더, 실적 등)에서 전일 시장 데이터를 비동기로 수집하고 공통 정규화 모델로 반환.

**Responsibilities**:
- 카테고리별(`news / price / macro / calendar / earnings`) 다수 어댑터 구현 보유
- Plugin registry로 신규 소스 추가가 단일 모듈 추가 + 등록 한 줄로 가능 (US-001, US-008)
- 단일 소스 실패가 전체 파이프라인을 죽이지 않음 — 실패는 로그 + 빈 리스트 반환 (US-001 graceful degradation, NFR-003)
- 공통 timeout/retry 정책을 base class에서 제공 (httpx 기반)

**Interfaces (외부에 노출)**:
- `class SourceAdapter(Protocol)` — 모든 어댑터의 공통 contract
- `def list_sources() -> list[SourceAdapter]` — registry에 등록된 어댑터 목록
- `async def fetch_all(target_date: date) -> list[NormalizedItem]` — 전체 어댑터를 `asyncio.gather`로 병렬 수집 + 부분 실패 허용

**Dependencies**: `models`, `httpx` (외부)
**Used by**: `orchestrator`

---

## C2: `briefing` — Briefing Generator

**Purpose**: 정규화된 시장 데이터를 입력으로 Claude Code CLI를 호출하여 한국어 7섹션 시황 markdown을 생성하고 면책조항을 자동 삽입.

**Responsibilities**:
- Two-stage prompt 흐름 운영 (Q5=B): (1) 분류·요약 → (2) 7섹션 통합 (US-002)
- Claude Code CLI 호출 (Q4=A) — `subprocess.run(["claude", "-p", ...])`
- 면책조항 자동 append (NFR-004, US-002 AC) — 코드 상수로 안정 보장 (Q6=A)
- LLM 호출 실패 시 retry (지수 backoff), 최종 실패 시 예외 raise → orchestrator가 게시 중단
- 비용 0원 보장 (US-009): Anthropic API key 직접 호출 금지, Claude Code subscription token만 사용

**Interfaces**:
- `async def generate_briefing(items: list[NormalizedItem], target_date: date) -> Briefing`

**Dependencies**: `models`, `claude` CLI (subprocess)
**Used by**: `orchestrator`

---

## C3: `publisher` — Publisher

**Purpose**: 생성된 시황 markdown을 `archive/YYYY/MM/YYYY-MM-DD.md`에 저장하고 git commit + push 수행. 게시 전 disclaimer presence 검증.

**Responsibilities**:
- markdown 파일을 archive 경로에 작성 (US-003, US-006)
- 게시 전 검증 (Q6 보강): 면책조항 누락 시 게시 차단 + Operator alert 트리거
- git add → commit → push (HTTPS or SSH, GH Actions 기본 인증)
- 동일 날짜 재실행 시 덮어쓰기 정책 (이전 버전은 git history로 보존)
- mkdocs build / Pages 배포는 본 컴포넌트 책임이 **아님** (GitHub Actions step에서 처리)

**Interfaces**:
- `def archive_path(target_date: date) -> Path`
- `def write_briefing(briefing: Briefing, target_date: date) -> Path`
- `def verify_disclaimer(briefing_md: str) -> bool`
- `def commit_and_push(message: str, files: list[Path]) -> None`

**Dependencies**: `models`, `git` CLI (subprocess), 파일시스템
**Used by**: `orchestrator`

---

## C4: `notifier` — Notifier (BriefingPublisher + OperatorAlerter)

**Purpose**: 생성된 시황을 텔레그램으로 분배. **공개 채널**과 **운영자 1:1 chat**을 별도 클래스로 분리하여 채널 혼선을 컴파일 타임에 방지.

**Responsibilities**:
- `BriefingPublisher`: 공개 Telegram 채널/그룹에 시황 요약 + 사이트 URL 발송 (FR-004, US-004)
  - 4096자 한도 준수 (초과 시 요약 + 링크)
  - 시크릿/PII 미포함 검증
  - 실패 시 시황 게시 자체는 막지 않음
- `OperatorAlerter`: 운영자 1:1 chat에 실패 알림 발송 (FR-007, US-007)
  - 실패 단계 + 에러 메시지 포함
  - 공개 채널과 분리된 chat ID 사용 (`TELEGRAM_OPERATOR_CHAT_ID`)
- 공통: Telegram Bot API raw HTTP 호출, retry + timeout

**Interfaces**:
- `class BriefingPublisher: async def send(payload: BriefingNotification) -> SendResult`
- `class OperatorAlerter: async def alert(failure: FailureContext) -> SendResult`
- `def build_summary(briefing: Briefing, max_chars: int = 4096) -> str` (공통 유틸)

**Dependencies**: `models`, `httpx` (Telegram Bot API)
**Used by**: `orchestrator` (BriefingPublisher 호출 + 모든 단계의 실패 처리에서 OperatorAlerter 호출)

---

## C5: `orchestrator` — Orchestrator

**Purpose**: 파이프라인의 단일 진입점. 단계별 실행 + 단계별 에러 정책 적용 + 운영자 알림 트리거.

**Responsibilities**:
- 파이프라인 단계: `collect → generate → publish → notify`
- 단계별 에러 정책 (Q9=B Graceful degradation):
  - **collect**: 부분 실패 허용 (sources의 graceful degradation 활용)
  - **generate**: retry → 최종 실패 시 게시 중단 + alert (시황 발행 X)
  - **publish**: git/disclaimer 실패 시 retry → 최종 실패는 alert
  - **notify (briefing)**: 실패해도 publish는 성공 처리 (사이트 게시는 살아 있음)
  - **notify (alert on failure)**: 어느 단계든 실패 시 OperatorAlerter 트리거
- target_date 결정 — KST 기준 cron 시간에서 도출 (평일 오전 7시 → 전일 미국장)
- 단일 job 실행 시간 ≤ 10분 검증 (NFR-001)
- 진입점: `python -m investo.run` (GitHub Actions에서 호출)

**Interfaces**:
- `async def run_pipeline(target_date: date | None = None) -> PipelineResult`
- `async def main() -> int` — entrypoint (exit code 0=성공, 1=실패)

**Dependencies**: `sources`, `briefing`, `publisher`, `notifier`, `models`
**Used by**: GitHub Actions workflow (외부)

---

## Common Module: `models`

**Purpose**: 컴포넌트 간 공유되는 pydantic v2 타입을 단일 모듈에 중앙화 (Q3=A). PBT round-trip 대상 (NFR-006).

**Key types**:
- `NormalizedItem` — Source Adapter 출력의 공통 정규화 형태
- `Briefing` — 7섹션 시황 본문 + 메타데이터 + 면책조항
- `BriefingNotification` — 공개 채널 발송 페이로드 (요약 + URL)
- `FailureContext` — 운영자 알림 페이로드 (단계, 에러, stack trace 요약)
- `SendResult` — Notifier 호출 결과 (성공/실패 + 사유)
- `PipelineResult` — 파이프라인 실행 요약 (단계별 상태 + duration)

---

## Component Summary Table

| ID | Component | Stories | NFR Touched | External Deps |
|----|-----------|---------|-------------|---------------|
| C1 | sources | US-001, US-008 | NFR-002, NFR-003, NFR-005 | httpx, 무료 API들 |
| C2 | briefing | US-002, US-009 | NFR-002, NFR-003, NFR-004 | claude CLI |
| C3 | publisher | US-003, US-006 | NFR-001, NFR-007 | git CLI, 파일시스템 |
| C4 | notifier | US-004, US-007 | NFR-003, NFR-007 | httpx, Telegram Bot API |
| C5 | orchestrator | US-005 | NFR-001, NFR-003 | (내부 의존만) |
| C6 | sector_dashboard | US-010, FR-022 | NFR-003, NFR-006, NFR-008 | local/private input in u139; qualified OHLCV later |
| — | models | (모든 스토리) | NFR-006 (PBT) | pydantic |

---

## 2026-07-18 Extension: C6 `sector_dashboard`

**Purpose**: 11개 Select Sector SPDR ETF와 SPY의 동일 기준 시계열을 받아 상대강도,
가속도, regime, 변동성, 낙폭, coverage를 결정론적으로 계산한다.

**Responsibilities**:
- fixed universe와 benchmark identity 검증
- NAV 또는 OHLCV 입력을 typed series로 정규화
- 1D/5D/21D/63D return, SPY excess return, 5D acceleration 계산
- `주도 / 둔화 / 회복 / 부진 / 데이터 부족` regime 계산
- input kind에 따라 volume·거래대금 지원 여부를 명시적으로 제한
- public/private artifact policy를 snapshot metadata에 포함

**Interfaces**:
- local private workbook을 canonical series input으로 변환
- canonical input에서 `SectorDashboardSnapshot` 계산
- private validation 결과를 repository 밖의 operator-selected output directory에 렌더

**Dependencies**: `models`, stdlib/approved XML parser only

**Used by**:
- u139 local/private validation runner
- future orchestrator/public publisher only after u140 source gate clears

**Boundary**:
- `sector_dashboard`는 `sources`, `briefing`, `publisher`, `notifier`를 import하지 않는다.
- source acquisition과 publish integration은 orchestrator가 조정한다.
- u140은 runtime component가 아니라 C1 source 후보를 승인하는 pre-construction gate다.
