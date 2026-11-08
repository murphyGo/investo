# DART 원문 parser 후속 범위 — u173 Step4 / u184 Step5

2026-10-30. 원문 요청 성공과 parser·source qualification은 별개다. 새 유닛이나 활성화를 만들지 않고 기존 미완료 단계에 연결한다. [실제 probe 증거](runtime-20261030.json)의 ZIP/XML digest를 재사용하며 원문을 다시 요청할 필요가 없다.

## 공식 계약 확인

- [OpenDART 소개](https://opendart.fss.or.kr/intro/main.do)는 개인·기업·기관이 공시 원문 XML에서 원하는 자료를 추출해 활용할 수 있다고 명시한다. 이 근거로 제한된 사실 추출을 설계할 수 있다. 원문 전체·이미지·서명·첨부 재배포 허가로 확대 해석하지 않는다.
- [이용약관](https://opendart.fss.or.kr/intro/terms.do)의 제10조는 접속/횟수 제한, 제11조는 원칙적 무료 서비스, 제16조는 API/프로그램 저작권과 그 밖의 저작권법·공공데이터법 준거, 제19조는 인증키의 제3자 이용 금지를 규정한다. 기존 키를 secret owner 안에서만 쓰고 공개 결과에는 원문 대신 출처 링크·사실 요약을 남기는 범위다. 이는 전체 공시 문서에 대한 포괄적 재배포 판단이 아니다.
- [원본파일 가이드 DS001/2019003](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)는 GET document.xml, 인증키와 14자리 접수번호, binary ZIP 응답을 명시한다. 확장자가 xml이어도 ZIP이다. HTTP200만으로 문서 성공으로 판정하지 않고 provider 오류 XML을 구분해야 한다.
- [공시검색 가이드 DS001/2019001](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)는 접수번호의 viewer 연결, YYYYMMDD 접수일자, 기재정정/첨부정정 및 정정·철회 비고를 구분한다. 접수일자는 정확한 공표 시각이 아니다.

위 문서들을 확인했지만 qualification matrix는 변경하지 않았다. 제한된 추출/보관 범위, versioned parser와 실제 필수 field refs가 하나의 검토 가능한 증거로 결속돼야 승격할 수 있다.

## 실제 확인한 문서에서 지켜야 할 매핑

진단 표본은 공시20261027000337의 **전환사채 발행 결정 정정**이다. 발행 완료나 납입 완료가 아니다. 문서에는 정정 전후 값과 다른 차수의 채무가 공존한다.

| 필수 slot | 후보 위치 | 남은 결속 |
| --- | --- | --- |
| issuer | COMPANY-NAME / AREGCIK | 같은 문서의 발행 주체와 기존 source identity |
| action | DOCUMENT-NAME의 ACODE11324 및 PL_KND/SEQ_NO | 지원하는 양식·행위만 닫힌 enum으로 처리 |
| action_status | CORRECTION / CRT_RSN / CRT_PLN | 정정된 결정·계획을 완료 사건으로 바꾸지 않음 |
| action_terms | DNM_SUM, EXE_PRC, STK_CNT/STK_RT, MIN_PRC, PRFT_RATE/LST_RTN_RT, FND_USE2 및 날짜 TU | 현재 발행 차수·정정 후 열·단위/기간·각 숫자의 정확한 ref |
| filing_locator | 요청 rcept_no + XML member명 + 응답 digest + 기존 viewer URL | XML에 접수번호 필드가 없으므로 본문에서 발명하지 않음 |

board date·correction date·planned payment·maturity를 별개로 보존한다. 정확한 공표 시각은 unknown이며 기존 source clock의 정밀도 계약을 따른다. selector가 중복되거나 정정 후 열을 구분하지 못하면 해당 slot은 blocked다. 전체 텍스트 평탄화나 첫 숫자 선택으로 필드를 채우지 않는다.

## 구현과 검증에 남은 일

1. 기존 HTML body 경로는 ZIP을 받지 않는다. DART XML을 연결하려면 source owner 안에 명시된 bounded parser 계약을 설계한다. 현행 N184의 ZIP 금지는 유지하며, 실제 경로 연결에 필요하면 해당 범위를 명시적으로 개정한다. 수동 진단 probe를 production fetcher로 우회 재사용하지 않는다.
2. 이미 검수한 1GET/no retry/8초·20초, 압축/총 해제500KiB, member16/XML node20k/depth256, STORED/DEFLATED 압축만 허용, defusedxml의 DTD/entity/external 금지·secret echo·closed encoding 경계를 보존한다. 목록 수집과 body enrichment의 공유 실행 예산을 넘기지 않는다.
3. 양식/version별 구조를 유지해 동일 차수·정정 후 조건의 typed chunk와 exact source refs를 만든다. field 단위 검증과 정정 전후/다른 차수 혼합·누락·중복·날짜 혼동 음성 fixture를 추가한다. 공개 fixture는 별도 합성 예시이고 실제 원문은 ignored private capture에만 둔다.
4. source/response/parser/context/fixture/policy/matrix hash 및 다섯 slot refs를 실제 factory replay에 결속한다. 공개 증거는 allowlisted count/hash/code만 기록한다.
5. 정확한 코드 CI·독립 source QA 후 matrix의 각 missing slot/rights scope/runtime 상태를 증거대로 갱신한다. local 검증과 runtime probe 및 activation은 각각 판정한다.

현재 local2/8 verified, runtime0, DART blocked, activation=false다. 이번 공식 문서 확인은 parser나 실제 기사 인수를 대신하지 않는다.
