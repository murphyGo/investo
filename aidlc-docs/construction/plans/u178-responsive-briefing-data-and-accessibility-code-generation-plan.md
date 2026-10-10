# Code Generation Plan: `u178 responsive-briefing-data-and-accessibility`

- **Date**: 2026-10-10

- **Unit**: u178 responsive-briefing-data-and-accessibility

- **Stage**: Construction complete — local

- **Status**: Complete — FD/NFR and Code Generation 7/7; local validation complete

- **Source**: 공개 Investo UI 6페이지의 2026-10-10 데스크톱/390×844 모바일/Material 다크 모드 관측과 현재 코드 확인. 사용자 지시: “굿 일단 유닛 문서화부터 진행해줘”.

- **Estimated Effort**: 설계/검증 계획 4–6 h, 설계 승인 이후 구현/브라우저 검증 10–16 h. HTML 표현과 finalizer region 계약을 확정하기 전에는 구현 추정치다.

- **Dependencies**: u176 공통 shell/theme tokens; 완료된 u70/u75/u98/u108/u120/u143/u144/u154 계약. u175의 차트 경로 결함 수정은 별도 단위이며 candle renderer를 이 단위에서 재작성하지 않는다.

- **Planning Baseline**: `origin/main` 48762793. 공개 관측은 2026-10-10 01:12–01:17 KST의 기록이며 최신 코드/사이트 적용 완료를 뜻하지 않는다. 전체 범위·의존성은 [UI 개선 등록 문서](../ui-modernization-20261010/README.md), 보존 증거는 [측정값](../ui-modernization-20261010/evidence/metrics.json)과 [집중 확인 결과](../ui-modernization-20261010/evidence/focused-findings.json)를 참조한다.

## Problem Statement

2026-10-10 공개 미국 시황 모바일 관측에서 `데이터 신뢰도`, `시장 스냅샷`, `가격 스냅샷`, `관심 자산 관련성` 이미지의 자연 폭은 모두 1200px이고 화면 폭은 약 357.97px였다. 정보 텍스트가 약 30% 크기로 함께 축소되어 숫자·출처·제약을 읽으려면 확대해야 한다. 본문 표의 지역 컨테이너는 390px/scrollWidth 434px 및 534px였지만 스크롤 가능성을 안내하는 읽기 동선이 부족했고, 해당 모바일 관측의 article 목차 링크는 0개였다. `visuals/watchlist_chart.py`는 누적 관심 자산 inline SVG에 `_TEXT_COLOR="#1f2937"`, `_TITLE_COLOR="#111827"`를 고정하여 Material slate 배경에서 텍스트가 어둡다.

이는 정보가 담긴 SVG를 더 크게 만드는 문제만으로 해결되지 않는다. SVG와 같은 검증된 정보를 웹에서 반응형 텍스트로 읽을 수 있는 새 표현 계약, 중복 읽기 방지, 접근성, JS 실패 시 동작을 함께 정해야 한다. 기존 u154의 요약 우선/닫힌 숫자 details 개선은 현재 코드에 반영되어 있으므로 이를 다시 만드는 단위로 취급하지 않는다.

## Goal

웹 독자가 세 시장의 신뢰도·시장 요약·가격·관심 자산 정보를 확대 없이 읽고, 출처와 기준 시각 및 제한사항을 함께 확인할 수 있게 한다. 기존 카드 입력과 신뢰 게이트를 재사용한 HTML 표현을 정의하고, SVG/OG/raw GitHub 폴백을 보존하며, 데스크톱 목차와 모바일 section jump navigation으로 본문을 탐색하게 한다.

## Verified Evidence / Canonical Owners

### 현재 버전과 동시 등록된 v3 설계

최초 코드 기준은 48762793, 최종 문서 기준은 838bed60이다. 본 UI 번호는 동시 등록된 사건·뉴스 v3 u167–u173을 피해 u178로 확정했다. v3의 문서 순서·PublicEditionView·EventVisualInput/asset 의미·typed region은 u169/u171 소유다. 본 유닛은 **같은 검증된 입력을 읽기 편하게 표시하는 pure HTML/CSS/접근성 renderer와 탐색 표현**만 제공한다. source/event selection, E1 visual preparation의 v3 의미 전환, finalizer schema, asset-impact·OG payload를 새로 만들지 않는다.

