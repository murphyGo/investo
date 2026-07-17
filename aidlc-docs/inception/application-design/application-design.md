# Application Design: Investo

**Date**: 2026-04-27
**Status**: Stage 1 Step 12 — Application Design (consolidated)
**Plan**: aidlc-docs/inception/plans/application-design-plan.md (all recommended)

---

## Overview

Investo는 1인 운영의 데일리 시황 자동 생성·게시 도구다. 본 design은 다섯 개의 1차 컴포넌트(`sources`, `briefing`, `publisher`, `notifier`, `orchestrator`)와 공통 모델 모듈(`models`)로 시스템을 구성하고, GitHub Actions cron이 매일 `python -m investo.run`을 실행하여 파이프라인을 돈다는 원칙을 정의한다. mkdocs build + GitHub Pages 배포는 본 Python 코드의 책임이 아니라 GitHub Actions step의 책임이다.

이 문서는 다음 4개 산출물을 통합 요약한다:
- [components.md](./components.md)
- [component-methods.md](./component-methods.md)
- [services.md](./services.md)
- [component-dependency.md](./component-dependency.md)

---

## Design Principles

1. **단순한 DAG**: orchestrator(root) → 4개 작업 컴포넌트(독립) → models(leaf). 컴포넌트 간 직접 통신 없음.
2. **외부 경계는 캡슐화**: Claude Code CLI, git CLI, Telegram API, 무료 데이터 API 호출은 모두 단일 컴포넌트에 격리되어 외부 변경의 폭발 반경을 제한한다.
3. **Failure isolation**: 단일 source 실패가 파이프라인 전체를 죽이지 않는다 (Q9=B graceful degradation). 단, 면책조항 누락이나 LLM 최종 실패 같은 컴플라이언스/품질 결함은 게시 자체를 중단한다.
4. **Plugin extensibility**: 새 데이터 소스는 단일 파일 추가 + `@register` 데코레이터 한 줄로 통합 (US-008).
5. **Cost zero**: LLM은 Claude Code CLI(설정 토큰)로만, 데이터는 무료 API로만. Anthropic API key 직접 호출 금지 (NFR-002, US-009).
6. **분리된 알림 채널**: 공개 시황 채널과 운영자 1:1 chat을 별도 클래스(BriefingPublisher / OperatorAlerter)로 컴파일 타임 분리.

---

## Component Map

```
investo/
├── models/             # NormalizedItem, Briefing, BriefingNotification,
│                       # FailureContext, SendResult, PipelineResult
├── sources/            # SourceAdapter Protocol + registry + async fetch_all
│   └── ... (per-source files, registered via @register)
├── briefing/           # generate_briefing (two-stage prompt)
│                       # call_claude_code (subprocess wrapper)
│                       # append_disclaimer (auto, idempotent)
├── publisher/          # write_briefing, verify_disclaimer, commit_and_push
├── notifier/
│   ├── briefing_publisher.py   # public channel (FR-004)
│   ├── operator_alerter.py     # operator 1:1 chat (FR-007)
│   └── summary.py              # build_summary helper
└── orchestrator/
    ├── pipeline.py     # run_pipeline + _stage_* + error policy
    ├── date_resolution.py
    └── __main__.py     # entry: python -m investo
```

(파일/모듈명은 가이드라인 — 구현 시 자연스럽게 조정 가능)

---

## Pipeline Flow (Happy Path)

```
GitHub Actions cron (KST 평일 07:00 / 토 09:00)
   |
   v
python -m investo                         <- orchestrator.__main__.main()
   |
   v
resolve_target_date(now)                  <- 어제 (또는 토요일이면 금요일)
   |
   v
sources.fetch_all(target_date)            <- asyncio.gather 모든 source
   |   (per-source 실패는 흡수)
   v
list[NormalizedItem]
   |
   v
briefing.generate_briefing(items, date)   <- two-stage Claude Code CLI
   |   (실패 시 retry; 최종 실패는 alert + 종료)
   v
Briefing (with auto-appended disclaimer)
   |
   v
publisher.verify_disclaimer(rendered_md)  <- 누락 시 차단
publisher.write_briefing(briefing, date)  <- archive/YYYY/MM/YYYY-MM-DD.md
publisher.commit_and_push(...)            <- git add/commit/push
   |
   v
notifier.BriefingPublisher.send(payload)  <- 공개 채널 (best-effort)
   |
   v
exit 0 (SUCCESS or PARTIAL)
   |
   v
GitHub Actions step: mkdocs build + actions/deploy-pages
```

실패 시: 어느 단계든 OperatorAlerter.alert(FailureContext) 호출 → exit 1.

---

## Method Signatures (high-level)

자세한 시그니처는 [component-methods.md](./component-methods.md). 핵심 진입점:

```python
# orchestrator
async def run_pipeline(target_date: date | None = None) -> PipelineResult
async def main() -> int

# sources
async def fetch_all(target_date: date) -> list[NormalizedItem]
def register(adapter_cls): ...  # plugin decorator

# briefing
async def generate_briefing(items, target_date) -> Briefing
def call_claude_code(prompt, system=None, timeout_seconds=120) -> str
def append_disclaimer(rendered) -> str

# publisher
def write_briefing(briefing, target_date) -> Path
def verify_disclaimer(briefing_md) -> bool
def commit_and_push(message, files) -> None

# notifier
class BriefingPublisher: async def send(payload) -> SendResult
class OperatorAlerter:    async def alert(failure) -> SendResult
```

