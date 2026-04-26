# Unit-of-Work Plan: Investo

**Date**: 2026-04-27
**Stage**: Stage 1 Step 13 (Units Generation — Planning)
**Inputs**:
- aidlc-docs/inception/application-design/{components,application-design}.md (5 components)
- aidlc-docs/inception/user-stories/stories.md (US-001~US-009)
- aidlc-docs/inception/plans/execution-plan.md (per-unit Functional Design strategy preview)

---

## Plan Overview

Investo는 **단일 deployable Python 패키지(monolith)**로 구성됩니다. 본 단계에서는 5개의 Application Design 컴포넌트를 어떻게 **개발 단위(units of work)**로 묶고, 어떤 순서로 incremental delivery 할지 결정합니다. 본 plan에 임베드된 [Answer]:를 채우시면 `application-design/`에 unit-of-work.md, unit-of-work-dependency.md, unit-of-work-story-map.md를 생성합니다.

## Execution Checklist

### Part 1 — Planning (you are here)
- [x] Q1~Q5 모두 [Answer]: 채움 (2026-04-27, "all recommended")
- [x] Ambiguity 분석: 없음 (옵션 letter 명확)
- [x] Plan 명시적 승인 ("all recommended")

### Part 2 — Generation (after approval)
- [ ] unit-of-work.md (단위 정의 + 책임 + 코드 조직 전략)
- [ ] unit-of-work-dependency.md (단위 간 의존 매트릭스 + 빌드/딜리버리 순서)
- [ ] unit-of-work-story-map.md (US-001~US-009을 단위에 1:1 매핑)
- [ ] aidlc-state.md / audit.md 업데이트
- [ ] Units Generation 명시적 승인

---

## Embedded Questions

### Q1: Unit Grouping — 단위 수와 그룹핑

Application Design의 5개 컴포넌트를 어떻게 단위로 묶을지:

A) **5 units, 1:1 with components (권장)** — `u1-sources / u2-briefing / u3-publisher / u4-notifier / u5-orchestrator`. Story↔Unit↔Component 추적성 최고. 각 unit이 작아 incremental PR이 자연스러움.
B) **3 units** — `u1-collector` (sources+models), `u2-processor` (briefing), `u3-output` (publisher+notifier+orchestrator). 운영 단계별로 묶음. unit 간 결합도 줄어드나 unit 안 변경 폭이 큼.
C) **2 units** — `u1-pipeline` (sources+briefing+publisher), `u2-channels` (notifier+orchestrator). 너무 거침. 1인 솔로에게도 단위 추적 약화.
D) **5 units이지만 models는 별도 zero-th unit** — `u0-models / u1-sources / ... / u5-orchestrator`. 의존 트리에서 leaf인 models를 기반으로 명시.
X) 기타 (자유 기술)

[Answer]: (per "all recommended" — see consolidated block below)

---

### Q2: Delivery Order — 단계적 개발 순서

솔로 개발이라 한 unit씩 완성·검증하는 incremental delivery가 자연스럽습니다. 권장 순서 (Q1=A 가정):

**권장 (A)**:
```
0. models (스토리 없음, 다른 unit의 prerequisite)
1. u1 sources       — US-001, US-008. 가장 외부 의존이 많고 PoC 가치 큼.
2. u2 briefing      — US-002, US-009. sources 산출물을 입력으로 LLM 통합 검증.
3. u3 publisher     — US-003, US-006. 게시 + 영구 보관 검증.
4. u5 orchestrator  — US-005. (u4 전에) 파이프라인 hook + 에러 정책 backbone 구축.
5. u4 notifier      — US-004, US-007. 외부 노출 채널은 마지막에. (앞 단계 안정 후 발송)
6. (인프라 step) GitHub Actions cron + mkdocs build + Pages deploy 활성화.
```

옵션:
A) **위 권장 순서 채택**
B) 순서 변경 — 자유 기술 (예: notifier를 먼저 만들어 alert 채널 검증)
C) **수직 슬라이스** — 각 sprint마다 5 unit 모두 가벼운 버전을 동시에 진행 (1인 솔로엔 비효율)

[Answer]: (per "all recommended" — see consolidated block below)

---

### Q3: Code Organization — 디렉토리/패키지 구조

Greenfield 단일 deployable이라 microservices가 아닌 **monolith with logical modules**.

