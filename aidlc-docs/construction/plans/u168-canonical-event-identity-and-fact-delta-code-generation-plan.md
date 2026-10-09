# Code Generation Plan: u168 canonical-event-identity-and-fact-delta

**Date**: 2026-10-10
**Unit**: u168 canonical-event-identity-and-fact-delta
**Stage**: Functional Design/NFR Required → Code Generation planned
**Status**: 개발 승인 기록; foundation 구현 5/8; native finalizer/transaction integration과 최종 unit 수용 미완료
**Source**: 사용자 event/news 이상향 분석 및 2026-10-10 문서 작성 요청; frozen `19c89b92`의 실제 코드
**Estimated Effort**: 24–36 h; 실제 identity fixture/CAS 검증 범위에 따라 조정
**Dependencies**: u167 event-context-evidence-and-quality의 C2 source-addressed refs·quality 입력. 소비 handoff는 u169·u170.
**Normative**: [design-brief](../u168-canonical-event-identity-and-fact-delta/design-brief.md), [공통 C2/C3/C7](../event-news-v3/contracts.md).

## Problem Statement

현재 v2의 사건 ID는 원문 actor/action/object와 날짜 또는 문서 alias로 만든다. 사건 날짜 없는 다른 매체 문서는 같은 occurrence라는 근거가 생겨도 흔들릴 수 있고, fact 원문 paraphrase는 material update처럼 보일 수 있다. 7일 ID별 마지막 receipt는 장기 사실 delta의 누적 비교를 충분히 제공하지 않는다. 뉴스 중심 제품은 reader에게 같은 사건의 새 사실과 반복을 구분해야 한다.

코드 근거: `src/investo/briefing/event_evidence.py:191-270,364-434,542-558`, `src/investo/models/events.py:158-225`, `src/investo/orchestrator/event_receipts.py:66-138`, `src/investo/orchestrator/event_publication.py:30-85`.

## Goal

source-backed canonical entity/fact를 부모가 결정하고, occurrence identity를 보존하며, source-backed delta만 material_update로 표시한다. 원문 refs와 상태·기간·단위는 그대로 검증 가능해야 한다. 무리한 merge를 허용하는 포착률 향상은 목표에 포함하지 않는다. 모호한 유사 사건은 uncertain_duplicate로 관찰하고 별도 ID를 유지한다.

## Existing Coverage / Deduplication

- u157의 source spans·parent-owned IDs·selection·remote receipt·CAS를 확장한다. 새 selection engine/finalizer/receipt transport를 만들지 않는다.
- u167이 EvidenceChunk/ContextRef/time/support vector와 diagnostics를 소유한다. u168은 evidence extraction/quality taxonomy를 복제하지 않는다.
- u169가 article/summary/editorial/render/finalizer 및 source facts의 reader 표시를 소유한다. u168이 headline·섹션·surface를 생성하지 않는다.
- u170이 story lifecycle/next check 의미/reducer/reader-state ledger를 소유한다. 의존 cycle을 막기 위해 u168은 C6 전체 frozen story DTO 선언과 source-backed hint만 foundation으로 제공한다. u169는 typed StoryRecord/StoryPublicationDelta를 검증하고 u170 reducer를 import하지 않는다.
- u160 news cursor/revision dedup은 document 관측이다. canonical occurrence/fact-delta가 이를 대체하거나 production cursor gate를 자동 통과시키지 않는다.
- 기존 numeric/entity/compliance/R13 gates, 기업·티커 registry, u144 publication transaction을 그대로 이용한다.

## Scope Boundary

In scope: 신규 `src/investo/models/event_identity.py`, `src/investo/models/event_story.py`의 전체 공유 DTO foundation, `src/investo/briefing/event_identity.py`; 기존 `orchestrator/event_receipts.py`, `orchestrator/event_publication.py`의 schema3 모델 호출·read/write preparation; `briefing/generation_contract.py`, `briefing/event_prompt.py`, `orchestrator/pipeline.py`의 typed handoff; 신규 단위/integration tests와 fixture. u169가 model/Stage2를 구현하기 전에는 u168 adapter contract test에서 출력까지 확인하며 가짜 빈 `Briefing`을 만들지 않는다.

