# Technical Environment: Investo

## Technology Stack

### Runtime & Language
- **Python 3.11+** (사용자 선호, 데이터/AI 생태계)
- 의존성 관리: `uv` 또는 `pip` + `requirements.txt` (lock file 포함)

### LLM Integration
- **Claude Code CLI** — GitHub Actions에서 setup token으로 인증해 비대화형(`-p`) 호출
- **Anthropic API key 직접 사용 금지** (별도 요금 회피 — NFR-002)
- 토큰은 GitHub Secrets로 주입

### Visual AI Integration
- **OpenAI Responses API image generation** — 선택 기능. `INVESTO_OPENAI_VISUALS=1` 및 `OPENAI_API_KEY`가 있을 때만 시황용 AI PNG를 생성한다.
- 기본 mainline model은 `INVESTO_OPENAI_VISUAL_MODEL=gpt-5.5`, 이미지 tool model은 `INVESTO_OPENAI_IMAGE_TOOL_MODEL=gpt-image-1.5`로 두되 환경변수로 교체 가능하게 유지한다.
- OpenAI 키가 없거나 API가 실패하면 기존 deterministic SVG 카드만 게시한다.
- 실제 뉴스/회사 이미지를 긁어오지 않는다. 생성 프롬프트는 로고, 뉴스 사진, 저작권성 기사 이미지, 투자 조언 문구를 금지한다.
- **Licensed external image fetch** — 선택 기능. `INVESTO_EXTERNAL_IMAGE_ASSETS=1`일 때만 `NormalizedItem.raw_metadata`에 이미지 URL, 라이선스, 저작자, attribution, 재게시 허용 문구가 모두 있는 이미지를 다운로드한다. `INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS`로 허용 host를 좁힐 수 있다.

### Data Layer
- **httpx** — async HTTP 클라이언트 (timeout/retry 친화적)
- **pydantic v2** — 외부 API 응답 모델링·검증
- 영속화: **Git repo 내 markdown 파일** (`archive/{segment}/YYYY/MM/YYYY-MM-DD.md`; 과거 단일 시황은 `archive/YYYY/MM/YYYY-MM-DD.md`)

### Web Publication
- **MkDocs Material** — 정적 사이트 생성기 (markdown 친화)
- **GitHub Pages** — 호스팅 (무료, public repo)

### Notification
- **Telegram Bot API** — raw HTTP 호출 (의존성 최소)
- Bot 토큰은 GitHub Secrets

### Scheduling & CI
- **GitHub Actions** — cron 트리거 + workflow_dispatch
- 평일 KST 07:00 (UTC 22:00 전일) / 토요일 KST 09:00

### Quality Tools
- **ruff** — lint + format
- **mypy** — strict type check
- **pytest** — unit test
- **hypothesis** — PBT (partial: 순수 함수 + 직렬화 round-trip)

## Development Environment

- macOS / Linux 개발 가정
- Python 3.11+ 로컬 설치
- `uv venv` 또는 `python -m venv` 가상환경
- 로컬 실행 시 `claude` CLI 설치 필요 (Claude Code subscription)
- `.env` 또는 `direnv`로 로컬 시크릿 (BOT_TOKEN, CLAUDE_CODE_OAUTH_TOKEN 등) — `.gitignore`에 포함

## Deployment Target

- **Primary**: GitHub Actions (cron 자동 실행)
- **Output channels**:
  - GitHub Pages 정적 사이트 (영구 보관)
  - Telegram 공개 채널/그룹 (한 메시지에 국내 증시, 미국 증시, 크립토 링크 포함)
