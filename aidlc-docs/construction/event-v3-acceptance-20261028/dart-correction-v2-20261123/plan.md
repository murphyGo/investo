# DART 6.4 계약조건 정정 형식 지원

사용자 “진행시켜”를 기존 u173 Step4/u184 Step5의 다음 bounded 구현·검수 승인으로 적용한다. 앞서 승인된 commit/push와 비게시 private 진단 범위를 재사용한다. 상위 유닛·운영 활성화·사람 인수를 자동 완료하지 않는다.

## Stage Decision

Functional Design/NFR Requirements: Required. 아래 FD/NFR을 구현 전 확정한다. FR-001/017/024, NFR-002/003/005/006/007/008, R10/R13과 앞선 `dart-preparation-20261117`의 실제 차단 증거를 잇는다. 신규 provider·API·credential·LLM·게시 경로는 없다. 기존 v1과 기본 Fed-only preview를 보존한다.

## Functional Design

새 `dart-cb-terms-correction-6.4-v2`는 동일 FORMULA6.4/20260723·ACODE11324의 별도 정확한 7행 계약조건 정정 형식만 처리한다. 기존 가격 정정 parser의 item/context/refs/XML 의미와 synthetic fixture bytes를 보존한다. 별도 검수 완료된 schedule v1 통합에 따른 공용 모듈 확장을 허용한다. ZIP/XML/정규화/날짜/표 grid 같은 안전 primitives는 재사용하고, 새 형식의 의미 검증은 별도 source-owned parser에 둔다. 알려지지 않은 행·중복·범위·혼합 형식은 거절하며 v1 실패를 임의 fallback으로 전환하지 않는다.

회사·공시번호·접수일·viewer·legacy 정규화·response/XML digest·실제 UTC를 다시 결속한다. 정확한 정정 후 열을 같은 current issue의 만기·이자 지급·원금 상환·전환 청구 시작/종료·옵션·납입일과 본문 23항에 대조한다. 한 정정 행의 두 날짜는 1→2 관계로 검증한다. 23항은 중복되지 않는 제목/범위와 명시적 주석 경계를 확인해 정정 후 전체 값과 현재 원문을 결속한다. 원래 결정/납입 예정/만기를 발생 완료로 바꾸지 않는다.

긴 계약 문장은 원문 검증 단계에서 자르지 않는다. projection은 검증한 필드와 단위/라벨만 사용하며, 각 문단 ≤1,200자·최대6문단·총 ≤3,600자 안에서 완전한 필드 단위로 배치한다. 단일 필드나 필수 내용이 예산을 넘으면 전체를 거절한다. 모든 원문 binding과 source ref를 독립 재해석하고, native2 factory에서 내용을 하나도 잃지 않았는지 대조한다. ContextRef 한 개의240자·qualification slot당16refs 제한을 유지한다. 부족한 제한은 전역으로 완화하지 않는다.

v2는 명시적인 version 선택과 전용 preview qualification/slot snapshot으로만 접근한다. canonical8행/v1 transport hash는 보존한다. 별도 v2 snapshot은 같은 국내 공시 slot의 추가 형식 근거이며 local source 수를4로 세지 않는다. `SourceSlotQualification`은 선택적인 native context contract2를 갖되 기존 contract1은 직렬화에서 생략해 기존 matrix hash를 보존한다. shared HTTP owner는 선택한 version과 정확한 qualification/parser/fixture/code/rights hash를 대조한다. 미승인·quota 밖·실패 입력은 현재 generic 차단 경계를 유지한다.

## NFR Requirements

- 기존 공유6HTTP/동시2/20초·GET8초·retry/redirect0·raw/ZIP/XML500KiB·20knodes/depth256·defusedxml·credential echo 거절을 유지한다.
- v1 projection은1,200자 그대로다. v2만 명시적 retention qualification과 article passages로 ≤3,600자를 허용한다. 기존 일반 HTML ZIP 금지와 source-neutral briefing 경계를 유지한다.
- v2 parser/transport/projection/context 계약을 별도 version으로 결속한다. 기존 JSON/hash·v1 5slot25refs/29XML fixture 재생을 회귀로 검증한다.
- 원문은 ignored0700/0600·암호문1일이다. 공개 fixture는 직접 만든 synthetic 값/문장만 사용한다. 실제 issuer·금액·장문·base64 원문은 공개하지 않는다. 공개 증거는 count/hash/clock/closed code만 갖는다.
- 보관된 실제 응답의 offline 성공을 새 수집·현재 최신성·runtime 자격으로 세지 않는다. 이미 독립 검수된 schedule 실제 run45059739620의 동일 XML을 재사용해 공통 owner/native를 재생한다. 기존 private manual workflow/pin을 보존한다. v2 별도 새 수집·runtime 승격은 후속으로 남긴다.
- 추가 비용은 기존 무료 OpenDART 진단 최대5calls/실행과 수동 Actions job이다. 모델·게시·알림·ledger·cursor0, activationfalse 및 기존 운영/preview/AI report pin은 유지한다. 별도 실제 positive 검수 전 runtime0이다.

