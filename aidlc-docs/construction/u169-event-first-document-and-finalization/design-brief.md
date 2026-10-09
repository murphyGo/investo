# u169 Functional / NFR Design: 사건 중심 전체 문서와 finalization

**Date**: 2026-10-10. **Status**: 설계 작성; 구현 미착수. **Dependencies**: u167 context, u168 canonical identity와 shared story DTO.

## 문제와 목표

현재 EventNarrative는②와상단요약에강하게연결돼있지만①③④⑤⑥은free section string이다. models/briefing.py의Briefing은그7개section이모두있어야한다. 고정section을채우면서반복지표/잔액이사건설명의분량을차지한다. 80자첫문장과240자본문에주체/대상을압축하는계약도다중fact사건과긴이름의표현을제한한다.

v3는문서전체를typed사건·context·followup·reference로구성하고renderer가단일Markdown을만든다. 과거archive는그대로읽을수있되신규문서에7개빈field를만들지않는다.

## Canonical owners

- models/event_document.py: EventVisualInput, ContentEditionAvailability, EventEditionDraft/EditorialPlan/EventArticle/EventDigest/FollowUpEntry/ContextPanel/MarketReferencePanel/EditionAvailability/PublicEditionView.
- models/public_notification.py: EventNotificationSummaryV3와terminal event projection. 기존PublicNotificationSummary/PublicEventSummary는v1/v2호환용으로유지한다.
- models/event_asset_impact.py: EventAssetImpact의 frozen 공통 타입을 선언한다. u171이 matcher를 제공하기 전에는 빈 tuple을 사용하며, finalizer가 event/fact/ref와 survivor 일치를 검증한다.
- briefing/editorial_plan.py: parent-owned 전체 placement/근거계획. 모델이임의의선정집합을고치지못한다.
- briefing/event_document.py와prompts.py/_core/orchestration.py: schema3 Stage2 parse/validate와동일2단계실행.
- _internal/event_v3_contract.py: source ownership/fact/entity/시간/정렬의pure공통validation. briefing와publisher가서로import하지않는다.
- publisher/event_edition.py: typedmodel→readerMarkdown·schema3regionexpectation·terminalviewprojection.
- publisher/public_document.py: 기존finalize_public_bundle와단일lifecycle/seal. writer.py는같은FinalizedPublicDocument의exactsealedtext를쓴다.
- orchestrator/pipeline.py/stages.py: 명시적variant/context/consumerwire. ledgerstate진전은u170만한다.

## Fixed functional contracts

[C1/C4/C5/C7](../event-news-v3/contracts.md)와[F1~F5](../event-news-v3/functional-design.md)가 단일 출처다. 신규 문서의 schema는3, 단일 생성 원본은 EventEditionDraft다. section string이나 별도 자유 Markdown을 출력받지 않는다. article0~5개/digest0~3개, article fact 최대8개/source 최대4개, what_changed600자/headline120자/digest 완성 문장140자다.

기존fixedimportance scoring의입력은u168normalizedevent와u167supportvector다. requiredreleaseactual을우선보호하고나머지eligibleevent를기존u157stableorder로선정한다. background만인기사·변화없는monthly/weeklyvalues는reference로배치한다. 의미없는유형quota나새LLM선정단계를추가하지않는다. 사람importance불합격은u172에서명시적owner결함으로귀속한다.

EditorialPlan은 ordered IDs/facts/roles/placement를 고정하고 모든 transmitted evidence를 actual budget으로 계산한다. 주요 사건 뒤에는 관련 sector/asset/반응 정보를 같은 event ID로 연결한다. 관계없는 global macro/thesis/callout/hero 자동 주입은 v3에서 꺼진다. 원인 미확인 가격 변화는 별도의 market reference 관측으로 허용하며 사건의 인과관계를 만들지 않는다.

digest가표현/길이검증에실패하면해당digest만제외하고reason을기록한다. 그것이유효한article을삭제하거나새factualclaim을만드는이유는아니다. 필요한summary가없을때알림은사건headline과safeavailability/detail link를사용하며본문을재요약하지않는다. 실질적인본문fact/entity/compliancehardfailure는기존정책을적용한다.

ContentEditionAvailability는 normal/quiet/source_limited만 draft/view에 허용한다. generation_failed는 E1 absence/generation_absent, trust_blocked는 기존 finalization outcome이며 실패 문서를 봉인하지 않는다. 유효 sibling과 기존 partial/exit/실패 시장 안내를 유지한다. EventVisualInput은 봉인 전에 E1 자산 staging으로 전달하고 최종 survivor의 used-only 후보만 봉인한다. 봉인 후 자산 생성이나 본문 재작성은 없다.

## 단일 finalizer와 전환

현재public_document.py의FinalizedPublicDocument는briefing을보유하고writer가document.briefing.rendered_markdown에의존한다. v3는PublicEditionView를가지고공통readonlyrendered_markdown/target_date/segment/hashaccessor를제공한다. legacyvariant는임시로oldBriefing을보유하지만v3에빈7sectionbridge를만들지않는다. v3가readonlymodelsview를통해다른컴포넌트에전달돼moduleboundary가유지된다.

_REGION_SPECS/expectation은schema별필수영역을검증한다. v3의event/fact/context/followup/reference/disclaimer지역은typedIDs로소유한다. numeric/entity/actualforecast/freshness/compliance/disclaimer/artifact/notification/sha/remote/partialgate는공통이다. 기존hardfinding은reconciliation전에수집하고제거한event를digest/followup/assetimpact/storydelta에서제거한후reindex한다. 2회finalization의bytes/outcome이동일해야한다.

u168이선언한typedStoryStateProposal/StoryPublicationDelta를C5seam에서검증한다. u170없을때는빈tuple이고상태기록을만들지않는다. u170입력이있으면terminal에표시된readerstate/IDs/facts/refs와matchingproposal/next_record_hash를대조하고그projection만seal한다. unknownsource/proposal/opaquehash만으로ledger를승격하지않는다.

## NFR와 전환

HTTP/LLM 단계 추가0,16KiB protected bytes와 기존 provider budget, secret-safe private buffers, seal 후 rewrite0을 지킨다. v2 active/legacy를 잠시 병행하는 동안 segment별1개 schema만 게시한다. u171의 소비자 전환과 u172의 모든 시장 수용/10회 관찰 뒤 기본 v3와 legacy runtime 제거가 이어진다. rollback은 이전 reviewed commit 단위다.

## 설계 수용

정책·실적·서비스·긴이름·다중fact에서필수내용이짧은요약제약으로소멸하지않고,quiet/limited/failed가서로다르며,월간/주간배경이headline으로반복되지않는최종Markdown/HTML을검증한다. 실제numeric/entity/compliancenegative와validsibling/asset/seal/partial회귀를함께검증한다. 상세AC는[계획](../plans/u169-event-first-document-and-finalization-code-generation-plan.md).
