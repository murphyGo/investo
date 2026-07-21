# Design Document: Investo

*Generated on 2026-04-27*
*Source: aidlc-docs/inception/application-design/ (see AI-DLC artifacts for detailed design)*

본 문서는 개발자용 요약본이다. 상세 설계의 단일 출처는 `aidlc-docs/inception/application-design/` 이다 — 본 문서가 그 내용과 모순되면 AIDLC 산출물이 우선한다.

---

## Overview

Investo는 **단일 deployable Python 패키지(monolith)**로, GitHub Actions cron이 매일 `python -m investo`를 실행해 다음 단계를 순차로 수행한다:

1. **수집** (sources): 무료 공개 API/RSS에서 전일 시장 데이터 수집
2. **시황 초안 작성** (briefing): Claude Code CLI를 two-stage prompt로 호출해 국내 증시·미국 증시·크립토 세그먼트별 한국어 초안을 생성
3. **최종화·게시** (publisher): 모든 조립/공개 projection/repair를 수행한 뒤 read-only 신뢰 게이트와 SHA-256 seal을 통과한 문서만 `archive/{segment}/YYYY/MM/`에 exact-byte 저장 + 단일 git commit/push
4. **알림** (notifier): 봉인 직전 terminal validation에서 파생된 `PublicNotificationSummary` DTO로 세 세그먼트 요약과 링크를 공개 Telegram 채널에 푸시 (실패 시 운영자 1:1 chat에 별도 알림)

`mkdocs build`와 GitHub Pages 배포는 별도 GitHub Actions workflow의 책임이다. daily workflow는 공개 commit이 있으면 Pages를 먼저 dispatch한 뒤 Python rc를 재발생시켜, 1~2개 세그먼트만 발행된 경우에도 사이트는 갱신하되 daily run은 exit 2로 red 상태를 유지한다.

---

## Architecture

### High-Level Design

```
                                +--------------------+
                                | GitHub Actions cron|
                                +---------+----------+
                                          |  python -m investo
                                          v
                                +---------+----------+
                                |   orchestrator     |
                                |  (run_pipeline)    |
                                +---------+----------+
                                          |
              +----------------+----------+----------+----------------+
              | (1) collect    | (2) generate         | (3) publish    | (4) notify
              v                v                      v                v
     +----------------+ +----------------+ +----------------+ +----------------+
     |    sources     | |    briefing    | |   publisher    | |    notifier    |
     | (asyncio.gather| | (Claude Code   | | (md write +    | | (Telegram Bot  |
     |  + degradation)| |  CLI two-stage)| |  git push +    | |  API)          |
     |                | |  draft output) | | finalizer+seal | | sealed DTO)    |
     +-------+--------+ +-------+--------+ +-------+--------+ +---+--------+---+
             |                  |                  |             |        |
             v (HTTP)           v (subprocess)     v             v        v
    +-----------------+ +----------------+ +----------------+ +----------+ +-----------------+
    | Free APIs       | | claude CLI     | | filesystem     | | Telegram | | Telegram        |
    | (news, prices,  | | (subscription  | | + git remote   | | public   | | operator 1:1    |
    |  macro, ...)    | |  via OAUTH     | | (origin/main)  | | channel  | | chat            |
    |                 | |  TOKEN)        | |                | | (FR-004) | | (FR-007)        |
    +-----------------+ +----------------+ +----------------+ +----------+ +-----------------+
```

### Components

| Component | Responsibility | Module path |
|-----------|---------------|-------------|
| sources | 무료 데이터 plugin 수집 + 부분 실패 허용 | `src/investo/sources/` |
| briefing | Claude Code CLI two-stage 초안 생성 + 호환 면책조항 보장 | `src/investo/briefing/` |
| publisher | generated→sealed 단일 finalizer, exact-byte archive, sealed consumer view, git commit | `src/investo/publisher/` |
| notifier | terminal `PublicNotificationSummary` formatter + BriefingPublisher (공개 채널) + OperatorAlerter (1:1) | `src/investo/notifier/` |
| orchestrator | 파이프라인 단일 진입점 + 단계별 에러 정책 | `src/investo/orchestrator/` |
| models | 공통 pydantic v2 타입 (NormalizedItem, Briefing, ...) | `src/investo/models/` |

