# Code Generation Plan: u180-public-insights-snapshot-and-publication

작성일: 2026-10-12 · u180 · 상태: 사용자 진행 지시로 설계 채택, 로컬 구현·검증 7/8 완료. 운영 활성화는 별도 pending.

## 문제와 목표

현재 수집 결과의 숫자·일정을 독립 typed snapshot 으로 검증하고 제한된 이력과 화면 파일을 원격에 일관되게 게시한다. 시황 LLM 실패와 데이터 dashboard 결과를 구별한다.

## Existing coverage / Deduplication

기존 u102 source registry, u113 scoped publish, u144 sealed/public boundary, u155 private runtime, u164 temporal truth, u165 source lifecycle. 새 화면 및 event/news v3 미완료를 prerequisite 로 추가하지 않는다.

[Program 중복 대조](../public-insights-20261012/README.md)와 [source 판정](../public-insights-20261012/source-assessment.md)을 따른다. source 별 defaults/tier/window/segment/registry 는 유지하며 raw numeric/event envelope 만 opt-in 추가한다.

## Scope boundary

models/insights.py, models/insights_calendar.py, models/items.py 의 선택 envelope 와 serializer, models/results.py 의 optional insights 결과; sources/_window.py 및 aggregator.py 의 default-false opt-in; orchestrator/insights.py/insights_projection.py/insights_publication.py 와 CollectStage handoff; publisher/insights/__init__.py/store.py; ops/insights_source_qualification.json 의 검증 타입·loader; __main__.py 의 optional GHA output 및 ops/private-runtime/production-briefing.yml Pages 신호 연계; 신규 공통 tests.

제외: 원천별 metric parser, 신규 source/secret/HTTP/scheduler, standalone 모듈 UI, event/news ledger/cursor, u145 store, 기존 archive/LLM finalizer, Telegram 추가 발송, production activation.

## Stage decision

- Functional Design: REQUIRED / ADOPTED. 새 public 데이터 의미·시간·상태·독자 workflow 와 cross-module contract 가 있다. [FD](../u180-public-insights-snapshot-and-publication/functional-design/business-logic-model.md).
- NFR Requirements: REQUIRED / ADOPTED. source rights/private 경계·신뢰·자원·retention/새화면·runtime 를 구체화한다. [NFR](../u180-public-insights-snapshot-and-publication/nfr-requirements/nfr-requirements.md).
- NFR Design: focused design in [shared contracts](../public-insights-20261012/contracts.md), C3–C7의 경계·cap·recovery를 채택하고 실제 fixture/resource 검증을 기록한다.
- Infrastructure Design: REQUIRED focused design adopted; u180 infrastructure-design/infrastructure-design.md 에 기존 privatejob/Pages output 결속과 mode/pin 경계를 기록한다.
- Code Generation: 사용자 후속 진행 지시로 로컬 구현·검증. 8개 단계 중 운영 Step 8은 모듈 구현 이후 별도 수용으로 남긴다. commit/push/배포는 수행하지 않았다.
- Source requirements: 사용자 2026-10-12 지시, US-011/012/013; FR-026; 기존 FR-001/003/005/006/010/011/017/021; NFR-001~008/R10/R13. 신규공식 source 자격검증이있으면 별도 bounded source plan 에 handoff 한다.

## Fixed contracts

[C1–C7](../public-insights-20261012/contracts.md), [unit rules](../u180-public-insights-snapshot-and-publication/functional-design/business-rules.md), [entities](../u180-public-insights-snapshot-and-publication/functional-design/domain-entities.md)가 u180 구현의 normative 계약이다. 입력/시간/identity/owner/permission/부분상태/파일원격확정순서를구현중임의로바꾸지않는다. DTO/private envelope 와 HTML·JSON·이력·receipt 의 role 을구별한다.

## Implementation steps

