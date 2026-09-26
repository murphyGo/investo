# 2026-09-26 뉴스·이벤트 중심 시황 개발 설계

사용자 요청: “그럼, 해당 기획을 유닛으로 정리하고, 어떻게 개발할지 설계해줘”.

## 결과와 상태

u157–u162 여섯 유닛을 backlog로 등록하고 공통 데이터/실패/NFR 계약, 개별 Functional Design 초안과 code-generation plan을 작성했다. 문서 작성은 완료했으며 설계 사용자 승인, 제품 구현, 커밋/푸시, 운영 활성화는 수행하지 않았다.

[전체 설계](../../aidlc-docs/construction/news-event-briefing/README.md), [22건 검토 반영](../../aidlc-docs/construction/news-event-briefing/review-resolution.md).

## 기준과 격리

- 원격 기준: `04978d81ec9ece8f4083e4be190c6539bdf3b5ff`, 2026-09-26 확인.
- branch: `codex/news-event-design-20260926`.
- worktree: `.tmp/news-event-design-20260926`.
- root의 `.claude/settings.local.json`, `.claude/worktrees/`, `.workflow/`, `archive/_meta/fact_snapshots.jsonl` 기존 변경을 보존했다.
- u156은 별도 로컬 브랜치 이름을 예약된 소유권으로 존중했다. 그 committed tree에서 계획/구현을 확인하지 못했으므로 완료로 추정하지 않았다.
- 2026-09-22의 18편 검토를 설계 근거로 사용했다. 그 시점 이후 원인 관련 src/config/workflow 변화가 없음을 확인했다. 최신 18편 통계를 다시 낸 것으로 표현하지 않는다.

## 개발 순서

u157 선정·공통 발행 확인 → u158 사건 본문·요약 → u159 실제 최종 반영 검증을 첫 제품 단위로 통합한다. u160의 window/adapter 작업 및 u161 qualification은 병렬 가능하다. u160 cursor와 u161 typed 보강은 u157 이후, u162는 u157/u158/u152 이후다.

검증은 구조적 입력 보존, 실제 finalizer/봉인 DTO, 사람이 주석한 사건 의미 평가로 나눈다. 가격 기준일과 뉴스 관측기간을 분리하고 24h overlap, source completeness와 remote cursor를 명시했다. 기존 수치 검증과 u154/u156 소유권을 유지한다.

## 검증 범위

독립 에이전트 3명의 초안 검토 후 22개 의견을 반영했다. 부모 에이전트가 registry/AC/dependency/상대 링크/placeholder/문서 whitespace/변경 범위를 검사했다. 결과는 설계 디렉터리 `validation.json`에 기록한다. 제품 코드와 공개 사이트 소스를 바꾸지 않아 pytest/실제 LLM/발행 테스트와 MkDocs build는 수행하지 않았다.

공식 본문 source qualification은 미실행이며 HTTP 접근 가능성·권리·parser·fixture를 구현 전 따로 확인하도록 계획했다. 운영 shadow/preview/active의 검증을 코드 완료로 대체하지 않는다.
