# Story-to-Unit Mapping: Investo

**Date**: 2026-04-27

---

## Mapping (Q1=A: 1:1 Component ↔ Unit)

| Story | Title | Primary Unit | Secondary Touch |
|-------|-------|--------------|-----------------|
| US-001 | 매일 시장 데이터를 자동 수집한다 | u1 sources | models |
| US-002 | AI가 한국어 데일리 시황을 작성한다 | u2 briefing | models |
| US-003 | GitHub Pages에 시황을 정적 게시한다 | u3 publisher | u6 infra (mkdocs/Pages) |
| US-004 | 공개 텔레그램 채널로 시황 요약이 푸시된다 | u4 notifier (BriefingPublisher) | u5 orchestrator (트리거) |
| US-005 | GitHub Actions cron으로 자동 실행된다 | u5 orchestrator | u6 infra (cron) |
| US-006 | 모든 시황을 영구 보관한다 | u3 publisher | u6 infra (Pages 인덱스) |
| US-007 | 파이프라인 실패 시 운영자 1:1 chat으로 알림 받는다 | u4 notifier (OperatorAlerter) | u5 orchestrator (실패 hook) |
| US-008 | 새 데이터 소스를 단일 모듈 추가로 통합한다 | u1 sources | (문서/CONTRIBUTING) |
| US-009 | 운영비를 월 $0으로 유지한다 | u2 briefing (Claude Code CLI) | u1 sources (free APIs) |

---

## Per-Unit Story Coverage

### u1 sources
- **Primary**: US-001, US-008
- **Touched by**: US-009 (free API constraint)
- **AC delivered**:
  - 무료 API/RSS만 사용 → US-001 AC + US-009 AC
  - Plugin registry + 단일 모듈 추가로 통합 → US-008 AC
  - Graceful degradation → US-001 AC + NFR-003

### u2 briefing
- **Primary**: US-002, US-009
- **AC delivered**:
  - Claude Code CLI 호출, Anthropic SDK 금지 → US-002 + US-009 AC
  - 7섹션 한국어 시황 → US-002 AC
  - 면책조항 자동 삽입 → US-002 AC + NFR-004
  - LLM retry → US-002 AC + NFR-003

### u3 publisher
- **Primary**: US-003, US-006
- **Touched by**: NFR-004 (disclaimer verify로 강제)
- **AC delivered**:
  - markdown archive 저장 → US-006 AC
  - git commit으로 영구 → US-006 AC
  - 게시 전 disclaimer 검증 → NFR-004 (US-002 AC 보강)
  - GitHub Pages 호환 markdown 생성 → US-003 AC (배포 자체는 u6)

### u4 notifier
- **Primary**: US-004 (BriefingPublisher), US-007 (OperatorAlerter)
- **AC delivered**:
  - 공개 채널 발송 + 4096자 한도 → US-004 AC
  - 운영자 1:1 chat 분리 → US-007 AC
  - 발송 실패가 게시를 막지 않음 → US-004 AC + NFR-003
  - 시크릿/PII 미포함 검증 → US-004 AC + NFR-007

### u5 orchestrator
- **Primary**: US-005
- **Touched by**: US-004, US-007 (트리거 위치), NFR-001 (시간 예산)
- **AC delivered**:
  - cron + workflow_dispatch + KST 시간대 → US-005 AC
  - ≤ 10분 단일 job → NFR-001
  - Graceful degradation 정책 → NFR-003 + 다수 US AC

### u6 infra/CI
- **Primary**: 인프라 자체. 모든 US가 간접적으로 의존.
- **AC delivered**:
  - cron 트리거 → US-005 AC
  - mkdocs build + GitHub Pages → US-003 AC
  - Secrets 주입 (CLAUDE_CODE_OAUTH_TOKEN, TELEGRAM_*) → NFR-007

---

## Cross-Cutting NFR Coverage

| NFR | Where Implemented | Verified By |
|-----|-------------------|-------------|
| NFR-001 Performance (≤10분) | u5 orchestrator (time budget per stage) | u5 integration test + first cron run |
| NFR-002 Cost ($0/월) | u1 (free APIs only) + u2 (Claude Code CLI only) | grep/lint check + PR review |
| NFR-003 Reliability (graceful degradation) | u1 (per-source isolation) + u2 (LLM retry) + u3 (git retry) + u4 (non-blocking failure) + u5 (stage policy) | per-unit failure tests + integration test |
| NFR-004 Compliance (disclaimer) | u2 (auto append) + u3 (verify presence) | u2/u3 unit tests |
| NFR-005 Maintainability (plugin) | u1 (registry/protocol) | u1 unit test + CONTRIBUTING |
| NFR-006 Testing (PBT partial) | models (round-trip), u1 norms, u2 prompt builders, u4 summary | hypothesis 기반 테스트 |
| NFR-007 Security (secrets via GH Secrets) | u6 (workflow secrets), u2 + u4 (env-only auth) | workflow audit + secret scan |

---

## Definition of Done — Inception Phase Output

이 매핑이 다음 단계(Construction)의 입력입니다:
- 각 unit별 Functional Design 대상이 명확 (execution-plan.md의 selective per-unit 정책 참조)
- 각 unit별 NFR Requirements 작성 시, 본 표의 "AC delivered" 컬럼이 출발점
- Code Generation은 unit-of-work.md의 Definition of Done 체크리스트를 task로 변환
