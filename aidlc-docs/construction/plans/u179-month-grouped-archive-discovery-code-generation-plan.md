# Code Generation Plan: `u179 month-grouped-archive-discovery`

- **Date**: 2026-10-10

- **Unit**: u179 month-grouped-archive-discovery

- **Stage**: 등록 계획 — Functional Design / focused NFR 선행 필요

- **Status**: Complete — Functional Design/focused NFR and Code Generation6/6

- **Source**: 공개 Investo UI의 2026-10-10 archive 관측 및 현재 `site_index`/archive path/extraction 코드 확인. 사용자 지시: “굿 일단 유닛 문서화부터 진행해줘”.

- **Estimated Effort**: 설계/검증 계획 3–5 h, 설계 승인 이후 구현/검증 6–10 h. 기간 필터 및 과거 요약 eligibility가 미결이므로 구현 추정치다.

- **Dependencies**: u176 공통 shell/theme tokens; 완료된 u16/u29/u63/u82/u144. u177의 홈 최신 bundle 상태는 재사용 경계이며 u179의 state model로 복제하지 않는다.

- **Planning Baseline**: `origin/main` 48762793. 공개 관측은 2026-10-10 01:12–01:17 KST의 기록이다. 전체 범위·의존성은 [UI 개선 등록 문서](../ui-modernization-20261010/README.md), 보존 증거는 [측정값](../ui-modernization-20261010/evidence/metrics.json)를 참조한다.

## Problem Statement

2026-10-10 공개 `archive/us-equity/` 데스크톱 관측은 날짜 링크 98개가 한 목록으로 이어졌고 1440×1000 viewport에서 전체 페이지 높이가 3664px였다. 날짜별 내용 단서와 월 단위 이동이 없어 특정 기간의 시황을 찾으려면 긴 목록을 훑어야 한다.

현재 `publisher/site_index/segment_archives.py::_render_segment_index`는 `_segment_entries` 결과의 모든 날짜를 최신순으로 출력한다. 이 scanner는 `archive_sections.py::_latest_segment_entry_before`에도 공유되므로 화면 구성을 바꾸려다 홈/최신 archive의 미발행 fallback 판정을 바꾸는 위험이 있다. 월별 탐색은 새 제품 행동으로 별도 설계하되 archive의 영구 경로와 partial-bundle 계약을 보존해야 한다.

## Goal

시장별 아카이브에서 월 단위 묶음과 기간 탐색으로 원하는 날짜를 쉽게 찾게 한다. 이미 게시된 문서의 검증 가능한 결론을 짧은 단서로 선택적으로 보여주되 새 분석/LLM을 호출하지 않는다. JS가 없어도 모든 기존 날짜 URL과 legacy 탐색에 도달할 수 있고 날짜·필터 상태가 결정적으로 표시되어야 한다.

## Verified Evidence / Canonical Owners

### 현재 버전과 동시 등록된 v3 설계

최초 코드 기준은 48762793, 최종 문서 기준은 838bed60이다. 동시 등록된 사건·뉴스 v3 u167–u173을 피해 본 UI 번호는 u179다. 이 유닛은 월별 grouping/filter/URL 접근만 소유한다. **현재 legacy 결론은 기존 read-only extractor를, 미래 v3 snippet은 u171의 `event_archive_reader.py`와 PublicEditionView의 hash 검증 결과를 소비**한다. v3 sidecar/schema/parser, terminal digest→headline→availability 선택, 사건/회고/asset 의미를 이 유닛에서 새로 구현하지 않는다. 아직 없는 reader seam은 FD의 handoff로 남기고 현재 존재한다고 가정하지 않는다. 검증 불가한 역사 자료는 기존 원문 링크를 유지한다. 같은 `segment_archives.py`의 v3 payload 변경은 u171과 조정하고 본 유닛은 render-only 월 그룹/탐색에 한정한다.

