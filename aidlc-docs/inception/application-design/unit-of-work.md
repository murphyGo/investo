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

## u19: `briefing-visual-assets` — Data-Derived Briefing Visuals

**Purpose**: 세그먼트별 시황에 데이터 신뢰도, 시장 스냅샷, 가격 스냅샷, 관심목록 관련성 이미지를 붙여 공개 아카이브의 첫 화면 이해도를 높인다.

**Stories**: FR-002 (AI 시황 작성), FR-003 (정적 웹 게시), FR-004 (시황 채널 알림), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `src/investo/visuals/` — visual card contracts, SVG renderer, optional OpenAI/external image handlers
- `src/investo/orchestrator/pipeline.py` — visual asset preparation and publish staging
- `archive/{segment}/YYYY/MM/*.assets/` — generated markdown-adjacent visual assets

**Tests**:
- `tests/unit/visuals/` — path, card, renderer, asset, OpenAI, external image policy contracts
- `tests/integration/test_pipeline.py` — segmented publish stages markdown plus generated assets

**Definition of Done**:
- [x] Data-derived SVG cards can be generated for each segment.
- [x] Visual assets are stored beside each segment markdown and linked with relative paths.
- [x] Visual generation failure falls back to text-only publish without blocking notification.
- [x] External images require explicit license metadata and safe host policy.

---

## u20: `archive-trust-and-latest-index` — Archive Trust and Latest Discovery

**Purpose**: 사용자가 public site 첫 화면과 archive index에서 최신 segmented briefing을 신뢰하고 빠르게 찾을 수 있게 한다. 레거시 단일 시황은 최신 탐색 경로와 분리하거나 저신뢰/구버전 맥락을 명시한다.

**Stories**: FR-003 (정적 웹 게시), FR-006 (영구 보관), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `src/investo/publisher/` or `src/investo/site/` — latest index update helper if introduced
- `site_docs/index.md` — latest segmented briefing discovery surface
- `archive/index.md` — archive landing page and legacy briefing treatment
- `src/investo/orchestrator/pipeline.py` — optional publish-stage hook

**Tests**:
- `tests/unit/publisher/` or `tests/unit/site/` — latest archive index update behavior
- `tests/integration/test_pipeline.py` — publish flow updates discoverability files when applicable
- `uv run mkdocs build --strict`

**Definition of Done**:
- [ ] Latest domestic/us/crypto links are generated or updated automatically.
- [ ] Legacy single briefing archive entries are clearly labeled as legacy or moved out of the primary path.
- [ ] Stale hard-coded latest dates are prevented by tests.
- [ ] MkDocs strict build remains green.

---

## u21: `summary-quality-gate` — Publish-Time Summary Quality Gate

**Purpose**: 시황 첫 화면의 `오늘의 결론`, `핵심 동인`, `주의할 점`이 깨진 markdown/list artifact나 빈 문구로 게시되지 않도록 publish 전 검증한다.

**Stories**: FR-002 (AI 시황 작성), FR-003 (정적 웹 게시), FR-008 (세그먼트별 시황 생성), NFR-003 (graceful degradation)

**Module path**:
- `src/investo/briefing/` — summary quality validation helpers
- `src/investo/orchestrator/pipeline.py` — validation hook before publish
- `src/investo/notifier/summary.py` — clean summary reuse if needed

**Tests**:
- `tests/unit/briefing/` — broken first-viewport summary cases
- `tests/unit/orchestrator/` — publish blocked or partial behavior for invalid summaries
- `tests/integration/test_pipeline.py` — valid segmented briefings remain publishable

**Definition of Done**:
- [ ] Broken summary lines such as `주의할 점: 1.` are rejected before publish.
- [ ] Truncated markdown/bold/link artifacts in first-viewport summary are rejected or cleaned.
- [ ] Data-limited fallback summaries remain allowed when intentionally conservative.
- [ ] Validation failure produces an operator-visible stage error without publishing broken markdown.

---

## u22: `source-coverage-transparency` — Source Coverage Transparency

**Purpose**: 사용자가 `정상/부분/부족` 상태의 이유를 이해할 수 있도록 세그먼트별 source 수집 상태, 0건, 실패, 누락 category를 본문과 카드에 더 투명하게 표시한다.

**Stories**: FR-001 (데이터 수집), FR-002 (AI 시황 작성), FR-008 (세그먼트별 시황 생성), NFR-003 (graceful degradation)

**Module path**:
- `src/investo/sources/aggregator.py` — source collection diagnostics surface if persisted
- `src/investo/briefing/segments.py` — coverage reason codes
- `src/investo/briefing/pipeline.py` — reader-facing coverage table/callout
- `src/investo/visuals/` — data-confidence card expansion

**Tests**:
- `tests/unit/sources/` — source status aggregation
- `tests/unit/briefing/` — coverage reason rendering
- `tests/unit/visuals/` — source names/reasons in confidence card

**Definition of Done**:
- [ ] Segment coverage exposes reason codes such as missing price/news, source failed, and zero items.
- [ ] Reader-facing markdown explains why a segment is partial or insufficient.
- [ ] Data confidence visual card includes source names or reason categories.
- [ ] Sensitive source errors are redacted before public rendering.

---

## u23: `notification-actionability` — Actionable Segmented Alerts

**Purpose**: 공개 알림에서 국내증시, 미국증시, 크립토가 더 빠르게 구분되고, 각 세그먼트 요약 바로 옆에서 상세 링크와 데이터 상태를 확인할 수 있게 한다. 알림 실패가 부분 성공으로 묻히지 않도록 운영자 가시성도 강화한다.

**Stories**: FR-004 (시황 채널 알림), FR-007 (운영자 알림), FR-008 (세그먼트별 시황 생성), NFR-003 (graceful degradation)

**Module path**:
- `src/investo/notifier/summary.py` — segmented summary layout
- `src/investo/notifier/briefing_publisher.py` — markdown/plain fallback behavior if needed
- `src/investo/orchestrator/pipeline.py` — partial notification failure visibility
- `tests/unit/notifier/`, `tests/unit/orchestrator/`

**Tests**:
- `tests/unit/notifier/test_summary.py` — segment block, inline link, status tag, length budget
- `tests/unit/notifier/test_briefing_publisher.py` — markdown/plain fallback preserves readability
- `tests/unit/orchestrator/test_run_pipeline.py` or `test_stage_notify_briefing.py` — notification failure diagnostics

**Definition of Done**:
- [ ] Each segment alert block includes a compact status tag and inline detail link.
- [ ] The footer/link structure remains readable within Telegram limits.
- [ ] Markdown parse fallback does not expose raw formatting artifacts.
- [ ] Notification failure in an otherwise successful publish is operator-visible.

---

## u24: `visual-provenance-and-layout` — Visual Provenance and Reader Layout

**Purpose**: AI/external/SVG visual assets의 출처와 생성 방식을 보존하고, 첫 화면에서는 핵심 hero visual만 보여 사용자가 본문에 빠르게 접근할 수 있게 한다.

**Stories**: FR-002 (AI 시황 작성), FR-003 (정적 웹 게시), FR-008 (세그먼트별 시황 생성), NFR-007 (secret/provenance safety)

**Module path**:
- `src/investo/visuals/` — manifest generation, image validation, layout placement rules
- `archive/{segment}/YYYY/MM/*.assets/` — visual provenance manifest storage
- `src/investo/briefing/` or `src/investo/visuals/assets.py` — caption/link placement

**Tests**:
- `tests/unit/visuals/` — manifest, caption, image dimension/signature validation
- `tests/integration/test_pipeline.py` — generated manifests staged with assets
- `uv run mkdocs build --strict`

**Definition of Done**:
- [ ] External/AI images write provenance metadata without secrets.
- [ ] Public markdown shows concise image provenance captions.
- [ ] First viewport prefers one hero visual and moves secondary cards closer to relevant sections.
- [ ] Corrupt or dimension-invalid images are rejected before publish.

---

## Wave 8 Quality Follow-Up Units

The 2026-05-13 ten-agent review of generated market briefings produced additional quality units after removing work already covered by u51, u52, and u53:

- Excluded as u51 scope: TL;DR block, anchor table, H3 conversion, bold-number scanability, glossary dedupe, and non-blocking action-ratio diagnostics.
- Excluded as u52 scope: day-over-day carryover, prior event lifecycle, resolved/unresolved table, and prior briefing bridge.
- Excluded as u53 scope: domestic foreign/institutional flow data and US sector/macro ETF source expansion.

### u54: `source-status-severity-and-quality-kpi` — Reader-Truthful Source Status

**Purpose**: `데이터 상태: 정상`이 실패/0건 소스를 덮어쓰지 않게 하고, quality dashboard가 실제 source coverage risk를 설명하도록 한다.

**Stories**: FR-001 (데이터 수집), FR-002 (AI 시황 작성), FR-003 (정적 웹 게시), FR-008 (세그먼트별 시황 생성), NFR-003 (graceful degradation)

**Module path**:
- `src/investo/briefing/segments.py` — coverage severity model and reason mapping
- `src/investo/briefing/pipeline.py` — first-viewport status rendering
- `src/investo/briefing/quality_eval.py` — KPI computation
- `src/investo/publisher/site_index.py` — quality page rendering
- `src/investo/visuals/render.py` — data-confidence card text, if needed

**Tests**:
- `tests/unit/briefing/` — normal/partial/limited severity and source count breakdown
- `tests/unit/publisher/` — quality page denominator and failure summary rendering
- `tests/unit/visuals/` — card status text remains concise and source-safe

**Definition of Done**:
- [ ] Source status distinguishes target/succeeded/zero/failed/body-used counts.
- [ ] Segment status labels use `정상/부분/제한/실패` semantics rather than hiding failures under `정상`.
- [ ] Core source failures downgrade reader-visible status when they affect a segment's conclusion.
- [ ] Quality page shows observed runs, failed sources, zero-item sources, and core-missing counts.
- [ ] Trace/collapsed source diagnostics can explain excluded or failed sources without leaking secrets.

### u55: `numeric-freshness-and-market-fact-gates` — Numeric Verification and Staleness Gates

**Purpose**: 핵심 지수/가격/날짜/방향성 수치가 source-backed인지 검증하고, stale briefing을 형식상 성공으로 보여주지 않게 한다.

**Stories**: FR-001, FR-002, FR-003, FR-006, FR-008, NFR-003

**Module path**:
- `src/investo/briefing/numeric_self_check.py` — claim/source numeric comparison
- `src/investo/briefing/market_anchor.py` — canonical market fact inputs
- `src/investo/orchestrator/pipeline.py` — publish/dry-run warning and failure policy
- `src/investo/publisher/site_index.py` — freshness/staleness marker

**Tests**:
- `tests/unit/briefing/` — source-backed numeric claims, tolerance, and date-token anomaly cases
- `tests/unit/orchestrator/` — stale archive/quality page detection
- `tests/unit/publisher/` — freshness marker rendering

**Definition of Done**:
- [ ] Core market claims require a source-backed numeric anchor or explicit `확인 필요` downgrade.
- [ ] Numeric quality separates `number present` from `number verified`.
- [ ] Date-token corruption such as `5/65/7` is detected before publish.
- [ ] Archive/quality freshness is measured against segment market calendars and operator policy.
- [ ] Stale or unverifiable facts are visible in status/KPI output without blocking unrelated segments unnecessarily.

### u56: `compliance-language-and-observational-tags` — Compliance Language Gate

**Purpose**: 시황이 투자 자문처럼 읽히지 않도록 행동 지시형 문구, 보장형 표현, 과도한 방향성 태그를 관찰형 언어로 제한한다.

**Stories**: FR-002, FR-003, FR-004, FR-008, NFR-004

**Module path**:
- `src/investo/briefing/prompts.py` — Stage 2 language rules
- `src/investo/briefing/action_tag.py` — observational tag vocabulary
- `src/investo/briefing/summary_quality.py` or new `compliance_language.py` — language gate
- `src/investo/publisher/verifier.py` — first-viewport compliance checks
- `src/investo/notifier/summary.py` — notification-safe wording

**Tests**:
- `tests/unit/briefing/` — blocked and softened phrases
- `tests/unit/publisher/` — first-viewport short disclaimer and compliance gate
- `tests/unit/notifier/` — Telegram summary does not surface high-risk action language

**Definition of Done**:
- [ ] Prompt no longer encourages `매수 검토/비중 축소/손절/헤지 확대/목표가` style action instructions.
- [ ] Publish gate blocks or warns on high-risk advisory phrases.
- [ ] `[강세]/[약세]` first-viewport tags are replaced or softened into observation labels.
- [ ] A short information-only disclaimer appears within the first viewport.
- [ ] Existing canonical disclaimer remains enforced at the document end.

### u57: `segment-narrative-scope-and-time-reconciliation` — Segment Scope and Time-State Reconciliation

**Purpose**: 국내/미국/크립토 세그먼트가 서로 다른 장중/마감 시점을 섞어 상충되는 내러티브를 만들지 않게 하고, 세그먼트별 핵심 소재 범위를 유지한다.

**Stories**: FR-002, FR-008, NFR-003

**Module path**:
- `src/investo/briefing/segments.py` — segment scope rules and shared macro classification
- `src/investo/briefing/prompts.py` — source/time-state wording rules
- `src/investo/briefing/pipeline.py` — cross-segment reconciliation context
- `src/investo/orchestrator/pipeline.py` — same-run segment context wiring

**Tests**:
- `tests/unit/briefing/` — domestic segment does not promote unrelated overseas open-state news as a core issue
- `tests/unit/briefing/` — `장중/출발/마감` wording reconciliation
- `tests/integration/` — same-date segmented bundle remains internally consistent

**Definition of Done**:
- [ ] Segment prompts rank native market facts above cross-market background.
- [ ] Shared macro facts are summarized once and reinterpreted per segment without duplicative overreach.
- [ ] Open/close/intraday states are labeled and reconciled when another segment has the final close.
- [ ] Domestic watchlist impact does not surface unrelated global tickers unless a domestic linkage is explicit.
- [ ] Cross-segment links are added only when they reduce duplication or clarify scope.

---

## Wave 9 Official Source Coverage Units

The 2026-05-14 CLARITY Act markup miss showed that crypto market briefings need official U.S. legislative and committee sources, not only generic market/news feeds. Feasibility was checked against official sources before creating this unit:

- Congress.gov API: official v3 API is available for machine-readable bill data, but requires an API key.
- Senate Banking Committee: official hearing/markup/news pages expose the CLARITY markup notice and related bill-text release; RSS was not confirmed as a stable path, so the safe scope is fixture-backed official HTML parsing only.
- House Financial Services Committee: official news listing and `news/rss.aspx` endpoint are reachable; emit only crypto policy items after keyword filtering.

### u58: `crypto-regulation-policy-sources` — Official U.S. Crypto Policy Source Coverage

**Purpose**: CLARITY Act markup 같은 시장 구조/스테이블코인/디지털자산 입법 이벤트가 크립토 시황 후보에서 누락되지 않도록 공식 U.S. policy source 어댑터와 crypto regulation priority signal을 추가한다.

**Stories**: FR-001 (데이터 수집), FR-002 (AI 시황 작성), FR-008 (세그먼트별 시황 생성), NFR-003 (graceful degradation), R10 (external fixture), R13 (secret hygiene)

