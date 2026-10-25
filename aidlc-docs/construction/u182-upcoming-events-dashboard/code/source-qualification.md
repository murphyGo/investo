# u182 일정 원천·공개 범위

2026-10-25 · 기존 네 어댑터의 응답과 legacy filtering/keys/HTTP/segment/registry를 유지한다. 이 기록은 운영 활성화가 아니다.

| 원천 | typed 입력과 precision | 기존 제한 | 공개 조건 | 개발 조회 |
| --- | --- | --- | --- | --- |
| Fed calendar.json | kind별 고정 label, 원 days의 단일일/연속 range; date-only, America/New_York. 원천 time/location/description hash는 occurrence 구별에만 사용 | 기존 유형/기본30일 및 env override. 파싱 불완전 range를 임의 완성하지 않음 | 이사회 공공영역 고지·출처 표기 범위로 9정의 허용 | HTTP200, 실제 응답 offline replay legacy15/typed10 |
| BEA schedule | 명시된 Year와 날짜·유효 ET 시각, 확실한 원문 월/분기만 target_period. 불명확 시각은 date-only | 기존45일/최대12건, 기존 파서는 시각 파싱 불가 행을 방출하지 않음. 새 화면도 누락 행을 추가하지 않음 | BEA 공공영역 안내·출처 표기 범위로4정의 허용 | HTTP200, replay legacy9/typed9 exact |
| Treasury Fiscal Data | CUSIP+auction_date+reopening; CUSIP 없으면 source-local own key. Date-only | 기존500행/선택 국채유형/기본30일/기존 dedupe, 미러 갱신 지연 가능 | 연방정부 업무 산출 일정 필드의 범위로1정의 허용. 제3자 자료까지 허용하는 판정은 아님 | HTTP200, replay legacy4/typed4 |
| FRED release/dates | 고정10 release ID의 날짜, target_period=null. 기존 inferred macro_event_key를 사용하지 않음 | 기존 ID별15개/기본30일 및 env override. 요청별 실패가 source ok와 공존 가능 | 사용 조건 범위 검토 전10정의 display/public Git 차단. 기존 수집 key/default는 그대로 | 키 조회·실제 요청 없음. 기존 recording/synthetic replay만 |

Fed/BEA의 기본 공공영역 안내는 [Federal Reserve disclaimer](https://www.federalreserve.gov/disclaimer.htm), [BEA FAQ147](https://www.bea.gov/help/faq/147)에서 확인했다. 재무부의 자체 일정 필드 판단은 [17 USC105](https://www.govinfo.gov/content/pkg/USCODE-2024-title17/html/USCODE-2024-title17-chap1-sec105.htm)와 기관 원천에 한정한 추론이며 일반 데이터 라이선스 주장으로 확대하지 않는다. FRED는 [약관](https://fred.stlouisfed.org/legal/terms/)의 software/재배포 범위가 해소되기 전 기존 보수적 차단을 유지한다. 로고·사진·연설 본문·제3자 자료는 복제하지 않는다.

Calendar24 정의는14허용/10차단이며 분석 이력 retention은 모두 false다. actual response에서 관측하지 못한 field_scope는 runtime_probe_state=unverified로 남긴다. source 전체 정상·모든 유형 정상으로 확대하지 않는다. 원 응답 body는 임시 개발 파일이며 공개 산출물에 넣지 않는다. [응답 hash/재생 기록](source-probes.json).

BEA release_type의 News/Data만으로 발표 family를 구별할 수 없어, source 안에서 공식 제목의 검토된 GDP/Personal Income and Outlays/International Trade prefix를 매핑한다. 공개 label/guide는 고정 문구이며 원문 제목·description은 복사하지 않는다. 대상 기간은 공식 제목에 명시된 월/분기만 추출하고 없으면 null이다.

같은 family·kind·현지 날짜/range·확인된 period가 모두 일치할 때만 BEA-FRED 참조를 묶는다. null period와 verified period는 서로 다르며 source별 중복/상충은 임의 병합하지 않는다. 정확한 시각은 KST, 날짜만 있는 일정은 원천 현지 날짜의 오늘을 기준으로7/30일을 선택한다.
