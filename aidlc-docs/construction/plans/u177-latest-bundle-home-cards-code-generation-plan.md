# Code Generation Plan: u177 latest-bundle-home-cards

- **Date**: 2026-10-10
- **Unit**: u177 latest-bundle-home-cards
- **Stage**: Documentation / design queue registration
- **Status**: Functional Design REQUIRED / PENDING; focused NFR Requirements REQUIRED / PENDING; Code Generation NOT STARTED
- **Source**: [2026-10-10 UI 분석·증거·유닛 개요](../ui-modernization-20261010/README.md)와 사용자의 “굿 일단 유닛 문서화부터 진행해줘” 요청
- **Priority**: P1
- **Estimated Effort**: Functional Design/NFR 3–5h, 승인 후 renderer·호환/회귀·화면 검증 6–10h. 리뷰·운영 배포 대기 제외.
- **Dependencies**: u176 공통 셸/CSS·클래스 계약; 완료된 u29/u63/u69/u96/u144/u153/u154. u174/u175 결함 수정은 본 홈 renderer의 선행 조건이 아니다.

## Problem Statement

`site_docs/index.md`에 정적 사이트 소개 H1, 생성된 hero의 “오늘의 시황” H1과 안내, 별도 `## 최신 시황` 링크 목록, `## 사이트 안내`가 함께 존재한다. 동일한 아카이브/서비스 안내 진입이 반복되고, “오늘”이라는 문구가 마지막 실제 발행일과 다른 현재 일자를 암시한다.

hero의 `_render_hero_block()`는 입력 `segment_briefings`에 없는 시장을 `continue`로 생략한다. 반면 최신 링크 목록은 기존 `SegmentBundleState`를 사용해 대상 날짜의 미발행과 이전 발행 날짜를 표현한다. 2026-10-08 묶음에서는 국내·미국 hero만 보이며 크립토 미발행/10-07 링크는 별도 아래 목록에 나타난다. 독자가 한곳에서 세 시장의 발행 여부·실제 날짜·요약·품질 고지를 확인하기 어렵다.

## Goal

“최신 발행 시황”이라는 하나의 홈 시작 영역과 세 시장 카드로 반복된 안내·링크를 통합한다. 모든 시장을 항상 표시하고 대상 bundle date와 각 시장의 실제 표시 문서 날짜를 분리한다. 발행 문서의 결론은 이미 validated/sealed 상태인 내용을 재사용하며, 발행 여부와 수집 근거 상태를 혼동하지 않는다. 이전 문서는 날짜가 명확한 fallback 진입으로 보여준다.

## Current Evidence

### 현재 버전과 동시 등록된 v3 설계

최초 코드 기준은 48762793, 최종 문서 기준은 838bed60이다. 작성 중 사건·뉴스 v3 u167–u173이 등록되어 본 UI 번호는 u177로 확정했다. 현재 v1/v2에서는 아래 결론 extractor·CoverageStatus·quality gate 계약을 사용한다. **v3는 u169의 PublicEditionView와 u171의 surface adapter/event archive reader를 소비**하며 digest→동일 terminal headline→사건 0일 때 availability라는 v3 순서를 보존한다. legacy callout으로 v3 요약을 재생성하거나 새 event summary/availability/hash reader를 본 유닛에서 구현하지 않는다. 홈 카드 세 개는 시장별 진입 수이며 TLDR를 강제로 3항목 채운다는 뜻이 아니다.

FD 결정 목록에 schema별 입력/summary/quality/absence adapter와 정확한 기존/미래 owner·전환 조건을 추가한다. v3 typed seam이 아직 없으면 구현됐다고 가정하지 않고 u171과 handoff를 정한다. 같은 site_index 함수의 semantic payload 변경은 u171이, 카드 마크업·날짜·진입 layout은 본 유닛이 소유하며 무조정 병렬 수정은 하지 않는다. 현재 품질 parser/pipeline 변경 범위는 v1/v2의 home consistency 보강이며 v3 판정은 기존 typed owner를 재사용한다.

2026-10-10 최초 코드 기준 main `48762793`에 대한 코드 읽기 근거다. 구현 시작 전 최신 상태를 재확인한다.

