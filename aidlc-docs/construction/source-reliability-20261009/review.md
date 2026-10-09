# 시황 부분 실패와 데이터 소스 점검 — 2026-10-09

부분 게시 실패를 줄이려면 **숫자 강조 표시 복구와 가격 수집 시간 기준 수정부터** 진행한다. 장애가 반복되는 보조 소스는 명시적으로 중지하고, 실패를 0건으로 숨기는 어댑터를 수정한다. 소스 개수 증가나 검증 조건 완화만으로는 해결되지 않는다.

## 점검 범위와 근거

- 코드 기준: 원격 `main` `269a15dc6753d48ba6f58f0834401400379244a5`. 로컬 원래 `main`은 128커밋 뒤에 있어 별도 worktree에서 검토했다.
- 로그 점검 당시 운영: 비공개 `murphyGo/investo-runtime`의 **Codex daily briefing**, `CODEX_PRODUCTION_ENABLED=1`; 실행 코드 pin은 `056dd8a1b4a8e599f44519e54b5bf4f486275dbd`. workflow 저장소의 `head_sha`와 실행 코드 SHA를 혼동하지 않는다. 이 pin과 점검 main의 관련 소스/숫자 복구 코드는 동일하다.
- 완료 전 재확인(09:54 UTC): 별도 작업으로 저장소가 `murphyGo/automation-runtime`으로 변경되고 enable=0, pin=`ca0ef610cdaafea7de188551f06d2107247e8472`인 전환 상태였다. 관련 sources/segments/surface_quality는 원래 점검 코드와 diff가 없음을 GitHub compare로 확인했다. 작업 공간도 새 main `9ff1bcbc`까지 fast-forward했다. 이 작업이 전환 상태를 변경하지 않으며 운영 closeout에서는 실제 owner/enable/pin을 다시 확인해야 한다.
- 이전 공개 daily workflow 최근 20회 중 실제 파이프라인 실행은 19회. `37136372915`는 파이프라인 로그가 없어 생성 성공률 분모에서 제외했다.
- 현재 비공개 운영은 10/4 전환 수동 실행 1회와 10/5–10/9 예약 실행 5회를 조사했다. preview/AI trend/preflight는 시황 생성 통계에 포함하지 않았다.
- 총 **25회, 등록 소스 44개**, 실제 로그의 `source returned`/`source failed`, 생성/최종화/게시 push/알림을 집계했다. 재실행으로 동일 target date가 중복되므로 이는 일별 실패율이 아니라 **실행별** 집계다.
- 원문 로그·외부 응답 본문·키는 Git에 저장하지 않는다. [정규화된 실행/소스 집계](evidence/run-summary.json)에는 ID, 상태, 건수, 소요시간, 제한된 오류 분류만 있다. 로컬 단발 HTTP 점검은 GitHub Actions 복구 증명이 아니다.

## 부분 게시 실패의 직접 원인

| 구분 | 파이프라인 실행 | 부분 게시 | 직접 차단 원인 |
| --- | ---: | ---: | --- |
| 이전 공개 운영 | 19 | 3 | 미국 시황 `markdown.broken_numeric_bold` |
| 비공개 Codex 운영 | 6 | 1 | 코인 시황 `markdown.broken_numeric_bold` |
| 합계 | 25 | 4 (16%) | 모두 숫자 강조 표시 오류 |

4회 모두 생성은 `ok=3 failed=0`였다. 최종 검증에서 한 시장이 `trust_blocked`가 되었으며 정상 시장은 게시 push와 Telegram 알림까지 진행했다. 수집 장애가 함께 있었지만 **게시 차단의 로그상 직접 원인은 포맷 오류**다. 인과관계를 데이터 장애로 단정하지 않는다.