각 컴포넌트의 메서드 시그니처는 `aidlc-docs/inception/application-design/component-methods.md` 참조.

---

## Technical Decisions

### TD-001: LLM 호출은 Claude Code CLI subprocess로만

**Choice**: `subprocess.run(["claude", "-p", prompt, ...])` 패턴
**Rationale**: 사용자가 Claude Max/Pro 구독자로서 setup token 발급 가능. Anthropic API key 직접 호출은 별도 요금 발생 → NFR-002(월 $0) 위반.
**Alternatives Considered**: `anthropic` Python SDK (요금 발생), Claude Code Node SDK (Python 프로젝트에 Node 의존성 추가는 과함).
**Reference**: requirements.md FR-002 + NFR-002, docs/feedback_claude_code_cli.md

### TD-002: 데이터 모델 중앙화 (pydantic v2 in `models/`)

**Choice**: 모든 컴포넌트 간 공유 타입을 `src/investo/models/`에 모음.
**Rationale**: 변환 보일러플레이트 최소, PBT round-trip 적용 위치 단일.
**Alternatives Considered**: 컴포넌트별 분산 (결합도↓이지만 변환 비용↑).

### TD-003: Two-Stage Prompt

**Choice**: 1차 분류·요약 → 2차 7섹션 통합 (각각 Claude Code CLI 호출).
**Rationale**: 토큰 효율 + 품질 향상. Single-shot은 컨텍스트 폭발 위험.
**Alternatives Considered**: Single-shot, templating + LLM hybrid.

### TD-004: 면책조항 코드 자동 append + Publisher 검증

**Choice**: `briefing.append_disclaimer`는 생성 경계의 호환 보장을 유지한다. 기본 segmented 경로에서는 `publisher.finalize_public_bundle`가 nav/요약/본문 evidence/visual/watchpoint/면책조항을 포함한 모든 producer 이후 terminal exact-disclaimer 검증을 수행하고 seal한다. `write_finalized_document`는 seal과 면책조항을 다시 확인한 뒤 exact bytes만 쓴다.
**Rationale**: NFR-004(컴플라이언스) 강제. LLM이 누락하더라도 코드로 보장.
**Alternatives Considered**: prompt에만 의존 (누락 위험).

### TD-005: 텔레그램 채널 분리

**Choice**: `BriefingPublisher`(공개 채널) + `OperatorAlerter`(운영자 1:1) 두 별도 클래스.
**Rationale**: FR-004와 FR-007의 채널 혼선 방지. Public Reader가 운영 노이즈를 보지 않도록.
**Alternatives Considered**: 단일 Notifier + channel 파라미터 (혼선 위험).

### TD-006: GitHub Actions step에서 mkdocs build / Pages deploy

**Choice**: Python publisher는 sealed markdown write + git commit까지 맡는다. daily workflow는 bounded `$GITHUB_OUTPUT`을 읽어 `publication_committed=true`일 때 Pages workflow를 dispatch하고, 마지막 `always()` step에서 rc 1/2를 재발생시킨다.
**Rationale**: 책임 분리와 GitHub native 배포를 유지하면서 content-partial commit도 배포하고 운영 실패 신호는 보존한다.
**Alternatives Considered**: Python에서 `mkdocs build` subprocess 호출 (책임 혼합).

### TD-007: Graceful Degradation Pipeline

**Choice**: 단일 source 실패는 흡수한다. 세그먼트 생성 부재 또는 numeric/entity/compliance/disclaimer/structure/notification-summary 신뢰 차단은 유효 sibling만 한 트랜잭션으로 발행하고 `content_completeness=partial`, exit 2로 표시한다. 0개 survivor/게시 실패는 exit 1, 완전 콘텐츠의 알림 실패는 exit 0이다.
**Rationale**: 무료 API의 불안정성 + 시황 품질 보장 + 외부 노출 안전.
**Alternatives Considered**: Fail-fast (단일 장애로 시황 누락).

### TD-008: First-Viewport 표현 계약 (reader-first reflow, u71)

