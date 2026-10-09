# Code Generation Plan: u169 event-first-document-and-finalization

**Date**: 2026-10-10
**Unit**: u169 event-first-document-and-finalization
**Stage**: Code Generation — 계획
**Status**: 설계 작성; 구현0/9
**Source**: 사용자 이벤트·뉴스 중심 문서 전체 구조 개편; [근거](../event-news-v3/evidence.md)
**Estimated Effort**: 36–48h
**Dependencies**: u167 context/quality, u168 identity/sharedstoryDTO. u170 semanticlogic/u171surface는후속consumer며역방향harddependency가아니다.

## Problem Statement
현재Stage2Sections와Briefing은6개freebody+disclaimer의고정7섹션을필수로한다. 사건②를바꿔도나머지body와topmacro/thesis/table이수치중심으로남는다. 긴본문내용이첫문장80자요건때문에실패할수있다. 신규문서전체를사건원본으로구성하고구조검증·소비자를같은단위에서전환해야한다.

## Goal
EventEditionDraft하나에서사건·설명·반응·후속·참고자료와최종요약을만들고u144단일finalizer로봉인한다. obsolete7sections와shortsummary제약을v3본문에서폐기한다.

## Existing Coverage / Deduplication
u157/u158선정/JSON/ref, u59requiredactual, u97stablehierarchy, u144finalizer, u149/u150/u163containment, u153complete-sentenceutility를재사용한다. u154legacyreflow및u156reservedTelegram은v3renderer를소유하지않는다. ledgeradvanceu170,모든표면layoutu171,semanticcutoveru172와경계를구분한다.

## Scope Boundary
In scope: design-brief의 canonical models/briefing/publisher/shared validation, generation_contract.py의 draft union, orchestrator/pipeline.py/stages.py, publisher/writer.py의 공통 sealed accessors, schema별 구조·수치·entity·compliance 검증과 terminal notification DTO.
Out of scope: 새provider/sourceHTTP,productionrelease,storyreducer/ledgerIO,Telegram다중eventlayout와homepage/weekly/OG전환,과거archive수정.

## Stage Decision
Functional Design: REQUIRED — 고정7section·anchor-first·3summary의제품구조와schema를교체한다. [설계](../u169-event-first-document-and-finalization/design-brief.md).
NFR Requirements: REQUIRED — 모든finalizer/validator/writerseam와typedbudget/partial/seal/asset계약이바뀐다. [공통NFR](../event-news-v3/nfr-design.md)의N1~N8을적용한다. 새로운runtime/dependency/infrastructure는추가하지않는다.

## Fixed Contracts
[C1/C4/C5/C7](../event-news-v3/contracts.md),[기능설계](../event-news-v3/functional-design.md),[처리규칙](../event-news-v3/business-rules.md)이normative다. 순환의존성을피해models/event_story.pyDTO는u168이선언한다. PublicEditionView는frozen이고mutablemapping/검증전Briefing을소비자원본으로허용하지않는다.

## Implementation Steps
- [ ] 1. EventVisualInput·EventAssetImpact·public projection 타입과 price/news-window metadata, EventEditionDraft/EditorialPlan/article/digest/panel/availability/PublicEditionView와schema3terminalnotificationmodel을추가한다. 모델serialization/union은한variant만허용한다.
- [ ] 2. briefing/editorial_plan.py에서parent-ownedorderedIDs/facts/placement를고정한다. requiredactual은보호하고repeat/background는reference로배치한다.
- [ ] 3. Stage1/2schema3prompt/parser/retry를현재2단계runner에연결한다. provider별동일입력에서callstage수가늘지않게한다.
- [ ] 4. pure event_v3_contract validator로 refs/facts/entities/time/meaning/reaction/selection을 검증하고 본문600자와 요약140자를 독립적으로 처리한다.
- [ ] 5. publisher/event_edition.py의 결정론적 renderer와 schema3 region expectation을 추가한다. 기존 reflow/7H2/callout/hero 강제 producer를 v3에 적용하지 않는다.
- [ ] 6. u144 finalize_public_bundle에 typed variant를 연결하고 original hard gates→bounded reconciliation→reindex→read-only terminal validation→SHA seal 순서를 유지한다. hidden7section bridge는0개다.
- [ ] 7. FinalizedPublicDocument와 writer에 공통 sealed text accessor를 추가한다. 기존 타입 검사와 exact bytes/disclaimer/hash 검증을 유지하고 typed story proposal/delta도 확인한다. C5a PublishedEventEdition sidecar의 exact bytes/hash writer를 추가하고 archive와 같은 publication transaction/CAS/rollback에 묶는다.
- [ ] 8. orchestrator의 variant/context handoff와 terminal notification projection을 통합한다. valid partial, source-limited/quiet, assets, remote-confirmed receipts를 회귀 검증한다.
- [ ] 9. 실제 finalizer/HTML/provider replay/full/static/policy 검증과 독립 review를 완료하고 u170/u171에 sealed view/delta seam을 인계한다. active는 u172 전환 gate 전 false다.

