# Component Dependencies & Data Flow: Investo

**Date**: 2026-04-27

---

## Dependency Matrix

행 = 의존하는 쪽 (caller), 열 = 의존받는 쪽 (callee).

| Caller \ Callee | models | sources | briefing | publisher | notifier | external |
|-----------------|:------:|:-------:|:--------:|:---------:|:--------:|----------|
| **sources** | ✅ | — | — | — | — | httpx, 무료 API들 |
| **briefing** | ✅ | — | — | — | — | `claude` CLI (subprocess) |
| **publisher** | ✅ | — | — | — | — | `git` CLI, 파일시스템 |
| **notifier** | ✅ | — | — | — | — | httpx, Telegram Bot API |
| **orchestrator** | ✅ | ✅ | ✅ | ✅ | ✅ | (내부 의존만) |
| **models** | — | — | — | — | — | pydantic v2 |

### Key Properties
- `models`는 leaf node (가장 안쪽). 모든 다른 컴포넌트가 의존.
- `orchestrator`는 root (최상위). 다른 모든 컴포넌트를 호출.
- `sources / briefing / publisher / notifier`는 서로 의존하지 않음 (수평 독립). 통신은 항상 orchestrator를 거침.
- 순환 의존성 없음 (DAG).

---

## Communication Patterns

| From → To | Pattern | Synchrony | Data |
|-----------|---------|-----------|------|
| GitHub Actions → orchestrator | subprocess (`python -m investo.run`) | sync | env vars |
| orchestrator → sources.fetch_all | function call | async | `target_date` |
| sources → external APIs | HTTP | async (httpx) | API requests/responses |
| orchestrator → briefing.generate_briefing | function call | async | `list[NormalizedItem], target_date` |
| briefing → claude CLI | subprocess (`claude -p`) | sync (in-thread) | prompt stdin/arg, markdown stdout |
| orchestrator → publisher.write/verify/commit | function call | sync | `Briefing, target_date` |
| publisher → filesystem | I/O | sync | markdown files |
| publisher → git CLI | subprocess | sync | git commands |
| orchestrator → notifier.BriefingPublisher.send | function call | async | `BriefingNotification` |
| orchestrator → notifier.OperatorAlerter.alert | function call | async | `FailureContext` |
| notifier → Telegram Bot API | HTTP | async (httpx) | sendMessage |
| GitHub Actions → mkdocs build → Pages deploy | step chain | sync | static site files |

---

## Data Flow Diagram

```
                                +--------------------+
                                | GitHub Actions cron|
                                +---------+----------+
                                          |
                                          v  python -m investo.run
                                +---------+----------+
                                |   orchestrator     |
                                |  (run_pipeline)    |
                                +---------+----------+
                                          |
              +----------------+----------+----------+----------------+
              | (1) collect    | (2) generate         | (3) publish    | (4) notify
              v                v                      v                v
     +----------------+ +----------------+ +----------------+ +----------------+
     |    sources     | |    briefing    | |   publisher    | |    notifier    |
     | (asyncio.gather| | (Claude Code   | | (md write +    | | (Telegram Bot  |
     |  + degradation)| |  CLI two-stage)| |  git push +    | |  API)          |
     |                | | + disclaimer   | |  verify)       | |                |
     +-------+--------+ +-------+--------+ +-------+--------+ +---+--------+---+
             |                  |                  |             |        |
             v (HTTP)           v (subprocess)     v             v        v
    +-----------------+ +----------------+ +----------------+ +----------+ +-----------------+
    | Free APIs       | | claude CLI     | | filesystem     | | Telegram | | Telegram        |
    | (news, prices,  | | (subscription  | | + git remote   | | public   | | operator 1:1    |
    |  macro, ...)    | |  via OAUTH     | | (origin/main)  | | channel  | | chat            |
    |                 | |  TOKEN)        | |                | | (FR-004) | | (FR-007)        |
    +-----------------+ +----------------+ +----------------+ +----------+ +-----------------+
                                                  |
                                                  v
                                         +-----------------+
                                         | GitHub Pages    |
                                         | (mkdocs build   |
                                         |  via Actions    |
                                         |  step, after    |
                                         |  publish commit)|
                                         +-----------------+
```

---

## Failure Path Diagram (graceful degradation)

```
collect (some sources fail)
   |  log + continue
   v
items list (possibly partial)
   |
   +-- empty? --> alert (operator) + exit FAILED  -----> OperatorAlerter
   |
   v
generate (LLM call)
   |
   +-- retries exhausted --> alert + exit FAILED   -----> OperatorAlerter
   |
   v
briefing (with disclaimer auto-appended)
   |
   v
publish (verify_disclaimer + git push)
   |
   +-- disclaimer missing --> alert + exit FAILED  -----> OperatorAlerter
   +-- git push fails (after retries) --> alert + FAILED -> OperatorAlerter
   |
   v
notify_briefing (channel push)
   |
   +-- fails --> mark PARTIAL, do NOT alert (v1)
   |
   v
PipelineResult: SUCCESS | PARTIAL
```

---

## External Dependency Inventory

| Component | External Dep | Purpose | Auth/Config |
|-----------|--------------|---------|-------------|
| sources | httpx | async HTTP | — |
| sources | 무료 API들 (TBD: yfinance, FRED, CoinGecko, FOMC RSS, Earnings Calendar 등) | 데이터 수집 | 일부는 free API key (선택), 일부는 키 불필요 |
| briefing | `claude` CLI binary | LLM 호출 | `CLAUDE_CODE_OAUTH_TOKEN` env (GitHub Secrets) |
| publisher | `git` CLI binary | commit/push | GH Actions runner의 GITHUB_TOKEN |
| publisher | 파일시스템 | markdown 저장 | working dir = repo root |
| notifier | Telegram Bot API | sendMessage | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_BRIEFING_CHANNEL_ID` + `TELEGRAM_OPERATOR_CHAT_ID` |
| (workflow) | mkdocs + actions/configure-pages + actions/deploy-pages | site build/deploy | GH Actions native |

---

## Dependency Stability Notes

- `httpx`, `pydantic v2` — stable, semver
- 무료 외부 API들 — **불안정 가능성 높음** (rate limit, schema 변경, 서비스 종료) → graceful degradation으로 흡수, 신규 소스 추가는 plugin 한 모듈 추가로 (US-008)
- Telegram Bot API — 안정
- `claude` CLI — Anthropic 제공, OAuth token 인증. 향후 SDK가 변경되면 `briefing.call_claude_code` 한 곳만 수정하면 됨 (캡슐화)
- `git` CLI — 시스템 표준
