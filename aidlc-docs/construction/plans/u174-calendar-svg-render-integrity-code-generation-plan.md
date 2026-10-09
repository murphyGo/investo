# Code Generation Plan: `u174 calendar-svg-render-integrity`

- **Date**: 2026-10-10
- **Unit**: u174 calendar-svg-render-integrity
- **Stage**: Code Generation
- **Status**: Planned — 0/6; 문서화만 승인됨, 구현 시작 전
- **Source**: 2026-10-10 공개 Investo UI 점검 및 사용자 “일단 유닛 문서화부터” 요청
- **Estimated Effort**: ~4–6 h
- **Priority**: P0 — 기존 발행 캘린더 표시 결함 복구
- **Dependencies**: u29 site-discovery-v2, u82 site-index split, u143 visual-theme-parity-dual-variant, u154 canonical-preamble-block-assembly. 모두 기존 계약 재사용; u175 및 홈 제품 디자인 승인과 독립적으로 구현 가능.

기획 맥락과 기준선은 [UI 개선 묶음](../ui-modernization-20261010/README.md), [브라우저 관측 JSON](../ui-modernization-20261010/evidence/focused-findings.json), [캘린더 화면](../ui-modernization-20261010/evidence/archive-desktop-light-viewport.png)에 보관한다.

## Problem Statement

발행 캘린더 데이터와 SVG 문자열은 존재하지만 실제 Pages 화면에 색상 셀이 나타나지 않는다. 현재 `publisher/site_index/archive_sections.py::_render_heatmap_block()`은 `<figure class="u29-heatmap" markdown="1">` 안에 raw SVG를 넣는다. u154의 닫힌 숫자 패널을 렌더하기 위해 `mkdocs.yml`에 등록된 `md_in_html`은 이 figure 내부까지 Markdown으로 해석한다. 결과적으로 SVG가 `<p><svg …></svg></p>`로 분리되고, 셀은 SVG 밖 HTML 요소가 된다. SVG 팔레트를 다시 바꾸거나 CSS를 조정하는 것으로는 복구되지 않는다.

2026-10-10 공개 `/investo/archive/` 브라우저 관측값:

- `.u29-heatmap svg`의 자식 수 **0**, 내부 `rect` 수 **0**.
- figure 전체에는 `rect` **160**개가 있으나 namespace는 `http://www.w3.org/1999/xhtml`, 첫 rect 부모는 `P`다.
- SVG shell 자체는 `width="435" height="165" viewBox="0 0 435 165"`와 캘린더 aria-label을 유지한다.
- 현재 `archive/index.md`에도 figure의 `markdown="1"`, 완전한 SVG/style/text/rect/legend가 들어 있다. 이 아카이브 파일은 `site_docs/archive` symlink를 통해 MkDocs로 빌드된다.

관측 수치는 결함의 기준선이다. 테스트 기대값을 160으로 영구 고정하지 않고 fixture 또는 실제 입력의 셀/범례 수와 출력 수를 비교한다. 문서 외부 임시 파일이 없어도 위 증거와 아래 코드 위치로 재현할 수 있어야 한다.

## Goal

실제 MkDocs 확장셋을 유지한 채 캘린더 figure만 raw SVG로 보존한다. 이후 발행분뿐 아니라 **이미 커밋된 `archive/index.md`도 다음 사이트 빌드에서 복구**한다. SVG 셀·텍스트·스타일이 하나의 SVG subtree와 SVG namespace에 남고, 기존 Material 사이트 토글을 그대로 따른다.

## Existing Coverage / Deduplication

| 기존 소유자 | 재사용하는 계약 | 이번 유닛에서 보강하는 부분 |
| --- | --- | --- |
| u29 / `visuals/calendar_heatmap.py` | coverage → 결정적 SVG, 날짜·정상/부분/부족/미발행·tooltip·범례 | 데이터·그리드 생성은 그대로 두고 HTML 렌더 경계만 복구 |
| u82 / `publisher/site_index/archive_sections.py` | `HEATMAP_BEGIN`/`HEATMAP_END` marker replacement와 기존 facade | 신규 발행용 figure를 raw로 명시 |
| u143 / DESIGN TD-013 | 인라인 SVG의 base light + `[data-md-color-scheme="slate"]` 조상 스타일; 파일 증가 0 | 빌드 후에도 해당 SVG subtree가 살아 있음을 검증 |
| u154 | `md_in_html`로 `details.investo-market-data` 안의 표·링크 렌더 | 확장 제거 또는 전역 차단 없이 함께 동작하도록 보호 |