## Acceptance Criteria
1. AC-169.1: schema3 JSON에6개 free body/별도 Markdown이 없고 신규 문서에①~⑦ dummy heading/field bridge가 없다.
2. AC-169.2: headline120/what600/digest140의독립경계를지키고긴주체·대상과8facts/4docs사건이본문에남는다. digest의 길이·문장 완결성만 실패하면 유효 article을 유지한다. unsupported fact/entity/compliance 실패는 삭제 전에 original hard finding을 수집한다.
3. AC-169.3: 새 정책/실적/서비스 사건이 상단과 관련 본문을 조직한다. 새 발표 없는 월간/주간 값은 참고 자료에서 날짜·단위를 가지며 반복 headline을 차지하지 않는다.
4. AC-169.4: 모든 required facts/source/time/field refs가 최종 본문에 남고 unsupported fact/entity/actual-forecast 및 인과관계의 기존 hard negative를 통과시키지 않는다.
5. AC-169.5: quiet/source_limited/generation_failed/trust_blocked를 구별하고0/1/2/3개 유효 시장 bundle의 게시/absence/exit/Pages 계약이 일치한다.
6. AC-169.6: 제거된 event가 digest/follow-up/asset/story delta에 재등장하지 않고 finalizer2회 bytes/hash/outcome가 동일하다. post-seal mutation0회다.
7. AC-169.7: v3 writer의 view/target/segment/hash/disclaimer 검증과 E1→E5→E6 asset promotion/pre-git rollback을 유지한다.
8. AC-169.8: public refs가 검증된 locator로 변환되고 sidecar/Markdown hash·동일 transaction이 일치한다.  유효 sealed reader state에 matching typed proposal/refs/hash가 있는 경우에만 StoryPublicationDelta를 생성한다. 미게시 transition이나 opaque hash만으로 생성하지 않는다.
9. AC-169.9: provider별 두 단계/기존 attempt·deadline/16KiB 보호 예산을 지키고 off/shadow/v2 기록 bytes와 과거 archive 읽기를 유지한다.

## Tests / Validation
예정 새 파일: tests/unit/models/test_event_document_v3.py, tests/unit/briefing/test_editorial_plan_v3.py, tests/unit/publisher/test_event_edition_v3.py, tests/integration/test_event_document_finalization_v3.py, tests/integration/test_event_document_partial_v3.py. 기존 test_event_finalization.py/test_event_publication_boundary.py와 numeric/entity/compliance/asset/writer 회귀를 같이 실행한다.

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/unit/models/test_event_document_v3.py tests/unit/briefing/test_editorial_plan_v3.py tests/unit/publisher/test_event_edition_v3.py tests/integration/test_event_document_finalization_v3.py tests/integration/test_event_document_partial_v3.py tests/integration/test_event_finalization.py tests/integration/test_event_publication_boundary.py
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run python -m pytest -q
python scripts/check_no_paid_apis.py
git diff --check
```

실제 provider 생성/운영 pin/viewport/사람 점수는 u172 actual evidence로 별도 수용한다. 코드 생성 완료와 production v3 완료를 구별한다.

## Non-Goals
legacy 섹션을 유지하는 숨겨진 dual 원본, 새 finalizer, 새 LLM 단계, source HTTP 권한 완화, hard trust 우회, 누락 사건 재추론, 전체 과거 archive 재작성.
