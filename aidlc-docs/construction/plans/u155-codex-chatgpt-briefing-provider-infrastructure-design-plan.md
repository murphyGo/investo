# Infrastructure Design Plan — u155 codex-chatgpt-briefing-provider

**Date**: 2026-09-09 KST
**Status**: Conditional infrastructure proposal prepared; approved for implementation.
**Authorization**: User approved FD and continuation to NFR/Infrastructure.

## Category assessment

| Category | Question / applicability | Decision basis |
|---|---|---|
| Deployment | Where does authenticated automation run? | Approved private runtime repository; public code/output stays Investo |
| Compute | Hosted or persistent runner? | Proposed standard ephemeral Ubuntu Actions runner; no new host service |
| Storage | Where do refreshed auth and generated history live? | Approved Environment Secret and latest public archive checkout; temporary local auth |
| Messaging | Is a queue/broker needed? | Existing Actions scheduling plus one fixed concurrency group; no external broker/FIFO promise |
| Networking | Which network boundaries are required? | CLI's official auth/model transport and existing source clients; operations writer targets GitHub API; no incoming endpoint |
| Monitoring | What evidence and notifications are kept? | Safe private receipt and existing public notification policy; no raw CLI/auth artifact |
| Shared infrastructure | Are other units' resources changed? | Existing public repository/Pages are integration destinations; no new shared service or global infrastructure mutation |

### Q1. 비공개 저장소와 Environment 배치

[Answer]: Proposed — `murphyGo/investo-runtime`, one `codex-runtime`
Environment and one trusted job; separately scoped writer/publisher credentials.
This refines the FD's separate publishing-environment suggestion and awaits
review. It preserves the existing single-process publication path.

### Q2. 비공개 Environment 기능

[Answer]: Pending — same account-plan question as the NFR plan. API returned
`plan: null`; repository lookup returned 404. No repository creation or
feature eligibility is claimed. Pro/Team/Enterprise support must be verified
before provisioning; no automatic subscription upgrade.

### Q3. 초기 실행과 전환

[Answer]: Already approved in FD R14 — manual dry-run first, then separately
reviewed operational cutover with one schedule owner. Default provider remains
Claude; Codex is explicit and requires a qualified model.

## Preparation steps

- [x] Step 1 — Analyze FD and proposed NFR contracts.
- [x] Step 2 — Evaluate all seven infrastructure categories.
- [x] Step 3 — Specify concrete repository/job/secret/checkout boundaries.
- [x] Step 4 — Map privilege flow, persistence, publication and failure cleanup.
- [x] Step 5 — Prepare manual qualification, cutover and rollback sequence.
- [x] Step 6 — Validate artifacts and stage/requirement references.

## Approval

[Answer]: Approved — user “구현까지 진행시켜”, 2026-09-09 KST. Account/model/usage gates remain prerequisites for live
provisioning/activation even after implementation approval.

- [Infrastructure design](../u155-codex-chatgpt-briefing-provider/infrastructure-design/infrastructure-design.md)
- [Deployment architecture](../u155-codex-chatgpt-briefing-provider/infrastructure-design/deployment-architecture.md)
- [NFR plan](u155-codex-chatgpt-briefing-provider-nfr-requirements-plan.md)