DEBT-061의 u143 해결을 되돌리거나 새 캘린더 기능을 등록하지 않는다. u143은 테마 선택, u174은 SVG가 Markdown/HTML 변환 과정에서 분해되는 결함을 소유한다.

## Scope Boundary

In scope:

- `src/investo/publisher/site_index/archive_sections.py`의 figure raw 처리 선언.
- 신규 `scripts/mkdocs_render_hooks.py`의 좁은 `on_page_markdown` adapter 및 순수 캘린더 wrapper 정규화 함수.
- `mkdocs.yml`의 해당 hook 등록. 확장셋·순서·Material palette는 유지한다.
- 기존 archive를 재발행하지 않아도 적용되는 build-time 정규화, 실제 built HTML 회귀 검사.
- `.github/workflows/pages.yml`의 hook/guard 경로 trigger와 build 후 guard, `.github/workflows/quality.yml`의 같은 guard 연결.
- 관련 publisher/visuals/integration 테스트, DESIGN의 렌더 경계 보충, 완료 시 state/summary.

Out of scope:

- 시황 Markdown·숫자·요약·seal·출처·coverage 정책 및 데이터 모델 변경.
- 기존 `archive/**.md` 또는 visual 자산의 일괄 재작성, 임의 발행 재생성.
- 캘린더 날짜 필터·새 링크·tooltip 기능 추가, SVG를 이미지 파일로 교체.
- 품질 sparkline/외부 SVG 카드/OG 스타일 전반 리팩터링; 결함이 별도로 입증되면 독립 범위로 판단한다.
- 홈·메뉴·아카이브 목록 디자인 변경, 배포/활성화 자동 수행.

## Stage Decision

- **Functional Design — SKIP**. u29에서 승인된 동일 발행 캘린더의 표시를 복구한다. 날짜 범위·상태 의미·탐색·사용자 행동·접근성 정보에 새 제품 결정이 없다. build hook은 기존 문서의 HTML 해석 방식을 수정하는 기술 소유자다.
- **NFR Requirements / Design — SKIP**. FR-003, NFR-005/006, u143 TD-013 및 u154 실제-config 렌더 계약을 재사용한다. 새로운 네트워크·키·서비스·런타임 의존성·비용이 없으며, docs-only hook은 daily runtime에 들어가지 않는다. 테스트 목적으로 XML을 파싱하면 기존 R6에 따라 `defusedxml`을 사용한다.
- **Code Generation — READY**. 아래 소유자와 AC에 제품 선택의 미결정 사항은 없다. 현재 요청은 문서만이므로 모든 구현 체크박스는 미완료로 남긴다.

## Fixed Contracts

1. **Canonical renderer/compatibility owner**: SVG 문자열 생성은 계속 `visuals/calendar_heatmap.py`, 발행용 wrapper는 `publisher/site_index/archive_sections.py::_render_heatmap_block`, 사이트의 기존-input 호환은 **`scripts/mkdocs_render_hooks.py`**가 소유한다. publisher가 MkDocs를 import하거나 build subprocess를 호출하지 않는다(DESIGN TD-006).
2. **Raw island**: 신규 wrapper는 `markdown="0"`로 명시한다. MkDocs hook의 `preserve_calendar_svg_markdown(markdown: str) -> str`은 `HEATMAP_BEGIN`/`HEATMAP_END` 사이의 완전한 `figure.u29-heatmap`에서만 `markdown="1"`을 `markdown="0"`으로 정규화한다. SVG/style/rect/text/title, figure class, figcaption, marker 내부 다른 텍스트와 바깥 문서는 변경하지 않는다. 이미 raw인 블록·캘린더가 없는 페이지는 byte-identical no-op; 재적용도 동일 결과다. fenced code 예시나 다른 figure/details의 attribute는 수정하지 않는다.
3. **Site-only adapter**: `on_page_markdown(markdown, *, page, config, files)`은 `page.file.src_uri == "archive/index.md"`에만 위 정규화를 적용한다. commit된 Markdown을 디스크에 쓰지 않는다. 알려진 불완전 블록·unknown HTML·중복/깨진 marker는 내용을 추정하거나 SVG를 재구성하지 않고 no-op으로 남긴다. guard가 실제 렌더 실패를 검출한다. fenced block 밖의 유효 marker pair와 하나의 완전한 known figure/SVG가 확인될 때만 변환한다.
4. **Existing archive recovery**: 현행 `archive/index.md`의 `markdown="1"`을 파일 편집 없이 빌드해도 캘린더가 복구되어야 한다. emitter 수정만 구현하거나 다음 daily publish까지 기다리는 방식은 완료가 아니다.
5. **u154 and u143 preservation**: `md_in_html`, `pymdownx.details`, 현재 extension options/order를 보존한다. 숫자 패널은 닫혀 있고 표·링크가 파싱된다. `#gh-light-mode-only`/`#gh-dark-mode-only` 이미지 쌍·단일 캡션, Material CSS guard, 인라인 캘린더 site-scoped 팔레트 모두 그대로다.
6. **Built output invariant**: 실제 `site/archive/index.html`의 figure 안에 SVG 하나, SVG 안에 기대한 셀·범례 rect와 텍스트가 존재한다. `<p>` wrapper 때문에 SVG 내용이 밖으로 나가면 실패다. HTMLParser 구조 검사만으로 namespace를 증명했다고 기록하지 않고, 실제 브라우저 DOM에서 rect/text/style가 SVG subtree 및 `http://www.w3.org/2000/svg`에 속하는지 확인한다.
7. **Durable build guard**: 신규 `scripts/check_calendar_render_contract.py`는 기본 `site/` 및 CLI `--site-dir`에서 실제 built archive index의 SVG containment/비어 있지 않은 필수 내용을 검사한다. 결함 재현 HTML 또는 빈 SVG는 nonzero, 정상 fixture는 zero다. Pages/Quality는 strict build 뒤 이 guard를 실행하고, Pages path filter에는 hook과 guard의 정확한 파일 경로를 추가한다. 새 일반 플러그인 패키지나 외부 parser 의존성을 만들지 않는다.

