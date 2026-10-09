# Event/news v3 — 처리·실패·소유권 규칙

**Date**: 2026-10-10. **Status**: 구현 예정 계약. Shared 타입·상한은 [contracts.md](contracts.md).

## B1. 관측과 source
orchestrator가sourceclock·가격기준일·newswindow·버전policy를한번구성한다. u160의확정창과sourceoutcome을전달하고u165의failed/zero/skipped를구별한다. source/bodyqualification이없는URL/path는요청하지않으며본문실패가유효feed를삭제하지않는다.

## B2. 근거 구성
sources는같은run의source-ownedchunk와시각precision을작성하고models로전달한다. source가확인하지않은actual/예상/guidance/사건시각을생성하지않는다. chunk/text와refs는generationprivatebuffer이며공개ledger/log가아니다.

## B3. Stage1과 후보
Stage1 v3는최대12typed후보와역할별refs를반환한다. parent는item/document/chunk소유권,span경계,actor/fact/time/relation/impact를검증한다. 의미/반응refs는독립역할로허용하지만후보에속하지않은기사나미전달text를가리킬수없다. requiredactual을unassigned로잃지않는다.

## B4. Identity와 editorial selection
u168이source-backedentity/factidentity와30일remote-confirmedhistory로novelty/delta를판정한다. parent는실제impact/신규성/시장관련성/근거/예산을고려해0~5사건을선정한다. 같은사건의중복보도는합치되같음이불확실하면merge하지않는다. 다양성은보조기준이고유형별quota는없다.

## B5. 입력 예산
필수fact·identity·time근거를먼저배정하고meaning/reaction과optionalbackground/follow_up을이어배정한다. 전송UTF-8bytes와actualrows로budget을계산한다. 16KiB를못맞추면optional을줄이고그래도부족하면후순위event를budget_deferred로제외한다. selectedplan과protectedblock이불일치하면generationerror이며정상0건으로숨기지않는다.

## B6. Stage2 v3와 단일 원본
Stage2는EventEditionDraftschema3JSON만반환한다. 자유7sectionMarkdown을동시에생성하지않는다. parent-owned선정사건/fact/ref/placement를바꾸거나새URL을추가할수없다. article별본문/의미/반응을검증하며failurefield/rulecode는boundedprivate로기록한다. 기존두단계와총attempt/deadline을유지한다.

## B7. 렌더와 region ownership
publisher는typededition을결정론적으로render하고u144같은finalizer에서조립·projection·repair·reindex·hardgate·seal을실행한다. v3구조는schema별RegionSpec으로검증한다. writer/consumer가7개가짜section을채우지않으며v1/v2readerformat체인을v3에적용하지않는다.

## B8. Hard trust와 survivor reconciliation
원래draft의numeric/entity/compliance/disclaimer/structurefinding을수집하고기존owner의containment규칙을적용한다. 제거한event/fact는digest/follow_up/assetimpact/storydelta에서재등장하지않는다. reconciliation은selectedevent수+1이내에fixedpoint여야한다. 이후readonlyvalidation과seal이이어진다. 소멸한source근거로meaning/reaction을유지하지않는다.

## B9. 수집 제한과 조용한 날
quiet는정상적수집에서중요변화0일때만가능하다. 제한적sourcecoverage의0건은source_limited다. generation_failed는 기존 E1 absence/generation_absent, trust_blocked는 finalizer outcome으로 표시한다. 실패 문서를 봉인하거나 archive에 발행하지 않는다. 원인미확인가격변화는관측사실로남길수있지만causality를만들지않는다.

## B10. Story transaction
StoryStateProposal은privatepre-sealinput이다. 실제publicarticle/follow_up에남은projection만StoryPublicationDelta로봉인한다. orchestrator가같은publicationtransaction의ledgerbytes에담고기존원격확인/CAS/PublishReceipt로확정한다. unseenproposal/failedpublish/preview/shadow는publicstate나freshness를갱신하지않는다. ledgerTTL또는ticker매칭은resolved근거가아니다.

## B11. 독자 표면
모든표면은PublicEditionView/terminalDTO만읽는다. Telegram최종UTF-16budget은4096이다. v3의eventlist를우선하며다른시장전체실패안내·링크·면책필수내용을예산밖으로버리지않는다. 홈/회고/OG/관심자산에서삭제사건·unsealedtext·가격only를새사건요약으로사용하지않는다.

## B12. 발행 완전성과 rollback
신뢰차단/generationabsence가있는시장은validsibling만기존transaction으로발행하고partial/exit2/Pagesdispatch를유지한다. 0survivor/publishfailure는exit1,콘텐츠완전한notification-onlyfailure는기존exit0이다. presentation결함만으로유효시장을소멸시키지않는다. rollback은schema2reviewedpin/policy단위이며별도hidden7section이나매일추가LLMfallback을운영하지않는다.