**Choice**: `publisher.reader_format.reflow_first_viewport`가 세그먼트 헤더 영역을 고정·idempotent 순서로 재배치 — (1) 제목+기준 시각 watermark+nav → (2) `## 한눈에 보기` TL;DR → (3) 요약 callout `오늘의 결론`/`핵심 동인`/`주의할 점`(caution <=90자 단어경계 절단) → (4) compact 1줄 status chip `> **데이터 상태**: {label} · 본문 사용 {n|미집계} · 실패 {n} · 0건 {n}` → (5) collapsed `<details><summary>수집/품질 진단</summary>...</details>`(원본 badge body: 소스 카운트/등급분포/상세사유/소스별 상태) → (6) `## ①` 본문. status가 `실패`이거나 u61이 유효 요약을 만들지 못한 경우에만 `<details open>`. orchestrator가 per-segment post-format 체인의 `emit_first_viewport_disclaimer` 직후 1회 와이어.
**Rationale**: 첫 화면이 운영 로그가 아니라 독자 요약(무엇이/얼마나 신뢰/무엇을 관전)을 먼저 답하도록 우선순위 재배치. 진단은 숨기지 않고 구조적으로 후순위로만 이동.
**Contract invariants**: idempotency guard = `수집/품질 진단` summary 존재 여부(2차 호출 no-op); 면책조항 footer는 고정(reflow는 header만 변경); compact status chip은 raw diagnostics로 취급하지 않음. CSS 추가 없음 — single-column document-order + Material 네이티브 `<details>`라 차트/요약 overlap 구조적 불가.
**Deduplication**: 새 요약 validator 없음. u51(TL;DR/H3/number-bold), u61(malformed-summary 검증/repair), u54/u62(status 값) 체인 **이후** 실행돼 재배치/절단만 수행 — malformed 값은 u61 fallback에 위임.
**Alternatives Considered**: 별도 first-viewport 페이지/위젯(static-site 비호환, 신규 의존성); 진단 완전 숨김(투명성 위배).

### TD-009: 큐레이션 컨텍스트-자산 라이브러리 (no-scraping hero, u86)

**Choice**: `assets/library/{person,topic,asset}/`에 사전 검수·라이선스 정리된 이미지를 **커밋**하고, 엔티티/토픽 키(`person:`/`topic:`/`asset:`)로 매핑한다(`visuals/curated.py`). 생성 시점에 세그먼트 인지 + 결정적 선택(`select_curated_asset`)으로 1개를 골라 `curated-context-image` hero로 `_HERO_PRIORITY`(`external-context-image > curated-context-image > ai-market-hero > data-confidence`)에 삽입한다. 매니페스트는 기존 `ExternalAssetManifest`(`kind="curated-licensed"`)를 재사용하고, 캡션/매니페스트는 기존 `provenance.py`로 작성한다.
**No-scraping guarantee**: `EXTERNAL_IMAGE_SCRAPING_ENABLED=False` 유지. 큐레이션 경로는 런타임 fetch 0 — 사전 커밋된 로컬 파일만 읽는다(AC-1.5). `assert_curated_asset_allowed`는 scraping 플래그를 읽지 않는 별도 분기다(R4).
**Deferred 상태 머신**: 매니페스트만 있고 바이너리가 없는 키는 **명시적 마커**(`allowed_use`의 `not-yet-available` 또는 `{asset_id}.deferred` 파일)일 때만 `deferred`로 허용(CI green, 선택 불가). 마커 없는 빈 항목은 `(invalid)` → CI 게이트 RED. `scripts/check_curated_assets.py`(stdlib, `check_no_paid_apis.py` 미러)가 게이트.
**Storage/secret**: filed 자산 ≤ 500 KB(raster)/≤ 64 KB(SVG), 라이브러리 총합 ≤ 20 MB, 100–2000 px(기존 게이트 재사용, pillow 미도입). 매니페스트 텍스트는 u27 redaction chokepoint 통과(R7/R13).
**Excluded**: 뉴스사진/짤방/기업 상표로고/실존인물 비공식 사진은 라이선스 게이트에서 거부.

### TD-010: 공개 문서 단일 finalization/seal 경계 (u144)

