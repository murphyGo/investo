# Functional Design: u160 주말·장후 뉴스를 포함하는 관측기간

**Date**: 2026-09-26
**Status**: Design approved by the 2026-09-27 sequential-development request. Code complete — 7/7 steps, full regression 5798 passed (462.55s); independent review PASS. Scheduled shadow and production cursor activation remain off.
**Priority / effort**: P1 / 20–30 h (rough engineering estimate, not commitment).
**Dependencies**: u157의 공통 PublishReceipt/transaction 기반. window 모델·adapter 설계와 구현은 병렬 가능하나 cursor 통합은 u157 이후다. 기존 u1/u5/u31/u35/u102/u113/u144 완료.

## Reader problem
월요일기본target_date가금요일이고RSS도하루창으로필터링되어토·일사건을별도로관측하지못한다. DART와정책adapter는window범위대신target_date를직접사용한다.

## Ownership and deduplication
Existing owners: u1 FetchWindow, u5 date_resolution, u35 lookahead, u102 source specs, u113 transaction, u144 published survivors.
Existing code touch points: `models/news_window.py, orchestrator/stage_context.py, orchestrator/stages.py, orchestrator/pipeline.py, __main__.py, sources/aggregator.py, _window.py, _internal/source_specs.py, sources/dart_disclosure.py, sources/official_policy.py, publisher/git_ops.py, models/coverage.py (window result capability)`.
Proposed new modules: `models/news_window.py; orchestrator/news_window.py; archive/_meta/news_cursors.json (runtime output only)`. These paths do not imply implementation exists.

## Shared contracts
[Program overview](../news-event-briefing/README.md), [entities and schema](../news-event-briefing/event-contract.md), [business rules](../news-event-briefing/business-rules.md), [NFR and evaluation](../news-event-briefing/nfr-and-validation.md).
The unit-specific rules below bind the shared contract. Inconsistency must be resolved in design before code; implementations cannot silently override common identity/budgets/trust semantics.

## Fixed contracts
1. NewsObservationWindow(logical_start,requested_start,end_utc,mode,run_id,baseline_ref), SourceWindowCoverage(requested_start/end,earliest/latest_observed,pages,cap_reached,completeness=full|partial|unknown)를 정의한다. 가격 target_date·history·macroactual·lookahead는 유지한다. optional fetch_with_coverage(window) → SourceFetchResult(items,window_coverage)를 models/coverage에 두고 aggregator는 한 번만 호출한다. 기존 fetch 반환은 unknown coverage로 감싼다.
2. scheduled end는 run_started_at UTC로 고정한다. logical_start는 source×수신 segment의 remote cursor 또는 최초 end-72h다. 지연·수정 기사를 위해 requested_start=max(logical_start-24h,end-7d)로 조회하며 bootstrap은 정확히 72h다. 7일 밖 gap과 24h 초과 지연의 포착 한계를 기록한다. (document_id,revision_id)로 overlap 중복을 제거하되 새 revision은 재평가한다. end<=cursor는 조회 없이 hold한다.
3. replay는명시적target_date가있는실행이다. 저장된동일publication manifest를지정하면그window,없으면source의해당시장calendar-day를사용한다. today clock/cursor를섞지않는다. override는paired INVESTO_NEWS_START_UTC/END_UTC이고target_date와함께만허용한다. dry-run/replay는productioncursor비변경이다.
4. source_specs에 news window opt-in을 명시한다. FOMC 실제 발표와 예정 lookahead를 분리한다. OpenDART inclusive bgn_de/end_de는 KST(requested_start).date()와 KST(end_utc-1 microsecond).date()다. max 3페이지와 페이지·재시도 합계 20초(기존 잔여 deadline과 min)를 적용한다. 날짜만 있는 항목은 day precision을 보존하고 UTC 범위와 날짜 구간의 교차 여부로 검사한다. 정확한 timestamp는 [start,end)로 필터한다.
5. source별 수신 창의 union을 한 번 fetch하고 최종 수신 segment에서 다시 필터한다. full은 검증된 제공자 pagination/보존·정렬 계약 또는 연속 수집 구간 증거가 있을 때만 허용한다. 일반 finite RSS는 기본 unknown이며 oldest timestamp는 진단값이다. pinned 항목, 중간 공백, 빈 XML은 full 증거가 아니다. cap/부분 parse는 partial이다. full도 세계 뉴스 완전성을 뜻하지 않는다.
6. production cursor advance는 news_window_mode=active, source coverage full, 해당 window/baseline을 실제 소비한 sealed segment receipt, remote-confirmed publication이 모두 필요하다. off/shadow/replay/dry-run은 production cursor write 0회다. 실패/partial/unknown source와 미게시 segment는 hold하며 알림만 실패하면 확정 cursor를 유지한다.
7. archive/_meta/news_cursors.json과 news_windows/{run_id}.json을 archive와 같은 transaction에 포함한다. u157의 E11 PublishReceipt를 재사용한다. pre-commit은 snapshot 복원, post-commit은 immutable pending receipt 보존 후 원격 reconcile이다. image extra_commit_paths rollback 예외를 재사용하지 않는다.
8. manifest는 run_id와 baseline cursor hash를 저장하며 자신의 commit SHA를 포함하지 않는다. 다음 실행은 remote baseline tree만 읽는다. rebase가 충돌 없이 끝나도 원격 cursor hash CAS가 달라지면 stale publication을 중단하고 새 baseline에서 재계산한다. cursor를 max() 병합하지 않는다. E11의 원격 ancestry 확인 전에는 성공/미발행을 단정하지 않는다.
9. 공개 watermark는 가격 기준일과 최종 수신 segment의 뉴스 관측 envelope(min requested_start,max end) 및 full/partial/unknown source 수를 구분한다. source별 requested range/gap은 진단으로 연결한다. envelope가 모든 source의 완전 수집 구간이라는 표현을 금지한다. 기존 archive path를 유지하고 주말 사건을 금요일 가격의 원인으로 서술하지 않는다.

