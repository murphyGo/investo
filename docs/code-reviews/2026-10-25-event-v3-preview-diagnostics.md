# Event v3 private preview 진단 검토

2026-10-25 KST. 실제 preview `40114529910`의 국내 분류 실패 manifest가 v3의 닫힌
`ContextEvidenceError` 사유를 누락했다. native 분류 오류는 기존 legacy 진단 매핑에 없었다.

`scripts/preview_event_briefing.py`는 실제 native exception의 정확한 문자열이 `ContextRule`의
13개 Literal 중 하나일 때만 `failure_code`와 단일 진단 코드를 보존한다. 원문·모델 출력·stdout/stderr는
계속 제외하며 위조 문자열과 list/dict 같은 비문자열은 공개하지 않는다. 생성 prompt, 재시도·예산,
검증 gate와 게시·알림·cursor 경로의 변경은 없다.

독립 reviewer의 판정은 **All Clear, 열린 P1/P2 0**이다. focused 22 PASS와 허용 rule 13개,
위조 값 8개, 비-native cause 3개 직접 probe를 수행했다. Security Boundary와 Error Contract를
검토했고 외부 호출·secret 접근·파일 편집은 하지 않았다.

private workflow의 schema 선택 8줄은 별도 리뷰를 통과했다. 기본값 2, 선택값 2/3,
quoted CLI 전달, private/main 제한, contents read, 기존 `queue: max`·auth cleanup·ciphertext 보관을 유지한다.
공개 reviewed template과 private queue 외의 bytes가 같다. 실제 native preview boundary 3시장과 parser/workflow
무변경 probe 5개도 통과했다. 운영 활성화와 사람 평가의 승인은 이 판정에 포함하지 않는다.

## Stage 1 source span 지시 보완

실제 미국 진단 preview가 `context.fact_invalid`를 보존한 뒤, 검증기가 이미 요구하던 세부 규칙을
Stage 1 지시에 추가했다. Unicode end-exclusive/1–240 codepoints, 숫자 token만의 value 참조,
matching metadata field와 actual/forecast/consensus 상태 구분이다. gate와 원본 buffer는 바꾸지 않았다.
whole-fact numeric ref 거부 후 같은 buffer의 올바른 numeric ref가 두 번째 시도에 성공하는 회귀를 추가했다.

별도 reviewer가 실제 Python slice·span validator·숫자 정규식·metadata field owner와의 일치를 확인했다.
독립 focused 104 PASS(57 native replay 포함), Ruff/format/diff PASS, 열린 P1/P2 0이다.
이 synthetic 결과로 실제 모델의 정확한 offending component나 개선 효과를 확정하지 않는다.

## 필수 actual과 실제 홈 회귀

후속 실제 preview의 `context.required_missing`에 따라 기존 required-item/actual fact와 metric/unit/period/status
proof 조건을 prompt에 명시했다. 회귀는 필수 event 전체 누락도 같은 budget의 재시도에서 거부하고 올바른
source-owned fact만 수용한다. 첫 prompt 변경의 실제 수용 성공을 주장하지 않는다.

원격 전체 CI가 찾은 홈 두 실패는 본문의 제한 문구가 짧은 요약에도 있어야 한다는 가정이었다.
해당 integration 검사를 실제 계약인 카드별 visible quality/data-quality와 발행본 canonical 상태 일치로
바꿨다. 링크·날짜·미발행 검사와 기존 unit의 품질 모순 거부는 유지한다. 로컬 집중 106 PASS를 확인했다.
독립 검토도 focused 125 PASS, 실제 directory/flat build와 품질 attribute/visible text/동시 상향/field 삭제
4개 변조 거부를 확인했다. 선택 요약의 한계 문구 보존 unit도 그대로 통과했다. 최종 이 diff의 열린 P1/P2는 0이다.

## Opt-in private model recording

실제 후속 preview도 실패해 정확한 모델 참조를 조사하기 위한 R10 옵션을 추가했다. 기본 false,
schema 3/Codex 전용이며 기존 owned delegate와 타입을 유지해 auth lifecycle·retry accounting을 바꾸지 않는다.
prompt와 검증 후 stdout/returncode/hash만 기록하고 argv·stderr·auth state는 기록하지 않는다.
ignored 파일의 pre-auth 검사, await 후 symlink 검사, exclusive/no-follow 0600 쓰기와 기존 ciphertext-only
artifact 경계를 유지한다. 12회/1MiB 한도 초과는 전체 기록을 버리고 unavailable, in-flight 취소는 incomplete다.

