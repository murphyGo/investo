# Code Generation Plan: u171 event-reader-surfaces-and-asset-impact

**Date**: 2026-10-10
**Unit**: u171 event-reader-surfaces-and-asset-impact
**Stage**: Code Generation — 계획
**Status**: 설계 작성; 구현0/8
**Source**: 사용자 사건 중심 전체 독자 경험; [근거](../event-news-v3/evidence.md)
**Estimated Effort**: 20–28h
**Dependencies**: u169 PublicEditionView/terminal DTO, u170 story projection. u156의currentref/owner확인은통합작업이며새Telegramengine선행조건이아니다.

## Problem Statement
현재 한 줄 conclusion과 가격 중심 watchlist가 실제 여러 중요 사건의 전달을 제한한다. 홈·회고·시각의 legacy callout parser와 generated Briefing 의존이 v3와 분리되지 않으면 삭제 사건/오래된 지표가 요약에 재등장할 수 있다.

## Goal
모든 독자 표면이 같은 봉인된 사건·변화·상태를 전달하고, 관심자산 영향은 사건 근거와 연결 경로를 설명한다. 제품 상단의 중복·장식을 줄인다.

## Existing Coverage / Deduplication
u156예약notifier/u154legacyreflow/u64·u111relevance/u20·u29retrospective/u141·u143visual/provenance/u144seal을확장한다. u169본문renderer와terminalfact검증, u170storyreducer를중복구현하지않는다. 기존price/watchlistengine을삭제해검증을우회하지않는다.

## Scope Boundary
In scope: notifier/summary.py와BriefingPublisher의versionedterminalDTOformatting; publisher/site_index/,weekly_digest.py,monthly_index.py,watchlistconsumer; visuals/assets.py,og_card.py,image_selection.py의modelsview소비; models/event_asset_impact.py및briefing의pureevent-to-assetmatchingextension; 필요한site_docsstyle/표면template조정.
Out of scope: 새source/LLM단계, event생성/ledger/finalizer, productiondispatch, 과거archive변경, 다른sector대시보드활성화.

## Stage Decision
Functional Design: REQUIRED — 웹·알림·관심자산의제품표시와event관련성계약변경. [설계](../u171-event-reader-surfaces-and-asset-impact/design-brief.md).
NFR Requirements: REQUIRED — UTF-16budget/terminal모델/provenance/원자성/viewport와historicalconsumer분리. [NFR](../event-news-v3/nfr-design.md)의N2/N3/N4/N5/N6/N8을적용한다.

## Fixed Contracts
[C4/C5](../event-news-v3/contracts.md)와 설계의 표면별 계약을 소비한다. 이벤트 모델·summary DTO·EventAssetImpact 선언은 u169의 canonical owner를 재사용한다. u171은 봉인 전 matcher·EventVisualInput 기반 E1 staging과 봉인 후 formatting을 소유한다. 관찰 가격과 news 영향을 구별한다. Telegram은 필수 상태/링크/면책을 예약한 후 완성된 digest를 추가하고 후순위 항목 전체를 제외한다.

## Implementation Steps
- [ ] 1. currentmain/u154/u156과grep으로surfaceconsumerinventory를고정하고GeneratedBriefing/callout/7H2의존을 분류한다. 공유타입은models만통과한다.
- [ ] 2. u169의 EventAssetImpact를 소비하는 relevance engine extension을 구현한다. 봉인 전 source-backed 직접/간접 mechanism과 condition, fact/ref 소유권을 검증해 draft로 전달하고 uncertain/rejected는 private diagnostic으로 분리한다.
- [ ] 3. notifier에EventNotificationSummaryV3formatting을 추가하고UTF-16budget/whole-event제외/partial/면책/retry/채널분리를유지한다.
- [ ] 4. 홈·시장 index에 digest→terminal headline→사건 0일 때 availability 순서를 적용한다. event_archive_reader.py에서 C5a sidecar/Markdown hash를 검증하고 missing/mismatch를 제한으로 표시한다. historical reader와 v3 current reader를 분리한다.
- [ ] 5. 주간/월간/관심자산페이지에서event/storyID와 검증된delta·출처를사용하고price-onlynews영향표시를제거한다.
- [ ] 6. 본문 visual의 E1 preparation을 EventVisualInput으로 전환하고 finalizer가 survivor에 맞는 used-only 후보를 선택하게 한다. OG는 기존 post-seal write_og_card에서 sealed public view로 생성하여 같은 publication transaction에 포함한다. 기본 hero 없음·가격 참고 영역과 본문 post-seal rewrite 금지를 적용한다.
- [ ] 7. 최종본문·DTO·홈·회고·시각·asset영향의 같은ID/statefixture와390×844/1440×900render를확인한다.
- [ ] 8. targeted/full/static/policy/strictMkDocs검증와 독립review를완료하고u172에actualsurface/corpushandoff를전달한다.

## Acceptance Criteria
1. AC-171.1: 웹/알림/홈/회고/OG/watchlist의모든v3readerfact가같은terminalevent/state에서파생되고생성초안을사실원본으로읽지않는다.
2. AC-171.2: source-backed직접/간접영향은eventID/fact/ref/condition을가지며priceitem/ticker만으로news영향을 확정하지않는다.
3. AC-171.3: 최종Telegram이4096UTF-16을지키고필수링크/상태/면책을보존한다. 후순위event는wholeunit으로제외하며중간절단·새fact·별도LLM요약0.
4. AC-171.4: sidecar/Markdown hash 검증으로 과거 v3를 복원하고 당시 상태와 최신 상태를 구별한다. 누락/불일치는 제한으로 표시하고 재추론하지 않는다.  제거/미게시event가 어떤surface에도 재등장하지않고history/retrospective는미해결상태를해결로추론하지않는다.
5. AC-171.5: v3기본hero는 없고관련licensedhero만 주요사건뒤에 1개가능하며기존E1/E5/E6provenance와 transaction을보존한다.
6. AC-171.6: 모바일/desktop첫화면에 사건요약/한계가가격/진단보다앞에보이고중복H1·강제3fallback·동일macro/callout반복가 없다.
7. AC-171.7: immutablelegacyarchive/URL/visual가 읽히고livev3는 legacygenerator/빈7fieldbridge에 의존하지않는다.
8. AC-171.8: public/operator채널분리,validsiblingpartial·notification-onlyfailure·retrybudget와 existingphoto/sourcegate을 유지한다.

## Tests / Validation
새targets: tests/unit/notifier/test_event_summary_v3.py, tests/unit/publisher/test_event_surface_views_v3.py, tests/unit/briefing/test_event_asset_impact.py, tests/integration/test_event_surface_consistency_v3.py, tests/integration/test_event_reader_html_v3.py. 기존notifier/siteindex/weekly/OG/asset/provenance회귀를함께유지한다.

```sh
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest -q tests/unit/notifier/test_event_summary_v3.py tests/unit/publisher/test_event_surface_views_v3.py tests/unit/briefing/test_event_asset_impact.py tests/integration/test_event_surface_consistency_v3.py tests/integration/test_event_reader_html_v3.py
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run python -m pytest -q
uv run mkdocs build --strict
python scripts/check_no_paid_apis.py
git diff --check
```

viewport기록은render된finalHTML과exactcodeSHA에 연결한다. browser불가하면 AC-171.6는 미검증으로남기고sitebuild을 viewport합격으로대체하지않는다.

## Non-Goals
새bot/dispatcher,가격데이터만의투자영향추론,unsealed재요약,기존source/secret/asset/채널gate완화,역사archive의일괄rewrite.
