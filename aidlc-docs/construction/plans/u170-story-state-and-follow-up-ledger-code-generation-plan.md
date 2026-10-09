# Code Generation Plan: u170 story-state-and-follow-up-ledger

**Date**: 2026-10-10
**Unit**: u170 story-state-and-follow-up-ledger
**Stage**: Functional Design/NFR Required → Code Generation planned
**Status**: 문서 초안 작성; 구현 0/8; 승인·시험·commit/push·운영 활성화 미완료
**Source**: 사용자 event/news 이상향 및 구조 변경 허용 문서화 요청; frozen `19c89b92`의 실제 carryover/watchpoint/publication 경로
**Estimated Effort**: 24–36 h; state fixture/CAS/finalizer integration에 따라 조정
**Dependencies**: u168 canonical-event-identity-and-fact-delta와 u169 event-first-document-and-finalization. u167 follow_up chunks/ContextRef/time를 입력으로 재사용한다.
**Normative**: [design-brief](../u170-story-state-and-follow-up-ledger/design-brief.md), [공통 C3/C4/C5/C6/C7](../event-news-v3/contracts.md).

## Problem Statement

현재 archive carryover의 회사/topic substring match는 다시 보도된 사건을 해결됐다고 표시할 수 있다. 신규 u162 watchpoint는 source-backed 사실을 보존하지만 다음 확인이 generic event-kind template에 머물 수 있다. canonical occurrence와 누적 fact delta로 일관된 story state를 관리하고, 실제 독자에게 봉인된 state만 다음 실행에 이어갈 필요가 있다.

근거: `src/investo/briefing/carryover_parser.py:412-449`, `src/investo/models/carryover.py:78-102`, `src/investo/orchestrator/pipeline.py:3315-3339`, `src/investo/publisher/event_watchpoints.py:38-48,94-168,172-206`, `src/investo/orchestrator/event_publication.py:67-85`, `src/investo/publisher/public_document.py:4012-4085`.

## Goal

previous state → source-backed verified change → open question → source-backed next check → explicit resolution/cancellation을 typed story로 연결한다. 이름 재등장/예정일 경과/TTL/수집 실패로 confirmed·implemented·resolved를 발급하지 않는다. 미확인 상태는 미확인대로 유지하면서 사실이 추가될 때만 독자에게 변화가 드러나게 한다.

## Existing Coverage / Deduplication

- u52 archive carryover와 u59 macro carryover를 v3 일반 story ledger와 구별한다. 기존 schema2 historical parsing/rollback은 유지하지만 v3 state의 권위로 사용하지 않는다.
- u168은 entity/occurrence/fact delta/30일 hash identity history 소유다. u170이 이를 다시 정규화하거나 새로운 event ID를 만들지 않는다.
- u169는 EditorialPlan/EventArticle/FollowUpEntry·renderer·sealed document union 소유다. u170은 그 입력인 StoryRecord/NextCheck와 source-backed proposals만 제공한다.
- u162 tagged numeric/event family를 재사용한다. numeric current 검증/u152를 회피하는 새 family/renderer/fallback은 만들지 않는다.
- u144 단일 generated→sealed finalizer와 existing receipt/CAS transaction 재사용. 새 finalizer·post-seal writer·별도 git push 없음.
- 공통 evidence/time/support/diagnostics는 u167, semantic/live cutover는 u172, source qualification은 u173 소유다. 이 유닛의 state 머신 통과를 source 사실의 semantic truth로 간주하지 않는다.

## Scope Boundary

In scope: u168 foundation `src/investo/models/event_story.py`의 공유 타입을 소비하는 신규 `src/investo/briefing/event_story.py`, `src/investo/orchestrator/event_story.py`; 기존 `briefing/generation_contract.py`, `orchestrator/pipeline.py`의 explicit frozen input/metadata composition; `publisher/event_watchpoints.py`의 tagged-family v3 input adapter; u169 소유 finalizer/DTO의 StoryPublicationDelta hook 통합; 신규 tests/fixtures. u168이 먼저 정의한 전체 StoryState/SealedStorySourceRef/NextCheck/StoryRecord/StoryStateProposal/StoryPublicationDelta 타입을 재선언하지 않는다.

