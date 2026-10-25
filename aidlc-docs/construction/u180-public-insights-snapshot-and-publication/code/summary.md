# u180 구현 및 검증

2026-10-12 · 기준 `55c00fc85e2828f62cd69d5583afd3761ef86d45` · 격리 worktree `codex/public-insights-unit-design-20261012`의 미커밋 변경.

사용자 “유닛 하나씩 진행시켜” 지시로 u180 설계를 채택하고 공통 데이터·이력·게시 기반을 구현했다. 매크로 화면 u181의 선행 코드가 마련됐다. 운영 Step 8은 후속 모듈 및 배포·예약 실행 수용 이후 완료한다. 기본 모드는 `off`, 실제 source qualification은 빈 목록이다.

## 변경

- `models/insights.py`: immutable source/private/public 타입, finite Decimal, 단위·시간·provider/정의 검증, current/history/manifest 식별자와 파일 크기 제한. 제한된 이력은 compact row와 스트리밍 canonical JSON을 사용한다.
- `sources/_window.py`, `sources/aggregator.py`, `orchestrator/pipeline.py`: 기존 수집 한 번에서 opt-in envelope를 캡처한다. 실제 어댑터 origin과 source outcome을 보존하고, 기존 enrichment/LLM/serializer에 전달하기 전에 envelope를 제거한다. 기본 직렬화와 기존 source registry를 유지한다.
- `orchestrator/insights*.py`: 공개·Git 보관·분석 이력 권한을 각각 검증한다. 원격에서 확인한 last-good만 재사용한다. source-specific 2026 calendar, 미래/미지원 clock, provider 변경, 비활성 모듈의 권한 철회를 처리한다. 다른 모듈의 source 장애는 정상 모듈의 상태에 섞이지 않는다.
- `publisher/insights/store.py`: current/index/history/manifest를 같은 스냅샷으로 준비하고 fsync journal/backup, 프로세스 lock, 무결성 검증과 rollback/recovery를 제공한다. 관계없는 파일·기존 index를 보존하며 변경된 파일이나 손상된 backup을 덮어쓰지 않는다.
- 기존 publication receipt/CAS를 재사용한다. manifest만 metadata CAS 대상으로 지정하고, 검증한 커밋 내용과 remote ancestry를 확인한다. unknown/pending은 성공 또는 이력 baseline이 되지 않는다.
- collection 후·시황 생성 전에 독립 게시를 수행한다. 이후 LLM 실패에도 확인한 인사이트 결과를 보존한다. optional GHA 출력과 기존 private runtime template의 Pages 조건을 연결하며 기존 종료코드를 유지한다.

## 검증

전체 suite checkpoint는 **6,987 passed / 1 known skipped**이다. 이후 보완한 lifecycle/resource 코드에는 관련 회귀 704개 및 최종 scoped suite **173 passed / 42.52s**를 실행했다. 정확한 명령·검증 시점·최종 결과는 [validation.json](validation.json), [AC 대조](../../../../docs/cross-checks/2026-10-12-u180-public-insights-foundation.md)에 기록한다.

Ruff/format, mypy 319 source files, 비용·SDK·asset/image guards, strict MkDocs, Material/Calendar contracts, actionlint를 통과했다. actionlint는 설치되지 않은 shellcheck를 제외하고 실행했다. 기존 sector schema2 데이터 이행으로 인한 skip을 새 통과로 계산하지 않는다.

[재현 가능한 자원 시험](../../../../scripts/benchmark_insights_resource.py)은 합성 64 지표·128 일정·8,013,025B 이력을 준비하고 별도 프로세스에서 실제 `_phase`의 새 커밋·로컬 bare Git push·remote confirmation을 실행한다. 추가 RSS 96MiB, CPU 5초, phase 60초 기준을 통과했다. 최신 수치는 [resource-evidence.json](resource-evidence.json)에 있다. 이 기록은 provider 원천/권리 또는 실서비스 성능 증거가 아니다.

독립 초기 리뷰의 crash-after-add High를 수정했고 최종 미해결 Critical/High/Medium은 0이다. [초기 리뷰](review-initial.md), [최종 재검토](review-final.md)로 범위와 증거를 구별한다. 세부 세션은 [session log](../../../../docs/sessions/2026-10-12-u180-public-insights-foundation.md)에 있다.

## 남은 운영 수용

u181→u182→u183 순서로 실제 metric/event envelope와 화면을 구현한다. 정확한 provider 공개·Git 보관·이력 보관 근거와 실제 source 응답을 확인한 정의만 활성화한다. 그 뒤 reviewed private pin/mode, 해당 SHA의 Pages와 5회 예약 실행을 확인한다. 현재 commit/push·실서비스 배포·mode/pin 변경·추가 알림은 수행하지 않았다. DEBT-090 및 기존 유닛의 운영 gate는 보존한다.
