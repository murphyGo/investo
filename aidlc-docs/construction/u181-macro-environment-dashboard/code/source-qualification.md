# u181 원천 자격 기록

2026-10-25 · 코드의 qualification matrix는 `ops/insights_source_qualification.json`이다. 아래는 검토 근거와 제한이며 source registry나 운영 성공 기록을 대신하지 않는다.

| 범위 | 권리 평가 | 구현/접근 증거 | 남은 항목 |
| --- | --- | --- | --- |
| Treasury 4만기+2파생 | 미국 정부 기관이 작성·공개하는 숫자 관측으로 평가하여 display/public Git/rolling analytics 허용 | 기존 XML endpoint 실제 HTTP200. 받은 응답을 같은 어댑터에 replay해 2026-10-23의 typed6개 확인 | 홈페이지 원천 링크의 HTTP 접근은 이번 도구에서 404/timeout으로 미확인. 정확한 Pages/source 관찰은 Step8 |
| BLS SA CPI/Core CPI/실업률 | BLS의 공개물 공공영역 안내와 출처 표시에 근거하여 세 축 허용 | 기존 API 구조/series의 합성 및 기존 fixture parity 확인. 개발 CPI endpoint 조회는 HTTP503 | 현재 정상 수집과 실제 field별 runtime qualification은 별도. 다음 일정 없는 월간 값의 freshness는 unknown |
| NY Fed SOFR/EFFR/같은날 spread | 명시된 재배포 notice/disclaimer를 충족한 공개 bundle 검토 전 세 축 false | SOFR HTTPS200. 다른 두 정의/운영 성공으로 확대하지 않음 | 실제 고지와 공개 Git 보관을 포함한 scope 검토 후에만 변경 |
| FRED DEXKOUS/H.10 | source public-domain citation과 FRED 서비스 조건의 적용 범위 확인 전 세 축 false | 기존 optional key/query 경로의 source Date 매핑과 secret-free envelope를 합성 fixture로 확인 | FRED 약관의 software/AI 관련 제한, 표시·공개 Git·보관 조건 검토; 실제 key/runtime 접근 미실행 |

Treasury 평가는 정부가 작성한 숫자 관측이라는 사실과 [17 USC105](https://www.govinfo.gov/content/pkg/USCODE-2024-title17/html/USCODE-2024-title17-chap1-sec105.htm)를 적용한 범위 판단이다. 사이트의 모든 이미지·제3자 자료까지 허용한 것이 아니다. 실제 입력은 기존 [Treasury XML 안내](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed)와 어댑터의 literal XML endpoint에 한정한다.

[BLS 공개물 안내](https://www.bls.gov/opub/copyright-information.htm)는 기관 출처 표시를 요청하며 사진·삽화 예외를 둔다. 이번 범위에는 숫자 series만 포함한다. CPI는 CUSR0000SA0/CUSR0000SA0L1E, 실업률은 LNS14000000을 그대로 사용한다.

[NY Fed reference-rate 이용 조건](https://www.newyorkfed.org/privacy/termsofuse.html)은 발표 데이터와 함께 정해진 고지·면책을 제시할 것을 요구한다. 단순 API 접근 가능성을 재배포/Git 보관 허가로 확장하지 않았다.

[FRED DEXKOUS 설명](https://fred.stlouisfed.org/series/DEXKOUS)은 Board of Governors H.10의 뉴욕 정오 매입률임을 설명한다. [FRED 현재 조건](https://fred.stlouisfed.org/legal/terms/)과 원천 권리를 별도로 평가해야 하므로 자동 allow를 기록하지 않았다. 일반 서비스 copyright 배너와 해당 series의 source/public-domain 정보를 구별한다.

실제 원천 응답은 임시 경로에만 남겼고 NY Fed 데이터나 API key가 포함된 fixture를 공개 저장소에 추가하지 않았다. 합성 테스트의 permission=true는 명확히 synthetic fixture로 표시하며 실제 permission 증거로 사용하지 않는다.

기존 FRED adapter의 7일 age 필터는 이번 작업에서 바꾸지 않았다. H.10 주간 공표 직전 등에는 새 envelope가 없어서 현재 카드가 미확인/확인된 last-good이 될 수 있다. projection의 H.10 주간 freshness와 원 어댑터의 입력 가용성은 별개이며, 이 조건도 FRED 활성화 전 source 수용에서 확인한다.