Out of scope: 다른 renderer·새 section 구조·Telegram/OG/Pages·surface gate·editorial score·source/HTTP/LLM 단계·DB; 임의 예측/예정일/numeric triggers; archive backfill·legacy state 자동 확정; production policy/runtime pin/cursor/body activation 변경; private chunk/public ledger 혼합.

## Stage Decision

**Functional Design REQUIRED**: family-specific transition과 state-vs-disposition, source-backed next check, closure의 독자 의미가 새롭다. 현재 design brief는 draft이며 승인 기록이 없다. **NFR Requirements REQUIRED**: remote public reader-state ledger,180일 inactivity/90일 closed retention/segment200active/5MiB와 CAS/TTL/public-private provenance가 바뀐다. 기존 NFR-001/002/003/004/005/006/007·R13·DEBT-090 재사용. 데이터 수명이 바뀌므로 새 I/O가 없다는 이유로 NFR를 skip하지 않는다. docs-only 요청만으로 code generation/activation을 시작하지 않는다.

## Fixed Contracts

1. shared models owner는 `models/event_story.py`; pure advance는 `briefing/event_story.py`; remote input/write preparation은 `orchestrator/event_story.py`다. publisher는 models 타입만 소비한다. u169의 FollowUpEntry와 renderer를 복제하지 않는다.
2. `StoryState`는 announced/pending/confirmed/implemented/resolved/cancelled/unknown. active/archived_unknown/closed는 별도 disposition이다. S170-1~3·family table·source time/operational clock 구별은 design brief에 고정한다.
3. no-new-evidence는 state/question/last_evidence_at 유지다. ticker·회사명·동일 fact 반복·날짜 경과는 transition evidence가 아니다. fact delta 없는 동일 event 재등장은 headline promotion0이다.
4. resolved/cancelled는 명시한 조건을 source가 확인하고 resolution facts/refs가 있어야 한다. pending은 source 미결 근거가 있어야 한다. source conflict/unknown으로 기존 검증 state를 조용히 downgrade하지 않는다. closed reopening은 기존 기록 덮어쓰기가 아니라 explicit related new story다.
5. scheduled next check는 fact/source timestamp exact/date와 refs 필수다. date-only source를 midnight UTC로 발명하지 않는다. 시간 미상은 observation_question으로 유지하며 임의 일정을 만들지 않는다.
6. u162 numeric/event tagged family를 재사용하되 v2 composition 제약을 schema3와 혼합하지 않는다. v3 FollowUpEntry 최대3개이며 같은 state를 별도 legacy §⑥ 카드로 중복 표시하지 않는다.
7. 공개 ledger `archive/_meta/event_stories_v3.json`, schema_version3; 진행 story segment당200,전체5MiB;180일 무근거는 archived_unknown·state 유지,closed_at 기준90일 후 closed retention 종료다. silent overflow eviction/state resolution0이다.
8. raw chunks/private fixture/원문 quote/secret은 public ledger에0. 이미 sealed reader text·validated source href·IDs/hashes/clock/source ref receipts만 저장한다.
9. `StoryPublicationDelta`는 u168 foundation models 계약이며 u169/u144 E5가 survivor에서 생성·봉인한다. prior/next state·prior hash·event/fact IDs·typed next_record·next_record_hash·source receipts·observed UTC clock·disposition을 담는다. u170 통합 전 tuple은 empty다. u170은 same-run typed StoryStateProposal/record/hash와 결속한다. invisible proposal 및 removed/trust-blocked dependency의 ledger update0이다.
10. 동일 remote SHA의 identity/story/news metadata paths를 한 PublicationRequest/CAS transaction으로 게시한다. pending/outcome_unknown/local dirty state를 다음 baseline으로 읽지 않는다. preview/shadow/off production write0이다.