| 근거 | 현재 동작 / 계획에 주는 제약 |
|---|---|
| `src/investo/publisher/site_index/hero.py` | `_render_hero_block()`가 absent 시장을 생략하고 `# 오늘의 시황 ({iso})`를 생성한다. `extract_conclusion()`는 neutral extraction과 공개 품질 언어 projection을 재사용한다. |
| `src/investo/publisher/site_index/archive_sections.py` | canonical `SegmentBundleState(segment, target_date, generated, href, fallback_date, fallback_href)`와 `_build_bundle_states()`가 이미 있다. fallback은 대상일보다 **이전** 날짜의 실제 파일이다. 새로운 absence 모델을 만들 필요가 없다. |
| `src/investo/publisher/site_index/__init__.py::update_latest_index_pages()` | 현재 hero를 먼저 쓰고 bundle states를 계산한 뒤 홈/아카이브 최신 목록·heatmap·세 시장 index를 갱신한다. 순서·호환 exports·반환 경로를 고려해야 한다. |
| `src/investo/publisher/site_index/_blocks.py` / `_constants.py` | 기존 u29 hero marker와 atomic write를 재사용한다. marker bootstrap/section replacement의 기존 동작을 검토해야 중복 H1/블록의 재생성을 막을 수 있다. |
| `src/investo/orchestrator/pipeline.py` 1450대 / 1590–1705 | E5 sealed `document.briefing`으로 소비 입력을 교체하고 exact archive를 쓴 뒤 index, OG, quality history/dashboard와 u69 gate를 처리한다. 홈은 generated `market_summary`에 돌아가면 안 된다. |
| `src/investo/publisher/quality_consistency.py` | `SegmentStatusBlock`, `parse_segment_status_block()`, `CanonicalQualitySnapshot`, `build_canonical_snapshot()`가 기존 품질 소유자다. 상태 타입/라벨은 `models/segments.py::CoverageStatus/COVERAGE_STATUS_LABELS`다. |
| `tests/unit/publisher/test_site_index.py` | marker·결론·idempotence, partial fallback/no-history, 경로 monkeypatch seam·아카이브 목록 테스트가 이미 있다. 오늘의 H1에 대한 기대는 제품 변경으로 갱신하되 나머지 보존 계약은 유지한다. |
| `tests/unit/orchestrator/test_run_pipeline.py` / `tests/integration/test_bundle_reconciliation.py` / `tests/integration/test_publisher_smoke.py` | publish/partial/rollback·통합 경계를 검증하는 기존 테스트 표면이다. 새 home write도 같은 pre-git rollback 안에 있어야 한다. |

[보존한 홈 시안](../ui-modernization-20261010/evidence/home-concept.html)은 1440px에서 세 카드 한 줄, 390px에서 세로 카드, 시장명·상태·실제 날짜·요약·명확한 링크를 보여주었다. [샘플 측정](../ui-modernization-20261010/evidence/concept-metrics.json)의 390px 카드 bottom은 402/581/761px였고 가로 overflow는0이었다. 이는 고정된 짧은 샘플에 대한 **디자인 후보 관측**이다. 임의 길이 요약을 세 카드 모두 first viewport에 맞추라는 계약이나 디자인 승인으로 해석하지 않는다. 시안은 검색·미국 섹터 등 최신 사이트 전체 기능을 갖추지 않았으며 그대로 운영 템플릿으로 복사하지 않는다. 임시 시안 파일이 없어도 이 문서의 텍스트 요구사항으로 후속 설계·납품이 가능해야 한다.

## Existing Coverage / Deduplication

- u29/u82: 자동 hero·site_index 패키지/호환 export를 제공한다. 신규 사이트/index 서비스로 대체하지 않는다.
- u63: generation present / absent-with-fallback / absent-without-history 표현이 이미 완성됐다. 같은 `SegmentBundleState`를 홈 카드에도 사용한다.
- u69/u96: canonical 품질 snapshot·현재 run 일관성 게이트를 소유한다. severity/KPI 가족·정상/부분/제한/실패 분류를 새로 만들지 않는다.
- u144/u149/u150: 봉인 문서/valid survivors와 degraded 처리·신뢰 차단을 소유한다. 홈의 표현 문제로 세그먼트 제외나 exit0/1/2 정책을 변경하지 않는다.
- u153: 문장 경계/완전한 요약·링크 안전성 helper를 소유한다. 홈 전용 임의 문자절단·ellipsis·sentence inference를 추가하지 않는다.
- u154: 본문 H1/TLDR/숫자 패널/뉴스 우선 순서를 소유한다. 여기서 시황 preamble·body를 다시 구현하거나 과거 본문을 고치지 않는다. 홈의 단일 H1만 본 유닛이 담당한다.
- u176: 공통 토큰·셸·메뉴·카드 CSS를 제공한다. renderer 변경은 본 유닛이며 같은 CSS 파일을 병렬로 수정하지 않는다.
- u145: “미국 섹터” 메뉴와 제품을 유지한다. 홈 링크를 정리하면서 이 메뉴를 시안에서 빠졌다는 이유로 제거하지 않는다.

