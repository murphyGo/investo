# Code Generation Plan: `u175 chart-sidecar-url-and-theme-repair`

- **Date**: 2026-10-10
- **Unit**: u175 chart-sidecar-url-and-theme-repair
- **Stage**: Code Generation
- **Status**: Complete — 6/6; local construction verified 2026-10-10
- **Source**: 2026-10-10 공개 Investo UI 점검 및 사용자 “일단 유닛 문서화부터” 요청
- **Estimated Effort**: ~5–7 h
- **Priority**: P0 — 실제 확장 차트 404 및 사이트 테마 불일치 복구
- **Dependencies**: u50 lightweight-charts-embed, u70 cross-surface-numeric-anchor-reconciliation, u75 chart-data-externalization-and-mobile-performance, u143 visual-theme-parity-dual-variant. 기존 계약 연장; u174 build hook이나 홈 디자인을 hard dependency로 두지 않는다.

기획 맥락과 기준선은 [UI 개선 묶음](../ui-modernization-20261010/README.md), [브라우저 관측 JSON](../ui-modernization-20261010/evidence/focused-findings.json), [확장 실패 화면](../ui-modernization-20261010/evidence/us-chart-mobile-dark.png)에 보관한다.

## Problem Statement

차트 sidecar 파일은 아카이브에 있지만 Pages에서 카드 펼치기를 하면 404로 실패한다. publisher는 Markdown 파일과 같은 폴더 기준의 `2026-10-08.assets/charts/us-equity-gspc.json`을 `data-history-src`에 넣는다. MkDocs의 directory URL은 문서 URL을 `/2026-10-08/`로 바꾼다. `investo-chart-init.js::loadSidecarBars(src)`의 `fetch(src)`는 이를 브라우저 문서 디렉터리에 붙여 실제 자산 폴더보다 한 단계 깊은 주소를 요청한다. JSON을 inline으로 되돌리거나 생성/staging을 새로 만드는 문제와 다르다.

2026-10-10 공개 미국 시황 브라우저 관측:

- 문서: `/investo/archive/us-equity/2026/10/2026-10-08/`.
- expand 후 요청: `/investo/archive/us-equity/2026/10/2026-10-08/2026-10-08.assets/charts/us-equity-gspc.json` → **404**.
- 실제 sibling 위치: `/investo/archive/us-equity/2026/10/2026-10-08.assets/charts/us-equity-gspc.json` → **200**.
- details는 열렸지만 canvas **0개**, 메시지는 “차트 데이터를 불러오지 못했습니다.”였다.
- dark 페이지의 `body[data-md-color-scheme]`은 `slate`, `html`의 동일 속성은 `null`이었다. 그러나 `currentColorScheme()`와 `MutationObserver`는 `document.documentElement`만 읽고 관찰한다. u143에서 이미 확인한 Material body palette 계약과 맞지 않는다.

URL과 테마는 같은 차트 client adapter의 실제 페이지 환경 해석 오류이므로 한 유닛으로 묶는다. 시황 숫자·차트 공급자·자산 소유자는 변경하지 않는다.

## Goal

기존 archive-local JSON을 올바른 document sibling 경로에서 **명시적 expand 시에만** 읽고, 차트를 실제 Material body scheme에 맞춰 초기화·전환한다. MkDocs directory URL, flat URL, `/investo/` 또는 다른 Pages prefix, legacy plain-file URL의 기존 의미를 보존한다. 현재 committed 아카이브도 JS 변경으로 복구한다.

## Existing Coverage / Deduplication

| 기존 unit/owner | 보존할 계약 | u175의 추가 범위 |
| --- | --- | --- |
| u50 / self-hosted Lightweight Charts v4.2.3 | bundle/Apache-2.0 license SHA pin, candlestick·ATH·52w·native details | client URL·palette adapter repair만 |
| u70 / `publisher/charts.py` + reconciled MarketAnchor | canonical label·close·pct 단일 payload | 값·레이블·숫자 계산 변경 0 |
| u75 / `publisher/chart_sidecar.py` | `{stem}.assets/charts/{chart_id}.json`, schema 1, deterministic JSON, staged archive assets, lazy expand | 브라우저 URL 해석을 실제 MkDocs directory output과 일치 |
| u143 / DESIGN TD-013 | Material body scheme, SVG fragment pair, 단일 캡션 | 같은 body scheme을 interactive chart adapter도 소비 |

