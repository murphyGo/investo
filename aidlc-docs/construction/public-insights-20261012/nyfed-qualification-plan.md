# u181 Step8 NY Fed 공개 조건 적용

2026-10-25 검토 시작 · 2026-10-26 KST 현재 검증. 사용자 “진행시켜”에 따라 기존 보류 지표 중 같은 원천의 SOFR/EFFR/금리차만 진행한다.
u180–u183 외 신규 unit/source/endpoint/key/scheduler를 추가하지 않는다.

## Stage decision

별도 Functional Design/NFR 단계를 추가하지 않는다. 기존 FR-026/027, u181의 source 권리·시간·파생값·
current/history/attribution 설계와 운영 Step8을 재사용하는 bounded qualification이다.
데이터 정의·계산법·관측 키를 바꾸지 않고 명시된 이용 고지와 파생값 표기를 완성한다.
재배포 조건은 데이터에 계속 적용되며 software MIT가 원천 데이터 이용 조건을 대체하지 않는다.

## 근거와 경계

NY Fed Terms의 Permissible Use는 저장·복제·배포·파생 작성을 허용한다.
Conditions의 출처/동일 조건/변형 명시/비보증, Reference Rates의 두 고지와 원천 라이선스 정보를 함께 적용한다.
공식 근거: https://www.newyorkfed.org/privacy/termsofuse.html . 허용 범위는 이 세 정의뿐이다.

FRED의 현행 API Prohibitions(k/l)는 AI 관련 사용 및 cache/archive·제3자 보관본 제공을 제한한다.
DeFiLlama는 재게시 허가, OKX는 public endpoint의 제3자 표시에도 서면 동의를 요구하고,
CoinGecko의 cache/encryption/deletion 조건도 공개 Git 경로와 맞지 않는다. 이 경로들은 열지 않는다.
Bybit는 최신 약관 링크가 별도 동적 페이지여서 재배포 허가를 확인하지 못했다. key나 외부 허가를 추정하지 않는다.
기존 legacy briefing 입력·사용 방식 변경은 이 qualification에 포함하지 않는다.

## 실행과 수용

1. 기존 collector의 Treasury/BLS/NY Fed 조회로 현재 typed SOFR/EFFR와 같은 유효일의 파생값을 확인한다.
   HTTP/status/hash와 원천 날짜를 남기고 raw body는 공개 fixture로 새로 복사하지 않는다.
2. 3개 정의의 display/public Git/rolling history를 원천 고지·공개 조건과 결속한다.
   NY Fed 외 43개 정의의 기존 권한(허용24개/보류19개)을 유지한다. source routing/HTTP 수는 기존 runtime과 같다.
3. 모든 macro group의 attribution을 값 앞에 표시하고, 금리차에는 Investo 계산값임을 명시한다.
   current/history JSON에도 동일 고지를 보존하고, data notice로 원천 조건과 software MIT를 구분한다.
4. loader/projection/parent rights/retention/render/history/escape/byte budgets와 실제 viewport를 검증한다.
   독립 리뷰와 정확한 application SHA의 전체 CI 후 private pin을 승격한다.
5. 매크로만 기존 receipt/CAS 경로로 현재값을 게시하고 live JSON/HTML/history/notice·Pages를 대조한다.
   calendar/crypto와 다른 event gates는 보존한다.
6. 아직 발생하지 않은 genuine scheduled 관찰은 세 모듈 모두0/5로 유지한다.
   첫 예약 전에 exact implementation SHA와 qualification hash를 관찰 기준에 반영한다.


## 배포 순서와 실제 조회

Stage1은 고지/계산값 표시/데이터 라이선스 안내 코드와924자 고지만 준비하고 기존 세 권한 flag는false로 유지한다. 전체 CI 후 그 application pin을 먼저 승격한다. Stage2에서 검증된 NY Fed 세 정의의 권한을 열고 매크로만 새 현재값으로 게시한다. 기존 package는 current public-data의 qualification을 읽는 계약이며 code pin과 policy hash를 별도로 기록한다.

운영 release는 현재 pin0025497d 위에 이번 macro renderer·고지/notice·동일 회귀만 적용한 bounded branch로 만든다.
최신 main의 다른 이벤트 구현을 이 권한 변경만으로 production에 승격하지 않는다.
공개 main과 bounded runtime release의 정확한 SHA CI를 각각 확인하고, runtime release를 pin한 뒤 policy를 연다.
독립 리뷰의 비교값 표기 지적을 반영해 5원천 영업일 변화도 Investo 계산으로 구별한다. 원천 SOFR/EFFR 관찰 자체는 바꾸지 않는다.

2026-10-26 01:56 KST 개발 조회: 기존Treasury/BLS/NYFed 총14요청 모두200, source outcome1/8/5 items. NY Fed의 typed2개는유효일2026-10-22가같고spread Decimal계산·freshness확인 PASS. Treasury6·NYFed3·BLS3 총12typed card 투영. BLS는월간값의nextrelease미확인으로unknown/limited이며최신확정으로표현하지않는다. 이조회는source/API local qualification일뿐 GHA 운영관찰이아니다.


## 실행 결과

- [x] 공식 원천 조건·기존14HTTP200·12projection 검증.
- [x] 필수 고지/파생값 구분/current·history/NOTICE/software license 분리.
- [x] Stage1 bounded873cea37 전체7347pass/1skip 및 공개e6ede833 전체7454pass/1skip.
- [x] 운영pin873cea37 승격/readback 후 Stage2 권한9flag만 main36bd84bf에 적용.
- [x] 정책7470923e 전체7454pass/1skip, 독립리뷰C/H/M0.
- [x] macro1d0532d9 remote-confirmed, 전체7464pass/1skip·Pages40217744504 SUCCESS.
- [x] 실제HTTPS10files/3snapshot·운영12렌더 및 로컬16렌더 PASS; sibling 자료 보존.
- [ ] 세 모듈 genuine scheduled 각5회(현재0/5). nominal07KST는 아직 관찰이 아니다.

[최종 검증](nyfed-qualification-validation.json), [운영 배포 기록](deployment-closeout.md)을 참고한다.
