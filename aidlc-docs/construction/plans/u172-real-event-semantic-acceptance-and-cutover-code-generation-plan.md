# Code Generation Plan: u172 real-event-semantic-acceptance-and-cutover

**Date**: 2026-10-10 KST. **Unit**: u172. **Stage**: Functional Design / NFR Requirements 초안; Code Generation 미착수. **Status**: Planned — 0/9. **Priority**: P0. **Estimated Effort**: 20–32h + 실제 사례/사람 검수/예약 관찰/최종 제거.

**Source**: 2026-10-10 사건·뉴스 중심 이상향 분석과 전체 구조 변경 지시, u159 평가/10월 9일 운영 수용 기록. **Dependencies**: u169 전체 문서, u170 story, u171 소비자 전환. Corpus 준비는 독립 착수 가능. [설계 및 AC](../u172-real-event-semantic-acceptance-and-cutover/design-brief.md), [공통 계약](../event-news-v3/contracts.md).

## Problem Statement

합성 구조 PASS와 실제 의미 수용이 분리되어 있고, 기존 golden 정상 사건은 미국에 집중되어 있다. v3의 전체 문서와 소비자 전환이 실제 세 시장의 중요한 사건 설명으로 이어지는지, 별도 사람 기준선과 sealed output으로 검증한다. 자동 fact 100% / unsupported 사건·인과 0과 사람5/5는 유지하며, 실제 release 지시는 점수와 구분한다.

## Goal

실제 세 시장의 중요 사건을 균형 있게 검수하고 코드·사람·운영 수용을 분리한다. 시장별 전환과 관찰 후 구형 생성 제거까지 증명한다.

## Existing Coverage / Deduplication

u159의 `models/event_quality.py`, `publisher/event_quality.py`, 기존 replay와 품질 history를 확장한다. u65 replay, u144 finalizer, u155 private runtime/auth/암호화 preview와 publication transaction을 재사용한다. 새 evaluator 서비스, 제3 LLM, generic quality dashboard, 별도 finalizer는 만들지 않는다. u160/u161 source/cursor 활성화, u163–u166 데이터/운영 복구는 해당 owner에 남긴다.

## Scope Boundary

In scope: `src/investo/models/event_quality.py`, `publisher/event_quality.py`, `publisher/quality_consistency.py`, `briefing/quality_history.py`, `models/quality_history.py`, `scripts/_event_coverage_replay.py`, `scripts/check_event_coverage.py`, 기존 preview/seal script와 workflow templates, v3 synthetic fixture, private corpus 절차와 cutover runbook. 수용 이후의 legacy generation/빈 bridge/활성 rewrite 제거와 default schema 3 정착도 Step 9 범위다. `ops/private-runtime/production-briefing.yml`의 policy/capability 연결은 승인된 최종 reviewed code에 한해 구현한다.

Out of scope: 실제 신규 source/body 도입, 지표 gate 완화, 과거 archive 수정, auth 설정/비용 변경, 현재 운영 pin 변경. 실제 cutover는 코드 완료 후의 별도 운영 실행이다.

## Stage Decision

Functional Design / NFR Requirements는 **REQUIRED**이며 design-brief의 고정 모델·분모·corpus·NF-172.1–4를 검토/승인한 뒤 구현한다. NFR/Infrastructure Design은 기존 runtime/암호화/transaction을 재사용한다. 현재 계획 작성으로 구현 승인이나 release를 완료 표시하지 않는다.

## Fixed Contracts / Migration

설계의 `EventSemanticAnnotation`, `EventSemanticReview`, `EventQualityV3Measurement`, `EventCutoverAcceptance`를 models 경계에서 소유한다. shared defaults는 [공통 계약](../event-news-v3/contracts.md)을 따른다. schema 2 manifest의 `human_review=pending`과 과거 필드 null을 유지하며 별도 `tests/fixtures/event_briefing_v3/` 및 private 실제 corpus를 추가한다. 전환 중 하나의 기존 runner가 manifest schema로 분기한다. 인간 score, 자동 outcome, 실제 release/remote receipt는 독립 기록이며 operator exception으로 score를 바꾸지 않는다. 최종 cleanup 전에 합성 `terminal_snapshots.json`과 reviewed SHA/hash를 고정하고 이후 v2 검사는 historical parser/output 회귀로 제한한다. production legacy generator는 제거하며 과거 generation 전체 재생/rollback은 이전 reviewed commit/policy 전체에서 수행한다.

