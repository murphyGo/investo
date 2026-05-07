# Units of Work: Investo

**Date**: 2026-04-27
**Source**: unit-of-work-plan.md (all recommended)
**Project type**: Greenfield monolith (single deployable Python package, GitHub Actions runner)
**Terminology**: "Unit of Work" used for development planning. There is no microservice split — this is a logical decomposition within a single deployable.

---

## Foundation: `models` (shared library)

Not a unit (no stories assigned), but a prerequisite for all units.

- Pydantic v2 types: `NormalizedItem`, `Briefing`, `BriefingNotification`, `FailureContext`, `SendResult`, `PipelineStatus`, `PipelineResult`
- Path: `src/investo/models/`
- Tests: `tests/unit/models/` (PBT for serialization round-trip per NFR-006)
- Built first (before u1) so all units can import from a stable surface.

---

## u1: `sources` — Source Adapters

**Purpose**: 무료 공개 데이터 소스 plugin들을 수집하고 비동기로 정규화 데이터를 반환.

**Stories**: US-001 (수집), US-008 (확장성)

**Module path**: `src/investo/sources/`
- `protocol.py` — `SourceAdapter` Protocol
- `registry.py` — `@register` 데코레이터 + `list_sources()`
- `aggregator.py` — `fetch_all(target_date)` (asyncio.gather + per-source isolation)
- `<source_name>.py` — 개별 어댑터 (PoC 단계에서 1~2개로 시작, 점진 추가)

**Tests**: `tests/unit/sources/`
- mock 어댑터로 registry/aggregator 동작 검증
- 부분 실패 시나리오 (단일 어댑터 raise → 다른 결과 유지)
- timeout/retry 정책

**Definition of Done**:
- [ ] `SourceAdapter` Protocol 정의
- [ ] registry + aggregator 동작
- [ ] 1개 이상의 reference 어댑터 구현 (예: 가장 단순한 RSS 또는 yfinance)
- [ ] 부분 실패 unit test 통과
- [ ] README/CONTRIBUTING에 신규 어댑터 추가 절차 문서화 (US-008 AC)

---

## u2: `briefing` — Briefing Generator

**Purpose**: NormalizedItem 리스트 → Claude Code CLI(two-stage prompt) → 면책조항 자동 삽입된 7섹션 한국어 시황 markdown.

**Stories**: US-002 (시황), US-009 (Claude Code only)

**Module path**: `src/investo/briefing/`
- `prompts.py` — `build_classification_prompt`, `build_briefing_prompt`
- `claude_code.py` — `call_claude_code(prompt, ...)` (subprocess wrapper)
- `disclaimer.py` — `DISCLAIMER` 상수 + `append_disclaimer` (idempotent)
- `generator.py` — `generate_briefing` 진입점 (two-stage 합성)

**Tests**: `tests/unit/briefing/`
- LLM 호출은 `tests/fixtures/llm/`의 record/replay로 mock
- prompt 빌더 순수 함수 테스트
- `append_disclaimer` idempotency 테스트
- retry 정책 시나리오

**Definition of Done**:
- [ ] `subprocess.run(["claude", "-p", ...])` wrapper에 timeout/retry/exit-code 처리
- [ ] Two-stage prompt 흐름 동작 (PoC fixture로 검증)
- [ ] `DISCLAIMER` 본문 코드 상수로 정의
- [ ] disclaimer auto-append + idempotent 테스트 통과
- [ ] **Anthropic SDK import 금지**: `from anthropic ...` 가 코드에 없음 검증 (간단한 grep 또는 lint rule)

---

## u3: `publisher` — Publisher

**Purpose**: 생성된 시황 markdown을 archive/YYYY/MM/YYYY-MM-DD.md에 저장하고 git commit/push. 게시 전 disclaimer 검증.

**Stories**: US-003 (정적 게시), US-006 (영구 보관)

**Module path**: `src/investo/publisher/`
- `paths.py` — `archive_path`, ARCHIVE_ROOT
- `verifier.py` — `verify_disclaimer`
- `writer.py` — `write_briefing`
- `git_ops.py` — `commit_and_push` (subprocess git)

**Tests**: `tests/unit/publisher/`
- archive_path 경로 빌드 검증
- verify_disclaimer false 시 raise 패턴
- git_ops는 subprocess mock + retry 동작
- 동일 날짜 재실행 시 덮어쓰기 시나리오

