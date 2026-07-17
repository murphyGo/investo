# Code Generation Plan: `u136 feed-image-metadata-harvest`

**Date**: 2026-07-17
**Unit**: u136 feed-image-metadata-harvest
**Stage**: Code Generation
**Status**: In Progress (4/5)
**Source**: 2026-07-17 user feature request — 시황 비주얼을 SVG 카드 중심에서 "실제 뉴스/칼럼/커뮤니티 이미지 활용"으로 확장. 1단계는 **이미지 수집 + 이미지 메타데이터**. u136은 그 첫 슬라이스: 이미 수집 중인 뉴스 피드 payload 안의 이미지 참조를 메타데이터로 채집한다.
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u1 sources (RSS adapter family + `_xml_namespaces.py` + defusedxml 규칙)
- u19 briefing-visual-assets (`visuals/external_image.py`의 `_IMAGE_URL_KEYS` 키 계약 — 키 이름 정렬 대상, 호출 대상 아님)
- u10 source coverage diagnostics (per-source `source returned` INFO 레코드 — image 카운트 필드 추가 지점)

---

## Problem Statement

시황의 이미지가 현재 전부 생성형(SVG 카드 / OG 카드 / 선택적 AI 히어로)이다. 실제 기사 이미지를 쓰려면 후보 이미지가 어디에 있는지부터 알아야 하는데, 지금은:

- `NormalizedItem`에 이미지 필드가 없고 어떤 어댑터도 `raw_metadata`에 이미지 URL을 넣지 않는다.
- RSS 어댑터들은 `<media:content>` / `<media:thumbnail>` 네임스페이스 요소를 **명시적으로 버린다** (`yonhap_market.py` docstring, `sec_edgar_8k.py` docstring).
- `visuals/external_image.py`는 `raw_metadata`의 `image_url`/`thumbnail_url` 등을 읽을 준비가 되어 있으나(휴면 스캐폴딩), 공급자가 없어 영구 no-op이다.

즉 **후보 이미지 메타데이터의 공급 파이프가 없다**. u136은 추가 HTTP 요청·바이너리 다운로드·페이지 스크래핑 없이, 이미 fetch한 피드 XML에서 이미지 참조만 뽑아 `raw_metadata`에 싣는다.

## Verified Source Facts (2026-07-17 라이브 프로브)

| Feed (기존 어댑터) | 이미지 요소 | 비고 |
| --- | --- | --- |
| `yonhap-market` `https://www.yna.co.kr/rss/market.xml` | `<media:content url=… type="image/jpeg">` | 로이터/AP/AFP 통신 사진(`img.yna.co.kr/photo/{reuters,ap,…}/…`) — **저작권 있는 와이어 사진**. 메타데이터 수집은 안전, 재게시는 u137 게이트 대상 |
| `yahoo-finance-news` `https://finance.yahoo.com/news/rssindex` | `<media:content url=… width=… height=…>` + `<media:credit role="publishing company">` | zenfs CDN 썸네일(예: 130×86) + 크레딧 텍스트 |
| `theblock-crypto` `https://www.theblock.co/rss.xml` | `<media:thumbnail url=… width="800" height="450">` | 자체 CDN(tbstat.com) 800×450 |
| `cnbc-top-news` | 없음 | per-item 이미지 요소 없음 — **u136 범위 외** (og:image 페이지 fetch는 명시적 defer) |
| `nasdaq-stocks-news` | 없음 | 동일 |

Media RSS 네임스페이스: `http://search.yahoo.com/mrss/`.

## Existing Coverage / Deduplication (reuse — do NOT rebuild)

- `sources/_xml_namespaces.py` — Clark-notation 네임스페이스 상수의 단일 등록처. `MEDIA_NS` 계열 상수를 여기에 추가한다 (어댑터 로컬 문자열 금지).
- `visuals/external_image.py::_IMAGE_URL_KEYS` — `("visual_image_url", "image_url", "thumbnail_url")`. u136은 이 중 `image_url` 키로 기록해 **키 계약을 정렬**한다. 이 모듈을 호출하거나 수정하지 않는다.
- `visuals/policy.py` — 수정하지 않는다. `EXTERNAL_IMAGE_SCRAPING_ENABLED=False` 유지.
- u86 curated library — 별개 채널(사전 큐레이션 정적 라이브러리). u136은 데일리 뉴스 흐름의 후보 채집이며 서로 대체하지 않는다.
- R8 raw_metadata 규칙 — strings/ints/floats only, no nesting; 기존 어댑터 `raw_metadata["creator"]` 패턴을 따른다.

