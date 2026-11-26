# DART 지원 양식 discovery 개선

사용자 “진행시켜”에 따라 u173 Step4/u184 Step5의 일반 목록 제한에 따른 누락을 수정했다. 코드는 공유 dirty root와 분리한 `codex/dart-discovery-20261126`에 저장했다. 최종 application SHA는 `39f757297c320e804277ac3b51657581f9a175c9`다. 기존 production/main·등록 adapter·기본 수집은 변경하지 않았다.

## 변경

비공개 article_v2에서 검수된 DART parser profile을 지정하면 B001 주요사항보고서를 조회하고, 해당 parser의 입력 신원 계약을 통과한 공시를 30건 제한 전에 고른다. 최대3 GET/20초/요청8초/응답500KiB이며, 기존 준비6 GET/20초와 구분된다. 반환된 source outcome과 조회 범위를 캡처한다. `full`은 해당 B001 조회의 완료만 의미한다.

첫 실제 응답에서 전일 접수번호와 당일 접수일을 가진 비지원 공시1건이 전체48행을 실패시키는 새 가정 오류를 발견했다. 그 전역 조건1줄만 제거하고 기존 선택항목의 `dart_identity`·최신Y목록·XML 검증은 유지했다. 실제 응답 재생과 회귀로 수정 전 실패/수정 후 지원1건을 검증했다.

## 검증

| 검증 | 결과 |
|---|---|
| 최종 exact CI45812557093 | 8361passed/1skipped,809.27초 |
| 정적·정책·브라우저 코드 | Ruff889files/mypy375files,JS39,정책검사,strictdocs9.12초 PASS |
| 독립 코드 검수 | 초기136tests,수정68tests,잔여C/H/M/L0 |
| 운영 helper | outcome/coverage M1·미기록실패원인 L1수정,정상/변조10cases PASS |
| 최초실제45811756622 | HTTP1뒤source failed/unknown,model1/기사0;실패증거보존 |
| 수정실제45814759782 | B00148행→지원1건,discovery1GET+Y/XML2GET,model1/기사0 |

최초 암호문57194bytes와 수정 암호문62816bytes를 즉시 확보했다. 최종6파일의 해시·0700/0600·모델IO·exact checkout·job시각·source입력·context/Stage1/edition 연결·전후전체repo변수와빈환경변수를 독립 대조했다. 캡처 원문은 ignored private 경로만 사용하고 문서에는 원문을 싣지 않는다.

## 실제 성과와 남은 작업

현재 공시 `20261126000356`을 일반 제한 밖에서도 발견해 공통 준비에 전달했다. 최신성은 `as_observed`이고, 원문 조회는 성공했다. 다만 원문의4개날짜가 `YYYY.MM.DD`, 기타주석이328자다. 기존 파서는 한국어 날짜 표기와240자이하 주석만 지원하므로 `parser_unsupported`로 차단했다. 메모리에서 날짜 동등성만 확인한 추가 오프라인 진단도 주석 예산에서 멈췄으며, 전달 코드의 파서·예산은 바꾸지 않았다.

따라서 discovery 양성은1건, 본문 준비·DART native·모델선택·기사양성은0건이다. 모델1회가사건0개를반환했고 `source_limited/content_not_ready` 안내를 봉인했다. 이는 시장에 중요사건이 없다는 판단이나 외부recall 통과가 아니다.

다음 자동화 가능 작업은 이 날짜 표기와328자전체주석의 bounded 근거 지원·별도자격 및 현재 상세기사 검증이다. 주석을 잘라 조건을 잃거나 임의 문장으로 보완하지 않는다. 오늘의 사람 사전 사건/핵심사실 목록은 요청했으며 답변·인수점수는 아직 없다.

private HEAD는 `aef573a71f8f2066562dc64c49e229e384367e99`, 전용 preview pin만39f75729로갱신했다. production378bccee·DART preparation4737ec42·qualification6ac349fe와다른변수/예약/게시/알림/cursor/receipt는보존했다. human0/12·canonical local3/8/runtime0/activationfalse·v3예약수용0·viewport/성능/운영인수는미완료다. 이 하위계획5/5만완료하고상위u173/u184/u172/u171은완료하지않는다.

[계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-discovery-20261126/plan.md), [최종결과](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-discovery-20261126/corrected-result.json), [원문 gap](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-discovery-20261126/parser-gap.json), [인계](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-discovery-20261126/handoff.json).