**DEBT-077**(u75 이전 inline-history archive의 sidecar 백필)과 **DEBT-078**(펼치기 전 compact sparkline 제품 결정)은 계속 별도 open debt다. `data-history-src`가 없는 레거시 카드에 히스토리를 새로 만들거나, sparkline을 위해 선행 fetch/inline history를 추가하지 않는다. 기존 u75의 GitHub Pages-compatible AC에서 빠진 실제 directory-URL 회귀를 보강한다.

## Scope Boundary

In scope:

- `site_docs/assets/investo-chart-init.js` 내부의 순수 URL resolver, `loadSidecarBars` 호출 경계, palette reader/observer.
- 기존 summary attrs, native `<details>/<summary>`, idle→loading→ready/error, per-card error 격리 보존.
- `tests/unit/publisher/test_chart_assets.py`의 기존 static assertions 보강 및 Node built-in `node:test`/`vm` 기반 행동 회귀 fixture.
- 실제 MkDocs directory/flat output·sidecar 위치를 다루는 isolated-build integration 및 실제 브라우저 검증.
- `.github/workflows/quality.yml`의 명시적 JS behavior gate, 완료 시 DESIGN/summary/state.

Out of scope:

- `chart_sidecar.py` JSON schema/path/파일 쓰기 및 asset staging 변경; `charts.py` placeholder 숫자/label/escaping 변경.
- MkDocs 전체 `use_directory_urls`를 뒤집거나 root absolute `/archive/…`를 Markdown에 새로 저장하는 방식.
- bundle 업그레이드, 외부 CDN/차트 API/키·서비스 추가, 새 source·price history.
- 아카이브 Markdown 일괄 rewrite, pre-u75 inline-history parse/backfill, compact sparkline 부활.
- 요약·본문·면책·quality·numeric/entity/compliance gate·최종화 seal 변경.
- observer의 SPA navigation 지원이나 새로운 재시도 UX 등 별도 제품 기능.

## Stage Decision

- **Functional Design — SKIP**. u50/u75가 승인한 동일 카드 펼치기와 light/dark 전환을 실제 배포 URL/Material palette에서 복구한다. 차트 범위·데이터·표시 의미·사용자 행동은 바뀌지 않고 새 sparkline/legacy backfill을 결정하지 않는다.
- **NFR Requirements / Design — SKIP**. 기존 NFR-003/005/006, R13, u75 lazy-load/zero-inline-history 계약을 재사용한다. 신규 런타임 의존성·외부 호출·비용은 없다. JS 행동 검증은 Node built-in만 쓰며 품질 workflow의 개발 검증에 한정된다; Playwright 등 브라우저 패키지를 프로덕션 dependency로 넣지 않는다.
- **Code Generation — READY**. 경로/테마 결함 복구의 아래 호환 매트릭스가 고정 계약이다. 사용자의 전체 개발 지시에 따라 구현/검증을 완료했다. [완료 증거](../u175-chart-sidecar-url-and-theme-repair/code/summary.md).

## Fixed Contracts

