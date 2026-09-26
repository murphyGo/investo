# Code Generation Plan: `u160 publication-news-observation-window`

**Date**: 2026-09-26
**Unit**: u160 publication-news-observation-window
**Stage**: Code Generation (planned)
**Status**: Queued — design approved; follows u159 in the user-requested sequence; cursor uses u157 receipt.
**Source**: `../news-event-briefing/evidence/review-20260922.md`; user planning request 2026-09-26.
**Estimated Effort**: ~20–30 h
**Dependencies**: u157의 공통 PublishReceipt/transaction 기반. window 모델·adapter 설계와 구현은 병렬 가능하나 cursor 통합은 u157 이후다. 기존 u1/u5/u31/u35/u102/u113/u144 완료.

## Problem Statement
월요일기본target_date가금요일이고RSS도하루창으로필터링되어토·일사건을별도로관측하지못한다. DART와정책adapter는window범위대신target_date를직접사용한다.

## Goal
주말·장후 뉴스를 포함하는 관측기간을 통해 전일 중요한 사건을 독자가 이해하고 신뢰 수준을 구분하게 한다. 자세한 동작은 [설계](../u160-publication-news-observation-window/design-brief.md)의 Fixed contracts로 고정한다.

## Existing Coverage / Deduplication
Extend u1 FetchWindow, u5 date_resolution, u35 lookahead, u102 source specs, u113 transaction, u144 published survivors. Add only the named event/window extension; no replacement pipeline/finalizer, generic new quality dashboard, generic numeric engine, or parallel source registry.

## Scope Boundary
In scope: `models/news_window.py, orchestrator/stage_context.py, orchestrator/stages.py, orchestrator/pipeline.py, __main__.py, sources/aggregator.py, _window.py, _internal/source_specs.py, sources/dart_disclosure.py, sources/official_policy.py, publisher/git_ops.py, models/coverage.py (window result capability)`; new files `models/news_window.py; orchestrator/news_window.py; archive/_meta/news_cursors.json (runtime output only)`.
No production activation, historical archive rewrite, paid API, independent LLM evaluation stage, credentials change, or unrelated unit completion.

## Stage Decision
Functional Design: REQUIRED; design draft and common event contracts are written, approved 2026-09-27.
NFR Requirements: REQUIRED — temporal semantics, bounded fetch/pagination, persistentcursor/remotecommit failure 변경. NF3/5/6/7/9/10 적용.
Use the shared NFR/validation document; no boilerplate infrastructure stage. This code plan does not bypass design/source/operational gates.

## Fixed Implementation Contracts
Normative: [design-brief](../u160-publication-news-observation-window/design-brief.md), [event-contract](../news-event-briefing/event-contract.md), [business-rules](../news-event-briefing/business-rules.md), [NFR](../news-event-briefing/nfr-and-validation.md). The numbered rules and exact defaults there are part of this plan. Changes require synchronized design/AC updates.

## Implementation Steps
- [ ] Step 1: mode/window/cursor/coverage DTO 및runclock 주입을추가하고cron/replay/dry-run입력을구분한다.
- [ ] Step 2: source별opt-inregistry와aggregatorunion-fetch/segment-filter를구현한다.
- [ ] Step 3: DART 자정·날짜 정밀도/3페이지/총 20초, 공식 정책 실제 발표 필터를 수정한다. RSS full 자격과 pinned/gap/빈 XML/partial parse fixtures를 추가한다.
- [ ] Step 4: remote cursor와 24h overlap, document/revision dedup, 최대 7일 gap을 구현한다. shadow/replay/dry-run은 생산 cursor bytes를 보존한다.
- [ ] Step 5: E11 PublishReceipt에 window baseline hash와 consumed receipt를 연결한다. push 응답 유실·remote ancestor 확인·clean rebase CAS 변경·pending 재실행을 검증한다.
- [ ] Step 6: 뉴스watermark와qualityreceipt를연결하되가격/지표/예정일정출력은유지한다.
- [ ] Step 7: 주말/DST/휴일/장후/partial/failureintegration을통과시키고shadow에서window만관찰한다. 운영cursor전환은별도gate다.

## Acceptance Criteria
1. AC-160.1: 월요일실행에토·일보도fixture가들어오고금요일가격기준일은유지된다. DST23/25h날짜와UTC시간이정확하다.
2. AC-160.2: replay/dry-run이livecursor를읽거나쓰지않고동일manifest재생은동일window다.
3. AC-160.3: DART 자정 종료/날짜 정밀도/3페이지·총 20초 및 official-policy/FOMC 실제 발표·예정 분리를 검증한다.
4. AC-160.4: shadow 정상 3/3 게시에도 cursor bytes는 같다. partial segment/failed source/pinned RSS/빈 XML/unknown에서 cursor가 잘못 전진하지 않는다.
5. AC-160.5: pre/post-commit 실패, push 성공·응답 유실, remote tip 전진과 clean rebase CAS 변경 후에도 다음 실행은 원격 확정 cursor만 쓴다. 알림만 실패하면 cursor를 유지한다.
6. AC-160.6: 최초 72h/최대 7d/24h overlap, 지연·수정 기사 dedup, 서로 다른 source 창의 envelope/gap/completeness를 명시하며 포착 완료로 오인시키지 않는다.

## Tests / Validation
Planned test targets (new paths are to be created): `tests/unit/orchestrator/test_news_window.py tests/unit/sources/test_aggregator.py tests/unit/sources/test_dart_disclosure.py tests/unit/sources/test_official_policy.py tests/integration/test_news_cursor_transaction.py`.

```sh
uv sync --extra dev --extra docs
uv run python -m pytest -q tests/unit/orchestrator/test_news_window.py tests/unit/sources/test_aggregator.py tests/unit/sources/test_dart_disclosure.py tests/unit/sources/test_official_policy.py tests/integration/test_news_cursor_transaction.py
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