실패 실행: [9/15 미국](https://github.com/murphyGo/investo/actions/runs/34913048177), [9/29 미국](https://github.com/murphyGo/investo/actions/runs/36508936990), [9/30 미국](https://github.com/murphyGo/investo/actions/runs/36653801286), [10/9 코인](https://github.com/murphyGo/investo-runtime/actions/runs/37872017717). 마지막 실행의 target date는 `2026-10-08`이다. 공개 `archive/_meta/quality_history.jsonl`에도 그 날짜 `published_segments=2`, `total_failed_sources=4`가 남아 있다.

현재 `_BROKEN_NUMERIC_BOLD_RE`는 `**+**2.3%`, `**-**$100`을 차단하지만 `_repair_broken_numeric_bold`는 이 두 형태를 복구하지 못한다. 실제 함수로 합성 반례를 재현했다. 거부된 원본 시황 본문은 로그에 없어 **이 합성 반례를 실제 실패 문장으로 주장하지 않는다**. 숫자·부호·단위를 보존하는 복구와 최종 문서 재검증을 u163으로 분리한다.

## 소스별 결정

`ok`는 1건 이상, `zero`는 어댑터가 반환한 0건, `failed`는 aggregator에 전달된 실패다. `zero`에는 정상 무발표일과 숨겨진 장애가 섞여 있다.

| 소스 | 전체 25회: ok / zero / failed | 현재 운영 6회 | 결정과 이유 |
| --- | --- | --- | --- |
| `binance-crypto-market` | 0 / 0 / 25 | 6회 모두 HTTP451 | 기존 host는 상시 호출에서 제외하는 계획. 공식 market-data-only host는 별도 자격검증 후 같은 provider 복구 후보로 사용한다. 지역 제한 우회·proxy·브라우저 위장은 사용하지 않는다. |
| `cnbc-top-news` | 0 / 0 / 25 | 6회 모두 HTTP403 | 기본 수집 중지 계획. 기존 Nasdaq 뉴스/Fed/SEC/CFTC로 남는 coverage를 먼저 검증한다. 동일 source 이름에 다른 언론을 넣지 않는다. |
| `korea-policy-rss` | 0 / 0 / 25 | 6회 모두 HTTP503 | u161의 HTTPS/`dc:date` 수리는 이미 pin에 있다. 현재 문제는 upstream503이다. 복구 때까지 중지/낮은 빈도의 명시적 probe; 한국은행 RSS는 다른 정책 범위의 독립 후보다. |
| `coingecko-price` | 1 / 23 / 1 | 6회 모두 zero | `/coins/markets` 현재 timestamp를 전일 UTC창에 넣어 버리는 계약 오류. u164에서 현재 조회 가격과 과거 날짜 가격을 구분한다. 단순 timestamp 재작성은 금지한다. |
| `fsc-krx-index-price` | 0 / 23 / 2 | 6회 모두 zero | HTTP200을 반복해도 항목이 없다. 응답 totalCount/받은 행/이름 일치/유효 행/제공일을 분리해 확인해야 한다. 공개 이용권 제한 때문에 무조건 복구·승격하지 않는다. |
| `krx-foreign-flows` | 4 / 21 / 0 | 6회 모두 zero | 실제 두 시장 요청 HTTP410이 21회에서 내부적으로 삼켜졌다. 전부 실패하면 `SourceFetchError`; 한 시장 성공은 보존한다. 재배포 가능한 무료 구조화 대체 소스는 아직 확정하지 않았다. 수급값은 누락으로 남긴다. |
| `yahoo-finance-news` | 5 / 17 / 3 | 최근 3회 HTTP404 | 뉴스 `rssindex` endpoint 수명 종료 의심. 기본 수집 중지 계획. 25회 모두 정상인 `yfinance-price` query2는 유지한다. 뉴스 장애를 가격 장애로 확대하지 않는다. |
| `bea-macro-actuals` | 0 / 25 / 0 | 6회 모두 zero | `_fetch_one`의 실패가 무조건 삼켜진다. 10/6 실행 180.069초/0건. HTTP/API 오류, 데이터 없는 기간, 스키마/line mismatch를 분리하고 전체 어댑터 예산을 고정한다. 원 API 응답을 확보하지 않아 zero의 실제 이유는 미확정이다. |
| `congress-gov-bill-actions`, `senate-banking-policy` | 각각 0 / 25 / 0 | 모두 zero | zero만으로 장애 판정 금지. 발표/상태변경 빈도와 기간 필터를 확인한다. core price와 달리 발표 없는 날이 가능하다. 키 누락 증거는 없다. |
| `fomc-rss` | 13 / 10 / 2 | 3회 ok / 3회 zero | 유지. 현재 공식 press와 monetary feed 모두 HTTP200/유효 RSS. 일시404 재발을 관찰하고 공식 동일-provider 대체 feed만 검토한다. |
| Yahoo 가격, FRED 환율/거시, Treasury, BLS, NYFed, SEC company facts, OKX/Bybit, DefiLlama, The Block, Yonhap 뉴스 등 | 집계 JSON 참조 | 계속 usable | 정상 소스 유지. 기존 수집·시장 routing·출처·비용 계약을 보존한다. |

코인 `data_limited=True`는 25회 중 **24회**(현재 운영 6/6)였다. 이는 게시 자체의 partial과 다른 지표다. 국내 `fsc-krx-index-price`도 25회 모두 usable 값을 주지 않았고, 국내 일부 게시에서는 `numeric.anchor_assertion`을 containment해 `finalized_degraded`로 게시했다. 이를 정상 수치 복구로 기록하지 않는다.

## 현재 endpoint와 대체 후보

로컬 curl은 중립적인 Investo UA, 5초 connect/15초 total timeout, 1MiB cap, 인증 없는 GET, 자동 redirect 없음으로 실행했다. 응답 본문은 로컬 임시 디렉터리에만 보관했다. 아래 기술적 성공과 공개 게시 자격을 구분한다.

| 후보/기존 endpoint | 실제 점검 | 자격 및 disposition |
| --- | --- | --- |
| CoinGecko `/coins/markets` | HTTP200, BTC/ETH/SOL 3건 정상 정규화. `last_updated=2026-10-09T09:34:58Z`; `2026-10-08T00:00Z ≤ t < 2026-10-09T00:00Z`에 3건 모두 불포함 | **ship-now: 기존 어댑터 시간 계약 수리의 개발 계획**. 기존 provider·키 없는 운영 요청은 현재 성공하지만 [Demo 문서](https://docs.coingecko.com/demo/reference/coins-markets)는 demo-key header를 안내한다. 무료 key 필요 여부·attribution을 운영에서 재검증하고 paid 자동 승격은 금지한다. |
| CoinGecko `/coins/bitcoin/history?date=08-10-2026&localization=false` | 인증 없이 HTTP200, JSON market_data 있음 | **defer: 역사 가격 보완**. [공식 history 문서](https://docs.coingecko.com/demo/reference/coins-id-history)는 선택 날짜00:00UTC snapshot,00:35UTC 제공, Demo365일/키필수를 명시한다. 기본 코인/GHA/attribution/무료 key 조건 확인이 필요하다. `history` 값을 종가/OHLC/24h 변화라고 임의 해석하지 않는다. |
| Binance `data-api.binance.vision/api/v3/ticker/24hr` 및 `/klines` | 각각 HTTP200. 10/8 UTC 일봉 1행 확인 | **defer: 동일 provider 복구 후보**. [공식 문서](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only)에 무인증 market-data-only host가 명시된다. USD와 USDT를 구분하고 GHA/지역 허용과 public derived-display 권한을 확인한 후 활성화한다. 기존451 host를 무작위 mirror로 재시도하지 않는다. |
| Coinbase Exchange `/products/BTC-USD/candles` | HTTP200. 응답에 10/8와 10/9 버킷이 함께 있어 날짜 경계 필터가 필수 | **defer: 독립 provider 예비 후보**. [공식 candle 문서](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)는 최대300개, 무거래 구간 누락, request start 밖 행 가능성을 명시한다. [public rate](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits)는 10req/s, burst15. 모든 코인·GHA·public display terms 확인 후 별도 source_name으로 추가한다. 전체시장 거래량/market cap을 이 거래소 값으로 채우지 않는다. |
| 한국은행 통화정책 RSS `https://www.bok.or.kr/portal/bbs/P0000559/news.rss` | HTTP200, application/xml, RSS 100개 항목 | **defer: 국내 정책 범위 보완 후보**. [공식 RSS 안내](https://www.bok.or.kr/static/guide/portal/popup/rss_popup.html)에서 발견. 무인증 RSS, 발표 시 갱신; rate 공개 수치 미확정, 일1회 요청 계획. 저작물별 공개 이용 조건/날짜 스키마/GHA 확인 후 별도 `bok-policy-rss`를 등록한다. FSC 정책의 동등한 대체라고 주장하지 않는다. |
| FSC 정책 RSS | HTTP503, text/plain, XML 불가 | 기존 u161의 transport/date repair 중복 구현 금지. upstream 회복 전 복구 완료 표시 금지. |
| Fed `press_all.xml`, `press_monetary.xml` | HTTP200, RSS 각20/15항목 | **유지**. [공식 RSS 안내](https://www.federalreserve.gov/feeds/feeds.htm). 기존 FOMC와 범위가 겹치므로 신규 어댑터 추가 대신 필요 시 동일 provider endpoint fallback을 사용한다. |
| Yahoo 뉴스 `rssindex` / Naver 수급 page | HTTP404 / HTTP410 | 현재 endpoint는 **reject: 기본 상시 수집**. 출처를 가장한 타 provider substitution 금지. |
| FSC 지수 API | 공식 설명: 다음 영업일 13시 이후 갱신. 이용범위에 공공누리4유형·제3자 무단 제공/재배포 금지 명시 | **reject: 권한 근거 없는 공개 가격 fallback**. [현재 공식 데이터 설명](https://www.data.go.kr/data/15094807/openapi.do). 무료 API 접속과 공개/가공 재배포 권한은 다르다. 현재 zero 원인은 별도 payload 진단이 필요하며 갱신 지연만으로 전부 설명되지 않는다. |
| KRX Open API | 공식 서비스/키 신청 경로와 약관 검토, live authenticated probe 없음 | **defer**. [서비스 이용방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp), [약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp). 별도 키·공개 표시 범위·데이터 지연·수급 fields가 미확정이어서 즉시 대체로 등록하지 않는다. |
| 정책브리핑 korea.kr RSS | 현재 [공식 뉴스 페이지](https://www.korea.kr/news/ministryNewsHome.do)에 RSS 서비스 제공 중단 안내 | **reject: RSS 대체 추천**. 오래된 RSS 주소를 새 안정 소스로 추천하지 않는다. |

## 실행 순서와 등록 유닛

| 우선순위 | 유닛 | 결과 | 의존성 |
| --- | --- | --- | --- |
| P0-1 | [u163 terminal-numeric-emphasis-containment](../plans/u163-terminal-numeric-emphasis-containment-code-generation-plan.md) | 숫자 표시 오류 때문에 시장 전체가 빠지는 문제를 복구 | 기존 u112/u144/u150 확장. 신규 source 없음 |
| P0-2 | [u164 crypto-price-time-basis-repair](../plans/u164-crypto-price-time-basis-repair-code-generation-plan.md) | 현재 snapshot과 target date의 시간 기준을 분리; 역사 fallback은 qualification 후 | 기존 CoinGecko core, 새로운 provider 활성화와 독립 |
| P1-1 | [u165 source-lifecycle-and-failure-truth](../plans/u165-source-lifecycle-and-failure-truth-code-generation-plan.md) | 상시 장애 소스 중지, skipped/zero/failed 구분, BEA/수급 hidden error 복구 | u1/u22/u31/u54/u161 확장; 신규 registry를 만들지 않음 |
| P1-2 | [u166 domestic-price-source-qualification](../plans/u166-domestic-price-source-qualification-code-generation-plan.md) | 국내지수 zero의 단계별 진단과 사용권/제공일에 맞는 소스 선택 | DEBT-068과 연결; 무료 공개 가능 source가 확인될 때만 추가 |

4개 유닛은 **새 계획/설계 초안이며 승인·구현·운영 복구 완료가 아니다**. u161 완료를 되돌리지 않고 upstream503 운영 후속만 연결한다. u138 가격 endpoint 수리는 다시 만들지 않는다. u154 layout, u157–u162 event/news 활성화, sector dashboard는 이 작업 범위에 포함하지 않는다.

u163/u164를 먼저 개발 검증한다. u165의 skipped 도입은 상태 모델/coverage/history 호환을 함께 수정한 뒤 적용한다. 복구 후보를 활성화하기 전에 기준값/출처/날짜/사용권과 기존 뉴스 coverage를 확인한다. 그 후 검증한 **새 실행 코드 SHA**를 private `REVIEWED_CODE_SHA`에 반영한다. 공개 main push만으로 private pin의 실행 코드가 바뀌지 않는다. 이 점검에서는 pin/변수/워크플로를 변경하거나 재게시하지 않았다.

## 수용 기준과 효과 측정

1. u163: 합성 반례·원본 확보 시 private replay·실제 finalizer full/partial 번들에서 숫자/부호/단위 보존, 복구 후 표시 오류0, 반복 처리 동일 결과. 미해결 내용 오류는 계속 차단한다.
2. u164: 예약 실행의 BTC/ETH/SOL 가격은 실제 as-of와 동일하며 현재 조회 가격을 전일 종가로 표시하지 않는다. 과거 replay에는 미래 현재가가 들어가지 않는다. 결측 변동률/OHLC/market cap은0으로 만들지 않는다.
3. u165: 전체 하위 요청 실패는 failed, 정상 무발표/유효0건은 zero, 운영 중지는 skipped. skip을 수집 성공으로 계수하지 않으며 history와 운영 알림에 중지 이유가 남는다. BEA 전체 예산60초, 하위 성공 보존, 예외 전부 삼키기0.
4. u166: 한국 휴장일/제공 지연/totalCount0/이름 mismatch/schema drop을 구분한다. public qualification 없는 fallback 추가0, stale 값의 정상 승격0.
5. 운영 closeout은 현재 owner/pin에서 **서로 다른 정상 예약 실행 10회**를 관찰한다. 취소/skip/manual replay는 분모에서 제외한다. 각 실행은 생성3시장, finalized 상태, source별 usable 값/가짜0/실패, 게시 commit/push, Telegram 결과, 실제 publication SHA의 Pages를 별도로 확인한다.
6. 목표: numeric-emphasis 차단0/10, 코인 가격 usable9/10 이상, 승인된 상시 source의 영구403/404/410/451 반복0. 후보 미승인으로 일부 목표가 미달이면 사유를 기록하고 운영 복구 완료로 닫지 않는다. 전체 부분 게시율과 source failure율을 따로 비교하며 이 표본만으로 향후 감소율을 보장하지 않는다.

## 완료한 작업

현 운영/원격 코드/25회 로그/44개 소스/공개 품질 기록을 점검했고, endpoint probe와 두 코드 반례를 재현했다. 계획과 등록만 작성했다. 운영 코드 수정, commit/push, 배포, live LLM 실행, Telegram 발송, runtime pin 변경은 수행하지 않았다. 원래 dirty 작업은 보존했다.

문서 검증: 변경13파일의 내부 상대 링크·placeholder·공백 검사와 u163–u166의 세 등록 표면 중복 검사를 통과했다. JSON25실행/44소스별 상태 합계,4partial/24crypto limited/25generation success,21회 숨겨진 수급410과 게시/알림 기록도 재계산해 일치했다. `git diff --check` 통과. `site_docs`/MkDocs 입력은 바뀌지 않아 사이트 빌드나 운영 코드 테스트를 이번 문서 작업의 검증으로 주장하지 않는다.
