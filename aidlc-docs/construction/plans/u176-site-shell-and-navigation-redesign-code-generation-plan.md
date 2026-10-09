# Code Generation Plan: u176 site-shell-and-navigation-redesign

- **Date**: 2026-10-10
- **Unit**: u176 site-shell-and-navigation-redesign
- **Stage**: Documentation / design queue registration
- **Status**: Functional Design REQUIRED / PENDING; focused NFR Requirements REQUIRED / PENDING; Code Generation NOT STARTED
- **Source**: [2026-10-10 UI 분석·증거·유닛 개요](../ui-modernization-20261010/README.md)와 사용자의 “굿 일단 유닛 문서화부터 진행해줘” 요청
- **Priority**: P1
- **Estimated Effort**: Functional Design/NFR 3–5h, 승인 후 구현·관측 검증 6–10h. 디자인 검토 대기와 운영 배포 시간 제외.
- **Dependencies**: 완료된 u29/u143의 Material·테마 계약, 최신 main의 u145 미국 섹터 메뉴. u177은 본 유닛의 공통 스타일·홈 클래스 계약에 의존한다. u174/u175 결함 수정과는 독립적으로 설계할 수 있다.

## Problem Statement

현재 사이트는 MkDocs Material의 문서 탐색 구조를 그대로 사용한다. 홈에서도 문서용 좌측 내비게이션과 우측 목차 공간을 고려한 폭을 사용하고, Home/About/Archive라는 영어 메뉴와 한국어 시장·품질 메뉴가 섞여 있다. `site_docs/watchlist/index.md`가 생성·배포되지만 `mkdocs.yml::nav`에 관심 자산 진입점이 없다. 시장 상태를 빨리 확인하려는 독자에게 주요 진입점과 본문 읽기 영역의 우선순위가 명확하지 않다.

현재 `site_docs/assets/u29.css`는 발행 캘린더와 차트 위젯에 대한 작은 스타일 집합이며, 공통 색·간격·글자 크기와 홈/본문 폭을 표현하는 Investo UI 계약이 없다. 세련된 화면으로 바꾸려면 홈의 카드 표현과 사이트 공통 셸의 역할을 나누고, 작은 화면의 실제 탐색·검색·테마 전환 동작까지 설계해야 한다.

## Goal

MkDocs Material과 기존 URL을 유지하면서 한국어 주요 메뉴, 관심 자산 접근, 검색·테마 전환, 일관된 색·간격·타이포를 갖춘 공통 셸을 만든다. 홈은 시장별 카드에 필요한 넓은 영역을 확보하고, 시황 본문은 읽기 편한 폭과 목차를 유지한다. 모바일·키보드·라이트/다크에서 같은 기능에 접근할 수 있어야 한다.

## Current Evidence

### 현재 버전과 동시 등록된 v3 설계

최초 코드 기준은 48762793, 최종 문서 기준은 838bed60이다. 작성 중 등록된 사건·뉴스 v3 u167–u173을 보존해 본 UI 번호는 u176이다. [v3 프로그램](../event-news-v3/README.md)과 u169/u171은 문서의 의미·순서·reader payload를 소유한다. 본 유닛은 두 버전의 공통 shell/CSS/탐색만 제공한다. u154의 legacy 순서/숫자 panel 보존은 v1/v2에 한정하며 v3에 강제3요약·7H2·기본 hero를 요구하지 않는다. 페이지 scope는 실제 page metadata/class로 판단하고 legacy heading 문자열로 v3를 오판하지 않는다. 미래 v3 seam은 아직 구현된 것으로 취급하지 않는다.

2026-10-10 최초 코드 기준 main `48762793`을 기준으로 읽은 근거다. 구현 착수 시 최신 상태를 다시 확인한다.