Out of scope: 새 source/HTTP/LLM 단계, 통화·scale 환산/semantic paraphrase 통합, alias 추측, 중요한 사건 선정점수 재설계, doc/render/Telegram/OG/Pages, 독립 DB/search/vector store, 기존 archive 수정, v2 자동 backfill/ledger conversion, 활성화/runtime pin 변경.

## Stage Decision

**Functional Design REQUIRED**: entity alias, occurrence discriminator, explicit correction, unknown vs repeat, uncertain duplicate라는 신규 독자 semantics가 있다. design brief는 초안이며 별도 승인 기록이 없다. **NFR Requirements REQUIRED**: 30일/segment5000records/1MiB remote hash ledger 및 combined CAS/read budget/privacy가 바뀐다. 현 NFR-001/002/003/004/005/006/007, R13, DEBT-090 적용. 새 유료 API·추가 runtime call·secret은 없다. Code Generation은 해당 단계의 결정·승인 기록 뒤 시작한다. docs-only 요청을 구현 승인으로 해석하지 않는다.

## Fixed Contracts

1. canonical DTO owner는 `models/event_identity.py`, pure normalization owner는 `briefing/event_identity.py`, I/O는 기존 `orchestrator/event_receipts.py`다. publisher는 models만 import한다. shared contracts의 정의를 다른 layer에 복제하지 않는다.
2. E168-1~4의 field/literal/bounds·API는 design brief가 명시한다. EntityIdentity의 source alias·CanonicalFact의 status/period/unit은 유지하고 original refs를 삭제하지 않는다.
3. 정규화는 NFKC·공백·numeric thousands separator만 허용한다. semantic synonym·casefold·직함 삭제·임의 약칭·환산·반올림은 하지 않는다. 모호하면 raw identity다.
4. 공식 occurrence key 또는 source-backed cross-reference 없이 다른 문서의 tuple/날짜 유사성만으로 merge하지 않는다. 같은 document의 다른 제품·결정·발표 단계는 별도 event다. 상충 official alias는 explicit conflict다.
5. fact hash는 normalized fact tuple로 정의하고, provenance/document arrival을 identity에서 분리한다. retained history는 cumulative fact hashes와 explicit supersession pairs를 보존한다. input에서 missing인 fact를 correction으로 만들지 않는다.
6. `new|material_update|repeat|unknown`에서 unknown은 remote history 부재/불확실성, material_update는 명시적 added/corrected source-backed facts다. revision 변화만으로 update하지 않는다.
7. ledger path `archive/_meta/event_identity_v3/{segment}.json`, schema_version3,30일/segment5000records/1MiB. fixed remote baseline·stable serialization·existing CAS·sealed survivor-only write다. overflow는 explicit preparation failure이며 truncation으로 조용히 history를 잃지 않는다.
8. off/shadow/preview는 production metadata write0이다. v2 7일 ledger/IDs/bytes는 그대로다. v2→v3 migration은 replay inspection input만 허용하고 live ledger·source facts·story states를 복원하지 않는다.
9. u170/news cursor와 결합될 때 single baseline SHA와 합집합 metadata hash로 하나의 PublicationRequest를 사용한다. remote-confirmed가 아닌 receipt를 새 history로 사용하지 않는다.
10. identity/fact diagnostics는 u167의 closed field/rule/event-hash/attempt에 결속한다. 이 유닛에서 raw source/alias/value/URL을 exception·log에 내보내는 별도 diagnostic transport를 추가하지 않는다.
11. `models/event_story.py`는 C6 및 u170 S170-1~3의 전체 공유 frozen DTO를 foundation으로 정의한다. typed `StoryPublicationDelta.next_record: StoryRecord`·prior/next canonical record hash를 포함하며 decoder/opaque payload를 만들지 않는다. 모델 선언에는 reducer/state advance/ledger write/render0이다. u169 standalone compile이 u170 code에 의존하지 않는다.