**Definition of Done**:
- [ ] markdown write가 archive 구조 준수
- [ ] verify_disclaimer가 코드 상수와 매칭
- [ ] commit_and_push retry (최대 N회) 동작
- [ ] 게시 전 disclaimer 누락 시 게시 차단 + 명시적 예외 (NFR-004 강제)

**Note**: `mkdocs build` + GitHub Pages 배포는 본 unit이 아니라 **u6 infra(CI)**의 책임.

---

## u5: `orchestrator` — Orchestrator

**Purpose**: 파이프라인 단일 진입점. 단계 실행 + 단계별 에러 정책 + alert 트리거.

**Stories**: US-005 (스케줄 실행)

**Note**: 딜리버리 순서상 u4(notifier)보다 먼저 만들지만 unit ID는 컴포넌트와 1:1 유지를 위해 u5로 표기.

**Module path**: `src/investo/orchestrator/`
- `pipeline.py` — `run_pipeline`, `_stage_collect`, `_stage_generate`, `_stage_publish`, `_stage_notify_briefing`
- `date_resolution.py` — `resolve_target_date`
- `__main__.py` — `main()` entrypoint (`python -m investo`)
- `__init__.py` — exports

**Tests**: `tests/unit/orchestrator/`
- date_resolution 평일/토요일/수동 시나리오
- 각 _stage 함수의 happy/failure path
- run_pipeline의 graceful degradation (stage 별 mocked 실패 주입)

**Integration test**: `tests/integration/test_pipeline.py`
- 모든 외부 호출 mock + run_pipeline 전체 수행
- Result.status SUCCESS/PARTIAL/FAILED 케이스 각각

**Definition of Done**:
- [ ] `python -m investo`로 entrypoint 동작 (env 미설정 시 명시적 에러)
- [ ] Q9=B graceful degradation 정책 모두 구현 + 테스트
- [ ] resolve_target_date 평일·토요일 분기 검증
- [ ] integration test가 외부 호출 없이 전체 파이프라인 검증

---

## u4: `notifier` — Notifier (BriefingPublisher + OperatorAlerter)

**Purpose**: 텔레그램 분배. 공개 채널과 운영자 1:1 chat을 별도 클래스로 분리.

**Stories**: US-004 (공개 채널), US-007 (운영자 1:1)

**Module path**: `src/investo/notifier/`
- `summary.py` — `build_summary` (4096자 한도)
- `briefing_publisher.py` — `BriefingPublisher` 클래스
- `operator_alerter.py` — `OperatorAlerter` 클래스
- `_telegram.py` — 공통 HTTP 호출 (httpx) — internal helper

**Tests**: `tests/unit/notifier/`
- httpx mock으로 Telegram Bot API 호출 검증
- 4096자 초과 시 truncation 동작
- send/alert 모두 non-raising (실패는 `SendResult.ok=False`)
- 시크릿/PII 노출 방지 검증 (시황 본문 패턴 매칭)

**Definition of Done**:
- [ ] BriefingPublisher가 공개 채널에만 발송 (channel ID 분리 검증)
- [ ] OperatorAlerter가 운영자 chat에만 발송
- [ ] 두 클래스가 같은 발송 경로 공유 안 함 (constructor 파라미터로 분리)
- [ ] HTTP 실패 시 SendResult로 반환 (raise 안 함)
- [ ] 본문 길이 한도 / parse_mode / URL 포함 검증

---

## u6: `infra/CI` — GitHub Actions + MkDocs + Pages

**Purpose**: 인프라/배포 단위. Python 코드는 없고 YAML/설정만.

**Stories**: US-005 (cron), US-003 (Pages 호스팅)

**Paths**:
- `.github/workflows/daily-briefing.yml` — cron + workflow_dispatch + `python -m investo` step
- `.github/workflows/pages.yml` — markdown commit 후 mkdocs build + actions/deploy-pages 트리거
- `mkdocs.yml` — 사이트 설정 (테마, 네비, archive plugin 설정)
- `docs/index.md`, `docs/about.md` — landing 페이지 등 (MkDocs source)

**Tests**: workflow는 직접 자동화 테스트 어려움. 검증:
- workflow_dispatch로 수동 실행 후 output 확인
- mkdocs build를 로컬에서 검증
- 첫 cron 실행을 임시로 가까운 시각으로 잡고 dry-run

