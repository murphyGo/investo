# 우선순위별 데이터 확장 교차 검증

## 범위와 결과

사용자 “우선수위별로 적용하자”를 따라 u66 활동 지표 → EF 조건 확인 → u43 위클리 순서로 진행했다. Coin Metrics 활동과 검증된 KRX 위클리 범위를 구현했다. EF·Deribit·Bybit의 미해결 조건을 구현 완료로 간주하지 않는다. [설계](../../aidlc-docs/construction/data-priorities-20261030/functional-design/design.md), [자격 판정](../../aidlc-docs/construction/data-priorities-20261030/qualification.md).

| 요구 | 검증 근거 | 결과 |
| --- | --- | --- |
| 무료 추가 데이터, FR-001 / NFR-002 | 키 없는 Community API, dependency/service 추가 없음 | 충족 |
| BTC/ETH 활성 주소·거래 건수 | 8개 완료 UTC일, 지표별 결측/충돌 검증, 7개 연속 비교일 | 충족 |
| NFR-003 실패 격리 | activity 403에도 기존 순유입 2행 유지, 64KiB/16행 제한 | 충족 |
| FR-002 수치 정합성 | 평균 Decimal 계산, source로 finalizer 패널 재생성, 정확한 표행만 USD 검사에서 제외 | 충족 |
| 출처·오독 방지 | CC BY-NC, Investo 평균 표시, 미제공 검토 상태·수정 가능성, 주소≠사용자·거래건수≠매매량·ETH L1 | 충족 |
| u43 옵션 범위 확장 | 월물/월·목 위클리 별도 모델, 월요일 후순연/목요일 앞당김, 월물 우선 최대2개 | 충족 |
| 달력의 검증 경계 | 2026 한정, 2027 차단, 11/19 수능일 시각 미검증 제외, 현재 상장 여부·최종결제일로 표현하지 않음 | 충족 |
| 공개 권한 판정 | EF·Deribit·Bybit 보류, 기존 dashboard 공개/보존 정책 유지 | 충족 |
| 기존 경로 호환 | native/legacy 최종 문서·기존 flow 공존, 알림 결론 오염 방지 | 충족 |

## 검증

[상세 검증 기록](../../aidlc-docs/construction/data-priorities-20261030/validation.md): 전체 7,653 pass / 1 known skip; 이후 경계 보완에는 관련 테스트 재실행. Ruff/mypy, Node 39, 정책 guards, strict 문서 빌드 통과. 실 API 4개 지표 수집 성공. 독립 리뷰와 공유 작업공간 통합 결과는 세션 기록에 결속한다.

## 잔여 항목

- KRX 2026-11-19 특별 거래시간 공지 자격, 2027 거래소 달력 갱신.
- EF 재사용/보존 범위, Deribit 서면허가, Bybit 지속 수집·복구 및 권한.
- 이번 새 변경은 코드 적용 범위이며 commit/push/runtime pin 변경/실제 게시·알림은 하지 않았다. 기존 production 배포를 이번 기능의 운영 검증으로 재사용하지 않는다.

## Final integration result

Independent review: Pass, with 43 tests independently executed. After baseline-checked integration, root passed **163 tests**, Ruff check/format and mypy. [Session record](../sessions/2026-10-30-data-priorities.md). Implementation and bounded qualification checks are complete; the explicitly deferred external prerequisites and deployment remain separate.
