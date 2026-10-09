# Event/news v3 — 실제 수용과 운영 전환

**Date**: 2026-10-10. **Status**: 앞으로 수행할 계약; 점수·발행 횟수·자격 합격을 이 문서로 생성하지 않는다. Canonical 평가 모델과 상세 AC는 [u172](../u172-real-event-semantic-acceptance-and-cutover/design-brief.md)가 소유한다.

## A1. 분리해서 측정할 것

| 측정 | 분모 | 사용할 근거 |
|---|---|---|
| 외부 중요 사건 포착 | 발행 시점에 접근 가능한 자료로 미리 주석한 must-cover 사건 | 출력을 보기 전에 확정한 사람 baseline·source 범위·기간 |
| 후보 안의 중요 사건 선정 | 실제 수집/후보에 존재한 must-include 사건 | source/context/Stage1 candidate lineage |
| 선정→최종 생존 | parent가 선정한 사건 | 실제 terminal HTML/DTO/survivor |
| 필수 fact 보존 | 선정 사건의 required fact | exact refs/actual-forecast/단위/기간과 최종 본문 |
| 설명 이해도 | 검수 대상 실제 사건 | 사람 what/when/why/react/source 각0/1 |
| 이어 읽기/쓸모 | 검수 대상 story/follow-up/자산 영향 | prior state·실제 delta·다음 질문·관련 경로 |

각 값은0/null/unknown을구별한다. 내부selected가적거나source제한이있으면생존률100%만으로전체뉴스포착을주장하지않는다. unavailable반응을정직하게설명한경우는react항목의유효한답일수있다. ‘왜중요한지모름’을지표숫자로채우거나근거없는인과를넣으면합격이아니다.

## A2. 필수 평가 자료

1. **균형 합성matrix:** 기존12 scenario categories를세시장에각각적용하여최소36case를만든다. 정상사건양성,quiet,sourcefailure,주말/휴일,독립meaning/ref,긴이름,4docs/8facts,변화없는배경,normalizeddelta,storytransition,삭제후surface일치,실제numeric/entity/compliancenegative를포함한다.
2. **실제privatecorpus:** 최소12최종문서,시장별4개,서로다른발행일2개이상이며각시장뉴스-rich사례를포함한다. sourcefailure/주말경계는별도실제기록또는명시된recordedreplay로검증한다. 확보하지못한자료는pending이다.
3. **사람평가:** what/when/why/react/source5/5,required fact100%,근거없는사건/인과0을실제최종본문·요약·반응·후속과원문으로평가한다. 모델자기채점이나releaseinstruction으로사람점수를만들지않는다.
4. **제품표면:** finalMarkdown/HTML/웹viewport/Telegramtext/홈/회고/OG/관심자산의같은event/story/상태를대조한다. actualsource관측기간과finalcodeSHA/hash를함께기록한다.

기존v2의12그룹25합성fixture와humanpending계약은그대로history로유지한다. v3새corpus가이를‘실제녹화/사람합격’으로다시라벨링하지않는다. raw실제입력은NFR-008/R13을따르는private/암호화경로이고public에는boundedmanifest/hash/합성재생만둔다.

## A3. code-ready / human-ready / release-ready

- code-ready: 정확한최종SHA의targeted/full/static/policy/docs,현재2provider계약,전체budget/실행시간,finalizer/partial/asset/ledgerCAS가합격한다.
- human-ready: 시장별actualcorpus/주석/rubric/금지주장/외부baseline범위와점수가완료된다.
- release-ready: currentruntimeowner/pin/mode/marketallowlist,기존source/cursor별gate,rollback,명시적release지시가확인된다.

셋은서로대체하지않는다. 기존u157~162의제한적운영예외와사람검수pending은과거사실로유지한다. 이설계작성은새v3release승인이아니다. source-slotverified도HTTP/cursor/human-ready를자동으로열지않는다.

## A4. preview와 시장별 active

preview/schema3는실제두단계LLM→typedv3→u144finalizer→terminalview까지수행하되archive/git/알림/productionreceipt/ledger/cursor쓰기0회다. 실행matrix에서한market실패와다른marketsealed성공을구별한다. 코인은자체actual성공/사람수용후에만allowlist에들어간다.

release지시후exactreviewedSHA와 policy을 읽고시장별active/schema3로전환한다. 최초3회genuine scheduledrun의 게시/Telegram/해당commitPages/identity-storymetadata/기존news-cursor를확인한다. manual같은 날 재생으로횟수를채우지않고source/생성/finalization/publish/notify/Pages/exit를분리해기록한다. partialvalidsibling을유지하며전체프로그램accepted는세market모두수용을요구한다.

## A5. 최종 cleanup

세시장accepted와실제v3예약10회관찰후u172Step9와[C8](contracts.md#c8-최종-runtime-폐기와-정착--u172)의별도reviewedcleanup을수행한다. 부분실패와제외시장을정확히집계하고성공횟수를합성run으로부풀리지않는다.

기본schema3와retiredpolicy거부,legacygenerator/free6sections/가짜bridge/oldliveconsumerfallback삭제를검증한다. v2terminalsnapshot/hash는제거전에고정하고historicalread/output회귀로바꾼다. cleanup코드의exactfullgate/독립review/v3byteparity와actualruntimepinreadback후cleanup_complete로표시한다. rollback은이전reviewedcommit/policy전체다.

## A6. release 이후 판단

hardtrust/semanticcriticalclaim실패는해당시장의promotion을멈추거나reviewedrollback한다. presentation한계만으로validsibling을없애지않는다. news창과source별coverage한계는계속독자/운영자료에표시한다. 성능·source·해외/국내각시장문제를별도owner로귀속하고문서적합률한개만으로제품완료를주장하지않는다.