**Definition of Done**:
- [ ] cron이 평일 KST 07:00 (UTC 22:00 전일) + 토 09:00에 실행
- [ ] `python -m investo`가 GitHub Secrets로 인증되어 동작
- [ ] commit 후 자동으로 Pages 빌드/배포

---

## u7: `segmented-briefing` — Domestic / US / Crypto Briefing Split

**Purpose**: 기존 단일 통합 시황을 국내 증시, 미국 증시, 크립토 세그먼트로 분리한다. 수집 소스의 편향이나 특정 시장의 강한 이슈가 전체 시황을 지배하지 않도록 세그먼트별 입력 필터링, 생성, 게시 URL, 텔레그램 요약을 명확히 한다.

**Stories**: FR-008 (세그먼트별 시황 생성), FR-002/003/004 extension

**Module path**:
- `src/investo/briefing/` — 세그먼트별 입력 분리와 LLM prompt 계약 확장
- `src/investo/orchestrator/` — 세그먼트별 generate/publish/notify orchestration
- `src/investo/publisher/` — archive path 확장 또는 세그먼트 path helper
- `src/investo/notifier/` — 세그먼트 링크/요약 포함 메시지

**Tests**:
- `tests/unit/briefing/` — 세그먼트 분류/필터링과 prompt shape
- `tests/unit/orchestrator/` — 세그먼트별 실패/부분 성공 routing
- `tests/integration/test_pipeline.py` — 세 브리핑 archive + Telegram 링크 검증

**Definition of Done**:
- [ ] 한 번의 daily run에서 국내 증시, 미국 증시, 크립토 세그먼트를 생성한다.
- [ ] 각 세그먼트가 독립 markdown과 URL을 가진다.
- [ ] 세그먼트별 핵심 데이터가 부족하면 다른 시장 뉴스로 대체하지 않고 데이터 부족을 명시한다.
- [ ] 텔레그램 메시지에 세 세그먼트 요약과 상세 링크가 포함된다.
- [ ] 기존 disclaimer, leak guard, Claude Code CLI only, retry/budget 계약을 유지한다.
- [ ] 빌드 실패 시 기존 사이트 유지

---

## u8: `market-aware-source-window` — Segment Source Coverage Correction

**Purpose**: u7 세그먼트 생성 후속 보정. 같은 `target_date`라도 국내/미국/크립토 소스의 "당일" 기준이 다르므로, 소스 수집 window를 시장별 시간대로 분리해 미국 증시와 크립토 세그먼트가 KST cutoff 이후 데이터 때문에 비지 않도록 한다.

**Stories**: FR-001 (데이터 수집), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `src/investo/sources/_window.py` — 시장별 local-date window 생성 지원
- `src/investo/sources/aggregator.py` — adapter source name 기반 window 선택

**Tests**:
- `tests/unit/sources/test_window.py` — New York / UTC local-date window anchor cases
- `tests/unit/sources/test_aggregator.py` — US/crypto adapters receive market-appropriate windows and keep same-day post-KST-cutoff items

**Definition of Done**:
- [x] 국내 소스는 기존 KST window를 유지한다.
- [x] 미국 증시/매크로/SEC/Nasdaq/FOMC/Yahoo/CNBC 소스는 America/New_York 기준 target date window를 받는다.
- [x] 크립토 소스는 UTC 기준 target date window를 받는다.
- [x] 2026-05-06 18:00 UTC처럼 KST window 밖이지만 미국/UTC 시장 당일인 데이터가 수집 결과에서 빠지지 않는다.
- [x] 기존 u7 routing/generation 테스트가 green이다.

---

## u9: `briefing-reader-experience` — Reader-Facing Briefing Quality

**Purpose**: 생성된 시황을 사용자가 실제로 읽을 수 있는 뉴스레터형 산출물로 개선한다. 세그먼트 문서 상단에 제목/세그먼트 이동/3줄 브리핑을 추가하고, 데이터가 전혀 없는 세그먼트는 반복적인 "데이터 부족" 6섹션 대신 짧은 수집 상태 문서로 발행한다.

**Stories**: FR-002 (AI 시황 작성), FR-003 (정적 웹 게시), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `src/investo/briefing/prompts.py` — 서사형 작성, 출처 링크, 과장 표현 억제, 종목 그룹화 규칙
- `src/investo/briefing/pipeline.py` — 세그먼트 상단 UX, 데이터 공백 fallback, source URL 전달

