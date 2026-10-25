# u182 Domain entities

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증 진행 중이며 운영 활성화는 별도다.

| Entity | 필드/관계 | 불변 조건 |
| --- | --- | --- |
| SourceInsightEvent | source owner, official_id/kind, local start/end, exact_at, verified target_period/ref | date-only 와 exact union, source 범위/정밀도 보존 |
| UpcomingEventIdentity | kind, official occurrence/family, declared date range, period-or-null | conservative cross-source merge; 가격·v3 사건 ID 와 별개 일정 projection |
| UpcomingEventView | category, display/date basis, title/guide/source links, limitation | target period infer 금지; raw prose 를 새로운 사건 사실로 쓰지 않음 |
| CalendarModuleCoverage | source outcomes/caps, selected/excluded/conflict count | normal/partial/empty 와 not verified 구별 |

공유 DTO 선언은 `src/investo/models/insights.py`와 공통 foundation 이 소유한다. source envelope → validated module → public manifest/receipt 관계는 [C1–C6](../../public-insights-20261012/contracts.md)에 고정한다. serializer 의 기본 bytes, Decimal/clock/기간·closed enum 검증을 유지한다. public writer 는 source raw item 이나 LLM draft 를 받지 않는다.