## Implementation Steps

### Step 1 — 실제-config 결함과 호환 요구 고정 `[ ]`

- [ ] 현행 archive marker block 및 normal/partial/insufficient/absent/empty fixture를 확보한다. `mkdocs.yml`에서 확장과 options를 읽어 기존 u154 integration 방식으로 동일 변환을 실행한다.
- [ ] emitter만 바꾸면 이미 커밋된 아카이브가 남는 실패, `md_in_html` 제거 시 u154가 깨지는 실패를 회귀 조건으로 명시한다. 현재 테스트는 raw SVG 문자열만 검사하는 한계가 있음을 기록한다.

### Step 2 — Wrapper와 사이트 build hook 구현 `[ ]`

- [ ] renderer를 변경하지 않고 `_render_heatmap_block`에 raw 선언을 적용한다.
- [ ] Fixed Contracts의 canonical hook/순수 정규화를 구현·등록한다. legacy attribute/이미 정규화/무관 페이지/다른 details/fenced code/불완전 block/no-marker 분기를 확인한다.
- [ ] 입력 Markdown의 변경 범위는 알려진 opening figure attribute 하나이며 디스크 write가 없음을 고정한다.

### Step 3 — 기존 archive와 u154/u143 동시 렌더 회귀 `[ ]`

- [ ] 신규 `tests/integration/test_calendar_svg_html_u174.py`에서 **현재 확장셋과 hook**을 포함한 isolated MkDocs build를 수행한다. legacy fixture와 신규 emitter fixture 모두 보존되는 SVG subtree 및 source-derived rect 수를 검사한다.
- [ ] `tests/integration/test_canonical_preamble_html_u154.py`와 기존 Material theme contract를 함께 검증한다. 기존 preamble test의 확장셋을 간소화하여 통과시키지 않는다.

### Step 4 — Built-site guard와 CI 연결 `[ ]`

- [ ] 신규 guard와 `tests/unit/visuals/test_check_calendar_render_contract.py`의 정상/빈 SVG/분리 rect/누락 figure 실패 케이스를 구현한다.
- [ ] Pages/Quality strict build 뒤 실행한다. hook/guard만 변경되는 후속 commit도 Pages path filter를 통과해야 한다.

### Step 5 — 실제 DOM과 화면 검증 `[ ]`

- [ ] 실제 `mkdocs build --strict` 산출물을 로컬 정적 서버로 열고 1440×1000 및 390×844에서 light/dark 각각 확인한다.
- [ ] 브라우저 DOM에서 셀·범례 namespace/containment, nonempty SVG bounds, caption 1개와 실제 테마 토글 후 fill 변화를 기록한다. 모든 상태 샘플과 empty fixture를 확인한다.
- [ ] 캘린더 자체의 horizontal scrolling은 기존 CSS를 유지하고, 페이지 전체의 가로 overflow를 만들지 않는지 확인한다. 사용한 도구·URL·viewport를 증거에 명시한다.

### Step 6 — 검증·리뷰·문서 종결 `[ ]`