## Scope Boundary

In scope:
- Media RSS 이미지 요소 추출 공용 헬퍼 1개.
- 이미지를 싣는 것으로 검증된 3개 어댑터(`yonhap-market`, `yahoo-finance-news`, `theblock-crypto`)의 `raw_metadata` 확장.
- per-source 커버리지 진단에 이미지 보유 아이템 수 노출.
- 라이선스 키 비오염 불변식(아래 Fixed Contracts #4)의 회귀 테스트 고정.

Out of scope (명시적 non-goal):
- 이미지 바이너리 fetch/저장 — **u137**.
- 기사 HTML 페이지를 열어 `og:image`를 얻는 enrichment (CNBC/Nasdaq 커버) — 추가 HTTP + 스크래핑 성격 → defer (u137 non-goal에도 재기재).
- 커뮤니티 소스(Reddit 등) 신규 어댑터 — 비인증 JSON 차단 확인(2026-07-17), OAuth 등록 필요 → defer.
- `NormalizedItem` 모델에 typed image 필드 추가 — `raw_metadata`로 충분하며 frozen/extra=forbid 모델 파급이 큼.
- 시황 본문/텔레그램 이미지 삽입 — 활용 단계 후속 유닛.

## Stage Decision

- **Functional Design — SKIP (confirmed)**: 기존 어댑터에 대한 bounded 메타데이터 추출 확장. 신규 엔티티·상태기계·라우팅 변화 없음 (u126 선례).
- **NFR Requirements — SKIP (confirmed)**: 신규 외부 호출/의존성/시크릿/비용 없음 — 이미 받는 payload 바이트에서 추출만 한다. R8/R13은 기존 규칙 적용.

## Fixed Contracts

1. **네임스페이스 상수** — `sources/_xml_namespaces.py`:
   `MEDIA_NS = "{http://search.yahoo.com/mrss/}"`, `MEDIA_CONTENT = MEDIA_NS + "content"`, `MEDIA_THUMBNAIL = MEDIA_NS + "thumbnail"`, `MEDIA_CREDIT = MEDIA_NS + "credit"`.
2. **공용 추출 헬퍼** — 신규 `src/investo/sources/_feed_media.py`:
   - `FeedImageRef` (frozen dataclass): `url: str`, `width: int | None`, `height: int | None`, `mime: str | None`, `credit: str | None`.
   - `extract_feed_image(item: Element) -> FeedImageRef | None` — `<media:content>`(이미지 mime 또는 mime 부재+이미지 확장자) 우선, 없으면 `<media:thumbnail>`; **item당 첫 이미지 1개만**; `http(s)` 스킴 필수; URL trim + 길이 캡 1000자; width/height는 int 파싱 실패 시 None; credit은 trim + 240자 캡. defusedxml Element만 입력받는 순수 함수.
3. **raw_metadata 키** (R8 — 값은 StrictStr/StrictInt만):
   `image_url`(str) / `image_width`(int) / `image_height`(int) / `image_mime`(str) / `image_credit`(str). 이미지 없으면 키 자체를 넣지 않는다(부재=키 없음).
4. **라이선스 키 비오염 불변식(안전 계약)** — 어댑터는 `image_license` / `image_attribution` / `image_author` / `image_allowed_use`(및 `visual_image_*`/무접두 동의어)를 **절대 emit하지 않는다**. 피드는 재사용 라이선스를 선언하지 않으므로, 이 키들이 없으면 `external_image._manifest_from_item`이 항상 None을 반환해 — 운영자가 `INVESTO_EXTERNAL_IMAGE_ASSETS=1`을 켜더라도 — 휴면 fetch 경로가 촉발되지 않는다. 회귀 테스트로 고정한다.
5. **어댑터 배선** — 3개 어댑터의 item 파싱 루프에서 `extract_feed_image` 호출 → 존재 시 계약 #3 키를 `raw_metadata`에 병합. 각 어댑터 docstring의 "media 네임스페이스 무시" 문구를 갱신.
6. **진단** — aggregator per-source `source returned` INFO 레코드(u10)에 `image_items=<n>` 필드 추가 (해당 소스 반환 아이템 중 `image_url` 보유 수). 신규 KPI/심각도 없음.

## Implementation Steps

### Step 1 — 네임스페이스 상수 + `_feed_media.py` 헬퍼 `[x]`
- [x] `MEDIA_*` 상수 추가, `extract_feed_image` 구현 (계약 #1, #2).
- [x] 단위 테스트: media:content only / media:thumbnail only / 둘 다(우선순위) / 복수 이미지(첫 번째만) / 비-http URL 거부 / URL 길이 캡 / width·height 비정수 / credit 캡 / 이미지 아닌 media:content(mime=video) 스킵.
- **Acceptance**: 헬퍼가 세 실피드 샘플 XML 조각 전부에서 기대 `FeedImageRef`를 반환하고, 악성/비정형 입력에 None 또는 필드 None으로 안전 강하.

### Step 2 — `yonhap-market` 어댑터 확장 + 픽스처 재녹화 `[x]`
- [x] item 루프에 헬퍼 배선, raw_metadata 병합 (계약 #3, #5).
- [x] R10 라이브 픽스처 재녹화(success에 media:content 포함) + empty/malformed 경로 유지.
- **Acceptance**: 픽스처 replay에서 이미지 보유 item의 raw_metadata에 5개 키가 정확히 존재하고, 이미지 없는 item에는 키가 없다.

### Step 3 — `yahoo-finance-news` + `theblock-crypto` 확장 `[x]`
- [x] 동일 배선. yahoo는 `media:credit` → `image_credit` 매핑 포함, theblock은 thumbnail 경로 검증.
- [x] 각 어댑터 R10 픽스처 재녹화.
- 구현 시 계약 #2 확장(2026-07-17 ratified): yahoo zenfs CDN은 type·확장자 모두 부재 → `_is_image_content`에 "type 부재 + 양의 정수 width+height 쌍" 수용 경로 추가. 라이브 야후 recording의 `media:credit`은 전부 빈 요소 → `image_credit` 부재(합성 XML로 매핑 자체는 고정). audit.md 기록 필요.
- **Acceptance**: Step 2와 동일 기준 ×2. 기존 어댑터 테스트(제목/요약/URL/published_at) 전부 그린 유지.

### Step 4 — 라이선스 키 비오염 회귀 테스트 `[x]`
- [x] 3개 어댑터의 replay 결과에 대해 `_manifest_from_item(item, target_date=…) is None`을 직접 단언 + emit 금지 키 부재 grep-단언 테스트 (계약 #4).
- **Acceptance**: 스크래핑 env 플래그가 켜진 상태를 monkeypatch해도 `fetch_contextual_external_image`가 harvested item만으로는 fetch를 시도하지 않음이 테스트로 고정.

### Step 5 — 커버리지 진단 + 품질 게이트 `[ ]`
- [ ] aggregator `source returned` 레코드에 `image_items` 필드 (계약 #6) + 테스트.
- [ ] full gate: ruff / ruff format(변경 범위) / mypy --strict / pytest / `scripts/check_no_paid_apis.py` / mkdocs build --strict(문서 영향 없음 확인).
- **Acceptance**: 게이트 그린. 신규 외부 호출 0 (httpx mock 감시로 확인).

## Acceptance Criteria (unit-level)

- AC-136.1: 검증된 3개 뉴스 소스의 이미지 보유 item이 `raw_metadata.image_url`(+폭/높이/mime/credit 가용 시)을 싣는다.
- AC-136.2: u136은 어떤 신규 HTTP 요청도 발생시키지 않는다 (피드 fetch 횟수/대상 불변).
- AC-136.3: 라이선스 계열 키는 어떤 어댑터도 emit하지 않으며, 휴면 fetch 경로는 harvested 메타데이터만으로 활성화될 수 없다.
- AC-136.4: per-source 진단에서 이미지 보유 item 수를 확인할 수 있다.
- AC-136.5: R8(문자열/정수, no nesting)·R13(시크릿 없음) 준수, 기존 어댑터 동작 회귀 없음.

## Tests / Validation

- `tests/unit/sources/test_feed_media.py` (신규 — Step 1 매트릭스)
- `tests/unit/sources/test_yonhap_market.py` / `test_yahoo_finance_news.py` / `test_theblock_crypto.py` (확장 + 픽스처 재녹화)
- `tests/unit/visuals/test_external_image.py`에 비오염 불변식 케이스 추가 (Step 4)
- aggregator 진단 테스트 (Step 5)
- `scripts/check_no_paid_apis.py` 통과 (신규 엔드포인트 없음)

## Follow-ups (this unit이 만들지 않는 것)

- **u137 image-candidate-registry-and-licensed-store** — 후보 원장/재출현 추적/라이선스 게이트 바이너리 저장.
- 활용(히어로 선정·본문 삽입·Telegram sendPhoto) — u137 이후 별도 유닛.
- CNBC/Nasdaq og:image enrichment, 커뮤니티 소스 어댑터 — defer (u137 계획서의 Deferred Candidates 참조).
