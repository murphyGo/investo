# Application Design Plan: Investo

**Date**: 2026-04-26
**Stage**: Stage 1 Step 12 (Application Design — Planning)
**Inputs**: docs/requirements.md (FR/NFR), aidlc-docs/inception/user-stories/{stories,personas}.md, aidlc-docs/inception/plans/execution-plan.md (5-component sketch)

---

## Plan Overview

Workflow Planning에서 도출된 5컴포넌트 sketch(Source Adapters / Briefing Generator / Publisher / Notifier / Orchestrator)를 출발점으로, 각 컴포넌트의 책임/메서드/의존성/오케스트레이션 패턴을 확정합니다. 본 plan에 임베드된 [Answer]: 태그를 모두 채워주시면 `application-design/` 디렉토리에 5개 산출물을 생성합니다.

## Execution Checklist

### Part 1 — Planning (you are here)
- [x] Q1~Q9 모두 [Answer]: 채움 (2026-04-27, "전부 권장으로 가자")
- [x] Ambiguity 분석: Q1=A vs Q8=B 표면적 충돌 → "5 컴포넌트 유지 + Notifier 컴포넌트 안에 BriefingPublisher/OperatorAlerter 두 클래스"로 reconcile
- [x] Plan 명시적 승인 ("전부 권장으로 가자" = approve)

### Part 2 — Generation (after approval)
- [ ] components.md 생성 (5개 컴포넌트 + 책임 + 인터페이스)
- [ ] component-methods.md 생성 (메서드 시그니처, 입출력 타입)
- [ ] services.md 생성 (오케스트레이션 / 트랜잭션 경계)
- [ ] component-dependency.md 생성 (의존 매트릭스 + 데이터 흐름)
- [ ] application-design.md 생성 (위 4개 통합 문서)
- [ ] aidlc-state.md / audit.md 업데이트
- [ ] Application Design 명시적 승인

---

## Embedded Questions

### Q1: Component Identification — 컴포넌트 구성

Workflow Planning에서 잠정 식별한 5컴포넌트:
1. **Source Adapters** (plugin) — 외부 무료 데이터 소스별 fetcher (US-001, US-008)
2. **Briefing Generator** — 수집 데이터 → Claude Code CLI → 7섹션 markdown (US-002, US-009)
3. **Publisher** — markdown 저장 + MkDocs 빌드 + git commit + Pages 배포 (US-003, US-006)
4. **Notifier** — 텔레그램 채널/Operator chat 디스패치 (US-004, US-007)
5. **Orchestrator** — GitHub Actions YAML + Python entrypoint (US-005)

A) **위 5개 그대로 유지** **(권장)** — 책임 경계 명확, 5개는 1인 솔로에게 적당.
B) **Publisher 분할** — `MarkdownArchiver`(파일/git) + `SiteBuilder`(MkDocs) 둘로. Publisher 내부 책임이 다소 다름.
C) **Notifier 분할** — `BriefingPublisher`(공개 채널) + `OperatorAlerter`(1:1 chat) 둘로. 채널 분리(FR-004 vs FR-007)를 컴포넌트 수준에서 강제.
D) **B + C 둘 다 분할** — 총 7개 컴포넌트.
E) **단순화** — Publisher와 Notifier를 합쳐 `OutputDispatcher` 1개로 (총 4개).

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q2: Source Adapter — Plugin 인터페이스

각 데이터 소스가 구현할 공통 인터페이스 옵션:

A) **Protocol/ABC 기반 동기 인터페이스**:
```python
class SourceAdapter(Protocol):
    name: str
    category: Literal["news","price","macro","calendar","earnings"]
    def fetch(self, target_date: date) -> list[NormalizedItem]: ...
```
구현 단순. asyncio 미사용 → 직렬 수집 시 latency 큼.

B) **Protocol 기반 async 인터페이스 (권장)**:
```python
class SourceAdapter(Protocol):
    name: str
    category: Literal[...]
    async def fetch(self, target_date: date) -> list[NormalizedItem]: ...
```
`asyncio.gather`로 동시 수집 → 10분 한도(NFR-001) 여유. httpx와 자연스럽게 결합.

C) **Generator 기반** — `async def fetch(...) -> AsyncIterator[NormalizedItem]`. 스트리밍에 좋으나 본 도구는 배치라 과함.

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q3: NormalizedItem 데이터 모델 위치

