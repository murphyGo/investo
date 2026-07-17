# Code Generation Plan: `u137 image-candidate-registry-and-licensed-store`

**Date**: 2026-07-17
**Unit**: u137 image-candidate-registry-and-licensed-store
**Stage**: Code Generation
**Status**: In Progress (3/7: Step 0-2 done, 2026-07-18)
**Source**: 2026-07-17 user feature request — "실제 뉴스/칼럼/커뮤니티 이미지를 **저장해두고** 활용" 중 저장(수집 2단계). u136이 채집한 이미지 메타데이터를 영속 원장으로 굳히고, 재출현(자주 쓰이는 이미지) 추적과 라이선스 게이트 바이너리 저장을 붙인다.
**Estimated Effort**: ~10-14 h (FD/NFR 포함)
**Dependencies**:
- **u136 feed-image-metadata-harvest** (raw_metadata `image_*` 키 — u137의 유일한 후보 입력)
- u19 visuals policy (`ExternalAssetManifest`, `assert_external_asset_allowed`, host allowlist, `INVESTO_EXTERNAL_IMAGE_ASSETS` env 게이트)
- u24 provenance (`build_external_provenance`, `write_manifest`, `sanitize_provenance_text`)
- u86 curated library (deferred-asset 상태기계 I14-I16 선례, `scripts/check_curated_assets.py` CI 게이트 선례)
- u78 filesystem primitives (atomic write 계열 재사용)

---

## Problem Statement

u136 이후에도 이미지 참조는 당일 run의 `raw_metadata` 안에만 존재한다. 뉴스 CDN 이미지 URL은 만료·교체되므로, "저장해두고 활용"하려면 (1) 후보를 **날짜별 원장으로 영속화**하고, (2) 같은 이미지가 여러 날 반복 등장하는지(= 커뮤니티/시장에서 "자주 쓰이는" 이미지 신호) 추적하고, (3) 재게시가 허용되는 것만 바이너리로 확보해야 한다.

**법적 전제(binding)**: 이 저장소는 public GitHub repo이고 산출물은 public Pages + public Telegram으로 나간다. 연합뉴스 피드의 이미지는 로이터/AP 와이어 사진(u136 프로브로 확인), Yahoo/The Block 썸네일도 출판사 저작물이다. u86이 뉴스 사진·밈을 큐레이션 대상에서 제외한 정책 결정은 유효하다. 따라서 u137의 기본 자세는:

> **메타데이터는 전부 수집, 바이너리는 클리어런스 있는 것만.**
> 뉴스/커뮤니티 이미지의 기본 상태는 `metadata-only`(재게시 차단)이며, 운영자가 개별 건의 라이선스를 확인해 매니페스트를 작성한 경우에만 fetch·저장된다. 시황에서의 표시(활용 단계)는 저장된 클리어 이미지 또는 "원문 링크 카드"(바이너리 비보유) 방식으로 후속 유닛이 다룬다.

## Existing Coverage / Deduplication (reuse — do NOT rebuild)

- `visuals/policy.py` — `ExternalAssetManifest`(kind/source_url/license/attribution/author/fetched_on/allowed_use), `assert_external_asset_allowed`(scraping 게이트), `assert_external_image_host_allowed`, `_assert_public_http_url`. **수정 최소화**: 신규 매니페스트 클래스 금지. `EXTERNAL_IMAGE_SCRAPING_ENABLED` 전역 기본값은 False 유지 — fetch는 기존 `external_image_scraping_enabled()` env 경로(`INVESTO_EXTERNAL_IMAGE_ASSETS=1`) + per-candidate 클리어런스의 이중 게이트.
- `visuals/external_image.py` — `_fetch_manifest_image` / `_extension_for_image`(PNG/JPEG 시그니처, 100B–2MB 캡). fetch 내부 기계를 재사용할 수 있게 필요한 최소만 공개화(private 복제 금지).
- `visuals/provenance.py` — 저장 바이너리의 사이드카는 `build_external_provenance` + `write_manifest` 재사용.
- u86 `visuals/curated.py` + `scripts/check_curated_assets.py` — 상태기계·CI 게이트의 형태 선례. curated 라이브러리 자체는 별개 채널로 유지(사전 큐레이션 스톡/PD vs 데일리 뉴스 후보). 운영자가 뉴스 이미지 대신 라이선스 클린 대체 이미지를 확보하면 그것은 u86 라이브러리로 들어가는 게 맞다 — u137 저장소는 "그 날의 실제 기사 이미지" 전용.
- `_internal/archive_layout.py` — `archive/_meta/` 경로 규칙(run_traces 선례) 재사용.
- 모듈 경계 — 원장/저장 로직은 `visuals/` 하위 신규 모듈(`visuals/image_library.py`)로 두고 orchestrator만 호출한다. sources/briefing/publisher/notifier와 상호 import 없음.

