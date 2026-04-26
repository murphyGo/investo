# Personas: Investo

**Date**: 2026-04-26
**Source**: Story Generation Plan Q1 (decision: A — two personas)

---

## P1: Operator-User (운영자 겸 1차 사용자)

| Attribute | Value |
|-----------|-------|
| Identity | 본인 (1인 — 운영자 + 1차 사용자 동일 인물) |
| Role | 시스템 운영자 + 매일 시황 소비자 |
| Tech literacy | High — Python 개발자 |
| Devices | 모바일 (Telegram) + 데스크톱 (GitHub Pages, GitHub Actions UI) |

### Context
한국 거주 개인 투자자. 미국 주식·크립토(+ 코스피) 관심. 아침 출근 전·후 짧은 시간에 시장 상황을 파악하고 싶다. Python·GitHub·CI 운영 경험 있음. 운영비를 0에 가깝게 유지하려는 강한 동기.

### Goals
- 매일 같은 시각 자동으로 한국어 시황을 받는다.
- 사실 오류 없이 핵심 이슈를 빠뜨리지 않는다.
- 운영비 월 0원을 유지한다.
- 데이터 소스 추가/제거를 단순한 코드 변경으로 처리한다.
- 파이프라인 실패를 즉시 인지하고 조치한다.

### Pain Points
- 직접 뉴스 검색·정리하면 매일 30~60분 소요.
- 무료 데이터 API의 rate limit·다운타임 위험.
- LLM 환각으로 인한 잘못된 정보 → 투자 판단 오류 위험.
- 공개 채널에 운영 노이즈(실패 알림 등)가 섞이면 일반 구독자가 떠난다.

### Channels
- GitHub Pages 사이트 (전체 시황 + 과거 archive)
- 공개 Telegram 시황 채널 (요약 푸시)
- 운영자 1:1 Telegram chat (실패 알림 전용)
- GitHub Actions UI (수동 재실행, 로그 확인)
- Git/IDE (코드/시황 markdown 직접 편집)

### Frequency
- **시황 소비**: 매일 (KST 평일 07:00 직후, 토요일 09:00 직후)
- **운영 작업**: 월 1~2회 (소스 추가, 디버깅, 포맷 조정)

---

## P2: Public Reader (지인/익명 방문자)

| Attribute | Value |
|-----------|-------|
| Identity | 본인이 URL/채널을 공유한 지인, 또는 검색·SNS 등으로 사이트를 발견한 익명 방문자 |
| Role | 시황 열람자 (선택적 텔레그램 채널 구독자) |
| Tech literacy | 가변 — 일반 인터넷 사용자 |
| Devices | 주로 모바일, 가끔 데스크톱 |

### Context
한국어로 정리된 미국 주식·크립토 시황을 빠르게 얻고 싶다. 인증 절차 없이 보고 싶고, 자기 시간에 맞춰 푸시로 받고 싶을 때 채널에 join한다.

### Goals
- 매일/필요할 때 한국어 시황을 빠르게 훑는다.
- 과거 시황도 검색·날짜로 찾을 수 있다.
- 가입·결제 없이 무료로 본다.

### Pain Points
- 시황이 누락되거나 어제 게시가 없으면 신뢰도 하락.
- 모바일에서 사이트 로딩이 느리거나 가독성이 떨어지면 떠난다.
- 너무 길거나 영어 위주면 부담.

### Channels
- GitHub Pages 사이트 (주 채널)
- 공개 Telegram 시황 채널 (옵션 — 본인이 join한 경우)

### Frequency
- 가변. 매일 ~ 가끔. 인증·구독 관리 없음.

### Notes
- Public Reader는 **운영 알림(FR-007), GitHub Actions UI, 운영자 1:1 chat 등 어느 것도 사용하지 않는다.**
- 향후 분석 댓글·리액션 등 인터랙션은 Out of Scope.

---

## Persona ↔ Channel Matrix

| Channel | Operator-User | Public Reader |
|---------|---------------|---------------|
| GitHub Pages 사이트 | ✅ | ✅ |
| 공개 Telegram 시황 채널 | ✅ | ✅ (옵션) |
| 운영자 1:1 Telegram chat (실패 알림) | ✅ | ❌ |
| GitHub Actions UI | ✅ | ❌ |
| Code repo / IDE | ✅ | ❌ |