## Implementation Steps

- [ ] **Step 1 — FD/NFR·모델 확정**: S170-1~3/transition table/closed+archived retention/모듈 소유권과 승인 기록을 확정한다. u168 foundation의 전체 공유 DTO와 u169 standalone typed record 검증/empty tuple seam을 확인한다. 모델을 재선언하지 않고 private ContextRef 구별·date precision·typed proposal/record/hash 결속 tests를 만든다.
- [ ] **Step 2 — Source-backed linking과 reducer**: u168 hint/bindings/delta와 prior record로 deterministic story linking을 구현한다. family별 signal/allowed edge/required refs/resolve conditions·no-new-evidence·conflict 결과를 pure functions로 구현한다. 회사명/ticker matching을 사용하지 않는다.
- [ ] **Step 3 — Concrete question/next check**: explicit open question, scheduled fact/time/ref, observation_question을 검증하고 FollowUpEntry용 proposals를 선택한다. editorial owner의 priority를 소비하고 max3·stable ordering·zero/no-evidence distinction을 확인한다.
- [ ] **Step 4 — Fixed remote ledger/retention**: u168의 같은 baseline SHA에서 story ledger를 읽고 stable exact-byte serialization,200active/5MiB·180일 disposition/90일 closed cutoff·overflow errors를 구현한다. private input과 public sealed provenance를 분리한다.
- [ ] **Step 5 — Generation/u162 handoff**: 기존 두 단계 안에 typed story input/proposal을 연결한다. NextCheck→existing tagged event input adapter를 구현하고 numeric current validation을 유지한다. schema3에서 archive substring/generic template 기반 success inference를 제거한다.
- [ ] **Step 6 — u169 E5 survivor/transaction integration**: 기존 u169 hook에 source-backed frozen record proposal/next_record_hash 검증을 연결하고 실제 finalizer가 article/followup/claim removal을 반영한 StoryPublicationDelta를 생성·봉인하게 한다. orchestrator는 frozen delta와 prior hash·next_record_hash로 동일 record를 검사해 combined metadata transaction을 준비한다. visible state와 ledger state 일치·no post-seal rewrite를 검증한다.
- [ ] **Step 7 — Negative/compatibility/clock verification**: 아래 negative matrix, actual finalizer partial removal/omission, CAS competing writers, push-response loss, replay/shadow write0, retention boundary와 state-table PBT를 통과한다. v2 carryover/watchpoint bytes와 imports를 유지한다.
- [ ] **Step 8 — Full gate·review·handoff**: focused/full regression, type/architecture/privacy check,200active/5MiB serialized/time 측정, independent review 및 AC cross-check를 기록한다. 완료 시에도 runtime activation은 u172 acceptance와 분리한다.

## Acceptance Criteria

