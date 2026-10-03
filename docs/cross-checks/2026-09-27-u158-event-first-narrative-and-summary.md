# u158 요구사항 cross-check

2026-09-27. 승인된 E6/E7, B6/B8 및 AC-158을 현재 구현과 대조했다. 독립 리뷰 교정과 집중 검증, 전체 5,521개 테스트(402.28초)를 통과했다. AC-158.1–6 결과: PASS.

| 기준 | 증거 |
|---|---|
| AC-158.1 정책·실적·제품·발언의 구체 설명 | `test_event_narrative.py`의 4종 주석 fixture, `test_event_finalization.py`의 실제 finalizer 경로. 시점, 주체, 필수 fact, 의미/반응 상태, source를 확인한다. |
| AC-158.2 제목/URL만으로 완료 인정 금지 | `test_event_blocks.py`의 필드 제거 negative는 event survival을 잃는다. 출처 누락은 detail_limited이며 원문을 재생성하지 않는다. |
| AC-158.3 숫자 없는 첫 완전문장·0건/수집 부족 | 80자 첫 문장, 긴 단일 문장 거부, 0건/limited/모두 제거 구분, 뉴스 정상·가격 부족 분리 회귀. |
| AC-158.4 생존 사건만 요약/DTO·재실행 동일 | real finalizer의 사건/section 제거, partial sibling, minimal fallback 및 sealed briefing 재입력 회귀. |
| AC-158.5 사실/명칭/근거·기존 hard gate | field-local refs, actual/forecast 교환, source·entity·숫자 tamper, compliance 및 canonical model_copy 거부. 자유 서술의 의미 평가와 구조 검증의 범위를 구분한다. |
| AC-158.6 호환성·2단계·7섹션·면책 | Claude/Codex 합성 subprocess에서 2회 정상/3회 retry, off/shadow 및 legacy wrapper prompt·문서 bytes 동일, empty event context 호환, 실제 HTML·기존 면책 유지. u154/u156의 별도 구현 완료는 추정하지 않는다. |

## 검증과 한계

생성/비게시 preview/provider replay 58개 통과(3.49초), 최종 publisher unit/integration 42개 통과(1.94초), 전체 Ruff/format626 및 mypy278 source 통과. 유료 API/Anthropic SDK/curated asset/image store 정책 검사, strict MkDocs(6.69초), Material CSS/HTML 계약 검사 통과. 최종 전체 5,521개 및 benchmark p95 69.97ms를 validation.json에 기록했다.

preview는 pure 생성/finalizer 경로로 구현했고 공개 CLI/main/run_pipeline에서는 차단한다. archive/Git/cursor/notification 쓰기 0회를 fixture로 검증했다. active capability는 false이며 u159 gate 전에는 운영 활성화를 하지 않는다. terminal identity receipt는 생성하지만 실제 E11 publication ledger 소비는 u159에서 연결한다. 주말·장후 window 확대는 u160 범위다.

실제 LLM 서비스, scheduled shadow, production notification/Pages, 운영 end-to-end p95는 미실행이다. u145 viewport gate 및 DEBT-090은 변경하지 않는다.
