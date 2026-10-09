# Code Generation Plan: u173 official-event-source-slot-qualification

**Date**: 2026-10-10 KST. **Unit**: u173. **Stage**: Functional Design / NFR Requirements 초안; Code Generation 미착수. **Status**: Planned — 0/7; qualification 결과에 따라 source 확보는 blocked일 수 있음. **Priority**: P1. **Estimated Effort**: 8–16h + 접근/권리/현재 schema 확인.

**Source**: 2026-10-10 사건 중심 이상향 분석, u161 official evidence와 source reliability 검토. **Dependencies**: u167 typed chunk 출력. 공식 증거 탐색/기존 파서 진단은 독립 가능. [설계 및 AC](../u173-official-event-source-slot-qualification/design-brief.md), [공통 계약 C2/C7](../event-news-v3/contracts.md).

## Problem Statement

정책 결정, 실적 actual/guidance, 국내 공시의 구체적인 변화가 기존 입력의 어느 slot에서 확보되는지 검증한다. 소스가 공식이거나 200을 반환한다는 사실과 공개 사용 권리·핵심 내용·실제 사건 시각·운영 접근을 구분한다. 결과는 exact verified/blocked qualification이며 신규 adapter, 권리 또는 production recovery를 발명하지 않는다.

## Goal

8개 정보 슬롯을 현재 근거로 verified/blocked 판정하고 typed chunk 매핑과 후속 owner를 제공한다. qualification 완료와 source 확보·운영 활성화를 구별한다.

## Existing Coverage / Deduplication

u161 `models/enrichment.py`, `sources/event_evidence.py`, `ops/event_source_qualification.json`과 현재 adapter/private fixture 절차를 확장한다. source 등록/tier/routing은 `_internal/source_specs.py`의 단일 출처를 유지한다. u165 failed/zero/skipped와 feed lifecycle, u166 가격 source, u172 사람 점수/운영 cutover는 각 owner에 남긴다. qualification-only matrix는 두 번째 adapter registry나 body HTTP 허용목록이 아니다.

## Scope Boundary

In scope: 기존 8개 named slot 조사, 현재 공식 access/rights/schema 증거, `src/investo/models/enrichment.py`의 frozen `SourceSlotQualification/SourceSlotQualificationSet/EndpointScope`, `sources/event_evidence.py`의 bounded loader/기존 파서 기반 u167 chunk 매핑, planned `ops/event_source_slot_qualification.json`, `scripts/check_event_source_slots.py`, synthetic fixture와 private evidence handoff.

Out of scope: 신규 source module 등록, provider 대체, body endpoint 자동 확대, commercial scraping, credential 도입/값 저장, production pin/HTTP/cursor 활성화, source 장애 복구 완료 선언. 기존 adapter defect가 드러나면 이 unit에서 임의 확장하지 않고 u165/u161 또는 별도 reviewed source plan에 handoff한다.

## Stage Decision

Functional Design / NFR Requirements는 **REQUIRED**다. design-brief의 schema, 8개 slot, verified/blocked, 권리/시간/ref 조건과 NF-173.1–4를 승인한 뒤 구현한다. 별도 infrastructure는 도입하지 않는다. 새 adapter/infrastructure 필요성은 qualification의 결론이지 이 계획의 구현 허가가 아니다.

## Fixed Contracts / Migration

설계의 source-slot JSON schema 1, 최대 64row/64KiB, immutable outcome, closed reason codes와 v3 chunk budgets를 그대로 따른다. `ops/event_source_qualification.json` / `SourceQualification(status=qualified|blocked|rejected)`는 기존 body runtime owner로 유지한다. 새 `status=verified|blocked`를 해당 타입으로 coercion하지 않으며, existing manifest를 migration하거나 enrichment capability를 올리지 않는다. u167이 전달한 typed chunks만 소비하고 C2 time/support semantics를 source별로 재정의하지 않는다.

## Implementation Steps

