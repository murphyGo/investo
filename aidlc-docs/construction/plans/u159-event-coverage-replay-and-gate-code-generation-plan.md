# Code Generation Plan: `u159 event-coverage-replay-and-gate`

**Date**: 2026-09-26
**Unit**: u159 event-coverage-replay-and-gate
**Stage**: Code Generation (planned)
**Status**: Queued — design approved; follows u157/u158.
**Source**: `../news-event-briefing/evidence/review-20260922.md`; user planning request 2026-09-26.
**Estimated Effort**: ~12–18 h
**Dependencies**: u157 선정/trace, u158 terminal event renderer/projection. 기존u65/u123/u144 완료.

## Problem Statement
기존 성공지표는 핵심이슈누락없음이지만품질history는숫자/소스/fallback 중심이다. sourceURL 언급만으로정책결정의설명깊이를보장하지못한다.

## Goal
중요 사건 반영률과 최종 품질 검증을 통해 전일 중요한 사건을 독자가 이해하고 신뢰 수준을 구분하게 한다. 자세한 동작은 [설계](../u159-event-coverage-replay-and-gate/design-brief.md)의 Fixed contracts로 고정한다.

## Existing Coverage / Deduplication
Extend u59 lineage, u54/u62/u96/u123 truthful metrics, u65 replay, u144 terminal gate. Add only the named event/window extension; no replacement pipeline/finalizer, generic new quality dashboard, generic numeric engine, or parallel source registry.

## Scope Boundary
In scope: `briefing/quality_eval.py, briefing/quality_history.py, models/quality_history.py, publisher/public_document.py, publisher/quality_consistency.py, orchestrator/pipeline.py, scripts/check_event_coverage.py`; new files `publisher/event_quality.py; tests/fixtures/event_briefing/manifest.json; scripts/check_event_coverage.py`.
No production activation, historical archive rewrite, paid API, independent LLM evaluation stage, credentials change, or unrelated unit completion.

## Stage Decision
Functional Design: REQUIRED; design draft and common event contracts are written, approved 2026-09-27.
NFR Requirements: REQUIRED — 공개품질의 분모·unknown 의미와 terminal gate 추가. NF1/3/6/7/9/10 적용.
Use the shared NFR/validation document; no boilerplate infrastructure stage. This code plan does not bypass design/source/operational gates.

## Fixed Implementation Contracts
Normative: [design-brief](../u159-event-coverage-replay-and-gate/design-brief.md), [event-contract](../news-event-briefing/event-contract.md), [business-rules](../news-event-briefing/business-rules.md), [NFR](../news-event-briefing/nfr-and-validation.md). The numbered rules and exact defaults there are part of this plan. Changes require synchronized design/AC updates.

## Implementation Steps
- [ ] Step 1: E8 stage receipts와 terminal result→QualitySnapshot 변환을 작성한다. default-null 역사호환을검증한다.
- [ ] Step 2: actor/action/fact/source/상태의final-block검사와새event issue codes를추가한다. source-only/marker-onlynegative를고정한다.
- [ ] Step 3: u144 real-finalizer 후검증과 public-quality consistency를연결하고state별분모를명시한다.
- [ ] Step 4: 18편출력inventory 및12시나리오goldenmanifest를작성하고합성/R10privatefixture경계를고정한다.
- [ ] Step 5: 오프라인script가manifest→실제pipelinefixture→sealedHTML/DTO를대조하도록구현한다. 실패원문은stdout에출력하지않는다.
- [ ] Step 6: 기존 quality/replay/full gate와 독립 리뷰를 통과한 뒤 v2 비게시 preview 품질과 live shadow 비간섭 증거를 분리해 기록한다. 활성화는 별도 운영 단계다.

## Acceptance Criteria
1. AC-159.1: marker-only/URL-only/requiredfact제거/summary재노출negative가전부검출된다.
2. AC-159.2: selected0/수집실패/미분류/partialpublish/알림만실패의분모와상태가거짓0/100%없이일치한다.
3. AC-159.3: historicalrecord의새필드null과현재receipt의실제count가페이지/메타에서동일하다.
4. AC-159.4:12golden시나리오의must_include/required facts100%,unsupported추가0;의미평가5/5기준을만족한다.
5. AC-159.5: 삭제/repair/부분 재조립 후 DTO는 terminal의 알림 적격 최대 3개 ordered subset이며 값이 일치한다. terminal 사건 4개·5개 fixture도 통과한다.
6. AC-159.6: source원문/privateprose/logsecret이공개fixture/quality에없고추가LLM평가호출0.

## Tests / Validation
Planned test targets (new paths are to be created): `tests/unit/publisher/test_event_quality.py tests/unit/briefing/test_quality_history.py tests/integration/test_event_coverage_replay.py`.

```sh
uv sync --extra dev --extra docs
uv run python -m pytest -q tests/unit/publisher/test_event_quality.py tests/unit/briefing/test_quality_history.py tests/integration/test_event_coverage_replay.py
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