아래 카드 4종·u154 순서/7H2는 현재 v1/v2/역사 자료를 설명한다. v3에 legacy 카드 bridge·TLDR3·7H2·기본 hero를 강제하지 않는다. FD는 현재 카드 입력과 향후 EventVisualInput을 분리하고, generic presentation에 필요한 exact fields는 각 schema의 canonical owner가 공급한다. v3 producer/region 연결 자체는 u169/u171이 소유하고 u178은 그 owner가 호출할 표현 함수·class/접근성 계약만 제공한다. 전환 중 v1/v2 새 HTML을 생산한다면 현재 u144 seal 이전 경계를 따르며 deprecated generator를 확장해 v3에 유지하지 않는다. `visuals/assets.py`/region 변경은 u171과 조정한 handoff에서만 수행한다. 아직 없는 v3 모델/API를 현재 구현으로 간주하지 않는다.

| 근거 | 현재 owner와 의미 |
| --- | --- |
| `src/investo/visuals/cards.py` | immutable `DataConfidenceCardInput`, `MarketSnapshotCardInput`, `PriceSnapshotCardInput`, `WatchlistRelevanceCardInput` 및 deterministic builder가 카드 입력의 정본이다. 새 browser-side 숫자 모델을 만들지 않는다. |
| `src/investo/visuals/assets.py::prepare_segment_visual_assets` | 동일 카드 입력에서 SVG와 dark companion을 준비한다. `VisualMarkdownBlock(placement_key, markdown, artifact_ids)`와 `PreparedVisualAssets`가 기존 표현/자산 전달 seam이다. |
| `src/investo/visuals/render.py` | SVG 카드 renderer와 테마 팔레트 owner. u143의 `light`/`dark`/`auto`/`site-scoped` 계약을 보존한다. |
| `src/investo/visuals/watchlist_chart.py::render_cumulative_match_chart` | 누적 매칭 수를 count 내림차순/term 오름차순으로 정렬하는 순수 inline SVG renderer. 다크 대비 보강 대상은 이 별도 표면이다. |
| `src/investo/publisher/public_document.py` | `PublicDocumentSupplement`, `PublicRegionExpectation`, `_build_region_expectation`, `_reindex_public_document`, `finalize_public_bundle`가 producer/region/terminal gate/seal의 정본이다. |
| `src/investo/publisher/reader_format/preamble.py` | u154의 canonical 제목·요약·닫힌 숫자 panel 조립 owner. 새 표현도 이 조립 이후 순서/region 계약을 통과해야 한다. |
| `_internal.public_quality_language`, `_internal.briefing_extract`, `_internal.archive_layout` | 공개 제한 문구, 결론/기준 시각 추출, archive 경로의 neutral owner. publisher→visuals/briefing 직접 의존을 만들지 않는다. |
| `mkdocs.yml`, `site_docs/assets/u29.css` | 실제 `md_in_html`, `toc`와 Material palette/공통 CSS 설정. 실제 빌드 후 DOM 및 접근성을 확인해야 한다. |

위 관측은 당시 공개 페이지의 기록이며 개선 완료 증거가 아니다. `/private/tmp` 캡처 파일의 존재는 미래 구현/검증의 필수 의존성이 아니다. 재현 fixture는 구현 단계에서 비밀 없는 고정 입력으로 저장한다.

## Existing Coverage / Deduplication

