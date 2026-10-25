# u181 Domain entities

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.

| Entity | 필드/관계 | 불변 조건 |
| --- | --- | --- |
| MacroMetricDefinition | metric_id, owner source/series, unit/adjustment, legal scope, display label | 13slot closed catalog; CUSR SA 와 다른 CPI 를 동일 정의로 취급하지 않음 |
| MacroCurrentView | primary4 cards, curve4 points, money-market3, monthly3 | 중복 값은 같은 typed object 를 표현; 원천 시점 보존 |
| MacroComparison | exact baseline/current observation refs, delta/unit | source/calendar/definition 일치, 이력 부족은 null+reason |
| RelatedBriefingLink | verified archived URL, 실제 발행일 | 같은 날짜가 없으면 최근 시황의 실제 날짜 표시 |

공유 DTO 선언은 `src/investo/models/insights.py`와 공통 foundation 이 소유한다. source envelope → validated module → public manifest/receipt 관계는 [C1–C6](../../public-insights-20261012/contracts.md)에 고정한다. serializer 의 기본 bytes, Decimal/clock/기간·closed enum 검증을 유지한다. public writer 는 source raw item 이나 LLM draft 를 받지 않는다.