**Module path**:
- `src/investo/sources/official_policy.py` or source-specific modules under `src/investo/sources/` — Congress.gov, Senate Banking, House Financial Services adapters
- `src/investo/sources/aggregator.py` — optional-key graceful degradation and source outcome reporting
- `src/investo/briefing/segments.py` — crypto policy routing/priority terms
- `src/investo/briefing/prompts.py` — Stage 1/2 policy-event importance guidance
- `src/investo/orchestrator/pipeline.py` — candidate cap preservation for official policy items, if needed

**Tests**:
- `tests/unit/sources/` — Congress.gov API fixture, Senate Banking HTML fixtures, House Financial Services RSS fixture, missing-key/403 graceful degradation
- `tests/unit/briefing/` — CLARITY/markup/digital asset policy items route to crypto and survive candidate caps
- `tests/integration/` — official policy item can become crypto §② core issue without BTC/ETH price-token dependence

**Definition of Done**:
- [x] Congress.gov adapter supports configured bills such as `119/hr/3633` and degrades cleanly when `CONGRESS_API_KEY` is absent or rejected.
- [x] Senate Banking adapter uses only official static HTML pages/listings with recorded fixtures; no unofficial endpoints or JS reverse-engineering.
- [x] House Financial Services adapter consumes official RSS/news output and filters to crypto/digital-asset policy terms before emission.
- [x] Official policy items emit sanitized metadata for bill id, committee, event type, and policy priority without leaking API keys.
- [x] Segment routing treats `CLARITY Act`, `digital asset market structure`, `stablecoin`, `committee markup`, `CFTC/SEC crypto jurisdiction`, and equivalent terms as strong crypto policy signals.
- [x] Candidate selection preserves official crypto-regulation items ahead of generic low-signal news caps.
- [x] Stage prompts allow a regulation/legislation event to become a core issue when it is market-structure relevant even without same-day price movement.
- [x] R10 fixtures cover success, empty, malformed, and auth/error paths for every new official source.

---

## Wave 10 Macro Quality Correction Units

The 2026-05-13 shared macro block exposed a deterministic evidence-selection defect: `customers` matched the bare case-insensitive `UST` regex and was rendered as `미 국채 수익률` evidence. This unit is intentionally narrower than u59. u59 owns first-class macro actual collection and lineage; u60 owns shared macro matcher correctness and representative evidence selection.

### u60: `shared-macro-evidence-hardening` — Source-Backed Shared Macro Evidence

**Purpose**: `## ⓪ 오늘의 매크로`가 임의 뉴스 제목의 부분 문자열을 UST/oil/FOMC evidence 로 오인하지 않도록, shared macro detection 을 source/category-aware deterministic matcher 로 강화한다.

**Stories**: FR-002 (AI 시황 작성), FR-008 (세그먼트별 시황 생성), FR-015 (shared macro evidence hardening), NFR-003 (deterministic graceful degradation), R13 (secret hygiene)

**Module path**:
- `src/investo/orchestrator/bundle_context.py` — `_detect_shared_macros`, UST/oil/FOMC matcher, representative evidence scoring
- `src/investo/publisher/shared_macro.py` — injection behavior should remain unchanged unless tests expose a direct issue
- `src/investo/briefing/segments.py` — routing reference only; do not edit in this unit. `treasury-rates` fan-out is preserved and `fred-macro` remains US-only.

**Tests**:
- `tests/unit/orchestrator/test_bundle_context.py` — `customers`/`trust`/`custody`/`dust` false positives rejected; `UST curve`, `DGS10`, `10Y Treasury yield`, and `미 국채 10년물 수익률` accepted
- `tests/unit/orchestrator/test_bundle_context.py` — `UST stablecoin collapse` / `UST depeg` false positives rejected; canonical `treasury-rates` / `fred-macro` evidence wins over earlier generic news
- `tests/integration/test_bundle_reconciliation.py` — `NormalizedItem` fixtures flow through `compute_bundle_context()` and reader-format injection; final markdown contains corrected macro evidence once and never contains the Immunefi/Code4rena title in the UST slot
- `tests/unit/publisher/test_shared_macro_block.py` — idempotent injection shape remains stable

**Definition of Done**:
- [x] `customers`, `trust`, `custody`, and `dust` do not match `ust_yield`.
- [x] `UST stablecoin collapse`, `UST depeg`, and `UST custody product` do not match `ust_yield` without rate/yield/curve/tenor context.
- [x] Real UST evidence from `treasury-rates` / `fred-macro` still matches.
- [x] `ust_yield` shared macro requires valid UST candidates in at least two routed segments and at least one canonical source candidate (`treasury-rates` or `fred-macro`).
- [x] `fred-macro` alone never creates a shared macro block or crypto fan-out.
- [x] Shared macro representative evidence is chosen by deterministic source/category/title specificity, not by first item order.
- [x] If only false-positive titles appear across segments, `shared_macro_block` is `None`.
- [x] If false-positive news appears before real UST evidence, the rendered `미 국채 수익률` line uses the real UST evidence.
- [x] Existing oil/FOMC shared macro happy paths remain green and boundary false positives are rejected.
- [x] No LLM call, network call, new paid source, or archive backfill is introduced.
- [x] R13-safe diagnostics for accepted/rejected/suppressed/selected candidates avoid raw metadata and secret-shaped values.

---

## Wave 11 Generated Briefing Quality Follow-up Units

The 2026-05-23 10-subagent review of the latest generated segmented briefings found that the remaining quality risk is no longer one isolated source bug. It is the combination of first-viewport formatting defects, contradictory quality/status surfaces, silent partial-bundle navigation, weak watchlist/entity matching, and the lack of a fast offline artifact replay loop.

These units intentionally avoid duplicating closed u54/u57/u60 implementation scope. They focus on publish-time regression gates, reader-facing status reconciliation, partial-bundle UX, watchlist actionability, and a repeatable replay harness.

### u61: `first-viewport-summary-gate-v2` — Summary Malformation Regression Gate

**Purpose**: Block or deterministically repair malformed first-viewport summaries such as heading leakage, truncated sentences, stray generation residue, and broken emphasis before archive or Telegram publication.

**Stories**: FR-002 (AI 시황 작성), FR-008 (세그먼트별 시황 생성), FR-009 (reader-facing format), NFR-003 (graceful degradation)

**Module path**:
- `src/investo/briefing/pipeline.py` — summary extraction/cleanup
- `src/investo/briefing/summary_quality.py` — validation contract
- `src/investo/publisher/reader_format.py` — post-format gate
- `src/investo/notifier/summary.py` — reuse cleaned summaries

**Definition of Done**:
- [x] `###` heading leakage, stray terminal tokens, malformed bold, and non-terminal truncation are pinned by tests.
- [x] Archive and Telegram first-viewport summaries share one clean contract.
- [x] Invalid summaries fail publish or use a deterministic compliance-safe fallback.

### u62: `quality-status-publish-reconciliation` — Canonical Quality Snapshot

**Purpose**: Make segment markdown, `quality_history.jsonl`, `site_docs/quality.md`, and `archive/index.md` derive from one canonical run snapshot so `본문 사용`, failed source counts, and worst status cannot contradict each other.

**Stories**: FR-001 (데이터 수집), FR-003 (정적 게시), FR-006 (보관), FR-010 (source-status severity/KPI)

**Module path**:
- `src/investo/briefing/segments.py` / `coverage.py` — segment coverage counts
- `src/investo/publisher/quality_history.py` — same-day worst-wins
- `src/investo/publisher/site_index.py` — quality/index rendering
- `src/investo/visuals/` — quality chart bounds if needed

**Definition of Done**:
- [x] Public status surfaces agree for normal/partial/limited/failed cases.
- [x] `본문 사용 0` is not rendered when the count is unknown or body evidence exists.
- [x] Date-level status uses worst segment status and quality SVG labels are not clipped.

### u63: `partial-bundle-navigation-and-absence-state` — Explicit Missing Segment UX

**Purpose**: When a date has only some generated segments, latest-bundle surfaces should show generated segments, missing segments, and the latest fallback date instead of silently omitting the absent segment.

**Stories**: FR-003 (정적 게시), FR-006 (보관), FR-008 (세그먼트별 시황 생성)

**Module path**:
- `src/investo/publisher/site_index.py` — archive/latest bundle blocks
- `src/investo/publisher/reader_format.py` or segment nav helper — per-segment navigation
- `src/investo/orchestrator/pipeline.py` — publish metadata handoff if required

**Definition of Done**:
- [x] Partial bundle nav explicitly labels missing segments.
- [x] Missing segments link to the latest previous artifact when available.
- [x] Home/archive/per-segment nav agree on the bundle state.

### u64: `watchlist-entity-matching-and-actionability` — Exact Entity Matching and Useful Watchpoints

**Purpose**: Prevent false matches such as `BTC` mapping to `BTM earnings`, and upgrade watchpoints from generic `확인/점검` phrasing into source-backed trigger/threshold/implication observations.

**Stories**: FR-002 (AI 시황 작성), FR-004 (텔레그램 알림), FR-009 (reader-facing format), FR-012 (compliance language)

**Module path**:
- `src/investo/briefing/watchlist.py` — entity matching, aliases, confidence/reason
- `src/investo/publisher/reader_format.py` — watchpoint/actionability validation
- `src/investo/notifier/summary.py` — concise high-confidence watchlist reason

**Definition of Done**:
- [x] Short tickers require strict boundaries and `BTC` never matches `BTM`.
- [x] Watchlist callouts include source-backed evidence or are omitted.
- [x] Watchpoints contain source/trigger/threshold/implication unless data-limited.

### u65: `generated-briefing-quality-replay-harness` — Offline Artifact Review Harness

**Purpose**: Add a deterministic offline replay harness that reviews generated archive markdown and metadata for the defect classes found by the 10-subagent review, without network calls, LLM calls, or archive mutation.

**Stories**: FR-003 (정적 게시), FR-006 (보관), FR-010/FR-011/FR-012/FR-013 quality controls

**Module path**:
- `scripts/` or `tests/` helper — date/segment replay entrypoint
- `src/investo/publisher/` and `src/investo/briefing/` validators — reuse existing gates
- `tests/fixtures/` — compact passing/failing archive bundles

**Definition of Done**:
- [x] A local offline command or pytest helper can review one generated bundle.
- [x] First-viewport, status consistency, navigation, watchlist, and compliance findings are reported deterministically.
- [x] The harness is documented as the first validation step after future briefing-quality reviews.

### u66: `crypto-channel-depth` — Crypto-Native Indicators and 24h Framing

**Purpose**: Add crypto-native reader signals and replace the unsuitable "전일 종가" frame with a UTC 24h snapshot frame for the crypto channel. Reader-facing feature gap raised independently by the 크립토 투자자 + 신뢰성 personas in the 2026-05-24 review. Plan: `aidlc-docs/construction/plans/u66-crypto-channel-depth-code-generation-plan.md`.

**Scope (confirmed via lead live reachability probe 2026-05-24)**:
- In scope (no-key free): 공포·탐욕 지수 (Alternative.me), BTC 도미넌스 + 전체 시총 (CoinGecko `/global`), BTC 펀딩비 + 미결제약정(OI) (Bybit primary → OKX fallback; both geo-safe, **not** Binance — GHA 451), existing DeFiLlama TVL/stablecoin, and a crypto UTC-24h render/prompt frame.
- Out of scope (no no-key free source): **24h 청산** (Coinglass requires API key) and **거래소 netflow** (CryptoQuant/Glassnode paid) — scope-out, TECH-DEBT to be registered at closeout (next free ids, expected DEBT-071 / DEBT-072).
- u66 **defines the crypto indicator raw_metadata contract** (`indicator` tag + per-key units) that **u74 market-channel-depth-v2 consumes** (u74 is implementation-blocked on this) — see the plan's "u74 Interface Contract".

**Stories**: FR-001 (수집), FR-002 (AI 시황 작성), FR-008 (소스 확장성), FR-009 (reader-facing format)

**Existing Coverage / Deduplication**:
- Improves u54/u62/u65 quality surfaces by adding crypto-native input rows; does not redefine source severity, quality history, or replay harness ownership.
- Improves u55 numeric fact discipline by adding fixed metadata fields; does not build a second generic numeric validator.
- Preserves u56 crypto disclaimer/compliance wording and u58 official crypto-policy priority.
- Defines the crypto-side indicator contract that u74 consumes; u74 remains the cross-channel presentation wrapper.

**Module path**:
- `src/investo/sources/alternative_fng.py` — no-key Fear & Greed adapter
- `src/investo/sources/coingecko_global_market.py` — no-key BTC dominance / global market totals adapter
- `src/investo/sources/bybit_derivatives.py` (+ OKX fallback) — no-key BTC 펀딩비 / OI adapter (`category="macro"` + `indicator` raw_metadata tag; no new `Category` enum value)
- `src/investo/sources/defillama_market_structure.py` — reuse existing DeFi TVL / stablecoin structure adapter
- `src/investo/briefing/segments.py` — register new sources in `_CRYPTO_ONLY_SOURCES` (crypto-only routing)
- `src/investo/briefing/prompts.py` — crypto 24h-snapshot framing scope
- `src/investo/publisher/crypto_indicators.py` — deterministic crypto-native indicator block
- `src/investo/publisher/anchor_table.py` — crypto snapshot columns (UTC, 24h)

**Definition of Done**:
- [ ] `alternative-fng`, `coingecko-global-market`, and `bybit-derivatives` (+ `okx-derivatives` fallback) land from confirmed no-key HTTP 200 sources with recorded fixtures; funding/OI follow Bybit→OKX precedence.
- [ ] Indicators exposed through the u74 raw_metadata contract (exact `indicator`/key names/units), routed crypto-only.
- [ ] Crypto channel renders Fear & Greed, BTC dominance, total crypto market cap, BTC 펀딩비, BTC OI, DeFi TVL, stablecoin supply, and explicit unavailable rows for 24h 청산 / netflow.
- [ ] Crypto channel uses a UTC 24h snapshot frame, not equity close / "전일 종가" prose.
- [ ] 24h 청산 + netflow scoped out (no no-key source) and registered as TECH-DEBT; no fabricated values.
- [ ] No paid key; per-source isolation; channel separation and disclaimer untouched; Anthropic SDK untouched; module boundary intact; R13 no secret.

### u67: `domestic-channel-depth` — KOSPI Close Fallback, FX, and Sector Depth

**Purpose**: Surface KOSPI/KOSDAQ 종가·등락률 with a deterministic fallback when `fsc-krx-index-price` is empty, populate 원/달러 환율 from a free source, narrate 반도체/2차전지 sector depth, and add an overnight-US → KR-open framing. Reader-facing feature gap raised independently by the 국내 투자자 + 한국어 personas in the 2026-05-24 review.

**Stories**: FR-001 (수집), FR-002 (AI 시황 작성), FR-009 (reader-facing format)

**Module path**:
- `src/investo/sources/yfinance.py` / `stooq_price.py` — FX (`KRW=X` / `usdkrw`) + index fallback symbols
- `src/investo/sources/yonhap_market.py` — terminal index-close numeric parse fallback
- `src/investo/publisher/anchor_table.py` — domestic index + FX rows
- `src/investo/briefing/prompts.py` — sector grouping + overnight bridge scope