- [x] **Step 1** — 기준 remote/current owner 와 C1–C7 을 고정한다. 기존 receipt 가 manifest-only metadata CAS 와 disjoint event/news 병행을 지원하는지 기존 tests 로 확인하고 public permission matrix 는 미확인=false 로 시작한다.
- [x] **Step 2** — models/insights.py 의 immutable source/public/result 타입 및 numeric/time/reason/qualification validation, 선택 item field 의 omit serializer 와 PipelineResult backward compatibility 를 구현한다.
- [x] **Step 3** — FetchWindow/collect_sources 의 default-false opt-in, 두 collection 경로의 capture/strip/report_sink 를 구현한다. empty·injected item-only·news-active·shadow/off payload parity 를 검증한다.
- [x] **Step 4** — source-neutral projection gate 와 C4 freshness/비교·C5 history/retention 을 구현한다. confirmed baseline·provider change·rights withdrawal·max data negative 를 검증한다.
- [x] **Step 5** — publisher/insights/store.py 의 staged multi-file prepare/recovery/rollback, canonical hash 와 manifest cross-validation 을 구현한다. 현재 u145 transaction 을 수정하지 않는다.
- [x] **Step 6** — orchestrator/insights_publication.py 가 기존 receipt/CAS 를 소비하고 collect 후·LLM 전 phase 를 연결한다. __main__.py optional insights_publication_committed 와 confirmed local_sha 출력, production-briefing.yml 의 Pages OR 신호를 연결한다. LLM 실패·dashboard 실패·pushunknown·cancellation·dry-run/replay·unrelatedwriter 를 검증한다.
- [x] **Step 7** — focused/full pytest, changed static checks, 정책 guards, strict MkDocs/Material, 최대-size resource/cancellation 를 확인하고 설계/코드 review 와 AC 대조를 기록한다.
- [ ] **Step 8** — 모듈 구현 이후 별도 운영 instruction 범위에서 reviewed private pin/mode 와 exact-SHA5 회 observations, Pages/live identity 를 확인한다. 이 단계는 code 완료와 구별해 pending 으로 남긴다.

## Acceptance criteria

- AC-180.1: off 에서 기본 collection/prompt/public/result bytes·source44 parity·기존 stage status 유지, active/shadow 에서는 source envelope 가 기존 consumers 에 0.
- AC-180.2: source ownership·finite Decimal·unit/time/definition·rights 를 통과한 값만 public DTO 에 포함. missing/NaN/bool/raw/title recovery0.
- AC-180.3: collection1 회·추가 source request/LLM/notify0; raw/뉴스 active·empty/report sink/input-only·shadow 경로의 outcome truth 보존.
- AC-180.4: current/index/history/manifest identity 와 public state 가 일치, cap 초과·revoked·incompatible history 는 fail-closed 이며 관계없는 files/state 보존.
- AC-180.5: exact remote receipt 이전 성공/이력 advance0; metadata conflict/push unknown/cancel 에 baseline 보호. event/news/sector concurrent fixture 통과.
- AC-180.6: 이후 LLM failure 에서도 dashboard confirmed 결과와 Pages 필요신호를 보존하고 기존 시황 failure/publication_committed/exitcode 의미 유지. 예상 module 오류는 정상 sibling 을 막지 않는다.
- AC-180.7: 최대 input 자원 상한·secret hygiene·source calendar unsupported-year/freshness 와 required guards 에 대한 실제 시험 증거.
- AC-180.8: 구현 수용과 public/private runtime·Pages·5 회 예약 운영 수용을 구별하여 state 기록. 설계 지시만으로 activation0.

## Tests / Validation

신규 contract/capture/projection/resource/store/integration tests와 재현 가능한 합성 benchmark를 추가했다.

- `tests/unit/models/test_insights_contracts_u180.py`
- `tests/unit/orchestrator/test_insights_capture_u180.py`
- `tests/unit/orchestrator/test_insights_projection_u180.py`
- `tests/unit/publisher/test_insights_store_u180.py`
- `tests/integration/test_insights_publication_u180.py`
- `tests/unit/orchestrator/test_insights_resources_u180.py`
- `scripts/benchmark_insights_resource.py`

LLM 실패 독립성은 `test_insights_capture_u180.py::test_confirmed_insights_survives_later_generation_failure`에서 검증한다.