## Scope Boundary

In scope:
- 날짜별 이미지 후보 원장(JSONL) + 재출현 인덱스.
- rights 상태기계(`metadata-only`/`cleared`/`blocked`) + 운영자 클리어런스 파일 계약.
- 클리어된 후보에 한한 content-addressed 바이너리 store + provenance 매니페스트.
- 파이프라인 stage 배선(실패 격리) + CI 게이트 스크립트.

Out of scope (명시적 non-goal):
- **시황 본문/히어로/텔레그램에의 이미지 삽입** — 활용 단계 후속 유닛(아래 Roadmap).
- og:image 페이지-fetch enrichment (CNBC/Nasdaq) — defer.
- 커뮤니티 소스 어댑터(Reddit 등) — defer (아래 Deferred Candidates).
- perceptual-hash(유사 이미지) dedup — v1은 URL-hash 동일성만. 필요 시 TECH-DEBT 후보로 기록.
- `EXTERNAL_IMAGE_SCRAPING_ENABLED` 전역 기본값 변경, u86 curated 정책 변경.

## Stage Decision

- **Functional Design — REQUIRED (lightweight)**: 신규 영속 아티팩트(원장/인덱스/store) + rights 상태기계 + 클리어런스 계약이라는 자체 불변식이 있다. u86 형식으로 `business-logic-model.md` / `business-rules.md` / `domain-entities.md` 작성 (R/E/I 번호 고정 후 개발 착수).
- **NFR Requirements — REQUIRED (focused)**: (a) **저장 예산** — public repo/Pages 크기 증가 상한 AC(파일당 기존 2MB 캡 재사용 + store 총량 상한, 기본 50MB, 초과 시 CI 게이트 실패), (b) **라이선스 컴플라이언스 CI 게이트 AC** — store의 모든 바이너리에 유효 매니페스트+클리어런스, 고아 파일 금지, (c) **R13** — 원장/매니페스트/로그에 시크릿 값 금지, (d) 신규 의존성 없음(TS 항목으로 기록; pillow 불필요 — 기존 시그니처 파싱 재사용).

## Fixed Contracts

1. **원장 (candidate ledger)** — `archive/_meta/image_candidates/{YYYY}/{YYYY-MM-DD}.jsonl`, 1행 = 1 `ImageCandidateRecord`:
   - `candidate_id` = sha256(정규화 URL: scheme/host lowercase, fragment 제거) hex
   - `image_url`, `source_name`, `segment`, `item_url`, `item_title`(sanitize + 160자 캡), `image_width/height/mime/credit`(u136 키 그대로), `collected_on`(target date — wall clock 금지)
   - pydantic frozen / `extra="forbid"` / 전 문자열 필드 `sanitize_provenance_text` 통과 (R13)
2. **재출현 인덱스** — `archive/_meta/image_candidates/index.json` (atomic rewrite): `candidate_id` → `{first_seen, last_seen, seen_count, sources: [source_name…], rights_state}`. `seen_count`가 "자주 쓰이는 이미지" 신호의 v1 정의(동일 URL 재등장 횟수)다.
3. **rights 상태기계** (u86 I14-I16 스타일, 명시적 상태만 허용):
   - `metadata-only` (기본) — 바이너리 fetch/저장 금지.
   - `cleared` — 운영자가 `archive/_meta/image_candidates/clearances/{candidate_id}.manifest.json`에 완전한 `ExternalAssetManifest`(kind=`explicit-license`)를 작성한 경우에만. 매니페스트 필드가 곧 클리어런스 증빙.
   - `blocked` — 운영자 명시 차단(`{candidate_id}.blocked` 마커). 재등장해도 fetch 후보에서 영구 제외.
   - 상태 전이는 운영자 파일 배치로만 발생(코드가 자동 승격 금지). 인덱스는 파일 존재를 반영만 한다.
