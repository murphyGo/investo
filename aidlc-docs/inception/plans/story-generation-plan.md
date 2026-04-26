# Story Generation Plan: Investo

**Date**: 2026-04-26
**Role**: Product Owner (acting via AIDLC user-stories rule)

## Plan Overview

이 plan은 `docs/requirements.md`의 FR-001~FR-007 + NFR-001~NFR-007을 INVEST 기준의 user story 집합으로 변환하기 위한 단계별 체크리스트입니다. 각 [Answer]: 태그를 채워주시면 plan 승인 후 Part 2(생성 단계)에서 stories.md / personas.md를 작성합니다.

## Execution Checklist

### Part 1 — Planning (you are here)
- [x] Q1~Q8 모두 [Answer]: 채움 (2026-04-26, "all recommended")
- [x] Ambiguity follow-up 없음 확인 (옵션 letter 명확)
- [x] Plan 명시적 승인 ("all recommended")
- [x] FR-004 / FR-007 정합성 갱신 (Q1 결과 반영)

### Part 2 — Generation (after approval)
- [ ] `aidlc-docs/inception/user-stories/personas.md` 생성
- [ ] `aidlc-docs/inception/user-stories/stories.md` 생성
- [ ] 각 story가 INVEST(Independent, Negotiable, Valuable, Estimable, Small, Testable) 충족 확인
- [ ] 각 story에 acceptance criteria 포함
- [ ] Persona ↔ Story 매핑 추가
- [ ] aidlc-state.md 업데이트, audit.md 기록
- [ ] Stories 명시적 승인

---

## Embedded Questions

### Q1: User Personas — 페르소나 범위

가정한 페르소나는 다음 두 개:
- **Operator-User**: 본인. 시스템 운영자이자 1차 사용자. 매일 텔레그램 푸시로 시황을 받고, 필요 시 GitHub Pages에서 전체 시황을 본다. 데이터 소스 추가/제거, 실패 디버깅, 시황 포맷 조정 같은 운영도 담당. 시스템 실패 알림(FR-007)을 받는 유일한 페르소나.
- **Public Reader**: 본인이 GitHub Pages URL을 공유한 지인 또는 우연히 사이트를 발견한 익명 방문자. 인증 없이 **웹에서 시황을 열람**하며, 추가로 **텔레그램 채널/그룹에 직접 참여하면 시황 푸시 알림도 수신 가능** (옵션). 운영/실패 알림은 받지 않고 시황 본문만 받음.

> **아키텍처 영향**: Public Reader가 텔레그램을 받을 수 있으려면 FR-004 발송 대상이 "1:1 chat"이 아닌 **public Telegram 채널 또는 그룹**이어야 합니다. 현재 `docs/requirements.md` FR-004 acceptance criteria는 "단일 chat (1:1 또는 채널 — 구현 시 확정)"으로 두 옵션을 모두 열어두고 있는데, 이번 결정으로 **공개 채널 방향으로 좁혀집니다**. requirements.md 업데이트 여부는 Plan 승인 시 함께 처리.

A) 위 두 페르소나로 충분 (Public Reader = web 열람 + 텔레그램 채널 옵션 구독)
B) Public Reader를 분리할 필요 없다 (본인 외에는 사실상 없을 것)
C) 추가 페르소나 필요 (예: "텔레그램만 받는 구독자"를 Public Reader와 별도로)
X) 기타 (자유 기술)

[Answer]: A (사용자가 "Public Reader도 텔레그램 알림 받을 수 있음을 명시" 요청 후 "all recommended" 승인)

---

### Q2: Story Granularity — 스토리 크기

A) **세분화** — FR 1개 → 2~3개 작은 스토리 (예: FR-001을 "뉴스 수집", "시세 수집", "지표 수집"으로 분할). 총 ~15개 스토리.
B) **균형** — FR 1개 → 1개 스토리 (총 7~10개). 하위 시나리오는 acceptance criteria로 분할. **권장**.
C) **느슨** — 가치 단위로 묶음 (예: "데일리 시황 받기"라는 하나의 큰 스토리). 총 3~5개.

[Answer]: B (균형, FR당 1개 + NFR 일부 별도 = 약 9개)

---

### Q3: Story Format — 포맷

