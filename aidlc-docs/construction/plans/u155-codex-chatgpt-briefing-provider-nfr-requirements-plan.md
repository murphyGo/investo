# NFR Requirements Plan — u155 codex-chatgpt-briefing-provider

**Date**: 2026-09-09 KST
**Status**: Assessment and artifacts prepared; approved for implementation.
**Authorization**: “진행시켜” approves the preceding Functional Design
and authorizes the proposed NFR/Infrastructure preparation.

## Assessment and answers

Answers distinguish approved contracts, design proposals and missing account
facts. Proposed engineering defaults are reviewable decisions, not fabricated
user responses.

| Category | Question / applicability | Answer basis |
|---|---|---|
| Scalability | How many auth streams and markets? | R5/R6: one stream; existing three markets; no horizontal auth reuse |
| Performance | What time ceiling applies after serialization? | Existing caller ceilings remain; bounded private runtime proposed below |
| Availability | How are auth outage and quota handled? | R9/R13/R14: stop publication, recover dedicated login, operator-controlled Claude rollback |
| Security | What can market content cause the CLI to access? | R3/R4/R7–R11: ChatGPT only, tools disabled, credential filtering, pre-publication persistence |
| Tech stack | Reuse runtime or introduce service/API? | Existing Python pipeline plus CLI/Actions; no service or paid API |
| Reliability | How to survive refresh, timeout and cancellation? | Bounded checkpoint/finally; strong kill remains a recovery case |
| Maintainability | How are changes accepted? | Existing typed seams, synthetic tests, full gate, independent review and cross-check |
| Usability | Does the reader-facing report change? | Same report/notification contracts; provider selection is operator configuration |

### Q1. 비용과 인증 경로

[Answer]: Already approved — existing subscriptions, ChatGPT CLI login,
private Actions; no additional LLM API usage or automatic plan purchase.

### Q2. 운영 시간 상한

[Answer]: Proposed — retain existing per-call/per-segment ceilings; private
job 240 minutes, supervised runtime 225 minutes, generation admission cutoff
210 minutes from supervisor start. Reserve final time for persistence and
existing finalization/publishing. These are ceilings, not measured latency.

### Q3. 비공개 Environment Secrets 사용 가능 여부

[Answer]: Pending account fact — GitHub Pro/Team/Enterprise is required for
private Environment Secrets. The account API returned no plan; a concise
asynchronous question was sent. Do not infer Free/Pro from null.
Implementation may prepare a conditional template; provisioning/activation
cannot pass until this prerequisite is established. Free requires a reviewed
infrastructure revision; do not silently fall back to repository auth secrets.

## Preparation steps

- [x] Step 1 — Record Functional Design approval and read runtime boundaries.
- [x] Step 2 — Assess all eight NFR categories and document answer provenance.
- [x] Step 3 — Specify measurable time, auth, output and failure constraints.
- [x] Step 4 — Map constraints to technology and existing component owners.
- [x] Step 5 — Prepare verification matrix and account/activation prerequisites.
- [x] Step 6 — Validate artifacts and present NFR/Infrastructure for review.

## Approval

[Answer]: Approved — user “구현까지 진행시켜”, 2026-09-09 KST.
Proceed through local implementation and validation; account/provisioning/activation gates remain.

- [NFR requirements](../u155-codex-chatgpt-briefing-provider/nfr-requirements/nfr-requirements.md)
- [Tech stack](../u155-codex-chatgpt-briefing-provider/nfr-requirements/tech-stack-decisions.md)
- [Infrastructure plan](u155-codex-chatgpt-briefing-provider-infrastructure-design-plan.md)