로컬 focused 80 PASS, 독립 focused 78 PASS와 최신 암호화 4 tests PASS를 확인했다.
독립 추가 probe는 UTF-8/encoding/12→13회 초과, concurrent finish, abort, in-flight 취소/늦은 쓰기,
awaited alias, default2/off와 opt-in3, private/public workflow mirror를 포함한다. Security Boundary,
Concurrency/Lifecycle, Data Integrity/Memory, Error Contract를 검토했으며 열린 P1/P2는 0이다.
이 검토는 외부 서비스·실제 secret·source edits 없이 수행했고 모델 의미 수용이나 운영 활성화 승인이 아니다.

## 실제 unit 누락 수리

기록을 재생한 결과 required FRED 4개에 unit이 전달되지 않아 기존 gate가 거절했다. Source adapter에서
공식 metadata로 확인한 5개 default series에만 unit을 전달하고 custom/unknown에는 추측하지 않는다.
명시 non-lin 응답은 거절하고 기존 fan-out sibling 계약을 유지한다. Prompt의 unit/macro_unit 대안도 기존
field allowlist와 일치한다. 값·delta·기간·priority·request params/call count·secret 연결은 그대로다.

독립 focused130 PASS, unit 누락 시 required_missing·잘못된 unit field면 fact_invalid인 추가 probe도 통과했다.
Ruff/format/diff PASS, 열린 P1/P2 0이다. 추가 HTTP·실제 key·private 원문 접근·source edits 없이 검토했다.

## Source metadata 좌표 전달

실제 미국 기록의 metric/unit offset -1/+1 실패를 위해 동일 metadata boundary owner가 계산한
field별 정확한 범위를 Stage 1 row에 전달한다. 원본 context/revision과 전체 ContextRef 출력은 유지하고
지도 bytes도 기존 24KiB에 포함한다. 반환된 좌표를 자동 보정하거나 gate를 우회하지 않는다.

독립 focused 201 PASS(12.58s: native57, budget/handoff/refs/models/FRED/legacy preview 포함),
Ruff/format/diff PASS를 확인했다. 추가 Unicode/escape/key-like-value·동일 literal의 다른 필드 9개 probe는
좌표 owner 일치를 확인했다. 같은 문자열이 있어도 unit의 wrong field→fact_invalid,
다른 revision→item_mismatch, 없는 chunk→unknown_chunk 거절을 확인했다. 열린 P1/P2는 0이다.
실제 모델 성공과 사람 수용은 이 synthetic 검토에 포함하지 않는다.

## Korean 성분명 오탐과 fact subject 근거

실제 분류 1회 성공 후 합성 두 응답에서 일반 성분명 ‘관측값’, ‘단위’를 고유명사로 오인한 것을 확인했다.
두 표현만 기존 generic noun에 포함한다. 사건 actor와 별개인 fact subject ref 누락도 기존 gate로 거부하며,
이미 전달된 compact draft.facts의 모든 component ref를 복사하도록 Stage 2 지시를 명시했다.
evidence payload/16KiB owner와 출력 schema·budget은 그대로이고 자동 근거 보완은 없다.

최종 독립 focused113 PASS(7.92s), Ruff/format/diff PASS, 열린 P1/P2 0이다.
source value/unit/status/period, 필수 actor/object, 새 기관명 등 9개 변조를 계속 거부했고,
별도 fact subject ref까지 복사하면 seal, 그 ref 하나 누락 시 evidence_invalid를 확인했다.
native57과 multi_document 세 시장 회귀, reader/claim/finalizer/budget/handoff/refs도 통과했다.
검토 중 발견한 잘못된 event_digest import는 중복 mapping 제거와 함께 원본화했고,
최종 editorial_plan.py diff는 0이다. counterfactual과 fresh model/human 수용은 구별했다.

## Classifier status-proof 수락 경계

실제 국내 텍스트 fact가 상태 근거 없이 분류를 통과하고 canonical 단계에서 identity.fact_unbound로
실패했다. 기존 canonical 요건을 classifier 수락 단계에서도 context.status_unbound로 검사해 기존
attempt/budget 내에서 근거 복구 또는 비필수 fact 생략이 가능하도록 했다. lower context의 limited
평가와 원래 canonical 검사는 그대로다. required actual 누락과 네 status 역할의 증명 요건도 유지한다.

독립 최종 focused151 PASS(12.63s), Ruff/format/diff PASS, 열린 P1/P2 0이다.
텍스트 fact의 lower PASS/limited→canonical 거부 경로를 재현했으며, 새 guard 두 줄을 메모리에서
제거한 mutation은 6/6 회귀 실패를 검출했다. proof 복구/optional fact 생략 두 재시도와 네 status 양성,
native57·source-slot·identity·models·budget/handoff/metadata/refs 및 legacy/shadow/no-fact를 검토했다.
raw/private/key·외부 호출·파일 편집 없이 검토했다. 새 실제 preview 성공은 별도 증거다.