## Implementation Steps

- [x] **Step 1 — FD/NFR 확정 및 contract tests**: E168-1~4, actual v2 callsite/import map, source-backed alias/occurrence/correction fixture matrix와 단계 승인 기록을 검수한다. C6 전체 story frozen DTO를 `models/event_story.py`에 foundation으로 선언하고 typed next_record/hash bindings의 standalone round-trip/import tests를 만든다. 이 단계에서 reducer/ledger/render를 구현하지 않는다.
- [x] **Step 2 — Entity normalization**: existing registry의 읽기 전용 deterministic resolver와 explicit alias proposals 검증을 구현한다. raw source label/provenance를 retained binding으로 보존한다. source 없이 생성한 alias/역할어→인물/다른 제품 suffix는 거부한다.
- [x] **Step 3 — Canonical facts와 delta**: 기계 정규화·value/period/unit/status identity·duplicate provenance union·added/unchanged/explicit supersession/conflict를 구현한다. 누적 facts를 입력 결손 때문에 삭제하지 않는다.
- [x] **Step 4 — Occurrence resolution**: official key/cross-reference/raw-document 순으로 match한다. existing remote ID 유지·같은 문서 여러 사건 분리·uncertain duplicate stable pair·official conflict를 구현한다. event identity와 story hint를 분리한다.
- [x] **Step 5 — Remote v3 ledger**: 기존 fixed remote load budget을 공유하는 schema-specific reader/serializer를 구현한다. segment scope·30일 rolling·5000/1MiB·cumulative hashes·fact slot/value association·overflow·missing vs invalid baseline을 검증한다. replay-only legacy adapter를 추가한다.
- [ ] **Step 6 — Stage/transaction handoff**: u167 source-linked input→canonical bindings/identity/delta→u169 editorial input을 두 기존 단계 안에 연결한다. E5 receipt를 existing transaction에 추가하고 concurrent metadata/CAS 실패·remote ancestry 확인을 검증한다. 별도 push/fetch·post-seal mutation을 만들지 않는다.
- [ ] **Step 7 — Negative/compatibility verification**: fixture의 reader-independent typed outcome과 actual public finalizer handoff가 agreement하는지 검증한다. 신규 v3 ledger의 off/shadow/preview write0, 기존 v2 공개 동작/bytes/receipt unchanged, original refs intact, ordering/idempotence/PBT를 통과한다.
- [ ] **Step 8 — Full gate·독립 review·handoff**: focused/full regression, ruff/mypy/module boundary, actual bound/performance 측정, AC별 evidence를 기록한다. u169/u170에 field·baseline/receipt·fixture를 전달한다. 구현 완료·remote delivery·activation은 각각 기록한다.

## Acceptance Criteria

