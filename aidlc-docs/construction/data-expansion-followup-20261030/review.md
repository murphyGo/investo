# 추가 데이터 후보 재검토 — 3순위 이후

2026-10-30 KST. 사용자 요청: “검토하고 괜찮을지 분석해줘”. 기존 연구의 Deribit 만기, Ethereum Foundation(EF) 공지, Bybit 청산과 추가 후보인 Coin Metrics 활동 지표·KRX 위클리를 검토했다. 분석 문서이며 신규 유닛 등록·구현·운영 활성화 지시로 해석하지 않는다.

## 판단

**기존 3→4→5 순서를 그대로 실행하는 것은 권하지 않는다.** Deribit은 무료 조회와 공개 사용의 조건이 다르고, 청산은 일일 수집 구조에 맞지 않는다. 가까운 후속 구현은 **Coin Metrics 활동 지표**, 공식 뉴스 근거 보강은 **EF 공지의 제한된 도입**이 적합하다. KRX 위클리는 연간 달력 유지와 표시 범위를 정한 뒤 진행한다.

`ship-now`는 범위를 고정해 설계·구현에 착수할 수 있다는 후보 판정이다. 코드·테스트·공개 자격·운영 환경 검증을 생략한 배포 승인을 뜻하지 않는다. 비용·효용·난이도 평가는 아래 공식 근거와 현재 코드 구조에 대한 판단이다.

| 후보 | 판정 | 독자 가치 | 추가 부담 | 제안 |
| --- | --- | --- | --- | --- |
| Coin Metrics 활동 지표 | **ship-now / 좁은 범위 구현 추천** | 가격·순유입과 다른 온체인 활동 축 추가 | 낮음~중간 | BTC·ETH 활성 주소·거래 건수부터. 수수료는 후속 |
| EF 공식 공지 | **defer / 조건부 추천** | 프로토콜 변경의 1차 근거 확보 | 중간 | 먼저 뉴스 근거로 제한. 사용 범위·기존 evidence 경로 합의 후 도입 |
| KRX 위클리 만기 | **defer / 후순위 조건부 추천** | 국내 단기 일정 보완 | 중간 | 2027 달력 유지 계획, 조정·중복·표시 상한 확정 |
| Deribit 옵션 만기 | **reject / 현재 무승인 공개 도입안** | 크립토 파생 만기 공백 보완 | 기술은 낮음~중간, 사용 허가 미확보 | 사전 서면 허가 확보 시 재평가 |
| Bybit 청산 스트림 | **defer / 현재 구조에서는 비추천** | 거래소 내 레버리지 스트레스 관측 | 높음 | 상시 수집·영속 저장·누락 처리와 공개 권한을 별도 검토 |

## 1. Deribit — 앞선 우선순위를 낮춰야 한다