**Definition of Done**:
- [ ] KOSPI/KOSDAQ close + 등락률 appears in the body even when `fsc-krx-index-price` returns 0 rows.
- [ ] `usd_krw` populated from a free source and 원/달러 anchor line present.
- [ ] 반도체/2차전지 narrated in §③ when prices are collected; overnight-US → KR-open bridge present without cross-segment leakage.

### u68: `reader-aids-residual` — Inline Glossary and Carryover Follow-up Strengthening

**Purpose**: Close only the *residual* of review Gaps C/D after confirming u52 (carryover) and the header glossary callout already exist. Scope is limited to (a) optional inline first-use glossing beyond the existing top-of-document callout, and (b) verifying/strengthening that prior §⑥ previews are echoed as resolved/unresolved in the next day's §② via the existing carryover surface. u64 already delivered watchpoint actionability — no overlap.

**Stories**: FR-002 (AI 시황 작성), FR-009 (reader-facing format)

**Module path**:
- `src/investo/briefing/glossary.py` — optional inline gloss variant
- `src/investo/publisher/carryover.py` / `src/investo/briefing/carryover_parser.py` — follow-up echo verification/strengthening

**Definition of Done**:
- [ ] Confirm-then-extend audit: document which parts of C/D are already done (u52 + header glossary + u64 watchpoints) before any code.
- [ ] Net-new work limited to inline glossing and/or carryover follow-up gaps not covered by u52.

## Wave 13 2026-05-24 User-Quality Review Follow-up Units

The 2026-05-24 ten-subagent review of the latest generated segmented briefings found that the remaining reader-facing issues are mostly **consistency, prioritization, and workflow gaps** on top of already-delivered reliability work. These units are therefore written as improvements to existing surfaces, not duplicate base features.

Explicitly deduplicated out:
- Generic quality KPI work is already owned by u54/u62/u65. u69 only closes contradictions between public quality surfaces.
- Generic numeric fact checking is already owned by u55. u70 only reconciles the same numeric anchor across top table, body, trace, and chart surfaces.
- Generic first-viewport formatting is already owned by u51/u61. u71 only reorders reader priority and collapses diagnostics after the summary.
- Generic watchlist matching/actionability is already owned by u64. u72/u73 only add structured trigger matrices and daily portfolio-style impact workflows.
- Generic domestic depth is already closed by u67; generic crypto depth is already u66 backlog. u74 is a channel-depth v2 wrapper that coordinates remaining cross-channel gaps without reopening u67.
- Generic chart compactness is already delivered by the compact market chart cards change and u50. u75 only externalizes large inline chart data and lazy-loads the heavy payload.
- u68 owns reader-aid residuals around glossary/carryover. u76 excludes those mechanics and focuses on plain-language meaning lines inside generated sections.

### u69: `quality-public-consistency-gate` — Public Quality Surface Consistency

**Purpose**: Ensure `site_docs/quality.md`, `archive/_meta/quality_history.jsonl`, per-segment markdown status blocks, latest/archive index pages, and offline replay output all derive from the same canonical quality snapshot for a run/date. The defect class is reader trust: public dashboards can claim failed/zero/limited counts are 0 or `n/a` while the same day's briefing body says source failures, data shortages, or partial publication happened.

**Stories**: FR-001 (data collection), FR-003 (static publishing), FR-006 (archive), FR-010 (source-status severity/KPI), NFR-003 (graceful degradation)

**Existing coverage / deduplication**:
- Improves u54 source-status severity and KPI denominator rules; does not redefine severity semantics.
- Improves u62 canonical quality snapshot; does not reimplement `SegmentCoverage` or quality-history append.
- Improves u65 replay harness by adding this contradiction class as a replay check; does not build a second harness.

**Module path**:
- `src/investo/briefing/quality_history.py` — canonical quality-history owner and same-day reconciliation
- `archive/_meta/coverage.jsonl` / `SegmentCoverage` — per-segment source/body-used counts when quality history is aggregate-only
- `src/investo/publisher/site_index.py` — quality/index rendering from canonical snapshot
- `src/investo/publisher/briefing_replay.py` or replay validator module — contradiction checks
- `archive/_meta/quality_history.jsonl` / `site_docs/quality.md` — generated artifacts used by tests/fixtures only

**Definition of Done**:
- [ ] For the same date/segment, public quality surfaces cannot disagree on status tier, failed-source count, zero-item-source count, body-used count, or limited/failed segment count.
- [ ] Denominator-zero states render as `n/a` only when genuinely unknown, never when the archive body or quality history contains evidence.
- [ ] Offline replay reports a deterministic error when `quality.md` contradicts `quality_history.jsonl` or segment markdown.
- [ ] A regression fixture models the 2026-05-22 contradiction pattern found by the review.
- [ ] No new severity enum, source outcome schema, or KPI family is introduced.

### u70: `cross-surface-numeric-anchor-reconciliation` — One Numeric Anchor Across Body/Table/Trace/Chart

**Purpose**: Make the same market anchor resolve consistently across first-viewport tables, prose body, trace metadata, and chart placeholders. Review examples include a domestic body asserting a KOSPI move while the status block says core price data was missing, a US table labeling `^IXIC` as Nasdaq 100, and crypto top prices differing from body/trace figures.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-003 (publishing), FR-011 (numeric freshness/fact gates), NFR-003 (graceful degradation)

**Existing coverage / deduplication**:
- Improves u55 numeric freshness and market fact gates; does not create a second numeric validator.
- Improves u49 deterministic market anchors and u50 chart placeholders by forcing one shared anchor object through all reader surfaces.
- Relies on u67 domestic fallbacks and u66 crypto-depth planning rather than adding new market data sources here.

**Module path**:
- `src/investo/briefing/numeric_verify.py` / `freshness.py` — existing fact gate inputs
- `src/investo/orchestrator/pipeline.py::_reconcile_anchor_closes` — extend existing close-reconciliation path; do not create a parallel reconciler
- `src/investo/briefing/market_anchor.py` or shared model layer — anchor/display contract if a typed DTO is required
- `src/investo/publisher/anchor_table.py` — first-viewport and section anchor rendering
- `src/investo/publisher/charts.py` — chart placeholder close/change metadata
- `src/investo/orchestrator/pipeline.py` — run-level anchor handoff
- `tests/unit/publisher/` and `tests/unit/briefing/` — cross-surface fixtures

**Definition of Done**:
- [ ] A single typed anchor payload feeds table rows, body-available facts, trace rows, and chart placeholder price/change values.
- [ ] `^IXIC` is never labeled Nasdaq 100; Nasdaq 100 uses the correct symbol/label if present, otherwise the label is explicit about Nasdaq Composite.
- [ ] If a core anchor is missing or stale, the body cannot assert a precise move without a data-limited marker.
- [ ] Crypto `BTC/ETH/SOL` anchor values do not diverge between top table, §⑤ body, trace, and chart card.
- [ ] Replay/fixture tests cover domestic missing-core, US index-label, and crypto price-divergence cases.

### u71: `reader-first-viewport-reflow` — Summary-First Briefing Layout

**Purpose**: Put the reader's first useful answer before diagnostics. The review repeatedly found that the first viewport is dominated by status warnings, raw source counts, and long malformed `주의할 점` lines before the user sees "what happened" and "what matters." u71 reflows the first screen so `한눈에 보기`, confidence/status chips, and the top watchpoints are concise and ordered.

**Stories**: FR-002 (AI briefing), FR-003 (static publishing), FR-004 (Telegram summary alignment), FR-009 (reader-facing format), FR-012 (compliance language)

**Existing coverage / deduplication**:
- Improves u51 TL;DR/layout and u61 summary gate; does not add a new summary-quality validator.
- Reuses u54/u62 status values; only changes placement, length, and collapse behavior.
- Keeps u56 compliance language and disclaimer gates unchanged.

**Module path**:
- `src/investo/publisher/reader_format.py` — first-viewport assembly and diagnostics placement
- `src/investo/briefing/pipeline.py` — summary line inputs and header assembly
- `src/investo/notifier/summary.py` — concise public alert alignment
- `src/investo/publisher/charts.py` / u50 chart block output — placement-only coordination; no chart semantic change
- `site_docs/assets/u29.css` — collapsed diagnostics styling if needed

**Definition of Done**:
- [ ] First viewport order is H1/date, `## 한눈에 보기`, one compact status chip, at most three bounded watch/caution lines, then `<details>` diagnostics.
- [ ] Raw source errors/API details never appear before the summary unless the segment is fully failed.
- [ ] `주의할 점`/caution lines are length-bounded (max 90 Korean-visible chars), not truncated mid-token, and use u61-cleaned text only.
- [ ] Mobile rendering keeps the first useful summary visible without chart/diagnostic displacement.
- [ ] Existing summary malformation gates from u61 remain the single validation contract.

### u72: `watchpoint-action-matrix` — Trigger/Confidence/Implication Watchpoints

**Purpose**: Convert §⑥ watchpoints from generic `관찰/확인/점검` text into a structured observational matrix: Signal, Current, Bullish trigger, Bearish trigger, Confidence, and Portfolio implication. This gives the user actionable monitoring context without producing buy/sell advice.

**Stories**: FR-002 (AI briefing), FR-004 (notification summary), FR-009 (reader-facing format), FR-012 (compliance language)

**Existing coverage / deduplication**:
- Improves u64 watchpoint actionability; does not reimplement entity matching.
- Builds on u52 carryover and u55 numeric gates when a prior watchpoint or verified numeric threshold exists.
- Keeps u56 observational wording and forbidden-phrase scanner as the compliance boundary.

**Module path**:
- `src/investo/publisher/reader_format.py` — deterministic matrix renderer/validator
- `src/investo/briefing/prompts.py` — Stage 2 watchpoint contract
- `src/investo/notifier/summary.py` — compact matrix summary if appropriate
- `src/investo/briefing/watchlist.py` — consume u64 evidence/match results only; no new matcher workflow grouping
- `tests/unit/publisher/test_watchpoints*.py` — matrix shape and compliance fixtures

**Definition of Done**:
- [ ] §⑥ can render a bounded Markdown table/list with Signal / Current / Bullish trigger / Bearish trigger / Confidence / Section-local implication.
- [ ] Missing thresholds are allowed only with an explicit `데이터부족` reason from coverage/numeric gates.
- [ ] At least one watchpoint can cite a verified anchor, carryover item, or source title; otherwise the section degrades to a data-limited note.
- [ ] Compliance tests prove no buy/sell/target-price wording is introduced.
- [ ] Telegram remains concise and does not embed a large table.

### u73: `watchlist-impact-center-v2` — Daily Watchlist Impact Workflow

**Purpose**: Turn watchlist hits into a daily impact center: direct matches, related/macro context, uncertain matches, and rejected false positives. The review found that watchlist pages still feel like keyword matches rather than a portfolio workflow, and short tickers can still attract noisy related entities such as SOL/SLGL/Solana-company or BTC/BTM-like cases.

**Stories**: FR-002 (AI briefing), FR-003 (static publishing), FR-004 (notifications), FR-009 (reader-facing format)

**Existing coverage / deduplication**:
- Improves u18/u28/u33/u64 watchlist layers; does not add accounts, brokerage sync, or portfolio accounting.
- Reuses u64 strict matching and confidence reasons; this unit adds workflow grouping and rejected-match visibility.
- Uses existing static `site_docs/watchlist/` pages rather than inventing a new app surface.

**Module path**:
- `src/investo/briefing/watchlist.py` — match type/rejection reason model extension
- `src/investo/publisher/watchlist_pages.py` — canonical `site_docs/watchlist/{slug}.md` renderer and daily impact center output
- `src/investo/publisher/site_index.py` — only if home/archive link summaries need updated counts
- `src/investo/notifier/summary.py` — top direct impact only
- `site_docs/watchlist/` — generated static pages/fixtures

**Definition of Done**:
- [ ] Watchlist impacts are grouped as Direct, Related macro/sector, Uncertain, and Rejected.
- [ ] Short ticker suppression covers false-positive classes found in the review while preserving explicit alias matches.
- [ ] Daily watchlist page prioritizes today's impacts before historical/configuration text, with Uncertain/Rejected collapsed and redacted.
- [ ] Public briefing only surfaces high-confidence direct/related impacts; uncertain/rejected stays diagnostic.
- [ ] Tests cover SOL/BTC false positives and at least one valid direct alias per asset class.

### u74: `market-channel-depth-v2` — Remaining Channel Depth Coordination

**Purpose**: Coordinate remaining channel-depth gaps after u67 domestic depth and u66 crypto backlog: consistent channel-specific anchor blocks, explicit missing-data rows, and a cross-market cause map that explains why a domestic/US/crypto move matters to the other channels without violating segment scope.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segment-specific briefings), FR-009 (reader-facing format), FR-013 (segment narrative scope)

**Existing coverage / deduplication**:
- Does not reopen u67 domestic-channel-depth; any domestic regression remains u67 maintenance.
- Does not duplicate u66 crypto-native indicators; u74 consumes whatever u66 lands and standardizes the cross-channel presentation.
- Improves u57 BundleContext/shared macro handling and u53 sector/macro coverage by turning remaining gaps into a common presentation contract.

**Module path**:
- `src/investo/models/bundle_context.py` — cross-market cause-map inputs if needed
- `src/investo/publisher/anchor_table.py` — channel-specific anchor block contract
- `src/investo/briefing/prompts.py` — channel-depth instructions
- `src/investo/publisher/cross_segment_lint.py` — scope guard

**Definition of Done**:
- [ ] Each channel has a deterministic anchor block schema with explicit missing-data rows instead of silent omissions.
- [ ] u74 is implementation-blocked until u66 defines or lands the crypto indicator interface; if executed earlier, it may only render "not yet available" missing rows for u66-owned indicators.
- [ ] Crypto consumes u66 native indicators when available and labels unavailable indicators without inventing values.
- [ ] Domestic reuses u67 outputs without changing source precedence.
- [ ] Cross-market cause-map language is allowed only for u57-approved macro/systemic links and remains observational.
- [ ] Tests cover one complete channel, one partially missing channel, and one forbidden cross-segment leakage case.

### u75: `chart-data-externalization-and-mobile-performance` — Lazy Chart Payloads

**Purpose**: Keep compact chart cards visually small and also make the HTML payload small. The compact chart UI now hides the large candlestick chart until click, but each placeholder still embeds large `data-history` JSON inline. u75 moves historical OHLC payloads to deterministic sidecar JSON files and lazy-loads them on expand/viewport.

**Stories**: FR-003 (static publishing), FR-006 (archive), FR-009 (reader-facing format), NFR-001 (performance), NFR-002 (cost)

**Existing coverage / deduplication**:
- Improves u50 lightweight charts and the compact chart-card change; does not redesign chart visual treatment.
- Reuses existing bundled `lightweight-charts` asset and chart placeholder schema.
- Does not add a CDN, paid chart API, or server endpoint.

