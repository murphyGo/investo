# Code Generation Plan: u167 event-context-evidence-and-quality

**Date**: 2026-10-10
**Unit**: u167 event-context-evidence-and-quality
**Stage**: Code Generation — 계획
**Status**: 개발 승인 기록; foundation 구현 7/8; 최종 회귀/독립 검토 진행 중
**Source**: 사용자 이벤트·뉴스 이상향 분석과 구조 개편 문서화 지시; [근거](../event-news-v3/evidence.md)
**Estimated Effort**: 24–32h
**Dependencies**: 기존u157/u158/u161 코드. source-slot확장u173은harddependency가아니다.

## Problem Statement
기존의미/반응은actor/action/object/fact등에선택된span밖의문장을쓸수없고,시간/내용/history부족이detail_limited하나로합쳐진다. 최신preview의국내5/미국2모두limited이지만공개카운트만으로원인을구별할수없다. 숫자없는좋은사건설명과올바른시점처리를위해context역할과품질축이필요하다.

## Goal
같은 사건의 설명용 근거를 끝까지 전달하고, 부족의 종류를 사실 그대로 계측한다. 다른 유닛이 source/time/meaning 계약을 다시 만들지 않게 한다.

## Existing Coverage / Deduplication
u157의span·선정과u161factory/HTTPbudget을확장한다. u158본문과u159qualityowners를유지한다. identity/delta는u168,문서schema/renderer는u169,story는u170,sourcequalification은u173의책임이다.

## Scope Boundary
In scope: models/event_context.py 신규; models/event_config.py, event_evidence.py, event_quality.py; sources/event_evidence.py와현재typedfeedadapter의변환; briefing/event_input.py,event_evidence.py,event_prompt.py,event_selection.py,prompts.py; generation_contract.py의frozencontext입력; orchestrator/pipeline.py의명시적policy/contexthandoff; publisher/event_quality.py의축별projection.
Out of scope: 새로운HTTPprovider·bodypath,productionactivation,entitysemanticmerge,전체v3document,watchlistlayout.

## Stage Decision
Functional Design: REQUIRED — 역할별 근거, 시간precision, 품질vector와Stage1schema가새제품계약이다. [작성된설계](../u167-event-context-evidence-and-quality/design-brief.md).
NFR Requirements: REQUIRED — 전송byte예산·private버퍼·진단과schema별호환이변경된다. [공통NFR](../event-news-v3/nfr-design.md)의N1/N2/N4/N5/N6/N7을적용한다. Infrastructure단계는새dependency/secret/배포체계가없어별도로추가하지않는다.

## Fixed Contracts
[C1/C2/C7](../event-news-v3/contracts.md)를재정의하지않는다. ContextEventDraft의identity/fact/relation/impact와설명역할refs는각각같은transmittedcontextdocument안에있다. ContextFactDraft의 성분별 binding과 source-owned metadata chunk 변환을 사용하고 모델이 locator/time/unknown 상태를 발명하지 못한다. policy의기본schema2와기존off/shadowbytes를유지한다. v3실제활성화는u169/u172consumer/gate완료전거절한다.

## Implementation Steps
- [x] 1. models의frozencontext/ref/time/vector/draft와GenerationPolicy를추가한다. precision별null/UTC/date검증과roleenum을고정한다.
- [x] 2. source-ownedfactory에서legacytitle/summary/detail을chunk로변환한다. v3opt-in만새필드를전달하며v2serialization은변경하지않는다.
- [x] 3. Stage1 v3schema와system/user/retrytemplate을일치시키고설명역할refs를반환하게한다. 기존requiredmacroactual보호를유지한다.
- [x] 4. same-run document/chunk/span ownership과독립된meaning/reactionrefs를검증한다. 다른item/failedsource/futurestate음성을고정한다.
- [x] 5. 필수근거→설명근거→optional순서의actual UTF-8budget을구현하고Stage1 24KiB/v3protected16KiB/v2 8KiB를별도검증한다.
- [x] 6. 품질vector와boundedprivatefield/rule진단을기존qualitytrace에연결한다. 날짜부족·history부족·내용부족을독립fixture로구별한다.
- [x] 7. orchestrator→GenerationInput→classification→protectedprompt의명시적handoff를통합한다. u168/u169consumer가없는단계의미관측카운트는null로둔다.
- [ ] 8. 실제buffer/projectionintegration회귀,static/policy/fullgate와독립review를완료하고per-AC결과를기록한다.

## Acceptance Criteria
1. AC-167.1: 기존fact/identityrefs와다른meaning/reaction/follow_up문장이동일sourceownership으로Stage2protectedbuffer까지도달한다.
2. AC-167.2: 다른event/document/chunk,범위밖span,failedsource,미전달text는supported로통과하지않는다.
3. AC-167.3: 사실충분/시점불명,history불명,locator부재,내용부족이서로다른vector/reason으로남는다. missingtime만으로기사사실을허위로표시하지않는다.
4. AC-167.4: announcement/publication/received/period가분리되고source없는시점/actual/forecast/단위를생성하지않는다.
5. AC-167.5: 24KiB/16KiB/8KiB와rowcaps를실제UTF-8로지키고selectedplan과transmittedblock이일치한다. 필수actual의조용한손실0.
6. AC-167.6: 같은기록입력/응답에서v2와off/shadow공개bytes·calls·알림·cursor·receipt가동일하다. 신규HTTP0회/LLM단계추가0.
7. AC-167.7: private진단에rawarticle/modeltext/secret값이없고field/code/hash/attempt상한만남는다.
8. AC-167.8: foundation범위의context준비완료를v3본문·사람수용·productionactivation완료로보고하지않는다.

## Tests / Validation
새test: tests/unit/models/test_event_context_v3.py, tests/unit/briefing/test_event_context_refs_v3.py, tests/integration/test_event_context_budget_v3.py, tests/integration/test_event_context_handoff_v3.py. 기존tests/integration/test_event_prompt_budget.py와test_event_enrichment.py를함께유지한다.

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/unit/models/test_event_context_v3.py tests/unit/briefing/test_event_context_refs_v3.py tests/integration/test_event_context_budget_v3.py tests/integration/test_event_context_handoff_v3.py tests/integration/test_event_prompt_budget.py tests/integration/test_event_enrichment.py
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run python -m pytest -q
python scripts/check_no_paid_apis.py
git diff --check
```

예정test파일은해당단계에서생성한다. 이문서작성에서실행코드test를통과했다고보고하지않는다. 실제LLM/성능/소스자격/운영검증은후속범위다.

## Non-Goals
표현만바꾸는뉴스증량,유료API,새LLM단계,source권한우회,기존qualified분모재정의,숫자/면책/구조검증완화.

## Implementation checkpoint — 2026-10-10

사용자의 별도 워크트리 개발 지시를 FD/NFR 및 code plan 실행 승인으로 기록했다. source context/model, 동일 소스 성분 binding, Stage1 CLI replacement, actual UTF-8 budgets, shadow 해시 관측, 명시 policy authority를 구현했다. shadow는 실제 classifier/Stage2 observation으로 표시하지 않는다. 실제 schema3 본문 소비는 u169가 담당하며 preview/active capability는 닫혀 있다. 실제 CLI replay의 Stage1→protected buffer 시험과 off/shadow 공개 bytes/calls 동등성을 검증했다. 최종 결과는 `../u167-event-context-evidence-and-quality/code/validation.json`에 기록한다.
