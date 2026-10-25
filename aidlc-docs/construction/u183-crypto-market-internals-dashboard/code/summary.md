# u183 크립토 시장 내부 구현

2026-10-25 · 격리 branch `codex/public-insights-unit-design-20261012` · 로컬 구현·검증 **7/8 완료**, 운영 Step8 별도.

사용자 후속 “진행시켜” 지시로 기존 FD/NFR/code plan을 채택하고 u180/u181/u182 위에 마지막 화면을 구현했다. modeoff 기본값, modules 기본macro, commit/push·main 통합·private pin/mode·실서비스 배포·Telegram은 변경하지 않았다.

## 제공 동작

- BTC dominance, total market cap, USD-linked supply, chain TVL sum, BTC funding, BTC USD OI, Fear & Greed의7slot을 세 패널+보조심리로 제공한다. 5기존 adapter의 응답에서만 opt-in envelope를 만들며 추가 runtime HTTP/key/registry/routing/fallback/legacy JSON bytes를 바꾸지 않는다.
- CoinGecko USD/점유율과 updated_at, DeFi 실제 요청 수집구간·원 숫자 Decimal 합계, Bybit/OKX 계약·fraction·USD명목·response clock·funding cycle, FNG의integer/index timestamp를 구별한다. 값의 source 역할도 검증단에서 고정하며 unknown clock은숫자를억제한다.
- Bybit 정상 fresh 표본을 우선하고 없으면 검증된 OKX를 선택한다. 동일 provider/계약/시점/값의 중복 응답만 dedupe한다. 다른 정상 표본은 최신 원천 시각으로 고르며 같은 시점의 상충은 해당 provider를 제외한다. fallback origin과 실제 producing source를 구별한다.
- 펀딩0.0001은 해당 적용주기의0.01%로 표시한다. cycle length는 원 필드에서 읽고 definition에 포함한다. 정산/24h평균/연율로 바꾸지 않으며 OI/공급/TVL을 전체시장 OI·실제 유입으로 해석하지 않는다.
- provider/contract/method/주기/단위/sample-policy가 바뀌면 이력 연결을 끊는다. UTC 수집 날짜별 마지막 remote-confirmed 표본을 쓰고 D/D-7의 정확한 호환 기록이 있을 때만 차이를 제공한다. 당일 새 표본 교체(superseded_from)와 같은 원천 시점의 수정(revised_from)을 구별하고 source/applicable cycle clock을 이력에 보존한다.
- 권리 철회/미확인 지표는 current·history에서 제외한다. current-only 첫 화면, 자료부족·부분 상태, 36h 초과 last-good·원래 시각, source별 수집경로/허용 범위를 제공한다. 기본 matrix는FNG1정의만허용하고 나머지8정의는차단한다.
- noJS에서도현재7카드·단위·기준시각·출처·면책을읽는다. history는 명시적 선택 후 same-origin manifest/snapshot/current hash/history SHA256과serieskey를 확인해 최대30표본 표·보조SVG로 보여준다. 오류는현재카드를보존한다. 출처 notice를 값·이력표·그래프 옆에 표시한다. 공용 reader의 기존 macro 기능도16조합/6row이력으로 회귀 확인했다.

## 검증과 범위

현재 collection7,143개를 네 full shard·최종focused·수정 shard의 node별 최신 결과로 대조해 **7,142 passed / 기존1 skipped**, 누락·미해결 실패0을 확인했다. 최종focused211pass/63.61초, 별도DST roundtrip9pass/2.26초다. 중복 집계 없이 [validation](validation.json)에 checkpoint를 구별한다. source/domain/render/integration의 초기46tests, source-clock 역할 두 negative를 추가한48tests를 확인했다. 독립 리뷰에서 초기47pass와 clock 후속2pass, 마지막 기존PBT9pass를 별도로 확인했으며 미해결 C/H/M0이다. [초기](review-u183-initial.md), [최종](review-u183-final.md).

전체 회귀 중 기존 모델 PBT가 DST imaginary datetime의 IANA-vs-fixed-offset equality로 실패했다. HEAD와 현재 모델 모두에서 같은 실패·동일JSON/UTCinstant를 재현했다. 제품 모델을 바꾸지 않고 assertion을 JSON-visible fields 보존으로 고쳤으며 imaginary/두fold의3개 시각 회귀를 추가했다. 기존 timezone 생성 범위를 줄이지 않았다. 실패한 full shard 전체를 다시 실행해1,789pass/284.53초를 확인했다. [기준 코드 재현](dst-baseline-evidence.json).

실제 임시 Chromium154의390×844/1440×900, light/dark, JS유무,100%/200%상당 확대16cases를 확인했다. 200%는 CSSviewport 절반+DPR2 등가 확대다. overflow·새pageerror·선택전history요청0, keyboard Enter·56row lazy table·hash/snapshot 차단·theme/hub/기존sectors200을 확인했다. Browser connector는 기존 설치 경로 오류이며 사용자 profile이나 u145waiver를 사용하지 않았다. 전체7card/history는 명시된 합성 fixture다. [화면](browser-evidence.json).

Ruff/format781·mypy328·정책/strictMkDocs/Material/Calendar를 통과했다. 합성7card의 current8,854bytes/HTML9,397bytes(100KiB 이하), 공통CSS+history JSgzip4,230bytes(20KiB 이하)다. 자원시험은 추가RSS61,063,168bytes/CPU2.550초/wall5.311초로 상한을 지켰다. 최종 crypto grid의 desktop2열/mobile1열도 실제렌더에서 확인했다. Source5개9typed metric의 실제응답replay·합성UI·로컬bare Git수용·실제production 배포를구별한다. [원천조건](source-qualification.md), [개발조회](source-probes.json), [자원](resource-evidence.json), [요구사항 대조](../../../../docs/cross-checks/2026-10-25-u183-crypto-market-internals-dashboard.md).

## 운영 경계

base55c00fc8과 시작시origin/main0768d780을 구별했다. 관련5adapter의upstream차이는없었지만 최신main 통합·정확한implementation SHA검증은Step8이다. u180/u181/u182와 root의 기존 작업을 보존했으며 새ADR/debt로 넘긴 미해결finding은없다.

요청한 매크로→일정→크립토의 세 화면은 로컬 구현 경로를 갖췄다. 다음은 후속 지시에 따른 최신main통합/commit·push와 source조건·reviewedprivate pin/mode·Pages·5회scheduled 운영수용이다. 이 로컬 결과만으로 활성화하지 않는다.