**Module path**:
- `src/investo/publisher/charts.py` — placeholder schema and sidecar manifest
- `src/investo/orchestrator/pipeline.py` — asset staging alongside segment markdown
- `site_docs/assets/investo-chart-init.js` — lazy fetch/expand behavior
- `tests/unit/publisher/test_chart_*.py` — HTML/sidecar invariants

**Definition of Done**:
- [ ] Segment HTML/markdown no longer embeds full OHLC history inline: no `data-history`, no OHLC row arrays; it carries only compact summary data and a sidecar URL/path.
- [ ] Sidecar JSON is deterministic, archive-local, staged with the markdown, and safe for GitHub Pages.
- [ ] Compact card still renders ticker/price/change without fetching the heavy payload.
- [ ] Full candlestick chart fetches sidecar data only on explicit click/keyboard expand, not on viewport entry, and degrades with a small error state.
- [ ] Tests assert payload-size reduction and no `</script>`/HTML injection regression.

### u76: `plain-language-reader-aids` — Section-Level Meaning Lines

**Purpose**: Add concise "그래서 의미는?" explanations inside each major section so non-expert Korean readers can understand why a data point matters. This is not a glossary/carryover unit; it is a prose usefulness layer for sections that currently list facts, tickers, or jargon without interpretation.

**Stories**: FR-002 (AI briefing), FR-009 (reader-facing format), FR-012 (compliance language)

**Existing coverage / deduplication**:
- Improves u40/u51/u68 reader aids but excludes u68 glossary/carryover mechanics.
- Reuses u56 compliance scanner; meaning lines must stay observational.
- Does not add new data sources, personas, or account state.

**Module path**:
- `src/investo/briefing/prompts.py` — Stage 2 instruction for section-level meaning lines
- `src/investo/publisher/reader_format.py` — deterministic validation/repair for line length and placement
- `tests/unit/briefing/test_prompts.py` and `tests/unit/publisher/` — format and compliance fixtures

**Definition of Done**:
- [ ] Sections §②-§⑤ can include one short line with exact marker `> **그래서 의미는?** `, max 80 Korean-visible chars after the marker, and idempotent replacement on rerun.
- [ ] Meaning lines are length-bounded, observational, and cannot contain buy/sell/target-price language.
- [ ] Ticker-heavy lines use known names only from existing static aliases/watchlist config/anchor labels; unknown tickers are not guessed.
- [ ] Existing glossary callout and u68 cross-day glossary/carryover work are untouched.
- [ ] Tests cover jargon-heavy, ticker-heavy, and data-limited sections.

---

### u87: `watchpoint-matrix-rehabilitation` — Fix §⑥ Universal Data-Limited + Markup/Diagnostic Leaks

**Purpose**: Make the §⑥ "오늘의 관전 포인트" matrix either present at least one genuinely structured observational row or collapse to a single honest data-limited note — never a multi-row wall of `데이터부족`, never a broken markdown-link fragment, never a leaked diagnostic hash. Refines the u72 renderer + Stage-2 prompt; does not replace them.

**Stories**: FR-002 (AI briefing), FR-004 (notification summary surface), FR-009 (reader-facing format), FR-012 (compliance language)

**Existing coverage / deduplication**:
- Refines u72 watchpoint-action-matrix (`publisher/watchpoint_matrix.py` + `briefing/prompts.py` §⑥ rule); adds no new module/API.
- Reuses the u64 `source + trigger + implication` contract and regexes unchanged; the fix targets the LLM input and non-observation lines that should never reach the contract gate.
- **Escalates and subsumes DEBT-074** (clause-slotting under-population → graceful `데이터부족`); mark it resolved-by-u87 on completion.
- Does NOT touch the watchlist "내 관심 자산 영향" line (u88), funding/numeric formatting (u89), meaning lines (u90), or bracket-tag prose leakage (u91). No new confidence enum; no change to u56 compliance.

**Module path**:
- `src/investo/publisher/watchpoint_matrix.py` — bullet pre-filter, `_short_signal` markdown/particle hardening, all-`데이터부족` collapse note
- `src/investo/briefing/prompts.py` — Stage-2 §⑥ structured-bullet contract
- `tests/unit/publisher/test_watchpoint_matrix.py` + `tests/unit/briefing/test_prompts.py` — defect-shape fixtures

**Definition of Done**:
- [ ] A trace-footer `- \`input_hash\`: \`…\`` (or `stage1_hash`/`stage2_hash`) line never becomes a matrix row (no diagnostic leak).
- [ ] A markdown-link bullet never yields a cell containing `](http`; the link text becomes the signal.
- [ ] A signal label never ends on a bare Korean particle from the pinned trim set.
- [ ] When no observation bullet is usable, §⑥ renders one pinned data-limited note, not a ≥2-row `데이터부족` table.
- [ ] A fully-structured source+trigger+implication bullet produces a populated row (proves the matrix can populate; closes DEBT-074).
- [ ] u56/u72 compliance tests stay green; transform stays idempotent and byte-preserves everything outside §⑥.

Plan: `aidlc-docs/construction/plans/u87-watchpoint-matrix-rehabilitation-code-generation-plan.md`.

---

### u92: `daily-briefing-runtime-observability` — Source/Segment/LLM Timing Surface

**Purpose**: Make daily briefing speed bottlenecks visible before changing runtime behavior. Today the GitHub summary exposes coarse stage timings, but `generate` hides context loading, market-anchor history fetch, three segment LLM generations, visual preparation, reader-format transforms, and publish-boundary work under one number. This unit adds structured timing for source adapters, segment generation, and each Claude attempt.

**Stories**: FR-005 (scheduled run), FR-007 (operator alerting), FR-008 (segmented briefing), NFR-001 (performance), NFR-003 (graceful degradation)

**Existing coverage / deduplication**:
- Extends u10 source diagnostics from item-count/window visibility to elapsed-time visibility.
- Extends u84 stage abstraction without changing the top-level stage order or failure routing.
- Does not parallelize source collection or segment generation; it only measures and reports.

**Module path**:
- `src/investo/sources/aggregator.py` and `src/investo/models/coverage.py` — per-source elapsed seconds on `SourceOutcome`
- `src/investo/briefing/_core/orchestration.py` — LLM attempt timing logs for classification/synthesis
- `src/investo/orchestrator/pipeline.py` — synthetic sub-stage timings for context, per-segment generation, reader-format, and visual assets
- `src/investo/__main__.py` — GitHub step summary rendering for the new timings
- `tests/unit/sources/`, `tests/unit/briefing/`, `tests/unit/orchestrator/` — timing and summary fixtures

**Definition of Done**:
- [ ] Each source adapter outcome carries elapsed seconds and the GitHub step summary displays the slowest sources without exposing secrets.
- [ ] Each segment generation records a timing key: `generate:domestic-equity`, `generate:us-equity`, and `generate:crypto`.
- [ ] Generate-stage context loading and reader-format work have separate timing keys.
- [ ] Each Claude attempt emits one structured INFO log with segment, LLM stage, attempt index, timeout, elapsed seconds, prompt byte length, stdout length, stderr length, and return code.
- [ ] Existing `PipelineResult.stage_timings` validation remains backward-compatible for older callers.

Plan: `aidlc-docs/construction/plans/u92-daily-briefing-runtime-observability-code-generation-plan.md`.

---

### u93: `llm-prompt-input-slimming` — Reduce Prompt Bytes Without Dropping Evidence

**Purpose**: Reduce daily briefing generation time by shrinking LLM prompts before concurrency changes. The current segmented path sends up to 96 candidates to Stage 1 with uncapped title/summary/URL fields, then sends a large Stage 2 system prompt plus optional context blocks. u93 keeps the existing candidate set and validation gates but trims prompt-only bytes.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-001 (performance), NFR-002 (cost)

**Existing coverage / deduplication**:
- Extends u13 candidate caps; u13 limits item count, while u93 limits prompt-field size and empty optional context text.
- Does not remove u55 numeric gates, u56 compliance gates, u61 first-viewport gate, u72/u87 watchpoint rules, or u76 meaning-line validation.
- Does not change source collection, segment routing, or publish-boundary validation.

**Module path**:
- `src/investo/briefing/_core/orchestration.py` — Stage 1 prompt serialization caps and prompt-size logs
- `src/investo/briefing/_assembly/prompt_fields.py` and `_reader_enhance/context_render.py` — compact prompt fields and empty optional context omission
- `src/investo/briefing/prompts.py` — compact Stage 2 system prompt text that references deterministic gates by contract name
- `tests/unit/briefing/` — prompt snapshot and semantic regression fixtures

**Definition of Done**:
- [ ] Stage 1 serialization caps title, summary, and URL fields with deterministic truncation while preserving macro payloads.
- [ ] Empty recent-context, carryover, lookahead, and bundle-context blocks are omitted from Stage 2 prompts.
- [ ] The Stage 2 system prompt removes mechanical rules already enforced by deterministic publisher/validator gates and keeps model-reasoning rules explicit.
- [ ] Prompt byte counts are lower in pinned tests for representative domestic, US, and crypto segment fixtures.
- [ ] Generated markdown still passes existing section, disclaimer, compliance, numeric, watchpoint, meaning-line, and quality replay tests.

Plan: `aidlc-docs/construction/plans/u93-llm-prompt-input-slimming-code-generation-plan.md`.

---

### u94: `bounded-segment-generation-concurrency` — Parallelize Independent Segment LLM Work

**Purpose**: Reduce wall-clock generation time by running independent market segment generation concurrently under an explicit concurrency limit. Current `_stage_generate_segments` awaits domestic, US, and crypto in fixed order; each segment performs Stage 1 classification and Stage 2 synthesis before the next segment starts.

**Stories**: FR-005 (scheduled run), FR-008 (segmented briefing), NFR-001 (performance), NFR-003 (graceful degradation), NFR-007 (secret hygiene)

**Existing coverage / deduplication**:
- Builds on u7 segmented briefing and u84 stage abstraction; it changes only intra-generate segment fanout.
- Requires u92 observability so before/after behavior is measured in GitHub summary.
- Does not overlap top-level collect/generate/publish/notify stages and does not change partial-publish semantics.

**Module path**:
- `src/investo/orchestrator/pipeline.py` — bounded segment task fanout inside `_stage_generate_segments`
- `src/investo/orchestrator/validators.py` or a small orchestrator config helper — `INVESTO_SEGMENT_GENERATION_CONCURRENCY` parsing
- `tests/unit/orchestrator/test_stage_generate.py` and `tests/unit/orchestrator/test_run_pipeline.py` — ordering, failures, and partial-publish fixtures

**Definition of Done**:
- [ ] `INVESTO_SEGMENT_GENERATION_CONCURRENCY` accepts integer values 1 through 3, defaults to 1 for a behavior-preserving rollout, and rejects invalid values with a deterministic fallback to 1 plus a warning log.
- [ ] With concurrency 2 or 3, segment generation tasks start before earlier sibling segments finish.
- [ ] Per-segment `BriefingGenerationError` isolation is unchanged: one failed segment still allows remaining successful segments to publish; all failed segments still fail the pipeline.
- [ ] Macro lineage, bundle context, market anchors, carryover, and source outcomes remain segment-scoped and deterministic.
- [ ] Existing tests that forbid top-level stage `asyncio.gather` remain valid.

Plan: `aidlc-docs/construction/plans/u94-bounded-segment-generation-concurrency-code-generation-plan.md`.

---

### u95: `workflow-and-enrichment-critical-path-budget` — Shorten Non-LLM Critical Path

**Purpose**: Reduce daily briefing runtime outside the main LLM calls by tightening workflow cold-start setup and best-effort enrichment budgets. The GitHub workflow installs runtime tools on every run, the market-anchor helper performs a separate Yahoo history fetch before segment generation, and visual asset preparation runs per segment in sequence.

**Stories**: FR-003 (static publishing), FR-005 (scheduled run), FR-008 (segmented briefing), NFR-001 (performance), NFR-002 (cost), NFR-003 (graceful degradation)

**Existing coverage / deduplication**:
- Extends u6 infra/CI but does not change cron semantics, secrets, Pages deploy, or exit-code mapping.
- Extends u49/u50/u75 enrichment paths by constraining critical-path budget; it does not redesign charts or add new visual sources.
- Requires u92 observability so workflow and enrichment improvements are measured.

**Module path**:
- `.github/workflows/daily-briefing.yml` — uv/npm cache, minimized Cairo install, setup-step timing comments
- `src/investo/orchestrator/stage_context.py` and `src/investo/sources/yfinance_history.py` — faster graceful-degrade market-anchor history fetch
- `src/investo/orchestrator/pipeline.py` and `src/investo/visuals/assets.py` — bounded concurrent visual preparation and tighter external-image budget
- `tests/unit/orchestrator/`, `tests/unit/sources/test_yfinance_history.py`, `tests/unit/publisher/test_chart_assets.py` — degraded enrichment and workflow text guards

**Definition of Done**:
- [ ] Daily briefing workflow uses cacheable uv and npm setup without adding paid services or new secrets.
- [ ] Cairo install is reduced to the packages required by the runtime OG-card preflight.
- [ ] Market-anchor history fetch has a bounded total budget and logs graceful omission without delaying all segment generation beyond that budget.
- [ ] Visual asset preparation can run per published segment under a bounded worker count and remains text-only on visual failure.
- [ ] GitHub step summary shows workflow/runtime timing changes through u92 surfaces.

Plan: `aidlc-docs/construction/plans/u95-workflow-and-enrichment-critical-path-budget-code-generation-plan.md`.

---

### u96: `quality-current-run-snapshot-sync` — Align Public Quality Metrics With Segment Reality

**Purpose**: Extend the existing u62/u69 canonical quality snapshot so the public `quality.md` dashboard, `quality_history.jsonl`, segment markdown status, latest/archive index labels, and publish-boundary consistency gate read from the same current-run facts. The 2026-06-09 generated bundle showed segment-level `[데이터부족]`, `데이터 상태: 제한`, and core-source failures while the public quality page still displayed healthier aggregate metrics.

**Stories**: FR-003 (static publishing), FR-007 (operator alerting), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (data integrity)

**Existing coverage / deduplication**:
- Extends u54/u62/u65 quality surfaces and u69 public consistency gate; it does not add a new quality KPI family.
- Keeps `CoverageStatus`, source adapter behavior, core-source membership, and `HealthTrackingStage` ordering unchanged.
- Fixes publish-time snapshot construction so final segment markdown and current coverage artifacts cannot contradict the dashboard.

**Module path**:
- `src/investo/briefing/quality_eval.py` — recognize segment-level `[데이터부족]`, `데이터 부족 안내`, `실시간 안내`, and limited/failed status-block markers.
- `src/investo/briefing/quality_history.py` — persist current-run snapshot fields with backward-compatible defaults.
- `src/investo/orchestrator/pipeline.py` — build the quality snapshot from current publish artifacts before writing public quality surfaces.
- `src/investo/publisher/quality_consistency.py` — block dashboard/segment contradictions at publish boundary.
- `src/investo/publisher/site_index/quality_dashboard.py` and `site_index.__init__.py::update_latest_index_pages` — render the new snapshot fields without overstating health.
- `tests/unit/briefing/`, `tests/unit/orchestrator/`, `tests/unit/publisher/` — fixture-level checks for the 2026-06-09 contradiction shape.