1. **AC-168.1**: approved registry 또는 같은 source의 explicit alias만 같은 EntityIdentity를 만들며 original labels/refs가 보존된다. 근거 없는 번역·약칭·현재 직함·homonym은 합쳐지지 않는다.
2. **AC-168.2**: `1,200`/`1200`의 허용 변형은 같은 fact이고 metric/unit/period/status/subject/object가 다르면 다른 fact다. 같은 값의 revenue/net_income과 같은 공식 key의 상충 actor/action/object/stage는 합쳐지지 않는다. occurrence alias와 canonical_tuple_hash가 다음 remote run에도 같은 ID·conflict 판정을 보존한다. quote/forecast/actual 전환을 자동화하지 않는다. 원문 span 변경·doc 추가는 동일 canonical fact의 provenance만 늘린다.
3. **AC-168.3**: 같은 공식 occurrence/cross-reference는 doc arrival/permutation과 무관하게 ID를 유지한다. 같은 문서의 두 제품·같은 회사 다른 기간·scheduled vs actual 단계는 별도 occurrence다. 날짜/주체만 같으면 uncertain_duplicate다.
4. **AC-168.4**: 모든 material_update에는 current source refs로 확인 가능한 added/explicit correction delta가 있다. 제목/revision만 변화한 보도는 repeat, baseline unavailable은 unknown이다. 사라진 fact를 superseded로 표시하지 않는다.
5. **AC-168.5**: 누적 retained fact history에서 A→A+B→A→A+B는 B를 두 번 새 사실로 세지 않는다. explicit correction의 원본/대체 hash pair는 보존되고 conflicting actual은 정상 supported fact로 합쳐지지 않는다.
6. **AC-168.6**: v3 ledger는 segment scope와30일/5000records/1MiB의 actual serialized bound를 만족한다. missing remote file은 available empty, malformed/over-budget/read failure는 unavailable, overflow는 명시 실패다. raw source/value/label/URL/private fixture/secret이 없다.
7. **AC-168.7**: history는 fixed remote SHA와 sealed survivor로만 advance한다. removed/trust-blocked/preview/shadow event write0이다. single transaction의 combined metadata CAS가 충돌하면 덮어쓰기0이며 pre/post-commit·push-response loss 결과는 기존 PublishReceipt semantics와 일치한다.
8. **AC-168.8**: 동일 frozen input에서 순서 불변·순수 API 재실행 불변·DTO round-trip가 통과하며 새 HTTP/LLM0이다. source refs는 transmitted context 밖을 가리키지 못한다. 전체 story DTO foundation이 typed next_record/hash·private/public refs로 독립 compile/round-trip하고 u170 reducer/ledger 없이 import된다. models→publisher·publisher→briefing 새 import0이다.
9. **AC-168.9**: schema2 output/receipt/legacy imports와 archive bytes는 회귀 동일하다. replay adapter가 old hashes로 canonical 사실·날짜·story를 발명하거나 live v3 ledger를 자동 갱신하지 않는다.
10. **AC-168.10**: 5000record/1MiB/96candidate 경계에서 실제 runtime/bytes를 기록하고 기존 deadline·DEBT-090 검토에 제공한다. 계획상의 상한만으로 성능 통과를 주장하지 않는다.

## Tests / Validation

신규 시험 파일은 구현 시 생성한다: `tests/unit/models/test_event_identity.py`, `tests/unit/models/test_event_story_contract.py`, `tests/unit/briefing/test_event_identity.py`, `tests/unit/briefing/test_event_fact_delta.py`, `tests/unit/orchestrator/test_event_identity_ledger_v3.py`, `tests/integration/test_event_identity_v3_boundary.py`. `test_event_story_contract.py`는 모델/import/bindings만 확인하며 state transitions는 u170 시험이다. 재사용 검증: `tests/unit/orchestrator/test_event_receipts.py`, `tests/unit/orchestrator/test_event_publication.py`, `tests/integration/test_event_publication_boundary.py`, `tests/unit/_internal/test_module_boundary.py`.

신규 고정 fixture: `tests/fixtures/event_briefing_v3/u168/entity_aliases.json`, `occurrences.json`, `fact_deltas.json`, `ledger_boundaries.json`, `migration_v2_replay.json`. 각 파일에 version, case_id, source-owned ContextDocument inputs, expected closed result/ID relation/novelty/delta/exception code를 기록한다. expected를 구현함수로 자동 생성하지 않는다. PBT는 normalization·permutation·serialization·allowed state delta invariants에 한정한다.

