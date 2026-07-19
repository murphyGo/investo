# Code Generation Plan: `u143 visual-theme-parity-dual-variant`

**Date**: 2026-07-19
**Unit**: u143 visual-theme-parity-dual-variant
**Stage**: Code Generation
**Status**: Planned (0/6)
**Source**: 2026-07-19 user ratification of the third path recorded in the DEBT-049 investigation (2026-07-19). 원안 (b) inline `<svg>` / (c) `<picture>` 모두 기각되었고, mkdocs-material 내장 light/dark 이미지 규약(`#only-light` / `#only-dark` 계열 fragment 쌍)을 채택한다. DEBT-061(캘린더 히트맵)은 같은 단위에서 함께 닫는다.
**Estimated Effort**: ~5-7 h
**Dependencies**:
- u19/u22/u26 briefing-visual-assets (`visuals/render.py::_CARD_STYLE`, `visuals/assets.py` 카드 렌더/삽입 경로)
- u24 visual-provenance manifests (`visuals/provenance.py` 사이드카 계약)
- u29 site-discovery-v2 (`visuals/calendar_heatmap.py` — DEBT-061)
- u86 curated-context-asset-library (`validate_visual_binary` — 사이드카 없는 바이너리 게이트 선례)
- u120 visual-asset-archive-context-boundary (`ArchiveLayout` 경유 경로 계약)

---

## Problem Statement

`<img src="…svg">`로 임베드된 SVG는 **독립 문서**다. 문서 내부 `<style>`의 `@media (prefers-color-scheme: dark)`는 **OS 수준** 스킴만 본다. mkdocs Material의 사이트 토글은 부모 페이지 `<body data-md-color-scheme="…">` 속성만 뒤집으므로 SVG에서 보이지 않는다. 결과: 사이트 토글을 OS 기본값과 다르게 맞춘 독자는 어두운 페이지 위 밝은 카드(또는 그 반대)를 본다 — 세그먼트 시황 UX에서 가장 레버리지 큰 신뢰 신호가 눈에 띄게 깨진다.

`<img>` 임베드가 유지되는 한 CSS로는 해결 불가능(투자 확정 사실, DEBT-049 investigation). **부모 쪽 CSS가 고를 수 있는 두 개의 자산**만이 토글을 추종할 수 있다.

## Verified Facts (2026-07-19 코드/빌드 산출물 확인)

| 사실 | 근거 |
| --- | --- |
| Material은 fragment 기반 light/dark 이미지 규약을 **내장 CSS로 이미 제공**한다 | `site/assets/stylesheets/palette.*.min.css`: `[data-md-color-scheme=slate] img[src$="#gh-light-mode-only"],[data-md-color-scheme=slate] img[src$="#only-light"]{display:none}` / `main.*.min.css`: `[data-md-color-scheme=default] img[src$="#gh-dark-mode-only"],[data-md-color-scheme=default] img[src$="#only-dark"]{display:none}` |
| `#only-*` 와 `#gh-*-mode-only` 는 Material 안에서 **완전 동치 alias** | 위 두 셀렉터 목록 |
| 셀렉터는 `src$=` (접미 일치) — fragment는 반드시 src 맨 끝 | 위 |
| `data-md-color-scheme`은 `<html>`이 아니라 **`<body>`**에 서버 렌더된다(초기값 `default`) | `site/index.html` `<body dir="ltr" data-md-color-scheme="default" …>` |
| mkdocs.yml 팔레트는 2개(default/slate) + media 기반 자동 선택 + 수동 토글 | `mkdocs.yml` L55-69 |
| 카드 SVG는 `archive/{segment}/{YYYY}/{MM}/{date}.assets/` 아래 — u137 스토어 게이트 범위 **밖** | `scripts/check_image_store.py` `_DEFAULT_STORE_ROOT = assets/images` |
| **캘린더 히트맵은 `<img>`가 아니라 markdown에 raw `<svg>`로 인라인된다** | `archive/index.md` L13-14 `<figure class="u29-heatmap" markdown="1">` + `<svg …>`; `publisher/site_index/archive_sections.py:71` |
| **품질 스파크라인도 인라인** | `site_docs/quality.md` L3 raw `<svg>`; `publisher/site_index/quality_dashboard.py:77` `render_quality_sparkline(...).decode("utf-8")` |
| 스타일 블록은 하나가 아니라 **셋** | `render.py::_CARD_STYLE` (카드 4종 + 스파크라인이 재사용), `calendar_heatmap.py::_HEATMAP_STYLE`, `og_card.py::_OG_STYLE` |