**Choice**: 기본 segmented production은 `publisher.public_document.finalize_public_bundle()`를 정확히 한 번 호출한다. 모든 Markdown producer와 deterministic repair는 E2 이전에 끝나며, terminal gate는 read-only다. 유효 문서는 `FinalizedPublicDocument` E5로 SHA-256 봉인되고 archive/index/OG/evidence/quality/replay/notifier consumer는 봉인된 bytes/DTO만 본다.
**Containment**: optional presentation defect는 region fallback/omission으로 격리하고 세그먼트를 제거하지 않는다. 실제 신뢰 위반만 `trust_blocked`; generation absence는 `generation_absent`다. survivor 변경 시 active `BundleContext`를 재계산하는 최대 3-pass fixed point를 사용한다.
**Artifact transaction**: 선택된 staged artifact만 E5 ID와 E6 promotion manifest를 거쳐 공개 위치로 승격된다. git 전 I/O 실패는 기존 byte snapshot으로 rollback하고, commit/push 이후는 기존 `PublisherGitError` 복구 계약을 따른다.

---

## Data Model

### NormalizedItem (Source 출력)
- `source_name: str`, `category: Literal[...]`, `title: str`, `summary: str | None`, `url: HttpUrl | None`, `published_at: datetime`, `raw_metadata: dict`

### Briefing (LLM 출력 + 메타)
- 7섹션 (`market_summary`, `key_issues`, `sector_flow`, `indicators_events`, `notable_tickers`, `today_watch`, `disclaimer`) + `rendered_markdown`

### FinalizedPublicDocument / PublicNotificationSummary
- `FinalizedPublicDocument`: segment/date, exact final Markdown bytes, SHA-256 seal, terminal notification DTO, selected artifact IDs를 갖는 immutable E5
- `PublicNotificationSummary`: final layout에서 파생된 conclusion/watchlist와 E1 typed coverage만 보유하며 notifier가 `Briefing.market_summary`를 다시 읽지 못하게 하는 경계

### BriefingNotification / FailureContext / SendResult / PipelineResult
- 채널 발송 페이로드, 실패 컨텍스트, Bot API 응답, 파이프라인 종료 상태
- `PipelineResult`는 기존 `PipelineStatus`와 별도로 `content_completeness`, canonical `segment_outcomes`, `publication_committed`를 제공한다.

자세한 정의는 `aidlc-docs/inception/application-design/component-methods.md`.

---

## Component Boundaries (DAG)

```
       orchestrator
       /  |   |   |  \
      v   v   v   v   v
  sources briefing publisher notifier
      \   |   |   /   /
       v  v   v  v  v
          models
```

- 4 working unit (sources / briefing / publisher / notifier)은 서로 import 금지
- `orchestrator`만 위 4개를 호출
- `models`는 모두에 의존되는 leaf
- 강제 방식: Convention only (코드리뷰 + 디렉토리 구조)

---

## Non-Functional Considerations

### Performance (NFR-001 ≤ 10분)
| Stage | Time budget |
|-------|-------------|
| collect | ≤ 4분 (asyncio.gather, 30s/source timeout) |
| generate | ≤ 4분 (two-stage with retry) |
| publish | ≤ 1분 (git push retry) |
| notify_briefing | ≤ 30초 |
| GH Actions overhead | ≤ 30초 |

### Cost (NFR-002 월 $0)
- LLM = Claude Code CLI only
- 데이터 = 무료 tier only
- public repo → GitHub Actions 무제한

### Reliability (NFR-003)
- Q9=B graceful degradation 다단계 (services.md 참조)
- 외부 호출은 timeout + retry

### Compliance (NFR-004)
- 면책조항 자동 append + 게시 직전 검증

### Security (NFR-007 baseline only — extension SKIP)
- 모든 시크릿은 GitHub Secrets
- 공개 채널 발송 메시지에 시크릿/PII 포함 검증
- public repo: 코드/시황 모두 공개, 시크릿만 비공개

---

## Construction Phase Plan (preview)

| Stage | Decision | Rationale |
|-------|----------|-----------|
| Functional Design | EXECUTE selectively (briefing + sources only) | LLM contract / plugin interface는 비자명 |
| NFR Requirements | EXECUTE | NFR-001~005 측정 가능 acceptance 필요 |
| NFR Design | SKIP | NFR Requirements 수준에서 흡수 |
| Infrastructure Design | SKIP | GitHub Actions YAML이 design 자체 |
| Code Generation | EXECUTE (always) | — |
| Build and Test | EXECUTE (always) | lint/type/unit/PBT partial |

상세는 `aidlc-docs/inception/plans/execution-plan.md`.

---

*Update this document as architectural decisions evolve during development. 큰 변경은 ADR(`docs/adr/NNNN-*.md`)로 별도 기록.*