| Negative fixture | 반드시 확인할 결과 |
|---|---|
| 같은 회사·날짜, 다른 제품/결정/발표단계 | 별도 occurrence; unsafe merge0 |
| 다른 doc에 같은 제목, explicit reference 없음 | uncertain duplicate; raw event IDs 분리 |
| role-only `Fed chair`→특정 인물 또는 한국어 alias 발명 | alias rejection; 원문 보존 |
| 실제/전망·단위·기간 다른 같은 숫자 | 별도 fact; status/scale 변환0 |
| source가 correction을 말하지 않은 fact omission | previous fact 보존; supersession0 |
| partial doc 추가·ref offsets 이동·문장 재작성 | available normalized fields 같으면 repeat; semantic synonym 추측0 |
| official key의 다른 tuples·actual values 충돌 | explicit conflict; 임의 winner0 |
| dirty local ledger, remote malformed, 1MiB+1, record5001 | local ignored; unavailable/명시 budget failure |
| removed event·push unknown·CAS competing story/cursor | 신규 history advance0; overwrite0 |
| v2 replay hashes만 제공 | typed replay inspection; invented canonical fact0 |

미래 실행 명령(이 docs-only 작업에서는 실행하지 않음):

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/unit/models/test_event_identity.py tests/unit/models/test_event_story_contract.py tests/unit/briefing/test_event_identity.py tests/unit/briefing/test_event_fact_delta.py tests/unit/orchestrator/test_event_identity_ledger_v3.py tests/integration/test_event_identity_v3_boundary.py tests/unit/orchestrator/test_event_receipts.py tests/unit/orchestrator/test_event_publication.py tests/integration/test_event_publication_boundary.py tests/unit/_internal/test_module_boundary.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run python scripts/check_no_paid_apis.py
uv run python -m pytest -q
git diff --check
```

u169 완성 후 actual finalizer 통합 fixture를 위 `test_event_identity_v3_boundary.py`에 연결한다. u168 독립 완료와 cross-unit integration 완료를 분리하며 missing downstream code를 fake sealed object로 통과시키지 않는다. 검증 결과는 `aidlc-docs/construction/u168-canonical-event-identity-and-fact-delta/code/validation.json`에 실제 명령/exit/AC/fixture hash/측정으로 기록한다. live scheduled receipt/semantic/source qualification/Pages acceptance를 offline test로 주장하지 않는다.

## Non-Goals

### Migration / Removals

schema3는 v2의 exact source-span tuple key, raw wording novelty,7일 ledger를 사용하지 않는다. legacy 함수와 imports는 schema2 replay/rollback에 한정해 유지한다. 기존 archive나 shared ledger를 고치지 않고 신규 v3 per-segment 파일을 bootstrap한다. 설계의 대담한 변경은 identity 경계의 교체이며 production data 손상이나 gate 삭제를 뜻하지 않는다.

공통 policy/evidence/quality/render/surface/semantic gate와 source registry는 소유자가 유지한다. alias 등록·source qualification의 근거 없이 구현자가 새로운 provider/registry entry를 만들지 않는다. 이 문서 작성의 완료와 실제 코드 완료·commit/push·배포/activation은 분리한다.

## Foundation checkpoint — 2026-10-10

Entity/fact/occurrence/delta 및 전체 story frozen DTO를 구현하고 원격 고정 SHA reader와 30일/5000records/1MiB stable serializer를 추가했다. 사실의 비교 slot/value 연결은 hash-only FactSlotReceipt로 보존한다. source-owned reporting period가 occurrence를 고정하며 새로운 fact 부분집합은 ID를 바꾸지 않는다. 현재 fixture matrix는 별도 JSON 복제 대신 고정 unit-test 입력으로 유지한다. source/private text는 ledger에 넣지 않는다.

Step6–8과 AC-168.7의 native E5 survivor/combined CAS 연결은 u169 이후 미완료다. replay-only v2 inspection adapter는 hash-only inspection으로 검증했다. registry 주체의 explicit correction integration은 source binding을 제공할 수 없는 경우 conservative rejection으로 남는다. v3 ledger production caller/write/activation은 없다. foundation 검증을 전체 unit 완료로 표시하지 않는다.