---

## Dependency Graph (DAG)

```
       orchestrator
       /  |   |   |  \
      v   v   v   v   v
  sources briefing publisher notifier
      \   |   |   /   /
       v  v   v  v  v
          models
```

순환 없음. `models`는 leaf로 모두가 의존. 4개 작업 컴포넌트는 서로 독립 — 상호 import 금지 (린트 룰로 강제 가능).

---

## Error Policy Summary (Q9=B)

| Stage | Failure → Behavior |
|-------|--------------------|
| collect (per-source) | 로그 + 비어있는 리스트로 진행 (graceful) |
| collect (total empty) | alert + 게시 중단 |
| generate (LLM) | 내부 retry → 최종 실패 alert + 게시 중단 |
| publish (disclaimer 누락) | alert + 게시 중단 (NFR-004 강제) |
| publish (git push) | retry → 최종 실패 alert + FAILED |
| notify_briefing | best-effort, 실패 시 PARTIAL 표시 (publish는 살림) |
| 예상치 못한 Exception | 최상위에서 alert + exit 1 |

---

## Time Budget (NFR-001 ≤ 10분)

| Stage | 예산 |
|-------|------|
| collect | ≤ 4분 (asyncio.gather, 30s/source timeout) |
| generate | ≤ 4분 (two-stage, retry 포함) |
| publish | ≤ 1분 (git push retry) |
| notify_briefing | ≤ 30초 |
| GitHub Actions overhead | ≤ 30초 |

---

## Out of Application Design (later stages)

다음은 본 단계의 범위가 **아니다** — 이후 단계에서 정의:

- **Functional Design (Construction phase, per-unit)**:
  - LLM prompt의 정확한 텍스트
  - retry 횟수 / backoff 계수 / timeout 값
  - 면책조항 본문 텍스트
  - source별 fetch 로직 (URL, 파싱, rate limit 처리)
  - markdown 7섹션 정확한 포맷·헤더
- **NFR Requirements (Construction phase)**:
  - NFR별 측정 가능 acceptance 기준
- **Build & Test**:
  - GitHub Actions workflow YAML 상세
  - mkdocs.yml, pages 설정
  - test 시나리오 / fixture / PBT 적용 범위 구체화

---

## Story Coverage

| Story | Component(s) involved |
|-------|------------------------|
| US-001 데이터 수집 | sources, models, orchestrator |
| US-002 시황 작성 | briefing, models |
| US-003 정적 웹 게시 | publisher (+ GH Actions step) |
| US-004 텔레그램 채널 알림 | notifier.BriefingPublisher |
| US-005 스케줄 실행 | orchestrator (+ GH Actions cron) |
| US-006 영구 이력 | publisher (git commit) |
| US-007 운영자 실패 알림 | notifier.OperatorAlerter, orchestrator |
| US-008 데이터 소스 확장 | sources.register, components/separation |
| US-009 운영비 0원 | briefing.call_claude_code (CLI only), sources (free APIs only) |

---

## Open Questions (deferred to later stages)

- 무료 데이터 소스 정확한 조합 (Functional Design / 구현 단계 PoC)
- LLM prompt 내용 (Functional Design briefing unit)
- 면책조항 정확한 문구 (Functional Design briefing unit)
- 미국 공휴일 처리 (운영 중 발견 시 보강)
- notify_briefing 반복 실패 시 alert 트리거 여부 (현재 v1: PartialSuccess 표시만)

---

## 2026-07-18 Extension: 미국 섹터 core radar

Application Design에 pure `sector_dashboard` component를 추가한다. 이 component는
11개 sector ETF + SPY의 canonical series input만 받아 metric/regime/snapshot을
계산하며 `models` 외 work component를 import하지 않는다.

### Delivery split

| Unit | Responsibility | Public effect |
| --- | --- | --- |
| u138 | dead Stooq/query1 runtime을 query2 기반으로 복구 | existing briefing price health only |
| u139 | local NAV workbook으로 domain math와 private render 검증 | none; repository 밖 output only |
| u140 | public Pages용 OHLCV provider의 rights/reachability qualification | gate only until provider accepted |

### Binding boundaries

- u138의 Yahoo endpoint 복구는 u140의 public data-rights gate를 통과한 것으로 보지 않는다.
- u139는 local file input만 허용하고 network collector, archive, site_docs, Telegram을
  사용하지 않는다.
- NAV input은 `NAV 수익률`과 `NAV 기준 실현변동성`으로만 표기하며 volume/flow를
  만들지 않는다.
- public sector collection/publish는 u139 domain validation과 u140 source qualification이
  모두 완료된 뒤 별도 construction units로 시작한다.
- actual flow/earnings는 Phase 2, Telegram은 web stability 이후다.

Detailed business rules and measurable controls are deferred to u139/u140 Functional Design
and NFR Requirements as declared in their unit registrations.