1. **Canonical ownership**: sidecar 파일 위치와 JSON은 `publisher/chart_sidecar.py`, placeholder attrs는 `publisher/charts.py`, **읽을 URL과 palette 해석은 `investo-chart-init.js`**가 소유한다. 다른 publisher/browser helper 또는 Markdown rewriter에 중복 resolver를 추가하지 않는다.
2. **URL normalization**: 같은 JS IIFE 안에 순수 `resolveSidecarUrl(src, documentUrl)` helper를 둔다. 브라우저 `URL`로 pathname/query/fragment를 해석한다. `src`가 u75의 단순 상대 `{stem}.assets/charts/{chart_id}.json`이고 현재 문서 URL 마지막 directory가 **동일한 `{stem}`**일 때만 article의 부모 폴더를 자산 base로 사용한다. `/…/{stem}/`와 `/…/{stem}/index.html`을 지원한다. flat `/…/{stem}.html`·plain `/…/{stem}.md`는 문서의 기존 폴더 base를 사용한다. query/hash는 경로 비교를 왜곡하지 않고 sidecar URL의 query/hash 의미는 보존한다.
3. **Compatibility preservation**: absolute URL, prefix 포함 root-relative URL, 이미 `../`로 보정된 참조, 기타 상대 참조에는 무조건 `../`를 붙이지 않는다. 이런 입력은 기존 `new URL(src, documentUrl)` 의미를 보존한다. 새 외부 URL이나 fallback host를 만들어 fetch하지 않는다. document URL과 `{stem}`이 일치하지 않으면 directory 보정을 하지 않는다. 오류 시 임의 다른 자산을 탐색하거나 여러 후보 URL을 fetch하지 않는다.
4. **Prefix support**: 현재 host·`/investo/`를 하드코딩하지 않는다. 테스트는 `/investo/`, 다른 project prefix `/demo/`, root `/`를 모두 다룬다. slash/trailing slash, 문서 query/hash, plain-file/flat URL에 대응한다. 실제 Markdown `data-history-src` bytes와 sidecar 상대 경로는 유지하므로 raw GitHub의 정적 Markdown 링크 의미도 바뀌지 않는다. GitHub가 chart JS를 실행한다는 보장은 만들지 않는다.
5. **Lazy/per-card preservation**: `loadSidecarBars`는 명시적 click/keyboard expand의 `toggle` 안에서만 resolver 결과를 fetch한다. DOMContentLoaded, viewport 진입, scheme toggle, 닫힌 카드 재렌더는 fetch 0건. 카드당 첫 expand의 fetch는 1건이고 재열기/테마 전환은 재fetch하지 않는다. HTTP/JSON/empty/malformed/history 실패는 기존 한국어 메시지와 그 카드만의 error state이며 sibling은 독립적으로 성공한다. `MAX_CHARTS_PER_PAGE = 5`를 유지한다.
6. **Material palette source**: 실제 Material scheme owner는 `document.body`다. 초기 값은 body attr 우선, body/attr 부재 시 기존 html attr compatibility fallback, 마지막 기본값 `default`; `slate`만 dark다. 하나의 MutationObserver로 존재하는 body와 html의 `data-md-color-scheme`을 모두 관찰하고 callback은 같은 reader로 유효 scheme을 다시 읽는다. body 존재/attr 부재 상태의 html 전환, 이후 body attr 추가·제거로 선택 owner가 바뀌는 상태도 놓치지 않는다. body에 scheme이 있으면 html 전환은 그 우선순위를 바꾸지 않는다. 유효 scheme 변경 시 이미 열린 chart/series options를 갱신하고, 닫혀 있거나 아직 loading인 카드는 다음 render 시 최신 scheme을 읽는다. theme 변경을 이유로 새 chart/series를 만들거나 history를 다시 받지 않는다.
7. **Unchanged financial/artifact contracts**: u70 canonical label·close·pct, ATH/52w·history row 해석, schema_version 1, deterministic `run_date`, asset/manifest/staged descriptor 소유 및 sealed Markdown bytes를 보존한다. Lightweight Charts bundle/license SHA, static SVG fallback·fragment 쌍·caption은 유지한다. 전체 OHLC inline이나 prefetch는 계속 금지다.
8. **Executable behavior gate**: 신규 `tests/js/test_investo_chart_init_u175.cjs`는 `node:test` + `vm` + 최소 DOM/MutationObserver/LightweightCharts stubs로 **실제 JS 파일을 실행**해 URL·fetch count·options를 검사한다. helper만 따로 복사하거나 문자열 grep으로 동작 검증을 대체하지 않는다. Quality workflow에는 Node 22 setup과 `node --test`를 명시해 Node 유무로 test를 조용히 skip하지 않는다. 브라우저 acceptance는 실제 built pages에서 별도로 수행한다.

## URL Acceptance Matrix

아래 표에서 `src = 2026-10-08.assets/charts/us-equity-gspc.json`이다. `{prefix}`는 `/investo`, `/demo`, 빈 문자열을 각각 대입한다.

| Document URL path | 확정 요청 path | 보정 여부 |
| --- | --- | --- |
| `{prefix}/archive/us-equity/2026/10/2026-10-08/` | `{prefix}/archive/us-equity/2026/10/2026-10-08.assets/charts/us-equity-gspc.json` | 동일 stem directory → sibling |
| `{prefix}/archive/us-equity/2026/10/2026-10-08/index.html` | 위와 동일 | directory index → sibling |
| `{prefix}/archive/us-equity/2026/10/2026-10-08.html` | 위와 동일 | flat 문서의 정상 상대 해석 유지 |
| `{prefix}/archive/us-equity/2026/10/2026-10-08.md` | 위와 동일 | plain file 상대 해석 유지 |
| `{prefix}/archive/us-equity/2026/10/other/` | `{prefix}/archive/us-equity/2026/10/other/2026-10-08.assets/charts/us-equity-gspc.json` | stem mismatch; 임의 추측 보정 없음 |