- **u70**: reconciled anchor 값·symbol label·표/차트/알림의 수치 정합성 owner. HTML은 확정 입력을 소비하고 숫자·변동률을 재계산하지 않는다.
- **u75**: lazy OHLC sidecar, 오류 상태, compact chart와 기존 no-JS 카드 owner. HTML 정보 전환을 차트 데이터 또는 로더 재설계로 확대하지 않는다.
- **u98**: §⑥ 관전 신호 compact card 및 제한값 처리 owner. §⑥ renderer/parser/프롬프트를 다시 만들지 않는다.
- **u108**: 공개 제한 문구와 raw diagnostic 보호 owner. 카드 모델의 raw 필드를 그대로 공개 HTML에 복사하지 않고 기존 projection을 재사용한다.
- **u120**: `ArchiveLayout` 주입과 visuals→publisher 금지 owner. 경로/스테이징을 sibling import로 해결하지 않는다.
- **u143**: SVG 카드 light/dark 쌍과 companion/provenance/raw GitHub 계약 owner. SVG를 없애거나 companion 목록에 HTML 자산을 혼합하지 않는다.
- **u144**: 한 번의 finalization, owned region containment, artifact descriptor→E5 선택 ID→E6 manifest, seal 이후 불변 owner. 새 텍스트는 이 경계를 우회할 수 없다.
- **u154**: 요약 우선, 제목 중복 제거, 닫힌 숫자 panel과 `reader_visible` 숫자 근거 owner. 재정렬·정보 접기를 이 단위가 재정의하지 않는다.
- **u176**: shell/theme/타이포그래피/공통 탐색 토큰 owner. u178은 토큰을 소비하며 사이트 전체 메뉴를 독자적으로 바꾸지 않는다.
- **u177**: 홈 market card/bundle 상태 owner. 본문 HTML 카드가 홈 미발행/신선도 판정을 복제하지 않는다.
- **u145**: sector radar renderer/nav/viewport/activation 계약 제외. 이 단위의 viewport 확인으로 u145 gate를 충족했다고 보고하지 않는다.

## Scope Boundary

In scope:

- 검증된 카드 4종 입력에서 웹 HTML 표현을 제공하는 설계 및 구현 seam.
- 수치/문자열/출처/날짜/기준 시각/미확인 값/제한사항의 보존과 공개 projection.
- HTML/SVG 대체 관계, 중복 screen-reader 읽기, JS 없는 기본 표시/fallback 계약.
- 누적 관심 자산 inline SVG의 site theme 대응 및 텍스트 대체 접근성.
- 본문에 필요한 표의 지역 스크롤 및 힌트, keyboard focus, 데스크톱 목차/모바일 jump navigation.
- u144 producer/region/artifact/fallback 통합과 실제 MkDocs DOM/viewport 검증.

Out of scope:

- 새 수집원/LLM 호출, 시장 판단·투자 조언·데이터 품질 계산·watchlist matching 변경.
- 브라우저에서 숫자·변동률·기준 시각 재계산, HTML DOM을 숫자 신뢰 정본으로 채택.
- SVG/PNG/OG/raw GitHub 산출물 삭제, 기존 archive 일괄 백필 또는 seal 이후 내용 변경.
- 홈/전역 메뉴 재설계, 달력 오류(u174), chart sidecar 경로 수정(u175), sector radar 활성화.

## Stage Decision

**Functional Design — REQUIRED/PENDING**. 새 HTML 표현은 웹/원문/SVG의 기본 표시, 중복 처리, 숨김·fallback, producer 위치와 region 소유권을 새로 결정한다. CSS 개선이라는 이유로 건너뛰지 않는다. 이 계획은 코드 생성 승인이나 구현 가능한 최종 설계가 아니다.

다음 3개 문서를 `aidlc-docs/construction/u178-responsive-briefing-data-and-accessibility/functional-design/`에 후속 작성한다.

1. `business-logic-model.md`: v1/v2의 카드 생성→공개 projection→HTML/SVG 표현→u154 조립→u144 region 재색인/검증/seal→MkDocs 표시 순서와, v3의 u169/u171 typed 입력·producer가 표현 함수를 호출하는 별도 흐름; JS/CSS/데이터/producer 실패 시 동작.
2. `business-rules.md`: 카드 종류별 필드·빈 값·노출·중복·목차·스크롤·fallback 규칙과 아래 미결 결정의 승인 결과.
3. `domain-entities.md`: 기존 card model과 `VisualMarkdownBlock`/`PublicDocumentSupplement`/region/artifact 매핑; 신규 DTO가 필요하다면 exact field/type/owner/compatibility.

**Focused NFR Requirements — REQUIRED/PENDING**. 새로운 정보 텍스트와 읽기 동선은 접근성·모바일 가독성·payload budget 검증을 필요로 한다. 아래 표준 후속 2개 문서를 작성한다.

- `nfr-requirements/nfr-requirements.md`: 390×844/1440×1000, light/slate, 확대 200%, keyboard/screen reader, contrast, no-JS/CSS 실패 및 카드 수 최대값의 payload/runtime 측정 기준. 본문 텍스트 16px 목표, 작은 메타 텍스트 14px 이상, 일반 텍스트 대비 4.5:1을 설계 검토 기준으로 삼고 최종 수치를 승인 문서에 고정한다.
- `nfr-requirements/tech-stack-decisions.md`: semantic HTML/CSS tokens/fallback/목차 구조, 실제 Markdown 설정 및 기존 NFR-003/004/005/006/R13 재사용, 측정 방법·상한·회귀/운영 검증 범위. 표준 `tech-stack-decisions.md`를 다른 단계 문서로 대체하지 않는다.

