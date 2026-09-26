# Functional Design: u159 중요 사건 반영률과 최종 품질 검증

**Date**: 2026-09-26
**Status**: Design approved by the 2026-09-27 sequential-development request. Code complete — 6/6 steps, full regression 5652 passed (416.33s); independent review PASS. Human semantic acceptance pending; active remains off.
**Priority / effort**: P0 / 12–18 h (rough engineering estimate, not commitment).
**Dependencies**: u157 선정/trace, u158 terminal event renderer/projection. 기존u65/u123/u144 완료.

## Reader problem
기존 성공지표는 핵심이슈누락없음이지만품질history는숫자/소스/fallback 중심이다. sourceURL 언급만으로정책결정의설명깊이를보장하지못한다.

## Ownership and deduplication
Existing owners: u59 lineage, u54/u62/u96/u123 truthful metrics, u65 replay, u144 terminal gate.
Existing code touch points: `briefing/quality_eval.py, briefing/quality_history.py, models/quality_history.py, publisher/public_document.py, publisher/quality_consistency.py, orchestrator/pipeline.py, scripts/check_event_coverage.py`.
Proposed new modules: `publisher/event_quality.py; tests/fixtures/event_briefing/manifest.json; scripts/check_event_coverage.py`. These paths do not imply implementation exists.

## Shared contracts
[Program overview](../news-event-briefing/README.md), [entities and schema](../news-event-briefing/event-contract.md), [business rules](../news-event-briefing/business-rules.md), [NFR and evaluation](../news-event-briefing/nfr-and-validation.md).
The unit-specific rules below bind the shared contract. Inconsistency must be resolved in design before code; implementations cannot silently override common identity/budgets/trust semantics.

## Fixed contracts
1. E8 trace와 u158 terminal receipt를 연결한다. generated, terminal_survived, published, included_in_summary를 다른 상태로 둔다. source/candidate cap까지의 누락은관측된것만기록하고수집못한세상뉴스를추정하지않는다.
2. E8의 필드별 nullable 표와 상태 우선순위를 따른다. 완료한 단계의 관측된 0만 0이며 미실행·실패 단계는 null이다. selected_count=0 또는 null이면 두 반영률은 null이다. collected 수는 분류 성공을 뜻하지 않는다.
3. selection_coverage=terminal_event_count/selected_count, qualified_coverage=qualified_event_count/selected_count다. detail_limited는 terminal에 포함하되 qualified에서 제외한다. segment별 값이 원본이며 bundle 게시 집계는 remote-confirmed published segment 중 분모가 알려진 것만 포함하고 제외 segment를 표시한다.
4. qualified는실제terminal event block에서actor/action,정확한시점또는명시적unknown,required fact값,출처,why/반응상태가모두존재할때다. ID/URL존재만으로통과시키지않는다. 자유서술의의미진위전부를보장하는검사라고표현하지않는다.
5. 구조적누락은u158 boundedfallback/limited경로,unsupported source/number/entity/compliance는기존hardgate를유지한다. 새검증기에서기존hardfinding을지우거나완화하지않는다.
6. 과거quality_history에는새필드default=null을쓴다. 0/100%로역사데이터를채우지않는다. 공개metadata는count/hash/status만,원문/quote는private이다.
7. nfr-and-validation의12시나리오와18발행본manifest를고정한다. 출력회귀와실제inputreplay를구분하고 사람이must_include/required facts/forbidden claims를작성한다. 전체뉴스포착률과수집후보내반영률을분리한다.

## Stage decision
Functional Design: REQUIRED — new cross-module/event behavior; this document and shared contracts were approved by the 2026-09-27 implementation request.
NFR Requirements: REQUIRED — 공개품질의 분모·unknown 의미와 terminal gate 추가. NF1/3/6/7/9/10 적용.
Separate NFR Design/Infrastructure Design: no separate artifact for pure code; focused runtime/storage rules are fully specified here. u160/u161 public I/O and transaction rules require their NFR review before implementation. No new deployment platform.

## Failure and compatibility
Apply B4/B5/B8/B11 and unit-specific states. Off mode preserves current producer/consumer behavior. Existing numeric/entity/compliance hard gates and sibling availability remain authoritative. Code-ready status requires hard dependencies and design approval; source qualification stays separate from code readiness.

## Acceptance criteria
- AC-159.1: marker-only/URL-only/requiredfact제거/summary재노출negative가전부검출된다.
- AC-159.2: selected0/수집실패/미분류/partialpublish/알림만실패의분모와상태가거짓0/100%없이일치한다.
- AC-159.3: historicalrecord의새필드null과현재receipt의실제count가페이지/메타에서동일하다.
- AC-159.4:12golden시나리오의must_include/required facts100%,unsupported추가0;의미평가5/5기준을만족한다.
- AC-159.5: 삭제/repair/부분 재조립 후 DTO는 terminal의 알림 적격 최대 3개 ordered subset이며 값이 일치한다. terminal 사건 4개·5개 fixture도 통과한다.
- AC-159.6: source원문/privateprose/logsecret이공개fixture/quality에없고추가LLM평가호출0.

## Development sequence
See [code-generation plan](../plans/u159-event-coverage-replay-and-gate-code-generation-plan.md). Implementation follows the 2026-09-27 user-authorized sequential queue.
