# About Investo

**Investo**는 1인용 자동화 도구로, 무료 공개 데이터를 수집해 Claude
Code CLI로 한국어 7섹션 시황을 만들고, GitHub Pages 정적 사이트에
영구 보관 + 공개 Telegram 채널로 푸시합니다.

## 운영 원칙

- **월 운영비 $0**: Claude Code 구독 외 추가 LLM API 비용 없음. 모든
  데이터 소스 무료 tier 한도 내 사용. GitHub Actions 무료 한도 내
  운영.
- **자동화 우선**: 매일 KST 평일 07:00 / 토요일 09:00에 GitHub
  Actions cron으로 자동 실행. 운영자 개입은 실패 시 1:1 Telegram
  알림을 통해서만.
- **공개 + 영구 보관**: 모든 시황은 git commit으로 영구 저장.
  과거 시황을 회고용으로 자유롭게 열람 가능.

## 데이터 소스

현재 통합된 무료 데이터 소스:

- **FOMC RSS** — 연준 발표문 + 의장 발언 일정

(추후 추가 예정: 주가/지수, 크립토 시세, 거시 지표 (FRED 등),
주요 기업 뉴스, 실적 캘린더)

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