- [ ] **Step 1 — Current evidence와 matrix**: 8개 named slot의 source/path/actual data/rights/precision을 조사한다. Fed/CFTC의 과거 scoped qualification, SEC body 403/commercial blocked, FSC 수리와 upstream 503, API/feed와 새 body를 분리한다. 현재 조회가 없으면 blocked/access.not_verified다.
- [ ] **Step 2 — Qualification DTO**: `models/enrichment.py`에 `SourceSlotQualification/SourceSlotQualificationSet`과 evidence/slot/source/path/hash/precision validation을 추가한다. runtime/GHA probe와 activation readiness를 별도 필드로 둔다. 기존 EnrichmentPolicy와 SourceQualification bytes/제한은 유지한다.
- [ ] **Step 3 — 독립 offline checker**: `scripts/check_event_source_slots.py --manifest ops/event_source_slot_qualification.json`을 만들고 bounded loader, duplicate, forged verified, verified의 missing rights, unknown slot, path mismatch를 검사한다. 미확인 정보를 정확하게 나타낸 정상 blocked row는 허용한다. script는 network/LLM/archive/notify/ledger/cursor I/O를 하지 않는다. 출력은 source/slot/status/closed code/count뿐이다.
- [ ] **Step 4 — u167 mapping과 fixture**: 실제로 존재하는 parser output을 C2 typedchunk로 매핑한다. facts/comparison/time과meaning/reaction/follow-up을 독립 검증하고 없는 내용을 만들지 않는다. 합성 양성/음성과 허용된 private capture 재생을 분리한다.
- [ ] **Step 5 — Qualification conclusions**: 정책/실적/국내 공시별 verified/blocked, useful slot, unsupported slot, 현재 접근/권리/schema와 runtime probe 상태를 공개 요약한다. 신규 source/path/provider가 필요한 경우 별도 등록/인증/비용/권리/window/consumer 설계를 handoff한다. 전부 blocked도 유효한 판정이며 운영 복구는 별도다.
- [ ] **Step 6 — 코드/문서 검증**: focused/full/static/policy/docs와 44개 source parity, v2 compatibility, private fixture, budget negative를 통과한다. independent review와 AC-173.1–8을 대조한다. source 준비와 qualification tooling 완료를 별도 상태로 기록한다.
- [ ] **Step 7 — 후속 운영 handoff**: 현재 reviewed runtime에서 GHA access/parser/useful rows/권리를 확인해야 하는 목록, u161 body capability와 u160 cursor의 별도 승인, u172가 소비할 source 상태를 인계한다. 실제 adapter/activation/예약 회복을 이 계획의 자동 완료로 만들지 않는다.

## Acceptance Criteria

AC-173.1–8은 [설계의 번호별 수용 기준](../u173-official-event-source-slot-qualification/design-brief.md#수용-기준)을 그대로 따른다. 단위 완료는 근거 있는 verified/blocked qualification과 reusable model/tool/fixture handoff다. 필요한 slot이 blocked이면 v3의 해당 source 준비는 미완료로 남긴다.

## Tests / Validation

기존 verified target: `tests/unit/sources/test_event_evidence.py`, `test_feed_event_evidence.py`, `test_source_specs.py`, `test_plugin_contract.py`, `test_sec_company_facts.py`, `test_sec_edgar_8k.py`, `test_dart_disclosure.py`, `test_nasdaq_earnings_calendar.py`, `tests/integration/test_event_enrichment.py`. u161 body tests는 기존 loader/bounds/activation 불변을 확인하며 각 슬롯의 현재 live access를 대신하지 않는다.

Step 2–4에서 신규 `tests/unit/models/test_source_slot_qualification_u173.py`, `tests/unit/sources/test_event_source_slot_mapping_u173.py`, `tests/integration/test_event_source_slot_checker_u173.py`와 `tests/fixtures/event_source_slots/`를 만든다. source checks는 사람 semantic corpus와 독립 실행되어야 한다. missing required slot/rights unknown은 판정 row를 blocked로 만들고, 정상 blocked row 자체는 checker error나 qualified count가 아니다.

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/unit/sources/test_event_evidence.py tests/unit/sources/test_feed_event_evidence.py tests/unit/sources/test_source_specs.py tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_sec_company_facts.py tests/unit/sources/test_sec_edgar_8k.py tests/unit/sources/test_dart_disclosure.py tests/unit/sources/test_nasdaq_earnings_calendar.py tests/integration/test_event_enrichment.py tests/unit/models/test_source_slot_qualification_u173.py tests/unit/sources/test_event_source_slot_mapping_u173.py tests/integration/test_event_source_slot_checker_u173.py
uv run python scripts/check_event_source_slots.py --manifest ops/event_source_slot_qualification.json
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

공식 source probe는 현재 공식 discovery와 approved source/path에서 bounded read로 별도 기록한다. public rights/raw private fixture/runtime credential/GHA를 offline PASS로 대체하지 않는다. 위 신규 target/tool/manifest는 Step 2–4에서 만들기 전까지 계획 경로이며 현재 실행 증거가 아니다.

## Non-Goals / Handoff

세계 뉴스 포착률 보장, source 수 늘리기, blocked 접근 우회, 타 언론 대체, 사람 점수 발급, 공개 기사 원문 저장과 현재 운영 변경은 범위 밖이다. Handoff는 8개 slot 판정 matrix, evidence hash/official rights/path, parser/typed chunk mapping, blocked exact reason, verified scope와 미완료 runtime/adapter owner다. 현재 문서는 설계 초안이며 새로운 source qualification이나 실제 복구를 선언하지 않는다.