| 근거 | 현재 동작 / 계획에 주는 제약 |
|---|---|
| `mkdocs.yml` | `theme.name: material`, `language: ko`, `navigation.tabs`, 검색 ko/en, Noto Sans KR, default/slate palette, `extra_css: assets/u29.css`. 기능과 Material 테마 계약을 재사용한다. |
| `mkdocs.yml::nav` | Home, About, **미국 섹터: sectors/index.md**, 데이터 품질, Archive가 존재한다. 관심 자산 메뉴가 없으며 미국 섹터는 최근 u145의 제품 진입점이다. 메뉴 개편으로 제거하거나 숨기지 않는다. |
| `overrides/main.html` | `base.html`을 상속하고 `extrahead`에서 OG PNG/SVG와 Twitter 메타를 방출한다. 셸 변경이 OG 헤더·Material 검색·접근성 기능을 손상하면 안 된다. |
| `site_docs/assets/u29.css` | `.u29-heatmap`, `.investo-chart-*` 스타일이 이미 존재한다. 신규 공통 토큰을 이 기존 컴포넌트에 무조건 덮어쓰지 않는다. |
| `site_docs/watchlist/index.md` | 관심 자산 누적 페이지와 `daily.md` 진입 링크가 이미 있다. 신규 watchlist 생성·매칭 기능이 필요하지 않다. |
| `scripts/check_material_theme_contract.py` / `tests/unit/visuals/test_check_material_theme_contract.py` | built CSS의 default/slate 이미지 숨김 규칙 및 정확한 light/dark 쌍의 built HTML을 검증한다. 셸 색상 변경과 별도로 유지할 기존 게이트다. |
| `docs/DESIGN.md` TD-006/TD-008/TD-010 | Pages 배포와 publisher의 책임 분리, 본문 first viewport 조립, sealed bytes 계약이 있다. 셸은 게시·본문 조립 소유자를 대체하지 않는다. |

[보존한 홈 시안](../ui-modernization-20261010/evidence/home-concept.html)은 밝은 회색 바탕, 진한 제목, 청록색 강조, 얇은 테두리와 모서리가 둥근 카드라는 **디자인 후보**를 보여준다. [1440px/390px 측정](../ui-modernization-20261010/evidence/concept-metrics.json)의 가로 overflow 0 관측은 그 standalone HTML에 대한 결과다. Material 통합·접근성·전체 사이트 성능이 검증되거나 디자인이 승인된 것으로 해석하지 않는다. 이 문서의 텍스트 요구사항이 계약이며 임시 `/private/tmp` 시안 파일의 존재를 납품·검증 조건으로 삼지 않는다. 원 공개 사이트 관측에는 당시 미국 섹터 페이지가 포함되지 않았으므로 새 nav/페이지에 대해 화면 인수를 소급 주장하지 않는다.

## Existing Coverage / Deduplication

- u29: 홈 hero와 About 분리, 시장별 아카이브 진입과 OG를 이미 구현했다. 공통 셸·관심 자산 메뉴·웹용 스타일을 확장한다.
- u63: 미발행/이전 발행 상태는 publisher의 기존 계약이다. 메뉴 스타일이 상태를 결정하거나 미발행을 정상으로 표시하면 안 된다.
- u69/u96: 데이터 품질 값과 일관성 게이트를 소유한다. 신규 UI 등급·품질 추론을 만들지 않는다.
- u143: light/dark 자산 쌍과 Material fragment 규약을 소유한다. 본 유닛은 사이트 CSS와 셸의 테마 적용에 한정한다.
- u144: generated→sealed, consumer view, asset promotion과 게시 트랜잭션을 소유한다. 셸 작업으로 pipeline/finalizer를 바꾸지 않는다.
- u153/u154: 문장 경계 및 시황 H1/TLDR/숫자 패널·뉴스 우선 배치를 이미 구현했다. 본문을 재조립하거나 과거 본문을 변환하지 않는다.
- u145: 현재 미국 섹터 제품과 nav를 보존한다. 대시보드 확대, source 변경, 공개 활성화·스케줄·정책 변경은 별도 기존 유닛의 책임이다.
- u177: 홈 데이터·문구·카드 마크업은 u177이다. 본 유닛은 해당 클래스의 공통 스타일 계약만 제공한다.

## Scope Boundary

In scope:

- 공통 CSS 토큰: 표면/본문/보조글/테두리/강조/상태색, spacing, radius, type scale, focus.
- 홈에서만 적용하는 넓은 content 영역과 불필요 sidebar/TOC 공간 정리. 본문·아카이브·품질·관심 자산·미국 섹터는 페이지 유형에 맞는 폭을 유지한다.
- 한국어 주요 메뉴와 데스크톱/모바일의 실제 탐색 방식, 관심 자산 진입점, 현재 페이지 표시.
- Material 검색, 모드 전환, 모바일 drawer, 키보드 focus, skip link와 landmark 보존.
- 동작 검증을 위한 화면/DOM/키보드 관측 증거.

Out of scope:

- 홈의 데이터 선택과 renderer, 날짜·품질·미발행 badge의 의미 결정(u177).
- SVG 내부 글자/관심 자산 그래프/본문 정보 블록의 재표현 및 아카이브 필터·월별 묶음(별도 UI 유닛).
- 캘린더 SVG 파싱·차트 데이터 URL 오류 수정(u174/u175).
- 사이트 프레임워크 교체, 신규 웹 서버·SPA·CMS, 로그인·실시간 시세·사용자 계정.
- 원격 배포·workflow dispatch·미국 섹터 운영 활성화 및 기존 제품 정책 변경.

## Stage Decision

| Stage | Decision | 이유 / 실행 조건 |
|---|---|---|
| Functional Design | **REQUIRED / PENDING** | 주요 메뉴 이름·순서·모바일 동작·홈/본문 폭이 제품 행동을 바꾸며 후보 시안은 승인되지 않았다. |
| NFR Requirements | **REQUIRED / PENDING — focused** | 테마 대비, 44px 조작 영역, keyboard/search/drawer, reflow와 no-overflow를 구체화해야 한다. 기존 NFR-002/003/004/005/006과 R13을 재사용한다. |
| NFR Design | 별도 단계 SKIP 후보; 요구사항 확정 후 확인 | 기존 정적 Material 셸과 CSS만 사용한다는 전제. 새로운 JS·폰트·외부 의존성이 필요한 결정은 focused NFR 산출물에 비용·fallback을 검토하고 재판정한다. |
| Infrastructure Design | SKIP | 기존 MkDocs→GitHub Pages 유지. 인프라·secret·런타임/API·스케줄 변경이 없다. |
| Code Generation | **NOT STARTED** | 이 문서화 요청은 디자인 승인 또는 코드 구현 요청이 아니다. FD/NFR 산출물과 미결 결정을 정리하고 명시적 디자인·개발 지시가 확인된 뒤 실행한다. |

후속 필수 산출물(현재 생성·승인되지 않음):

- `aidlc-docs/construction/u176-site-shell-and-navigation-redesign/functional-design/business-logic-model.md`
- `aidlc-docs/construction/u176-site-shell-and-navigation-redesign/functional-design/business-rules.md`
- `aidlc-docs/construction/u176-site-shell-and-navigation-redesign/functional-design/domain-entities.md`
- `aidlc-docs/construction/u176-site-shell-and-navigation-redesign/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/u176-site-shell-and-navigation-redesign/nfr-requirements/tech-stack-decisions.md`

FD/NFR에서 결정할 사항:

1. 최신 시황/관심 자산/미국 섹터/아카이브/데이터 품질/서비스 안내의 명칭·순서와 메뉴 묶음. 모든 기존 진입점은 보존한다.
2. 모바일은 상단 compact menu, drawer 또는 필요한 별도 진입점 중 무엇을 사용할지 결정한다. 화면에 모든 메뉴를 작은 글자로 억지로 넣지 않는다.
3. 홈 max-width, 본문 reading-width, TOC/sidebar 조건과 breakpoint. 후보 홈 1120px·본문 70–80ch와 밝은 회색/청록은 검토안이다.
4. 테마 토큰의 정확한 값과 일반글/상태색 대비, 본문·보조글 크기. 수치 관측을 승인 증거로 기록한다.
5. 새 클래스·페이지 유형 판별 방식을 u177와 공동 확정한다. index만 확인하는 scoped template/body class로 광역 Material 내부 DOM override를 줄인다.

## Fixed Contracts

