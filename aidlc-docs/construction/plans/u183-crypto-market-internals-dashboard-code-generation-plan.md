# Code Generation Plan: u183-crypto-market-internals-dashboard

작성일: 2026-10-12 · u183 · 상태: 2026-10-25 사용자 후속 “진행시켜” 지시로 설계 채택. 로컬 구현·검증7/8 완료, 운영 Step8은 별도다.

## 문제와 목표

시장 규모·USD 연동 공급·체인 TVL·BTC 거래소 파생상품을 제공자/계약/주기/조회시점에 맞게 읽을 수 있는 공개 내부 지표 화면을 만든다.

## Existing coverage / Deduplication

u180 typed gate/history/receipt, u181/u182 사용자 순서 전달, u66/u74 기존 crypto indicator 의미와 u164 source-vs-query time 재사용. 소스별 public display/retention 은 activation prerequisite 이며 코드 fixture 작업의 가짜 승인으로 만들지 않는다.

[Program 중복 대조](../public-insights-20261012/README.md)와 [source 판정](../public-insights-20261012/source-assessment.md)을 따른다. source 별 defaults/tier/window/segment/registry 는 유지하며 raw numeric/event envelope 만 opt-in 추가한다.

## Scope boundary

기존 sources/defillama_market_structure.py/coingecko_global_market.py/bybit_derivatives.py/okx_derivatives.py/alternative_fng.py 의 opt-in envelope; models/insights.py 의 crypto7slot definition; orchestrator/insights_projection.py crypto precedence/selection; publisher/insights/crypto.py; crypto/index.md 와 _data/crypto; 공통 history/filter/nav·qualification·tests.

제외: crypto price/Demo 키 활성화, 추가 ETH/SOL 파생상품, 거래소별 liquidation/netflow, ETF 실제 fund flow, TVL 기반 유입 단정, 펀딩 연율·24h 평균·시장 종합 위험점수, provider 바뀐 OI 이력 연결, 새 paid/historical endpoints.

## Stage decision

- Functional Design: REQUIRED / ADOPTED. 새 public 데이터 의미·시간·상태·독자 workflow 와 cross-module contract 가 있다. [FD](../u183-crypto-market-internals-dashboard/functional-design/business-logic-model.md).
- NFR Requirements: REQUIRED / ADOPTED. source rights/private 경계·신뢰·자원·retention/새화면·runtime 를 구체화한다. [NFR](../u183-crypto-market-internals-dashboard/nfr-requirements/nfr-requirements.md).
- NFR Design: focused design in [shared contracts](../public-insights-20261012/contracts.md), 별도상투적문서 대신 C3–C7 의경계·cap·recovery 로구체화. 승인·실제검증은미기록.
- Infrastructure Design: SKIP separate stage; u180 의 focused 기존 privatejob/Pages 계약을 재사용하며 새스케줄/환경/secret 은 없다.
- Code Generation: LOCAL VERIFIED7/8. 사용자 후속 지시로 로컬 구현·검증하며 commit/push/운영 활성화는 별도다.
- Source requirements: 사용자 2026-10-12 지시, US-013; FR-029/026; 기존 FR-003/011/013/018; NFR-001~008/R10/R13. 신규공식 source 자격검증이있으면 별도 bounded source plan 에 handoff 한다.

## Fixed contracts

[C1–C7](../public-insights-20261012/contracts.md), [unit rules](../u183-crypto-market-internals-dashboard/functional-design/business-rules.md), [entities](../u183-crypto-market-internals-dashboard/functional-design/domain-entities.md)가 normative 초안이다. 입력/시간/identity/owner/permission/부분상태/파일원격확정순서를구현중임의로바꾸지않는다. DTO/private envelope 와 HTML·JSON·이력·receipt 의 role 을구별한다.

## Implementation steps

