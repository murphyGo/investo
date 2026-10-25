# NY Fed 공개 데이터 자격 결정

검토일: 2026-10-26 KST. u181 기존 운영 Step8의 SOFR/EFFR/동일일 금리차 세 정의만 대상으로 한다.
새 원천·인증·유료 계약·메일 문의·scheduler를 추가하지 않는다.

## 세 가지 증거

권리, 실제 응답, 운영 수용은 각각 확인한다. HTTP 200은 재배포 허가가 아니며,
로컬 실측·수동 게시·CI 성공은 genuine scheduled 관찰이 아니다.

| 원천 | 이번 권리 판단 | 적용 |
|---|---|---|
| NY Fed 3정의 | Permissible Use의 저장·복제·배포·파생 허용, Conditions의 출처/변형/동일 조건/비보증 및 Reference Rates의 필수 고지 적용 | 실행 코드·고지 선배포 후 세 권한 활성화 |
| FRED 11정의 | 현행 API Prohibitions(k)의 AI 관련 사용 및 (l)의 cache/archive·저장본 제3자 공급 제한과 공개 Git 경로가 맞지 않음 | 기존 차단 유지 |
| CoinGecko 2정의 | §6의 24시간 내 갱신·암호화·종료 후 영구삭제, §6.2 저장/복제 제한 | 기존 차단 유지 |
| DeFiLlama 2정의 | 적용 범위에 public API 포함, §8의 mirror/재게시·상업적 복제 허가 조건 | 기존 차단 유지 |
| OKX 2정의 | §9.4(a)가 public unauthenticated endpoint 데이터도 사전 서면동의 없이 제3자 표시/재배포 금지 | 기존 차단 유지 |
| Bybit 2정의 | 공식 안내가 연결한 최신 동적 약관에서 공개 Git 재배포 권한을 확인하지 못함 | 기존 차단 유지 |

공식 자료:

- [NY Fed Terms of Use](https://www.newyorkfed.org/privacy/termsofuse.html), 최종 갱신 2023-06-09.
- [FRED Terms](https://fred.stlouisfed.org/legal/terms/). 기존 legacy briefing 경로 변경은 이번 범위 밖이다.
- [CoinGecko API Terms](https://www.coingecko.com/en/api_terms), 최종 갱신 2025-09-05.
- [DeFiLlama Terms](https://enterprise.defillama.com/terms), 2025-06-24, public API 적용 범위 포함.
- [OKX API Agreement](https://www.okx.com/help/okx-api-agreement), 최종 갱신 2026-07-28.
- [Bybit 공식 안내](https://www.bybit.com/en/help-center/article/API-Terms), 2026-10-20;
  [최신 약관 연결](https://www.bybit.com/en/legal/service-specific-terms/API-Terms).

NY Fed의 현재 허용은 해당 원천 조건에 종속된다. 무조건적·철회 불가능한 영구 권리를 주장하지 않는다.
조건 변경이나 권리 철회 시 기존 qualification fail-closed/retention 정리 경로를 적용한다.
다른 43개 정의의 권한은 기존 24허용/19보류에서 바뀌지 않는다. 적용 후 총 27허용/19보류다.

## 고지와 계산값

924자 원문 고지를 세 qualification에 동일하게 넣는다. 저작권, 이용조건, 비보증, 비제휴,
DTCC underlying-data 안내와 Investo 계산 구분을 current/history에 함께 보존한다.
화면은 숫자 앞의 원천별 고지와 [NOTICE](../../../site_docs/insights/_data/NOTICE.txt)를 제공한다.
SOFR/EFFR 원 관찰을 변형하지 않으며 SOFR−EFFR와 5원천 영업일 변화는 Investo 계산으로 표시한다.
software MIT는 원천 데이터에 적용되는 별도 조건을 대체하지 않는다.

## 실제 원천과 화면 검증

기존 collector로 2026-10-26 01:56 KST 실측한 14요청이 모두 HTTP200이다.
NY Fed SOFR/EFFR 두 관찰은 같은 유효일 2026-10-22이며 Decimal 차이를 bp로 투영했다.
Treasury6+NYFed3+BLS3 총12개 값이 검증됐다. BLS 월간 관찰의 다음 공식 발표일을 확정하지 못했으므로
fresh를 추정하지 않고 unknown/limited로 표시한다. FRED는 빠진 값으로 유지한다.
raw body를 신규 공개 fixture로 복제하지 않고 HTTP/status/hash/clock metadata만 보존한다.

실제 Chromium 16조건(390/1440, light/dark, JS on/off, 확대 동등조건1/2)에서
13카드/12관찰·고지 선행·derived 표시·overflow 없음·JS 오류 없음·current 무fetch·선택 history 로드를 확인했다.
대표 모바일 dark/desktop light 화면을 시각 검수했다. 이는 로컬 source qualification 화면이며 예약 수용이 아니다.

## 두 단계 전달

Stage1 공개 main `e6ede833b0b471c0748dac5f69f6278db2039024`는 notice/code를 제공하되 세 권한을 false로 둔다.
운영 release `873cea37c878da3f9363d2457aa2a4c5a01db3fb`는 현재 pin `0025497d` 위에
README/qualification 고지/NOTICE/macro renderer/동일 회귀 다섯 파일만 적용했다.
다른 이벤트 구현을 production에 승격하지 않는다. 두 정확한 SHA의 CI 성공 후 private pin을 먼저 변경한다.

Stage2는 NY Fed 아홉 permission flag만 true로 바꾸고 기본 qualification 회귀를 12허용/FRED차단으로 갱신한다.
실행 코드는 public-data cwd의 qualification을 읽는다. 따라서 실행 SHA와 정책 SHA/바이트 해시는
독립된 검토 증거이며 코드 checkout 정책과 public-data 정책이 같다고 가정하지 않는다.
검증된 capture를 기존 macro-only phase/receipt/CAS로 게시할 때 추가 source/LLM/Telegram 호출은 0이다.

최종 CI·pin readback·정책 SHA/hash·remote receipt·Pages/HTTPS 증거는 후속 closeout에 기록한다.
세 모듈 genuine scheduled는 아직 각각0/5다. 첫 nominal slot 2026-10-26 07:00 KST는 실행 관찰이 아니다.