1. **AC-170.1**: 서로 다른 products/periods/decisions와 회사명/ticker 재등장은 자동 linking/resolution하지 않는다. explicit official/cross-reference는 deterministic story로 연결하며 original event/fact/source provenance가 보존된다.
2. **AC-170.2**: family transition table에서 confirmed/implemented/resolved/cancelled는 source-backed 현재 사실·근거를 요구한다. no-new-evidence·revision-only·시간경과·수집실패는 기존 state/question/last_evidence_at을 유지한다.
3. **AC-170.3**: resolution에는 exact question과 ResolutionTarget의 동일 occurrence 또는 explicit linked release/thread·issuer·period·status·metric 조건을 충족하는 resolution facts/refs가 있다. cancelled에는 철회/취소/결렬 evidence가 있다. forecast/quoted opinion을 actual completion으로 바꾸지 않는다.
4. **AC-170.4**: source conflict/unknown은 별도 limited/conflict outcome이며 기존 확인 state를 unknown으로 덮어쓰지 않는다. closed record는 immutable이며 명시 재개는 related new story가 된다.
5. **AC-170.5**: scheduled next check는 source-backed fact/time/ref를 요구하고 date-only는 date로 표시된다. timestamp 없는 관찰은 구체적 observation_question이며 invented future date/numeric trigger0이다.
6. **AC-170.6**: v3 FollowUpEntry max3·순서 불변·no duplicate story/state가 통과한다. same event/no delta headline promotion0이다. numeric/event current/source 검증은 우회되지 않고 v2 mixed2/numeric6/fallback2 fixture는 회귀 동일하다.
7. **AC-170.7**: public ledger에 raw chunk/quote/private fixture/secret0이며 reader state·validated href·IDs/hash/시각만 있다. 진행200/segment·5MiB actual bounds가 지켜지고 overflow는 explicit failure다.
8. **AC-170.8**:180일 무근거→archived_unknown과 closed_at+90일 retention이 boundary fixture로 검증된다. latest_state는 TTL로 resolved되지 않으며 no-new-evidence로 clock/retention을 연장하지 않는다. source date와 operational UTC clock은 서로 대체되지 않는다.
9. **AC-170.9**: 실제 E5 sealed delta는 reader-visible survivor claim/fact/ref와 prior baseline hash에 정확히 결속된다. invisible/removed/trust-blocked transition은 update0, 생존 story는 summary/reader/ledger에서 같은 state다. finalization idempotence·post-seal mutation0이 통과한다.
10. **AC-170.10**: fixed remote baseline·combined metadata CAS·existing PublishReceipt로만 state를 advance한다. pre/post-commit 실패·response loss·competing writer에서 overwrite/false confirmed0이다. local dirty/pending/outcome_unknown은 next baseline이 아니다.
11. **AC-170.11**: off/shadow는 기존 schema2 공개 bytes·알림·receipt·cursor 동작을 유지하고 신규 v3 ledger write0이다. preview의 archive/git/알림/production ledger/cursor write0이며 v3가 추가하는 HTTP/LLM0이다. v3가 legacy substring carryover/generic next-check 성공 추론을 호출하지 않는 architecture guard가 있다. existing archive/URLs는 그대로다.
12. **AC-170.12**:200active/5MiB/96candidate/3followup의 실제 bytes/time과 regression commands/AC mapping이 기록된다. offline tests로 live semantic/source/runtime activation acceptance를 주장하지 않는다.

## Tests / Validation

신규 구현 시험: `tests/unit/models/test_event_story.py`, `tests/unit/briefing/test_event_story.py`, `tests/unit/orchestrator/test_event_story.py`, `tests/integration/test_event_story_finalization_v3.py`, `tests/integration/test_event_story_publication_v3.py`. 기존 재사용 시험: `tests/unit/publisher/test_event_watchpoints.py`, `tests/unit/publisher/test_event_watchpoint_composition.py`, `tests/integration/test_mixed_event_watchpoints.py`, `tests/unit/briefing/test_carryover_parser.py`, `tests/unit/orchestrator/test_event_publication.py`, `tests/integration/test_event_publication_boundary.py`, `tests/unit/publisher/test_public_document_architecture_u144.py`, `tests/unit/_internal/test_module_boundary.py`.

신규 고정 fixture: `tests/fixtures/event_briefing_v3/u170/story_transitions.json`, `story_linking.json`, `next_checks.json`, `retention_boundaries.json`, `sealed_survivor_updates.json`, `publication_failures.json`. 입력에 explicit clock/source time precision/prior sealed record/u168 fact delta/ContextRefs와 expected edge/result/reader state/delta membership을 넣는다. expected는 implementation reducer로 자동 생성하지 않는다. source snippets는 권리·R13를 통과한 synthetic 또는 qualified fixture로 작성하며 public ledger fixture와 raw private input fixture를 분리한다.

