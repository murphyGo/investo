# 닫힌 원문 계약과 비기능 경계

## 실제 근거

- sample1 run45130745466, filing20261123000148, HTTP200/1GET/0.790076초/4380byte, XML1/27817byte/340nodes. response SHA09d4248a13da3837828c390ec04b2a71ec897e7a263ec4007a7f1d053cea7687. 검수 코드5d9885d2bebc7ea1a9b9d51b4c5d7df4338c708d와 실행 시간·아티팩트 결속 확인.
- sample2 run45136966583, HTTP200/1GET/1.041674초/4388byte 뒤 request_or_document_invalid. 원문을 보관하지 않았으므로 원인·양식 동일성을 추정하지 않는다. 재시도 없이 차단 증거로만 유지한다.

## Functional Design

FR-001/002/023/024: 별도 dart-trust-termination-6.2-v1, 명시적 trust-termination preview profile만 지원. 정정 없는 주요사항보고서(자기주식취득신탁계약해지결정), ACODE11335, FORMULA6.2/ADATE20260723. 목록/원문 issuer8자리·filing14자리·문서명·회사명·접수일 및 원문 표지 날짜를 일치시킨다. 기존 CB parser 파일/기본값/세 profile은 보존한다.

- TBL_ACQ_CNL의 17행/6열을 rowspan/colspan까지 해석하고 선택 필드가 정확한 행·열·TE/ACODE 또는 TU/AUNIT와 레이블에 귀속됨을 검증한다. 중복·누락·다른 표의 동일 코드·변경된 양식은 거절한다.
- 계약금액 해지 전/후, 계약기간 시작/종료, 해지목적·기관, 예정일·이사회결의일, 해지예정 보통/기타주식 및 bounded 기타 투자판단 주석을 원문 문자열 그대로 보존한다. '-'는 0으로 변환하지 않는다. 예정주식은 소각주식이 아니며 취득 완료는 신탁계약 해지 완료가 아니다.
- issuer/action/action_status/action_terms/filing_locator 5개 슬롯과 각 XML경로·ContextRef를 결속한다. 결의일과 예정일을 구분하며 occurred_at은 unknown으로 유지한다. 일자→09:00 사건 시각 추정 금지.
- 원문 주석은 240자 이하 단일 문단을 정확히 보존하고 전사 과거 보유 표·서명·연락처·이미지·첨부는 제외한다. 모델은 검증된 금액/조건/목적 외 의미나 시장 반응을 보충할 수 없다. native 원문 사실 검증 및 core_only detailed 차단은 유지한다.
- 후보선정은 명시적 parser_version의 문서명 적합성을 quota 전에 판별한다. 선택하지 않은 DART 문서는 계속 quarantine한다. 두 번째 실제 원문 지원을 주장하지 않는다.

## NFR Requirements / Design

NFR-002/003/006/007/008: 신규 provider/키/유료 호출 없음. 기존 공통 소유자의 fixed-host 최신목록1GET+원문1GET, global6회/20초/동시2/응답500KiB, ZIP/XML/credential guard 재사용. 미지원·중복·최신목록누락·정정/철회·불완전페이지·토큰검출은 fail closed, 자동 parser fallback 없음.

원문은 실행 메모리와 ignored0700/0600, 수신자 암호화1일 보관만 허용한다. 전용 qualification은 공식 XML의 원하는 데이터 추출 안내와 제한된 사실 범위에 근거하며 원문/사진/서명/첨부 재배포를 승인하지 않는다. 정적 합성 fixture에는 실제 회사/연락처/원문을 복사하지 않는다. projection1200자·ref240자·slot당16개 경계를 유지한다.

## 검증

합성 독립 fixture로 정상·금액 '-'·예정 상태·필드 소유권·중복/이동·행단위/단위/잘못된 날짜·XML 공격·토큰·입력 identity·기본 profile 거절과 최신목록+원문 mocked integration을 검사한다. private 실제 sample1 replay에서 XML 및 native5슬롯 값·해시를 확인한다. 별도 agent 코드 검수 뒤 exact CI를 완료하고 전용 preview qualification으로 실제 공통 준비/기사 캡처를 검증한다. 기사 유무·brief/detailed/source_limited를 관측대로 기록한다.

사람 사전 사건/핵심 사실 목록은 별도 요청 중이다. 사람 corpus0/12·5/5·외부 recall·viewport/성능·예약 실행 인수와 production 전환은 이 소스 지원 완료와 별개로 유지한다.
