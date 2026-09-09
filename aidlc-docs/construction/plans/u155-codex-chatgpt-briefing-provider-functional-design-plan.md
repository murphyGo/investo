# Functional Design Plan — u155 codex-chatgpt-briefing-provider

**Date**: 2026-09-09 KST
**Status**: Functional Design approved on 2026-09-09 KST.
**Unit**: u155; independent of u151/u152/u154.

## Scope answers already supplied in this conversation

These answers record the original accepted scope. The later explicit detailed
design approval is recorded below. No repeated scope question is needed.

### Q1. Claude와 Codex를 어떻게 제공하는가?

A) Claude 기본값 유지 + Codex 선택 기능.
B) Claude를 완전히 제거하고 Codex로 교체.
C) Other.

[Answer]: A — 사용자가 “Claude와 더불어 Codex 옵션을 추가” 요청.

### Q2. Codex 인증·비용 경로는 무엇인가?

A) Codex CLI + ChatGPT 로그인.
B) OpenAI API key 사용량 과금.
C) Other.

[Answer]: A — 사용자 명시.

### Q3. 인증 정보를 어디서 관리하는가?

A) GitHub Actions Secrets.
B) 외부 secret manager.
C) Other.

[Answer]: A — 사용자 명시. Environment Secret 세부 선택은 설계에서 제안.

### Q4. 공개·비공개 실행 경계는 무엇인가?

A) 코드/결과는 공개 Investo, 인증 자동화는 별도 비공개 실행 저장소.
B) Investo 전체를 비공개로 전환.
C) Other.

[Answer]: A — 직전 추천 구성에 사용자가 “오케이. 일단 작업 시작해줘” 응답.

## Steps

- [x] Step 1 — Read current remote unit registry, runtime/generation/publish
  boundaries and official authentication/Secret lifecycle documentation.
- [x] Step 2 — Register u155, map existing stories/requirements, and decide
  Functional Design/NFR/Infrastructure coverage.
- [x] Step 3 — Record approved scope above; distinguish proposed defaults
  and later activation prerequisites from user-approved facts.
- [x] Step 4 — Write business-logic-model.md including persistence-before-
  publication and error/partial-outcome boundaries.
- [x] Step 5 — Write business-rules.md with provider compatibility, auth
  rotation, Environment Secrets, serialization and R13 contracts.
- [x] Step 6 — Write domain-entities.md and reviewable implementation plan.
- [x] Step 7 — Validate local links, state/plan/AC consistency and doc diff;
  present the completed Functional Design for explicit approval.

Validation: six new Markdown artifacts passed local-link, code-fence and
whitespace checks; 12 unique ACs, 14 business rules, nine unstarted code steps,
five registry/requirement references and docs-only diff verified.
`git diff --check` passed. No source/test/workflow/site-doc changes, so no
runtime tests or public-site build were represented as necessary or executed.

## Design approval

[Answer]: Approved — user replied “진행시켜” to the explicit FD approval /
NFR and Infrastructure handoff; recorded at 2026-09-08T18:06:59Z.

R1–R14 and the Functional Design are approved. Prepare focused NFR and
Infrastructure artifacts for the next review; implementation is not yet approved.
Repository name, credentials, model availability and billing allowance are
activation prerequisites, not a reason to leave this design undocumented.

## Artifacts

- [Design brief](../u155-codex-chatgpt-briefing-provider/design-brief.md)
- [Business logic](../u155-codex-chatgpt-briefing-provider/functional-design/business-logic-model.md)
- [Business rules](../u155-codex-chatgpt-briefing-provider/functional-design/business-rules.md)
- [Domain entities](../u155-codex-chatgpt-briefing-provider/functional-design/domain-entities.md)
- [Code Generation plan](u155-codex-chatgpt-briefing-provider-code-generation-plan.md)
