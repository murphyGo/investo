# u184 Code Generation Plan — 사건 근거 패킷과 원문 보강 연결

2026-10-26. **설계 작성; 구현0/6.** 사용자 요청은 실제 자동 기사의 충분한 내용을 위한 설계·아키텍팅이다. 이번 문서는 live HTTP/production 활성화 증거가 아니다.

## 문제·목표·범위

실제 preview `40186613927`은15개 뉴스 입력 뒤125자 기사1개만 남았다. preview는 원문 보강을 호출하지 않고 production은 v2에만 연결한다. source excerpt1,200자와 Stage2 optional allocation은 필요한 설명 근거를 보장하지 않는다. 기존 수집·u161 body·u167 context에 **v3 공통 preparation + 사건별 packet**을 연결한다.

Coverage: US-001/002/007/008; FR-001/002/017/021/023/024; NFR-001/002/003/005/006/007/008. u160/u161/u165/u167/u168/u173 확장이다. canonical identity, human acceptance, 새 provider/유료 API, public raw archive, 새 crawler, 별도 source ledger는 범위 밖이다.

## 설계·의존성과 module map

Functional Design/NFR **EXECUTE — 공통 설계 작성됨**: [처리](../event-news-v3-content-20261026/functional-design/business-logic-model.md), [규칙](../event-news-v3-content-20261026/functional-design/business-rules.md), [타입](../event-news-v3-content-20261026/functional-design/domain-entities.md), [NFR](../event-news-v3-content-20261026/nfr-requirements/nfr-requirements.md). 반복되는 별도 FD를 만들지 않는다.

기존 `models/enrichment.py`, `sources/event_evidence.py::enrich_event_evidence`, `orchestrator/pipeline.py::_enrich_collected_events/CollectStage`, `orchestrator/event_preview.py`, `scripts/preview_event_briefing.py`, `briefing/event_context.py`, `_internal/event_context.py`를 읽는다. 신규 `orchestrator/event_evidence.py`, `models/event_article.py`에 각각 공통 준비·private packet 타입을 둔다. sources와 briefing 사이를 orchestrator가 연결한다.

offline 설계 구현은 기존 u167/u168으로 착수 가능하다. live source별 확대는 u173 qualification 및 u161 source policy가 선행조건이다. u185는 packet 계약을 소비한다. renderer나 evaluation이 HTTP를 호출하지 않는다.

## 구현 순서

- [ ] **Step1 — 타입·정책**: immutable Passage/Question/Packet, profile 기본role_v1, preview enrichment 기본off와 별도 capability/allowlist/policy hash를 추가한다. 기존 active capability는 보존한다. max6 HTTP/run·20초·6,000자 확대와 old1,200자 path를 명시적으로 분기한다.
- [ ] **Step2 — 공통 preparation**: 기존 orchestration만 공유 함수로 옮겨 preview와 production에 연결한다. 실제 production dispatch/default는 바꾸지 않는다. 전체 run에서 body6회 한도를 공유하며 시장마다6회를 새로 배정하지 않는다. off/shadow/replay에서는 새 HTTP0회, source 실패는 원래 outcome 유지다.
- [ ] **Step3 — passage 추출과 input**: qualified selector의 완결 문단·attribution/조건/negation offset을 보존한다. Stage1 24KiB 실전송/source-diverse input과 synopsis를 검증한다. title-only와 body available을 구별하고 source·중복 문서·순서에 결정론적 결과를 낸다.
- [ ] **Step4 — packet/질문/Stage2 배정**: u168 identity binding 뒤 existing editorial order로 core→필수 설명→선택 설명을 배정한다. Stage2 evidence48KiB/전체64KiB를 계산하고 누락 refs·후순위 budget_deferred·conflicting evidence를 기록한다. selection/packing으로 사라진 정보를 source_empty로 바꾸지 않는다.
- [ ] **Step5 — source별 확장 검증**: [8개 source handoff](../event-news-v3-content-20261026/acceptance-and-handoff.md)의 기존 source별 access/rights/selector/retention fixture를 대조한다. 허용된 기존 국내 정책/DART/SEC filing source에 필요한 bounded enum/selector만 추가한다. 근거 없는 endpoint를 발명하지 않는다. 각 substep의 qualified/blocked와 미해결 슬롯을 적고 blocked 상태에서는 해당 live 경로를 열지 않는다.
- [ ] **Step6 — 검증·인계**: 아래 tests와 module boundary/static 검증, shared HTTP budget·source privacy 회귀를 완료한다. 실제 rights/parser 증거가 필요한 Step5가 남으면6/6로 보고하지 않는다. exact SHA/packet manifest/남은 qualification을 u185/u173/u172에 전달한다.

## Acceptance Criteria

1. **AC-184.1**: 같은 collection·clock·policy 입력의 preview/production preparation이 같은 packet hash를 만들며 source outcomes·기존 cursor는 변하지 않는다.
2. **AC-184.2**: off/shadow/replay/unqualified에서 새 HTTP0; qualified preview만 닫힌 host/path의 run당6회/20초/동시2/500KiB를 지킨다. redirect도 request에 포함한다.
3. **AC-184.3**: 원문1200자 이후의 중요한 조건·배경을 완결 passage로 전달하는 양성과 잘린 부정/다른 revision/잘못된 event를 거절하는 음성이 통과한다.
4. **AC-184.4**: Stage1/2 실전송 cap을 metadata 포함 지키며 required fact와 핵심 설명 근거는 모두 전송하거나 사건이 명시적으로 deferred다. raw ref가 남고 실제 text가 빠진 성공은 없다.
5. **AC-184.5**: source별 qualification/retention 상태와 actual packet coverage가 다르게 보고되고 blocked를 verified로 승격하지 않는다. 필요한 live source substep이 없으면 미완료다.
6. **AC-184.6**: 입력 순서/중복 변화·timeout·본문 실패에도 stable IDs/hash, feed fallback과 유효 sibling을 보존하고 private raw가 공개 serializer/log에 나오지 않는다.

## Tests / Validation

기존: `tests/unit/sources/test_event_evidence.py`, `tests/unit/briefing/test_event_context_refs_v3.py`, `tests/unit/models/test_event_context_v3.py`, `tests/integration/test_event_context_handoff_v3.py`, `tests/unit/orchestrator/test_event_preview_boundary.py`, `tests/unit/orchestrator/test_event_preview_encryption.py`.

신규 Step1–5: `tests/unit/models/test_event_article_packet_u184.py`, `tests/unit/orchestrator/test_event_evidence_preparation_u184.py`, `tests/unit/briefing/test_event_packet_budget_u184.py`, `tests/integration/test_event_packet_handoff_u184.py`. AC1/2→preparation/handoff, AC3/4→packet/budget, AC5/6→model/source/boundary에서 검증한다.

구현 후 `uv sync --extra dev --extra docs --extra sector --extra operations`, 위 파일에 대한 `uv run python -m pytest -q`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run mypy src`, `git diff --check`를 수행한다. 정확한 통합 SHA의 full/policy/docs gate와 live source 수용은 [공통 인수](../event-news-v3-content-20261026/acceptance-and-handoff.md)에서 결속한다. 현재 문서 작업에서 새 tests가 존재하거나 실행됐다고 기록하지 않는다.
