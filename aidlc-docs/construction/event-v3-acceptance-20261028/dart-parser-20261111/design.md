# DART 정정공시 parser — u173 Step4 / u184 Step5

2026-11-11. 사용자의 “진행시켜”는 기존 parser/5필수 field 후속의 설계·구현·검수를 진행하는 승인이다. 새로운 source/provider·secret·HTTP·runtime/production 활성화를 추가하지 않는다.

## Stage Decision / FR·NFR

Functional Design/NFR Requirements: Required, 이 문서에서 기존 u173/u184 설계를 구체화한다. FR-001/002/017/024, NFR-002/003/005/008, R10/R13 및 기존 source-slot/C2/finalizer 계약을 재사용한다. 변경은 기존 DART source가 보관한 원문 ZIP을 오프라인으로 안전하게 읽고 typed context/정확한 refs로 매핑하는 범위다. live N184의 HTML-only/ZIP 금지와 u161 HTTP owner는 유지한다.

## 처리·의미·출처 계약

- 기존 목록 `NormalizedItem`과 단일 `rcept_no.xml` ZIP, 응답 digest, received_at을 받는다. 목록 source/공시번호/회사코드/공개 viewer URL/접수일, XML 회사코드와 요청·파일명·digest를 서로 결속한다. API key나 API query URL은 저장하지 않는다.
- 초기 parser version은 FORMULA-VERSION6.4/ADATE20260723, DOCUMENT-NAME ACODE11324와 목록 report_nm의 정확한 `[기재정정]` 상태인 전환사채 발행결정 **정정**만 지원한다. BODY의 현재 발행 차수와 정정 표의 정정 후 열을 구분한다. 다른 차수·정정 전 표·첫 숫자를 현재 조건으로 선택하지 않는다.
- 정정 표의 단일4열 header와 bounded rowspan/colspan grid를 읽어 전환가액·주식수/비율·최저 조정가액의 정정 후 값이 현재 body ACODE와 동일한지 대조한다. 지원하지 않는 양식/모호한 열·중복 필수 필드·누락·불일치는 닫힌 실패다.
- 필수5slot은 issuer(COMPANY-NAME/회사코드), action(DOCUMENT-NAME/PL_KND/SEQ_NO), action_status(CORRECTION/CRT_RSN/CRT_PLN), action_terms(현재 amount/price/shares/ratio/floor와 별도 source dates), filing_locator(목록 공시번호+viewer/요청/member/digest 결속)다.
- CRT_PLN의 발행 예정은 계획으로만 보존한다. 발행/납입 완료를 추론하지 않는다. 접수일·최초제출일·이사회일·납입예정일·만기는 서로 구분하고 정확한 공표/사건 시각은 unknown이다.
- source-owned 정규화 projection의 각 값에 XML path/attribute·원본 XML digest를 결속한다. 기존 C2 factory의 document/revision/chunk/offset/hash를 사용한다. 원문 전체를 평탄화하지 않으며 작은 필수 field projection만 최대1,200자로 보관한다. listing title/summary는 보존하고 source 날짜 정밀도만 보존한다.

## 보안·예산 / NFR 보완

새 HTTP/LLM/게시/알림/ledger/cursor I/O0. source API key를 읽지 않는 순수 parser다. ZIP 압축/총 해제 각각500KiB·member16·XML nodes20k/depth256; STORED/DEFLATED만, 암호화/경로탈출/중복member/symlink/unknown encoding/DTD/entity/external 모두 거절한다. 실사용 양식은 단일 정확한 XML member만 허용한다. 전체 source guard와 기존 C2 chunk4/각1,200자·ref240자/field16refs 한도를 유지한다. 오류/기본 repr에는 raw field를 넣지 않는다. 공개 fixture는 별도 합성 예시, 실제 ZIP/XML/정규화 데이터는 ignored0700/0600에만 둔다.

권리 근거는 공식 OpenDART 소개/약관의 제한된 자료 추출 범위와 기존[인계](../dart-parser-handoff-20261030.md)다. 원문 전체·이미지·개인 서명·첨부 재배포 허가로 확대하지 않는다. public manifest에는 count/hash/closed code만 남긴다.

## 수용 / qualification 분리

1. 합성 양성의5slot refs와 단위·날짜·현재 차수를 검증한다. 정정 전후/다른 차수 혼합·숫자 교체·중복/누락·행 span 변조·URL/공시/회사/해시 불일치를 거절한다.
2. ZIP/XML 보안·node/depth/byte 한도, raw/error/secret 누출, deterministic context/hash, clock·legacy item 보존 회귀를 통과한다.
3. 보관된 실제 원문 digest를 다시 확인하고 같은 parser와 C2 factory로5slot/원문 path/offset/hash를 독립 대조한다. 새 HTTP나 새 모델/사람 인수로 세지 않는다.
4. 독립 code/source QA, focused/full/static/policy/docs 검증 후 증거를 남긴다. global ops matrix의 source2/8·runtime0·DARTblocked/activationfalse는 별도 qualification 결정 전 유지한다. 다른 source 미완료 때문에 u173 Step4/u184 Step5 전체를 완료로 올리지 않는다.