기존 owner 회귀: tests/unit/sources/test_aggregator.py; tests/unit/publisher/test_publication_receipts.py; tests/unit/orchestrator/test_run_pipeline.py; tests/integration/test_event_publication_boundary.py; tests/unit/models 및 source plugin 계약.

필수 공통 명령은 `uv sync --extra dev --extra docs --extra sector`, scoped+full `uv run python -m pytest`, changed Ruff/format·source mypy, `python scripts/check_no_paid_apis.py`, `python scripts/check_no_anthropic_sdk.py`, 기존 curated/image guards, `uv run mkdocs build --strict`, `python scripts/check_material_theme_contract.py`, `git diff --check`다. workflow 변경이 있는 u180 은 actionlint 와 private runtime template/output negative 검증을 포함한다.

각 source recording/문서조건·합성 domain case·실제 viewport·remote/livePages·5 회 scheduled 를서로구별해기록한다.  설계 작성 당시의 문서 검증과 구현 이후의 실제 test/resource 검증을 구별한다. [시나리오](../public-insights-20261012/acceptance-scenarios.md)를 AC 에연결한다.

## Implementation evidence (2026-10-12)

최종 scoped suite **173 passed / 42.52s**: 신규 contracts/capture/projection/resources/store/local-Git integration, 기존 private publication와 aggregator. 초기 전체 suite checkpoint **6,987 passed / 1 known skipped**, 이후 관련 회귀 **704 passed**. 최종 source static: Ruff/format 755 files 및 mypy 319 files PASS. 정책 guards, strict MkDocs/Material/Calendar, actionlint PASS. registry 실제 44개 확인.

독립 초기 리뷰에서 crash-after-add 복구 High 1건을 실행 재현했고, durable initial HEAD와 owned index identity/scoped reset을 추가한 뒤 reviewer가 29 tests를 직접 실행해 통과했다. 최종 재검토 미해결 Critical/High/Medium 0. 전체 검토와 좁은 수정 재검토의 범위를 구별한다.

64 지표·128 일정·약 8MiB 이력을 다루는 실제 `_phase`의 새 커밋/로컬 bare Git push·remote confirmation 합성 benchmark가 RSS 96MiB / CPU 5s / phase 60s 기준을 통과했다. [검증 기록](../u180-public-insights-snapshot-and-publication/code/validation.json), [resource evidence](../u180-public-insights-snapshot-and-publication/code/resource-evidence.json), [독립 review](../u180-public-insights-snapshot-and-publication/code/review-final.md), [AC 대조](../../../docs/cross-checks/2026-10-12-u180-public-insights-foundation.md).

Step 8은 모듈 구현 이후 운영 수용이다. source permission·실서비스 Pages·private pin/mode·5회 scheduled는 pending이며 7/8 코드 수용을 운영 완료로 확대하지 않는다. 다음 코드 구현은 u181이다.


## 2026-10-25 운영 연결 진행

후속 사용자 지시에 따라 최신main 통합·commit/push·공개 조건별 순차 초기 게시와 기존 private 예약 갱신 연결을 수행했다. 실행pin0025497d/quality40182882842, 최종current게시1f6b37c6/quality40184291647/Pages40184291651 모두 확인했다. 실제HTTPS snapshot/hash·운영Chromium12조건과 기존코드7344pass/1knownskip. [운영 증거](../public-insights-20261012/operations-evidence-20261025.json). 모듈별 genuine scheduled0/5이므로 Step8 체크는 미완료로 유지한다. 로컬probe·수동초기게시를 예약관찰로 세지 않는다.

## 2026-10-25 Step8 관찰 증거 보강

후속 “진행시켜” 지시로 [bounded capture 계획](../public-insights-20261012/observation-capture-plan.md)을 실행한다.
기존 u155의 private status/timing receipt와7일보존을 재사용하며, 공개 current 값·원문·auth·모델 출력은 artifact에 담지 않는다.
기존 applicationpin0025497d와 cron/인증/queue/예산/최종exit를 보존한다.
[검증](../public-insights-20261012/observation-capture-validation.json),
[독립리뷰](../public-insights-20261012/observation-capture-review.md).
설정·합성검증은 관찰횟수가 아니며 Step8은0/5로 미완료다.