## Scope Boundary

In scope:

- 홈 renderer의 시작 제목·소개·세 시장 카드·간결한 보조 링크 구성.
- 기존 bundle states와 finalized consumer view에서 시장별 present/absence/date/link/결론을 결정적으로 투영.
- 기존 품질 owner에서 얻은 상태를 독자에게 badge/고지로 표시하고 미확인값의 보수적 표현을 정한다.
- 기존 홈 블록을 일회 마이그레이션하되 다음 publisher 실행에서 새 구조가 재생성되도록 owner를 바꾼다.
- built HTML/strict build·sealed/rollback/idempotence·실제 모바일/테마 화면 검증.

Out of scope:

- 새 시장 데이터·LLM 요약/API 요청, 품질 threshold/새 severity enum, 완료 문서의 재작성.
- 아카이브 최신 목록의 의미 변경·날짜 필터·월별 분류, 관심 자산 결과 생성, 본문 SVG/숫자 evidence 재표현.
- 캘린더/차트 URL 결함(u174/u175), 셸 CSS·메뉴 재설계(u176).
- source qualification·retry·secret·runtime·배포·미국 섹터 활성화·운영 정책 변경.

## Stage Decision

| Stage | Decision | 이유 / 실행 조건 |
|---|---|---|
| Functional Design | **REQUIRED / PENDING** | 홈 정보 계층과 부분 발행 카드·품질 badge·fallback 동작이 제품 행동을 바꾼다. 미결 디자인/품질 입력 우선순위를 고정해야 한다. |
| NFR Requirements | **REQUIRED / PENDING — focused** | 가변 길이 요약 reflow, no-clipping, accessible links/상태, publisher idempotence·sealed/rollback 보존을 명세해야 한다. 기존 NFR-002/003/004/005/006 및 R13을 재사용한다. |
| NFR Design | 별도 단계 SKIP 후보; 요구사항 확정 후 확인 | 기존 순수 renderer·atomic write·게시 트랜잭션 재사용. 신규 IO/저장 계약이 필요해지면 재판정한다. |
| Infrastructure Design | SKIP | 기존 사이트/Pages와 publisher 경계를 유지한다. 신규 인프라·source/API·secret·스케줄 없음. |
| Code Generation | **NOT STARTED** | 사용자 요청은 유닛 문서화다. FD/NFR의 필수 산출물·미결 결정 및 u176 스타일 계약을 검토하고 명시적 디자인·개발 지시가 확인된 뒤 구현한다. |

후속 필수 산출물(현재 작성·승인되지 않음):

- `aidlc-docs/construction/u177-latest-bundle-home-cards/functional-design/business-logic-model.md`
- `aidlc-docs/construction/u177-latest-bundle-home-cards/functional-design/business-rules.md`
- `aidlc-docs/construction/u177-latest-bundle-home-cards/functional-design/domain-entities.md`
- `aidlc-docs/construction/u177-latest-bundle-home-cards/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/u177-latest-bundle-home-cards/nfr-requirements/tech-stack-decisions.md`

FD/NFR에서 고정할 미결 사항:

1. 카드 전체 link 또는 명시적 primary link, 빠른 시장 진입 영역, 보조 안내 위치와 heading hierarchy.
2. `CoverageStatus`의 badge 공개 문구와 미확인 상태 표시. 발행 여부/근거 상태/대상 bundle date를 한 등급으로 합치지 않는다.
3. 품질 badge 입력을 sealed 문서의 기존 `SegmentStatusBlock`로 한정할지, 동일 날짜 `CanonicalQualitySnapshot.segment_blocks`를 전달할지 결정한다. 어떤 방식이든 기존 canonical owner·보수적 의미를 재사용하며 publisher 현재 순서상 오래된 `quality.md`/history를 먼저 읽는 방식은 금지한다. 기존 `quality_consistency.check_quality_consistency`/`validate_date_quality_consistency`의 optional home 입력 타입·기본값·호환 호출과 `pipeline._enforce_quality_consistency_gate`의 home read/pass-through를 FD에 정확히 고정한다. old caller의 기본값은 home 검사를 요청하지 않는 `None`이며 기존 품질 검사 의미를 보존한다. 신규 홈을 생산한 segmented 경로는 같은 run의 실제 홈 텍스트를 필수로 전달하고 읽기 실패/누락을 조용히 skip하지 않는 규칙 및 현재 pre-git 호출 순서를 고정한다.
4. 이전 문서 카드는 날짜+미발행 고지만 보여줄지 검토한다. 기본 제안은 이전 문서 요약·품질을 읽지 않고 날짜가 명확한 fallback 링크만 표시하는 것이다. 표시하기로 하면 정확한 fallback 날짜의 이미 발행된 문서만 소비하고 provenance를 명시한다.
5. 기존 `segment_briefings=None` 호환 경로와 direct `update_index_hero()`를 유지하는 전략, static introduction·최신 목록·사이트 안내를 안전하게 이행하는 marker 경계를 확정한다.
6. u176와 shared class/header·홈 scope 계약을 확정한다. 시안에 있는 “최근 발행” 목록·티커 칩은 이번 목표에 필수인 것으로 간주하지 않는다.
7. 카드 내부를 기존 MkDocs build-time Markdown parser로 처리할지, 안전한 plain-text HTML로 표현할지 결정한다. 허용되는 강조·링크·escaping owner를 고정한다. 현재 publisher에 범용 Markdown→HTML runtime renderer가 있다는 가정을 하지 않으며 `docs` extra의 Markdown 패키지를 daily runtime 의존성으로 추가하지 않는다.

## Fixed Contracts

### Canonical ownership / compatibility

- **Bundle owner**: `publisher/site_index/archive_sections.py::SegmentBundleState` 및 `_build_bundle_states()`. 필드는 `segment: MarketSegment`, `target_date: date`, `generated: bool`, `href: str`, `fallback_date: date | None`, `fallback_href: str | None` 그대로다. 새로운 시장 상태 enum/중복 dataclass/저장 sidecar를 만들지 않는다.
- **Conclusion owner**: `_internal/briefing_extract.py::extract_conclusion`; 공개 language projection은 `_internal/public_quality_language.py`, 표면 호환 wrapper는 `site_index/hero.py::extract_conclusion`이다. generated `Briefing.market_summary`, 원시 LLM reply, notification용 별도 summary가 홈의 대체 입력이 되면 안 된다.
- **Quality owner**: `publisher/quality_consistency.py::SegmentStatusBlock/CanonicalQualitySnapshot/parse_segment_status_block/build_canonical_snapshot`; 타입/라벨은 `models/segments.py::CoverageStatus/COVERAGE_STATUS_LABELS`. 카드의 품질값은 `CoverageStatus | None`로 소비한다. None은 미확인 표시이며 normal로 기본화하지 않는다. 단순 결론 문구 “제한”이나 source 이름·파일 유무로 새 status를 추론하지 않는다.
- **Renderer owner**: `site_index/hero.py`가 홈 마크업, `site_index/__init__.py`가 갱신 순서·호환 export를 소유한다. package-level 기존 public import, 경로 call-time resolution, optional kwargs/test seams, 반환 changed paths 의미를 보존한다.
- **Write boundary**: 구현 예정은 `src/investo/publisher/site_index/hero.py`, `__init__.py` 및 필요 최소 `_constants.py`/`_blocks.py`와 focused tests다. **`src/investo/publisher/quality_consistency.py`**는 기존 canonical gate 안의 홈 badge 파싱/비교를, **`src/investo/orchestrator/pipeline.py::_enforce_quality_consistency_gate` 및 기존 caller**는 현재 홈 읽기·gate 입력 전달만 최소 수정할 수 있다. 새 gate registry·snapshot 계산·publish 순서·판정/exit 정책은 만들지 않는다. FD에서 optional home 입력의 정확한 타입/기본값/검사필수 경로·호환 export·pre-git 호출을 고정한다. 홈 마이그레이션으로 `site_docs/index.md`를 변경할 수 있으나 **생성기 변경 없이 파일만 편집해서 완료할 수 없다**. `u176` CSS 파일·메뉴는 본 유닛 write 대상이 아니다. `archive_sections.py`의 기존 아카이브 표현은 의미를 유지하며 bundle state를 공유하는 최소 연결만 허용한다.