## Implementation Steps

- [ ] **Step 1 — Characterization과 oracle**: 기존 12/25 replay, market별 양성 공백, 내부/외부 denominator, preview write 경계를 고정한다. 실제 12개/시장별 4개 corpus의 수집 가능성과 R10/private 권리를 기록하고 사람이 기대 목록을 먼저 작성한다. 준비 부족은 pending이다.
- [ ] **Step 2 — Typed 평가 모델**: `models/event_quality.py`에 설계의 frozen DTO, closed outcome, nullable count/ratio, hash/SHA/market identity 검증을 추가한다. v2 공용 필드를 바꾸지 않는다.
- [ ] **Step 3 — Schema별 replay 확장**: 기존 `_event_coverage_replay.py`와 `check_event_coverage.py`가 v2와 v3 oracle/recording을 구별해 실제 generation→u144 finalizer→HTML/DTO/story를 대조하게 한다. 새로운 evaluator나 평가 전용 renderer를 만들지 않는다.
- [ ] **Step 4 — Matrix와 사람 수용**: 최소 36개 market/scenario 사례와 세 시장 정상 양성, 12개 scenario groups, source 실패/주말 재생, 독립 context chunks, 4 document/8 fact, 길이·문장 완결성만 무효인 digest의 국소 제외, fact delta/story 및 trusted fact negative를 고정한다. 실제 12개/시장별 4개/서로 다른 발행 날짜 2개 이상 corpus의 사람 5/5와 자동 fact 100%/unsupported 0을 각각 기록한다.
- [ ] **Step 5 — 품질 projection과 preview**: terminal/remote-confirmed 집계와 사람 reference, support vector, 외부 baseline을 구분한다. 기존 private preview/seal 도구에 C1 schema 3 policy와 SHA/hash manifest를 연결하고 write 0/추가 LLM stage 0을 증명한다.
- [ ] **Step 6 — Cutover/rollback 계약**: ready market allowlist와 capability 기본 false, 현재 owner/pin/policy readback, release instruction reference, 전체 schema 2 rollback 및 archive 불변을 runbook과 offline workflow/consumer fixtures에 고정한다. 코인은 자체 수용과 release가 필요하다. source/cursor gate는 그대로 유지한다.
- [ ] **Step 7 — 코드 수용**: 집중/full/static/policy/docs 검증, 실제 16KiB/budget/performance 측정, 독립 review와 AC 대조를 완료한다. code-ready/human-ready/release-ready를 따로 보고하고 부족 항목은 pending으로 남긴다.
- [ ] **Step 8 — 승인된 운영 수용**: 실제 release 지시 후 exact reviewed code/policy를 연결하고 시장별 최초 3회 실제 예약 발행의 게시·Telegram·해당 SHA Pages·ledger/cursor를 관찰한다. 실패 시 reviewed schema 2 전체로 rollback하고 결과를 별도 기록한다. 수동 실행으로 횟수를 채우지 않는다. 정상 sibling은 다른 시장의 수용을 기다리지 않고 유지하며 전체 v3 수용은 세 시장 모두 accepted를 요구한다.
- [ ] **Step 9 — 최종 제거와 정착**: 세 시장 accepted와 최소 10회의 실제 v3 예약 발행, 부분 실패의 정확한 집계를 확보한다. 별도 reviewed cleanup으로 `briefing/pipeline.py`, `prompts.py`, `event_narrative.py`, `models/briefing.py`, `models/event_narratives.py`, `publisher/segment_reader_format.py`, `publisher/reader_format/` 및 호출부의 legacy generation/자유 section strings/빈 bridge/활성 rewrite를 제거한다. 정상 default schema를 3으로 정착시키고 retired policy 명시적 거부, read-only historical parser, prior reviewed commit/policy rollback을 검증한다. cleanup 코드의 full/static/policy/docs 및 독립 리뷰를 다시 통과한 후 실제 reviewed pin/policy readback과 기존 auth/게시 연결을 확인한다.