| 근거 | 현재 owner와 재사용 계약 |
| --- | --- |
| `publisher/site_index/segment_archives.py::_segment_entries` | `archive/{segment}/YYYY/MM/*.md` directory scan의 현 canonical owner. `_render_segment_index` 및 `archive_sections._latest_segment_entry_before`가 소비한다. 새 렌더용 모델을 추가하더라도 두 번째 scanner를 만들지 않는다. |
| `publisher/site_index/segment_archives.py::update_segment_archive_index` | 시장별 `index.md` 갱신 owner. `segment`과 `segment_index_path` 호출 계약 및 결과 `Path`를 보존한다. |
| `publisher/site_index/archive_sections.py` | `SegmentBundleState`, `_build_bundle_states`, `_archive_segment_href`, `_latest_segment_entry_before`, `_legacy_section`의 owner. 최신·미발행·과거 링크 정책과 legacy root를 독립 필터로 대체하지 않는다. |
| `publisher/site_index/__init__.py::update_latest_index_pages` | archive/segment index 갱신 driver와 u82 compatibility re-exports. 새 탐색 구현은 기존 entry point를 통해 호출된다. |
| `_internal/archive_layout.py::ArchiveLayout` 및 `publisher/paths.py` | 영구 segmented/unsegmented archive path의 정본. 기존 날짜 문서 이동/rename 없이 index만 개선한다. |
| `_internal/briefing_extract.py::extract_conclusion` | 순수 canonical prefix 추출 owner. `site_index/hero.py::extract_conclusion`은 public-quality projection/fallback wrapper다. publisher→briefing.context 직접 import는 금지한다. |
| `publisher/site_index/_blocks.py` | `_escape_inline`은 줄바꿈 정규화, `_write_text_atomic`은 기존 atomic write owner다. `_escape_inline`이 HTML/Markdown escaping까지 수행한다고 가정하지 않는다. |
| `_internal/text.py::bound_at_sentence` | u131/u153의 단일 완결 문장 경계 helper. 새 snippet의 상한·decimal-safe 문장 경계와 `None` fallback에 재사용한다. |
| `tests/unit/publisher/test_site_index.py` | empty/일자 전체 목록/최신 partial navigation/legacy/멱등성의 기존 회귀 기반. |

관측 결과는 이 문서에 수치로 보존한다. 임시 audit 디렉터리나 캡처 파일은 구현의 외부 필수 의존성이 아니다. 98개/3664px는 당시 문제 설명이고 최종 pagination/filter 기능 통과 증거가 아니다.

## Existing Coverage / Deduplication

- **u16**: segmented 최신 진입점과 legacy 경로 노출을 이미 완료했다. 새 단위는 링크 존재를 다시 구현하지 않고 긴 시장별 목록의 시간축 탐색을 개선한다.
- **u29**: hero/전체 Archive/달력/주차별 회고/시장별 색인의 원래 제품 계약이다. 달력 renderer 오류는 u174에서 별도 수정하며 u179가 달력이나 회고 생성기를 다시 만들지 않는다.
- **u34**: 최근 N일 결론을 생성 context로 읽는 owner다. 그 loader는 전체 archive 탐색 모델이 아니며 publisher가 briefing sibling을 import하거나 최근 context 예산/기간을 변경하지 않는다. 결론 prefix 추출은 이미 neutral owner가 있으므로 그 경로만 재사용한다.
- **u58**: crypto regulation/policy source 단위다. archive UI는 source coverage/adapters/regulatory 판단을 추가하지 않으며 해당 단위와 실행 범위가 겹치지 않는다.
- **u63**: partial bundle의 target date별 미발행/이전 발행 fallback nav owner다. 월 필터가 미발행을 신규 문서로 만들거나 최신값 상태를 변경하지 않는다.
- **u82**: surface별 module owner와 공개 re-export/API를 완료했다. 새 archive 구조도 `segment_archives.py` 중심으로 유지하고 새로운 site-index facade/scanner를 만들지 않는다.
- **u144**: sealed consumer boundary owner다. archive 목록은 최종 문서의 소비자이며 raw generated `Briefing`에서 요약을 만들거나 sealed 본문을 후처리하지 않는다.
- **u131/u153**: 공개 요약의 완결 문장·decimal-safe 경계·단일 splitter owner다. archive snippet에 새 word-boundary/ellipsis 절단기를 만들지 않는다.
- **u176**: 공통 shell/theme tokens owner. index grouping/filter UI는 이를 소비한다.
- **u177**: 홈 최신 발행/bundle/미발행/fallback 상태 owner. 월별 historical entries에는 별도 “오늘”/stale 판단을 추가하지 않는다.
- **u145**: sector dashboard nav/renderer/public activation 제외. 시장 archive UI에서 sector 화면을 활성화하지 않는다.

## Scope Boundary

In scope:

- 세 시장의 `archive/{segment}/index.md` 월 그룹, 월별 일수/이동 링크, 기간 탐색 UI와 empty/filter-no-result/error/fallback 표현.
- canonical archive scan 결과를 render-only entry/month model로 묶는 결정적 변환.
- 기존 finalized conclusion의 선택적 bounded text snippet 및 eligibility/escaping/omission 규칙.
- malformed 날짜·directory mismatch·legacy root 경로의 안전한 취급과 기존 최신 fallback 소비자의 회귀.
- JS off에서도 전체 날짜 링크 접근, raw GitHub 읽기 및 실제 MkDocs built href/viewport 검증.

Out of scope:

- archive 날짜 문서/asset URL 변경·이동·rename·백필, 생성 시황 본문 변경, JSON search service/새 DB.
- 새 LLM 요약/분류/제목·수치·시장 의미 생성, source adapters/생성 recent context/예측 평가 변경.
- 홈 latest/bundle 상태 재정의, 달력 결함 수정, 주차·월간 회고 생성기, sector renderer/activation.
- 무한 스크롤 또는 JS 실행 전에는 기존 링크에 도달할 수 없는 pagination.

## Stage Decision

**Functional Design — REQUIRED/PENDING**. 월 그룹/기간 선택/검색 결과와 요약 eligibility는 새 제품 행동이다. 이 문서는 단위 등록 계획이며 현재 코드 생성에 바로 착수할 수 있는 승인된 설계가 아니다.

다음 3개 문서를 `aidlc-docs/construction/u179-month-grouped-archive-discovery/functional-design/`에 후속 작성한다.

1. `business-logic-model.md`: scan→entry validation/grouping→optional finalized snippet→static month navigation→filter enhancement→empty/error/fallback 흐름과 기존 latest state consumer 경계.
2. `business-rules.md`: sort/group/year/month anchors, filter semantics, 링크 전수 보존, malformed/legacy/summary eligibility, 상태 copy와 아래 결정의 승인 결과.
3. `domain-entities.md`: canonical paths와 proposed render-only `ArchiveEntry`/`ArchiveMonthGroup`의 exact fields/type/owner. `SegmentBundleState`와 같은 도메인 상태를 복제하지 않는다.

**Focused NFR Requirements — REQUIRED/PENDING**. archive가 누적될 때의 빌드 I/O/payload 및 keyboard/mobile/no-JS 접근을 새로 검증한다.

- `nfr-requirements/nfr-requirements.md`: 기준 98개 및 더 큰 고정 archive 집합의 deterministic scan/read count/build overhead/HTML byte budget, 390×844/1440×1000 light/slate, keyboard/JS-off 전수 링크 접근·오류/검색 결과 안내 기준과 승인 상한.
- `nfr-requirements/tech-stack-decisions.md`: static grouping과 선택적 enhancement 구조, cached/limited snippet 읽기, atomic write/fallback, CSS/theme tokens, 실제 MkDocs link rewriting 및 측정 방법. 표준 `tech-stack-decisions.md`를 다른 단계 문서로 대체하지 않는다.

**Separate NFR Design — decision PENDING**. 기존 static renderer·atomic write·탐색 구조를 재사용해 요구사항/기술결정 문서에 흡수하는 안을 FD/NFR에서 검토한다. 추가 필터 상태/캐시/저장 경계가 필요하면 구체적 이유를 기록하고 `nfr-design/nfr-design.md`를 추가한다. 별도 단계 생략 또는 완료를 지금 확정하지 않는다.

**Code Generation — NOT STARTED**. FD/NFR 후속 문서를 작성·승인하고 아래 결정을 고정하기 전에는 필터/summary renderer를 구현하지 않는다.

### FD에서 확정해야 할 결정