[공식 회원 약관](https://support.deribit.com/hc/en-us/articles/25944532191645-Deribit-Exchange-Membership-Terms-Deribit-FZE)은 2026-08-13 버전이며, **2.10조가 시장 데이터와 파생 데이터의 개인 사용 외 집계·공개·전달 등에 사전 서면 승인을 요구**한다. 비상업 공개 사이트라고 자동 허용되는 조건은 아니다. 만기 reference 필드의 별도 예외는 이번 검토에서 확인하지 못했다. API 정책에 데이터 표시권이 없다는 종전의 불확실성보다 강한 보류 근거다.

[get_instruments](https://docs.deribit.com/api-reference/market-data/public-get_instruments)는 약 1분 cache와 1초당 1회 제한을 문서화한다. 기술적으로는 일일 조회에 맞지만, settlement 통화 기준 필터·비활성 상태·동일 만기의 여러 행을 구분해야 한다. 새로 확인한 [get_expirations](https://docs.deribit.com/api-reference/market-data/public-get_expirations)도 향후 허가 후 검토할 수 있으나 이번에는 실제 응답을 검증하지 않았다.

공개 도입을 보류하는 이유는 비용이나 파서 난이도가 아니라 사용 범위다. 재개 조건은 사이트 표시·Telegram 연결·Git 보존·계산한 일정의 범위를 포함하는 서면 허가다. 이번에 제공자에게 연락하거나 권한을 요청하지 않았다. 예전 로컬 HTTP 200을 현재의 재배포 자격이나 GHA 안정성으로 사용하지 않는다.

## 2. EF 공지 — 뉴스 근거로는 가치가 있고, 자동 달력은 별도 문제다

[공식 RSS](https://blog.ethereum.org/en/feed.xml)를 다시 조회한 결과 HTTP 200, 531,824 bytes, 안전 XML 파싱 644항목이다. 조회 시점 최근 30일은 4건(프로토콜 2건·연구 2건), 최근 24시간은 0건이었다. 이 표본은 장기 발행 빈도를 보장하지 않지만, 매일 부족한 뉴스 수를 채우는 소스로 기대하기는 어렵다. 공식 변경 공지가 발생했을 때 신뢰도를 높이는 보조 소스로 적합하다.

실제 [Hoodi 연기 공지](https://blog.ethereum.org/2026/10/22/glamsterdam-hoodi-delay)는 이전 일정을 철회하고 대체 일정을 정하지 않았으며, 메인넷 일정을 발표한 것도 아니다. 따라서 `pubDate`를 시행일로 바꾸거나 최신 정정을 놓친 과거 일정을 유지하면 잘못된 일정이 된다.

- 첫 범위: `ethereum-foundation-news`, crypto 전용 공식 뉴스. 제목·원문 URL·발행일·네트워크·확인된 변경 사실을 제한적으로 사용한다. 본문 전체·이미지의 공개 복제는 포함하지 않는다.
- 권리: RSS에는 `All rights reserved 2026`이 있고 명시적 공개 라이선스 링크는 발견하지 못했다. 다른 ethereum 사이트나 코드의 라이선스를 블로그에 전용하지 않는다. 짧은 사실 요약·제목·링크와 내부 근거 보존의 허용 범위를 정리하기 전 공개 자격을 승인하지 않는다.
- 시간: 발행일·수정 확인 시각·실제 시행일을 분리한다. 일정 승격은 network/upgrade/status/activation과 후속 정정 연결을 별도 검증한 경우로 제한한다. 날짜가 철회되면 `unknown/postponed`로 두고 추정하지 않는다.
- 운영: 최근 항목 수·응답 크기·본문 근거량을 제한하고, 공지 없는 정상 기간을 수집 장애와 구분한다. 조회된 RSS 크기가 500KiB보다 크므로 다른 body 경로의 500KiB 제한을 그대로 복사하면 안 된다.
- 중복: `sources/__init__.py`에는 EF adapter가 없다. 다만 u173/u184의 공식 evidence·권리·보존 계약과 같은 영역이므로 해당 경로를 재사용하고 독립적인 body bypass를 만들지 않는다. 일반 뉴스가 같은 사건을 보도하면 두 사건으로 세지 않는다.

## 3. Bybit 청산 — API 추가가 아니라 운영 체계 추가다

[공식 allLiquidation 문서](https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation)는 종목별 500ms 스트림이며, `Buy`는 long 청산이고 `p`는 bankruptcy price라고 정의한다. [연결 문서](https://bybit-exchange.github.io/docs/v5/ws/connect)는 public 인증 불필요, heartbeat와 재연결을 설명한다. 시장 전체 합계가 아니라 Bybit의 구독한 상품 범위다.

현재 `bybit_derivatives.py`의 funding/OI는 HTTP snapshot이다. 여기에 몇 초간 WebSocket을 구독하는 방식으로 지난 24시간 총액을 얻을 수 없다. 일일 cron은 과거 스트림을 소급 복원하지 못한다.

필요한 것은 상시 프로세스, 영속 저장, 재시작·재연결, 중복과 누락 판정, 관측구간의 완전성 표시다. 끊긴 시간을 0으로 채우면 안 되며, 고유 event ID 없이 동일 필드만으로 중복을 제거할 때 실제 서로 다른 사건을 지우지 않는지도 검증해야 한다. 수량×bankruptcy price를 실제 체결액·실현 손실·USD 총액으로 부르지 않는다.

기존 u183 qualification도 Bybit 데이터의 별도 public current/history 재배포를 차단한다. [API 약관 안내](https://www.bybit.com/en/help-center/article/API-Terms)는 새 법률 페이지로 연결되지만, 이번 브라우저 조회에서는 본문 조건을 확보하지 못했다. 따라서 공개 사용 허가가 확인됐다고 판단하지 않는다. WebSocket 연결·24시간 수집·복구 실측도 이번에 수행하지 않았다.

## 4. Coin Metrics 활동 지표 — 가장 현실적인 다음 확장

[Community 카탈로그](https://community-api.coinmetrics.io/v4/catalog/asset-metrics)에서 `AdrActCnt`, `TxCnt`, `FeeTotNtv`의 BTC·ETH 일별 지원과 단위를 확인했다. 2026-10-21~28 batch 요청은 HTTP 200, 두 자산×8일=16행, 세 필드 모두 유한한 비음수였으며 count 필드는 정수였다. 페이지 추가 없음. 값 원문은 보고서나 공개 fixture에 넣지 않았다.

순유입은 거래소 방향의 흐름이고, 이 후보는 네트워크 활동이다. 기존 F&G·funding·OI·TVL·순유입을 단순 복제하지 않는다. [기존 Community 데이터 라이선스](https://github.com/coinmetrics/data)는 CC BY-NC 4.0이며, 이미 정한 Investo 비상업·출처·변경 표시 조건을 재사용할 수 있다.

권장 첫 범위는 BTC·ETH의 **활성 주소 수와 거래 건수**, 비교는 충분한 일별 표본이 있을 때 직전 7일 평균 정도다. 일별 주소 수를 더해 주간 고유 사용자 수로 표시하지 않는다. [공식 active addresses 설명](https://docs.coinmetrics.io/network-data/network-data-overview/addresses/active-addresses)은 체인 구조에 따라 지표 의미가 달라지고 주소 활동이 실제 사용자 수와 같지 않음을 보여 준다. ETH L1 지표를 전체 L2 생태계 활동으로 확대하거나 증가를 자동 상승 신호로 해석하지 않는다.

`FeeTotNtv`는 native 단위 총수수료다. 최초 버전에서는 뒤로 미루어 표시 부담을 줄일 수 있다. 추가할 때 BTC·ETH 단위의 합산과 총수수료의 가격 또는 검증자 수익 오인을 방지한다.

**재사용 한계:** 이번 활동 응답에는 `*-status`/`*-status-time`이 없다. 기존 순유입의 필수 `flash/reviewed/revised` 모델에 끼워 넣거나 상태를 만들어서는 안 된다. 별도 typed activity 모델과 optional revision/provenance 계약이 필요하다. 같은 공급자라도 활동 필드 오류가 이미 운영 중인 순유입을 없애지 않도록 분리한다.

제안 범위는 `sources/coinmetrics_network_activity.py`, source name `coinmetrics-network-activity`, crypto/macro/tier B다. native/legacy 표시와 numeric validation, 관측 UTC 일자·수집 시각·cutoff, 부분 결측·완료되지 않은 일자·정수/Decimal·429·응답 상한을 함께 검증한다. u183 dashboard current/history는 기존 권한과 typed projection을 추가 검토할 별도 범위다.

## 5. KRX 위클리 — 규칙은 확인됐지만 월물 모델에 날짜만 추가하면 안 된다

[KRX 현행 상품 명세](https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp)는 월요일 위클리의 휴장 시 뒤로 조정, 목요일 위클리의 앞으로 조정, 둘째 목요일 월물과 겹치는 위클리 제외를 명시한다. 기존 월물 구현의 직전 거래일 이동을 두 유형에 공통 적용할 수 없다.

기존 `krx-option-expiry`를 확장하되 월물·월요일 위클리·목요일 위클리를 typed kind로 나누는 설계가 적절하다. 조정된 날짜가 같은 경우에도 원래 계약 유형의 구별을 보존한다. native 패널은 현재 최대 2개 날짜와 월물 고정 문구라서 수집기만 확장하면 표시 누락이나 오표시가 생긴다.

독자에게 매주 여러 행을 반복하는 효과를 고려해 기본 표시는 가까운 일정 1~2개, 월물 우선, 상세 일정은 별도 범위로 제한하는 편이 낫다. 일정의 존재만으로 가격 변동이 커질 것이라고 단정하지 않는다. 현재 달력은 2026년만 검증되어 있으므로 위클리 수를 늘리는 것보다 2027 연간 달력 갱신을 먼저 확보하는 운영 가치도 크다.

## 권장 진행 순서와 수용 기준

1. **Coin Metrics 활동 지표의 좁은 구현**: 두 자산·두 지표부터, 완료 UTC 일자와 부족한 표본 처리, 출처·라이선스 표시, 기존 순유입 회귀를 확인한다.
2. **EF 공지의 사용 범위·evidence 연결 검증**: 공지 없는 날, 동일 사건 중복, 테스트넷/메인넷 구분, 수정·연기·취소 사례를 통과한 뉴스 근거부터 도입한다. 자동 예정 달력은 분리한다.
3. **KRX 연도 갱신 후 위클리**: 월/목 조정 방향, 월물 제외, 연속 휴장·연말·미지원 연도, 표시 상한을 검증한다.
4. Deribit은 사용 허가 확보 전 공개 구현 우선순위에서 제외하고, Bybit 청산은 상시 수집을 별도 제품 범위로 받아들일 때 재검토한다.

신규 adapter의 공통 변경 지점은 `sources/__init__.py`, `_internal/source_specs.py`의 tier/window/item/outcome routing, registry/plugin/source-spec 테스트, `sources/aggregator.py`의 실패 진단이다. 미래 일정은 `briefing/segments.py::LOOKAHEAD_AWARE_SOURCES`와 빈 일정 진단까지 필요하다. `scripts/check_no_paid_apis.py` 통과는 무료 사용·표시권을 모두 증명하지 않으므로 공식 조건 확인을 별도로 유지한다.

## 이번 검토의 증거와 변경 범위

- 핵심 직접 응답 세 건의 시각·해시·필드 검증은 [probe-summary.json](probe-summary.json)에 기록했다. EF RSS와 Coin Metrics activity/catalog는 로컬 read-only 조회다. 공식 문서 웹 조회는 별도다.
- 운영 GHA/IP, 제공자 사용 허가, 24시간 청산 완전성, 미래 예약 실행은 새로 검증하지 않았다. HTTP 200을 운영 인수 완료로 간주하지 않는다.
- `src/`, `tests/`, workflow, 운영 변수, 공유 state/debt/다른 세션 문서는 변경하지 않았다. 신규 유닛·코드 생성 계획도 등록하지 않았다.
- 보고서·검증 metadata만 저장했다. Markdown 공백·JSON·로컬 링크·placeholder를 점검하며, site에 포함되지 않는 연구 문서이므로 전체 pytest/MkDocs는 실행하지 않는다.
