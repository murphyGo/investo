# u157 사건 근거·선정·발행 확인 기반

2026-09-27 사용자 요청으로 개발·검증·유닛별 커밋/푸시를 승인받았다. 현재 상태: Code Generation 8/8 완료, 유닛 커밋·푸시 준비 완료.

## 구현

- E1–E5: immutable 사건/근거 DTO, 실제 전송 문자열의 codepoint span, source/projection revision 분리, 필수 fact 재계산과 canonical 사건 ID를 구현했다. 같은 문서의 두 제품은 분리하고 기존 사건의 새 사실·공식 근거·날짜 보강은 기존 ID로 연결한다. 상충 fact는 순서로 덮어쓰지 않는다.
- 후보: canonical 문서 중복을 lane 배정 전에 제거한다. 기존 macro/공식 crypto 정책 보호를 유지하면서 news와 명시적 actual 발표를 최대 24건 예약한다. 96/24/12 입력 상한과 12 drafts/64KiB 응답 한도를 유지한다.
- Stage1 v2: required macro payload/ID, section 의미, 정확한 refs를 전달한다. 유효한 events=[]와 누락/실패를 구분하고 기존 retry 안에서 처리한다. 잘못된 출력은 코드만 남기고 원문을 예외·로그로 전달하지 않는다.
- Stage2 handoff: 0~5건의 실제 근거 행과 8KiB protected block을 함께 만든다. grouped/unassigned에서도 같은 근거를 중복 전송하지 않는다. 가격 14개와 뉴스 2개 사례는 뉴스 2개와 가격 12개가 남는다.
- 공유: 공식 Fed monetary release/speech만 source+host+path로 검증하여 최대 6건 추가한다. native coverage와 세그먼트별 선정은 독립이다. u74 allowlist는 article 인증이 아니므로 지정학 글로벌 공유의 대체 근거로 사용하지 않는다.
- E11: 기존 publisher의 선택적 PublicationRequest/PublishReceipt를 추가했다. 원격 ancestry와 metadata CAS, push 응답 유실, remote 전진·rebase를 구분한다. pre-commit 오류/취소는 파일/index를 복원하고 commit 이후는 보존한다. 기존 staged 다른 파일은 mutation 전에 거부한다. private receipt는 원자적으로 저장하며 원격 확인 뒤 저장 실패는 게시 결과와 구분한다.
- 7일 event receipt는 fixed Git SHA만 읽으며 hash/ID만 보존한다. off/shadow는 동일 v1 입력·프롬프트·문서를 사용하고 event metadata를 쓰지 않는다.

## 구현과 활성화의 경계

`INVESTO_EVENT_BRIEFING_MODE` 기본값은 off다. u157에는 v2 consumer를 위한 선택·렌더·transaction API를 구현했으며 preview/active 진입은 코드 capability로 차단한다. u158이 실제 v2 생성·비게시 preview 및 sealed survivor를 연결하고, u159가 최종 품질을 검증한다. 이 선행 계약은 처음부터 u157의 완료 범위다. 실제 생성·발행 활성화나 scheduled shadow를 수행하지 않았다.

기존 `NormalizedItem` serialization에서는 새 event_evidence=None 키만 생략하고 기존 null 키를 유지한다. CLI 호출 수는 2단계 그대로다. workflow, archive, site_docs, credentials 및 다른 유닛 구현은 변경하지 않았다.

## 검증

최종 전체 회귀 5,415개 통과(377.62초), 사건·발행 통합129개 통과(58.37초), 마지막 추가 경계를 포함한 foundation/input/classification61개 통과(1.48초). 전체 Ruff/format(614파일), mypy(273source), 정책4종, strict MkDocs, Material 검사 통과. 결과는 validation.json 및 docs/cross-checks/2026-09-27-u157-event-evidence-selection-contract.md에 기록했다. NF3 재현 명령은 `uv run python scripts/benchmark_event_selection.py`이며 1,000건/10회 p95 57.239ms(예산200ms)를 확인했다. end-to-end 운영 p95/DEBT-090은 이 측정으로 완료 처리하지 않는다.