**Tests**:
- `tests/unit/briefing/test_prompts.py` — reader-experience prompt rules
- `tests/unit/briefing/test_budget_happy_path.py` — 세그먼트 H1/3줄 브리핑과 zero-item fallback
- `tests/unit/briefing/test_pipeline_unit.py` — source URL이 Stage 2 prompt에 전달되는지 검증

**Definition of Done**:
- [x] 세그먼트 문서가 H1, 세그먼트 이동 링크, 오늘의 결론/핵심 동인/주의할 점을 가진다.
- [x] zero-item 세그먼트는 Claude 호출 없이 짧고 정직한 수집 상태 문서를 생성한다.
- [x] Stage 2 prompt에 source URL을 전달해 주요 주장에 출처 링크를 붙일 수 있게 한다.
- [x] Prompt는 나열형 bullet dump 대신 서사형 뉴스레터 톤, 과장 표현 억제, 주요 종목 그룹화를 요구한다.

---

## u10: `source-coverage-diagnostics` — Per-Source Collection Observability

**Purpose**: GitHub Actions 로그에서 소스별 성공/실패뿐 아니라 실제 반환 item 수와 적용된 market window를 확인할 수 있게 한다. 미국/크립토 세그먼트 품질 개선 과정에서 "HTTP 200인데 0건"과 "소스 실패"를 구분하기 위한 운영 진단 단위다.

**Stories**: FR-001 (데이터 수집), FR-008 (세그먼트별 시황 생성), FR-007 (운영자 실패 진단)

**Module path**:
- `src/investo/sources/aggregator.py` — source별 success count/window structured log

**Tests**:
- `tests/unit/sources/test_aggregator.py` — success count, zero-item success, window fields

**Definition of Done**:
- [x] 성공한 adapter마다 `source returned` INFO 로그를 남긴다.
- [x] 로그에 `source_name`, `category`, `item_count`, `window_start_utc`, `window_end_utc`가 포함된다.
- [x] 0건 성공도 실패와 구분되어 로그에 남는다.
- [x] 기존 failure isolation과 structured warning contract를 유지한다.

---

## u14: `summary-quality-contract` — Stable Reader Summary Header

**Purpose**: 세그먼트 문서 상단의 "오늘의 결론 / 핵심 동인 / 주의할 점"을 본문 markdown에서 거칠게 추출하지 않고, 독립적으로 검증 가능한 요약 계약으로 만든다. 현재 샘플에서 `주의할 점: 1.` 또는 markdown 강조가 잘린 문장이 노출되는 문제를 제거한다.

**Stories**: FR-002 (AI 시황 작성), FR-003 (정적 웹 게시), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `src/investo/briefing/pipeline.py` — summary header generation and validation
- `src/investo/briefing/prompts.py` — optional structured summary prompt contract
- `src/investo/notifier/summary.py` — Telegram one-line summary source reuse, if applicable

**Tests**:
- `tests/unit/briefing/` — markdown stripping, numbered-list handling, malformed-summary fallback
- `tests/unit/notifier/` — segmented summary uses stable per-segment summary text

**Definition of Done**:
- [ ] Header summary no longer emits bare list markers such as `1.` as caution text.
- [ ] Markdown emphasis/link syntax is stripped or rendered cleanly in header fields.
- [ ] `conclusion`, `driver`, and `risk/caution` are bounded, non-empty, and independently testable.
- [ ] Data-limited segments produce conservative summary fields without directional overstatement.
- [ ] Existing 7-section markdown and disclaimer contracts remain unchanged.

---

## u15: `coverage-confidence-badges` — Data Coverage and Confidence UX

**Purpose**: 독자가 각 세그먼트의 신뢰도를 즉시 판단할 수 있도록, 수집 커버리지와 결측 카테고리를 briefing 산출물에 노출한다. "데이터 부족"과 "강한 시장 해석"이 한 문서 안에서 충돌하지 않도록 생성 전/후 품질 게이트를 강화한다.

**Stories**: FR-001 (데이터 수집), FR-002 (AI 시황 작성), FR-008 (세그먼트별 시황 생성), NFR-003 (Reliability)

**Module path**:
- `src/investo/sources/aggregator.py` or new diagnostics model — source/category item counts
- `src/investo/briefing/segments.py` — segment coverage thresholds and required categories
- `src/investo/briefing/pipeline.py` — render coverage badge/table and enforce data-limited wording

