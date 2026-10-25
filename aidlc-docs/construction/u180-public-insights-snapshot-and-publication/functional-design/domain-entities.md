# u180 Domain entities

작성일: 2026-10-12 · u180 · 상태: 사용자 “유닛 하나씩 진행시켜” 지시로 설계 채택, 로컬 구현·검증 진행. 공개/운영 활성화는 pending.

| Entity | 필드/관계 | 불변 조건 |
| --- | --- | --- |
| SourceInsightEnvelope | source_name, collector-bound origin_adapter_name, metrics/events tuples, schema1 | private in-memory only; item serialization 에서 제외 |
| SourceInsightMetric / SourceInsightEvent | definition/scope/provider, Decimal/unit 또는 일정 identity/time | sources owns payload mapping; 단위/기간/시각 self-consistency |
| InsightTime | basis, precision, local date/period/exact timestamps | C2 상호 배타 조건; 원천/운영 시계 분리 |
| InsightSourceQualification | field_scope, display/public_git_history/retention, terms/attribution, runtime state | current 숫자도 공개 Git 이력 허가 필수; source discovery registry와 별개 |
| ValidatedInsightModule | 모듈 ID, 값/일정, source refs, status, snapshot_id | 완료된 deterministic public projection 만 renderer 에 전달 |
| PublicInsightsManifest | module identity, index/current/history hashes, schema1 | single remote baseline CAS metadata |
| InsightRunOutcome | mode/modules, per-module result, PublishReceipt 또는 없음 | PipelineResult opt-in field; 기본 serialization omit |

공유 DTO 선언은 `src/investo/models/insights.py`와 공통 foundation 이 소유한다. source envelope → validated module → public manifest/receipt 관계는 [C1–C6](../../public-insights-20261012/contracts.md)에 고정한다. serializer 의 기본 bytes, Decimal/clock/기간·closed enum 검증을 유지한다. public writer 는 source raw item 이나 LLM draft 를 받지 않는다.
