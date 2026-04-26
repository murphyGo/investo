# Refinement Log: Investo

**Date**: 2026-04-25
**Depth Level**: Standard
**Initial idea**: 매일 미국 주식·크립토(+ 코스피) 데일리 시황을 자동 생성해 웹 UI에 게시하고 텔레그램으로 알림. Python + GitHub Actions 운영. 본인 전용으로 시작, 추후 포트폴리오/기업 분석 확장.

## Refinement Dialogue

### Round 1
**Claude's Analysis**: 6개 카테고리에서 누락/모호점 식별 — (1) 데이터 소스 미정의, (2) LLM 호출 엔진 미정의, (3) 웹 호스팅·구조 미정의, (4) 시황 출력 포맷 미정의, (5) 텔레그램 봇 인프라 미정의, (6) 실행 시각/타임존 미정의. 추가로 컴플라이언스(투자 조언 표현)·에러 처리·모니터링 누락 지적. Tech Stack은 Python + Claude API + MkDocs + Telegram Bot + GitHub Actions를 제안.

**User's Response**:
1. 무료 위주로
2. Claude Code의 setup token으로 Claude Code 실행. Anthropic API는 별도 요금이 있어 불가
3. 본인 전용, 하지만 남한테 보여줄 수도 있음
4. 한국어
5. 영구 보관, 문제될 정도로 많아지면 삭제 고려
6. 현재는 No
Extension A: SKIP, B: Partial

**Ambiguity Check**: 모든 답변이 명확. 구체적 데이터 소스 조합·시황 시각·텔레그램 대상 등은 구현 단계에서 결정해도 무방한 디테일이므로 Open Questions로 보관.

**Outcome**:
- Tech Stack 변경: LLM 호출은 anthropic SDK가 아닌 **Claude Code CLI를 GitHub Actions에서 setup token으로 인증해 호출**하는 방식으로 확정. 이건 일반 패턴과 다르므로 FR-002 acceptance criteria + NFR-002 비용 절약 근거에 명시.
- public repo 운영 가정 (열람 공유 + GitHub Actions 무제한)
- 시황 한국어, 영구 보관, 면책조항 자동 삽입 의무화
- Security Baseline SKIP, PBT Partial 적용

## Final Changes

| Original (IDEA.md) | Refined (requirements.md) | Reason |
|---|---|---|
| "주요 소스로부터 뉴스, 이벤트, 지표 수집" | FR-001 + Open Questions에 무료 소스 후보 명시, plugin 구조 요구 | 구체화 + 확장성 |
| "시황 작성" | FR-002 — 7섹션 정형 포맷 + 면책조항 + Claude Code CLI 호출 | 일관성, 컴플라이언스, 비용 |
| "웹 UI 게시" | FR-003 — MkDocs Material + GitHub Pages, archive/YYYY/MM/ 구조 | 무료 호스팅, 영구 이력 |
| "텔레그램 요약 알림" | FR-004 — Bot API, 4096자 한도, 발송 실패가 게시 막지 않음 | 견고성 |
| (없음) | FR-005 — 한국시간 평일 7시 / 토요일 1회 cron | 미국장 마감 후 데이터 확보 |
| (없음) | FR-006 — git commit으로 영구 보관 | 사용자 답변 #5 |
| (없음) | FR-007 — 실패 시 텔레그램 알림 | 모니터링 갭 보완 |
| (없음) | NFR-002 비용 0원 + Claude Code CLI 강제 | 사용자 답변 #2 |
| (없음) | NFR-004 면책조항 의무 | 컴플라이언스 리스크 |
| (없음) | NFR-006 PBT partial (순수 함수 + 직렬화만) | Extension B Partial |

## Suggestions Applied

- [x] (1) 데이터 소스 — 무료 위주, 구체 조합은 PoC 단계로 이연
- [x] (2) 시황 작성 엔진 — Claude Code CLI 방식으로 변경 채택
- [x] (3) 웹 UI — MkDocs + GitHub Pages 채택
- [x] (4) 시황 포맷 정형화 — 7섹션 채택
- [x] (5) 텔레그램 봇 — Bot API + Secrets 채택
- [x] (6) 실행 시각 — 한국시간 평일 7시 / 토요일 채택
- [x] 면책조항 자동 삽입 — NFR-004로 의무화
- [x] 실행 실패 알림 — FR-007로 추가
