# Event validation retry feedback — 2026-11-23

## Result

Local implementation and verification complete for the bounded u157/u158 follow-up. Event classification retries now receive fixed corrective instructions for the validator's closed evidence/schema diagnostics. Narrative retries receive specific fact/evidence guidance. Each rejected attempt logs only closed diagnostic codes; arbitrary `event.*` exception text maps to `event.output_invalid`.

The existing evidence validators, required facts, event membership, terminal publish gate, attempt limits, backoff and time budget remain unchanged. A corrected second response can pass the actual validators; repeatedly invalid responses still fail. Feedback is rebuilt from the latest failure without accumulating failed text. Independent bounds are 2,069 bytes for Stage 1 and 809 bytes for Stage 2.

## Changed files

- `src/investo/briefing/_core/classification.py`: closed diagnostics to fixed Stage 1 repair hints.
- `src/investo/briefing/_core/orchestration.py`: retry feedback and sanitized per-attempt logs.
- `src/investo/briefing/_assembly/markdown_render.py`: closed Stage 2 codes and fact/evidence repair hints.
- `tests/unit/briefing/test_event_retry_feedback.py`: 19 synthetic regression cases, including validator-driven recovery, repeated rejection, privacy and latest-only feedback.
- `tests/unit/briefing/test_event_entity_retry.py`: compatibility assertion accommodates the added fact hint while preserving entity-hint separation.

## Validation

| Check | Result |
|---|---|
| Latest public base `af3ca28920944880b19b86981f23826fa9b8541d` | 2,088 related tests passed in 103.57s; no failures/skips |
| Current production base `3ce35148947db7f5ec8c4011578e078d03ee19b7` with only this repair | 111 tests passed in 2.57s |
| Focused regression suite | 50 passed; included in public suite, not an additional total |
| Independent review | PASS; no findings; reviewer separately ran 159 related tests |
| Static checks | Ruff and format: five Python files; Mypy: three source files; diff check passed |
| Integration | Owned files copied only after baseline hash checks; shared HEAD/index preserved |

The portable command arrays and code hashes are in [verification evidence](retry-feedback-verification-20261123.json). Run from the indicated clone with the existing Python 3.11 environment and `PYTHONPATH=src`; no new dependency is required. The broad selection covers all briefing unit tests plus orchestrator, module-boundary, event model/publisher and event integration tests. It is not a repository-wide suite.

Local raw test artifacts are in ignored `.tmp/event-reliability-20261123/`: `related-tests.log`, `related-tests.xml`, `runtime-tests.log`, `test-command.json` and `integration-receipt.json`. The production-base patch is isolated from unrelated public v3/DART development.

## Evidence and acceptance limits

The sanitized [incident summary](retry-feedback-incidents-20261123.json) records Nov 17/18 classification failures and Nov 20 unsupported-fact failure. Classification retries reused prompts with identical byte counts; code inspection established missing corrective feedback for most validation failures. This proves the feedback gap, not the precise contents or causes of the rejected production responses.

Failed raw model output was intentionally not retained. Tests therefore use synthetic inputs through actual validators; they are not replays of those production payloads. The Nov 19 terminal `event.evidence_invalid` cause remains unresolved. The gate is unchanged, and this work makes no claim that the terminal incident is repaired or that live success rates have improved.

No manual live model invocation, publication, notification, commit, push, deployment or runtime-pin change was performed for this repair. After release, observe scheduled attempts and their new closed diagnostics before assessing operational improvement. Preserve the terminal gate if the unexplained failure recurs.

## References

- [Plan](../../plans/u157-u158-event-retry-feedback-code-generation-plan.md)
- [Independent review](retry-feedback-review-20261123.md)
- [Cross-check](../../../../docs/cross-checks/2026-11-23-event-retry-feedback.md)
- [Session](../../../../docs/sessions/2026-11-23-event-retry-feedback.md)

## Subsequent release authorization

After the local implementation report, the user again requested “진행시켜”. This authorizes the next stated step: commit this scoped repair and deploy it. The no-release statements above describe the completed local implementation phase. Release proceeds only after full quality CI succeeds for the exact public and production-base candidate commits. Production deployment changes only `REVIEWED_CODE_SHA`; other source-qualification pins, runtime variables and workflows remain unchanged. The release receipt is retained locally at `.tmp/event-reliability-20261123/release-receipt.json` and the exact CI links are reported in the release handoff. Scheduled live success-rate improvement remains unmeasured at promotion.
