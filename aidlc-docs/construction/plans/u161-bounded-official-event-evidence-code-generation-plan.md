# Code Generation Plan: `u161 bounded-official-event-evidence`

**Date**: 2026-09-26
**Unit**: u161 bounded-official-event-evidence
**Stage**: Code Generation (planned)
**Status**: Queued — design approved; source qualification is part of implementation; body fetch remains gated.
**Source**: `../news-event-briefing/evidence/review-20260922.md`; user planning request 2026-09-26.
**Estimated Effort**: ~16–24 h plus source qualification
**Dependencies**: 자격검증/기존feed진단은독립. typed enrichment integration은u157. 신규officialbody는source별qualification후에만구현/활성화.

## Problem Statement
기존뉴스에는280자요약/제목수준자료가많아정책발표·실적내용을충분히설명하기어렵다. 9/22검토에서는CNBC/Korea policy반복장애가있었다. 현재접속상태는qualification에서다시확인한다.

## Goal
공식 사건 근거 보강과 뉴스 소스 복구 판정을 통해 전일 중요한 사건을 독자가 이해하고 신뢰 수준을 구분하게 한다. 자세한 동작은 [설계](../u161-bounded-official-event-evidence/design-brief.md)의 Fixed contracts로 고정한다.

## Existing Coverage / Deduplication
Extend u103 Fed/SEC RSS, u126 CFTC RSS, u1/u102 adapterregistry, u27 R13, u95 runtime budgets. Add only the named event/window extension; no replacement pipeline/finalizer, generic new quality dashboard, generic numeric engine, or parallel source registry.

## Scope Boundary
In scope: `sources/fed_speech_rss.py, fomc_rss.py, sec_newsroom_rss.py, cftc_policy_rss.py, cnbc_top_news.py, korea_policy_rss.py, _retry.py, sources/aggregator.py, orchestrator/pipeline.py, briefing/generation_contract.py, models/items.py (u157 evidence field), sources/aggregator.py, briefing/generation_contract.py`; new files `sources/event_evidence.py; ops/event_source_qualification.json (planned contract)`.
No production activation, historical archive rewrite, paid API, independent LLM evaluation stage, credentials change, or unrelated unit completion.

## Stage Decision
Functional Design: REQUIRED; design draft and common event contracts are written, approved 2026-09-27.
NFR Requirements: REQUIRED — 새로운외부본문I/O와source권리/fixture/SSRFlimit/latency. NF1/4/6/7/8/10, NFR-008 적용.
Use the shared NFR/validation document; no boilerplate infrastructure stage. This code plan does not bypass design/source/operational gates.

## Fixed Implementation Contracts
Normative: [design-brief](../u161-bounded-official-event-evidence/design-brief.md), [event-contract](../news-event-briefing/event-contract.md), [business-rules](../news-event-briefing/business-rules.md), [NFR](../news-event-briefing/nfr-and-validation.md). The numbered rules and exact defaults there are part of this plan. Changes require synchronized design/AC updates.

## Implementation Steps
- [ ] Step 1: 기존2개장애source의현재probe와진단기록을작성한다. 결과에따라동일source수리또는blocked판정을명시한다.
- [ ] Step 2: 4개officialsource의본문qualificationmatrix와fixture/권리증거를채운다. qualified0이면StageC를실행하지않는다.
- [ ] Step 3: adapter parsing 시 280자 절단 전 bounded detail_excerpt를 만들고 NormalizedItem.event_evidence에 연결한다. 없는 source는 None, off mode serialization은 기존 bytes를 유지한다.
- [ ] Step 4: qualified manifest만 사용하는 fetch/parser를 구현한다. qualified source가 0이면 Stage C 구현은 보류하고 관련 AC를 blocked/pending으로 남긴다. 다른 stage 완료와 혼동하지 않는다.
- [ ] Step 5: typed item evidence가 collection/routing/GenerationInput/Stage1 buffer로 전달되게 하고 Stage C는 같은 identity의 새 revision으로 보강한다.
- [ ] Step 6: Stage1/2 excerptbudget과실적/예상/시점추출negative를검증한다.
- [ ] Step 7: 수리sourceliveevidence와enrichmentfixture/성능검증을따로기록한다. 신규fetch는sourcequalification및운영승인전off다.

## Acceptance Criteria
1. AC-161.1: CNBC/Korea policy 각각현재원인/동일source수리결과또는blocked이유가실제증거와함께있다.
2. AC-161.2: qualification이없는URL/새provider/access제한을자동fetch하지않고qualifiedHTTP외에는원feed를유지한다.
3. AC-161.3: 281~1200번째 문자에만 있는 핵심 사실이 typed evidence를 통해 Stage1 buffer와 Stage2 선정 span에 실제 도달한다. routing 제외/실패 source의 근거가 다른 item에 붙지 않는다.
4. AC-161.4:6요청/동시2/20초/500KiB/소스2기사/excerpt1200상한과redirect/SSRFnegative가통과한다.
5. AC-161.5:본문fetch실패가원뉴스를삭제하지않고가짜실적actual/정책결정/시점을만들지않는다.
6. AC-161.6:rawbody/secret/privatefixture는publicgit에없고NFR-008/DEBT-090성능상태를정확하게보고한다.

## Tests / Validation
Planned test targets (new paths are to be created): `tests/unit/sources/test_event_evidence.py tests/unit/sources/test_cnbc_top_news.py tests/unit/sources/test_korea_policy_rss.py tests/integration/test_event_enrichment.py`.

```sh
uv sync --extra dev --extra docs
uv run python -m pytest -q tests/unit/sources/test_event_evidence.py tests/unit/sources/test_cnbc_top_news.py tests/unit/sources/test_korea_policy_rss.py tests/integration/test_event_enrichment.py
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
