# u186 Code Generation Plan — 기사 의미 검증·제한된 수정·내용 준비도

2026-10-26. **개발 승인·구현 진행.** 사람 수용·운영 전환은 기존 u172 책임으로 남긴다.

## 문제·목표·Coverage

기존 두 단계의 literal/slot 검사만으로 자연스러운 한국어 설명의 의미·내용 충실도를 검증할 수 없다. 같은 writer의 자기 평가나 본문 길이를 합격으로 쓰지 않고 별도 CLI review를 추가한다. 세 번째 호출로 인한 retry/timeout 증가를 전역 예산으로 제어하고 최종 출력에 평가를 결속한다.

US-002/003/005/007; FR-002/006/007/017/021/023/024/025; NFR-001~008. u169 orchestration, u159/u172 quality·replay, u144 seal, u155 runner를 확장한다. 새 유료 evaluator, 다른 모델 자동 fallback, event별 무한 retry, 새로운 사람 rubric/rollout unit, legacy 같은 실행 재생은 범위 밖이다.

Functional Design/NFR **EXECUTE — 공통 설계 작성됨**: [처리](../event-news-v3-content-20261026/functional-design/business-logic-model.md), [규칙](../event-news-v3-content-20261026/functional-design/business-rules.md), [타입](../event-news-v3-content-20261026/functional-design/domain-entities.md), [고정 예산](../event-news-v3-content-20261026/nfr-requirements/nfr-requirements.md). u184 packet과 u185 narrative/claims 선행. code 착수와 실제 u172 corpus·source·viewport 합격은 별개다.

## Module map

신규 `briefing/event_article_review.py`; 기존 `briefing/_core/orchestration.py`, `briefing/claude_code.py::RetryBudget`, `briefing/event_document.py`, `models/event_config.py`, `models/event_article.py`, `models/event_quality.py`, `publisher/event_quality.py`, `publisher/quality_consistency.py`, `publisher/public_document.py`, `scripts/_event_coverage_replay.py`, `scripts/check_event_coverage.py`, `scripts/preview_event_briefing.py`, `ops/private-runtime/event-preview.yml`을 연결한다. production workflow/default/pin은 수정하지 않는다.

## 구현 순서

- [x] **Step1 — 전역 호출 allocator**: article_v2의 시장별3900초, call1/2/3=600/900/600초, optional4/5=900/600초를 고정한다. 각 stage attempts1이며 source prep·finalizer와 workflow deadline을 포함해 admission한다. initial review·repair/review pair reserve, exact equality·cancel·timeout을 검증한다. 기존 profile budget은 그대로 둔다.
- [x] **Step2 — Stage3 verifier**: 원문 packet/claim map/draft/questions만 새 CLI 호출에 전달한다. writer self-score와 자유 URL/tool은 제외한다. 모든 claim/필수 질문의 verdict·refs·reason code·exact hash가 필요하며 누락/unknown/malformed는 실패다. hard gate를 override하지 못한다.
- [x] **Step3 — 한 번의 batch 수정**: 검토된 candidate의 고칠 수 있는 gap만 전달한다. source가 없는 gap은 반복 작성하지 않는다. 수정할 전체 사건에 최대1 call, 이어 전체 재검증1 call이다. 지원되지 않은 새 event/fact/ref를 추가하면 reject하고 기존 hard finding은 보존한다.
- [x] **Step4 — terminal readiness**: content readiness와 source/selection/fact preservation/semantic/human KPI를 분리한다. stale hash와 finalizer 삭제 뒤 coverage를 재검사하고 미검증 본문 seal을 막는다. blank/footer-only·주요 기사 누락을 normal 성공으로 세지 않으며 valid sibling/기존 partial outcome을 보존한다.
- [x] **Step5 — 실제 preview·u172 연결**: preview template에 default role_v1인 명시적 profile 입력을 추가하고 검증된 코드·source policy로만 article_v2를 실행할 수 있게 한다. raw recording과 human0/12 상태를 구별한다. u172의 기존 corpus/model/CLI validation에 추가 hashes/질문 coverage를 연결하되 synthetic/model 점수를 human5/5로 바꾸지 않는다.
- [ ] **Step6 — 검증·인계**: 아래 집중·전체·정적·정책·docs gate와 로컬 code review/AC cross-check를 수행한다. u172에 exact source SHA/profile/policy/source qualification, stage bytes/calls/time, actual/human pending 항목을 전달한다. 운영 활성화와 genuine scheduled 증거는 이 유닛의 코드 완료로 만들지 않는다.

## Acceptance Criteria