**Separate NFR Design — decision PENDING**. 기존 정적 사이트·projection·region/transaction 설계를 재사용해 위 요구사항/기술결정 문서에 흡수하는 안을 FD/NFR에서 검토한다. 새 DTO/producer/asset 경계가 별도 상세 설계를 요구하면 근거를 기록하고 `nfr-design/nfr-design.md`를 추가한다. 현재는 생략 또는 완료를 확정하지 않는다.

**Code Generation — NOT STARTED**. 위 설계와 미결 사항이 확정된 뒤 이 계획을 구체화하고 구현 단계를 시작한다. 현재 등록은 체크박스 완료나 배포 승인으로 해석하지 않는다.

### FD에서 확정해야 할 결정

- **D-178.1 HTML owner/seam**: 기존 카드 모델을 `visuals` 내 pure HTML renderer 후보에서 재사용하고 `VisualMarkdownBlock`로 전달할지, neutral immutable DTO를 명시적으로 분리할지 결정한다. publisher가 `visuals` 모델/renderer를 직접 import하는 선택은 불가하다. 구현 파일/호환 export/호출자를 설계 산출물에 정확히 고정한다.
- **D-178.2 기준 시각**: 카드 모델의 `target_date`와 실제 price time basis/원문 watermark/provenance를 구분한다. 현재 모델에 없는 세부 as-of를 임의로 만들지 않는다. 카드별 전달 가능한 필드와 `미확인` fallback 및 time basis 표기를 승인한다.
- **D-178.3 HTML/SVG 기본 노출**: JS 없이 HTML이 읽히고 SVG/원문 fallback도 접근 가능하도록 static 구조를 선택한다. CSS 실패 때 두 표현이 함께 보이는 경우와 screen-reader 중복 방지·원문 GitHub 렌더 tradeoff를 명시한다. SVG를 숨겨 terminal gate 대상까지 제거하는 설계는 불가하다.
- **D-178.4 region/failure policy**: HTML을 기존 visual supplement 안에 포함할지 별도 owned region으로 둘지 결정하고, 필수/선택 카드별 omission/replacement/fallback, 숫자 중복 finding과 artifact ID 선택을 표로 고정한다. 기존 `reader_visible` gate 및 u149 numeric containment를 재정의하지 않는다.
- **D-178.5 읽기 동선**: 현재 v1/v2는 u154 canonical headings, v3는 u169의 실제 schema별 headings를 소스로 사용한다. 데스크톱 목차와 모바일 jump nav의 위치·중복·stable anchor·focus 동작을 실제 Markdown DOM 기준으로 승인하고 v3에 legacy 7H2를 요구하지 않는다.

## Fixed Contracts

1. **동일 근거, 단일 계산**: 기존 immutable card inputs와 reconciled 값/label/time-basis를 소비한다. Browser JS/LLM/CSS로 새로운 숫자·등급·출처·시장 요약을 만들지 않는다. 표시 형식 변경도 수치 문자열·단위·방향·as-of·출처의 의미를 보존한다.
2. **공개 제한 보존**: u108 neutral projection을 재사용하고 진단 raw labels는 기존 protected diagnostics에만 남긴다. 데이터 없음/미확인 값을 0/정상/오늘 데이터로 바꾸지 않는다. 면책과 provenance caption을 보존한다.
3. **seal 전 생산**: 본 유닛의 HTML 표현 함수는 schema별 canonical producer가 u144 E2 재색인 전에 호출한다. 현재 v1/v2 연결과 v3 u169/u171 producer의 정확한 책임을 FD에 분리해 등록한다. 각 카드/문구의 stable ID/order, visibility policy, required/optional 판단, safe fallback과 artifact IDs는 해당 기존 owner의 계약을 소비하며 별도 finalizer/asset registry를 만들지 않는다. terminal gate는 read-only이고 seal 이후 archive를 수정하지 않는다.
   이미 sealed bytes를 사후 변환한 별도 숫자 HTML을 새로운 검증 없이 노출하는 경로도 금지한다. 사이트 CSS는 동일 검증된 콘텐츠의 가독성만 조정하고 새로운 데이터 표현 producer의 우회 경로가 되지 않는다.
