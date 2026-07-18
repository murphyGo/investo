# Code Generation Plan: `u141 image-selection-and-insertion`

**Date**: 2026-07-19
**Unit**: u141 image-selection-and-insertion
**Stage**: Code Generation
**Status**: Planned — implementation gated on candidate-data accumulation (start when the image_candidates ledger holds >=5 distinct dates; check archive/_meta/image_candidates/)
**Source**: u137 Roadmap 항목 1 (활용 단계 — 선정·삽입 유닛). 2026-07-17 user feature request "실제 뉴스/칼럼/커뮤니티 이미지를 저장해두고 **활용**" 중 활용 1단계: 재출현 인덱스 + 당일 후보에서 히어로/섹션 이미지를 결정적으로 선정하고, cleared 바이너리는 기존 `_HERO_PRIORITY`의 `external-context-image` 슬롯으로, metadata-only 후보는 "원문 링크 카드"(제목+크레딧+링크, 바이너리 비게시)로 렌더한다.
**Estimated Effort**: ~10-14 h (Step 0 데이터 분석 + FD 포함)
**Dependencies**:
- **u137 image-candidate-registry-and-licensed-store** (날짜별 원장 `archive/_meta/image_candidates/{YYYY}/{YYYY-MM-DD}.jsonl`, 재출현 인덱스 `index.json`, rights 상태기계, content-addressed store `assets/images/` — u141의 유일한 입력)
- u136 feed-image-metadata-harvest (원장 필드의 원천: `image_url/width/height/mime/credit`)
- u19/u24 visuals 정책·provenance (`_HERO_PRIORITY`, `insert_visual_links`, `build_external_provenance`, `provenance_caption`, `validate_visual_asset`)
- u86 curated library (`_prepare_curated_context_image` — 로컬 바이트 복사→provenance→검증 패턴 선례; `select_curated_asset` — 결정적 선정 tie-break 선례)
- u52/u50 pipeline 주입 선례 (`_inject_carryover_into_segments` / `_inject_chart_blocks_into_segments` — visuals prep 이후, reader-format 체인+`scan_compliance` 이전)
- u56/u61/u71/u112 게이트 (링크 카드가 통과해야 하는 compliance / first-viewport / polish 표면)

---

## Data-Accumulation Gate (구현 착수 조건)

u137은 의도적으로 "수집 먼저, 활용은 데이터 본 뒤"로 닫혔다. 이 유닛은 **원장에 ≥5 distinct dates가 쌓인 뒤** 착수하며, Step 0에서 실데이터로 아래 질문에 답한 뒤에야 선정 휴리스틱의 상수를 고정한다 (계획 시점 2026-07-19 현재 `archive/_meta/image_candidates/`는 미존재 = 0 dates):

| # | 실데이터 질문 | 결정되는 설계 |
| --- | --- | --- |
| Q1 | `seen_count` 분포 — ≥5일 원장에서 `seen_count>=2`인 candidate 비율은? 재출현이 실제로 발생하는가? | 재출현이 유의미(≥~10%)하면 랭킹 1키 = `seen_count` desc. 사실상 0이면 v1 랭킹에서 seen_count를 빼고 당일-신선도(당일 원장 존재) + tie-break만 사용 |
| Q2 | per-source 이미지 점유율 — yonhap-market / yahoo-finance-news / theblock-crypto 중 어디가 지배적인가? 세그먼트별(us/crypto/domestic) 당일 후보 수 분포는? | 세그먼트별 후보-부재 처리(카드 생략 vs 소스 확장 선행), 소스 편중 시 per-source cap 필요 여부 |
| Q3 | credit 가용률 — `image_credit` non-null 비율은? (2026-07-16 Yahoo 녹화에서는 `media:credit` 전부 empty였다) | 링크 카드의 크레딧 줄 설계: credit 부재 시 `source_name` 표기로 대체할지, 줄 자체를 생략할지 |
| Q4 | `image_width/height/mime` 가용률과 분포 — 히어로로 쓸 만한 해상도(예: width≥600) 판별이 메타데이터만으로 가능한가? | cleared 히어로 적합성 필터(최소 폭)의 도입 여부와 값 |
| Q5 | 160자 캡 이후 `item_title` 길이·품질 분포 — 당일 §② 헤드라인과 중복되는 제목 비율은? | 카드 제목 절단 정책(u131 sentence-boundary helper 재사용 여부) + 본문-중복 제목 스킵 규칙 |
| Q6 | cleared 모수 — 운영자 클리어런스가 실제로 몇 건 작성됐는가? (0건이면 히어로 경로는 픽스처로만 검증되고 프로덕션에서는 dark로 출시) | 히어로 경로의 프로덕션 검증 계획(클리어런스 1건 확보 후 수동 확인 run) |