1. **AC-186.1**: 기사 있는 정상 실행3 calls, 수정 시최대5 calls; quiet는 classification 후 불필요한 호출0이다. timeout/schema/cancel을 포함한 전역3900초와 stage timeout을 지키고 repair+review 잔여 예산이 없으면 수정0회다. old profile의 behavior는 동일하다.
2. **AC-186.2**: 의미가 어긋난 번역·새 인과·조건/부정 삭제·잘못된 발언 주체·원문 지시 주입·허위 source ID를 자동 reviewer와 deterministic gate가 차단한다. 전체 검증 우회0이다.
3. **AC-186.3**: 동일 모델 separate call을 독립 사람 검증으로 보고하지 않는다. supporting refs와 exact draft hash 없는 verdict는 실패이며 hard finding을 supported가 덮지 못한다.
4. **AC-186.4**: 근거는 있으나 빠진 설명을 한 번의 수정으로 회복하는 양성과 근거 없는 내용 추가를 거절하는 음성이 통과한다. 수정 후 재검증 실패는 공개0이다.
5. **AC-186.5**: finalizer 이후 exact text·survivor·readiness·digest/story projection이 일치한다. brief/quiet/limited/evidence_gap/content_not_ready/trust failure 분모가 뒤섞이지 않는다.
6. **AC-186.6**: private actual 기록과 외부 annotation·human review를 별도로 결속하고, 녹화·reference·AI점수는 actual/human count0이다. 미완료 source·viewport·성능·운영 gate를 u172에 정확하게 인계한다.

## Tests / Validation

기존 `tests/unit/models/test_event_semantic_acceptance_u172.py`, `tests/integration/test_event_document_v3_replay_u172.py`, `tests/unit/orchestrator/test_event_v3_cutover_u172.py`, `tests/unit/orchestrator/test_event_preview_codex.py`, `tests/unit/orchestrator/test_event_preview_encryption.py`, `tests/unit/orchestrator/test_private_workflow_u155.py`.

신규 `tests/unit/briefing/test_event_article_review_u186.py`(AC2/3/4), `tests/unit/briefing/test_event_article_budget_u186.py`(AC1/4), `tests/unit/publisher/test_event_article_readiness_u186.py`(AC5), `tests/integration/test_event_article_acceptance_u186.py`(AC2–6). fixed-clock fake runner는 실제 provider 품질을 증명하지 않는다. 실제 adversarial semantic 성능은 private corpus에서 사람이 다시 확인한다.

구현·통합 후 실행:

```sh
uv sync --extra dev --extra docs --extra sector --extra operations
uv run python -m pytest -q tests/unit/briefing/test_event_article_review_u186.py tests/unit/briefing/test_event_article_budget_u186.py tests/unit/publisher/test_event_article_readiness_u186.py tests/integration/test_event_article_acceptance_u186.py
uv run python -m pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run python scripts/check_event_coverage.py --manifest tests/fixtures/event_briefing_v3/manifest.json
uv run python scripts/check_no_paid_apis.py
uv run python scripts/check_no_anthropic_sdk.py
uv run python scripts/check_curated_assets.py
uv run python scripts/check_image_store.py
uv run mkdocs build --strict
uv run python scripts/check_material_theme_contract.py
git diff --check
```

현재 설계에서 새 tests는 미작성이다. 위 명령은 구현 이후 실행 지시이며 PASS 기록이 아니다.


## 2026-10-26 개발 승인과 실행

사용자 개발/계속 진행 지시로 공통 FD/NFR를 구현 기준으로 채택했다. Functional Design/NFR Requirements는 작성 완료·승인 적용, 신규 인프라는 불필요하며 기존 CLI/auth/단일 finalizer를 유지한다. [구현·검증 기록](../event-news-v3-content-20261026/implementation-evidence.md)을 따른다. 기존 “현재 설계/테스트 미작성” 서술은 최초 계획 시점의 이력이다.

실제 생성된 테스트 경로는 `tests/unit/orchestrator/test_event_evidence_preparation_u184.py`, `tests/unit/briefing/test_event_packet_budget_u184.py`, `tests/unit/briefing/test_event_article_budget_u186.py`, `tests/unit/briefing/test_event_article_review_u186.py`, `tests/unit/publisher/test_event_article_projection_u185.py`, `tests/integration/test_event_article_acceptance_u186.py`다. 기존 계획의 미생성 별도 테스트 파일 역할을 이 경로들에 통합했고, nonexistent target을 검증 명령으로 실행하지 않는다. 실제 source·사람·운영 인수는 기존u172/u173의 별도 gate다.
