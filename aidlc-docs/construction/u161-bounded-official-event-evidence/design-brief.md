# Functional Design: u161 공식 사건 근거 보강과 뉴스 소스 복구 판정

**Date**: 2026-09-26
**Status**: Design approved by the 2026-09-27 sequential-development request. Queued — design approved; source qualification is part of implementation; body fetch remains gated.
**Priority / effort**: P1 / 16–24 h plus source qualification (rough engineering estimate, not commitment).
**Dependencies**: 자격검증/기존feed진단은독립. typed enrichment integration은u157. 신규officialbody는source별qualification후에만구현/활성화.

## Reader problem
기존뉴스에는280자요약/제목수준자료가많아정책발표·실적내용을충분히설명하기어렵다. 9/22검토에서는CNBC/Korea policy반복장애가있었다. 현재접속상태는qualification에서다시확인한다.

## Ownership and deduplication
Existing owners: u103 Fed/SEC RSS, u126 CFTC RSS, u1/u102 adapterregistry, u27 R13, u95 runtime budgets.
Existing code touch points: `sources/fed_speech_rss.py, fomc_rss.py, sec_newsroom_rss.py, cftc_policy_rss.py, cnbc_top_news.py, korea_policy_rss.py, _retry.py, sources/aggregator.py, orchestrator/pipeline.py, briefing/generation_contract.py, models/items.py (u157 evidence field), sources/aggregator.py, briefing/generation_contract.py`.
Proposed new modules: `sources/event_evidence.py; ops/event_source_qualification.json (planned contract)`. These paths do not imply implementation exists.

## Shared contracts
[Program overview](../news-event-briefing/README.md), [entities and schema](../news-event-briefing/event-contract.md), [business rules](../news-event-briefing/business-rules.md), [NFR and evaluation](../news-event-briefing/nfr-and-validation.md).
The unit-specific rules below bind the shared contract. Inconsistency must be resolved in design before code; implementations cannot silently override common identity/budgets/trust semantics.

## Fixed contracts
1. Stage A는기존CNBC/Korea policy의현재URL/redirect/status/parser/header를읽기전용probe하고기존제공자의공식feed안내와대조한다. 기존source이름/category/tier/routing은보존한다. 허용된동일제공자경로가검증되면bounded수정,아니면blocked/failed상태로남긴다. 다른매체를기존이름으로대체하지않고403우회기술을추가하지않는다.
2. 기존 허용 feed를 parsing하는 시점에 280자 summary 절단 전에 EvidenceDocument.detail_excerpt를 최대 1200자로 만든다. u157의 default-None NormalizedItem.event_evidence에 담아 SourceCollectionReport.items → CollectStage → GenerationInput.items로 운반한다. document/revision identity로 검증하며 routing/filter는 item과 함께 이동한다. sources는 briefing을 import하지 않는다. summary/global cap/raw_metadata는 그대로다.
3. Stage C의첫qualification집합은fomc-rss, fed-speech-rss, sec-newsroom-rss, cftc-policy-rss가직접인용한공식원문이다. 검증된host/path/MIME/parser와공식이용근거/livefixture해시가opsmanifest에없으면새HTTP는0회다. 현재문서는어느bodyendpoint도qualified로선언하지않는다.
4. models 소유 EnrichmentPolicy와 sources helper를 orchestrator가 collection 후 generation 전에 호출한다. Stage C는 frozen item의 typed evidence를 보강하고 revision을 다시 계산해 새 item을 반환한다. source당 최대 2개, bundle 최대 6개를 최근순/source round-robin으로 고른다. 추가 LLM이나 Stage1 이후 fetch는 없다. Stage2는 실제 선정된 spans만 소비한다.
5. bundle6요청/동시2/요청8초/총20초/500KiB/소스2기사/excerpt1200자,원문fetch추가retry0. 기존streamingretry_get의작은RetryConfig와외부aggregate deadline을재사용한다. redirect도요청예산에포함하고부족하면후속fetch를하지않는다.
6. timeout/403/404/selector변경/HTML없음은원feeditem을보존하고enrichment_unavailable를기록한다. 본문성공과source수집성공은별도다. text에는eventtime/actual/guidance가실제로있을때만추출하고없으면만들지않는다.
7. SEC8-K첨부실적,기업IR/상품발표원문,DARTviewer,상업매체본문수집은v1본문fetch범위밖이다. 기존feed의실적/상품뉴스는u157/158에서이미처리하고깊이부족을표시한다. 이후새adapter는새qualification기록과명시범위확장으로진행한다.
8. qualificationrecord필드: source_name, checked_at, official_discovery_url, allowed_host/path, content_type, public_rights_basis, extraction_selector_version, fixture_sha256, status=qualified|blocked|rejected, reason. HTTP200만으로qualified를주지않는다. accessrestriction/권리불명은blocked,제공자변경은새source후보로분리한다.

## Stage decision
Functional Design: REQUIRED — new cross-module/event behavior; this document and shared contracts were approved by the 2026-09-27 implementation request.
NFR Requirements: REQUIRED — 새로운외부본문I/O와source권리/fixture/SSRFlimit/latency. NF1/4/6/7/8/10, NFR-008 적용.
Separate NFR Design/Infrastructure Design: no separate artifact for pure code; focused runtime/storage rules are fully specified here. u160/u161 public I/O and transaction rules require their NFR review before implementation. No new deployment platform.

## Failure and compatibility
Apply B4/B5/B8/B11 and unit-specific states. Off mode preserves current producer/consumer behavior. Existing numeric/entity/compliance hard gates and sibling availability remain authoritative. Code-ready status requires hard dependencies and design approval; source qualification stays separate from code readiness.

## Acceptance criteria
- AC-161.1: CNBC/Korea policy 각각현재원인/동일source수리결과또는blocked이유가실제증거와함께있다.
- AC-161.2: qualification이없는URL/새provider/access제한을자동fetch하지않고qualifiedHTTP외에는원feed를유지한다.
- AC-161.3: 281~1200번째 문자에만 있는 핵심 사실이 typed evidence를 통해 Stage1 buffer와 Stage2 선정 span에 실제 도달한다. routing 제외/실패 source의 근거가 다른 item에 붙지 않는다.
- AC-161.4:6요청/동시2/20초/500KiB/소스2기사/excerpt1200상한과redirect/SSRFnegative가통과한다.
- AC-161.5:본문fetch실패가원뉴스를삭제하지않고가짜실적actual/정책결정/시점을만들지않는다.
- AC-161.6:rawbody/secret/privatefixture는publicgit에없고NFR-008/DEBT-090성능상태를정확하게보고한다.

## Development sequence
See [code-generation plan](../plans/u161-bounded-official-event-evidence-code-generation-plan.md). Implementation follows the 2026-09-27 user-authorized sequential queue.