A) **표준 INVEST 포맷** + Gherkin 스타일 acceptance criteria (Given/When/Then). 가독성 우수.
B) **표준 INVEST 포맷** + 체크리스트 acceptance criteria ([ ] criterion). 작성·관리 단순. **권장** (이미 requirements.md가 이 포맷).
C) Job Story 포맷 ("When [상황], I want to [동기], so I can [결과]"). 페르소나 강조 약함.

[Answer]: B (체크리스트 AC, requirements.md와 일관)

---

### Q4: Breakdown Approach — 조직 방식

A) **Feature-Based** — FR ID에 1:1 매핑. requirements.md 추적성 최고. **권장**.
B) **User Journey-Based** — 운영자 하루 흐름(스케줄 트리거 → 수집 → 작성 → 게시 → 알림 → 모니터링) 순서.
C) **Persona-Based** — Operator 스토리 vs Reader 스토리로 그룹.
D) **Hybrid** — 1차로 Persona, 2차로 Feature.

[Answer]: A (Feature-Based, US-ID ↔ FR-ID 1:1)

---

### Q5: Acceptance Criteria Detail — 상세도

A) **요약** — 핵심 동작 검증만 2~3개씩.
B) **표준** — 정상 흐름 + 주요 실패 흐름 + NFR 연결 4~6개씩. **권장**.
C) **상세** — 모든 엣지 케이스를 포함 (테스트 시나리오 1:1).

[Answer]: B (표준 — 정상 + 주요 실패 + NFR 연결)

---

### Q6: NFR 매핑 방식 — 비기능 요구사항을 스토리에 어떻게 녹일지

A) **별도 NFR 스토리 추가** — "운영자로서 시황 생성 실패 시 알림을 받고 싶다"처럼 NFR-003/FR-007을 독립 스토리로.
B) **기존 스토리의 acceptance criteria로 흡수** — 예: 시황 작성 스토리의 AC에 "면책조항 자동 삽입(NFR-004)" 포함. 스토리 수 적게.
C) **A + B 혼합** — 운영성/모니터링 NFR은 별도 스토리, 컴플라이언스/포맷 NFR은 AC로 흡수. **권장**.

[Answer]: C (혼합)

---

### Q7: User Journey 명시 — 별도 journey 다이어그램이 필요한가?

A) **필요** — `aidlc-docs/inception/user-stories/journeys.md`를 추가로 생성하여 운영자의 하루 흐름을 시각화.
B) **불필요** — stories.md 안에 짧은 narrative 한 단락이면 충분. **권장** (1인 사용 + 파이프라인이 단순)
C) 다른 형태 (자유 기술)

[Answer]: B (별도 journey 문서 불필요 — stories.md 안에 한 단락 narrative)

---

### Q8: 추가 비즈니스 컨텍스트 — 스토리에 반영해야 할 것

지금까지 식별된 컨텍스트:
- 운영비 월 $0 (NFR-002)
- 면책조항 자동 삽입 의무 (NFR-004)
- 한국시간 평일 오전 7시 + 토요일 (FR-005)
- public repo 운영 (시크릿만 비공개)

추가로 스토리에 명시되어야 할 비즈니스 제약/목표가 있나요?

A) 없음, 위 4개로 충분
B) 추가 있음 (자유 기술 — 예: 특정 종목 워치리스트, 특정 시간대 추가, 외부에 공유 URL 디자인 요구 등)

[Answer]: A (식별된 4개로 충분)

---

## Story Approach Options Reference

위 Q4에서 권장한 Feature-Based 외에 비교용:

| Approach | Pros | Cons | Fit for Investo |
|----------|------|------|-----------------|
| Feature-Based | requirements.md 추적성 최고, 1:1 매핑 단순 | 사용자 여정이 흐릿 | **High** (단일 페르소나 중심이라 여정이 단순) |
| User Journey-Based | 워크플로우 가시화 | 페르소나 적으면 중복 | Medium |
| Persona-Based | 다중 페르소나 강조 | 본 프로젝트는 페르소나 적음 | Low |
| Domain-Based | 큰 시스템 정리 | 본 프로젝트는 도메인이 단일 | Low |
| Epic-Based | 단계적 확장에 유리 | 현재 MVP에는 과함 | Low (확장 시 재검토) |

---

## How to Fill Answers

각 Q1~Q8 섹션의 `[Answer]:` 다음에 직접 답을 적어주세요. 옵션 letter (A/B/C 등) 또는 자유 텍스트 모두 가능. 모두 채워지면 ambiguity 분석 후 plan 승인 단계로 진행합니다.
