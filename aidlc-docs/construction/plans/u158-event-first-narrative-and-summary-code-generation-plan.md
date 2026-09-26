# Code Generation Plan: `u158 event-first-narrative-and-summary`

**Date**: 2026-09-26
**Unit**: u158 event-first-narrative-and-summary
**Stage**: Code Generation (planned)
**Status**: Code complete — 7/7 steps, full regression 5521 passed (402.28s); independent review and cross-check PASS. Preview ready; active remains off.
**Source**: `../news-event-briefing/evidence/review-20260922.md`; user planning request 2026-09-26.
**Estimated Effort**: ~18–26 h
**Dependencies**: u157 모델/plan 구현. u154 배치 및 u156 Telegram 구성은 hard dependency가 아니다.

## Problem Statement
9/16 미국 문서는 FOMC 성명서 공개만 설명하고 결정 메시지는 빈약했다.13/18 상단 결론은 fallback이어서 본문 사건을 전달하지 못했다.

## Goal
사건 중심 본문과 상단 요약을 통해 전일 중요한 사건을 독자가 이해하고 신뢰 수준을 구분하게 한다. 자세한 동작은 [설계](../u158-event-first-narrative-and-summary/design-brief.md)의 Fixed contracts로 고정한다.

## Existing Coverage / Deduplication
Extend u2/u83 synthesis, u51/u61/u71 summary, u153 sentence bound, u144 finalizer, u154 layout, reserved u156 notifier. Add only the named event/window extension; no replacement pipeline/finalizer, generic new quality dashboard, generic numeric engine, or parallel source registry.

## Scope Boundary
In scope: `briefing/_core/orchestration.py, briefing/prompts.py, briefing/generation_contract.py, models/public_notification.py, publisher/public_document.py, publisher/reader_format/tldr.py, orchestrator/pipeline.py, briefing/_assembly/markdown_render.py (_stage2_retry_feedback)`; new files `briefing/event_narrative.py; publisher/event_blocks.py`.
No production activation, historical archive rewrite, paid API, independent LLM evaluation stage, credentials change, or unrelated unit completion.

## Stage Decision
Functional Design: REQUIRED; design draft and common event contracts are written, approved 2026-09-27.
NFR Requirements: REQUIRED — Stage2 schema와 public/notification projection 및 실패 처리 변경. NF1/2/3/7/9/10 적용.
Use the shared NFR/validation document; no boilerplate infrastructure stage. This code plan does not bypass design/source/operational gates.

## Fixed Implementation Contracts
Normative: [design-brief](../u158-event-first-narrative-and-summary/design-brief.md), [event-contract](../news-event-briefing/event-contract.md), [business-rules](../news-event-briefing/business-rules.md), [NFR](../news-event-briefing/nfr-and-validation.md). The numbered rules and exact defaults there are part of this plan. Changes require synchronized design/AC updates.

## Implementation Steps
- [x] Step 1: E6 parser와 system/user/retry의 schema version을 일치시킨다. _stage2_retry_feedback의 v1 bytes를 유지하고 v2는 JSON 객체를 재요청한다. 두 provider에서 invalid v2 → valid v2 replay를 검증한다.
- [x] Step 2: 사건 renderer와 event validator를 구현한다. 필수 fact, 허용 entity, 필드별 EvidenceRef, actual/forecast/period를 검증하며 event.fact_unsupported / event.entity_unsupported / event.evidence_invalid hard findings를 보존한다.
- [x] Step 3: 상단 conclusion/driver/caution/TL;DR content producer를 사건 기반으로 연결하고 u153 sentence bound를 재사용한다.
- [x] Step 4: GenerationResult → orchestrator → PublicDocumentContext의 default-empty frozen event payload를 전달한다.
- [x] Step 5: B8의 bounded repair reconciliation과 reindex를 구현한다. 모든 수정 후 기존 hard gates와 읽기 전용 terminal/summary 검증을 다시 수행한다.
- [x] Step 6: PublicEventSummary와 optional events DTO, 기존 conclusion consumer 호환을 추가한다. notifierlayout은 수정하지 않는다.
- [x] Step 7: 전체 real-finalizer/HTML/partial tests와 provider replay를 통과시킨다. u159평가 통과 전active는blocked다.

## Acceptance Criteria
1. AC-158.1: 정책결정·실적·제품·발언 fixture에서 selected 사건의 what/when/required facts/why/reaction status/source가최종②에존재한다.
2. AC-158.2: 동일fixture에서source title나URL만 남은문서는상세설명완료로인정되지않는다.
3. AC-158.3: 숫자 없는 중요 사건의 80자 이내 첫 문장이 상단 결론에 남는다. 90자 초과 단일 문장은 retry 대상이다. 사건 0건과 수집 부족은 다른 안내문을 쓴다.
4. AC-158.4: containment/부분bundle재조립후살아있는사건만TL;DR/callout/DTO에있으며finalizer2회byte동일이다.
5. AC-158.5: 구조화 factual slots의 미허용 fact/entity/refs와 기존 compliance 위반은 hard gate에서 거부한다. 필드별 refs mismatch negative와 자유 서술 주석 평가를 별도로 통과하며 유효 sibling은 게시 가능하다.
6. AC-158.6: u154 전후layoutfixture와legacyDTOconsumer호환,추가LLM단계0,기존7섹션/면책조항보존을증명한다.

## Tests / Validation
Planned test targets (new paths are to be created): `tests/unit/briefing/test_event_narrative.py tests/unit/publisher/test_event_blocks.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/integration/test_event_finalization.py`.

```sh
uv sync --extra dev --extra docs
uv run python -m pytest -q tests/unit/briefing/test_event_narrative.py tests/unit/publisher/test_event_blocks.py tests/unit/publisher/test_summary_sentence_extension_u153.py tests/integration/test_event_finalization.py
uv run ruff check src tests
uv run mypy src
python scripts/check_no_paid_apis.py
git diff --check
```

Before the final integration, run the repository's current full gate and the shared golden matrix. Do not claim scheduled shadow, source qualification, notification or Pages checks from offline tests. Each fixture asserts final reader-visible output/typed outcome, not only helper internals. The exact test module names must be created or mapped to a verified existing module before running; this planning task does not execute future tests.

## Non-Goals
No promise of worldwide event completeness, no fabricated importance/market causality, no copying of unqualified full articles, no increasing LLM stages or removing data-trust gates. u154 layout, u156 Telegram formatting, unrelated sector dashboard/activation gates remain with their owners.

## Completion and handoff
Deliver code/test diff, focused/full gate evidence, per-AC results, cumulative read-only review, cross-check and public-surface compatibility proof. State remains Backlog until work actually starts. Code completion, remote delivery and operational activation are distinct statuses. The user authorized a commit and push after each completed unit on 2026-09-27.