A) **단일 Python 패키지 (권장)**:
```
investo/                       # repo root
├── pyproject.toml             # 프로젝트 메타 + deps
├── README.md
├── mkdocs.yml                 # Pages site config
├── docs/                      # mkdocs source (인덱스, about 등)
├── archive/                   # 시황 markdown 영구 저장 (YYYY/MM/...)
├── src/
│   └── investo/
│       ├── __init__.py
│       ├── __main__.py        # python -m investo entry
│       ├── models/
│       ├── sources/
│       ├── briefing/
│       ├── publisher/
│       ├── notifier/
│       └── orchestrator/
├── tests/
│   ├── unit/                  # per-module
│   ├── integration/           # cross-module
│   └── fixtures/              # LLM record/replay, sample API responses
├── .github/
│   └── workflows/
│       ├── daily-briefing.yml # cron trigger
│       └── pages.yml          # site build/deploy
└── aidlc-docs/, aidlc-workflows/, docs/   (기존 그대로)
```

B) **flat module (no src/)** — `investo/sources/...`로 repo 루트에 직접. tests/는 동일. 단순하나 import isolation 약함.
C) **multi-package monorepo** — `packages/sources`, `packages/briefing` 등. 1인 솔로엔 과함.

[Answer]: (per "all recommended" — see consolidated block below)

---

### Q4: Module Boundary Enforcement — 단위 간 import 규칙

Application Design DAG: orchestrator만 4개 unit을 호출하고, 4개 unit은 서로 import 금지 (모두 models만 공유). 강제 방법:

A) **Convention only (권장)** — 코드 리뷰 + 디렉토리 구조로 충분. import linter 미도입.
B) **import-linter** 도입 — `importlinter` 패키지로 contracts 정의 (`forbidden:` rules). Layered architecture 강제. 셋업 부담 약간.
C) **Architectural test** — pytest 안에 `test_no_cross_unit_imports.py`로 ast 분석. 가벼움.
X) 기타

[Answer]: (per "all recommended" — see consolidated block below)

---

### Q5: Test Boundaries — 단위별 테스트 전략

A) **Unit-level + 단일 통합 테스트 (권장)**:
- `tests/unit/<unit_name>/` — 각 unit의 메서드 단위 테스트. mock 활용. PBT(hypothesis)는 models 직렬화/순수 함수에만.
- `tests/integration/test_pipeline.py` — orchestrator를 entrypoint로 한 전체 파이프라인 mocked 통합 테스트 (실제 외부 호출 X).
- LLM/외부 API: `tests/fixtures/` 안에 record/replay 데이터.
B) **Unit only** — 통합 테스트 생략, 실제 cron 실행이 곧 통합 테스트. 솔로 small-scope에선 가능하지만 회귀 위험.
C) **End-to-end만** — 실제 외부 API 호출 포함. 무료 API rate limit + 비결정성으로 CI에 부적합.

[Answer]: (per "all recommended" — see consolidated block below)

---

## Plan Summary Reference

| Aspect | Recommendation |
|--------|----------------|
| Unit count | 5 units (1:1 with components) + zero-th models |
| Deployment | Single Python package, GitHub Actions runner |
| Delivery order | models → sources → briefing → publisher → orchestrator → notifier → infra |
| Directory style | `src/investo/` layout |
| Boundary enforcement | Convention + code review |
| Test strategy | unit/integration split + LLM fixture |

---

## How to Fill Answers

각 Q1~Q5 섹션의 `[Answer]:` 다음에 letter 또는 자유 텍스트 답변. 권장안에 모두 동의하시면 **"all recommended"** 한 줄로 진행 가능.

---

## Consolidated Answers (recorded 2026-04-27)

User: "all recommended"

| Q | Answer | Decision |
|---|--------|----------|
| Q1 | A | 5 units, 1:1 with components. `models`는 unit이 아닌 shared foundation library |
| Q2 | A | 권장 순서 채택: (0) models → (1) sources → (2) briefing → (3) publisher → (4) orchestrator → (5) notifier → (6) infra/CI |
| Q3 | A | `src/investo/` layout, 단일 Python 패키지 |
| Q4 | A | Convention only — 코드리뷰 + 디렉토리 구조로 강제. import-linter 미도입 |
| Q5 | A | tests/unit/<unit_name>/ + tests/integration/test_pipeline.py + tests/fixtures/ (LLM record/replay) |