**Tests**:
- `tests/unit/sources/` — source success vs zero-result coverage summary
- `tests/unit/briefing/` — normal/partial/insufficient coverage rendering and prompt constraints
- `tests/integration/test_pipeline.py` — archived briefing includes coverage status per segment

**Definition of Done**:
- [ ] Each segment exposes `normal`, `partial`, or `insufficient` coverage status.
- [ ] Briefing top matter lists successful sources and missing core categories.
- [ ] `partial` and `insufficient` segments use conservative wording and do not imply full-market coverage.
- [ ] Coverage status is available to Telegram summary generation.
- [ ] Source failure and HTTP-success-zero-items remain distinguishable.

---

## u16: `public-site-discovery` — Latest Briefing and Archive Navigation

**Purpose**: GitHub Pages 독자와 공유받은 사용자가 최신 세그먼트 시황을 바로 찾을 수 있게 홈/About/Archive를 현재 세그먼트 구조와 동기화한다. 오래된 단일 archive 경로 설명과 FOMC-only source 설명의 드리프트를 제거한다.

**Stories**: FR-003 (정적 웹 게시), FR-006 (영구 이력 보관), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `site_docs/index.md` — latest briefing entry point
- `site_docs/about.md` — current source coverage and limitations
- `archive/index.md` or publisher helper — latest date and segment links
- `src/investo/publisher/` — optional archive index update during publish

**Tests**:
- `tests/unit/publisher/` — archive index/latest-link generation if automated
- `uv run mkdocs build --strict` — site nav and links validate

**Definition of Done**:
- [ ] Archive landing page reflects `archive/{segment}/YYYY/MM/YYYY-MM-DD.md`.
- [ ] Latest domestic/us/crypto briefing links are visible without relying on sidebar discovery.
- [ ] Home and About describe all three segments and current data-source coverage accurately.
- [ ] Legacy single-briefing archive remains discoverable.
- [ ] MkDocs strict build passes with the updated navigation/content.

---

## u17: `operations-visibility` — Partial Success and Run Diagnostics

**Purpose**: 운영자 관점에서 "게시 성공, 공개 Telegram 알림 실패" 같은 partial 상태가 조용히 묻히지 않게 한다. GitHub Actions 초록색 run에서도 운영자가 필요한 실패/진단 정보를 확인할 수 있도록 summary 또는 artifact를 남긴다.

**Stories**: FR-004 (텔레그램 시황 채널 알림), FR-007 (운영자 실패 알림), FR-005 (스케줄 실행), NFR-003 (Reliability)

**Module path**:
- `src/investo/orchestrator/pipeline.py` — partial status metadata
- `src/investo/__main__.py` — GitHub Step Summary or diagnostics output
- `src/investo/notifier/operator_alerter.py` — optional partial alert path
- `scripts/` — optional `investo doctor` or diagnostic helper

**Tests**:
- `tests/unit/orchestrator/` — partial notify failure carries actionable metadata
- `tests/unit/notifier/` — operator partial alert formatting, if implemented
- `tests/unit/orchestrator/` or script tests — diagnostics summary output

**Definition of Done**:
- [ ] Public-channel notification failure is visible to the operator even when publishing succeeds.
- [ ] Pipeline result exposes stage timings, briefing URLs, and notify error context.
- [ ] GitHub Actions can surface a concise run summary without scraping logs.
- [ ] Existing successful and failed pipeline exit-code contracts remain intentional and documented.
- [ ] Sensitive tokens and chat IDs are redacted in operator-facing diagnostics.

---

## u18: `watchlist-relevance` — Personal Relevance Layer

**Purpose**: Investo를 일반 시장 요약에서 1인 투자자의 실제 아침 루틴으로 끌어올린다. 관심 티커/코인/섹터/키워드 설정을 받아 "내 관심 자산에 미치는 영향"을 우선 표시한다.

**Stories**: FR-002 (AI 시황 작성), FR-004 (텔레그램 시황 채널 알림), FR-008 (세그먼트별 시황 생성), future extension from IDEA.md (포트폴리오/기업 분석 토대)

**Module path**:
- `src/investo/briefing/` — watchlist context injection and relevance summary
- `src/investo/models/` — optional watchlist config model
- `src/investo/notifier/summary.py` — watchlist-impact line in Telegram summary
- `config/` or repository-root config file — non-secret watchlist settings

