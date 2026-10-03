# 독립 설계 검토와 반영 기록

2026-09-26. 읽기 전용 에이전트 3명이 탐색과 초안 검토의 두 차례 작업을 수행했다. 아래 22건의 수정 의견을 부모 에이전트가 문서에 반영했다. 수정 이후의 최종 일관성 검사는 부모가 수행했다. 제품 테스트 통과나 설계 사용자 승인을 뜻하지 않는다.

| 검토 | 발견 내용 | 최종 반영 |
|---|---|---|
| 선정/품질 1 | live shadow의 v2 변경과 legacy 불변 충돌 | E9: v1 shadow와 v2 비게시 preview 분리 |
| 선정/품질 2 | 동일 문서의 복수 사건 병합·anchor 교체 ID 변경 | E2: actor/action/object/time과 committed alias |
| 선정/품질 3 | 사건 수와 실제 근거 row cap 혼용 | E5: 필수 근거 우선, 모든 cap은 실제 rows |
| 선정/품질 4 | input permutation과 기존 index tie 충돌 | E5: active 모든 lane stable key, off 순서 보존 |
| 선정/품질 5 | 분류 실패가 정상 0건으로 계수됨 | E8: 단계별 nullable 표와 상태 우선순위 |
| 선정/품질 6 | terminal 최대 5건과 DTO 최대 3건 충돌 | E7/AC-159.5: ordered subset |
| 선정/품질 7 | 공식 crypto-policy에 새 cap을 숨겨 도입 | E5: 기존 정책 우선권 유지, reservation 부족 계측 |
| 소스/기간 1 | 오래된 RSS 항목 하나로 full 판정 | u160: 검증된 기간 계약만 full, finite RSS 기본 unknown |
| 소스/기간 2 | commit 후 불명확한 push를 파일 rollback | E11: pending 보존, 원격 ancestry/CAS reconciliation |
| 소스/기간 3 | shadow 게시가 cursor를 전진시킴 | u160: active+consumed window+remote receipt만 advance |
| 소스/기간 4 | 지연·수정 기사가 cursor 밖에서 누락 | u160: 24h overlap과 document/revision dedup |
| 소스/기간 5 | DART 자정·페이지 deadline 모호 | u160: end-1 microsecond, 날짜 정밀도, 총 20초 |
| 소스/기간 6 | summary 절단 후 원자료 복원 불가 | E11/u161: adapter에서 typed optional item evidence 생성 |
| 소스/기간 7 | source마다 다른 창을 단일 완전 구간으로 표현 | u160: envelope와 completeness/source별 진단 분리 |
| 공개/관전 1 | terminal 검증 중 요약·카드 재작성 순환 | B8: bounded repair 후 읽기 전용 validation |
| 공개/관전 2 | 의미·반응별 출처/unknown을 표현할 수 없음 | E6: MeaningClaim/ReactionClaim의 별도 상태·refs |
| 공개/관전 3 | 기존 trust gate 능력을 과장 | E6: structured validator 소유권과 자유 서술 평가 분리 |
| 공개/관전 4 | v2 retry에서 Markdown 요구 | u158: system/user/retry schema version 분기 |
| 공개/관전 5 | 총 2카드와 기존 numeric 최대 6 충돌 | u162: event-present 2, event-absent legacy 유지 |
| 공개/관전 6 | 긴 사건 첫 문장이 u153 fallback으로 복귀 | E6/u158: 80자 완전 첫 문장 재사용 |
| 공개/관전 7 | next_check 생산자가 없음 | u162: scheduled fact 또는 닫힌 관찰 템플릿 |
| 공개/관전 8 | u159의 숨은 hard dependency | u162: 자체 CompanionOutcome 완료, 소비자 확장은 후속 |

통합 과정에서 발견한 공통 dependency도 수정했다. 중복 방지용 event receipt와 뉴스 cursor가 모두 원격 발행 확인을 필요로 하므로 PublishReceipt seam을 u157이 소유한다. u160의 cursor 통합은 u157 이후이며 window/adapter 작업은 병렬 가능하다. 3개 registry, overview, 설계, 계획을 함께 갱신했다.

신규 공식 본문 endpoint는 아직 하나도 qualified로 선언하지 않았다. u161은 qualification 작업 준비 상태이며 qualified source가 0이면 Stage C 구현과 관련 AC를 pending/blocked로 남긴다.
