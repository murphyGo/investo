# Event/news v3 native 구현 검증

2026-10-12 KST. 사용자 개발·나머지 계속 진행·커밋/푸시 지시의 범위에서 작업했다.
별도 워크트리 `.tmp/news-event-v3-dev-20261010`과 브랜치 `codex/news-event-v3-dev-20261010`을 사용했다.
기존 root의 작업 파일과 새 `docs/planning/`은 보존했다.

## 구현과 통합 기준

| 경계 | 결과 |
| --- | --- |
| native 구현 | `8532d90b` — schema 3 전체 generation/publication/acceptance tooling |
| 동시 UI·sector 통합 | `cf704b9a` — 원격 `55c00fc85e2828f62cd69d5583afd3761ef86d45`의 변경 보존 |
| 경계 수리 | `703bbb1d408c7c5f80e414de7c07ecbe7e674447` — context containment·quiet history·preview/Telegram/retention 경계 |
| 최종 코드 | `ca631e245d0341c09ea1671c32c4286dbd2c9c3a` — visible context 원문 locator 보존·중복 제거·접힌 참고 자료 |
| u168/u169/u170 | native 구현 단계 완료, 전체 실제 runtime 성능/운영 수용 별도 |
| u171 | consumer 구현, 실제 native viewport pending |
| u172 | 평가/replay/preview/cutover 감사 구현, 실제 사람·운영·cleanup pending |
| u173 | qualification model/checker/factory/conclusions/handoff 구현, private parser capture/source 준비 pending |

`EventEditionDraft`와 `PublicEditionView`는 legacy Briefing과 union의 다른 variant다. native 경로에 7개의
dummy fields나 여섯 free sections를 생성하지 않는다. 소유권·사실·시간·원본 주장 검증 후 기존 단일
`finalize_public_bundle`에서 renderer/projection/terminal gates/SHA seal을 수행한다.

identity의 actual/forecast/metric/unit/period/subject 결속, current source correction proof, fixed remote
baseline과 cumulative fact history를 사용한다. 새 source status와 story 상태는 source evidence에서 검증하며
부정·조건부 future completion을 actual resolution으로 바꾸지 않는다. 반복·TTL은 evidence clock을 갱신하지 않는다.

archive Markdown/sidecar/identity/story/news metadata는 기존 한 PublicationRequest/CAS와 remote ancestry
확인으로 묶는다. writer는 직렬화와 두 hash를 먼저 검사하고 pre-Git failure는 함께 복원한다.
sealed public source receipts에는 raw private chunk가 없다.

## reader와 실패 처리

HTML/알림/홈/주간·월간/OG/관심자산/시장별 archive는 typed terminal event를 읽는다.
새 u174–u179 HTML 카드·월별 archive 구조를 보존하면서 native digest→headline→availability를 연결했다.
sidecar 누락/변조는 상세 재추론 대신 제한으로 표시한다. 당시 story 상태·근거 시각을 최신 상태로 바꾸지 않는다.

관심자산 직접 영향은 fact subject, 간접 영향은 source의 명시된 affirmative relation으로 결속한다.
다른 문장/주체·부정·조건부 관계·ticker substring·price-only item은 확정 news impact를 만들지 않는다.
native E1 visual은 source fact 전체를 가진 light/dark SVG+provenance 3개이며 finalizer가 실제 used-only를 선택한다.
넓거나 긴 자료는 visual 전체를 제외하고 본문 사실은 유지한다. 다른 시장의 visual 실패는 유효 sibling을 없애지 않는다.

국내 numeric-only 처리 권한은 기존 `publisher/numeric_containment.py`가 가진다. original hard code가
numeric.anchor_assertion 하나일 때만 정확한 optional meaning/reaction 필드 전체를 unavailable로 바꾸고 witness를
남긴다. 조건부 mechanism/assumptions와 coincidence 경고도 같은 owner 범위다. 필수 fact/identity/headline/digest/story/anchor는
보호되며 미국·크립토 numeric hard failure는 계속 차단한다. 변경된 meaning의 간접 asset은 다시 계산하고 모든 terminal gate를 재실행한다.