## 구현·검수 계획

- [x] 1. 이전 실측 원문과 현 경계를 대조하고 FD/NFR·버전 분리·승인 범위를 기록한다.
- [x] 2. 새 7행 parser와 synthetic fixture를 구현하고 원문 binding/5slot/native2 완전성 및 부정 회귀를 통과한다.
- [x] 3. 선택적 context contract·typed v2 qualification·동일 HTTP owner/preview probe의 명시적 version을 연결한다.
- [ ] 4. 독립 QA·기존 hash/보안/예산 회귀·정적 검사와 exact code CI를 통과한다.
- [x] 5. 기존 실측 run45059739620의 암호문·private5파일 해시를 재확인하고 같은 clock/원문을 shared owner에서 v2로 재생한다. 새 HTTP·v2 runtime 판정은 만들지 않는다.
- [ ] 6. session/cross-check/evidence/state/audit와 기존 u173/u184 잔여를 갱신하고 승인 범위만 전달한다.

## 승인·미해결 입력

현재 사용자 지시는 직전 제시한 새 정정표 parser 지원 검수의 진행 승인이다. 기술적 범위/예산 선택은 위 기존 계약 안에서 처리한다. 현재 추가 사용자 답변이 필요한 항목은 없다. 23항의 정확한 원문 결속과 실제 projection/ref 예산은 독립 원문 검수로 확정하며, 불가능하면 성공으로 꾸미지 않고 닫힌 실패와 구체적인 잔여로 기록한다.


## Parser foundation 검수

v1+v2 독립105PASS 및 보관본154 XML 경로/속성/값·5slot22refs 재생을 통과했다(C/H/M0). 초기 참조분할의 날짜 overlap과 표 cell 경계 문제를 고쳤다. v2는 날짜/숫자 regex를 독립 탐색하며, note23은9개 source node 전체를 검증한 뒤 P별 값과 논리5열 TABLE로 직렬화한다. 실제2950자/3문단/terms13refs이며 context SHA4556979982e0e0e1200c7b43381624bb4d51faceed8f990f5c756e624afa280d다. source/fixture/test3파일 최초 foundation은 `a4b6f5dd402767cd1f4f060867e523d20876d551`이었다. 통합 검수의 XML 경계 수리와 synthetic 표 위치 수정 후 새 immutable ancestor로 자격을 재결속한다. 이후 v2 qualification의 parser code 근거로 이 immutable ancestor를 사용하며, 전체 연결과 함께 한 번 push/최종head CI를 검증한다. 기존 canonical8행/v1 policy typed hash는 exact 보존됐다. 전용 v2 snapshot의1sample/5slot은 기존 default8slot CLI 인수로 세지 않는다. 새HTTP0·runtime0이다.


## 연결 검수

새explicit version/one-row variant/native2 binding은 독립255PASS와C/H/M0이다. phase2의10파일 해시를 code-review.json에 고정했다. canonical8row/v1typedhash는그대로다. Ruff878·source/script mypy374·strictdocs6.50초를 통과했다. 이 시점의 실제source요청0이며, 이후 확인된 기존 schedule 실측 재사용 결정으로 새pin/manual 재측정 계획은 폐기한다. 기존 private workflow/pin과 실제450597 기록을 보존한다.


## Existing schedule work reconciliation

The completed schedule v1 implementation and independently reviewed live run were discovered late in the initial workspace audit. Merge the existing d6ce1050 branch and preserve its evidence. Schedule v1 projects661 characters of corrected schedule facts; terms v2 retains2950 characters including full corrected clauses and note23. The latter remains a separate article-passage candidate, with no automatic fallback or live acceptance inferred from the schedule run.

The public manual template remains byte-identical to the reviewed price/schedule workflow (SHA4f8c4a88). The CLI explicitly selects price/schedule/terms; the previously introduced --parser-version v1/v2 aliases select price/terms and are mutually exclusive with --parser-profile. Conflicting internal selectors fail before HTTP.

The actual450597 capture's five files, response/XML digests and original receipt clock were verified. A MockTransport replay through the shared owner/native factory produced2950 characters/3paragraphs/5slots22refs154XML bindings, nativeSHA927c47a4e318959c355dfb7ccd0063d1c1adb002ffeb36b1e6f15a7e983533d5. New source HTTP0 and model/publication/notification/ledger/cursor0. This is retained-response evidence, not a new live run.

Pre-integration3b8 CI45060834986 passed8152 tests/1skip and39Node tests. Integrated focused226PASS, Ruff/format881 files and source/script mypy374 passed; final exact-head CI and independent integration review remain pending.


## Integration review repair

Independent integration review found M1: unwrapped correction/section text, direct child tails and page-break content could be ignored. Reject all those shapes, unknown empty nodes and text outside table cells. Thirteen negative regressions cover these cases. Move only the invented terms fixture's note table to the actual qualified position after seven paragraphs; price/schedule fixtures are untouched. Actual retained context927c and154XML bindings remain unchanged. The fixed parser source/fixture/tests are committed as a new immutable ancestor before qualification is rebound.