4. **바이너리 store** — `assets/images/{candidate_id[:2]}/{candidate_id}{.ext}` + 사이드카 `…​.provenance.json`(u24 `write_manifest`):
   - fetch 조건 = `cleared` AND `external_image_scraping_enabled()`(env opt-in) AND `assert_external_asset_allowed` AND host allowlist 통과.
   - 바이너리 검증 = 기존 `_extension_for_image` 시그니처/바이트 캡 재사용. 실패 시 저장 안 함 + WARN.
   - content-addressed이므로 재fetch는 자연 idempotent. bytes sha256이 URL-hash와 별도로 매니페스트에 기록된다.
5. **파이프라인 stage** — `orchestrator/pipeline.py`에 세그먼트 라우팅 후 stage 추가: routed items → 후보 추출(원장 append) → 인덱스 갱신 → cleared fetch. **실패 격리**: 이 stage의 어떤 예외도 시황 생성/게시를 실패시키지 않는다(WARN 로그 + 커버리지 진단 1행). 산출 파일 경로는 기존 publish 스테이징(`git add` 대상 목록)에 합류.
6. **CI 게이트** — 신규 `scripts/check_image_store.py` (`check_curated_assets.py` 미러, stdlib only):
   - store의 모든 바이너리에 유효 provenance 사이드카 + 대응 클리어런스 매니페스트 존재
   - 고아 바이너리/고아 사이드카/미인식 확장자 실패
   - 파일당 2MB / store 총량 50MB 예산 (NFR AC 번호로 고정)
   - R13 스캔(시크릿 패턴)
   - GHA quality 워크플로에 편입 (investo-ops 표면).

## Implementation Steps

### Step 0 — FD + NFR 작성 (planner) `[x]`
- [x] FD 3문서 + NFR 2문서, R/E/I/AC 번호 고정 (Stage Decision 참조).
- **Acceptance**: 개발자가 계약 번호를 인용해 착수 가능.

### Step 1 — `ImageCandidateRecord` + 원장 쓰기 `[x]`
- [x] `visuals/image_library.py`: 모델 + `append_candidates(target_date, items) -> LedgerWriteReport` (u136 키 없는 item 스킵; 동일 run 내 동일 candidate_id 1회).
- 구현 시 I2/R4 divergence ratified (2026-07-18): u27 STRICT sanitizer가 64-hex/쿼리스트링/장문 URL 경로를 redact해 I1/I9 해시 정체성을 깨므로, `candidate_id`(regex-lock)·URL 필드는 rewrite 대신 **fail-closed 스크리닝**(SECRET_ENV_VARS + scan_for_leak 히트 시 후보 전체 드롭). 텍스트 필드는 STRICT chokepoint 유지. audit.md 기록 필요.
- **Acceptance**: 픽스처 items로 결정적 JSONL 산출(키 순서/정렬 고정), 재실행 idempotent.

### Step 2 — 재출현 인덱스 + rights 상태 반영 `[x]`
- [x] `update_index(target_date) -> IndexReport`: 원장 스캔 → seen_count/last_seen 갱신, clearances/blocked 파일 → rights_state 반영.
- **Acceptance**: 3일치 픽스처 원장에서 재출현 카운트 정확, 상태 파일 배치/제거가 인덱스에 반영, atomic rewrite 검증.

### Step 3 — 라이선스 게이트 fetch + store `[ ]`
- [ ] `fetch_cleared_candidates(...)`: 계약 #4의 4중 조건, `external_image.py` fetch 기계 재사용(필요 최소 공개화), provenance 사이드카 작성.
- **Acceptance**: cleared+env-on만 fetch 시도(httpx mock 감시), metadata-only/blocked은 어떤 조합에서도 fetch 0회 — 회귀 테스트 고정; 시그니처 불일치/2MB 초과 저장 거부.