Telegram은 상태·출처 시간·링크·면책을 먼저 예약하고 시장별 최대 3개의 완전한 사건 단위만 넣는다.
4096 UTF-16 한도와 더 작은 budget에서도 중간 절단을 하지 않는다. 공개/운영자 채널·retry·partial 정책은 기존 owner가 유지한다.

## 검증 결과

최종 full regression: **7,066 PASS, 1 skipped, 0 warnings (1166.32s)**, 코드 `ca631e245d0341c09ea1671c32c4286dbd2c9c3a`. 이전 중간 실행은 source 통합/수정 때문에 중단했으며 전체 PASS로 주장하지 않는다.
중간 helper/API seam 실패는 수정했고 이후 집중 회귀 211 PASS(198.60s)를 확인했다.

| 검사 | 결과 |
| --- | --- |
| native recorded replay | synthetic 57 cases, 12 groups, 3 markets; 실제 generation→sole finalizer→HTML/DTO/notification/story 대조 |
| 독립 QA | focused 166 PASS(4.01s), 최종 renderer regression 61 PASS와 실제 HTML 3건 PASS; 열린 P1/P2 0 |
| 추가 경계 | preview public-write0, UTF-16 whole-event, 국내 original hard gate/related asset, 180/90일 경계·200active/5MiB 초과 포함 22 PASS |
| Ruff / format | PASS, 775 files |
| mypy | PASS, 328 source files |
| 정책·source·docs gates | paid API / SDK / curated assets / image store / calendar / strict MkDocs / Material CSS+built HTML PASS |
| 차트 client behavior | Node 29 PASS |
| legacy historical output | 기존 v2 synthetic 25 cases PASS, terminal 24개 Markdown/HTML/알림 snapshot 고정; 파일 SHA f3688443d205abbf30689192c1775fa361eb948631f895c23f74a6c28e26d3d0 |
| git diff --check | PASS |

위 PASS는 자동 회귀와 구현 경계의 결과다. AI 합성 fixture는 human pending이며 현재 실제 corpus 0/12,
사람 review 0, source-slot verified 0/8, native viewport 미실행, genuine v3 scheduled 관찰 0회다.

## 실제 예산과 제한된 성능 측정

오프라인 1,000개 입력을 warm 10회 측정했다: preparation p95 38.631ms/median 37.112ms,
후보 24개·Stage1 retained 19개·실제 UTF-8 24,553 bytes. 4 documents/8 facts의 Stage2 protected payload는
15,588 bytes로 16KiB 안에 들어간다. source span/IDs/refs/time/header를 포함하며 required facts를 잘라 맞추지 않는다.
200active story ledger는 184,033 bytes, warm10 p95 19.789ms/median 4.546ms였다.
201active와 실제 직렬화 5MiB 초과는 explicit failure이며 silent eviction을 하지 않는다.

`tests/fixtures/event_briefing/terminal_snapshots.json`은 현재 v2 generator를 이용해 고정한 합성 historical output이다.
향후 cleanup의 read-only 회귀 준비이며 actual recording/human acceptance/legacy 제거 완료가 아니다.

이는 offline helper 측정이다. 실제 source collection→CLI→finalization→publish p95, 이전 baseline과 10% 회귀,
NFR-001 10분 목표의 수용은 미측정이다. DEBT-090을 완료로 변경하지 않았다.

## 배포·사람 수용 handoff

기본 schema 2/off, schema 3 preview, v3 active capability false를 유지한다. production pin/active allowlist,
새 HTTP, cursor 활성화와 legacy 최종 제거는 실행하지 않았다. 정확한 code/policy hash를 읽는
`check_event_cutover.py`는 상태만 보고하며 blocked를 활성화할 수 없다.

[번호별 AC 대조](../../../docs/cross-checks/2026-10-12-event-news-v3.md)는 56개 기준을 Complete/Partial/Pending으로
분리한다. [private 수용·전환 runbook](private-acceptance-and-cutover-runbook.md)과
[source-slot 결론](../u173-official-event-source-slot-qualification/qualification-conclusions.md)에 남은 owner와 실제 증거를 기록했다.