**Tests**:
- `tests/unit/briefing/` — watchlist matching, prompt context, no-match fallback
- `tests/unit/notifier/` — Telegram summary includes watchlist impact without exceeding limits
- `tests/unit/models/` — watchlist config validation if a model is introduced

**Definition of Done**:
- [ ] A simple non-secret watchlist config can define tickers, crypto assets, sectors, and keywords.
- [ ] Briefing generation highlights relevant collected items before generic market narrative.
- [ ] No-match days are handled cleanly without inventing impact.
- [ ] Telegram summary can surface the most important watchlist impact or state that none was found.
- [ ] The feature does not introduce accounts, paid data sources, automatic trading, or portfolio accounting.

---

## Code Organization Strategy

### Repository Layout (per Q3=A)

```
investo/                           # repo root
├── pyproject.toml
├── README.md
├── CLAUDE.md                      # (init-project Stage 2에서 생성)
├── mkdocs.yml
├── archive/                       # 시황 markdown (run-time output)
│   └── YYYY/MM/YYYY-MM-DD.md
├── docs/                          # mkdocs source (사이트의 정적 페이지)
│   ├── index.md
│   └── about.md
│   # 주의: aidlc 산출물용 docs/와는 별개. 충돌 시 /site-docs/로 이름 변경 검토
├── src/
│   └── investo/
│       ├── __init__.py
│       ├── __main__.py
│       ├── models/
│       ├── sources/
│       ├── briefing/
│       ├── publisher/
│       ├── notifier/
│       └── orchestrator/
├── tests/
│   ├── unit/
│   │   ├── models/
│   │   ├── sources/
│   │   ├── briefing/
│   │   ├── publisher/
│   │   ├── notifier/
│   │   └── orchestrator/
│   ├── integration/
│   │   └── test_pipeline.py
│   └── fixtures/
│       ├── llm/                   # Claude Code record/replay
│       └── api/                   # 외부 API 응답 샘플
├── .github/
│   └── workflows/
│       ├── daily-briefing.yml
│       └── pages.yml
└── (기존 그대로)
    ├── aidlc-docs/
    ├── aidlc-workflows/
    ├── docs/                      # AIDLC 문서. mkdocs source(/docs)와 충돌 가능
    │                              # → 충돌 시 mkdocs source를 site-docs/로 옮길 것
    ├── examples/
    └── IDEA.md
```

### Naming Convention
- Python 패키지/모듈: `snake_case`
- 클래스: `PascalCase`
- 모듈 ID는 컴포넌트 ID와 일치 (`sources` ↔ u1, etc.)

### Module Boundary Rule (Q4=A — Convention Only)
- `orchestrator`만 `sources / briefing / publisher / notifier`를 import 가능
- 나머지 4 unit은 서로 import 금지 (오직 `models`만 공통 의존)
- 코드리뷰 + 디렉토리 구조로 강제. import-linter 미도입.
- 위반은 향후 PR 검토 시 차단; 패턴이 반복되면 import-linter 도입 검토 (현재 Open Question)

### Dependency Management (per docs/tech-env.md)
- `pyproject.toml` (PEP 621)
- `uv` 또는 `pip` + lock file
- core deps: `pydantic>=2`, `httpx`, `mkdocs-material`
- dev deps: `pytest`, `hypothesis`, `ruff`, `mypy`

---

## Test Strategy (Q5=A) — 단위 ↔ 단위별 테스트 매핑

| Unit | tests/unit/ subdir | Mocked externally | PBT applicable |
|------|--------------------|-------------------|----------------|
| models | tests/unit/models | — | ✅ 직렬화 round-trip |
| u1 sources | tests/unit/sources | httpx, 외부 API | partial (정규화 함수) |
| u2 briefing | tests/unit/briefing | claude CLI (subprocess) | partial (prompt builder, append_disclaimer) |
| u3 publisher | tests/unit/publisher | git CLI, 파일시스템 | — |
| u4 notifier | tests/unit/notifier | httpx, Telegram API | partial (build_summary 한도) |
| u5 orchestrator | tests/unit/orchestrator | 모든 다른 unit | — |
| u6 infra | (workflow 수동 검증) | — | — |
| (cross-unit) | tests/integration/test_pipeline.py | 모든 외부 호출 | — |

LLM 호출은 `tests/fixtures/llm/`의 record/replay 데이터로 결정성 보장.