### Card truth table

대상 날짜는 publisher의 `target_date`이며 브라우저/서버 wall clock으로 “오늘”을 바꾸지 않는다. 순서는 국내 증시→미국 증시→크립토로 `_SEGMENTS`와 일치한다.

| 기존 입력 | 필수 표시 | 링크 / 요약 |
|---|---|---|
| `generated=True`, sealed document 있음 | 시장명, `발행 {target_date}`, canonical 근거 상태 또는 미확인 | 해당 날짜의 실제 archive 링크와 봉인된 결론. 근거 제한 문장 등 필수 고지를 임의 삭제하지 않는다. |
| `generated=False`, `fallback_date/href` 있음 | `{target_date} 미발행`, `최근 발행 {fallback_date}` | fallback 날짜 문서로 이동. 대상 날짜 문서처럼 표시하거나 “오늘 발행”으로 승격하지 않는다. 기본안에는 이전 결론을 복사하지 않는다. |
| `generated=False`, fallback 없음 | `{target_date} 미발행`, `이전 발행 없음` | 존재하지 않는 대상 날짜에 대한 read link를 만들지 않는다. 필요하면 해당 시장 아카이브 index로 이동한다. |
| 품질 parser에서 status 미확인 | `근거 상태 미확인` 등 FD 확정 문구 | 새 status값·색상만으로 정상 암시를 하지 않는다. 상세 문서 진입은 유지한다. |

세 시장 카드/상태 영역은 항상 존재한다. 현재 v1/v2의 발행 absence와 CoverageStatus `failed`는 독립 축이다. 생성되었으나 quality failed인 유효 survivor를 미발행으로 바꾸거나, absent 시장에 current bundle의 정상 badge를 붙이지 않는다. 과거 문서 fallback의 날짜와 품질값을 현재 묶음의 snapshot으로 채우지 않는다. v3에서는 u169/u171의 availability/quality와 당시 typed 상태를 소비하며 legacy CoverageStatus 하나로 축약하지 않는다.

### Layout / generation / publication invariants

1. 제목은 “최신 발행 시황”과 실제 대상 bundle date로 한 번만 표시한다. `오늘 자동 발행` 같은 clock 의존 안내를 제거한다. 사이트 소개·hero·최신 목록의 H1/시장 링크 중복을 새 생성기 구조에서 해결한다. 정보 제공 면책·운영 원칙 링크는 보존한다.
2. 홈 카드의 의미 데이터는 하나의 bundle-state tuple로 계산하고 홈/아카이브가 같은 present/absence/fallback date를 소비한다. 현재 hero-before-state 순서를 state-build→home render로 바꿀 수 있으나 별도 날짜탐색 알고리즘을 만들지 않는다.
3. `segment_briefings=None`은 현재 legacy/nonsegmented compatibility 경로다. 빈 dict와 혼동하지 않는다. 홈을 placeholder로 덮어쓰지 않는 기존 hero 보존 의도를 유지하고, FD에서 이 경로의 최신 목록 처리까지 테스트로 고정한다. empty dict는 renderer 테스트 가능 상태일 뿐 0-survivor 생산 게시 성공을 허용하지 않는다.
4. E5 sealed consumer 입력을 유지한다. 현재 v1/v2의 `.briefing.rendered_markdown`, 향후 v3의 PublicEditionView/기존 surface adapter를 읽기만 하며 document digest·notification DTO·survivor set을 바꾸지 않는다. 결론/digest/headline 선택과 신뢰 검증은 schema별 기존 owner를 소비하고 본 유닛이 재요약·새 LLM/API를 추가하지 않는다.
5. 품질 badge는 같은 날짜의 canonical parser/snapshot과 정합한다. 기존 u69 gate를 제거·완화하거나 별도 quality validator registry를 만들지 않는다. 새로운 홈 badge의 일관성 검증은 기존 `quality_consistency.py` 소유자 아래 focused comparison으로 확장한다. current quality history가 index 이후 생성되는 실제 순서를 FD에서 명시하고, stale row/read 또는 snapshot 자체를 홈과 다르게 생성하지 않는다.
6. 기존 marker/block/atomic helper를 재사용하고 idempotence를 보장한다. marker 없는 bootstrap·옛 section migration·반복 발행·반복 동일 날짜에서도 카드/H1/중복 블록이 증가하지 않는다. 다른 section·footer의 보호 bytes와 index changed-path contract를 확인한다.
7. 모든 home/index write는 `pipeline.py`의 기존 snapshots→pre-git rollback에 포함된다. IO·품질 gate 오류에서 이전 홈·아카이브 bytes가 복구된다. commit/push 이후는 기존 PublisherGitError/publication receipt 계약을 유지하며 홈 작업이 임의 rollback을 추가하지 않는다.
8. HTML link/class/label은 escaping·접근성을 유지한다. Markdown 문장·강조·링크를 HTML로 옮길 때 새 regex sanitizer나 raw HTML interpolation을 만들지 않는다. `_blocks._escape_inline`은 줄바꿈 정규화일 뿐 HTML escape가 아니므로 안전화 근거로 사용하지 않는다. FD에서 pure renderer의 출력 문맥별 text/attribute escaping과 safe href owner를 고정한다(HTML text는 stdlib `html.escape`, attribute는 quote escaping 및 기존 archive path 검증; Markdown을 허용하면 실제 renderer의 안전 정책·링크 구조 보존을 검증). 키보드로 primary link에 focus할 수 있고 accessible name에는 시장과 대상 날짜가 있다. absent-without-history 카드를 전체 잘못된 link로 감싸지 않는다.
9. u176 승인 클래스·tokens를 소비한다. 390×844 및 1440×1000 light/dark에서 document horizontal overflow0, 의미 있는 글자 크기·대비·최소44px primary target을 확인한다. 가장 먼저 시장명·발행 상태·빠른 진입을 볼 수 있게 설계한다. 가변 길이 모든 요약/고지를 첫 viewport에 넣기 위해 line-clamp·ellipsis·overflow hidden·글자 축소로 잘라내지 않는다. 200% 확대에서도 내용 접근과 자연스러운 줄바꿈을 유지한다. JavaScript 비활성 상태에도 세 시장의 날짜·상태·실제 링크를 읽고 이동할 수 있다. 세 상세 카드 전체 첫 화면 노출은 짧은 fixture의 참고 목표이며 모든 데이터 길이에 대한 필수 AC가 아니다.

