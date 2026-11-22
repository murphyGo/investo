# DART 계약조건 정정 v2 지원 검수

사용자 “진행시켜”로 기존 u173 Step4/u184 Step5의 [계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-correction-v2-20261123/plan.md)을 진행한다. 이전 commit/push/private 비게시 진단 승인을 적용한다.

## 구현과 독립 검수

같은6.4/20260723·11324 양식 안에서도 가격 정정과 계약조건 정정은 서로 다른 profile이다. 기존 v1 파일과 fixture는 바꾸지 않고 v2 source parser를 분리했다. v2는 정확한7행의 정정 후 값을 같은 차수의 본표 만기·이자·상환·전환기간·옵션·납입일 및 현재23항 전체에 결속한다. 23항 포인터는 정정후8P+1TABLE 전체와 현재 본문의 순서·태그·전체 텍스트·각cell/span 구조를 대조한다.

기존240자 ref 제한을 유지하면서 숫자·날짜·단위를 자르지 않도록 범위를 나눈다. 표는 원문 header와span에서 논리5열을 구성하고 모든 데이터 cell 경계를 보존한다. 필드 전체를 ≤1200자 문단·최대6문단·총3600자 안에 배치한다. 예산이 부족하면 전체를 거절하며 잘라낸 내용을 완전한 계약으로 승인하지 않는다.

가격 정정과 자동 fallback을 섞지 않는다. 기본값은 v1이며 v2는 별도1행 slot snapshot/preview transport와 명시적인 version 선택이 필요하다. generic context contract2는 기존값1을 직렬화에서 생략하므로 기존 canonical8행과 v1 정책 hash가 정확히 같다. 두 version 모두 동일 prepare_event_evidence owner의 전체6HTTP/동시2/20초·GET8초·raw/ZIP/XML500KiB와 기존 XML/비밀값 경계를 쓴다. runtime active capability는 false다.

보관된11월21일 실제 응답을 새 parser로 offline 재생해 **2950자·3문단·5slot22refs·154 XML binding**과 native2 전체 보존을 확인했다. 새 수집이나 현재 최신성 증거는 아니다. 새 HTTP와 모델/게시/알림/ledger/cursor 호출은0이다. 전용 snapshot은 같은 source-slot의 추가 형식 근거로 다루며 source 수를4로 늘리거나 default8slot CLI 인수로 세지 않는다.

별도 QA가 foundation3파일105PASS와 연결255PASS·C/H/M0으로 승인했다. 합성 계약만 공개 fixture로 만들었고 실제 issuer/장문 원문은 공개하지 않는다. 초기 날짜 overlap과 table cell 연접 문제를 회귀로 고쳤다. foundation `a4b6f5dd`는 parser code 근거로 고정하고, 모든 연결과 함께 전달한 최종head의 CI를 확인한 뒤 비게시 재측정한다. 비용 영향은 기존 무료 OpenDART 진단 최대5calls와 manual Actions job이다. 실제 결과·최종 CI는 후속 기록으로 추가한다.

## 현재 수용 범위

local3/8·runtime0·activationfalse·human0/12·v3예약0과 상위 유닛 미완료를 유지한다. 운영/preview/AI report 핀은 보존하며, 검수된 새 code만 별도 DART preparation pin으로 전달할 예정이다. 실제 positive source/native를 독립 검수하기 전에는 runtime 성공으로 세지 않는다.
