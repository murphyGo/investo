# Functional Design: u158 사건 중심 본문과 상단 요약

**Date**: 2026-09-26
**Status**: Design approved by the 2026-09-27 sequential-development request. Queued — design approved; follows u157.
**Priority / effort**: P0 / 18–26 h (rough engineering estimate, not commitment).
**Dependencies**: u157 모델/plan 구현. u154 배치 및 u156 Telegram 구성은 hard dependency가 아니다.

## Reader problem
9/16 미국 문서는 FOMC 성명서 공개만 설명하고 결정 메시지는 빈약했다.13/18 상단 결론은 fallback이어서 본문 사건을 전달하지 못했다.

## Ownership and deduplication
Existing owners: u2/u83 synthesis, u51/u61/u71 summary, u153 sentence bound, u144 finalizer, u154 layout, reserved u156 notifier.
Existing code touch points: `briefing/_core/orchestration.py, briefing/prompts.py, briefing/generation_contract.py, models/public_notification.py, publisher/public_document.py, publisher/reader_format/tldr.py, orchestrator/pipeline.py, briefing/_assembly/markdown_render.py (_stage2_retry_feedback)`.
Proposed new modules: `briefing/event_narrative.py; publisher/event_blocks.py`. These paths do not imply implementation exists.

## Shared contracts
[Program overview](../news-event-briefing/README.md), [entities and schema](../news-event-briefing/event-contract.md), [business rules](../news-event-briefing/business-rules.md), [NFR and evaluation](../news-event-briefing/nfr-and-validation.md).
The unit-specific rules below bind the shared contract. Inconsistency must be resolved in design before code; implementations cannot silently override common identity/budgets/trust semantics.

## Fixed contracts
1. E6의 JSON v2 하나를 파싱하고 event records로②를 결정론적으로 렌더한다. 자유 Markdown②와 별도 JSON의 이중 원본을 만들지 않는다. 나머지5개 section string을 기존 Briefing에 조립한다.
2. actor/action/시점/필수 fact/meaning/reaction/출처를 E6의 구조로 표시한다. meaning과 reaction은 각각 근거·상태를 갖는다. 사건 validator가 허용 fact/entity/reference를 검사하고 새 URL은 EvidenceRef lookup으로만 렌더한다. 자유 서술의 의미적 정확성은 별도 주석 평가로 검증한다.
3. 첫 conclusion은 첫 유효 사건 what_happened의 완전한 첫 문장(80 codepoints 이하)이다. 전체 설명은 240자 이내다. 3개 TL;DR와 B6 순서를 유지하며 첫 bullet의 숫자 필수만 event-mode에서 완화한다. u153 90자 경계에서 generic fallback으로 되돌아가지 않아야 한다.
4. u154 블록순서/H1/hero 변경과 u156 Telegram 배열/장식/예산은 건드리지 않는다. 기존 carrier의 conclusion 개선과 optional events=() DTO 확장까지만 소유한다.
5. GenerationResult→orchestrator→PublicDocumentContext의 frozen event payload를 명시적으로 연결한다. sibling-module import 금지. 새 event region은② section_body 안의 하위 identity로만 추적해 기존 region ownership과 겹치는 이중 mutation을 만들지 않는다.
6. _derive_public_notification_summary는 검증된 terminal layout을 읽기만 한다. DTO는 알림 적격 terminal 사건의 결정론적 최대 3개 ordered subset이다. 생성 시점 Briefing.key_issues/market_summary를 사실 원본으로 사용하지 않는다.
7. 기존 hard finding을 삭제 전에 보존한다. _repair_projected_draft 안에서 provisional event survival → callout/TL;DR/관전 카드 reconciliation → reindex를 수행한다. 제거된 ID는 재추가하지 않는다. 반복은 최초 selected 수+1회 이내이며 불안정하면 fail-closed다. 이후 hard gates, _validate_repaired_draft, _derive_public_notification_summary를 읽기 전용으로 실행한 뒤 seal한다.

## Stage decision
Functional Design: REQUIRED — new cross-module/event behavior; this document and shared contracts were approved by the 2026-09-27 implementation request.
NFR Requirements: REQUIRED — Stage2 schema와 public/notification projection 및 실패 처리 변경. NF1/2/3/7/9/10 적용.
Separate NFR Design/Infrastructure Design: no separate artifact for pure code; focused runtime/storage rules are fully specified here. u160/u161 public I/O and transaction rules require their NFR review before implementation. No new deployment platform.

## Failure and compatibility
Apply B4/B5/B8/B11 and unit-specific states. Off mode preserves current producer/consumer behavior. Existing numeric/entity/compliance hard gates and sibling availability remain authoritative. Code-ready status requires hard dependencies and design approval; source qualification stays separate from code readiness.

## Acceptance criteria
- AC-158.1: 정책결정·실적·제품·발언 fixture에서 selected 사건의 what/when/required facts/why/reaction status/source가최종②에존재한다.
- AC-158.2: 동일fixture에서source title나URL만 남은문서는상세설명완료로인정되지않는다.
- AC-158.3: 숫자 없는 중요 사건의 80자 이내 첫 문장이 상단 결론에 남는다. 90자 초과 단일 문장은 retry 대상이다. 사건 0건과 수집 부족은 다른 안내문을 쓴다.
- AC-158.4: containment/부분bundle재조립후살아있는사건만TL;DR/callout/DTO에있으며finalizer2회byte동일이다.
- AC-158.5: 구조화 factual slots의 미허용 fact/entity/refs와 기존 compliance 위반은 hard gate에서 거부한다. 필드별 refs mismatch negative와 자유 서술 주석 평가를 별도로 통과하며 유효 sibling은 게시 가능하다.
- AC-158.6: u154 전후layoutfixture와legacyDTOconsumer호환,추가LLM단계0,기존7섹션/면책조항보존을증명한다.

## Development sequence
See [code-generation plan](../plans/u158-event-first-narrative-and-summary-code-generation-plan.md). Implementation follows the 2026-09-27 user-authorized sequential queue.