**Definition of Done**:
- [ ] `[데이터부족]`, `데이터 부족 안내`, `실시간 안내`, `데이터 상태: 제한`, `데이터 상태: 실패`, and current coverage severities are counted by the same current-run snapshot used by `quality.md`.
- [ ] The snapshot exposes `current_run_zero_item_sources`, `current_run_core_missing_segments`, `current_run_segments_limited_or_worse`, `current_run_data_limited_briefings`, and `current_run_briefings_observed` with backward-compatible loading for older history rows.
- [ ] The 2026-06-09 fixture shape renders `데이터 부족 폴백 25.0% | 12 건`, `핵심 소스 결손 세그먼트 3`, `제한/실패 세그먼트 3`, and at least seven zero-item source records.
- [ ] The u69 consistency gate blocks a publish when `quality.md`, `quality_history.jsonl`, or index labels are healthier than the corresponding final segment markdown/current coverage facts.
- [ ] No source adapter, severity enum, or core-source list changes are included in this unit.

Plan: `aidlc-docs/construction/plans/u96-quality-current-run-snapshot-sync-code-generation-plan.md`.

---

### u97: `evidence-weighted-story-hierarchy` — Rank Evidence Before Narrative Assembly

**Purpose**: Add deterministic story-tier metadata so Stage 2 can distinguish core thesis evidence from supporting, contextual, and watchlist-only items. The reader review found that low-signal rows could receive the same narrative weight as macro or market-wide evidence, weakening the story arc. This unit should run before u99 so the daily thesis does not amplify weak evidence.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-006 (data integrity)

**Existing coverage / deduplication**:
- Extends u13 candidate caps, u57 narrative scope, u59 macro priority, and u64/u73 watchlist routing without changing source collection.
- Reuses existing macro priority and required-macro actual detection; it does not replace shared macro blocks or cause-map logic.
- Keeps lower-tier evidence available for appropriate sections instead of deleting it from the briefing.

**Module path**:
- `src/investo/briefing/_core/section_planning.py` — add `StoryMetadata`, `story_identity()`, deterministic `story_tier`, and fixed `story_score`.
- `src/investo/briefing/_assembly/markdown_render.py` — pass story metadata into Stage 2 evidence bullets.
- `src/investo/briefing/prompts.py` — instruct Stage 2 to lead with core evidence, then supporting and contextual evidence.
- `tests/unit/briefing/` — tier assignment, cap preservation, and prompt-contract regression fixtures.

**Definition of Done**:
- [ ] Section planning marks each candidate as `core`, `supporting`, `context`, or `watchlist_only` with a deterministic score.
- [ ] Core rows survive candidate/section caps ahead of lower-tier rows when both compete for the same narrative slot.
- [ ] Serialized Stage 2 input presents `core` evidence ahead of `watchlist_only` or purely contextual evidence when core evidence exists.
- [ ] Stage 2 prompt inputs expose prompt-only tier labels without changing the six-section briefing structure or leaking mechanical labels into published markdown.
- [ ] Required macro actuals and u59 macro lineage behavior remain unchanged.

Plan: `aidlc-docs/construction/plans/u97-evidence-weighted-story-hierarchy-code-generation-plan.md`.

---

### u98: `watchpoint-card-list-redesign` — Replace the Dense §⑥ Matrix With Reader-First Cards

**Purpose**: Replace the six-column §⑥ watchpoint matrix with the canonical compact card format that preserves actionability while reading cleanly on mobile. The current table repeats source text, exposes `데이터부족` cells, and can leak broken markdown/link fragments.

**Stories**: FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (data integrity)

**Existing coverage / deduplication**:
- Extends u72/u87 watchpoint rendering; keeps the exact `render_watchpoint_matrix()` callable signature as the public API.
- Reuses u64 watchlist/actionability structure checks, u56 compliance scanning, and the closed confidence enum.
- Does not change the watchlist matcher, source adapters, numeric evidence extraction, or Telegram summary semantics.

**Module path**:
- `src/investo/publisher/watchpoint_matrix.py` — render card/list output from the existing structured rows.
- `src/investo/briefing/prompts.py` — align Stage 2 §⑥ instructions with the new reader-facing shape.
- `tests/unit/publisher/test_watchpoint_matrix.py` — card rendering, sanitation, idempotence, and byte-preservation fixtures.
- `tests/unit/briefing/test_prompts.py` — prompt contract fixture.

**Definition of Done**:
- [ ] §⑥ no longer renders the six-column table header `관찰 신호 | 현재 | 상방 확인 조건 | 하방 확인 조건 | 신뢰도 | 섹션 내 관심 영향`.
- [ ] Usable watchpoints render as canonical reader cards with `출처`, current signal, upside/downside confirmation, confidence, and watchlist relevance.
- [ ] Rows with no usable signal collapse to the existing data-limited note instead of producing multiple all-`데이터부족` cards.
- [ ] Raw URLs, broken markdown fragments, trace hashes, and dangling link text cannot appear in the rendered §⑥ body.
- [ ] Rendering remains idempotent and byte-preserving outside §⑥.

Plan: `aidlc-docs/construction/plans/u98-watchpoint-card-list-redesign-code-generation-plan.md`.

---

### u99: `daily-thesis-layer` — Add a Cross-Segment "오늘의 큰 그림" Narrative Line

**Purpose**: Add a deterministic daily thesis layer that states the cross-market story before segment-specific detail. The reader review found that individual segments contained facts and local conclusions, but lacked one clear "why today matters" line across domestic equity, US equity, and crypto. This unit should run after u97 and with u100 so the inserted first-viewport line is both evidence-weighted and surface-gated.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (data integrity)

**Existing coverage / deduplication**:
- Extends u57 narrative scope and u74 cross-market channel depth; it does not replace shared macro blocks or cause-map gating.
- Uses `BundleContext`, an orchestrator-owned `DailyThesisDecision`, and deterministic publisher insertion, not a third LLM call.
- Keeps segment briefings independently publishable under partial-success conditions.

**Module path**:
- `src/investo/models/bundle_context.py` — add structured daily-thesis fields or reusable macro-signal fields.
- `src/investo/orchestrator/bundle_context.py` and `src/investo/orchestrator/pipeline.py` — compute and pass thesis signals from successful segments and market anchors.
- `src/investo/publisher/daily_thesis.py` — render and inject the thesis decision only.
- `src/investo/publisher/segment_reader_format.py` — inject the thesis line before §① in each successful segment.
- `src/investo/publisher/cross_market_cause_map.py` and `src/investo/briefing/_reader_enhance/context_render.py` — share structured macro keys without weakening u74 gating.
- `tests/unit/orchestrator/`, `tests/unit/publisher/`, `tests/unit/briefing/` — deterministic, partial-publish, idempotence, and prompt-context fixtures.

**Definition of Done**:
- [ ] Successful segments in the same bundle receive the same bounded "오늘의 큰 그림" line before §①.
- [ ] The thesis follows the fixed decision table: 0-1 successful segments omit, 2+ without shared approved signal render a neutral data-limited note, 2+ with shared approved signal render a strong line.
- [ ] The rendered line contains no digits, advice, price targets, or outcome predictions.
- [ ] Re-running reader formatting does not duplicate or drift the thesis line.
- [ ] u74 cause-map gating remains active and forbidden cause-map types remain suppressed from both cause-map output and the thesis line.

Plan: `aidlc-docs/construction/plans/u99-daily-thesis-layer-code-generation-plan.md`.

---

### u100: `surface-quality-gate` — Repair and Block Broken First-Viewport Language Artifacts

**Purpose**: Add a deterministic surface-quality pass for known bad Korean tokens and broken first-viewport artifacts. The reader review found defects such as `불강한성`, dangling `...`, broken markdown fragments, and repeated template phrases that damage trust even when underlying facts are acceptable. This unit should run with u99 so the new daily thesis line is included in the final first-viewport gate.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (data integrity)

**Existing coverage / deduplication**:
- Extends u56 compliance, u61 first-viewport validation, u71 reflow, and u76 meaning-line normalization.
- Repairs only known deterministic artifacts and blocks unrepaired first-viewport defects.
- Does not add a full Korean spellchecker, semantic LLM rewrite, or global ban on ellipses.

**Module path**:
- `src/investo/_internal/surface_quality.py` — shared issue codes, first-viewport extraction, repair, and scan logic.
- `src/investo/briefing/summary_quality.py` — add surface-defect findings for first-viewport text.
- `src/investo/briefing/_assembly/summary_extraction.py` — prevent broken artifacts from entering summary/conclusion extraction.
- `src/investo/publisher/reader_format/reflow.py` and `src/investo/publisher/segment_reader_format.py` — place the pass after reflow and before final publish-boundary checks.
- `src/investo/publisher/errors.py` and `src/investo/orchestrator/pipeline.py` — route blocking `SurfaceQualityError` when unrepaired first-viewport defects remain.
- `tests/unit/briefing/`, `tests/unit/publisher/`, `tests/unit/orchestrator/` — repair, block, idempotence, and warning-only fixtures.

**Definition of Done**:
- [ ] Known bad token `불강한성` is repaired to `불확실성` before final markdown is written.
- [ ] First-viewport dangling `...` is repaired and warned; broken markdown links and trace/link fragments are blocked before publish.
- [ ] Code blocks, markdown tables, disclaimers, and diagnostic details are not rewritten by the repair pass.
- [ ] Repeated template phrases generate warnings but do not block publish in this unit.
- [ ] The pass is idempotent, runs after u71 reflow, and runs before the final compliance/disclaimer/public consistency gates.

Plan: `aidlc-docs/construction/plans/u100-surface-quality-gate-code-generation-plan.md`.

---

### u101: `verified-fact-cache-and-entity-guard` - Auto-Refresh High-Drift Entity Facts

**Purpose**: Add an official-source-backed fact cache for high-drift entity facts, starting with `fed.current_chair`, and block stale or unsupported person/role claims before publish. The 2026-06-16 US-equity briefing called the 2026-06-17 FOMC press conference a Powell press conference even though the current Fed chair was Kevin Warsh. The root cause was that `fomc-calendar` supplied only `FOMC Press Conference`, while Stage 2 filled the chair name from model memory. This unit makes the current officeholder a structured, refreshed input and makes unsupported names fail closed.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (data integrity), NFR-007/R13 (public-surface safety)

**Existing coverage / deduplication**:
- Extends u35/u43 FOMC lookahead and u59 macro-event lineage by adding the current officeholder context that scheduled-event feeds do not contain.
- Extends u55/u70 trust gates but does not create another numeric validator; this unit only handles high-drift entity/role facts such as current chairs, presidents, governors, and official committee leaders.
- Extends u100 surface-quality gating with semantic entity consistency; it does not add an LLM fact-checker or broad web search.
- Uses official source-of-record adapters only. First scope is Federal Reserve Board Members for `fed.current_chair`; non-Fed facts are registry-ready but not implemented in the first slice.

**Module path**:
- `src/investo/models/facts.py` - add `FactId`, `FactSnapshot`, `FactStatus`, `FactSourceTier`, and `VerifiedFactBundle` pydantic models with primitive-safe serialization.
- `src/investo/sources/fed_board_leadership.py` - fetch and parse the Federal Reserve Board Members page, extracting exactly one `*, Chairman` row as `fed.current_chair`.
- `src/investo/sources/aggregator.py` and `src/investo/sources/tiers.py` - register `fed-board-leadership` as a Tier S source and include it in the US equity collection path.
- `src/investo/briefing/fact_context.py` and `src/investo/briefing/prompts.py` - render a compact "Verified current facts" prompt block and instruct Stage 2 to use role/person names only from that block or from supplied source items.
- `src/investo/publisher/entity_fact_guard.py` - scan generated markdown for current-role claims such as `파월 의장`, `Powell chair`, `Chair Powell`, and block claims that conflict with fresh facts or lack evidence when the fact is stale.
- `src/investo/publisher/segment_reader_format.py` and `src/investo/orchestrator/pipeline.py` - run the guard after reader formatting and before final publish-boundary validators; route failures as a publish-blocking error.
- `archive/_meta/fact_snapshots.jsonl` - append current-run fact snapshots for operator lineage; stale snapshots remain diagnostic only and must not authorize names.
- `tests/unit/models/`, `tests/unit/sources/`, `tests/unit/briefing/`, `tests/unit/publisher/`, `tests/unit/orchestrator/` - model round-trip, fixture-backed parsing, prompt rendering, conflict blocking, stale fail-closed, and pipeline wiring fixtures.

**Definition of Done**:
- [ ] A live-recorded Federal Reserve Board Members fixture parses `Kevin Warsh, Chairman` into a fresh `FactSnapshot` with `fact_id="fed.current_chair"`, `value="Kevin Warsh"`, Korean aliases, source URL, observed timestamp, and expiry timestamp.
- [ ] Stage 2 receives a compact verified-facts block when `fed.current_chair` is fresh; when the fact is missing or stale, the block explicitly says the current Fed chair is unverified and the prompt forbids naming a Fed chair.
- [ ] FOMC meeting and press-conference prose may render `Kevin Warsh 의장` only when the fresh fact is present; otherwise it must render role-neutral text such as `FOMC 기자회견`.
- [ ] Publish is blocked when target-date-current prose says `파월 의장`, `Powell chair`, or `Chair Powell` while `fed.current_chair` is fresh and not Powell.
- [ ] Historical references remain allowed only when marked as former/prior context, such as `전임 의장 Powell`, `former Chair Powell`, or a dated past event before the fact's effective window.
- [ ] Fact refresh failure does not reuse an expired value as truth; expired snapshots are diagnostics only and allow role-neutral wording, never a person-name claim.
- [ ] Fact snapshots and guard diagnostics are R13-safe: no raw HTML, cookies, headers, tokens, or long page excerpts are written to public markdown or logs.

Plan: `aidlc-docs/construction/plans/u101-verified-fact-cache-and-entity-guard-code-generation-plan.md`.

---

### u102: `source-adapter-registry-completeness` - Prevent Source Routing, Tier, and Window Drift

**Purpose**: Add a deterministic registry completeness gate before further source expansion. The source layer currently registers adapters through several separate maps: package imports, plugin-contract tests, tier labels, market-window routing, and segment allow-lists. New source adapters must not silently fall back to default tier or the wrong market clock.

**Stories**: FR-001 (data collection), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (data integrity)

**Existing coverage / deduplication**:
- Extends the existing adapter drift guard in `tests/unit/sources/test_plugin_contract.py`.
- Does not add a data source, change adapter behavior, or revise coverage severity policy.
- Protects future u103-u107 source units from registry omissions.

**Module path**:
- `src/investo/sources/tiers.py` - require explicit tier coverage for every registered adapter.
- `src/investo/sources/aggregator.py` - expose or test the market-window source sets without changing runtime behavior.
- `src/investo/briefing/segments.py` - validate segment source membership for every registered adapter.
- `tests/unit/sources/test_plugin_contract.py` and `tests/unit/orchestrator/test_stage_collect.py` - add registry completeness and market-clock regression coverage.