- **D-179.1 기간 UI**: static 월 anchor navigation을 기본으로 유지하고, 기간 필터의 입력(월 선택 또는 from/to), inclusive 경계, reset, 잘못된 범위, URL state 적용 여부를 결정한다. JS off/실패 시 모든 그룹/링크가 도달 가능해야 한다.
- **D-179.2 entry validation**: 날짜 stem/parent YYYY/MM 일치·invalid date·legacy/symlink/outside-root 안전 처리와 safe href 생성을 정의한다. malformed 항목을 숨기기만 하지 말고 기존 safe 항목의 reachable fallback을 명시한다. shared `_segment_entries`의 반환/정렬 계약 변경은 두 consumer 모두를 검증한 후에만 한다.
- **D-179.3 snippet eligibility**: legacy 최종문서/기존 archive에서 finalized 여부를 확인할 실제 증거/metadata가 무엇인지 조사한다. 단순히 오래된 `.md`라는 이유로 seal을 확인했다고 주장하지 않는다. 검증 가능한 finalized bytes가 없거나 legacy/read-error일 때는 날짜 링크만 남기는 안전 기본값을 고정한다. v3는 u171의 hash 검증 reader 결과와 제한 상태를 그대로 소비하고 별도 eligibility 판정을 만들지 않는다.
- **D-179.4 snippet shape/예산**: **legacy 경로만** 기존 neutral extractor/public projection과 한 줄 plain text, 최대 120 Unicode characters 후보를 사용한다. legacy 상한은 FD에서 확정하되 문장 경계는 `_internal/text.py::bound_at_sentence(..., require_complete=True)`를 재사용한다. 문장 없음/초과/unsafe 상태는 날짜 링크만 남기는 fallback이며 새 word-boundary/ellipsis splitter를 만들지 않는다. 숫자의 소수점을 문장 끝으로 오인하지 않는 기존 경계를 보존한다. **v3 경로는 u171이 제공한 exact terminal plain snippet을 소비**한다. digest 최대140자와 headline 최대120자의 서로 다른 계약을 보존하고, 마침표 없는 유효 headline 또는 121–140자 유효 digest에 legacy 120자/완결문장/projection 규칙을 적용하지 않는다. UI는 문맥별 escaping·자연스러운 줄바꿈·layout만 제공하며 별도 snippet 제한이 필요하면 u171 handoff에서 확정한다. 출력 text/attribute별 escaping 및 safe href 검증 owner, 제한 고지 보존과 읽기 개수 budget을 exact rule로 고정한다. 새 요약이나 의미 추론을 하지 않는다.
- **D-179.5 상태/failure**: empty archive/filter-no-result/unreadable entry/scan-write failure의 책임·copy·로그 범위를 정한다. summary read 실패는 날짜 링크를 제거하거나 정상 sibling 게시를 막지 않는다. index atomic failure는 기존 publisher의 오류/rollback 계약을 유지하며 성공으로 위장하지 않는다.

## Fixed Contracts