Step 0의 답과 고정된 상수는 FD `business-rules.md`에 R번호로 기록한다.

## Problem Statement

u136+u137로 이미지 후보는 날짜별 원장·재출현 인덱스·(클리어 시) 바이너리 store까지 영속화되지만, **독자 표면에는 아무것도 나타나지 않는다**. `_HERO_PRIORITY`의 1순위 슬롯 `external-context-image`는 u19 런타임 스크래핑(정책상 off)만이 유일한 생산자라 사실상 영구 공석이고, metadata-only 후보(대다수)는 어떤 형태로도 활용되지 않는다. 이 유닛은 (1) 원장+인덱스+store에서 세그먼트별 이미지 사용을 **결정적으로 선정**하고, (2) cleared 바이너리를 로컬 복사로 히어로 슬롯에 공급하며, (3) metadata-only 후보를 바이너리 없이 "원문 링크 카드"로 렌더한다.

**법적 전제(binding, u137에서 그대로 승계)**:

> **메타데이터는 전부 수집, 바이너리는 클리어런스 있는 것만.**
> metadata-only 후보는 **어떤 경우에도 바이너리로 재게시되지 않는다** — 링크 카드는 텍스트+링크만 나른다 (이미지 URL 핫링크/`<img>`/`![](…)` 임베드 전부 금지; 핫링크는 바이너리를 시각적으로 재게시하는 것과 같다). 이미지 바이트가 독자 표면(사이트·텔레그램)에 실리는 경로는 cleared store 바이너리뿐이다.

## Existing Coverage / Deduplication (reuse — do NOT rebuild)

- `visuals/assets.py` — `_HERO_PRIORITY`(line 84: `external-context-image` 1순위)와 `_select_hero_index`/`insert_visual_links`는 **무변경**. cleared 복사본이 슬롯에 존재하기만 하면 기존 우선순위가 히어로로 채택한다. `_prepare_curated_context_image`(로컬 바이트 복사→`visual_asset_path`→provenance→`validate_visual_asset`)가 히어로 경로의 구현 템플릿.
- `visuals/image_library.py` — `ledger_path_for`/`read_index`/`RecurrenceIndexEntry`/`store_binary_path`/`store_sidecar_path`/`_STORE_EXTENSIONS`가 선정의 입력 표면. 원장 레코드는 이미 STRICT-sanitized(u137 I2) — 카드 렌더에 추가 새니타이즈 불필요, 단 compliance 스캔은 통과해야 함.
- u19 `_prepare_external_context_image` + `fetch_contextual_external_image` — **무변경 유지**. u141은 같은 슬롯의 **fetch-free 2번째 생산자**를 추가하는 것이며 런타임 스크래핑을 재활성화하지 않는다 (`EXTERNAL_IMAGE_SCRAPING_ENABLED` 기본값·env 게이트 불변).
- u24 provenance — 세그먼트 복사본의 사이드카는 store 사이드카(+클리어런스 매니페스트)의 필드로 `build_external_provenance` 재구성, 캡션은 기존 `provenance_caption` 경로가 자동 표시.
- u86 curated — 별개 채널 유지. 우선순위상 external > curated이므로 cleared 이미지가 있는 날은 curated가 자연스럽게 `## ① 요약` 리포지션(기존 `_SECTION_ANCHORS` 동작)으로 밀린다. `assets.py`의 "external은 정책상 disabled" 주석만 현행화.
- 모듈 경계 — 선정·카드 렌더는 `visuals/` 신규 모듈, 호출은 orchestrator만. sources/briefing/publisher/notifier와 상호 import 없음.

## Scope Boundary

In scope:
- 결정적 선정 함수(세그먼트별): 당일 원장(파일 진실) + 재출현 인덱스 + store 존재 여부 → `cleared 히어로 후보 0..1개` + `링크 카드 후보 0..1개`.
- cleared 히어로 경로: store 바이너리 → 세그먼트 asset 디렉터리 복사(`external-context-image`) + provenance + 기존 검증.
- 원문 링크 카드 렌더러 + 세그먼트 markdown 주입 (`## ② 전일 핵심 이슈` 하단, 첫 화면 밖).
- orchestrator 배선: 이미지 stage(원장→인덱스→fetch)를 visuals prep **앞으로** 이동 + 선정 결과 전달, 실패 격리.