1. **기존 정적 사이트 유지**: MkDocs Material, `docs_dir: site_docs`, `site_url`의 `/investo/` prefix, ko/en 검색, default/slate와 모드 토글, archive symlink, 기존 URL/OG 메타를 유지한다. 새 외부 폰트·아이콘 CDN·JS 프레임워크·유료/API 요청을 추가하지 않는다.
2. **write ownership**: 예정 구현은 `mkdocs.yml`, `overrides/main.html` 및 필요 최소 header/navigation partial, 신규 `site_docs/assets/investo-ui.css`만 소유한다. 기존 `assets/u29.css`의 캘린더/차트 규칙을 교체하는 것은 기본 범위가 아니다. `site_docs/index.md`와 `publisher/site_index/*`의 홈 content 생성은 u177가 소유한다.
3. **CSS 소비 계약**: 후보 클래스는 `.investo-home`, `.investo-home-quick-links`, `.investo-market-grid`, `.investo-market-card`, `.investo-market-status`, `.investo-market-date`, `.investo-market-link`. FD에서 이름을 확정해 u177의 마크업 계약에 동일하게 기록한다. CSS는 badge 값·날짜·링크를 생성하지 않으며 상태 의미를 `::before` content에만 두지 않는다.
4. **검색·theme·focus 동작**: built HTML과 실제 브라우저로 기능을 검증한다. Material key shortcut/search input, 모바일 drawer 열기/닫기, 테마 persisted preference/OS default, skip-to-content, 열린 overlay의 focus/닫기 동작을 유지한다. 숨겨진 desktop/mobile 복제 메뉴가 중복 keyboard tab stop을 만들지 않도록 한다.
5. **테마 자산 보호**: `#gh-light-mode-only`/`#gh-dark-mode-only`와 Material built CSS 규칙을 보존한다. global `img`, `svg`, `.md-content`, `.md-sidebar`를 indiscriminate display override하지 않는다.
6. **본문 계약 보호**: 현재 v1/v2의 u154 순서·숫자 `<details>`와 역사적 근거를 보존한다. v3는 u169/u171의 typed 문서 순서를 소비하고 legacy 구조를 강제하지 않는다. 두 버전 모두 제목/면책/근거·실제 목차를 유지하며 홈 폭 확장이 장문을 화면 전체 폭으로 늘리지 않는다.
7. **제품 탐색 보존**: 관심 자산 `watchlist/index.md`를 주요 메뉴에서 접근 가능하게 추가하고, 기존 `sectors/index.md`, 세 시장 아카이브, 주간/월간 회고, 품질/정확도, About 링크를 보존한다. nav 표시 변경은 발행일·미국 섹터 freshness·운영 상태를 바꾸지 않는다.
8. **가독성과 조작 기준**: 목표 본문 16px 이상, 핵심 UI/일자·상태 최소 12px, 본문 line-height 1.5 이상. 주 조작 버튼·탭·카드 링크 target은 최소 44×44 CSS px; inline prose link는 문장 간격으로 충분히 구분한다. 일반글 대비 4.5:1 이상, 큰글/비텍스트 조작 경계·focus 3:1 이상을 focused NFR에서 측정한다. 색만으로 메뉴 선택·상태를 구분하지 않는다. 200% 확대에서도 내용과 주요 링크가 접근 가능해야 하며 JavaScript가 없어도 기존 정적 본문·실제 링크로 시장/아카이브/관심 자산에 진입할 수 있어야 한다.

## Implementation Steps

- [ ] 1. 최신 main의 nav/테마/페이지 유형을 재확인하고 FD 3개·focused NFR 2개 산출물 및 u177 공유 클래스·미결 디자인 결정을 작성·검토한다. 승인 여부와 코드 실행 허가를 별도 기록한다.
- [ ] 2. 승인된 토큰/폭/메뉴를 최소 Material override와 전용 CSS에 적용한다. 홈 scope와 본문 scope를 분리하고 OG/search/theme 계약을 보존한다.
- [ ] 3. 한국어 주요 메뉴와 관심 자산 진입점을 추가한다. 미국 섹터와 기존 아카이브·회고·품질·정확도 진입점을 확인한다.
- [ ] 4. desktop/mobile keyboard·drawer/search/theme 및 focus/tap target을 검증한다. `390×844`와 `1440×1000`에서 light/dark 화면을 기록하고 대표 본문·미국 섹터·관심 자산을 함께 확인한다.
- [ ] 5. built HTML/CSS의 링크·홈 scope·OG·테마 pair 회귀를 확인하고 의미 있는 경계 검증이 필요한 경우 focused contract test를 작성한다. 단순 CSS 숫자를 그대로 복사한 테스트는 쓰지 않는다.
- [ ] 6. 디자인 AC·NFR 관측 및 Material/strict docs 게이트를 독립 검토한다. 코드 완료와 운영 배포 상태를 구분해 summary에 기록한다.