| Negative / 경계 case | 반드시 확인할 결과 |
|---|---|
| 회사명/ticker 재보도, topic substring, 기간이 다른 실적 | unresolved state 유지; 잘못된 linkage0 |
| 예정일/주말/180일 TTL 경과·fetch failure | confirmed/implemented/resolved0 |
| 법안 발의 vs 의결 vs 시행, 서비스 발표 vs 실제개시 | source 단계에 맞는 state; shortcut0 |
| 협상 결렬/공식 철회와 cancelled refs 부재 | source-backed cancelled만 허용 |
| oldactual와 contradictingnewactual, unknown evidence | currentstate silent downgrade0; conflict 보존 |
| 시각없는 next check, date-only schedule | invented date0; date precision 유지 |
| nofactdelta 동일event 재보도 | headline 승격0; clock 갱신0 |
| generic `_NEXT_CHECK`만 제공·numeric current 없음 | 성공 transition/card로 우회0 |
| article/follow_up 하나 finalizer 제거, invisible4번째proposal | 해당 semantic ledger update0; orphan summary0 |
| active201/segment·5MiB+1·recordevents129/refs65 | explicit budget failure; silent pruning0 |
| day179/180/181와 closedday89/90/91 | UTC operational cutoff와 별도 source precision 검증 |
| shadow/preview·dirtylocal·push unknown·concurrentCAS | productionwrite0/committedstate advance0/overwrite0 |
| existingclosed 재등장 | 원기록 immutable; explicit newrelatedstory만 |

미래 실행 명령(이 docs-only 작업에서는 실행하지 않음):

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/unit/models/test_event_story.py tests/unit/briefing/test_event_story.py tests/unit/orchestrator/test_event_story.py tests/integration/test_event_story_finalization_v3.py tests/integration/test_event_story_publication_v3.py tests/unit/publisher/test_event_watchpoints.py tests/unit/publisher/test_event_watchpoint_composition.py tests/integration/test_mixed_event_watchpoints.py tests/unit/briefing/test_carryover_parser.py tests/unit/orchestrator/test_event_publication.py tests/integration/test_event_publication_boundary.py tests/unit/publisher/test_public_document_architecture_u144.py tests/unit/_internal/test_module_boundary.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run python scripts/check_no_paid_apis.py
uv run python -m pytest -q
git diff --check
```

actual finalizer integration은 u169의 실제 EventEditionDraft와 frozen sealed DTO를 사용한다. helper가 만든 fake sealed bytes로 AC-170.9를 대신 입증하지 않는다. publication tests는 existing GitRunner로 remote baseline/ancestry/content/CAS를 fixture화하고 테스트 중 실제 push/Telegram/production file write를 하지 않는다. PBT는 순수 linking/reducer/serialization·no-new-evidence/idempotence·allowed transition invariants에 한정한다.

구현 evidence는 `aidlc-docs/construction/u170-story-state-and-follow-up-ledger/code/validation.json`에 명령/exit/fixture hash/AC/byte+time 측정으로 기록한다. 문서의 checkbox·test 이름은 실행 결과가 아니며 현재 구현0이다.

## Non-Goals

### Migration / Removals

schema3가 `briefing/carryover_parser.py`의 substring/ticker resolved inference와 generic event-kind next check를 fresh state authority로 사용하지 않도록 제거한다. legacy API/archives는 historical read-only parsing/schema2 rollback에서만 남긴다. old archive의 §⑥ text를 scan하여 v3 story ledger를 채우거나 closure를 발명하지 않는다. live v3 ledger missing은 available empty bootstrap이며 migration은 explicit frozen replay inspection뿐이다.

follow-up는 u169 본문 typed region에서 한 번 렌더링한다. 새 event card layout/종합 watchpoint engine/semantic grader/source registry/activation workflow는 범위 밖이다. docs-only 완료, code validation 완료, remote delivery, runtime cutover를 따로 보고한다.
