# Event/news v3 구현 AC 대조

2026-10-12 KST. 범위 u168–u173, 구현 SHA `ca631e245d0341c09ea1671c32c4286dbd2c9c3a`. Checked by Codex.

공통 요구사항은 `docs/requirements.md`와 승인된 v3 C1–C8/N1–N8이다. Complete는 아래 자동 구현 경계의 검증을 뜻하며 human-ready/release-ready를 뜻하지 않는다. 최종 full gate의 실행 결과는 공통 구현 증거에 기록한다.

| 상태 | AC 수 |
| --- | --- |
| Complete | 47 |
| Partial | 6 |
| Pending | 3 |

## u168

| AC | 상태 | 구체적 증거 / 제한 |
| --- | --- | --- |
| AC-168.1 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.2 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.3 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.4 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.5 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.6 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.7 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.8 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.9 | Complete | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS |
| AC-168.10 | Partial | `test_event_identity_v3.py`, `test_event_publication_v3.py`: normalization/correction/remote CAS; 전체 runtime 성능 비교 pending; offline bound 측정 완료 |

## u169

| AC | 상태 | 구체적 증거 / 제한 |
| --- | --- | --- |
| AC-169.1 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.2 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.3 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.4 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.5 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.6 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.7 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.8 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |
| AC-169.9 | Complete | `test_event_document_finalization_v3.py`, `test_event_document_claim_boundaries_v3.py`, `test_event_reader_html_v3.py`, `test_event_numeric_containment_native_v3.py` |

## u170

| AC | 상태 | 구체적 증거 / 제한 |
| --- | --- | --- |
| AC-170.1 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.2 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.3 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.4 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.5 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.6 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.7 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.8 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.9 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.10 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.11 | Complete | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py` |
| AC-170.12 | Partial | `test_event_story_semantics_v3.py`, `test_event_story_contract_v3.py`, `test_native_story_retention_v3.py`, `test_event_publication_v3.py`; 200active/5MiB 경계·offline 시간 완료; end-to-end pending |

## u171

| AC | 상태 | 구체적 증거 / 제한 |
| --- | --- | --- |
| AC-171.1 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |
| AC-171.2 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |
| AC-171.3 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |
| AC-171.4 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |
| AC-171.5 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |
| AC-171.6 | Partial | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS; final HTML 회귀 완료; 실제 390×844/1440×900 viewport 미실행 |
| AC-171.7 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |
| AC-171.8 | Complete | `test_event_surface_views_v3.py`, `test_native_event_summary_v3.py`, `test_event_reader_html_v3.py`, `test_archive_discovery_u179.py`; independent 166 PASS |

## u172

| AC | 상태 | 구체적 증거 / 제한 |
| --- | --- | --- |
| AC-172.1 | Complete | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py` |
| AC-172.2 | Partial | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py`; synthetic required facts/unsupported negative 완료; 실제 corpus pending |
| AC-172.3 | Pending | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py`; 실제 0/12 문서, 사람 0건; AI score 발급 없음 |
| AC-172.4 | Complete | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py` |
| AC-172.5 | Complete | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py` |
| AC-172.6 | Complete | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py` |
| AC-172.7 | Pending | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py`; 예약 관찰 0회·runtime rollback rehearsal 미실행 |
| AC-172.8 | Partial | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py`; budget/privacy/기존 gates 완료; actual end-to-end p95 pending |
| AC-172.9 | Pending | `test_event_document_v3_replay_u172.py` 57 cases, `test_event_semantic_acceptance_u172.py`, `test_event_v3_cutover_u172.py`, `test_event_preview_native_v3.py`; all3accepted·실제10회·reviewed cleanup 미확보 |

## u173

| AC | 상태 | 구체적 증거 / 제한 |
| --- | --- | --- |
| AC-173.1 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |
| AC-173.2 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |
| AC-173.3 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |
| AC-173.4 | Partial | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked; source-owned factory/actual field mapping 검증; 실제 private parser capture pending |
| AC-173.5 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |
| AC-173.6 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |
| AC-173.7 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |
| AC-173.8 | Complete | `test_source_slot_qualification_u173.py`, `test_event_source_slot_mapping_u173.py`, `test_event_source_slot_checker_u173.py`; offline manifest 0 verified/8 blocked |

## NFR 적용과 남은 작업

1,000 items/warm10 offline preparation p95 38.631ms, Stage1 24553 bytes; four-document/eight-fact Stage2 15588 bytes. 200active ledger 184033 bytes, p95 19.789ms. 모두 실제 직렬화로 측정했다. 전체 수집→CLI→finalization→publish p95/baseline/표본은 미확보다. DEBT-090은 그대로다.

현재 미완료는 실제 corpus와 사람 검수, native viewport, source private parser capture/runtime qualification, reviewed release/pin, genuine scheduled 관찰과 최종 legacy cleanup이다. 각 owner와 절차는 [수용 runbook](../../aidlc-docs/construction/event-news-v3/private-acceptance-and-cutover-runbook.md)에 있다. 기존 등록 unit 안의 명시된 수용 작업이며 새 debt 번호를 중복 발급하지 않았다.

private raw/CLI output/secret public 유출을 허용하지 않았다. 두 private 경로의 git check-ignore를 확인했고 production pin/HTTP/cursor/기본 schema는 변경하지 않았다. synthetic 성공을 human 5/5, source 복구, actual scheduled로 다시 라벨링하지 않는다.