- [x] **Step 1** — 5adapter 의 field/cadence/source-clock/contract/funding basis/OIUSD·public display/retention/attribution 와 실제 scoped fixtures 를 qualification 으로 고정한다. source unavailable/미확인도 정상 판정이다.
- [x] **Step 2** — 기존 응답에서 opt-in crypto envelopes 를 추가한다. source HTTP·Bybitfallback·legacy title/metadata/serialized prompt bytes 를 유지하고 실제 source clock/계약/주기만 side channel 에 전달한다.
- [x] **Step 3** — crypto7slot finite/range/unit/aggregation/time validation, 기존 provider precedence·중복응답 conservative dedupe·source-specific status 를 구현한다.
- [x] **Step 4** — publisher/insights/crypto.py 의 3panels+optionalFNG current-only view 를 구현한다. supply/TVL 과 netflow, venue OI 와 globalOI, indicative 와 settled 를 독자용 표기로 구별한다.
- [x] **Step 5** — 허용된 public history 의 UTC 일별표본·exact7 일 변화·30 표본 graph 를 연결하고 provider/contract/basis 바뀌면 비교를 억제한다. 이력 부족과 delayed/stale source 를 표시한다.
- [x] **Step 6** — u181/u182 hub/nav 와 scoped CSS/JS·noJS·모바일·출처/clock/cycle 보조설명을 구현하고 실제 두 viewport/theme/keyboard/200%를 확인한다.
- [x] **Step 7** — source/domain/render/history/sitefocused 와 full/static/policy/docs 검증, source-specific qualification/AC review 를 기록한다. raw fixture 를 public repo 에 새로 복사하지 않는다.
- [ ] **Step 8** — 후속 운영 instruction 에서 권리/필드/time 검증 카드만 활성화한다. exact-SHA5 회 예약관찰·runtimepin/mode·Pages/live hash/시점을 기록하고 미확인 카드 활성화 0.

## Acceptance criteria

- AC-183.1:crypto7slots 는 검증된 source fields/unit/provider/계약/clock/집계 범위와 일치, metric 범위를 넘어서는 global/flow inference0.
- AC-183.2:funding fraction0.0001 은 해당 주기의 0.01% 관찰로 표시;24h 평균/연율/settled 추정 0. OIUSD 와 coin/contracts 를 구별.
- AC-183.3:Bybit 우선/OKXfallback 을 보존하고 같은 source/contract 의 같은 sample 만 dedupe; provider switch 에 7 일/그래프연결 0.
- AC-183.4:source time 없음은 unknown/collection 구간으로 표시;Synthetic window clock 를 실제 시각으로 만들지 않고 36h freshness 의미를 유지.
- AC-183.5:소스별 display/retention/attribution 과 원천 scope 가 검증된 card 만 public/current/history 에 포함; 일부실패의 정상 sibling card 유지.
- AC-183.6:current-only first release·compatibleD/D−7·30 표본·noJS/두 viewport/theme/keyboard/확대/payload 예산과 정책 tests 통과.
- AC-183.7:source qualification·코드·원격배달·5 회운영·livePages 수용을 구별하고 기존 Demo/source/event/sectoractivation 을 변경 0.

## Tests / Validation

source/domain/render/integration 48cases와 실제browser QA를 구현했다. 현재7143개검증의latest node 집계7142pass/기존1skip, 최종focused211pass+별도DST9pass. [검증](../u183-crypto-market-internals-dashboard/code/validation.json).

- `tests/unit/orchestrator/test_crypto_insights_projection_u183.py`
- `tests/unit/publisher/test_crypto_insights_render_u183.py`
- `tests/integration/test_crypto_insights_site_u183.py`

기존 owner 회귀: tests/unit/sources/test_defillama_market_structure.py; test_coingecko_global_market.py; test_bybit_derivatives.py(Bybit+OKX fallback/standalone owner); test_alternative_fng.py; u66/u74 crypto indicator tests.

필수 공통 명령은 `uv sync --extra dev --extra docs --extra sector`, scoped+full `uv run python -m pytest`, changed Ruff/format·source mypy, `python scripts/check_no_paid_apis.py`, `python scripts/check_no_anthropic_sdk.py`, 기존 curated/image guards, `uv run mkdocs build --strict`, `python scripts/check_material_theme_contract.py`, `git diff --check`다. workflow 변경이 있는 u180 은 actionlint 와 private runtime template/output negative 검증을 포함한다.

각 source recording/문서조건·합성 domain case·실제 viewport·remote/livePages·5 회 scheduled 를서로구별해기록한다.  현재문서작업은제품 test 결과가아니다. [시나리오](../public-insights-20261012/acceptance-scenarios.md)를 AC 에연결한다.

## 2026-10-25 로컬 구현 수용

Steps1–7 PASS. [구현](../u183-crypto-market-internals-dashboard/code/summary.md), [AC](../../../docs/cross-checks/2026-10-25-u183-crypto-market-internals-dashboard.md). 독립C/H/M0, crypto16+기존macro16render PASS. Source5/9정의1allow·8blocked, 기존7endpoint개발200/typed9replay와production은구별한다. source별 source-role clock·history정의단절·인접attribution을검증했다. 전체회귀의기존DST PBT를HEAD에서도재현한후JSON보존계약에맞춰test만수정하고실패shard1789pass를확인했다. Step8 latest-main/exact implementationSHA·source권리·privatepin/mode·Pages·5회scheduled는pending. 새유닛진입없이요청한세화면의로컬구현을마쳤다.