- [ ] 아래 targeted/full gate 및 독립 리뷰·요구사항 cross-check를 완료한다. 실제 브라우저 확인을 실행하지 않았다면 AC-174.5를 미완료로 둔다.
- [ ] DESIGN TD-013에 raw island/build owner를 추가하고 unit summary/state를 evidence와 함께 갱신한다. 변경된 tracked archive 파일이 없는지 확인한다. 커밋·푸시·공개 배포는 구현 시의 별도 사용자 지시 범위에서 처리한다.

## Acceptance Criteria

- **AC-174.1 — 실제 렌더 복구**: legacy `markdown="1"` fixture와 신규 emitter 출력이 실제 MkDocs 확장셋/hook을 거친 built HTML에서 SVG 하나의 완전한 subtree를 이룬다. 기대 셀·범례 rect 수는 원본과 같고, SVG 밖의 캘린더 rect는 0개다.
- **AC-174.2 — 기존 archive 무수정**: 현재 committed `archive/index.md` bytes가 변하지 않은 상태로 strict build와 built-site guard가 통과한다. 다음 daily 발행이나 historical Markdown rewrite가 필요하지 않다.
- **AC-174.3 — 범위/멱등성**: 캘린더 없는 페이지·fenced example·다른 figure·u154 details는 byte-identical이고, 정규화 2회 결과는 1회와 같다. caption·aria-label·title·palette·범례·coverage mapping은 보존된다.
- **AC-174.4 — 기존 계약 보호**: u154 closed numeric panel의 표·링크와 visible TLDR 3항목, u143 fragment 쌍/Material CSS/site-scoped 팔레트가 기존 gate를 통과한다. md_in_html 전역 삭제나 CSS-only 은폐로 해결하지 않는다.
- **AC-174.5 — 브라우저 증거**: built archive page의 SVG rect/text/style namespace가 SVG이고 셀이 화면에 표시된다. desktop/mobile, 초기 light/dark 및 양방향 toggle에서 색상·텍스트가 페이지 scheme을 따른다. empty fixture도 문구가 보인다.
- **AC-174.6 — 지속 가드**: 실제 broken built HTML은 guard nonzero, 정상 output은 zero이며 Pages/Quality의 strict build 뒤 실행된다. hook/guard 단독 변경 시 Pages rebuild 경로가 포함된다. archive bytes, daily runtime dependency, asset/manifest 수 증분은 0이다.

## Tests / Validation

구현 단계에서 실행할 명령이며 이번 문서화에서는 실행하지 않는다. 신규 파일명은 위 implementation에서 만들 대상이다.

- **신규 예정**: `tests/integration/test_calendar_svg_html_u174.py`, `tests/unit/visuals/test_check_calendar_render_contract.py` 및 Step 2/4의 hook/guard. 아래 명령의 나머지 test 경로는 현재 존재한다.

```bash
uv sync --extra dev --extra docs --extra sector
uv run python -m pytest tests/unit/publisher/test_site_index.py tests/unit/visuals/test_calendar_heatmap.py tests/unit/visuals/test_check_material_theme_contract.py tests/unit/visuals/test_check_calendar_render_contract.py tests/integration/test_calendar_svg_html_u174.py tests/integration/test_canonical_preamble_html_u154.py
uv run ruff check src/investo/publisher/site_index/archive_sections.py scripts/mkdocs_render_hooks.py scripts/check_calendar_render_contract.py tests/integration/test_calendar_svg_html_u174.py tests/unit/visuals/test_check_calendar_render_contract.py
uv run ruff format --check src/investo/publisher/site_index/archive_sections.py scripts/mkdocs_render_hooks.py scripts/check_calendar_render_contract.py tests/integration/test_calendar_svg_html_u174.py tests/unit/visuals/test_check_calendar_render_contract.py
uv run mypy --strict src/investo/publisher/site_index/archive_sections.py
uv run mkdocs build --strict
uv run python scripts/check_calendar_render_contract.py
uv run python scripts/check_material_theme_contract.py
uv run python -m pytest
git diff --check
git diff --exit-code -- archive
```

추가 화면 검증은 Step 5의 실제 브라우저 관측을 evidence에 남긴다. `HTMLParser`/문자열 확인이나 strict build 성공만으로 SVG namespace·실제 표시 검증을 대체하지 않는다.

## Non-Goals

새 UI 제품 설계, grid/색상 의미 변경, 아카이브 백필, dual SVG 자산 재생성, numeric seal/최종문서 변경, 공급자 추가, 새 데이터 요청, 운영 배포는 수행하지 않는다. 품질 sparkline이나 관심 자산 그래프의 새로운 레이아웃은 별도 unit 경계다.