4. **신뢰 게이트 범위**: HTML에 보이는 수치/링크/제약이 `reader_visible` region에서 기존 numeric/entity/compliance/disclaimer/link 검증을 받는다. HTML tags/닫힌 details/aria 속성이 unsafe evidence를 숨겨서는 안 된다. 중복 표현 검증은 same input/value가 일치한다는 것을 검사하며 검증 우회로 삼지 않는다.
5. **자산/폴백 계약**: SVG의 light/dark 쌍, OG·provenance·raw GitHub 링크·companion path를 보존한다. 새 HTML 표현은 독립 binary asset로 가장하지 않는다. visual omission 시 E1→E5→E6 surviving artifact chain과 롤백은 기존 u144 의미를 유지한다.
6. **progressive enhancement**: 카드 본문·출처·제한사항·section links는 JS가 없어도 접근 가능하다. 차트 fetch 실패가 HTML 정보를 없애거나 세그먼트를 차단하지 않는다. 표 overflow는 지역 컨테이너에 머무르고 힌트는 실제 overflow가 있는 표에만 제공한다.
7. **버전별 정보 순서**: 현재 v1/v2/역사 자료에서는 u154 숫자 panel·기존 body/u98 watchpoints를 보존한다. v3는 u169/u171의 사건 우선·접힌 참고·기본 hero 없음 계약을 소비한다. 실제 schema의 제목으로 목차를 만들며 7H2를 v3에 강제하지 않는다. 새 표현이 뉴스 요약 위로 길게 늘어서지 않는다.
8. **관측과 검증 분리**: 당시 이미지 폭/목차/색상 관측은 문제 근거다. 향후 새 발행 문서의 3시장·2테마·2viewport 및 no-JS 확인만 구현 AC의 검증 증거로 사용한다.

## Implementation Steps

- [x] **Step 1 — Functional Design**: 위 3개 산출물, D-178.1–5 및 kind별 필드/region/producer/failure/artifact 표를 작성·검토한다. 승인 전 renderer를 구현하지 않는다.
- [x] **Step 2 — Focused NFR**: 위 2개 산출물에서 실제 측정 기준과 승인 상한을 고정한다. u176 토큰/heading/nav 책임 경계를 확인한다.
- [x] **Step 3 — 설계에 따른 표현 renderer**: 동일 validated inputs의 HTML 표현과 static fallback을 구현한다. 모델/출처/숫자 계산을 복제하지 않으며 누적 watchlist SVG에는 site theme 대응을 추가한다.
- [x] **Step 4 — seal 통합/읽기 동선**: schema별 canonical owner와 조정한 producer/region/expectation/asset 연결을 E2 전에 통합한다. v1/v2의 u154 순서 및 v3 u169/u171 순서를 각각 보존하고 stable section anchors, 표 스크롤과 목차/jump nav를 구현한다.
- [x] **Step 5 — 의미/실패 회귀**: 4종 정보·3시장, 최대 rows, 없음/미확인, unsafe 링크/수치, diagnostics 보호, unsafe HTML evidence, fallback/omission, idempotence 및 surviving artifacts를 테스트한다.
- [x] **Step 6 — 실제 빌드/viewport 검증**: strict MkDocs와 기존 boundary/finalizer 테스트 후 390×844/1440×1000 light/slate, JS off, 200% 확대와 keyboard를 확인한다. 적용 archive/date/SHA/화면을 증거로 기록한다.
- [x] **Step 7 — closeout 기록**: 설계·코드·검증 범위와 신규 발행 적용 시점을 summary에 기록한다. 배포/기존 archive 백필은 별도 명시적 지시가 있을 때만 수행한다.

## Acceptance Criteria

