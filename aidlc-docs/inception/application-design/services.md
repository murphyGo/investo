# Services & Orchestration: Investo

**Date**: 2026-04-27
**Note**: Investo는 단일 진입점·단일 process 배치 시스템이라 별도 service layer는 얇음. 본 문서는 orchestrator의 stage 합성 + 에러 정책을 정리.

---

## Service Inventory

| Service | Owner Component | Trigger |
|---------|-----------------|---------|
| **PipelineService** | `orchestrator` | GitHub Actions cron + workflow_dispatch |
| **DateResolutionService** | `orchestrator` | PipelineService 진입 시 |
| **AlertingService** | `notifier.OperatorAlerter` | 실패 단계에서 호출 |

외부 노출 service나 RPC는 없음. 모두 in-process Python 함수/클래스.

---

## PipelineService

### Stages and Order

```
1. collect           -> list[NormalizedItem]
2. generate          -> Briefing
3. publish           -> Path (committed)
4. notify_briefing   -> SendResult (best-effort)
```

각 단계는 orchestrator의 `_stage_*` 함수로 구현됨 (component-methods.md 참조).

### Error Policy (Q9=B Graceful Degradation)

| Stage | Failure Mode | Policy |
|-------|--------------|--------|
| collect | 단일 source 실패 | 로그만, 다른 source 계속. 결과 비어있어도 generate 진입 |
| collect | 모든 source 실패 (총량 0건) | generate 단계로 진입은 하되 LLM 입력이 비어있어 generate가 의미 없는 결과를 만들 위험 → orchestrator 가드: items 비면 게시 중단 + alert |
| generate | LLM 호출 실패 | Briefing 모듈 내 retry (지수 backoff). 최종 실패 시 raise |
| generate | 면책조항 append 실패 | 코드 상수라 실패 거의 불가. 만약 raise되면 게시 중단 |
| publish | disclaimer presence 검증 실패 | 게시 차단 + alert (NFR-004 강제) |
| publish | git push 실패 | 단계 내 retry. 최종 실패는 alert. |
| publish | mkdocs/Pages 단계 | 본 service 책임 X (GitHub Actions step에서 처리; build 실패는 GitHub native fail) |
| notify_briefing | 채널 발송 실패 | 결과만 PartialSuccess로 마킹. publish는 성공 처리. alert는 옵션. |
| (any) | 예상치 못한 Exception | 최상위 try/except → alert 후 exit 1 |

### Pseudo-flow

```
def run_pipeline(target_date):
    started = now()
    stages = {}

    # 1) collect
    try:
        items = await _stage_collect(target_date)
        stages["collect"] = "ok" if items else "ok (empty)"
    except Exception as e:
        stages["collect"] = f"failed: {e}"
        await OperatorAlerter.alert(FailureContext(stage="collect", ...))
        return PipelineResult(status=FAILED, ...)

    # Guard: empty items
    if not items:
        await OperatorAlerter.alert(FailureContext(stage="collect", error="no items"))
        return PipelineResult(status=FAILED, ...)

    # 2) generate (with disclaimer auto-append inside)
    try:
        briefing = await _stage_generate(items, target_date)
        stages["generate"] = "ok"
    except Exception as e:
        stages["generate"] = f"failed: {e}"
        await OperatorAlerter.alert(FailureContext(stage="generate", ...))
        return PipelineResult(status=FAILED, ...)

    # 3) publish (with disclaimer presence verify)
    try:
        path = await _stage_publish(briefing, target_date)
        stages["publish"] = "ok"
    except Exception as e:
        stages["publish"] = f"failed: {e}"
        await OperatorAlerter.alert(FailureContext(stage="publish", ...))
        return PipelineResult(status=FAILED, ...)

    # 4) notify briefing (best-effort)
    try:
        result = await _stage_notify_briefing(briefing, site_url)
        stages["notify_briefing"] = "ok" if result.ok else f"failed: {result.error}"
        status = SUCCESS if result.ok else PARTIAL
    except Exception as e:
        stages["notify_briefing"] = f"failed: {e}"
        status = PARTIAL  # publish는 성공이므로 PARTIAL

    return PipelineResult(target_date, status, stages, duration, briefing_url=...)
```

### Time Budget (NFR-001)

10분 한도(NFR-001)를 단계별로 분배:
- collect: 최대 4분 (asyncio.gather + per-source 30s timeout × N sources, 동시 실행)
- generate: 최대 4분 (two-stage Claude Code CLI 호출, retry 포함)
- publish: 최대 1분 (git push retry 포함)
- notify_briefing: 최대 30초 (single HTTP)
- 여유: ~30초

---

## DateResolutionService

`resolve_target_date(now_utc)` — orchestrator 내부 함수.

| Trigger time (KST) | Resolved target_date |
|--------------------|----------------------|
| 평일 07:00 (월~금) | 전일 (전일이 미국장 마감일) |
| 토요일 09:00 | 금요일 |
| workflow_dispatch (수동) | 호출자가 명시한 날짜 또는 위 규칙 |

월요일은 금요일 미국장 분석 + 주말 이슈. 일요일은 cron 미실행 (요구사항). 미국 공휴일은 v1에서 별도 처리 안 함 (Open Question — 운영 중 발견 시 보강).

---

## AlertingService

OperatorAlerter는 다음 시점에 호출:
- collect 전체 실패 또는 items 비어있음
- generate 최종 실패
- publish 최종 실패 (disclaimer 검증 실패 포함)
- (옵션) notify_briefing 실패 시 — 본 v1에서는 PartialSuccess로 처리하고 alert 생략. 패턴이 반복되면 별도 alert 추가 (Open Question).

Operator 자신도 alert 채널의 유일한 구독자이므로, alert 발송 실패는 GitHub Actions 로그에 명시적 마킹으로 fallback.

---

## Service-Story Traceability

| Service | Stories | NFR |
|---------|---------|-----|
| PipelineService | US-005 | NFR-001, NFR-003 |
| DateResolutionService | US-005 | — |
| AlertingService | US-007 | NFR-003 |
