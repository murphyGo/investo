# Technical Environment: Investo

## Technology Stack

### Runtime & Language
- **Python 3.11+** (사용자 선호, 데이터/AI 생태계)
- 의존성 관리: `uv` 또는 `pip` + `requirements.txt` (lock file 포함)

### LLM Integration
- **Claude Code CLI** — GitHub Actions에서 setup token으로 인증해 비대화형(`-p`) 호출
- **Anthropic API key 직접 사용 금지** (별도 요금 회피 — NFR-002)
- 토큰은 GitHub Secrets로 주입

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
  - 데이터 소스 API key (사용 시)

## Existing Systems

- **없음** (greenfield 프로젝트)

## Technical Constraints

- LLM 호출은 Claude Code CLI로만 (Anthropic SDK 직접 호출 금지)
- 일 1회 배치 (실시간 아님)
- GitHub Actions 단일 job 실행 시간 한도 (≤ 10분 NFR-001)
- 무료 데이터 소스의 rate limit 및 안정성 한계
- public repo 운영 가정 (코드/시황 모두 공개; 시크릿만 비공개)
- Claude Code subscription 보유 가정 (token 발급 가능)