- **AC-178.1**: FD 3개/NFR 2개 산출물과 미결 결정이 모두 확정되어 단위 구현의 owner·exact input·failure policy가 명확하다.
- **AC-178.2**: 현재 v1/v2의 4종 정보와 v3에서 실제 제공된 typed 정보가 390px에서 확대 없이 읽히며 필드·출처·time-basis·미확인·제한 문구 의미가 schema별 validated inputs와 동일하다. 카드/typed 모델이 없는 정보는 임의 생성하거나 legacy bridge로 채우지 않는다.
- **AC-178.3**: light/slate 토글, JS off, CSS 제한 환경에 대한 승인된 기본 표시/fallback/중복 정책이 실제 DOM에서 성립한다. 누적 watchlist SVG 텍스트 대비가 승인 기준을 통과한다.
- **AC-178.4**: 숫자/링크 HTML이 모든 기존 trust gate에서 reader_visible로 검사되고 required/optional region containment, u149 정책, E1/E5/E6 surviving asset 연결과 seal 불변을 보존한다.
- **AC-178.5**: v1/v2/역사 자료의 u154 순서와 v3 u169/u171의 사건 우선·참고 영역을 각각 보존한다. 데스크톱 목차/모바일 jump nav는 해당 schema의 실제 제목으로 이동하고 표 스크롤은 페이지 overflow를 만들지 않는다.
- **AC-178.6**: SVG/OG/raw GitHub와 no-JS 경로가 보존되고 새 외부 호출/LLM/금융 데이터 계산/sector 활성화가 없다. 실제 구현 이후 viewport 결과와 당시 문제 관측을 구분해 보고한다.

## Tests / Validation

현재는 **문서 등록만** 수행하며 아래 실행은 향후 구현 후 검증 계획이다. 새 파일명은 설계 확정 시 구체화한다.

```bash
uv run --extra dev python -m pytest tests/unit/visuals/test_cards.py tests/unit/visuals/test_render.py tests/unit/visuals/test_assets.py tests/unit/visuals/test_watchlist_chart.py
uv run --extra dev python -m pytest tests/unit/publisher/test_public_document_assembly_u144.py tests/unit/publisher/test_public_document_containment_u144.py tests/unit/publisher/test_staged_artifacts_u144.py tests/unit/publisher/test_canonical_preamble_u154.py tests/integration/test_canonical_preamble_html_u154.py
uv run --extra dev python -m pytest tests/unit/_internal/test_module_boundary.py tests/unit/publisher/test_public_document_architecture_u144.py tests/unit/publisher/test_segment_reader_surface_quality.py
uv run --extra dev --extra docs mkdocs build --strict
uv run --extra dev ruff check src/investo tests
uv run --extra dev ruff format --check src/investo tests
uv run --extra dev mypy --strict src/investo
git diff --check -- aidlc-docs/construction/plans/u178-responsive-briefing-data-and-accessibility-code-generation-plan.md
```

- **신규 예정**: `tests/unit/visuals/test_responsive_card_presentation_u178.py` — 동일 입력 표현 parity/projection/missing/time-basis；`tests/integration/test_responsive_briefing_html_u178.py` — 실제 `mkdocs.yml` HTML/region/fallback/JS off. exact files/owner는 FD 확정 후 계획에 갱신한다.
- 단위별 focused test 후 repository-required 전체 gate를 수행한다. 당시 screenshot이나 HTML 문자열 검사만으로 접근성·viewport 통과를 주장하지 않는다.
- 브라우저 QA는 실제 실행한 접근 경로와 viewport/theme/JS 상태를 기록하며 u145 activation gate 증거로 재사용하지 않는다.

## Non-Goals

금융 데이터 변경, 기사/시황 생성 품질의 새 정책, 투자 권유, 새 외부 서비스/의존성, 정적 asset 삭제, 기존 archive backfill, 운영 배포/커밋/푸시, u145 활성화는 이 등록 작업의 완료 조건이 아니다.

## Development decisions 2026-10-10

Required FD/NFR authored before implementation. Individual answers are developer decisions under complete development authorization. Exact producer/fallback/time/region/NFR choices are in unit design artifacts. Separate NFR/Infrastructure SKIP with concrete existing architecture reuse.

## Local completion 2026-10-10

All7 construction steps complete. Current v1/v2 inputs integrated before E2; future v3 owner remains u169/u171. Exact implementation, tests and measured22-case browser evidence: [summary](../u178-responsive-briefing-data-and-accessibility/code/summary.md). New tests are test_html_cards_u178.py, test_visual_html_gate_u178.py, test_section_navigation_u178.py and test_reader_seal_u178.py. Original docs-only validation text is the registration snapshot. Program-wide final gate follows u179. No push/deployment.
