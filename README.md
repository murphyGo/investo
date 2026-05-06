# Investo

> 매일 국내 증시·미국 증시·크립토 데일리 시황을 자동 생성·게시하는 1인용 자동화 도구

## Overview

매일 직접 뉴스를 검색하고 정리하는 시간 비용을 0으로 만들기 위해, 무료 공개 데이터 소스에서 전일 시장 데이터를 수집해 일관된 한국어 시황을 자동 생성한다. 결과는 GitHub Pages 정적 사이트에 영구 보관되고, 공개 Telegram 채널로 푸시된다. 운영비는 월 $0 (Claude Code 구독 외).

## Features

- 매일 KST 평일 07:00 / 토요일 09:00 자동 실행 (GitHub Actions cron)
- 무료 데이터 소스 다수 통합 수집 (뉴스, 시세, 거시 지표, 연준 캘린더, 실적)
- Claude Code CLI 기반 한국어 시황 자동 생성 (국내 증시, 미국 증시, 크립토 각각 ①~⑥ 섹션 + 공통 면책조항)
- GitHub Pages 정적 사이트에 영구 보관 (`archive/{segment}/YYYY/MM/`)
- 공개 Telegram 채널에 세 세그먼트 요약과 링크를 한 메시지로 푸시 + 운영자 실패 알림 (1:1 chat 분리)
- Plugin 구조로 신규 데이터 소스 추가 = 단일 모듈 + 등록 1줄

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| LLM Runtime | Claude Code CLI (subprocess) |
| HTTP | httpx (async) |
| Validation | pydantic v2 |
| Static Site | MkDocs Material → GitHub Pages |
| Notification | Telegram Bot API |
| Scheduler | GitHub Actions cron |

## Getting Started

### Prerequisites

- Python 3.11+
- Claude Code CLI (Claude Max/Pro subscription)
- GitHub repository (public 권장 — Actions 무제한)
- Telegram Bot 1개 (BotFather로 토큰 발급)

### Required Secrets (GitHub Actions)

| Secret | Purpose |
|--------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code CLI 인증 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 인증 |
| `TELEGRAM_BRIEFING_CHANNEL_ID` | 공개 시황 채널 (모든 구독자) |
| `TELEGRAM_OPERATOR_CHAT_ID` | 운영자 1:1 실패 알림 |
| `SITE_URL_BASE` | GitHub Pages 시황 URL base |

### Local Development

```bash
git clone git@github.com:murphyGo/investo.git
cd investo

# Python venv + dependencies
uv sync --extra dev --extra docs

# Lint / Type / Test
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest -q
uv run mkdocs build --strict

# Manual run (with env set)
uv run python -m investo
```

로컬 live run에는 위 GitHub Actions secrets와 동일한 환경 변수가 필요하다.

## Development

This project uses AI-DLC methodology with Claude Code skills.

### Quick Start

```bash
claude
/dev-investo
```

### Development Workflow

1. `/dev-investo` — 다음 task 가져오기 (AIDLC Construction stage 진행)
2. Implement — `docs/requirements.md` + `docs/DESIGN.md` 따라 구현
3. `/code-review git` — 커밋 전 리뷰
4. `/tech-debt` — 발견된 이슈 등록
5. Commit & push

### Key Documents

| Document | Description |
|----------|-------------|
| `aidlc-docs/aidlc-state.md` | AIDLC state and progress |
| `docs/requirements.md` | Detailed requirements (FR + NFR) |
| `docs/DESIGN.md` | Architecture summary |
| `aidlc-docs/inception/application-design/` | Detailed component / unit design |

## Disclaimer

본 도구가 생성하는 시황은 **투자 자문이 아니라 정보 제공**이며, 손실에 대한 책임은 사용자 본인에게 있다. 모든 시황 본문에 면책조항이 자동 삽입된다.

## License

MIT