## Temporal examples (synthetic)

- 월요일 `2026-09-28 07:00 KST` 실행, 확정 cursor가 금요일 `07:00 KST`이면 logical 창은 금요일 07시~월요일 07시다. 실제 조회는 24시간 overlap을 포함해 목요일 07시부터이며 반복 revision은 제거한다. 가격 기준일은 기존 금요일이다.
- cursor가 없는 같은 실행의 bootstrap은 금요일 07시부터 정확히 72시간이다.
- DART 종료가 `2026-09-28 00:00 KST`이면 inclusive end_de는 `20260927`이다. 날짜 정밀도 자료를 00시 발생 사건으로 바꾸지 않는다.
- 어떤 source는 토요일부터, 다른 source는 일요일부터 조회됐다면 public envelope는 토요일~월요일이지만 각 source의 범위와 unknown 상태를 별도 진단에 표시한다.

## Stage decision
Functional Design: REQUIRED — new cross-module/event behavior; this document and shared contracts were approved by the 2026-09-27 implementation request.
NFR Requirements: REQUIRED — temporal semantics, bounded fetch/pagination, persistentcursor/remotecommit failure 변경. NF3/5/6/7/9/10 적용.
Separate NFR Design/Infrastructure Design: no separate artifact for pure code; focused runtime/storage rules are fully specified here. u160/u161 public I/O and transaction rules require their NFR review before implementation. No new deployment platform.

## Failure and compatibility
Apply B4/B5/B8/B11 and unit-specific states. Off mode preserves current producer/consumer behavior. Existing numeric/entity/compliance hard gates and sibling availability remain authoritative. Code-ready status requires hard dependencies and design approval; source qualification stays separate from code readiness.

## Acceptance criteria
- AC-160.1: 월요일실행에토·일보도fixture가들어오고금요일가격기준일은유지된다. DST23/25h날짜와UTC시간이정확하다.
- AC-160.2: replay/dry-run이livecursor를읽거나쓰지않고동일manifest재생은동일window다.
- AC-160.3: DART 자정 종료/날짜 정밀도/3페이지·총 20초 및 official-policy/FOMC 실제 발표·예정 분리를 검증한다.
- AC-160.4: shadow 정상 3/3 게시에도 cursor bytes는 같다. partial segment/failed source/pinned RSS/빈 XML/unknown에서 cursor가 잘못 전진하지 않는다.
- AC-160.5: pre/post-commit 실패, push 성공·응답 유실, remote tip 전진과 clean rebase CAS 변경 후에도 다음 실행은 원격 확정 cursor만 쓴다. 알림만 실패하면 cursor를 유지한다.
- AC-160.6: 최초 72h/최대 7d/24h overlap, 지연·수정 기사 dedup, 서로 다른 source 창의 envelope/gap/completeness를 명시하며 포착 완료로 오인시키지 않는다.

## Development sequence
See [code-generation plan](../plans/u160-publication-news-observation-window-code-generation-plan.md). Implementation follows the 2026-09-27 user-authorized sequential queue.