추가 케이스: 이미 `../2026-10-08.assets/…`인 directory 참조, root-relative prefix 참조, same-origin absolute 참조는 기존 `new URL()` 결과와 같아야 한다. input 없는 legacy placeholder는 기존대로 비확장 처리하고 fetch하지 않는다. 존재하지 않는 sidecar를 “고치기” 위해 날짜·세그먼트·공급자를 변경하지 않는다.

## Implementation Steps

### Step 1 — 실제 URL/팔레트 기준선과 회귀 fixture `[x]`

- [x] 현재 US `2026-10-08.md`/동일 sidecar 한 쌍과 legacy missing-src fixture를 isolated docs에 복사하여 directory/flat 각각 build한다. 실제 config의 확장/Material·symlink 자산 레이아웃을 보존한다.
- [x] 현재 실패 URL, 올바른 sibling JSON 위치, html/body attr 차이와 정적 tests만으로 누락된 행동을 기록한다.

### Step 2 — 좁은 URL resolver 구현 `[x]`

- [x] 위 matrix와 Fixed Contracts를 만족하는 같은-client 순수 resolver를 작성하고 lazy `loadSidecarBars`에서 사용한다.
- [x] prefix·query/hash·flat/raw·directory/index.html·이미 보정된 src·다른 stem·absolute/root-relative case를 실제 client harness에 연결한다. placeholder/schema/staging은 바꾸지 않는다.

### Step 3 — Material body palette 초기화와 observer 복구 `[x]`

- [x] body palette 우선 reader와 body/html의 선택 owner 변경을 관찰하는 observer로 변경한다. 기존 html fallback·기본 light는 유지한다.
- [x] initial slate, body/html 상충 시 body 우선, body 존재/attr 없음/html initial slate 및 html 양방향 전환, body attr 추가·제거, default↔slate, fetch 진행 중 toggle 후 render, reopen을 검증한다. theme transition에 따른 fetch·chart 재생성 0건을 확인한다.

### Step 4 — 행동 회귀 및 Quality gate `[x]`

- [x] 실제 JS를 실행하는 Node harness를 만들고 클릭/keyboard에 대응하는 details toggle, fetch 횟수, loaded bars, chart/series palette options를 단언한다.
- [x] 한 카드 HTTP404/JSON malformed/empty history 실패와 다른 카드 정상 확장의 독립성, legacy missing-src, max5 cap, no-inline/no-prefetch를 검증한다.
- [x] 기존 static tests는 필요 시 새 호출 형태로 갱신하되 fetch가 toggle 뒤에 있다는 기존 강도를 보존한다. Quality에 Node22 setup·syntax/behavior gate를 명시한다.

### Step 5 — 실제 MkDocs output 및 브라우저 검증 `[x]`

- [x] 신규 `tests/integration/test_chart_sidecar_site_u175.py`는 repository config를 바탕으로 isolated **directory/flat** 사이트를 build하고 sidecar가 Markdown sibling으로 복사되는지 검증한다. Node harness를 같은 built page URL/placeholder 기준으로 실행해 resolve된 fetch path를 output file과 대조한다.
- [x] 실제 built site를 prefix가 보존된 로컬 서버에서 desktop1440×1000/mobile390×844 각각 light/dark로 연다. expand 전 요청0, click/keyboard expand 후 JSON200·canvas>0, 닫고 재열기 요청추가0, 열린 chart 양방향 theme toggle을 확인한다.
- [x] 성공·실패 sibling, legacy no-src의 기존 static fallback을 확인한다. legacy에 새 compact quote를 만들지 않는다. 실제 차트 텍스트/그리드/series가 body palette를 따라가는 증거를 남긴다.

### Step 6 — 검증·리뷰·문서 종결 `[x]`

- [x] 아래 targeted/full gate, 독립 리뷰·cross-check를 수행한다. 브라우저 실행이 없으면 AC-175.6은 완료로 기록하지 않는다.
- [x] DESIGN에 URL/client palette 소유자를 보충하고 summary/state를 evidence와 함께 갱신한다. DEBT-077/078은 계속 별도 미완료로 두고 archive Markdown/JSON 및 bundle/license가 무변경인지 확인한다. 커밋/푸시/공개 배포는 당시 명시적 사용자 지시에 따른다.

