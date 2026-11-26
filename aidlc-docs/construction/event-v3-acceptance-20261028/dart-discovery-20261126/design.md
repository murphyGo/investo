# 기능 및 비기능 설계

## 기능과 소유권

비공개 article_v2에서 기존의 검수된 명시적 DART parser profile을 선택했을 때만 sources의 비등록 DartDiscoveryAdapter를 해당 수집 호출에 주입한다. 전역 registry 객체와 기본 fetch는 그대로 둔다. adapter는 OpenDART 주요사항보고서 B001을 접수일자 내림차순으로 조회하고 정상화·기존 dart_identity를 통과한 양식만 선택한다. 회사·접수번호 하드코딩, 과거 sample 주입, 첨부추가/정정 양식 자동fallback은 없다. 최대30개 반환 cap은 적합성 검사 뒤에 적용한다.

기존 collect_sources가 skip/zero/failure/outcome 순서를 소유한다. discovery는 news-window/cursor 수집과 동시 사용하지 않는다. SourceWindowCoverage는 이 B001 조회의 pagination 증거이며 전체 DART 또는 전체 시장의 완전성을 뜻하지 않는다. private snapshot과 manifest에 조회범위·parser·coverage를 함께 남긴다. 날짜는 date precision이고 사건 발생시각은 추정하지 않는다.

조회 실패는 첫 페이지 전이면 failed, 앞선 유효 페이지가 있으면 partial이다. pagination/total 변화·중복·비정상 행·범위 밖 날짜·응답 구조 오류는 해당 페이지를 수용하지 않고 partial로 종료한다. 철회/정정 여부와 최신성·문서 identity는 기존 Y목록+XML 공통 준비가 최종 판정한다. 발견된 제목만으로 기사 생성하지 않는다.

## 예산·보안·자격

별도 discovery는 최대3 GET(재시도0), 페이지100, 전체20초/개별8초, 응답500KiB로 제한한다. 기존 일반 목록1GET을 이 조회로 대체한다. 본문 준비는 기존 최대6 GET/20초를 유지하므로 DART 총 상한9 GET/40초이다. 새 provider/키/유료 API는 없다. fixed HTTPS endpoint, redirect 금지, trust_env false, duplicate JSON key/credential echo/비정상 encoding 거절, 정제한 오류코드만 반환한다.

기존 DartCapture를 별도 discovery에 사용하고 본문 캡처와 구분해 저장한다. 각192KiB와 합쳐서 기존256KiB encoded 파일/전체2MiB artifact cap을 유지한다. 초과·unsafe 원문은 진단 전체를 실패시키고 모델 호출 전에 종료한다. source 원문은 private 암호화 캡처만 허용하고 합성 fixture에는 복사하지 않는다. 기존 parser/matrix/본문 예산·fact proof·core-only brief 상한은 유지한다.

## 검증과 실행

비지원100건 뒤 다음 페이지의 지원양식,30cap 전 필터,3page/20초/8초/byte cap, pagination 변화/duplicate/응답·날짜·identity/credential/withdrawn 후속차단, skip/실패/기본경로 불변을 mock으로 검사한다. 독립 검수 후 전체 quality를 exact SHA에서 완료한다. 실제 run은 당일 조회를 사용하고 discovery HTTP와 이후 Y목록/XML 및 모델 입력을 결속한다. 지원공시가 없거나 원문 검사가 실패하면 이를 그대로 기록하며 반복 호출로 양성을 만들지 않는다.

공식 조회 계약(2026-11-26 확인): [OpenDART 공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001). B001, last_reprt_at=N, sort=date, sort_mth=desc, page_count=100. 이는 discovery 필터이며 본문 자격을 부여하지 않는다.