**Definition of Done**:
- [ ] Every registered adapter has an explicit `ADAPTER_TIERS` entry; no production adapter reaches the default tier path.
- [ ] Every registered adapter is present in exactly one segment-only source set or in an explicit shared-source map.
- [ ] Every US-only and crypto-only source receives the correct market-window policy in aggregator tests.
- [ ] The test suite fails loudly when a new adapter is imported without tier, segment, and market-window registration.
- [ ] Existing default-tier fallback remains available only for test stubs and emits a diagnostic log.

Plan: `aidlc-docs/construction/plans/u102-source-adapter-registry-completeness-code-generation-plan.md`.

---

### u103: `official-policy-speech-rss-sources` - Add Fed and SEC Official Speech Feeds

**Purpose**: Add official no-key RSS feeds for Federal Reserve speeches/testimony and SEC newsroom speech/press releases. The current policy coverage has FOMC releases, FOMC calendar events, SEC company 8-K filings, and Congress/committee policy sources, but it lacks official speech and testimony text that often moves rates, market structure, and crypto regulation narratives.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-002 (zero-cost operation), NFR-003 (graceful degradation), R10, R13

**Existing coverage / deduplication**:
- Extends `fomc-rss` and `official_policy` coverage without replacing them.
- Does not add third-party news, paid APIs, browser automation, or broad web search.
- Uses no-key official RSS feeds only.

**Module path**:
- `src/investo/sources/fed_speech_rss.py` - collect Federal Reserve speeches and testimony RSS items.
- `src/investo/sources/sec_newsroom_rss.py` - collect SEC press releases and speeches/statements RSS items.
- `src/investo/sources/__init__.py`, `tiers.py`, `aggregator.py`, and `briefing/segments.py` - register sources, tiers, market windows, and segment routing.
- `tests/unit/sources/test_fed_speech_rss.py`, `tests/unit/sources/test_sec_newsroom_rss.py`, and plugin contract tests - fixture-backed parsing and registration coverage.

**Definition of Done**:
- [ ] Fed speeches and testimony feeds are collected from official `federalreserve.gov` RSS endpoints with no API key.
- [ ] SEC press release and speech/statement feeds are collected from official `sec.gov` RSS endpoints with no API key.
- [ ] Fed speech items route to `us-equity`; SEC newsroom items route to `us-equity` and crypto only when the item text matches existing crypto-policy routing terms.
- [ ] Each adapter uses `retry_get`, timezone-aware timestamps, text sanitation, R10 recorded fixtures, and R13-safe errors.
- [ ] Source cost, auth, rate-limit, and no-paid-tier facts are documented in the plan and PR checklist.

Plan: `aidlc-docs/construction/plans/u103-official-policy-speech-rss-sources-code-generation-plan.md`.

---

### u104: `sec-company-facts-and-symbol-directory` - Add Official US Company Fact and Symbol Anchors

**Purpose**: Add official SEC company submissions/companyfacts and Nasdaq Trader symbol directory anchors so US equity briefings can distinguish company filings, watchlist CIKs, exchange listings, ETF flags, and financial statement facts from generic news text.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-002 (zero-cost operation), NFR-003 (graceful degradation), R10, R13

**Existing coverage / deduplication**:
- Extends `sec-edgar-8k`; it does not duplicate the current 8-K Atom feed.
- Extends existing Nasdaq news/earnings sources; it does not replace earnings calendar collection.
- Does not ingest all SEC XBRL concepts. The first slice uses a bounded watchlist CIK map and an allow-list of financial concepts.

**Module path**:
- `src/investo/sources/sec_company_facts.py` - collect bounded SEC submissions/companyfacts for configured watchlist CIKs.
- `src/investo/sources/nasdaq_symbol_directory.py` - parse Nasdaq listed and other-listed symbol directory text files.
- `src/investo/briefing/fact_context.py` or a new source-context helper - render compact company/symbol anchors into Stage 2 context.
- `tests/unit/sources/test_sec_company_facts.py`, `tests/unit/sources/test_nasdaq_symbol_directory.py`, and routing/tier tests.

**Definition of Done**:
- [ ] SEC company endpoints use `data.sec.gov`/`sec.gov` JSON with a declared fair-access User-Agent and no API key.
- [ ] The adapter collects only configured watchlist CIKs and a fixed concept allow-list such as revenue, net income, EPS, assets, liabilities, operating cash flow, and share count.
- [ ] Nasdaq symbol directory parsing records symbol, listing exchange, ETF flag, test issue flag, and financial status without scraping web pages.
- [ ] SEC and Nasdaq anchor items are bounded so Stage 1 candidate caps are not exhausted by bulk filing history.
- [ ] Fixtures cover happy path, missing CIK, missing concept, malformed JSON, and SEC 403/429 graceful degradation.

Plan: `aidlc-docs/construction/plans/u104-sec-company-facts-and-symbol-directory-code-generation-plan.md`.

---

### u105: `macro-actual-source-of-record` - Add BLS and BEA Actual Release Data

**Purpose**: Add source-of-record macro actuals for BLS and BEA releases. Existing FRED/FOMC/BEA schedule coverage tells the pipeline what is coming, but critical releases such as CPI, payrolls, PCE, and GDP need official actual/prior/period values and canonical event keys so schedule and actual evidence join cleanly.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-002 (zero-cost operation), NFR-003 (graceful degradation), R10, R13

**Existing coverage / deduplication**:
- Extends u59 macro actual/lineage work; it does not replace macro lifecycle logic.
- Extends `fred-economic-calendar`; it does not add another calendar-only source.
- Does not create consensus, forecast, or surprise values unless official no-cost source fields provide them directly.

**Module path**:
- `src/investo/sources/bls_macro_actuals.py` - collect bounded CPI, labor, PPI, JOLTS, and wage series from BLS Public Data API.
- `src/investo/sources/bea_macro_actuals.py` - collect bounded GDP and PCE/NIPA actuals from BEA API.
- `src/investo/briefing/macro_carryover.py` and `src/investo/models/macro.py` - reuse canonical macro event key fields without expanding the model surface beyond required metadata.
- `tests/unit/sources/test_bls_macro_actuals.py`, `tests/unit/sources/test_bea_macro_actuals.py`, and macro lineage tests.

**Definition of Done**:
- [ ] BLS and BEA adapters emit official actual/prior/period/source metadata for a bounded release allow-list.
- [ ] CPI, payrolls, PCE, and GDP actuals stamp canonical `macro_event_key` values that match existing schedule events.
- [ ] Missing API keys or exhausted free endpoints degrade at adapter level and do not stop sibling sources.
- [ ] Generated prompt context can prioritize official actuals without claiming consensus or surprise when those fields are unavailable.
- [ ] Fixtures cover current release, prior revision, empty series, malformed payload, missing-key behavior, and no-secret diagnostics.

Plan: `aidlc-docs/construction/plans/u105-macro-actual-source-of-record-code-generation-plan.md`.

---

### u106: `money-energy-volatility-source-expansion` - Add Funding, Energy, and Volatility Context

**Purpose**: Add no-key or free official sources for money-market funding conditions, petroleum supply, and options-volatility sentiment. Existing Treasury/FRED/Stooq/YFinance sources provide rates and market prices, but they do not explain SOFR/EFFR funding stress, petroleum inventories, or option-tail risk through official data.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-002 (zero-cost operation), NFR-003 (graceful degradation), R10, R13

**Existing coverage / deduplication**:
- Extends `treasury-rates`, `fred-macro`, and `stooq-price`; it does not replace price snapshots or yield curve collection.
- Uses official NY Fed/EIA/Cboe surfaces only.
- Excludes FRED ICE BofA credit OAS series with restrictive redistribution language.

**Module path**:
- `src/investo/sources/nyfed_reference_rates.py` - collect SOFR, EFFR, OBFR, BGCR, TGCR and volume/percentile fields.
- `src/investo/sources/eia_petroleum_weekly.py` - collect weekly crude, gasoline, distillate, production, import, and refinery utilization facts.
- `src/investo/sources/cboe_volatility_indices.py` - collect VVIX and SKEW official CSVs; VIX is included only as cross-check metadata because price sources already carry VIX.
- `tests/unit/sources/test_nyfed_reference_rates.py`, `test_eia_petroleum_weekly.py`, `test_cboe_volatility_indices.py`, and segment routing tests.

**Definition of Done**:
- [ ] NY Fed reference-rate items publish business-day actual values with official source URL, observed date, and units.
- [ ] EIA weekly petroleum items publish release-date, inventory, production, imports, and refinery utilization metadata with source lag clearly represented.
- [ ] Cboe volatility items prioritize VVIX/SKEW so the unit does not duplicate existing VIX price snapshots.
- [ ] All adapters use bounded retry/body-size behavior and classify stale weekly data as source-lag context, not fresh intraday data.
- [ ] Fixtures cover current data, holiday/stale release, empty table/CSV, malformed payload, and source failure isolation.

Plan: `aidlc-docs/construction/plans/u106-money-energy-volatility-source-expansion-code-generation-plan.md`.

---

### u107: `cftc-positioning-layer` - Add Regulated Futures Positioning Context

**Purpose**: Add CFTC COT/TFF positioning data for equity index, VIX, Treasury, FX, energy, metals, and crypto futures. The current system has price, rates, domestic investor flows, crypto funding/OI, and sentiment, but lacks regulated futures positioning that explains who is leaning into a move.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-002 (zero-cost operation), NFR-003 (graceful degradation), R10, R13

**Existing coverage / deduplication**:
- Complements `krx-foreign-flows`, `bybit-derivatives`, `okx-derivatives`, and `alternative-fng`; it does not replace them.
- Uses official CFTC public reporting data only.
- Does not implement paid liquidation, exchange netflow, or private positioning products.

**Module path**:
- `src/investo/sources/cftc_cot_positioning.py` - fetch and parse bounded COT/TFF datasets.
- `src/investo/briefing/segments.py` - route selected contracts to `us-equity`, `crypto`, or shared macro context.
- `src/investo/publisher/channel_anchor_block.py` or a new positioning renderer - present delayed weekly positioning as a context row with release lag.
- `tests/unit/sources/test_cftc_cot_positioning.py`, routing tests, and delayed-data presentation tests.

**Definition of Done**:
- [ ] CFTC positioning collection uses official public data with no token and a bounded contract allow-list.
- [ ] The adapter maps selected contract codes to reader labels for S&P 500/Nasdaq/VIX/Treasury/USD/WTI/gold/BTC where official contract data exists.
- [ ] Published context labels the data as weekly and Tuesday-as-of/Friday-release, avoiding daily freshness claims.
- [ ] The source emits no result for unmapped contracts rather than inventing labels or approximating from unrelated contracts.
- [ ] Fixtures cover current report, holiday-delayed report, unmapped contract, malformed row, and source failure isolation.

Plan: `aidlc-docs/construction/plans/u107-cftc-positioning-layer-code-generation-plan.md`.

---

### u108: `reader-facing-quality-language-boundary` - Keep Operator Diagnostics Out of Briefing Prose

**Purpose**: Stop generated daily briefings from exposing operator-facing quality labels such as `데이터 부족`, `[데이터부족]`, `본문 사용 미집계`, `확인 소스 미상`, and raw failure-count language inside the reader narrative, first viewport, site cards, visual cards, and Telegram summaries.

