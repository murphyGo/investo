# Requirements Reference

## Intent Analysis
- **Request Clarity**: Mostly Clear (idea was concise; refinement filled in tech, format, ops details)
- **Request Type**: New Project (Greenfield)
- **Scope**: Medium — multiple data sources, LLM integration, static site, notification, scheduling
- **Complexity**: Medium — orchestration of external APIs + LLM + multiple output channels

## Source

Primary requirements document: `docs/requirements.md` (single source of truth)
Refinement questions: `docs/refinement-questions.md`
Refinement log: `docs/refinement-log.md`
Vision: `docs/vision.md`
Tech environment: `docs/tech-env.md`

## Extension Configuration

| Extension | Status | Impact on Requirements |
|-----------|--------|------------------------|
| Security Baseline | DECLINED | Standard secret-handling via GitHub Secrets only; no formal threat modeling required |
| Property-Based Testing | PARTIAL | NFR-006: hypothesis applied to pure functions and serialization round-trips only |

## Traceability Summary

- **Functional Requirements**: base FR-001 through FR-007 plus post-MVP FR-008 through FR-015 (defined in docs/requirements.md §2)
  - FR-001 데이터 수집
  - FR-002 AI 시황 작성
  - FR-003 정적 웹 게시
  - FR-004 텔레그램 알림
  - FR-005 스케줄 실행
  - FR-006 영구 이력 보관
  - FR-007 실행 실패 알림
  - FR-015 shared macro evidence hardening (u60)
- **Non-Functional Requirements**: NFR-001 through NFR-007 (defined in docs/requirements.md §3)
  - NFR-001 Performance, NFR-002 Cost, NFR-003 Reliability, NFR-004 Compliance/Disclaimer, NFR-005 Maintainability, NFR-006 Testing, NFR-007 Security
- All requirement IDs are defined in `docs/requirements.md`.

## Notes

- LLM 호출은 **Claude Code CLI**(GitHub Secrets 토큰)로만. Anthropic SDK 직접 사용 금지 — NFR-002·FR-002에 강제 명시.
- 데이터 소스 정확한 조합은 Open Question으로 남겨둠 (구현 단계 PoC에서 결정).

## u180–u183 — Public Insights (2026-10-12)

사용자의세제품선택과유닛설계지시에따라 FR-026common/FR-027macro/FR-028calendar/FR-029crypto 초안을등록한다. 세부요구/AC 의단일본문은[docs/requirements.md](../../../docs/requirements.md)의 2026-10-12amendment 와[공통계약](../../construction/public-insights-20261012/contracts.md)이다. 기존 Inception 완료기록이나 newsource/runtime 승인을변경하지않는다.

2026-10-25: 사용자 후속 진행 지시로 FR-028/u182의 기존 설계를 채택하고 로컬 구현·검증6/7을 기록했다. source별14allow/10blocked와 실제 운영 Step7은 별도다. [구현 증거](../../construction/u182-upcoming-events-dashboard/code/summary.md).

2026-10-25: FR-029/u183의기존설계를채택해로컬구현·검증7/8을기록했다. 세화면로컬구현완료와운영수용은구별한다. [증거](../../construction/u183-crypto-market-internals-dashboard/code/summary.md).
