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

- **Functional Requirements**: FR-001 through FR-007 (defined in docs/requirements.md §2)
  - FR-001 데이터 수집
  - FR-002 AI 시황 작성
  - FR-003 정적 웹 게시
  - FR-004 텔레그램 알림
  - FR-005 스케줄 실행
  - FR-006 영구 이력 보관
  - FR-007 실행 실패 알림
- **Non-Functional Requirements**: NFR-001 through NFR-007 (defined in docs/requirements.md §3)
  - NFR-001 Performance, NFR-002 Cost, NFR-003 Reliability, NFR-004 Compliance/Disclaimer, NFR-005 Maintainability, NFR-006 Testing, NFR-007 Security
- All requirement IDs are defined in `docs/requirements.md`.

## Notes

- LLM 호출은 **Claude Code CLI**(GitHub Secrets 토큰)로만. Anthropic SDK 직접 사용 금지 — NFR-002·FR-002에 강제 명시.
- 데이터 소스 정확한 조합은 Open Question으로 남겨둠 (구현 단계 PoC에서 결정).