**투자 전제 정정 2건** (DEBT-049/061 investigation 대비):
1. DEBT-061은 "히트맵도 `<img src>`라 DEBT-049와 같은 dual-variant를 상속한다"고 기술하나 **사실이 아니다**. 인라인 `<svg>`이므로 `<style>` 블록이 페이지 CSS 캐스케이드에 그대로 참여한다 → **조상 셀렉터(원안 (b)) 방식이 파일 증가 0으로 성립**한다. 히트맵·스파크라인은 dual-variant 대상이 아니다.
2. "`_CARD_STYLE` 초크포인트 하나"가 아니라 스타일 블록이 3개다. dual-variant가 실제로 필요한 것은 `_CARD_STYLE`을 쓰는 **`render_card_svg` 산출 SVG 카드 4종**뿐이다.

## Existing Coverage / Deduplication (reuse — do NOT rebuild)

- `visuals/render.py::_CARD_STYLE` — 색 팔레트 단일 출처. 상수를 **팩토리로 매개변수화**하되 문자열 테이블을 새로 만들지 않는다.
- `visuals/paths.py::visual_asset_path` — `_SAFE_ASSET_NAME = ^[a-z0-9][a-z0-9-]*$`. `data-confidence-dark` 등 다크 이름이 이미 통과한다. 정규식 완화 금지.
- `visuals/assets.py::validate_visual_binary` — 사이드카 없이 바이너리만 검증하는 기존 게이트(u86 선례). 다크 트윈 검증에 그대로 쓴다.
- `visuals/assets.py::_visual_block` / `_select_hero_index` / `_find_section_anchor` — 전부 `path.stem`을 키로 쓴다(`_CARD_LABELS` / `_HERO_CARD_KINDS` / `_SECTION_ANCHORS`). 다크 경로를 `asset_paths`에 섞으면 `_CARD_LABELS[path.stem]`이 KeyError를 내고 DEBT-040 순서 계약이 깨진다 — **섞지 않는다**(Fixed Contract #3).
- `visuals/provenance.py::sanitize_provenance_text` — `additional_metadata` 값은 STRICT 리댁션을 통과한다. `"light"` / `"data-confidence-dark.svg"`는 시크릿 형태가 아니므로 무손실 통과(u137 TS-2 digest 예외와 무관).
- `orchestrator/pipeline.py:2111-2115` — `prepared.asset_paths`를 돌며 매니페스트 경로를 스테이징에 덧붙이는 기존 루프. 여기에 companion 경로만 합류시킨다.

## Scope Boundary

In scope:
- `_CARD_STYLE` 초크포인트의 variant 매개변수화 (`light` / `dark` / `auto` / `site-scoped`).
- SVG 카드 4종의 light/dark 이중 산출 + markdown fragment 쌍 방출 + 스테이징.
- 다크 트윈의 프로비넌스 정책 확정(사이드카 미발급, 주 매니페스트에 기록).
- DEBT-061: 캘린더 히트맵 + 품질 스파크라인의 조상 셀렉터 전환(**같은 팩토리, 파일 증가 0**).
- 기존 단일 variant 테스트/골든 마크다운/파일 카운트 단언의 갱신(약화 아님).

Out of scope (명시적 non-goal):
- `mkdocs.yml` 변경 — 0줄. Material 내장 CSS만 사용한다.
- 커스텀 CSS/JS 오버라이드 추가 (`overrides/`).
- OG 카드(`og_card.py::_OG_STYLE`) — 소셜 스크레이퍼/`cairosvg` PNG 래스터화 대상이라 Material CSS가 존재하지 않는다. `auto` 유지, 팩토리 통합은 Deferred.
- PNG/JPEG 히어로(`ai-market-hero` / `curated-context-image` / `external-context-image`) — 사진에는 테마 변종이 없다. 단일 링크·fragment 없음 유지.
- 기존 커밋된 아카이브 마크다운의 백필 — 신규 발행분부터 적용(DEBT-077 선례와 동일 원칙). Deferred에 기재.
- 색 팔레트 값 자체의 변경(대비/접근성 튜닝) — 현재 hex 값을 그대로 재배치만 한다.

## Stage Decision

- **Functional Design — SKIP (confirmed)**: 신규 도메인 엔티티·상태기계·라우팅 없음. 기존 렌더 초크포인트의 매개변수화와 산출물 1:2 확장이며, 카드 입력 모델(`cards.py`)·수집·생성·게시 흐름은 불변. u129(visual-provenance sidecar error boundary) / u120 선례와 동급의 표면 단위.
- **NFR Requirements — SKIP (confirmed)**: 신규 외부 호출·의존성·시크릿·비용 0. 성능 영향은 로컬 SVG 문자열 렌더 1회 추가(밀리초 단위, u5 10분 예산과 무관). 저장 영향은 기존 게이트의 **범위 밖**이며 Fixed Contract #5에서 정량 고정 + Step 0에서 실측한다 — 신규 NFR AC를 세울 만한 예산 표면이 없다. 접근성/일관성은 NFR-005 기존 항목으로 커버, 단위 AC(AC-143.1/143.2)로 고정한다.

## Fixed Contracts

### #1 — 스타일 초크포인트 형태 보존 (variant 매개변수화)

`visuals/render.py`에 **색 테이블 1개**를 단일 출처로 둔다:

- `_CARD_PALETTE: Final[tuple[tuple[str, str, str], ...]]` — `(css_class, light_declarations, dark_declarations)` 행. 현재 `_CARD_STYLE` 문자열에 든 8개 클래스의 값을 그대로 옮긴다(값 변경 금지).
- `CardStyleVariant = Literal["light", "dark", "auto", "site-scoped"]`
- `build_card_style(variant: CardStyleVariant) -> str` — 유일한 `<style>` 생성 경로:
  - `light` — light 선언만. `@media` 없음.
  - `dark` — dark 선언만(forced-dark). `@media` 없음.
  - `auto` — light 선언 + `@media (prefers-color-scheme: dark){…}`. **오늘의 `_CARD_STYLE` 문자열과 바이트 동일**해야 한다.
  - `site-scoped` — light 선언 + `[data-md-color-scheme="slate"] .card-…{…}` 조상 셀렉터 오버라이드. 인라인 `<svg>` 표면 전용.
- `_CARD_STYLE: Final[str] = build_card_style("auto")` 별칭을 남긴다 — `quality_sparkline.py`의 기존 import가 Step 5까지 무변경으로 산다.
- `render_card_svg(card, *, variant: CardStyleVariant = "light")` / `_svg_document(..., variant)` — variant는 `_svg_document` 한 곳에서만 소비된다.

**신규 카드 타입이 추가 작업 없이 양쪽 variant를 상속함**의 정의: 새 카드 입력 클래스는 `_RenderableCard` 유니온에 들어가고 `render_card_svg`가 `_svg_document`를 거치므로, Contract #2의 쌍 방출기가 자동으로 두 파일을 쓴다. **이를 고정하는 테스트**(Step 1): `typing.get_args(_RenderableCard)`로 유니온 멤버를 열거하는 registry-driven 파라미터라이즈 테스트가 각 멤버에 대해 (a) `variant="light"`/`"dark"` 산출 SVG가 서로 다르고 각각 `@media`를 포함하지 않으며, (b) `prepare_segment_visual_assets` 후 `{kind}.svg` + `{kind}-dark.svg`가 모두 존재하고, (c) markdown에 fragment 쌍이 있음을 단언한다. 유니온에 클래스를 추가하고 배선을 빠뜨리면 이 테스트가 실패한다.

### #2 — 이중 산출 + fragment 쌍

- 파일명: light = `{kind}.svg` (**기존 이름 불변** — 아카이브 연속성), dark = `{kind}-dark.svg`. `visual_asset_path(...)`의 `_SAFE_ASSET_NAME`을 그대로 통과한다.
- fragment 상수는 `visuals/paths.py`에 단일 등록: `LIGHT_ONLY_FRAGMENT` / `DARK_ONLY_FRAGMENT`. 값은 Contract #4 참조.
- markdown 방출 형태(캡션은 **쌍당 1회**):

  ```
  ![데이터 신뢰도](2026-07-19.assets/data-confidence.svg#gh-light-mode-only)
  ![데이터 신뢰도](2026-07-19.assets/data-confidence-dark.svg#gh-dark-mode-only)
  *<provenance caption>*
  ```

- **fragment는 순수 표현 계층이다**: `Path` 값·`asset_paths`·`companion_paths`·매니페스트 `asset_path`·git 스테이징 인자·`validate_visual_asset` 입력 어디에도 `#`가 들어가지 않는다. `visual_asset_relative_path()`는 fragment 없는 문자열을 반환하고, fragment는 `_visual_block`에서만 접합한다. Step 3 회귀 테스트로 고정.
- PNG/JPEG 히어로는 오늘의 단일 링크(fragment 없음)를 유지한다.
- 멱등성: `insert_visual_links`의 `all(block in markdown …)` 검사는 쌍 전체를 담은 블록 문자열 기준으로 동작하므로 2회차 호출이 입력을 그대로 돌려준다 — 기존 계약 유지.

### #3 — `asset_paths` 멤버십 불변, companion은 별도 채널

- `PreparedVisualAssets`에 `companion_paths: tuple[Path, ...]` 필드를 추가한다.
- `asset_paths`의 **멤버십과 순서는 오늘과 완전히 동일**하게 유지한다(주 자산만). `_select_hero_index` / `_find_section_anchor` / `_CARD_LABELS[path.stem]` / DEBT-040 동일-앵커 순서 계약이 전부 무변경으로 산다.
- 다크 트윈은 `companion_paths`에만 들어간다.
- `insert_visual_links(markdown, *, markdown_path, asset_paths, dark_variants: Mapping[Path, Path] = {})` — 키워드 전용, 기본 빈 매핑(빈 매핑 = 오늘의 단일 링크 출력, 바이트 동일). **프로덕션에서 빈 기본값 분기는 도달 불가**여야 하며, `prepare_segment_visual_assets`가 모든 SVG 카드에 대해 항상 비어있지 않은 매핑을 넘긴다는 사실을 테스트로 고정한다(AC-143.7).
- `orchestrator/pipeline.py:2111` 루프는 `prepared.asset_paths`에 더해 `prepared.companion_paths`를 스테이징 목록에 합류시킨다. 롤백 스냅샷 정책은 기존 시각 자산과 동일하게 취급(u137 이미지 스토어 예외와 무관).

### #4 — Raw-GitHub 폴백: 저비용 완화 채택, 실패 시 원안 트레이드오프로 강하

투자 보고서는 "raw-GitHub에서 light+dark가 세로로 쌓이는 것"을 수용 대상으로 기록했다. **더 싼 완화가 존재한다**: Material 내장 CSS는 `#only-light`/`#only-dark`와 `#gh-light-mode-only`/`#gh-dark-mode-only`를 **동일 규칙에서 함께** 매칭한다(Verified Facts 참조). 따라서 후자를 방출하면

- **mkdocs 사이트**: `#only-*`와 완전 동일하게 동작한다(같은 셀렉터 목록, 같은 `display:none`). 순수 markdown, `mkdocs.yml` 0줄 변경 — 비준된 메커니즘 그대로.
- **raw GitHub**: GitHub의 레거시 fragment 규약과 철자가 일치하므로, GitHub가 이를 아직 존중하면 한 장만 보인다.

GitHub는 이 문법을 `<picture>` 권장으로 **deprecate**했고 현재 렌더러에서의 동작은 이 계획서 작성 시점에 미검증이다. 따라서:

- 채택 근거는 **downside가 0**이라는 점이다. GitHub가 무시하면 두 장이 쌓이고, 그것은 사용자가 비준한 수용 트레이드오프와 정확히 동일한 상태다. 사이트 동작은 어느 쪽이든 불변.
- Step 6에서 실제 push된 아카이브 파일 1개를 github.com에서 육안 확인하고 결과를 이 계획서 하단 + `docs/DESIGN.md`에 기록한다.
- **수용 명문화**: GitHub가 무시하는 것으로 확인되면 "아카이브 `.md`의 raw-GitHub 렌더에서 카드가 light/dark 두 장으로 쌓인다"를 영구 수용 트레이드오프로 DESIGN.md에 남긴다. raw-GitHub는 폴백 표면이고 정본 독자 표면은 Pages다.
- 철자를 `#only-light`/`#only-dark`로 되돌리길 원하면 `visuals/paths.py` 상수 2개만 바꾸면 된다(Fixed Contract #2의 단일 등록처).

### #5 — 저장/프로비넌스 영향

- **다크 트윈은 자체 `.json` 사이드카를 발급받지 않는다.** 근거: (a) 프로비넌스는 *논리적 자산* 단위 계약이며 다크 트윈은 동일 생성기·동일 버전·동일 치수의 **렌더링 변종**이다, (b) `_provenance_caption_for`는 주 자산 매니페스트만 읽으므로 두 번째 매니페스트는 영구 미독출 파일이 된다, (c) 매니페스트 수를 평탄하게 유지해 저장/커밋 diff 증가분을 절반으로 줄인다.
- 대신 주 매니페스트 `additional_metadata`에 `theme_variant="light"`, `dark_variant="{kind}-dark.svg"`를 기록한다(STRICT 리댁션 무손실 통과).
- 다크 트윈 검증은 `validate_visual_binary(path)`(u86 선례 — 사이드카 비요구 게이트). `validate_visual_asset`을 쓰지 않는다.
- **예산 게이트 대조**: u137의 파일당 2MB / 총 50MB 예산은 `scripts/check_image_store.py`가 `assets/images/` 트리에만 적용한다(AC-137.5). 카드 SVG는 `archive/**/*.assets/`에 있어 **어떤 저장 예산 게이트에도 걸리지 않는다**. 리포 전체 크기 게이트는 존재하지 않음(2026-07-19 확인). 따라서 예산 위반 리스크 없음.
- **정량 영향**: 세그먼트/일당 SVG 카드 3-4장 → 다크 트윈 3-4장 추가. 매니페스트 수 불변. Step 0에서 실제 `.assets` 디렉터리로 바이트 실측하고 "일/월/연 증가분"을 계획서에 기록한다. SVG는 gzip 친화적 텍스트이고 다크 트윈은 light와 색 선언만 다르므로 git 압축 효율이 높다.
- 브라우저는 `display:none` 대상도 fetch할 수 있다 — 페이지당 SVG 요청 수가 최대 2배가 될 수 있음을 DESIGN.md에 명시(자산 크기가 KB 단위라 실질 영향 미미, u75 모바일 성능 계약과 무관).

### #6 — DEBT-061 커버리지 (인라인 표면)

- `calendar_heatmap.py::_HEATMAP_STYLE`과 `quality_sparkline.py`(현재 `_CARD_STYLE` 재사용)는 **인라인 `<svg>`**이므로 dual-variant가 아니라 **`site-scoped` variant**로 전환한다: light 선언 + `[data-md-color-scheme="slate"] …` 오버라이드. 특이도 (0,2,0) > (0,1,0)이므로 확정적으로 이긴다. **파일 증가 0, 마크다운 형태 변화 0.**
- 히트맵은 `_HEATMAP_STYLE`을 같은 팩토리 형태(`_HEATMAP_PALETTE` 테이블 + `build_heatmap_style(variant)`)로 맞춰, 카드 쪽과 동일한 "팔레트 테이블 1개 → variant 렌더러" 구조를 갖는다.
- 스파크라인은 `_CARD_STYLE` import를 `build_card_style("site-scoped")`로 바꾼다.
- 이로써 DEBT-049(=`<img>` 카드)와 DEBT-061(=인라인 히트맵)이 **같은 단위에서 동시에 닫힌다**. 두 debt 모두 Step 6에서 Resolved 처리한다.

## Implementation Steps

### Step 0 — 기준선 실측 + Material CSS 규약 검증 `[ ]`
- [ ] 실제 `archive/{segment}/{YYYY}/{MM}/{date}.assets/` 1개 디렉터리에서 SVG 파일 수·바이트·매니페스트 바이트를 실측하고 일/월/연 증가분을 계획서 하단 "Measured Baseline" 절에 기록.
- [ ] 빌드 산출 CSS(`site/assets/stylesheets/palette.*.min.css`, `main.*.min.css`)에서 4개 셀렉터(`#only-light`, `#only-dark`, `#gh-light-mode-only`, `#gh-dark-mode-only`)의 존재를 확인하고 정확한 규칙 문자열을 기록.
- [ ] 현재 `_CARD_STYLE` 문자열을 테스트 픽스처로 스냅샷(Step 1의 바이트 동일성 기준선).
- **Acceptance**: 4개 셀렉터 전부 확인됨. 증가분 수치가 문서에 기록됨. `mkdocs.yml`은 손대지 않음이 확인됨.

### Step 1 — 스타일 팩토리 (`render.py`) `[ ]`
- [ ] `_CARD_PALETTE` 테이블 + `CardStyleVariant` + `build_card_style(variant)` 도입 (Contract #1). 색 hex 값 변경 금지.
- [ ] `_CARD_STYLE = build_card_style("auto")` 별칭 유지.
- [ ] `render_card_svg(card, *, variant="light")` / `_svg_document(..., variant)` 배선.
- [ ] 테스트: `build_card_style("auto")`가 Step 0 스냅샷과 **바이트 동일**; `light`/`dark`에 `@media` 부재; `light` != `dark`; `site-scoped`에 `[data-md-color-scheme="slate"]` 포함 및 `@media` 부재; 8개 클래스가 4개 variant 전부에서 정확히 1회씩 정의됨.
- [ ] 테스트(초크포인트 핀): `typing.get_args(_RenderableCard)` registry-driven 파라미터라이즈로 각 카드 입력 클래스가 두 variant를 산출함을 단언 (Contract #1).
- **Acceptance**: `auto` 바이트 동일성 통과 → `og_card`/인라인 표면/기존 골든이 이 단계에서 churn 0. 카드 SVG 산출은 variant 기본값(`light`) 때문에 아직 바뀌지 않음(다음 스텝에서 쌍 방출).

### Step 2 — 이중 산출 + 프로비넌스 정책 (`assets.py`) `[ ]`
- [ ] `prepare_segment_visual_assets`의 카드 루프를 쌍 방출기로 교체: light `{kind}.svg` + dark `{kind}-dark.svg` 작성.
- [ ] 주 자산: 기존대로 `_write_generated_svg_manifest` + `validate_visual_asset`. 매니페스트 `additional_metadata`에 `theme_variant` / `dark_variant` 추가 (Contract #5).
- [ ] 다크 트윈: 사이드카 미발급 + `validate_visual_binary`로 검증 (Contract #5).
- [ ] `PreparedVisualAssets.companion_paths` 추가; `asset_paths` 멤버십/순서 불변 (Contract #3).
- [ ] 테스트: 4종 카드 각각 두 파일 존재 / 다크 파일에 `.json` 사이드카 부재 / 주 매니페스트에 두 키 존재 / `asset_paths` 길이·순서가 pre-u143과 동일 / 다크 SVG가 `_validate_svg_asset` 치수·텍스트 요건 통과.
- **Acceptance**: 디스크에 쌍이 떨어지고, `asset_paths` 기반 히어로 선택·앵커 배치 테스트가 **무수정으로** 그린 유지.

### Step 3 — markdown fragment 쌍 방출 `[ ]`
- [ ] `visuals/paths.py`에 `LIGHT_ONLY_FRAGMENT` / `DARK_ONLY_FRAGMENT` 상수 단일 등록 (Contract #4 철자).
- [ ] `insert_visual_links(..., dark_variants: Mapping[Path, Path] = {})` + `_visual_block`이 쌍 + 단일 캡션을 방출 (Contract #2).
- [ ] PNG/JPEG 히어로는 fragment 없는 단일 링크 유지.
- [ ] 테스트: 쌍 형태 정확 일치 / 캡션 1회 / 멱등성(2회 호출 = 입력 동일) / PNG 히어로 무-fragment / **`#`가 어떤 `Path`·`asset_paths`·`companion_paths`·매니페스트 `asset_path`에도 없음**(AC-143.5) / 빈 기본 매핑이 pre-u143 단일 링크와 바이트 동일.
- [ ] 기존 단일 링크 단언(`tests/unit/visuals/test_assets.py:95,147`)을 **쌍 형태로 갱신**(삭제·완화 금지).
- **Acceptance**: 렌더된 markdown이 카드마다 정확히 2개의 `<img>` 라인 + 1개 캡션을 갖고, fragment는 문자열 계층에만 존재.

### Step 4 — 오케스트레이터 스테이징 + 카운트 단언 정정 `[ ]`
- [ ] `pipeline.py:2111` 루프에 `companion_paths` 합류(스테이징 대상 포함, 매니페스트 경로 부여는 주 자산에만).
- [ ] `stage_notes["visual_assets"] = f"ok: {n} files"`의 새 값 산정: 현재 18(3 세그먼트 × 3 카드 × [svg+manifest]) → 다크 트윈 합류로 3 × 3 × [light svg + dark svg + manifest] = **27 예상**. 실제 값은 실행으로 확정하고 `tests/integration/test_pipeline.py:256`을 그 값으로 갱신.
- [ ] 테스트: `tests/unit/orchestrator/test_run_pipeline.py:762-764` 단언을 fragment 쌍 형태로 갱신; L831의 `![` 라인 스캔 로직이 쌍을 정상 처리하는지 확인.
- **Acceptance**: 통합 파이프라인이 3세그먼트 그린으로 완주하고, 다크 트윈이 git add 대상에 포함되며, 카운트 노트가 실제 파일 수와 일치.

### Step 5 — DEBT-061: 히트맵 + 스파크라인 조상 셀렉터 전환 `[ ]`
- [ ] `calendar_heatmap.py`: `_HEATMAP_PALETTE` 테이블 + `build_heatmap_style(variant)`; 산출은 `site-scoped`. 모듈 docstring의 DEBT-049 수용 문단을 새 사실로 교체.
- [ ] `quality_sparkline.py`: `_CARD_STYLE` import → `build_card_style("site-scoped")`.
- [ ] `render.py` `_CARD_STYLE` 별칭의 잔여 사용처 정리(남으면 `og_card` 계열 주석으로 이유 명시).
- [ ] 테스트: `tests/unit/visuals/test_calendar_heatmap.py:53`의 `@media (prefers-color-scheme: dark)` 단언을 `[data-md-color-scheme="slate"]` 단언으로 **갱신**(약화 아님 — 토글 추종을 더 강하게 고정); 스파크라인 동일 단언 추가.
- [ ] `archive/index.md` / `site_docs/quality.md`의 인라인 SVG는 다음 발행 시 자동 갱신 — 재생성 경로가 새 스타일을 쓰는지 게이트에서 확인.
- **Acceptance**: 두 인라인 표면의 `<style>`이 사이트 토글 속성으로 구동되고 `@media`가 사라짐. 파일 수 증가 0.

### Step 6 — 골든/테스트 churn 정리 + 게이트 + 문서/부채 종결 `[ ]`
- [ ] 잔여 골든 마크다운·스냅샷·파일 카운트 단언 일괄 갱신(`test_briefing_replay.py`, `test_git_ops.py` 등 `.assets/` 참조 테스트 스윕).
- [ ] full gate: ruff / ruff format(변경 범위) / mypy --strict / pytest / `scripts/check_no_paid_apis.py` / `scripts/check_image_store.py` / `mkdocs build --strict`(clean tree).
- [ ] 실제 push된 아카이브 `.md` 1개를 github.com raw 렌더에서 육안 확인 → 결과를 Contract #4에 따라 기록.
- [ ] `docs/DESIGN.md`에 "테마 패리티 계약" 절 추가: dual-variant 규약, fragment 철자, 사이드카 정책, raw-GitHub 트레이드오프, 인라인 표면의 조상 셀렉터 예외.
- [ ] `docs/TECH-DEBT.md`: DEBT-049 / DEBT-061을 `## Resolved Items`로 이동 + `**Resolved**: 2026-07-19 — …` 라인.
- [ ] `aidlc-docs/aidlc-state.md` u143 행 갱신, `code/summary.md` 작성.
- **Acceptance**: 전 게이트 그린(사전 존재 DEBT-081 쌍 제외). 두 부채 종결. 신규 외부 호출 0.

## Acceptance Criteria (unit-level)

- **AC-143.1 (양쪽 토글 상태 패리티)**: 모든 SVG 카드 종류에 대해, 사이트 토글 light 상태에서는 light 자산이, dark 상태에서는 dark 자산이 표시된다 — OS `prefers-color-scheme`과 무관하게. 실행 가능 형태로 고정: (a) 빌드된 HTML에 두 `<img>`가 정확한 fragment 접미로 존재, (b) 빌드된 Material CSS에 각 variant를 숨기는 두 규칙이 존재(Material 업그레이드가 규약을 없애면 실패).
- **AC-143.2 (OS 폴백)**: JS 비활성/저장된 선호 없음 상태에서 `<body data-md-color-scheme="default">`가 서버 렌더되어 페이지=light, 카드=light로 일치한다. JS 활성 시 Material이 `prefers-color-scheme`로 팔레트를 확정하고 카드가 이를 따른다. **어떤 상태에서도 카드가 반대 배경 위에 놓이지 않는다** — 오늘 대비 순개선.
- **AC-143.3 (초크포인트)**: 신규 카드 타입은 추가 작업 없이 두 variant를 상속하며, `_RenderableCard` 유니온 기반 registry-driven 테스트가 배선 누락 시 실패한다.
- **AC-143.4 (비침습)**: `build_card_style("auto")`가 pre-u143 `_CARD_STYLE`과 바이트 동일하여, 의도적으로 전환하지 않은 표면(OG 카드)은 산출물이 변하지 않는다.
- **AC-143.5 (fragment 격리)**: URL fragment는 fetch/검증/스테이징 경로에 도달하지 않는다 — 어떤 `Path`·매니페스트 `asset_path`·git 인자에도 `#`가 없다.
- **AC-143.6 (DEBT-061)**: 캘린더 히트맵과 품질 스파크라인이 사이트 토글 속성으로 구동되며(`@media` 제거), 자산 파일 수는 증가하지 않는다.
- **AC-143.7 (테스트 강화, 약화 금지)**: 기존 단일 variant 단언은 쌍 형태로 **갱신**된다(삭제·주석·완화 금지). `dark_variants` 빈 기본값 분기는 프로덕션에서 도달 불가함이 테스트로 고정된다.

## Tests / Validation

- `tests/unit/visuals/test_render.py` — 스타일 팩토리 매트릭스(4 variant × 8 클래스), `auto` 바이트 동일성, registry-driven 카드 유니온 핀.
- `tests/unit/visuals/test_assets.py` — 쌍 산출, 사이드카 정책, `asset_paths` 불변, fragment 쌍 markdown, `#` 격리, 멱등성, PNG 히어로 무-fragment (L95/L147/L219/L289/L340 갱신).
- `tests/unit/visuals/test_calendar_heatmap.py` — L53 단언 전환 + 조상 셀렉터 핀.
- `tests/unit/visuals/test_provenance.py` — `theme_variant` / `dark_variant` 키 왕복.
- `tests/unit/orchestrator/test_run_pipeline.py` — L762-764 쌍 형태, L831 스캔 로직.
- `tests/integration/test_pipeline.py` — L256 `"ok: N files"` 실측값 갱신.
- `tests/unit/publisher/test_briefing_replay.py` / `test_git_ops.py` — `.assets/` 참조 골든 스윕.
- 신규: 빌드 산출 Material CSS에 4개 fragment 규칙이 존재함을 확인하는 가드 테스트(AC-143.1(b)).

## Deferred (this unit이 만들지 않는 것)

- **기존 아카이브 백필** — pre-u143 커밋된 `.md`는 단일 링크 그대로 남는다(다크 트윈 파일 자체가 없음). 사이트 토글 불일치가 과거 발행분에 잔존. DEBT-077(레거시 차트 사이드카 백필)과 동일 성격이며, 필요 시 `scripts/backfill_2026_05_06_visuals.py` 패턴의 일회성 워크로 별도 처리.
- **`og_card.py::_OG_STYLE`의 팩토리 통합** — 색 테이블이 사실상 동일(`og-*` vs `card-*` 접두만 다름)하므로 중복 제거 여지가 있으나, OG 표면은 Material CSS가 없는 외부 소비자용이라 variant 개념이 적용되지 않는다. 순수 중복 제거 항목으로 TECH-DEBT 등록 검토.
- **색 대비/접근성 튜닝** — 이번 단위는 기존 hex 값 재배치만 한다. WCAG 대비비 검토는 별도.
- **`<picture>` 기반 raw-GitHub 정식 지원** — raw HTML을 markdown 본문에 넣으면 게시 게이트(leak_guard / compliance-language / reader-format 체인)가 SVG/HTML 내부를 처리하게 되어 blast radius가 커진다(투자 보고서 option (b) 기각 사유 (3)과 동일). 순수 markdown 유지가 이 단위의 전제.
- **다크 트윈 개별 사이드카** — Contract #5에서 명시적으로 기각. 프로비넌스 소비자가 렌더링 변종 단위 추적을 요구하게 되면 재검토.
- **브라우저 이중 fetch 최적화** — `display:none` 대상도 fetch될 수 있는 점. 자산이 KB 단위라 현 시점 비용 무시 가능.

## How to Approve

1. **Request Changes** — 계약/스텝/AC 수정 요청
2. **Continue to Next Stage** — Step 0 착수 승인
