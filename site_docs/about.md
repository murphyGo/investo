# About Investo

**Investo**는 1인용 자동화 도구로, 무료 공개 데이터를 수집해 Claude
Code CLI로 국내 증시·미국 증시·크립토 한국어 7섹션 시황을 만들고,
GitHub Pages 정적 사이트에 영구 보관 + 공개 Telegram 채널로 푸시합니다.

## 운영 원칙

- **월 운영비 $0**: Claude Code 구독 외 추가 LLM API 비용 없음. 모든
  데이터 소스 무료 tier 한도 내 사용. GitHub Actions 무료 한도 내
  운영.
- **자동화 우선**: 매일 KST 평일 07:00 / 토요일 09:00에 GitHub
  Actions cron으로 자동 실행. 운영자 개입은 실패 시 1:1 Telegram
  알림을 통해서만.
- **공개 + 영구 보관**: 모든 시황은 git commit으로 영구 저장.
  과거 시황을 회고용으로 자유롭게 열람 가능.

## 7섹션 구성

각 세그먼트 시황은 다음 7개 섹션으로 구성됩니다:

1. **요약** — 전체 흐름 한 줄
2. **전일 핵심 이슈** — 시장 영향이 컸던 이벤트
3. **섹터/수급 동향** — 자금 흐름 + 강세/약세 섹터
4. **지표·이벤트** — 거시 지표 + 예정 이벤트
5. **주요 종목** — 큰 변동을 보인 종목들
6. **오늘의 관전 포인트** — 다음 거래일에 주목할 사항
7. **면책조항** — 투자 자문이 아님을 명시

## 데이터 소스

현재 통합된 무료 데이터 소스:

- **가격**: yfinance 가격 데이터, CoinGecko 크립토 가격
- **거시/연준**: FRED 거시 지표, FOMC RSS
- **미국 뉴스/공시**: Yahoo Finance News, CNBC Top News, SEC EDGAR 8-K,
  Nasdaq Stocks News
- **일정/실적**: Nasdaq Earnings Calendar
- **국내/크립토 뉴스**: Yonhap Market, The Block Crypto

### 현재 한계

- 국내 증시는 현재 뉴스 중심 커버리지라 가격·수급 데이터가 부족할 수 있습니다.
- 무료 공개 소스만 사용하므로 특정 소스가 0건을 반환하거나 지연될 수 있습니다.
- 각 시황 상단의 데이터 상태가 `정상`, `부분`, `부족`으로 표시됩니다.

## 사이트 탐색

- [Home](index.md) — 오늘 자동 발행된 세 개 세그먼트의 결론 요약 카드.
- [Archive 인덱스](archive/index.md) — 발행 캘린더 히트맵 + 세그먼트별
  / 레거시 단일 시황 진입.
- 세그먼트별 색인:
  [국내 증시](archive/domestic-equity/index.md) ·
  [미국 증시](archive/us-equity/index.md) ·
  [크립토](archive/crypto/index.md).
- [주차별 회고](archive/weekly/index.md) — 토요일 09:00 KST cron이
  지난 5영업일의 결론을 모아 한 페이지로 정리합니다.

## 기술 스택

- **언어**: Python 3.11+
- **LLM 런타임**: Claude Code CLI (Anthropic SDK 직접 호출 금지)
- **HTTP**: httpx (async)
- **검증**: pydantic v2
- **정적 사이트**: MkDocs Material → GitHub Pages
- **알림**: Telegram Bot API (raw HTTP)
- **스케줄러**: GitHub Actions cron
- **저장소**: Git repo (markdown 파일)

## 면책조항

> 본 시황은 정보 제공 목적이며 **투자 자문이 아닙니다**.
>
> 특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다. 투자
> 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며, 본 시황의
> 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지
> 않습니다.

## 소스코드

[GitHub](https://github.com/murphyGo/investo) (MIT License)