1. **영구 URL 보존**: 기존 valid `YYYY/MM/YYYY-MM-DD.md` 상대 링크와 built URL을 유지한다. group/filter는 index 표현만 바꾸며 날짜 문서나 자산 경로를 바꾸지 않는다. legacy unsegmented archive는 `_legacy_section`의 기존 경로로 계속 접근 가능하다.
2. **scanner 단일 owner**: scan은 `segment_archives._segment_entries`를 기준으로 한다. render-only grouping/model은 같은 모듈에 두고 필요하다면 그 helper를 수정하되 `archive_sections._latest_segment_entry_before`와 compatibility re-export의 소비 의미를 보존한다. 두 번째 archive walker를 만들지 않는다. `_blocks`의 줄바꿈 정규화와 atomic write를 재사용하되 HTML escaping을 제공한다고 가정하지 않는다.
3. **결정적 시간축**: 월/일자 정렬은 검증한 archive의 날짜를 기준으로 내림차순이다. 최신 bundle state의 시간축은 caller의 `target_date`와 기존 `SegmentBundleState`를 사용하고 wall clock/mtime/browser timezone으로 다시 판정하지 않는다. 동일 input tree/target_date→동일 index bytes.
4. **링크 접근 전수 보존**: JS off/실패 시 모든 기존 valid 날짜 링크가 static DOM에 존재하고 keyboard로 도달 가능하다. 그룹 접기를 쓰면 native control로 열 수 있어야 한다. 필터 사용 중에도 reset/전체 목록 경로가 보이며, 초기 script 미실행 상태에서 CSS로 전체 과거 링크를 숨기지 않는다.
5. **sealed 소비 경계**: optional snippet은 legacy의 검증 가능한 기존 결론 또는 v3 u171 reader가 hash 검증한 당시 PublicEditionView의 표면 요약만 소비한다. v3의 digest/headline/availability 선택과 sidecar validation을 별도로 구현하지 않는다. raw generated `Briefing`, raw source/diagnostic/fixture/secret, DOM 또는 새 LLM에서 재생성하지 않는다. historic eligibility를 증명하지 못하면 snippet을 생략해도 날짜 링크는 남는다.
6. **버전별 제한·공통 escaping**: legacy snippet만 승인된 상한의 완결 one-line plain text와 u108 공개 표현을 사용하며 u131/u153의 `bound_at_sentence(..., require_complete=True)` 및 `None`→날짜 link-only를 재사용한다. v3는 u171의 exact terminal snippet과 제한 상태를 그대로 표시하며 추가 sentence bounding·120자 제한·공개 projection·digest/headline/availability 재선택을 하지 않는다. 유효한 마침표 없는 headline과 121–140자 digest는 모두 유지한다. source/date/시장 제한의 의미를 바꾸지 않는다. 두 경로의 `segment_archives.py` pure presentation helper가 stdlib `html.escape`를 text node와 quote를 포함한 attribute 문맥에 사용하고, href는 검증된 날짜/segment와 기존 ArchiveLayout 경로로 구성한다. 구체 helper명/입력 타입 및 raw Markdown 표현의 호환 처리는 FD에 고정한다. 줄바꿈 정규화만으로 안전한 HTML을 보장했다고 해석하지 않는다. snippet 부재 또는 reader 오류 때는 날짜 링크를 유지하고 v3의 제한 상태도 보존한다.
7. **상태 경계**: 실제 파일 존재가 historical entry의 근거이고 미발행 날짜는 생성하지 않는다. 홈/latest의 generated/fallback 상태 정의는 u63/u177 owner를 소비한다. 빈 archive와 필터 결과 0개를 구분하고 읽기 실패를 “아카이브 없음”으로 오인시키지 않는다.
8. **쓰기/API/실패 보존**: `update_segment_archive_index(...)->Path`, `update_latest_index_pages`, facade exports, `_blocks` 줄바꿈 정규화/atomic write와 publisher rollback 의미를 유지한다. snippet failure는 링크-only fallback, 필수 index write failure는 기존 명시적 오류 경로다.

## Implementation Steps

- [x] **Step 1 — Functional Design**: 위 3개 산출물, D-179.1–5, typed entry/group 및 state/failure/link tables를 작성·검토한다. legacy/current/archive eligibility를 실제 코드/metadata로 확인한다.
- [x] **Step 2 — Focused NFR**: 위 2개 산출물에 누적 archive fixture 크기, 읽기/payload/빌드 overhead의 승인 상한과 no-JS/keyboard/browser 검증 방법을 고정한다. u176 tokens 및 u177 state 경계를 확인한다.
- [x] **Step 3 — 월별 static grouping**: 기존 scanner/atomic entry point를 사용해 valid 날짜 링크를 월별로 묶고 월 navigation/count를 표시한다. malformed 날짜/경로는 승인된 안전 처리와 fallback을 구현한다.
- [x] **Step 4 — 필터/optional snippet**: 설계에서 고른 progressive enhancement와 schema별 소비 경로를 구현한다. legacy만 승인된 bounded snippet을 만들고 v3는 u171의 terminal snippet/제한 상태를 escape해 표시한다. 초기 HTML/JS off에서는 전체 항목 접근이 가능하며 reset/no-result/read-error를 표시한다.
- [x] **Step 5 — 회귀/실제 href 검증**: empty/mixed dates/multi-year/partial/current/legacy/read failures/idempotence/no-JS 전체 링크와 existing fallback/re-export 테스트를 추가한다. v3의 마침표 없는 유효 headline, 121–140자 digest 및 missing/hash-mismatch 제한 상태가 UI 때문에 생략·절단·재선택되지 않는지 검증한다. Markdown→built HTML URL을 전수 비교한다.
- [x] **Step 6 — 성능/브라우저 검증 및 closeout**: 실제 MkDocs strict build, 승인 archive 규모와 2viewport×2theme, keyboard/JS off/filter/reset을 확인한다. 코드/데이터 SHA와 증거를 summary에 남긴다. 운영 배포와 과거 archive 수정은 별도 지시가 있을 때만 진행한다.

## Acceptance Criteria

