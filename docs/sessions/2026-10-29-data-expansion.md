# 세션: KRX 월물 만기 및 Coin Metrics 일별 거래소 흐름

- 사용자: 연구 결과 1~2순위 도입 승인.
- 적용: `dev-investo`; u43/u66 확장의 FD/NFR/구현/검증. 다른 세션과 겹침을 피하려고 HEAD 4cc5467 기반 임시 clone에서 작업 후 baseline 대조 통합.
- 수집기 2개와 canonical SourceSpec 등록. KRX 2026년 계산 일정, native BTC/ETH 일별 유입/유출/순유입.
- native v3 호환을 위해 시장 기준 자료 패널에도 연결. 생성 모델이 제공한 supplemental 값은 사용하지 않고 수집 입력으로 최종 재구성.
- 검증된 순유입 행을 USD 가격으로 오인하지 않도록 정확히 재구성된 행만 가격 검사에서 제외. 변경된 행은 계속 검사.
- v3 수집에 동일 evidence cutoff 전달. 외부 API는 Community 무료 무키 한 번 배치와 공통 bounded retry만 사용.
- 공개 데이터 조건: 비상업 CC BY-NC 4.0, 출처·계산·잠정·관측일 고지. Telegram은 상세 페이지 링크로 attribution에 연결.
- 독립 코드 리뷰: Correctness/Safety/Reliability/Maintainability/Test Coverage 모두 Pass. 수정 전 지적과 해결 증거는 cross-check 참조.
- 테스트: 넓은 회귀 4,607 pass, count 갱신 후 집중 89 pass, reviewer 독립 44 pass. 기존 HTML malformed 사례 1건 실패를 통합 전 원본에서도 재현하여 분리 기록.
- 2026-10-29 구현 단계에서는 배포/예약 실행/외부 채널 송신은 하지 않음. 유료 fallback/API key 없음.

관련: [설계](../../aidlc-docs/construction/data-expansion-20261029/functional-design/design.md), [계획](../../aidlc-docs/construction/plans/data-expansion-20261029-code-generation-plan.md), [cross-check](../cross-checks/2026-10-29-data-expansion.md).

최종 통합: 공유 작업공간 집중 144 passed. 새 문서 링크 확인, 변경 source 17개 mypy/ruff/무료 API 검사 및 공백 검사 통과. 다른 세션의 기존 변경을 덮어쓰지 않았음.

2026-10-30 사용자 커밋·배포 요청으로 후속 작업 진행. 공개 main 반영본과 기존 운영 SHA 기반의 source/test 전용 반영본을 분리했다. 설치된 운영 워크플로는 schema 2 / role_v1, 국내·미국 active 및 크립토 shadow이며 이 모드는 유지한다. `active` 변수를 native v3 운영으로 해석했던 판단은 정정했다. 운영 반영본 독립 리뷰 Pass, 기존 HTML 테스트도 운영 Python 3.11.9에서 통과했다. 상세 검증과 배포 기록은 cross-check 참조.