각 Source Adapter 출력의 공통 정규화 타입을 어디에 둘지:

A) **단일 `models/` 모듈에 중앙화** **(권장)** — `NormalizedItem`, `Briefing`, `NotificationPayload` 등을 한 곳에 모음. pydantic v2 모델.
B) **각 컴포넌트별로 분산** — Source/Briefing/Notifier 각자 자신의 dataclass 정의. 결합도는 낮으나 타입 변환 보일러플레이트 증가.
C) **dataclass + TypedDict 혼합** — 내부는 dataclass, 직렬화 경계만 pydantic.

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q4: Briefing Generator — Claude Code 호출 방식

GitHub Actions에서 Claude Code CLI를 호출하는 구체적 패턴:

A) **subprocess.run(claude -p ...)** **(권장)** — `claude` CLI를 비대화형(`-p`)으로 호출, prompt는 stdin/-p arg, 출력은 stdout. 단순. CLI는 Action에서 별도 install step으로 준비.
B) **Claude Code SDK (Node)** — npm `@anthropic-ai/claude-code` 사용. Python 프로젝트에 Node 의존성 추가 → 복잡도 증가.
C) **Claude Code Python SDK가 있다면 그것** — 현재 공식 Python SDK 미존재 가정. 추후 등장 시 마이그레이션 옵션.
X) 기타 (자유 기술)

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q5: Briefing Generator — Prompt/Output 구조

A) **Single-shot prompt** — 모든 NormalizedItem을 한 번에 LLM에 전달, 7섹션 markdown 출력 받음. 단순. 컨텍스트 폭발 위험.
B) **Two-stage prompt (권장)** — 1차: 수집 데이터를 섹션별로 분류/요약 (LLM). 2차: 분류 결과를 7섹션 시황으로 통합 (LLM). 토큰 효율 + 품질↑.
C) **Templating + LLM hybrid** — 정형 섹션(지표·이벤트)은 코드로 생성, 분석 섹션(이슈·관전포인트)만 LLM. 면책조항은 자동 append.
X) 기타

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q6: 면책조항 강제 삽입 메커니즘

NFR-004는 면책조항 자동 삽입을 의무화. 구현 방식:

A) **Briefing Generator가 출력 후 자동 append (권장)** — LLM 출력 끝에 별도 disclaimer 블록을 코드로 붙임. 누락 불가능. 내용은 코드 상수.
B) **Prompt에 disclaimer 작성을 요청** — LLM이 직접 작성. 누락 위험 → A에 비해 약함.
C) **A + Validation** — A 방식 + Publisher가 게시 전 disclaimer presence 검증, 없으면 게시 차단.

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q7: Publisher / Archive 구조

`archive/YYYY/MM/YYYY-MM-DD.md` 저장 + MkDocs 빌드 + GitHub Pages 배포 흐름:

A) **단일 워크플로우 1 step** — Publisher가 markdown write → mkdocs build → git add/commit/push 직접 수행. Python에서 git CLI subprocess.
B) **GitHub Actions 단계 분리 (권장)** — Python Publisher는 markdown write까지만. 이후 mkdocs build / actions/deploy-pages는 GitHub Actions 표준 step으로 분리. 책임 분리 + GitHub 네이티브 활용.
C) **Branch 분리 (gh-pages)** — main에 markdown, gh-pages에 빌드 산출물. peaceiris/actions-gh-pages 등 사용. 표준 GitHub Pages 패턴이지만 step 더 많음.

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q8: Notifier — 발송 대상 분리 강제

A) **단일 Notifier 클래스 + channel param** — `notify(payload, channel: Literal["briefing","operator"])`. 코드 단순, 분리 강제는 호출자 책임.
B) **컴포넌트 분할 (Q1 옵션 C와 동일)** — `BriefingPublisher` / `OperatorAlerter` 별 클래스. 채널 분리 컴파일 타임 강제. **(권장)** — FR-004와 FR-007 분리 의도와 일치.
C) **단일 Notifier + 정적 분리 메서드** — `notifier.send_briefing(...)`, `notifier.send_alert(...)` 두 메서드만 노출. 클래스는 1개.

[Answer]: (per "all recommended" — see consolidated answer block below)

---

### Q9: Orchestrator — Pipeline 흐름과 에러 정책