## Implementation Steps

- [ ] 1. FD3개/focused NFR2개를 작성하고 카드 truth table·품질 입력 배선·None 호환·migration·u176 클래스 계약과 승인 상태를 확정한다. 디자인·코드 실행 허가를 별도 확인한다.
- [ ] 2. 실제 기존 home/archive/partial/unknown/no-history/None/bootstrap fixture로 현재 동작을 pin한다. u153/u154·sealed 문서 bytes가 보호되는지 확인한다.
- [ ] 3. `update_latest_index_pages()`가 canonical bundle states를 한 번 만들고 홈 renderer에 전달하도록 순서를 조정한다. 기존 public exports/path seams·archive meanings·returned paths를 보존한다.
- [ ] 4. “최신 발행 시황” 단일 시작영역과 세 시장 카드를 생성하고 static 소개/최신/사이트 안내 중복을 owner-controlled migration으로 정리한다. 한 번의 수동 homepage 편집 이후 다음 발행에서 되돌아오는 구조를 허용하지 않는다.
- [ ] 5. 승인된 품질 입력으로 existing parser/snapshot의 값과 고지를 표시한다. prior-date fallback·unknown 상태·실제 partial와 u69 gate의 일관성 및 rollback을 확인한다.
- [ ] 6. strict built HTML과 u176 통합 화면에서 light/dark,390×844/1440×1000, 긴 결론·품질 고지·특수문자·no-history keyboard/tap/reflow를 검증한다. 명시적 내용 손실 없이 빠른 시장 진입을 확보한다.
- [ ] 7. focused/full/static/policy/Material 게이트와 독립 리뷰를 완료해 summary/cross-check에 evidence를 연결한다. 문서화·디자인 승인·코드 완료·원격 배포를 별도로 기록한다.

## Acceptance Criteria

