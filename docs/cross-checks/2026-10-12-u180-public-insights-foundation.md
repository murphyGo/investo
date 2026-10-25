# u180 요구사항 대조

2026-10-12 · `cross-check` skill · scope FR-026 / AC-180.1–8 / NF180.1–6.

검토 대상은 `55c00fc85e2828f62cd69d5583afd3761ef86d45` 기준 격리 worktree의 미커밋 구현이다. FR-027/028/029와 US-011/012/013의 실제 화면은 다음 유닛이 소유한다. 이 보고서는 primary agent의 요구사항 대조이며 별도 코드 리뷰와 구별한다.

## 수용 기준

| 기준 | 로컬 구현 결과 | 근거 |
| --- | --- | --- |
| AC-180.1 기본 경로 보존 | PASS | `test_config_default_off`, `test_envelope_never_serializes_into_item_or_prompt`, collector opt-in test; legacy models/aggregator/pipeline 568 및 관련 회귀 704 tests |
| AC-180.2 숫자·정의·시간·권리 gate | PASS | contracts PBT/negative tests; `test_reviewed_semantics_must_match_not_only_definition_string`, future/unsupported time, href, owner, rights tests |
| AC-180.3 수집 한 번·기존 consumers 분리 | PASS | 두 pipeline collection 경로, empty report sink, items-only injection, 실제 origin fallback 및 capture tests; 공통 phase에 source HTTP/LLM/Telegram 호출 없음 |
| AC-180.4 snapshot/history 일관성과 경계 | PASS | store hash/readback/rollback/symlink/corrupt-backup tests; caps, provider 변경, rights/retention 철회; `test_inactive_module_rights_or_retention_withdrawal_is_published` |
| AC-180.5 원격 확정·동시 게시·취소 | PASS | 실제 로컬 bare Git 통합 tests; disjoint metadata rebase와 same-manifest CAS; unknown→reconciliation, cancellation drain, live transaction lock, pre-existing index 보존, committed-byte mismatch push 차단 |
| AC-180.6 시황 실패와 별도 결과 | PASS | `test_confirmed_insights_survives_later_generation_failure`, failed briefing의 confirmed GHA output, private Pages OR/종료코드 tests, `test_failed_other_module_does_not_degrade_healthy_sibling` |
| AC-180.7 자원·정책·calendar | PASS, 합성/로컬 범위 | 32 지표/module·128 일정·366 이력 관찰 제한; 약 8MiB history의 새 커밋/로컬 원격 게시 benchmark; official-calendar 2026 holiday/unsupported-year tests; static/policy/build guards |
| AC-180.8 구현과 운영 수용 구별 | 기록 PASS; 운영 DEFERRED | state/plan의 7/8 로컬 구현과 Step 8 운영 대기, production qualification 빈 목록, default off. 실제 private pin/Pages/5회 예약 실행은 수행하지 않음 |

## NFR

| 기준 | 결과 | 증거/범위 |
| --- | --- | --- |
| NF180.1 추가 source/LLM/Telegram 0 | PASS | collector의 기존 1회 경로 재사용, 독립 phase는 typed 입력만 소비; default source/tier/timeout 계약 회귀 |
| NF180.2 크기·개수 cap | PASS | DTO·projection·store·remote blob size bounds; maximum/33rd metric·aggregate input·history tests |
| NF180.3 자원·취소 | PASS, 로컬 합성 | `scripts/benchmark_insights_resource.py`, resource evidence; bounded Git deadline·local budget, cancellation drain test. 실서비스 지연을 검증한 결과로 확대하지 않음 |
| NF180.4 공개/비공개 경계 | PASS | envelope `exclude=True` 및 capture strip, public href/escaped label, closed failure result, 실제 source permission 기본 false, 정책 guards |
| NF180.5 신뢰성·보존 | PASS | receipt/CAS 기존 34 tests, 새 transaction durability·recovery·동시 writer·remote unknown 통합 tests |
| NF180.6 source calendar | PASS, 2026 범위 | SOFR/EFFR 7월 3일 차이·H.10 holiday publication·미지원 연도 unknown; 신규 원천별 parsing/recording은 후속 유닛 |

## 후속 작업

FR-026의 로컬 구현은 수용 기준을 충족한다. 운영 인수는 명시적으로 보류돼 있으므로 전체 FR-026/유닛을 실서비스 Complete로 표시하지 않는다. 후속 u181은 공통 코드에 의존하며 u180의 다중 모듈 운영 관찰은 consumer 구현 이후 수행한다. 기존 debt/activation gate의 완료 상태를 변경하지 않는다.

검증 명령과 시점별 수치는 [validation](../../aidlc-docs/construction/u180-public-insights-snapshot-and-publication/code/validation.json), [구현 요약](../../aidlc-docs/construction/u180-public-insights-snapshot-and-publication/code/summary.md)을 참조한다.