Out of scope (명시적 non-goal):
- **Telegram 이미지 배달** — u142 (별도 유닛).
- 선정 휴리스틱 v2(perceptual similarity, 다중 카드, 세그먼트당 >1 이미지) — v1은 세그먼트당 히어로 0..1 + 카드 0..1.
- og:image 페이지 enrichment / Reddit 등 신규 소스 — u137 Deferred 그대로.
- rights 상태기계·클리어런스 계약 변경, `EXTERNAL_IMAGE_SCRAPING_ENABLED` 기본값 변경, u86 curated 정책 변경.
- 과거 아카이브 소급 삽입 — 신규 run부터만.

**Slice discipline (u136/u137 기준)**: 선정+히어로+카드를 한 유닛으로 묶는 이유 — 세 조각이 동일한 선정 출력 하나를 소비하고, 히어로 경로는 u86 패턴의 ~40줄 복사 수준이라 단독 유닛 가치가 없다. 단, **Step 3(링크 카드)는 절단 가능선**: Step 0 데이터 분석(Q3/Q5)이 카드 설계 재작업을 요구하면 Step 1-2+4(선정+히어로)만으로 이 유닛을 닫고 링크 카드를 후속 유닛으로 분리한다. 분리 시 이 계획에 절단 기록을 남기고 audit.md에 항목을 추가한다.

## Stage Decision

- **Functional Design — REQUIRED (lightweight)**: 신규 결정적 선정 계약(랭킹 키, tie-break, 세그먼트 스코프, cleared/metadata-only 분기)과 **재게시 금지 불변식**(metadata-only → 텍스트+링크만)이라는 자체 규칙이 있고, 상수 일부가 Step 0 실데이터 분석으로 결정된다. u137 형식으로 `business-logic-model.md` / `business-rules.md` / `domain-entities.md` 작성, R/E/I 번호 고정 후 개발 착수 (Step 0).
- **NFR Requirements — SKIP (planned)**: 신규 의존성·신규 HTTP 호출·신규 시크릿·신규 저장 예산 없음. 히어로 복사는 로컬 바이트 이동이며 기존 파일당 2MB 캡+`validate_visual_asset` 게이트 안이고, 날짜별 세그먼트 asset 커밋 증가는 curated/AI 히어로가 이미 확립한 기존 패턴이다(u137 store 50MB 예산과는 별개 표면, 예산 변경 없음). R13은 원장 레코드가 이미 u137 스크리닝을 통과한 값만 담으므로 신규 표면 없음. 링크 카드는 순수 문자열 렌더. 구현 중 이 전제가 깨지면(예: 히어로 적합성 판단에 이미지 라이브러리 의존성이 필요해지는 경우) planner에 보고하고 NFR 재결정.

## Fixed Contracts

1. **선정 함수** — 신규 `visuals/image_selection.py`:
   `select_image_usage(segment, *, target_date, ledger_root, store_root) -> ImageUsageSelection`
   - 입력은 전부 **파일 진실**: 당일 원장 `ledger_path_for(target_date)`의 해당-세그먼트 레코드 + `read_index()` + `store_binary_path` 존재 확인. rights는 인덱스 표시값이 아니라 store 파일+사이드카 존재로 판정한다(u137 I7/I14 정신 — 인덱스는 후보 우주만 공급).
   - `ImageUsageSelection`(frozen dataclass): `hero_candidate: ImageCandidateRecord | None`(store에 바이너리+사이드카가 있는 cleared 후보), `card_candidate: ImageCandidateRecord | None`(metadata-only 후보; hero로 채택된 candidate_id는 제외), `reason: str`(진단용, sanitized).
   - **결정성**: 동일 원장/인덱스/store → 바이트 동일 출력. 랭킹 키는 Step 0 Q1 답으로 고정하되 tie-break 사슬은 지금 고정: `(랭킹 키…, first_seen asc, candidate_id lexical)` (u86 `select_curated_asset`의 priority→lexical 선례). wall clock 금지 — `target_date`만 사용.
   - 세그먼트당 hero ≤1, card ≤1 (v1 캡).