수집 → 시황 작성 → 게시 → 알림 흐름의 에러 처리:

A) **Fail-fast** — 어느 단계든 예외 발생 시 즉시 중단 + Operator 알림. 단순하나 단일 소스 장애로도 시황 누락.
B) **Graceful degradation (권장)** — 다단계 fault tolerance:
   - Source 단계: 개별 소스 실패는 로그 + 해당 카테고리 일부 데이터로 진행 (NFR-003, US-001 AC)
   - Generator 단계: LLM 실패는 retry → 최종 실패 시 게시 중단 + Operator 알림 (시황 게시 X)
   - Publisher 단계: git push 실패는 retry, MkDocs 빌드 실패는 기존 사이트 유지
   - Notifier 단계: 채널 발송 실패는 게시 자체를 막지 않음 (US-004 AC)
C) **Circuit breaker** — 외부 호출에 모두 circuit breaker. 본 도구 규모엔 과함.

[Answer]: (per "all recommended" — see consolidated answer block below)

---

## Design Pattern Reference (informational)

| Pattern | Where | Notes |
|---------|-------|-------|
| Plugin Registry | Source Adapters | 단일 모듈 추가 + registry 한 줄 (US-008 AC) |
| Strategy / Protocol | Source Adapter, Notifier | duck typing + Protocol으로 ABC 회피 |
| Pipeline | Orchestrator | 단계별 함수 합성, 각 단계는 순수 함수에 가깝게 |
| Result type | 단계 간 반환 | `Result[T, E]` 또는 raises + try-except (Python 표준) |
| Pydantic v2 | NormalizedItem, Briefing, NotificationPayload | 직렬화 + PBT round-trip 대상 |

---

## How to Fill Answers

각 Q1~Q9 섹션의 `[Answer]:` 다음에 **letter (A/B/C..)** 또는 자유 텍스트로 답변. 권장안에 모두 동의하시면 **"all recommended"** 한 줄로 진행 가능합니다.

---

## Consolidated Answers (recorded 2026-04-27)

User: "전부 권장으로 가자" (all recommended)

| Q | Answer | Decision |
|---|--------|----------|
| Q1 | A | 5 컴포넌트 유지 (sources / briefing / publisher / notifier / orchestrator) |
| Q2 | B | Source Adapter는 async Protocol (`async def fetch(target_date) -> list[NormalizedItem]`) |
| Q3 | A | NormalizedItem 등 공통 타입은 `models/` 단일 모듈에 중앙화, pydantic v2 |
| Q4 | A | Claude Code CLI 호출은 `subprocess.run(["claude", "-p", ...])` 패턴 |
| Q5 | B | Two-stage prompt — 1차 분류/요약, 2차 7섹션 통합 |
| Q6 | A | Disclaimer는 Briefing Generator가 출력 후 코드로 자동 append |
| Q7 | B | Python Publisher는 markdown write + git commit까지. mkdocs build / Pages 배포는 GitHub Actions step. |
| Q8 | B | Notifier 컴포넌트 안에서 클래스 분할: `BriefingPublisher` (공개 채널, FR-004) + `OperatorAlerter` (1:1 chat, FR-007) |
| Q9 | B | Graceful degradation 다단계 — Source 부분 실패 허용, Generator 실패는 게시 차단, Publisher git 실패는 retry, Notifier 실패는 게시를 막지 않음 |

### Reconciliation note (Q1 vs Q8)
"5 components 유지"(Q1=A)와 "BriefingPublisher / OperatorAlerter 분할"(Q8=B)은 component-level 명칭과 class-level 명칭의 차이이므로:
- **Component name**: `notifier` (5개 중 하나로 유지)
- **Inside `notifier/`**: 두 개의 client 클래스 — `BriefingPublisher`(공개 채널 발송) + `OperatorAlerter`(운영자 알림)
- 외부에서 보면 두 별도 진입점, 컴포넌트 카운트는 5 유지.

### Disclaimer 보강 (Q6 권장 + 안전 보강)
Q6=A 채택. 추가 보강으로 Publisher의 acceptance criterion에 "게시 전 disclaimer presence를 string 검증"을 포함 (검증 실패 시 Publisher가 게시 차단 → Operator alert). 이는 Q6 옵션 C의 정신에 해당하나 별도 컴포넌트 추가 없이 Publisher AC로 흡수.
