# Public insights main integration review

작성일: 2026-10-25. 별도 reviewer. 현재 확인한 통합 변경의 미해결 **Critical 0 / High 0 / Medium 0**.

## 검토 기준과 범위

검토 트리는 `codex/public-insights-main-integration-20261025`의 merge --no-commit 상태다. main 기준은 `0768d780d2e8c2487a004927603c398f8d21c0e8`, feature는 `cb56fd7dd3300a5ce5832d26f8d8672997fffffa`, merge base는 `55c00fc85e2828f62cd69d5583afd3761ef86d45`다. 최종 merge commit/원격 배포 SHA를 이미 수용했다는 의미가 아니다.

기존 u180–u183 전체 재리뷰 대신 code-review의 correctness/security/data-integrity/concurrency/error/lifecycle 관점으로 main 대비 pipeline handoff diff와 feature 대비 최신 v3/news 통합 차이를 읽었다. ops runtime template·entrypoint 결과 신호·event/news config gate도 대조했다. audit conflict는 두 부모 각각의 모든 nonempty line이 통합 파일에 남는지 Counter로 확인하여 missing=0/0을 얻었다. conflict marker 및 diff --check에서도 문제를 확인하지 못했다. 이 확인은 감사 로그 양측 내용 보존이며 과거 모든 기록의 사실을 새로 검증한 것은 아니다.

## 통합 경계 확인

- main의 v3/news baseline load 분기, `event_v3_baseline` stage data handoff, native generation/finalization/publication 경로를 유지한다. main 대비 pipeline 변경은 opt-in insights collect option/report sink·capture/strip·phase·optional result 전달에 한정한다.
- news-active와 일반 collect가 동일한 opt-in 요청을 받고 collect 직후 insights를 처리한다. private envelope를 legacy/native generation 소비자에 넘기기 전에 제거한다. 정상/empty collect source outcomes와 기존 EmptyCollectError 의미도 유지한다.
- v3 baseline/news windows를 수집한 뒤 insights가 별도 manifest-only receipt로 게시되더라도 event/news metadata를 바꾸지 않는다. native/event/news publisher는 기존 metadata CAS/receipt owner를 그대로 사용한다. scoped publication 회귀를 실제 local bare Git으로 실행했다.
- 뒤 generation 실패에도 stage accumulator의 confirmed insights 결과를 최종 PipelineResult에 전달한다. briefing publication_committed/status/종료 의미와 insights receipt를 구별한다. dry-run/replay의 write0 및 bounded cancellation drain·retained receipt 복구는 기존 feature 구현을 유지하며 관련 회귀를 통합본에서 다시 실행했다.
- feature 대비 `stages.py`, `__main__.py`, production runtime template에는 추가 통합 drift가 없다. Pages 조건은 briefing OR confirmed insights, target SHA는 briefing이 게시됐으면 그 결과, 아니면 confirmed insights SHA를 사용한다. failed/unknown receipt를 성공으로 바꾸지 않으며 기존 pipeline exit code 재발급을 유지한다.

## reviewer 직접 실행한 교차 회귀

```text
.venv/bin/python -m pytest tests/unit/orchestrator/test_insights_capture_u180.py tests/integration/test_insights_publication_u180.py tests/unit/orchestrator/test_event_v3_cutover_u172.py tests/unit/orchestrator/test_private_publication_u155.py tests/integration/test_event_publication_v3.py tests/integration/test_news_window_pipeline.py -q
67 passed in 83.40s
```

추가로 repo 파일을 쓰지 않는 독립 test seam을 실행했다. 직접 Stage context의 schema3 preview + news active + insights active 조합에서 baseline loader/source/insights만 대체하고 실제 CollectStage→후속 실패 stage→실제 결과 composer를 통과시켰다. runtime의 v3/news capability는 test seam에서만 대체하고 공개 entrypoint 활성화 gate를 우회하는 production 변경은 하지 않았다.

```text
order ['v3_baseline', 'collect', 'insights', 'generate']
status failed
insights remote_confirmed
briefing_committed False
v3_active_gate False
```

이 seam은 collection1회, news window/insights option 전달, v3 baseline 보존, private envelope 제거, generation 실패 후 insights 결과 보존을 assertion으로 확인했다. receipt는 합성이며 production 게시 증거가 아니다.

## 실제 runtime pin과 활성화 gate

reviewer가 GitHub private repository 및 `codex-runtime` environment의 variables를 read-only 조회한 시점에 다음을 확인했다. secret 값은 조회하거나 기록하지 않았다.

- REVIEWED_CODE_SHA=`35ea6c6e8cb3e871bd06bbdb1810065b5d97949f`.
- INVESTO_EVENT_BRIEFING_MODE=`active`.
- schema/news/insights mode/modules 변수는 해당 repo/environment scope에 없었다.

통합 코드에서 해당 환경을 직접 해석·검증하면 schema2 active는 기존 domestic-equity/us-equity v2만 선택하고 v3_segments는 비어 있다. `EVENT_V3_ACTIVE_READY=False`, `NEWS_WINDOW_ACTIVE_READY=False`, schema3 공개 publication 거부가 유지됨을 실행 확인했다. insights 기본은 off/modules macro이며, 뉴스는 private workflow 기본 shadow다. pin 승격을 v3/news 활성화 허가로 확대하지 않는다.

현재 private workflow snapshot `/private/tmp/public-insights-private-daily-before.yml`에는 `concurrency.queue: max`가 있다. public runtime template로 전체 교체하면 이 private 설정을 잃을 수 있으므로 lead가 계획한 **INSIGHTS env2개+Pages 조건/선택 SHA의 네 변경만 적용하고 나머지 private workflow를 보존하는 방식**이 적절하다. 실제 private patch·pin/mode 변경과 remote readback은 아직 이 reviewer가 수행하거나 수용하지 않았다. 적용 뒤 기존 schema2/v3false/news shadow/enrichment off/queue:max·225분 allowance·0/1/2 재발급과 변경 범위를 readback해야 한다.

## 검토 트리 fingerprint

```text
pipeline.py: 2092d07c7b5ed087e3808647a7964bea650cddf7fd364537d1c5ad62b15ebe79
models/event_config.py: 18a54a4c07a2a7377471b3d6c55d25b394bf75303242db495bce29a4ab1cfa6b
models/news_window.py: 087a50d48fa471f9336aa095389cdcf887af98e061cbde4559c4c28cfdf987bc
ops/private-runtime/production-briefing.yml: f40211dfe8451fbbdb0cd8cc82eed4f1e1c2c1ce4c2b2c14b89fbb8e579e5ca4
```

이후 코드가 바뀌면 변경분의 재검토가 필요하다. 최종 merge SHA의 broader full regression/CI·strict docs/Material/Node/policy/resource/browser는 lead의 별도 검증 증거와 연결해야 한다. lead가 전달한 로컬 shadow 실원천 조회는 개발 수집 증거이며 GHA 실제 게시·Pages·5회 scheduled 관찰로 계산하지 않는다.

추가 source/test 수정, commit/push, workflow/variable 변경, dispatch/배포를 하지 않았으며 이 보고서만 작성했다. 확인한 범위에서 통합 때문에 추가로 필요한 미해결 code finding은 없다. runtime 적용 후 검증과 기존 운영 수용 단계는 별도다.