2. **히어로 경로** — `visuals/assets.py`에 `_prepare_curated_context_image` 미러인 `_prepare_stored_context_image` 추가:
   - `store_binary_path`의 바이트를 `visual_asset_path(target_date, segment, "external-context-image", extension)`으로 복사(`_STORE_EXTENSIONS` = `.png`/`.jpg`만), store 사이드카+클리어런스 매니페스트 필드로 `build_external_provenance` 작성, `validate_visual_asset` 통과. **외부 fetch 0회** (로컬 바이트만).
   - `_HERO_PRIORITY` / `_select_hero_index` / `insert_visual_links` **무변경** — 슬롯 1순위가 이미 `external-context-image`다.
   - 같은 세그먼트에서 store 복사본이 생산되면 u19 `_prepare_external_context_image`(런타임 스크래핑 경로) 호출을 **스킵**한다(동일 kind 이중 생산 방지; 스크래핑 경로 자체는 무변경·env-off 유지).
3. **원문 링크 카드** — 신규 렌더러(같은 `visuals/image_selection.py` 내 순수 함수) + orchestrator 주입:
   - 형태(텍스트+링크만): 마커 라인 `> **📷 오늘의 시장 이미지(원문)**` + `> {item_title} — {credit 또는 source_name} · [원문 보기]({item_url})`. 링크는 **기사 페이지 `item_url`만** — `image_url`은 어떤 형태(마크다운 이미지, `<img>`, 일반 링크 포함)로도 출력 금지 (CDN 이미지 직링크 = 재게시 등가).
   - 마커는 u40 `> **용어 가이드**` / u76 `> **그래서 의미는?**` / u52 carryover와 lexically disjoint. 주입은 idempotent(재실행 시 교체) — u76 `normalize_meaning_lines` 방식.
   - 위치: `## ② 전일 핵심 이슈` 첫 블록 뒤 (u61/u71 첫 화면 밖 — reflow 무간섭). 세그먼트당 ≤1.
   - 주입 시점: visuals prep 이후, reader-format 체인 **이전** (u52/u50 주입 선례와 동일 슬롯) — u56 `scan_compliance`와 u112 polish 게이트가 카드 텍스트를 검증하게 된다.
4. **파이프라인 순서 재배선** — 현재 `_run_image_candidate_stage`(원장→인덱스→fetch)는 `_stage_prepare_segment_visual_assets` **이후**에 실행된다(pipeline.py ≈2632/2659) — 이대로면 당일 확보 바이너리가 당일 히어로에 못 실린다. 계약: 이미지 stage를 visuals prep **앞으로** 이동(스레드 오프로드·실패 격리·run-trace note·publish git-add 합류 전부 보존), 그 다음 세그먼트별 `select_image_usage` 실행 → `prepare_segment_visual_assets`에 `curated_selection`과 같은 방식의 optional kwarg로 전달. 이동으로 u137 AC-137.4(이미지 stage 실패 무전파) 통합 테스트가 계속 성립함을 회귀로 재고정한다.
5. **실패 격리** — 선정/복사/카드 주입의 어떤 예외도 시황 생성·게시를 실패시키지 않는다: WARN + stage note 후 기존 히어로 체인(curated→AI→data-confidence)과 카드-없음으로 fall through.
6. **재게시 금지 회귀 고정** — (a) metadata-only 후보만 있는 픽스처에서 세그먼트 asset 디렉터리·rendered markdown에 이미지 바이트/`image_url` 참조가 0건 — `INVESTO_EXTERNAL_IMAGE_ASSETS=1` 조합 포함 전 조합에서, (b) cleared 픽스처에서만 `external-context-image` 복사본 생성, (c) 신규 무조건 HTTP 호출 0 (httpx spy).

## Implementation Steps

### Step 0 — 원장 데이터 분석 + FD 작성 (planner + developer) `[ ]`
- [ ] ≥5 dates 원장 실데이터로 Q1-Q6에 답하고 선정 상수(랭킹 키, 히어로 적합성 필터, 카드 credit 정책, 제목 절단) 확정. 분석 요약은 FD에 부록으로.
- [ ] FD 3문서 작성, R/E/I 번호 고정. Step 3 절단 여부(Q3/Q5 결과) 결정·기록.
- **Acceptance**: 개발자가 계약 번호를 인용해 착수 가능; 선정 상수에 "TBD" 0건.