## Acceptance Criteria

- **AC-176.1**: 신규 메뉴의 한국어 명칭과 순서가 승인된 FD와 일치하며 관심 자산·미국 섹터·아카이브·품질·정확도·서비스 안내가 실제 URL로 이동한다. desktop/mobile 각각 관심 자산과 미국 섹터에 최대 두 번의 메뉴 조작으로 접근한다.
- **AC-176.2**: 홈에 불필요한 문서 sidebar/TOC 공간이 남지 않으며 장문 시황의 reading width·목차·숫자 패널은 보존된다. 홈 content DOM은 u177의 renderer 출력으로 유지한다.
- **AC-176.3**: `390×844`와 `1440×1000`, default/slate 모두 대표 홈·시황·관심 자산·미국 섹터·품질 페이지에서 document 가로 overflow가 0이다. 긴 표는 자체 scroller로 접근할 수 있으며 페이지 전체 overflow를 숨겨서 통과시키지 않는다.
- **AC-176.4**: 검색·모드 전환·drawer·skip link·키보드 Tab/Enter/Escape가 동작하고 현재 메뉴가 시각/접근성 이름으로 식별된다. 최소44px 주 조작 target과 실제 focus ring·글자/대비 수치가 관측 증거로 확인된다. 200% 확대와 JavaScript 비활성 상태에서 정적 본문과 핵심 진입 링크 접근이 유지된다.
- **AC-176.5**: 기존 URL, OG/Twitter 메타, ko/en 검색, u143 Material theme pair 및 u145 미국 섹터 진입이 모두 유지된다. 새 API·LLM·네트워크 의존성·운영 활성화가 없다.
- **AC-176.6**: 임시 시안의 고정 숫자·스타일이 승인·검증된 것으로 기록되지 않으며 FD/NFR→구현→관측 증거가 연결된다.

## Tests / Validation

현재는 문서만 작성한다. 아래 명령은 승인 후 구현 시 사용할 게이트이며 **현재 실행·통과 기록이 아니다**.

```bash
uv sync --extra dev --extra docs
uv run --extra dev --extra docs python -m pytest tests/unit/visuals/test_check_material_theme_contract.py tests/unit/publisher/test_watchlist_pages.py tests/unit/publisher/test_site_index.py
uv run --extra docs mkdocs build --strict
uv run --extra docs python scripts/check_material_theme_contract.py
git diff --check -- mkdocs.yml overrides site_docs/assets aidlc-docs
```

HTML 링크·페이지 scope 계약이 바뀌면 focused built-HTML fixture로 의미를 검증한다. 화면 테스트는 임시 mockup이 아니라 위 strict build 결과를 대상으로 한다. 네 가지 viewport/theme 조합의 screenshot + DOM 좌표·scrollWidth/clientWidth + 실제 클릭/Tab focus/search/theme 관측을 남긴다. 가독성·tap/대비는 screenshot 하나나 Material gate의 PASS만으로 증명하지 않는다. u176 CSS-only 변경에는 pipeline 전체 테스트를 습관적으로 반복하지 않되, Python/publisher 경계가 실제 바뀌면 u177 게이트와 함께 재판정한다.

## Non-Goals

발행 의미·데이터 품질 정책·매매 판단을 바꾸지 않는다. 홈 요약을 재생성하거나 본문/숫자 evidence를 제거하지 않는다. 미국 섹터 공개 활성화, scheduling, quote/source qualification, 과거 아카이브 backfill, 새로운 framework·accounts·paid service·LLM/API 추가는 본 유닛에서 수행하지 않는다.