- **Secrets**: 모두 GitHub Secrets에 저장
  - `CLAUDE_CODE_OAUTH_TOKEN` (Claude Code 인증)
  - `TELEGRAM_BOT_TOKEN` (Bot API)
  - `TELEGRAM_BRIEFING_CHANNEL_ID` (공개 시황 채널/그룹)
  - `TELEGRAM_OPERATOR_CHAT_ID` (운영자 1:1 실패 알림)
  - `SITE_URL_BASE` (GitHub Pages base URL; 예: `https://murphygo.github.io/investo`)
  - `OPENAI_API_KEY` (선택: AI 시황 이미지 생성)
  - `INVESTO_EXTERNAL_IMAGE_ASSETS` (선택: 라이선스 명시 외부 이미지 다운로드)
  - `INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS` (선택: 외부 이미지 host allow-list)
  - `CONGRESS_API_KEY` (선택: Congress.gov 공식 법안 action 수집; 미설정 시 해당 adapter만 graceful degradation)
  - `INVESTO_CONGRESS_BILLS` (선택: Congress.gov 감시 bill id 목록, 예: `119/hr/3633`)
  - `INVESTO_SENATE_BANKING_WATCH_URLS` (선택: Senate Banking 공식 crypto-policy watch URL 목록)
  - `INVESTO_HOUSE_FINANCIAL_SERVICES_RSS_URLS` (선택: House Financial Services 공식 RSS URL 목록)
  - `INVESTO_STOOQ_KR_SYMBOLS` (선택: 국내 지수/환율 fallback 심볼 목록, 기본 `^KOSPI,^KOSDAQ,KRW=X`)
  - `INVESTO_STOOQ_KR_CONCURRENCY` (선택: 위 어댑터 동시 fetch 수, 기본 2)
  - 데이터 소스 API key (사용 시)

### Free data sources (no-key) — domestic depth (u67)
- **`stooq-kr-market` 어댑터** — KOSPI 종가·원/달러 환율은 Stooq 무인증 CSV(`^kospi`, `usdkrw`)에서, KOSDAQ는 Stooq가 `N/D`를 반환하므로 연합뉴스 마켓+ RSS 헤드라인 숫자 파싱(`defusedxml`)에서 수집한다. yfinance `KRW=X`는 GitHub Actions IP에서 HTTP 429를 받아 사용하지 않는다.
- **국내 지수 종가 precedence**: `fsc-krx-index-price`(공식 KRX) → Stooq `^kospi` → 연합뉴스 숫자 파싱. KOSDAQ는 공식 KRX → 연합뉴스 숫자 파싱(스투크 미보유).
- **원/달러 precedence**: Stooq `usdkrw`(no-key) — `usd_krw` core fact를 채운다.

### Free data sources (no-key) — crypto channel depth (u66)
- **`alternative-fng` 어댑터** — Crypto Fear & Greed 지수를 Alternative.me 무인증 JSON(`https://api.alternative.me/fng/?limit=1`)에서 수집한다. `indicator=fear_greed` 태그, `value`(0-100)·`classification`.
- **`coingecko-global-market` 어댑터** — BTC 도미넌스 + 전체 시총을 CoinGecko 무인증 `/api/v3/global`에서 수집한다. `indicator=global_market` 태그, `btc_dominance_pct`·`total_market_cap_usd`·`market_cap_change_24h_pct`.
- **`bybit-derivatives` 어댑터 (+ `okx-derivatives` fallback)** — BTC 펀딩비 + 미결제약정(OI)을 수집한다. **precedence: Bybit v5 `tickers`(primary, 무키·geo-safe) → OKX public funding-rate/open-interest(fallback)**. `indicator=btc_funding`/`btc_oi` 태그, `funding_source`/`oi_source` ∈ {bybit, okx}. **Binance fapi는 primary로 쓰지 않는다** — GitHub Actions IP에서 HTTP 451 geo-block.
- **DeFi TVL / 스테이블코인 공급**: 기존 `defillama-market-structure` 어댑터 재사용(무키).
- **scope-out (무키 free 소스 미확정)**: 24h 청산(Coinglass — API key 필요), 거래소 순유출입(CryptoQuant/Glassnode — 유료/키 필요). 값 날조 금지 — 크립토 지표 블록에서 `무료 검증 소스 미확정` 행으로만 표기. TECH-DEBT(DEBT-071/072 예상)로 closeout에서 등록.

## Existing Systems

- **없음** (greenfield 프로젝트)

## Technical Constraints

- LLM 호출은 Claude Code CLI로만 (Anthropic SDK 직접 호출 금지)
- OpenAI 이미지 생성은 선택 기능이며, 실패 시 deterministic SVG fallback을 유지해야 함
- 외부 이미지는 라이선스 manifest가 없는 경우 절대 재게시하지 않음
- 일 1회 배치 (실시간 아님)
- GitHub Actions 단일 job 실행 시간 한도 (≤ 10분 NFR-001)
- 무료 데이터 소스의 rate limit 및 안정성 한계
- public repo 운영 가정 (코드/시황 모두 공개; 시크릿만 비공개)
- Claude Code subscription 보유 가정 (token 발급 가능)