## Acceptance Criteria

AC-172.1–9는 [설계의 번호별 수용 기준](../u172-real-event-semantic-acceptance-and-cutover/design-brief.md#수용-기준)을 그대로 따른다. 첫 Code Generation 수용은 Step 1–7, 시장별 운영 accepted는 Step 8, 전체 cleanup_complete는 Step 9다. 합성 PASS/배포 지시/부분 sibling 성공을 사람 5/5 또는 전체 운영 성공으로 치환하지 않는다. 문서/score가 자동으로 Step 8/9의 외부 상태를 변경하지 않는다.

## Tests / Validation

기존 verified target: `tests/integration/test_event_coverage_replay.py`, `tests/unit/models/test_event_quality.py`, `tests/unit/publisher/test_event_quality.py`, `test_event_quality_history.py`, `tests/unit/orchestrator/test_event_preview_script.py`, `test_event_preview_codex.py`, `test_event_preview_boundary.py`, `test_event_preview_encryption.py`, `test_private_publication_u155.py`.

Step 2–6에서 신규 `tests/unit/models/test_event_semantic_acceptance_u172.py`, `tests/integration/test_event_document_v3_replay_u172.py`, `tests/unit/orchestrator/test_event_v3_cutover_u172.py`를 만든다. Step 9는 `tests/integration/test_event_v3_legacy_retirement_u172.py`로 정상 v3 생성/retired policy/과거 parser/legacy 호출 금지를 검증한다. u169/u170/u171의 실제 생성·finalizer·story·consumer 테스트 경로는 통합된 파일을 `rg --files tests`로 확인해 포함한다. 신규 경로가 생성되기 전 테스트 실행을 주장하지 않는다.

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/integration/test_event_coverage_replay.py tests/unit/models/test_event_quality.py tests/unit/publisher/test_event_quality.py tests/unit/publisher/test_event_quality_history.py tests/unit/orchestrator/test_event_preview_boundary.py tests/unit/orchestrator/test_event_preview_encryption.py tests/unit/orchestrator/test_private_publication_u155.py tests/unit/models/test_event_semantic_acceptance_u172.py tests/integration/test_event_document_v3_replay_u172.py tests/unit/orchestrator/test_event_v3_cutover_u172.py
uv run python scripts/check_event_coverage.py
uv run python scripts/check_event_coverage.py --manifest tests/fixtures/event_briefing_v3/manifest.json
uv run python -m pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run python scripts/check_no_paid_apis.py
uv run python scripts/check_no_anthropic_sdk.py
uv run python scripts/check_curated_assets.py
uv run python scripts/check_image_store.py
uv run mkdocs build --strict
uv run python scripts/check_material_theme_contract.py
git diff --check
```

Step 9의 신규 retirement 테스트를 만든 후에는 다음 집중 검증과 위 full/static/policy/docs gate를 다시 수행한다. 기존 v2 integration 테스트도 historical output 기준으로 이행해야 하며 generator를 보존해 옛 기대값을 만족시키지 않는다.

```sh
uv run python -m pytest -q tests/integration/test_event_v3_legacy_retirement_u172.py tests/unit/orchestrator/test_event_v3_cutover_u172.py tests/integration/test_event_document_v3_replay_u172.py tests/integration/test_event_coverage_replay.py
uv run python scripts/check_event_coverage.py --manifest tests/fixtures/event_briefing_v3/manifest.json
```

실제 사람 검수, source recording, private workflow dispatch, cutover와 예약 관찰은 위 offline 명령으로 통과했다고 기록하지 않는다. 실제 승인 시 기존 preview workflow의 target/segment/recipient public key와 reviewed SHA를 사용하며 private key/raw output은 git에 넣지 않는다.

## Non-Goals / Handoff

세계 모든 뉴스의 완전 포착 보장, 점수 기준 완화, 새로운 유료 소스/평가 LLM, 기사 원문 공개, historical archive rewrite는 범위 밖이다. Handoff는 per-AC 증거, automated와human 결과, corpus/record hash, exact reviewed SHA, 미완료 source/cursor/performance 항목, rollback snapshot과 실제 예약 receipt다. 현재 문서는 설계 초안이며 runtime/test 실행 증거가 아니다.
