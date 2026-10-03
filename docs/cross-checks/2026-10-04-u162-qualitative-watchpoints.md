# u162 요구사항 대조

판정: **APPROVE — 코드 범위 fixed contracts 7개, AC 5개 충족**. 기준 u152 `82c4e072`. 승인 계약을 실제 최종 문서 경로에 대조했다.

| 기준 | 구현·증거 |
|---|---|
| AC-162.1 | 실제 source-addressed 협상/법안/서비스 fixture가 숫자 없는 상태 카드로 봉인된다. |
| AC-162.2 | EventFact와 scheduled next-check 분리, unsupported 숫자 문장 재분류 없음, raw §⑥ 및 카드 hard finding에 sibling 보존. |
| AC-162.3 | 실제 mixed 1+1/event-only2, event0 numeric6/fallback2; 기존 aggregate 제약과 private kind count 검증. |
| AC-162.4 | 조립 후 partial/all 사건 삭제가 카드·요약에 반영되고, all-removed numeric6 복원 후 repeated bytes/digest/DTO/companion 동일. |
| AC-162.5 | off/empty numeric byte 비교, unknown/missing source·meaning 제외, 실제 compliance 및 supplements/disclaimer 검증. |

Fixed contracts 1–7은 각각 명시적 numeric/event union, source-backed 현재 상태, same-event 예정 fact/닫힌 next-check 문구, 기존 숫자 gate 유지, mixed/event-only cap과 numeric 복원, private CompanionOutcome, bounded pre-seal repair 및 no-source 구분으로 구현했다. 유효 detail_limited 사건과 실제 source locator 누락을 구분하며, 숨김/HTML literal 카드와 terminal 이후 출처 삭제를 실제 finalizer에서 차단한다.

최종 실제 finalizer 독립 **24개**, 통합 focused **222개**, 전체 **6087개/460.18s** 통과. 교차 리뷰 P2 두 건은 원래 반례와 독립 음성·양성 대조로 종결했다. Ruff/format661/mypy290, 정책4, strict docs/Material 모두 통과했다. 공통 event benchmark p95 **122.515ms/200ms**는 selection/receipt/v2 parser/renderer/terminal event quality 범위이며 새 카드 전용 또는 E2E 측정으로 해석하지 않는다.

기능은 기본 off다. main 통합, 운영 활성화, scheduled shadow, 실제 LLM 의미 평가 및 게시/알림/Pages 수용 검증은 이 코드 완료에 포함하지 않는다. DEBT-090은 변경하지 않았다. 새 코드 차원의 gap이나 debt는 없다.
