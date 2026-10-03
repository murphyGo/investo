# u152 요구사항 대조

기존 code plan AC-152.1–7과 실제 public resolver/renderer/finalizer를 대조한다. 사용자 승인 u162의 필수 선행 작업이며 별도 사용자 답변을 받은 것으로 기록하지 않는다.

| 기준 | 증거 |
|---|---|
| AC-152.1 | threshold/source/date 숫자만으로 current 통과 불가. |
| AC-152.2 | canonical ETH 가격 대체, ETH funding이 BTC funding/가격을 차용하지 못함. |
| AC-152.3 | 명시적 필드 분리, missing-current whole-paragraph 복사 제거, unsafe title canonical repair. |
| AC-152.4 | 동등 우선순위 충돌의 모든 순열 거부, 동일 중복 안정, source specificity 보존. |
| AC-152.5 | CFTC 두 날짜·순서·주간 지연·보통 이하 신뢰도, missing/invalid 날짜 거부. |
| AC-152.6 | 미지원 국내 수급/정성 아닌 미지원 수치 지표는 제외, 지원 fallback/기존 제한 문구. |
| AC-152.7 | 실제 sealed Markdown의 관측값, supplements/disclaimer, terminal DTO와 반복 bytes/partial sibling/hardgate. |

최종 집중 165개, 독립 contract/actual-finalizer 66개와 source-slot 반례 14개가 통과했다. 최종 전체 gate 수치는 validation.json에 기록한다. 운영 배포·main 통합·다른 유닛 활성화를 뜻하지 않는다.

판정: APPROVE. AC 7/7, DoD 5/5 충족. 최종 전체 5961개/472.37s, Ruff/format657, mypy289, 정책4개, strict MkDocs/Material 및 성능 p95=137.474ms 통과. 새 gap/debt 없음.