- **AC-177.1**: 자동 갱신되는 홈에 “최신 발행 시황”과 실제 bundle date, H1 한 개, 국내·미국·크립토 카드 세 개가 표시된다. 중복 시장 링크/장문 소개가 주요 영역을 반복하지 않고 운영 원칙·면책·아카이브 진입은 남는다.
- **AC-177.2**: all-present, partial+fallback, partial+no-history에서 truth table과 정확한 날짜/URL이 일치한다. 홈페이지와 아카이브의 present/absence/fallback 상태가 같으며 존재하지 않는 same-date read URL이 없다.
- **AC-177.3**: 현재 v1/v2는 validated/sealed 결론을, v3는 기존 u171 adapter가 선택한 terminal digest/headline/availability를 소비한다. 각 schema의 문장·필수 제한 고지를 유지하고 legacy callout bridge를 v3에 추가하지 않는다. 홈 생성 전후 archive SHA/bytes·DTO·원문 근거는 동일하며 새 LLM/API·quality enum/추론이 없다.
- **AC-177.4**: 품질 badge가 기존 canonical 상태와 일치하고 unknown은 정상으로 기본화되지 않는다. absence와 failed가 구분되며 fallback 날짜를 current 정상으로 꾸미지 않는다. 기존 u69 gate에서 홈/문서의 의도적 모순 fixture가 확인된다.
- **AC-177.5**: 같은 입력 두 번 갱신 시 home/archive bytes가 동일하고, 옛 home migration·marker bootstrap·None 경로에서도 중복 블록/H1이 생기지 않는다. 경로 seam은 실제 generated 파일을 테스트 중 수정하지 않는다.
- **AC-177.6**: pre-git IO/품질 검증 실패가 홈·아카이브·지정 snapshot을 원래 bytes로 복구하며 유효 siblings·partial exit/Pages sequencing·post-commit 복구 계약이 보존된다.
- **AC-177.7**: u176 통합 built site의 네 viewport/theme 조합에서 document overflow0, 시장 상태·빠른 진입 우선, 실제 focus·44px primary target·가독성/대비가 관측된다. 긴 결론/필수 고지가 clipping 없이 자연스럽게 흐르며 200% 확대·JavaScript 비활성 상태에도 내용과 링크 접근을 유지한다.
- **AC-177.8**: 다음 publisher 갱신 후에도 새 홈 구조가 유지되며 홈-only 수동 수정으로 완료 판정하지 않는다. 임시 시안 관측·FD 승인·구현 완료·운영 검증은 각각 기록한다.

## Tests / Validation

아래는 승인 후 구현용 명령이다. 현재 문서화 작업에서는 구현 테스트를 실행하지 않는다. 새 테스트를 추가한다면 existing `test_site_index.py`와 품질/rollback suite에 경계를 검증하는 fixture를 확장하며 렌더 문자열을 그대로 따라 쓰는 테스트를 만들지 않는다.

```bash
uv sync --extra dev --extra docs --extra sector
uv run --extra dev --extra docs python -m pytest tests/unit/publisher/test_site_index.py tests/unit/publisher/test_quality_consistency.py tests/unit/publisher/test_public_document_architecture_u144.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_bundle_reconciliation.py tests/integration/test_publisher_smoke.py
uv run --extra dev ruff check src/investo/publisher/site_index src/investo/publisher/quality_consistency.py src/investo/orchestrator/pipeline.py tests/unit/publisher tests/unit/orchestrator
uv run --extra dev ruff format --check src/investo/publisher/site_index src/investo/publisher/quality_consistency.py src/investo/orchestrator/pipeline.py tests/unit/publisher tests/unit/orchestrator
uv run --extra dev mypy src
uv run --extra docs mkdocs build --strict
uv run --extra docs python scripts/check_material_theme_contract.py
uv run --extra dev --extra docs --extra sector python -m pytest
git diff --check
git status --short
```

구현 시에는 기존 CI의 모듈 경계/no-paid/secret·정책 게이트를 동일하게 실행한다. browser 증거는 임시 standalone 시안이 아니라 실제 build 결과의 네 조합 screenshot·DOM metrics·키보드/클릭 행동으로 남긴다. built homepage 카드의 링크를 실제 산출 경로와 대조한다. canonical gate의 기존 PASS만으로 신규 홈 badge·partial 의미 검증을 대체하지 않는다.

## Non-Goals

월력일 기준으로 “오늘”을 위조하거나 미발행을 fresh로 표시하지 않는다. 품질·generation absence를 단일 상태로 합치지 않는다. 추가 LLM 요약·API, severity/KPI 확대, sealed 본문·제목/TLDR/숫자 preamble 재구현, source/retry/notification·exit 정책 변경, 과거 문서 backfill과 운영 배포·미국 섹터 활성화는 수행하지 않는다.