### Step 4 — orchestrator stage 배선 + 실패 격리 `[ ]`
- [ ] stage 추가(계약 #5), 산출 경로 publish 스테이징 합류, stage 예외 → WARN + 파이프라인 계속.
- **Acceptance**: stage 강제 예외 주입 통합 테스트에서 시황 3세그먼트 게시 정상 완료; run trace에 이미지 stage 결과 기록.

### Step 5 — CI 게이트 스크립트 + 워크플로 편입 `[ ]`
- [ ] `scripts/check_image_store.py`(계약 #6) + 워크플로 스텝(investo-ops).
- **Acceptance**: 정상 store 통과 / 주입된 고아·무매니페스트·예산 초과 픽스처 각각 명확한 메시지로 실패.

### Step 6 — full gate + 문서 `[ ]`
- [ ] ruff / mypy --strict / pytest / mkdocs build --strict / `check_no_paid_apis` / 신규 게이트.
- [ ] CONTRIBUTING 운영 런북에 클리어런스 절차(운영자가 매니페스트 작성하는 법 + 법적 기준: 재게시 가능 근거가 확인된 경우만) 1절 추가.
- **Acceptance**: 게이트 그린, 런북에 클리어런스 예시 1건.

## Acceptance Criteria (unit-level)

- AC-137.1: 이미지 보유 item이 있는 run은 날짜별 원장 JSONL과 갱신된 재출현 인덱스를 남긴다.
- AC-137.2: 바이너리는 `cleared`+env opt-in+정책 통과 조합에서만 저장되며, 기본 상태에서는 저장이 0건이다.
- AC-137.3: store의 모든 바이너리는 provenance 사이드카와 클리어런스 매니페스트를 갖고 CI 게이트가 이를 강제한다.
- AC-137.4: 이미지 stage 실패가 시황 생성·게시를 실패시키지 않는다.
- AC-137.5: 저장 예산(파일 2MB / 총 50MB)과 R13이 게이트로 강제된다.
- AC-137.6: 동일 이미지 URL의 다일 재출현이 `seen_count`로 조회 가능하다.

## Deferred Candidates (이번에 만들지 않고 기록만)

| 후보 | 분류 | 근거 (2026-07-17 검증) |
| --- | --- | --- |
| CNBC/Nasdaq og:image 페이지 enrichment | defer | 피드에 이미지 없음 → 기사 HTML fetch 필요 = per-item 추가 HTTP + 스크래핑 성격. 후보 부족이 확인되면 host-allowlist 기반 bounded fetcher로 별도 유닛 |
| Reddit(r/wallstreetbets 등) 커뮤니티 이미지 | defer | 비인증 `/.json` 차단 확인(라이브 프로브). Data API OAuth 등록 + free-tier 조건 검토 필요. 밈 이미지는 rights 기본 `metadata-only`로도 재게시 불가 — 활용 형태(링크 카드) 설계와 함께 재평가 |
| 국내 커뮤니티(디시·클리앙 등) | reject(현시점) | 구조화 피드 부재, 스크래핑 전용, 저작권·초상권 리스크 최고 |
| perceptual hash dedup | defer | v1 URL-hash로 충분. 재출현 신호가 유용해지면 TECH-DEBT로 승격 |

## Roadmap (활용 단계 — 후속 유닛, 이 계획의 산출물 아님)

1. **선정·삽입 유닛**: 재출현 인덱스 + 당일 후보에서 히어로/섹션 이미지를 결정적으로 선정, cleared 바이너리는 기존 `_HERO_PRIORITY`의 `external-context-image` 슬롯으로, metadata-only 후보는 "원문 링크 카드"(제목+크레딧+링크, 바이너리 비게시)로 렌더.
2. **Telegram 이미지 배달 유닛**: `notifier/_telegram.py`에 `sendPhoto` 경로 신설(현재 sendMessage만 존재), cleared 이미지 한정.