- **AC-179.1**: FD 3개/NFR 2개 산출물과 D-179.1–5가 확정되어 entry/group/state/summary eligibility·예산이 context 없는 구현자에게 명확하다.
- **AC-179.2**: 세 시장의 모든 valid 기존 날짜 링크가 월/일 내림차순 그룹에 정확히 한 번 포함되며 기존 상대/built URL과 target-date/latest fallback 의미를 보존한다. JS off에서 모두 접근할 수 있다.
- **AC-179.3**: 승인된 기간 UI로 선택/초기화/결과 0개/invalid range를 구분하고 초기 JS 미실행/실패 때도 전체 링크 탐색이 남는다. legacy 원문 경로도 계속 도달 가능하다.
- **AC-179.4**: legacy snippet은 eligibility를 증명한 기존 finalized 결론의 bounded safe text이며, v3 snippet은 u171 hash 검증 reader가 제공한 exact terminal plain text/제한 상태다. 새 생성·추론·v3 재선택·추가 절단이 없다. 마침표 없는 유효 headline 및 121–140자 유효 digest도 유지한다. 없음/legacy/read-error/unsafe text 때는 날짜 링크를 유지하는 schema별 승인 fallback을 따르며 v3 reader의 제한 상태를 숨기지 않는다.
- **AC-179.5**: malformed 날짜/parent mismatch/outside-root/빈 경로를 안전하게 다루고 `_latest_segment_entry_before`, `SegmentBundleState`, facade API, atomic write 및 failure/rollback 계약을 보존한다.
- **AC-179.6**: 동일 tree/target_date에서 결과 bytes가 결정적이고 승인한 대규모 archive 빌드/payload budget 및 390px/1440px light/slate/keyboard/JS-off 검증을 통과한다. 당시 98개/3664px 관측을 최종 검증으로 대체하지 않는다.

## Tests / Validation

현재는 **문서 등록만** 수행한다. 아래는 구현 이후 수행할 명령이며 현재 테스트/브라우저 합격을 뜻하지 않는다.

```bash
uv run --extra dev python -m pytest tests/unit/publisher/test_site_index.py tests/unit/_internal/test_archive_layout.py tests/unit/publisher/test_paths.py tests/unit/_internal/test_module_boundary.py
uv run --extra dev --extra docs mkdocs build --strict
uv run --extra dev ruff check src/investo/publisher/site_index tests/unit/publisher/test_site_index.py
uv run --extra dev ruff format --check src/investo/publisher/site_index tests/unit/publisher/test_site_index.py
uv run --extra dev mypy --strict src/investo
git diff --check -- aidlc-docs/construction/plans/u179-month-grouped-archive-discovery-code-generation-plan.md
```

- **신규 예정**: `tests/unit/publisher/test_archive_discovery_u179.py` — exact links/multi-year grouping/invalid paths/snippet eligibility/read failure/static fallback/idempotence/shared fallback compatibility.
- **신규 예정**: `tests/integration/test_archive_discovery_html_u179.py` — 실제 `mkdocs.yml`에서 built href 전수 비교/escaping/JS-off 기본 접근. 새 파일은 FD owner 확정 후 계획에 갱신한다.
- 향후 browser evidence: 390×844/1440×1000 light/slate, 모든 월 이동/filter/reset/no-result, keyboard focus와 JS disabled 전수 링크 접근; 승인 scale fixture의 build time/read count/HTML bytes. 시각 캡처만으로 링크 전수 보존을 주장하지 않는다.
- 구현 focused tests 이후 repository-required 전체 gate를 수행한다. 문서화 시점에는 source/runtime 테스트를 실행하지 않는다.

## Non-Goals

새 시황 생성·정보 의미 변경·검색 서비스·데이터 소스·기존 URL/본문 backfill·운영 배포/커밋/푸시·u145 활성화는 이 단위의 등록 작업에 포함되지 않는다.

## Development decisions 2026-10-10

Required FD/NFR authored before implementation under entire development authorization, choices by developer. Minimal optional finalized-document handoff in site_index driver/pipeline is needed to consume actual E6 objects after verified archive write; no old document parsing/hash registry. Future u171 handoff stays presentation-only.

## Local completion2026-10-10

All6 steps complete. Actual legacy sealed-only plain summary and exact terminal presentation seam are distinguished; v3 hash reader remains u171. New tests test_archive_discovery_u179.py and test_archive_site_u179.py; final25 targeted and global6774 earlier snapshot are distinguished in [summary](../u179-month-grouped-archive-discovery/code/summary.md). Actual Chromium36 and5000-file budgets passed. No push/deploy.