### Step 1 — 선정 함수 + `ImageUsageSelection` `[ ]`
- [ ] `visuals/image_selection.py`: 계약 #1. 파일-진실 판정, 결정성, 캡.
- **Acceptance**: 다일 픽스처 원장/인덱스/store에서 결정적 선정(동일 입력 → 동일 출력 바이트 비교), cleared-없음/후보-없음/세그먼트-없음 각 fall-through, wall-clock 미사용.

### Step 2 — cleared 히어로 복사 경로 `[ ]`
- [ ] `_prepare_stored_context_image` + `prepare_segment_visual_assets` optional kwarg 배선 + u19 경로 스킵 조건 (계약 #2).
- **Acceptance**: cleared 픽스처에서 세그먼트 복사본+provenance 사이드카 생성·`_select_hero_index`가 히어로로 채택(우선순위 테이블 무변경 assert), 캡션에 attribution 노출, 외부 fetch 0회(httpx spy), 계약 #6(a)/(b) 회귀 고정.

### Step 3 — 원문 링크 카드 렌더러 + 주입 `[ ]`
- [ ] 렌더러(순수 함수) + orchestrator 주입 (계약 #3). `image_url` 비출력 정적 assert 포함.
- **Acceptance**: 카드 idempotent 주입(재실행 교체), 마커 disjoint 테스트, `## ②` 부재 시 생략(첫 화면 불침범), compliance/polish 게이트 통과, `image_url` 문자열이 rendered markdown에 0회 출현 회귀 고정.

### Step 4 — 파이프라인 순서 재배선 + 실패 격리 `[ ]`
- [ ] 이미지 stage 이동 + 선정 배선 (계약 #4), stage 예외 → WARN + 기존 체인 fall-through (계약 #5).
- **Acceptance**: 강제 예외 주입 통합 테스트에서 3세그먼트 게시 정상(u137 AC-137.4 재고정 포함), run trace에 선정 결과 기록, stage 순서 이동 후에도 원장/인덱스/store 산출 동일.

### Step 5 — full gate + 문서 `[ ]`
- [ ] ruff / mypy --strict / pytest / mkdocs build --strict / `check_no_paid_apis` / `check_image_store`.
- [ ] CONTRIBUTING 런북에 "클리어된 이미지가 히어로로 나가기까지" 흐름 1절(클리어런스 작성→다음 run fetch→그다음 선정) 추가.
- **Acceptance**: 게이트 그린; Q6이 cleared=0이면 프로덕션 dark-launch 사실과 수동 검증 계획을 code/summary.md에 기록.

## Acceptance Criteria (unit-level)

- AC-141.1: 동일 원장/인덱스/store 입력에 대해 선정과 렌더 출력이 결정적이다(재실행 바이트 동일).
- AC-141.2: cleared store 바이너리가 있는 세그먼트는 로컬 복사만으로 `external-context-image` 히어로가 게시되고(우선순위 테이블 무변경), provenance 캡션에 attribution이 노출된다.
- AC-141.3: metadata-only 후보는 어떤 플래그 조합에서도 바이너리·핫링크로 재게시되지 않는다 — rendered markdown에 `image_url` 0회, 세그먼트 asset에 신규 바이트 0건 (회귀 고정).
- AC-141.4: 링크 카드는 제목+크레딧(또는 소스명)+원문 링크만 담고, `## ②` 하단에 세그먼트당 최대 1개, idempotent하게 주입되며 compliance/polish 게이트를 통과한다.
- AC-141.5: 선정/복사/주입 실패가 시황 생성·게시를 실패시키지 않고 기존 히어로 체인으로 degrade한다.
- AC-141.6: 이 유닛은 신규 무조건 HTTP 호출을 추가하지 않으며 u19 런타임 스크래핑 경로와 env 게이트 기본값을 변경하지 않는다.

## Deferred / Roadmap (이번에 만들지 않고 기록만)

| 항목 | 분류 | 근거 |
| --- | --- | --- |
| Telegram 이미지 배달 (`sendPhoto`) | 후속 유닛 u142 | 이 유닛의 히어로 세그먼트 복사본이 u142의 입력 |
| 세그먼트당 다중 카드 / 카드 갤러리 | defer | v1 캡(≤1)으로 독자 소음·법적 표면 최소화; Q2 데이터로 재평가 |
| perceptual-hash 유사 이미지 dedup | defer | u137 Deferred 승계 — seen_count가 URL-hash 동일성 기준으로도 유용한지부터 확인 |
| og:image enrichment / Reddit 어댑터 | defer | u137 Deferred 승계 (후보 부족이 Q2에서 확인되면 별도 유닛) |