## Acceptance Criteria

- **AC-175.1 — URL 호환**: matrix 모든 prefix/case가 정확한 URL을 resolve한다. directory/index.html에서 sibling JSON으로 향하고 flat/plain file은 기존 의미를 유지한다. absolute/root-relative/이미 보정된 src에 중복 `../`나 prefix 제거가 없다.
- **AC-175.2 — 실제 asset 일치**: actual-config directory/flat isolated build의 resolved URL이 실제 output JSON 파일과 대응하고 기존 current US fixture가 HTTP200으로 expand된다. 기존 Markdown `data-history-src`·JSON bytes·asset paths·seal은 바뀌지 않는다.
- **AC-175.3 — zero upfront fetch**: 초기 렌더/viewport/closed-card palette toggle에서 history 요청0, 첫 명시적 expand1, reopen/테마 toggle 추가0. inline OHLC는 없고 missing-src legacy는 fetch0이다.
- **AC-175.4 — 실패 격리**: 404/잘못된 JSON/빈 또는 유효 bar 없는 history는 기존 해당-card 한국어 error와 compact quote를 유지한다. sibling 성공 차트·본문·SVG fallback을 깨지 않는다.
- **AC-175.5 — 사이트 테마**: body slate/html 없음인 초기 상태는 dark options, body default는 light다. body/html 상충 시 body를 따른다. body 존재/attr 부재 상태의 html initial slate와 html 양방향 변경, body attr 추가·제거에 따른 선택 owner 변화도 반영된다. 유효 scheme 변경은 기존 chart/series options만 갱신하고 추가 fetch·객체 재생성·숫자 재계산은 0건이다. loading 도중 toggle도 최종 render에 반영된다.
- **AC-175.6 — 실제 브라우저 표시**: built directory/flat pages를 prefix 포함 URL에서 desktop/mobile로 확인하여 JSON200, canvas 생성, click/keyboard native expand, reopen no-refetch, light↔dark 읽기 가능한 text/grid를 증명한다. DOM stub와 `node --check`만으로 육안 acceptance를 충족하지 않는다.
- **AC-175.7 — 계약/지속 gate**: u50 bundle/license SHA, u70 reconciled attrs, u75 payload/path/schema/1fetch, u143 fragment/caption/Material guard가 통과한다. 실제 client Node behavior gate가 Quality에 연결되고 DEBT-077/078·배포 activation·새 product behavior는 추가하지 않는다.

## Tests / Validation

아래는 구현 검증 명령이다. 실제 실행 범위/결과는 완료 summary에 기록했으며 전체 회귀는 프로그램의 글로벌 Build & Test에서 추가 확인한다.

```bash
uv sync --extra dev --extra docs --extra sector
node --check site_docs/assets/investo-chart-init.js
node --test tests/js/test_investo_chart_init_u175.cjs
uv run python -m pytest tests/unit/publisher/test_chart_assets.py tests/unit/publisher/test_chart_placeholder.py tests/unit/publisher/test_chart_sidecar.py tests/integration/test_chart_sidecar_site_u175.py tests/integration/test_canonical_preamble_html_u154.py
uv run ruff check tests/integration/test_chart_sidecar_site_u175.py tests/unit/publisher/test_chart_assets.py
uv run ruff format --check tests/integration/test_chart_sidecar_site_u175.py tests/unit/publisher/test_chart_assets.py
uv run mkdocs build --strict
uv run python scripts/check_material_theme_contract.py
uv run python -m pytest
git diff --check
git diff --exit-code -- archive site_docs/assets/lightweight-charts.standalone.production.js site_docs/assets/lightweight-charts.LICENSE.txt
```

Python source/signature가 범위상 바뀌지 않으면 불필요한 source mypy 변경을 만들지 않는다. full CI의 기존 `uv run mypy src`, 네 정책 guard와 strict docs gate는 그대로 유지한다. 검증 증거는 Node version/actual-script execution, built page path, 네트워크 요청과 브라우저 theme observations를 구분한다.

## Non-Goals

신규 차트/통계/공급자, 더 많은 OHLC history, 레거시 백필, compact sparkline, prefetch, 숫자나 caption 수정, Markdown seal 재작성, UI 전면 디자인, u145 섹터 활성화, 공개 deployment는 이 유닛에서 수행하지 않는다.