**Stories**: FR-002 (AI briefing), FR-003 (public publishing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (quality observability), R13

**Existing coverage / deduplication**:
- Extends u54/u62/u65/u69/u96 quality surfaces; it does not add a new KPI family.
- Extends u71 first-viewport reflow and u100 surface-quality gate; it does not redesign the first viewport.
- Keeps operator diagnostics in logs, quality history, collapsed diagnostics, and quality pages with reader-safe wording.

**Module path**:
- `src/investo/_internal/surface_quality.py` - add public-prose forbidden/relocation issue codes.
- `src/investo/_internal/public_quality_language.py` - own shared reader-safe quality wording for publisher, visuals, and notifier.
- `src/investo/publisher/segment_reader_format.py` and `src/investo/publisher/reader_format/` - enforce prose boundary after reflow.
- `src/investo/publisher/site_index/`, `src/investo/visuals/`, and `src/investo/notifier/` - sanitize summary/card/Telegram surfaces.
- `tests/unit/internal/test_surface_quality.py`, `tests/unit/publisher/test_segment_reader_surface_quality.py`, `tests/unit/publisher/test_site_index.py`, `tests/unit/visuals/`, and `tests/unit/notifier/`.

**Definition of Done**:
- [ ] Reader-facing body prose and first viewport do not contain operator labels `본문 사용 미집계`, `[데이터부족]`, bare `데이터 부족`, or `확인 소스 미상`.
- [ ] Collapsed diagnostics and quality dashboards may keep machine-readable evidence only behind reader-safe labels.
- [ ] Low-coverage pages render human wording such as "이번 문서는 수집 근거가 제한적입니다" without leaking counters into the narrative.
- [ ] Site index, visual cards, and Telegram summary share the same public-quality projection.
- [ ] Regression fixtures cover 2026-06-17 domestic, US, and crypto segment snippets.

Plan: `aidlc-docs/construction/plans/u108-reader-facing-quality-language-boundary-code-generation-plan.md`.

---

### u109: `domestic-anchor-sanity-quarantine` - Quarantine Implausible Domestic Anchor Values

**Purpose**: Prevent Korean market briefings from publishing precise KOSPI/KOSDAQ, USD/KRW, or bounded large-cap close values when the core price source is missing, stale, internally contradictory, or outside deterministic plausibility bands.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-003 (public publishing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (quality observability), R10, R13

**Existing coverage / deduplication**:
- Extends u55 numeric freshness, u67 domestic channel depth, u70 anchor reconciliation, and u96 quality snapshot sync.
- Does not add a new domestic source adapter and does not replace KRX/Stooq/YFinance collection.
- Does not rewrite LLM prose; it quarantines invalid anchor payloads before render and blocks precise claims that lack usable anchor provenance.

**Module path**:
- `src/investo/orchestrator/pipeline.py` and `src/investo/orchestrator/stage_context.py` - quarantine domestic anchors before table/body/chart/visual-card/Telegram projection.
- `src/investo/publisher/anchor_assertion_gate.py` - block exact domestic index/price claims when anchor trust is invalid.
- `src/investo/publisher/channel_anchor_block.py` - render missing reasons without precise numbers.
- `tests/unit/orchestrator/test_kr_anchors.py`, new `tests/unit/orchestrator/test_domestic_anchor_quarantine.py`, `tests/unit/orchestrator/test_anchor_close_reconcile.py`, `tests/unit/publisher/test_anchor_assertion_gate.py`, `tests/unit/visuals/`, and notifier summary tests.

**Definition of Done**:
- [ ] Domestic anchor rows with impossible values or failed core provenance are omitted or rendered as unavailable, never as closes.
- [ ] Precise domestic index and large-cap price claims are blocked when the matching trusted anchor is quarantined.
- [ ] `quality_history.jsonl`/quality snapshot records distinguish "exact number withheld" from "number absent".
- [ ] Archive regression fixtures cover June 2026 domestic snippets where anchor tables contradicted body claims.
- [ ] Chart sidecars, visual cards, and Telegram summaries do not receive quarantined domestic values.
- [ ] US and crypto anchor behavior remains unchanged except for shared helper imports.

Plan: `aidlc-docs/construction/plans/u109-domestic-anchor-sanity-quarantine-code-generation-plan.md`.

Functional design:
- `aidlc-docs/construction/u109-domestic-anchor-sanity-quarantine/functional-design/domain-entities.md`
- `aidlc-docs/construction/u109-domestic-anchor-sanity-quarantine/functional-design/business-rules.md`
- `aidlc-docs/construction/u109-domestic-anchor-sanity-quarantine/functional-design/business-logic-model.md`

NFR / infrastructure decisions:
- `aidlc-docs/construction/u109-domestic-anchor-sanity-quarantine/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/u109-domestic-anchor-sanity-quarantine/nfr-requirements/tech-stack-decisions.md`

---

### u110: `watchpoint-human-readability-v2` - Make Watchpoint Cards Actionable and Non-Mechanical

**Purpose**: Clean the §⑥ watchpoint card contract so public cards do not repeat template labels, emit `출처: 확인 소스 미상` when source text is present, duplicate upside/downside conditions, or render low-value data-limited placeholders as substantive watchpoints.

**Stories**: FR-002 (AI briefing), FR-004 (compliance-safe actionability), FR-008 (segmented briefing), FR-009 (reader-facing format), FR-012 (plain-language reader aid), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- Depends on u108 for public-safe collapsed-note wording.
- Extends u72/u87/u98 watchpoint renderer and u64 actionability checks.
- Does not change watchlist matching, add source adapters, or create a new matrix shape.
- Keeps the canonical u98 card format and improves field normalization/source extraction inside that format.

**Module path**:
- `src/investo/publisher/watchpoint_matrix.py` - normalize field prefixes, extract sources, reject duplicate up/down triggers, and collapse invalid rows.
- `src/investo/briefing/prompts.py` - tighten Stage 2 watchpoint examples so card fields are populated without repeating labels.
- `tests/unit/publisher/test_watchpoint_matrix.py`, `tests/unit/briefing/test_prompts.py`, and rendered archive fixtures from 2026-06-17.

**Definition of Done**:
- [ ] Public cards never contain `관심 영향: 관심 영향`, `상방 상방`, `하방 하방`, or duplicate up/down condition text.
- [ ] Source names embedded in `현재:` text are promoted to the `출처` field before fallback is used.
- [ ] Rows with no source, no distinct trigger, and data-limited confidence collapse to the existing bounded note.
- [ ] Card rendering stays idempotent and byte-preserves text outside §⑥.
- [ ] Regression tests cover domestic, US, and crypto 2026-06-17 watchpoint snippets.

Plan: `aidlc-docs/construction/plans/u110-watchpoint-human-readability-v2-code-generation-plan.md`.

---

### u111: `watchlist-public-impact-language-cleanup` - Hide Matcher Internals From Public Watchlist Impact

**Purpose**: Stop internal watchlist matcher reasons such as `[boundary-term]`, `[structured-symbol]`, and `[alias:Bitcoin]` from appearing in the public "내 관심 자산 영향" callout, Telegram summary, watchlist daily page, and visual card text.

**Stories**: FR-002 (AI briefing), FR-003 (public publishing), FR-004 (compliance-safe actionability), FR-009 (reader-facing format), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- Extends u64 strict matching and u73 impact center; it does not change match eligibility or Direct/Related/Uncertain/Rejected grouping.
- Preserves diagnostics in collapsed operator pages with R13-safe wording.
- Does not expose `matched_alias` or raw `reason` in public briefing prose.

**Module path**:
- `src/investo/briefing/watchlist.py` - render public labels from match confidence/status instead of raw `match.reason`.
- `src/investo/briefing/watchlist_impact.py` - keep raw reasons only in diagnostic data.
- `src/investo/publisher/watchlist_pages.py` and `src/investo/visuals/` - apply the same public projection.
- `src/investo/notifier/summary.py` - ensure Telegram consumes the sanitized projection.
- `tests/unit/briefing/test_watchlist.py`, `tests/unit/briefing/test_watchlist_impact.py`, `tests/unit/publisher/test_watchlist_daily_page.py`, and `tests/unit/visuals/`.

**Definition of Done**:
- [ ] Public surfaces contain no bracketed matcher reason codes.
- [ ] Public labels use a fixed Korean label map such as `직접 관련`, `관련 맥락`, `관심 목록 보류`, and `수집 제한`.
- [ ] Telegram and visual-card text use the same sanitized public projection as the site.
- [ ] Diagnostic surfaces may include reason codes only inside collapsed R13-safe sections.
- [ ] Existing match/grouping tests prove no matching semantics changed.

Plan: `aidlc-docs/construction/plans/u111-watchlist-public-impact-language-cleanup-code-generation-plan.md`.

---

### u112: `reader-markdown-polish-gate-v2` - Block Remaining Public Markdown and Truncation Artifacts

**Purpose**: Extend the surface-quality gate to block remaining public formatting defects: malformed timestamp watermark brackets, broken signed-number emphasis, nested bold markers, bounded truncation residue, ellipsis inside URL targets, and known Korean particle artifacts.

**Stories**: FR-002 (AI briefing), FR-003 (public publishing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- Extends u51 number bolding, u61 summary gate, u71 reflow, u81 reader-format package, and u100 surface-quality gate.
- Does not add a full Markdown parser, spellchecker, or broad archive backfill.
- Does not change watchpoint semantics; §⑥-specific field cleanup belongs to u110.

**Module path**:
- `src/investo/_internal/surface_quality.py` - add issue codes for watermark syntax, broken emphasis, URL ellipsis, and truncation residue.
- `src/investo/publisher/reader_format/emphasis.py` - treat sign/currency/number/unit as one boldable token.
- `src/investo/publisher/segment_reader_format.py` - run the stricter gate before archive/index writes.
- `tests/unit/internal/test_surface_quality.py`, `tests/unit/publisher/test_reader_format.py`, `tests/unit/publisher/test_segment_reader_surface_quality.py`, and `tests/unit/briefing/test_summary_quality.py`.

**Definition of Done**:
- [ ] Published segment markdown has a valid `**기준 시각**:` watermark line with balanced market-window brackets.
- [ ] Signed numeric tokens such as `-0.04%p`, `-$0.23`, and `+0.74달러(+0.97%)` are never split into malformed bold fragments.
- [ ] Public links never contain `...` or `…` in the href.
- [ ] First-viewport summary lines do not end with bounded truncation residue.
- [ ] `민감도을` is repaired or blocked in public prose; `불강한성` remains covered as a u100 regression.

Plan: `aidlc-docs/construction/plans/u112-reader-markdown-polish-gate-v2-code-generation-plan.md`.

---

### u123: `body-evidence-attribution-reconciliation` - Reconcile Rendered Evidence With Quality Metrics

**Purpose**: Stop current-run quality rows from reporting `본문 사용 미집계`, `figures_presence=0.0`, and fallback-heavy status when the published briefing body clearly contains links, figures, and source-backed facts.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-003 (public publishing), FR-008 (segmented briefing), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- Extends u54/u62/u69/u96 quality accounting and u65 replay; it does not create a new quality dashboard.
- Extends u108 by fixing the operator metric behind the public projection, not by changing reader-safe language.
- Does not change source collection, source severity rules, or the LLM prompt.

**Module path**:
- `src/investo/publisher/evidence_accounting.py` or an existing quality helper - compute bounded rendered evidence counts from markdown links, known source domains, and verified numeric anchors.
- `src/investo/orchestrator/pipeline.py` publish/generate quality assembly - pass rendered evidence counts into `SegmentCoverage`/`QualitySnapshot`.
- `src/investo/publisher/quality_consistency.py` and `src/investo/publisher/briefing_replay.py` - assert metadata agrees with rendered evidence.
- `tests/unit/publisher/test_evidence_accounting.py`, quality consistency tests, replay tests, and a fixture built from the 2026-06-23 bundle.

**Definition of Done**:
- [ ] A segment with rendered source links and source-backed numeric facts records `body_used_count > 0`.
- [ ] `quality_history.jsonl` no longer records `figures_presence=0.0` for a run whose published markdown contains verified core figures.
- [ ] The first-viewport public projection still hides operator counters per u108.
- [ ] Data-limited severity still applies when core sources fail; the fix does not upgrade severity solely because prose has links.
- [ ] Replay and quality-consistency checks fail when markdown evidence and quality metadata contradict each other.

Plan: `aidlc-docs/construction/plans/u123-body-evidence-attribution-reconciliation-code-generation-plan.md`.

---

### u124: `segment-specific-daily-thesis-guard` - Make Daily Thesis Segment-Native

**Purpose**: Prevent the same generic daily thesis line from being stamped across domestic, US, and crypto briefings when each segment has different evidence, time state, and reader action context.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- Extends u57 time/scope reconciliation and u99 daily thesis layer; it does not redesign bundle context.
- Reuses u60 shared macro evidence hardening; it does not add new macro sources.
- Extends u112 only where surface gates catch repeated generic thesis text; it does not add a grammar checker.

**Module path**:
- `src/investo/briefing/context.py` or bundle-context builder - emit segment-specific thesis inputs with evidence references.
- `src/investo/briefing/prompts.py` - require the shared macro bridge to name the segment consequence.
- `src/investo/publisher/reader_format/reflow.py` or `_internal/surface_quality.py` - block identical `오늘의 큰 그림` text across all three segments in one bundle.
- `tests/unit/briefing/test_context.py`, prompt tests, bundle reconciliation tests, and surface-quality tests.

**Definition of Done**:
- [ ] Domestic, US, and crypto briefings cannot publish identical `오늘의 큰 그림` lines for the same date bundle.
- [ ] Each thesis line names a segment-native consequence such as domestic 수급/환율, US sector/rates, or crypto liquidity/policy.
- [ ] Shared macro facts may be reused, but the consequence sentence must differ by segment.
- [ ] A missing segment-specific consequence collapses to a bounded reader-safe low-evidence line rather than a generic cross-market sentence.
- [ ] Regression covers the 2026-06-23 repeated "금리와 달러 변수" line without changing u57 shared macro block rendering.

Plan: `aidlc-docs/construction/plans/u124-segment-specific-daily-thesis-guard-code-generation-plan.md`.

---

### u125: `acronym-glossary-collision-guard` - Prevent Wrong Acronym Expansions

**Purpose**: Stop glossary and inline reader aids from attaching the wrong expansion to a market acronym, such as rendering `ESMA` as `미니S&P선물` instead of the European Securities and Markets Authority.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- Extends u40 glossary and u68 reader-aid residuals; it does not add broad in-body auto-glossing.
- Extends u51 glossary dedupe by validating expansion identity before a term enters the visible glossary.
- Does not add a new acronym source or a language model validation pass.

**Module path**:
- `src/investo/publisher/reader_format/glossary.py` or the current glossary helper - tokenize acronyms with exact boundaries and canonical expansion ids.
- `src/investo/briefing/prompts.py` glossary instruction - forbid composing acronym expansions from substrings.
- `src/investo/_internal/surface_quality.py` - block known wrong expansion pairs in public prose and glossary callouts.
- `tests/unit/publisher/test_glossary.py`, reader-format tests, and a crypto fixture from 2026-06-23.

**Definition of Done**:
- [ ] `ESMA` renders only as `유럽증권시장청`/European Securities and Markets Authority in crypto regulation context.
- [ ] `E-mini S&P`/`ES` futures glossary entries do not match inside `ESMA`.
- [ ] Known wrong acronym-expansion pairs are blocked before archive write.
- [ ] Existing first-use glossary dedupe from u51 remains unchanged for valid terms.
- [ ] Tests cover all-caps acronym boundaries, hyphenated futures names, Korean parenthetical expansions, and idempotent reruns.

Plan: `aidlc-docs/construction/plans/u125-acronym-glossary-collision-guard-code-generation-plan.md`.

---

### u130: `domestic-anchor-level-claim-quarantine-v2` - Gate Bare Index Level Claims and Discontinuous Anchors

**Purpose**: Stop published briefings from asserting precise index/large-cap *level* values (bare closes without movement verbs, e.g. "코스피는 150.00을 나타냈다") when the matching anchor is quarantined or absent, and quarantine anchor values that are discontinuous against the segment's own recent published anchors.

**Stories**: FR-001 (data collection), FR-002 (AI briefing), FR-003 (public publishing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003 (graceful degradation), NFR-006 (quality observability), R13

**Existing coverage / deduplication**:
- Extends u109 anchor trust classification (plausibility bands stay) and the u70 assertion gate (movement-verb claims stay); the 2026-07-02 commit `d4d32d1` already extended the gate to blockquote callouts — keep that behavior.
- Does not add a source adapter, re-verify numeric truth (u55), or change US/crypto anchor behavior.
- Does not re-implement channel-baseline missing reasons (u74) or anchor label registry (u70).

**Module path**:
- `src/investo/publisher/anchor_assertion_gate.py` - add level-claim detection (core anchor label adjacent to a bare numeric close) beside the existing move-claim detection; enforce same-run same-symbol gate-decision consistency across TL;DR/callouts/body.
- `src/investo/orchestrator/domestic_anchor_quarantine.py` - add a `discontinuous` quarantine reason comparing candidate values against the most recent published anchor within 7 calendar days.
- `tests/unit/publisher/test_anchor_assertion_gate.py`, `tests/unit/orchestrator/test_domestic_anchor_quarantine.py`, plus a rendered regression fixture from the 2026-06-30 domestic archive.

**Definition of Done**:
- [ ] A bare level claim about a core anchor symbol whose anchor is quarantined/absent is gated identically to a move claim (2026-06-30 "코스피는 150.00" shape).
- [ ] Index/FX anchor values differing >15% (large-caps >30%) from the most recent published anchor within 7 days quarantine as `discontinuous` (2026-06-30 ^KOSDAQ 477→344 shape).
- [ ] When the gate rewrites a claim about symbol X anywhere in a run, equivalent precise claims about X in other sections of the same document are also gated (2026-06-30 SK하이닉스 TL;DR-vs-§③ contradiction shape).
- [ ] Quality history records the new quarantine reason distinctly; US/crypto outputs are byte-unchanged on existing fixtures.

Plan: `aidlc-docs/construction/plans/u130-domestic-anchor-level-claim-quarantine-v2-code-generation-plan.md`.

---

### u131: `bounded-line-sentence-boundary-truncation` - Bounded Reader Lines End at Sentence Boundaries

**Purpose**: Ensure every bounded reader-facing line (주의할 점 snippet, `그래서 의미는?` meaning line, §⑥ card title) ends at a complete Korean sentence/clause boundary — never mid-clause with `...`/`…` residue or a spliced continuation suffix.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), FR-012 (plain-language reader aid), NFR-003, NFR-006

**Existing coverage / deduplication**:
- Extends the shared bounding algorithm used by u71 (주의할 점 snippet), u76 (meaning lines), and u98/u110 (card titles); caps and line types are unchanged.
- Extends u112 truncation-residue detection so it fires on the production shapes it currently misses; no new issue-code family.
- Does not add new fallback texts: reuses `MEANING_FALLBACK` (u76) and the existing bounded-note collapse (u110).

**Module path**:
- `src/investo/_internal/text.py` - shared sentence-boundary bounding helper (single home).
- `src/investo/publisher/reader_format/meaning.py` - replace the word-boundary + `...` cut.
- `src/investo/publisher/reader_format/reflow.py` - replace the 주의할 점 snippet cut + `본문 참고.` splice.
- `src/investo/publisher/watchpoint_matrix.py` - card title bounding.
- `src/investo/_internal/surface_quality.py` - extend `_looks_truncated_mid_token` region coverage to meaning lines, caution callouts, and §⑥ titles.
- `tests/unit/publisher/test_reader_format_meaning_u76.py`, `tests/unit/publisher/test_watchpoint_matrix.py`, `tests/unit/internal/test_surface_quality.py`, rendered regression fixtures from 2026-06-29 crypto and 2026-06-30 us-equity archives.

**Definition of Done**:
- [ ] No public bounded line ends with `...`/`…` or a mid-clause splice (2026-06-29 "특정 지역의...", 2026-06-30 "매파적 본문 참고." shapes).
- [ ] A first sentence exceeding the cap collapses to the surface's existing deterministic fallback, not a hard cut.
- [ ] The u112 surface gate blocks the legacy residue shapes on rendered segment markdown.
- [ ] All existing caps (`MEANING_MAX_CHARS`, snippet cap) are unchanged and reruns stay idempotent.

Plan: `aidlc-docs/construction/plans/u131-bounded-line-sentence-boundary-truncation-code-generation-plan.md`.

---

### u132: `watermark-window-reader-render-and-gate-alignment` - Readable Collection Window That Survives Repair

**Purpose**: Render the `**기준 시각**` collection window in a reader-readable bracket-free form so downstream bracket repair cannot mangle it, and align the u112 watermark check with the shape production actually emits so the gate fires.

**Stories**: FR-002 (AI briefing), FR-003 (public publishing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-006

**Existing coverage / deduplication**:
- Extends u112's `watermark.window_bracket` issue code (currently keyed on a `수집창` token production never emits — the check never fires); no new issue-code family.
- Does not backfill legacy archives and does not change window computation (u8 market-aware windows stay).

**Module path**:
- `src/investo/briefing/_reader_enhance/enhancement.py` - replace the half-open `[start, end)` math notation (its lone `[` is inherently bracket-unbalanced, so bracket repair strips it, leaving the dangling `)` seen in every published briefing) with `수집창 {start} ~ {end}`.
- `src/investo/_internal/surface_quality.py` - update `_WATERMARK_LINE_RE` and `_bad_watermark_window` to the new shape; add a blocking match for the legacy dangling-paren shape.
- `tests/unit/internal/test_surface_quality.py`, `tests/unit/briefing/` enhancement tests, rendered regression from the 2026-06-30 archives.

**Definition of Done**:
- [ ] Published watermark lines contain a balanced, bracket-free `수집창 start ~ end` window.
- [ ] The legacy `..., ...Z)` dangling-paren shape is a blocking surface-quality issue on new writes.
- [ ] The watermark line is byte-stable through the full reader-format chain (repair passes leave it untouched).
- [ ] Legacy committed archives are not rewritten.

Plan: `aidlc-docs/construction/plans/u132-watermark-window-reader-render-and-gate-alignment-code-generation-plan.md`.

---

### u133: `watchlist-registry-source-impact-suppression` - Registry Metadata Is Not a Watchlist Impact

**Purpose**: Stop static reference/registry sources (`nasdaq-symbol-directory`, `sec-company-facts`) from creating public "직접 관련" watchlist impact rows, inflating the "N건 확인" count, and being narrated as §⑤ pseudo-news ("상장 정보가 갱신됐으나 …").

**Stories**: FR-002 (AI briefing), FR-004 (compliance-safe actionability), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- u64 matching semantics and u73 Direct/Related/Uncertain/Rejected grouping are unchanged; this adds a source-class routing input, not a matcher change.
- u111 public label projection is unchanged; u101 fact-cache/entity-guard continues consuming registry sources for verification.
- u104 keeps collecting these sources; nothing is removed from collection or diagnostics.

**Module path**:
- `src/investo/_internal/source_specs.py` - add a `reference_registry` spec flag (initial fixed set: `nasdaq-symbol-directory`, `sec-company-facts`).
- `src/investo/briefing/watchlist_impact.py` - route registry-source matches to diagnostics only; exclude from public impact rows and the "N건 확인" count.
- `src/investo/briefing/prompts.py` - Stage-2 rule: registry metadata items are entity evidence, not §⑤ narrative events, unless a same-run non-registry item corroborates the ticker.
- `tests/unit/briefing/test_watchlist_impact.py`, `tests/unit/sources/test_source_specs.py`, prompt tests, rendered regression from the 2026-06-30 us-equity archive.

**Definition of Done**:
- [ ] The public impact callout count excludes registry-source rows (2026-06-30 "14건 확인" listing-metadata shape).
- [ ] Registry-source matches appear only in collapsed diagnostics with R13-safe wording.
- [ ] §⑤ no longer renders a registry-only "상장 정보 갱신" narrative block.
- [ ] Telegram/visual-card impact counts agree with the site callout; u73 grouping tests prove matching semantics unchanged.

Plan: `aidlc-docs/construction/plans/u133-watchlist-registry-source-impact-suppression-code-generation-plan.md`.

---

### u134: `callout-and-diagnostic-line-composition-repair` - Well-Formed Deterministic Callout Composition

**Purpose**: Fix four deterministic composition defects visible in every recent briefing: (a) `핵심 동인` heading+sentence concatenation without a separator, (b) `오늘의 결론` low-coverage suffix spliced without punctuation, (c) the collapsed-diagnostics `소스 카운트` line repeating the public pointer sentence three times in place of numeric counters, (d) crypto funding rate rendered as `0.0001000000000000`.

**Stories**: FR-002 (AI briefing), FR-008 (segmented briefing), FR-009 (reader-facing format), NFR-003, NFR-006

**Existing coverage / deduplication**:
- u61/u71/u127 summary extraction/reflow/reject-predicate contracts stay; this repairs producers, adding no new gate family.
- u108's public-language boundary stays for first-viewport/public regions; the fix restores numeric counters only *inside* the collapsed `<details>` diagnostics where u108 permits operator counts.
- u66/u74 indicator table structure is unchanged; only Decimal normalization changes.

**Module path**:
- `src/investo/briefing/_reader_enhance/enhancement.py` - `핵심 동인` driver = `{heading} — {first sentence}` with an explicit ` — ` separator.
- `src/investo/publisher/reader_format/reflow.py` - low-coverage suffix appended as its own sentence (reuse `PUBLIC_LOW_COVERAGE_TEXT`, not the inline fragment); `소스 카운트` slots render numeric counters inside diagnostics, with the pointer sentence at most once per line.
- `src/investo/publisher/channel_anchor_block.py` - normalize funding-rate Decimals to shortest exact form.
- `tests/unit/publisher/test_reader_format.py`, `tests/unit/publisher/test_channel_anchor_block.py`, enhancement tests, rendered regressions from 2026-06-29/30 archives.

**Definition of Done**:
- [ ] `핵심 동인` renders heading and sentence with a visible separator (2026-06-30 "…마감 나스닥 기사에 따르면…" shape eliminated).
- [ ] The low-coverage note renders as its own complete sentence after the preceding period (no "…관찰된다. 수집 근거가 제한적입니다" splice).
- [ ] The collapsed `소스 카운트` line shows numeric `0건/실패/본문 사용` counters; the pointer sentence appears at most once.
- [ ] Funding rates render without trailing-zero noise (`0.0001`).

Plan: `aidlc-docs/construction/plans/u134-callout-and-diagnostic-line-composition-repair-code-generation-plan.md`.

---

### u135: `watchpoint-current-value-and-deterministic-fallback` - Cards Carry Real Values; Rich Runs Don't Go Empty

**Purpose**: Make §⑥ cards show an actual snapshot value in `현재:` (not a source name), and synthesize at most two bounded observational cards from already-reconciled deterministic data when all LLM cards are filtered out but the run demonstrably has concrete signals.

**Stories**: FR-002 (AI briefing), FR-004 (compliance-safe actionability), FR-008 (segmented briefing), FR-009 (reader-facing format), FR-012, NFR-003, NFR-006, R13

**Existing coverage / deduplication**:
- u72 matrix contract, u87 rehabilitation, u98 card shape, and u110 field cleanup/filters all stay; this adds value resolution and a bounded deterministic fallback only.
- DEBT-074's graceful `데이터부족` collapse remains correct for genuinely empty payloads.
- No new LLM call, no matrix redesign, no watchlist matching change.

**Module path**:
- `src/investo/publisher/watchpoint_matrix.py` - resolve `현재:` values from the reconciled indicator/anchor payload by symbol/indicator key (anchor close, 24h range, F&G value, CFTC net-% rows); rows whose value cannot resolve keep hard-failing per u110.
- `src/investo/publisher/watchpoint_matrix.py` (or a sibling module) - deterministic synthesis: when zero LLM cards survive AND the payload contains ≥1 of {reconciled core anchor with range data, CFTC positioning row, F&G value}, emit ≤2 cards from closed Korean templates pinned in the plan; 신뢰도 derives from data freshness (weekly-delayed → `보통`).
- `src/investo/orchestrator/pipeline.py` - pass the reconciled payload into the §⑥ conversion; re-run `scan_compliance` over synthesized cards.
- `tests/unit/publisher/test_watchpoint_matrix.py`, orchestrator stage tests, rendered regressions from 2026-06-29 crypto (`현재: CoinGecko BTC` shape) and 2026-06-30 us-equity (empty §⑥ despite CFTC divergence).

**Definition of Done**:
- [ ] No public card renders a source label in the `현재:` slot; values resolve from reconciled data or the row is filtered.
- [ ] A run with reconciled anchor/CFTC/F&G data and zero surviving LLM cards renders 1-2 synthesized observational cards instead of the bounded note.
- [ ] Synthesized cards pass `scan_compliance` and the u64 structure regexes; segments with genuinely empty payloads keep the bounded note.
- [ ] Card shape, 신뢰도 closed set, and u110 filters are unchanged for LLM-produced cards.

Plan: `aidlc-docs/construction/plans/u135-watchpoint-current-value-and-deterministic-fallback-code-generation-plan.md`.

---

### u136: `feed-image-metadata-harvest` - Collect Real-Article Image References From Feeds Already Fetched

**Purpose**: Start the "실제 뉴스 이미지 활용" track (2026-07-17 user request) at its safe base: extract per-item image references (`media:content` / `media:thumbnail` / `media:credit`) from the news feed XML the pipeline already downloads, into `NormalizedItem.raw_metadata` image keys plus per-source image-yield diagnostics. No new HTTP requests, no binary downloads, no page scraping.

**Stories**: FR-001 (data collection), FR-008 (segmented briefing), NFR-002 (no paid APIs — no new calls at all), NFR-006, R8, R13

**Existing coverage / deduplication**:
- `visuals/external_image.py` already recognizes `image_url`/`thumbnail_url` raw_metadata keys but has no producer; u136 aligns to that key contract without calling or enabling the dormant fetch path.
- u86 curated library is a separate pre-cleared static channel; u136 harvests daily news candidates and replaces nothing.
- RSS adapters currently discard media namespaces by design (`yonhap_market.py`, `sec_edgar_8k.py` docstrings) — u136 reverses that only for verified image-bearing feeds.

**Module path**:
- `src/investo/sources/_xml_namespaces.py` - add `MEDIA_NS` (`http://search.yahoo.com/mrss/`) constants.
- `src/investo/sources/_feed_media.py` (new) - `extract_feed_image(item) -> FeedImageRef | None`, first-image-only, http(s)-only, capped fields.
- `src/investo/sources/yonhap_market.py`, `yahoo_finance_news.py`, `theblock_crypto.py` - wire the helper into item parsing (live-probed 2026-07-17: these three feeds carry per-item images; CNBC/Nasdaq do not).
- Aggregator per-source `source returned` diagnostics - add `image_items` count.
- `tests/unit/sources/test_feed_media.py` (new), adapter tests + re-recorded R10 fixtures, `test_external_image.py` non-contamination invariant.

**Definition of Done**:
- [ ] Image-bearing items from the three verified feeds carry `image_url` (+width/height/mime/credit when available) in raw_metadata; imageless items carry no image keys.
- [ ] No adapter emits license/attribution/author/allowed_use keys, and the dormant external-image fetch path cannot trigger from harvested metadata even with the env flag on (regression-pinned).
- [ ] Zero new HTTP requests (feed fetch count/targets unchanged).
- [ ] Per-source diagnostics expose image-bearing item counts.
- [ ] R8 (strings/ints, no nesting) and R13 hold; existing adapter behavior regressions green.

Plan: `aidlc-docs/construction/plans/u136-feed-image-metadata-harvest-code-generation-plan.md`.

---

### u137: `image-candidate-registry-and-licensed-store` - Persist Image Candidates; Store Binaries Only With Clearance

**Purpose**: Persist u136's harvested image references into a per-date candidate ledger with a recurrence index ("자주 쓰이는 이미지" signal), an explicit rights state machine (`metadata-only` default / `cleared` / `blocked`), and a content-addressed binary store that fetches only operator-cleared, license-manifested candidates — metadata for everything, binaries only with clearance, on a public repo/Pages/Telegram surface.

**Stories**: FR-001, FR-006 (permanent archive), NFR-002, NFR-006, NFR-007 (R13), R8

**Existing coverage / deduplication**:
- Reuses u19 `ExternalAssetManifest` + policy gates, u24 provenance manifests, `external_image.py` fetch internals (signature/byte checks), u86 deferred-state-machine and CI-gate precedents, u78 atomic-write primitives.
- Does not change `EXTERNAL_IMAGE_SCRAPING_ENABLED` global default or u86 curated policy; cleared license-clean alternatives still belong in the u86 library.
- Depends on u136; blocked without it.

**Module path**:
- `src/investo/visuals/image_library.py` (new) - `ImageCandidateRecord`, ledger append (`archive/_meta/image_candidates/{YYYY}/{date}.jsonl`), recurrence index, rights-state resolution from operator clearance/block files, license-gated fetch into `assets/images/{hash[:2]}/{hash}.{ext}` + provenance sidecar.
- `src/investo/orchestrator/pipeline.py` - failure-isolated post-routing stage; outputs join publish staging.
- `scripts/check_image_store.py` (new) - CI gate mirroring `check_curated_assets.py`: manifest completeness, no orphans, 2MB/file + 50MB/store budgets, R13 scan.
- CONTRIBUTING runbook - operator clearance procedure (investo-ops surface).
- FD (R/E/I) + NFR (AC) documents required before code (new persisted artifact + rights state machine + storage budget).

**Definition of Done**:
- [ ] Runs with image-bearing items leave a deterministic per-date ledger and updated recurrence index; reruns idempotent.
- [ ] Binaries are stored only for `cleared` + env-opt-in + policy-passing candidates; default posture stores zero binaries.
- [ ] Every stored binary has a provenance sidecar and clearance manifest, enforced by the CI gate with byte budgets.
- [ ] Image-stage failure never fails briefing generation/publish.
- [ ] Same-URL recurrence across days is queryable via `seen_count`.

Plan: `aidlc-docs/construction/plans/u137-image-candidate-registry-and-licensed-store-code-generation-plan.md`.

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
