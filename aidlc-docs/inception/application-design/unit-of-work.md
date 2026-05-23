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

**Purpose**: Add crypto-native reader signals (펀딩비, 미결제약정, 24h 청산, BTC 도미넌스, 공포·탐욕 지수, exchange netflow where free) and replace the unsuitable "전일 종가" frame with a UTC 24h snapshot frame for the crypto channel. Reader-facing feature gap raised independently by the 크립토 투자자 + 신뢰성 personas in the 2026-05-24 review.

**Stories**: FR-001 (수집), FR-002 (AI 시황 작성), FR-008 (소스 확장성), FR-009 (reader-facing format)

**Module path**:
- `src/investo/sources/` — new free crypto-indicator adapters (Alternative.me Fear&Greed, CoinGecko dominance, Coinglass public funding/OI/liquidation where free-reachable)
- `src/investo/briefing/prompts.py` — crypto 24h-snapshot framing scope
- `src/investo/publisher/anchor_table.py` — crypto snapshot columns (UTC, 24h)

**Definition of Done**:
- [ ] At least Fear&Greed + BTC 도미넌스 land from confirmed free sources (per-indicator reachability verified in the plan).
- [ ] Crypto channel uses a UTC 24h snapshot frame, not "전일 종가".
- [ ] No paid key; per-source isolation; `defusedxml` for any XML; channel separation and disclaimer untouched.

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
