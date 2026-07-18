# Code Generation Plan: `u142 telegram-image-delivery`

**Date**: 2026-07-19
**Unit**: u142 telegram-image-delivery
**Stage**: Code Generation
**Status**: Planned — implementation gated on candidate-data accumulation (start when the image_candidates ledger holds >=5 distinct dates; check archive/_meta/image_candidates/)
**Source**: u137 Roadmap 항목 2 (활용 단계 — Telegram 이미지 배달 유닛). `notifier/_telegram.py`에 `sendPhoto` 경로 신설(현재 `sendMessage`만 존재), **cleared 이미지 한정**, 공개 채널 전용.
**Estimated Effort**: ~6-8 h
**Dependencies**:
- **u141 image-selection-and-insertion** (세그먼트 히어로 복사본 + provenance 캡션 — u142의 유일한 사진 입력; u141 완료 전 착수 금지)
- u137 licensed store (cleared 바이너리 + 클리어런스 매니페스트 — 사진 바이트의 법적 근거)
- u4/u80 notifier (`_telegram.send_message` retry 기계, `_dispatcher.dispatch` 합성 패턴, kwargs-only 생성자, R5 채널 분리)
- u31 retry 정책 (`retry_budget` 전역 게이트, 429 `Retry-After` 처리)
- u27/R13 (`redact_text` STRICT chokepoint — sendPhoto URL에도 bot token이 들어간다)
- u30 telegram first-impression (기존 요약 메시지 계약 — 무변경 유지 대상)

**추가 착수 조건**: 데이터 게이트(≥5 dates) 외에, u141이 닫혀 있고 **cleared store 바이너리가 ≥1건 존재**할 때(또는 최소한 운영자 클리어런스 절차가 1회 실증됐을 때) 착수한다. cleared 0건 상태에서 이 유닛을 먼저 만들면 프로덕션에서 영구 dark인 코드가 된다.

---

## Problem Statement

시황 텔레그램 알림은 텍스트 요약(`sendMessage`)뿐이다. u141이 cleared 이미지를 사이트 히어로로 게시하게 되면, 같은 이미지를 공개 채널에도 실어 첫인상을 높일 수 있다 — 단 **법적 전제는 사이트와 동일**하게:

> 이미지 바이트가 독자 표면에 실리는 경로는 cleared store 바이너리뿐이다. metadata-only 후보는 텔레그램에서도 **어떤 형태로도 바이너리로 재게시되지 않는다** (사진 업로드·이미지 URL 전달 방식의 `sendPhoto` 포함 — Telegram이 URL을 fetch해 재호스팅하므로 URL 전달도 재게시다). attribution(출처/크레딧)은 사진 캡션에 항상 동반한다.

## Existing Coverage / Deduplication (reuse — do NOT rebuild)

- `notifier/_telegram.py` — `telegram_api_url(bot_token, method)`은 이미 method 파라미터를 받는다(`sendPhoto` URL 구성 무료). `send_message`의 bounded retry 루프(`_MAX_RETRIES`/backoff/`_RETRY_AFTER_CEILING_S`/`retry_budget`)와 `_AttemptOutcome`은 사진 경로가 재사용해야 할 기계 — 사본 금지, 공용 retry 헬퍼로 추출.
- `_redact_bot_token` — sendPhoto의 모든 에러 문자열도 이 shim을 통과한다 (신규 regex 금지, u27 단일 chokepoint 유지).
- `notifier/_dispatcher.dispatch` — markdown→plain fallback은 **텍스트 요약 전용**으로 무변경. 사진 캡션은 fallback 대상이 아니다(캡션은 짧고 deterministic — parse 실패 시 plain 재시도는 사진 경로 안에서 자체 처리).
- `BriefingPublisher` — kwargs-only 생성자 + `dry_run` 계약 유지. 사진도 `dry_run`이면 I/O 0.
- `models/briefing.py` — `BriefingNotification`의 UTF-16 검증 패턴(`utf-16-le` 인코딩 길이/2)이 캡션 1024-unit 캡 검증의 템플릿.
- `visuals/` — notifier는 visuals를 import할 수 없다(모듈 경계). 클리어런스 판정·파일 선택은 전부 orchestrator 쪽(u141 산출물)에서 끝난 상태로 전달받는다.

## Scope Boundary

In scope:
- `_telegram.py`의 `send_photo`(multipart 업로드, 로컬 바이트) + 공용 retry 헬퍼 추출.
- 사진 payload 모델(`models/`): 경로 + 캡션(≤1024 UTF-16 units) + 검증.
- `BriefingPublisher`의 사진 후속-발송 경로(텍스트 요약 발송 후 best-effort).
- orchestrator 배선: u141 히어로 복사본(clearance-backed provenance 확인된 것만) → payload 구성(캡션 = 날짜 + attribution + 상세보기 링크).

Out of scope (명시적 non-goal):
- **이미지 URL 전달형 sendPhoto** — 금지 (위 법적 전제; 업로드 방식만).
- `sendMediaGroup`(다중 사진), OG 카드 PNG(u38)의 사진 발송, 주간 다이제스트 사진 — defer.
- `OperatorAlerter` 변경 — 운영자 chat에는 사진 경로 자체가 존재하지 않는다 (R5).
- 기존 텍스트 요약 메시지(`build_segmented_summary` / `dispatch`) 계약 변경 — 사진이 없거나 실패한 run은 오늘과 바이트 동일하게 동작.
- 텔레그램 전용 이미지 가공(리사이즈/크롭) — store 바이너리(≤2MB, 기존 검증 통과)를 그대로 업로드. Telegram 사진 업로드 캡(10MB)에 여유.

**Slice discipline**: u136/u137 기준으로 단일 유닛 크기다(신규 HTTP 메서드 1개 + 모델 1개 + 배선). 추가 분할 없음.

## Stage Decision

- **Functional Design — SKIP (planned)**: u4/u80 dispatcher 합성 패턴의 연장이며 신규 엔티티는 frozen payload 모델 1개뿐. binding 규칙(cleared-only, 캡션 attribution 동반, R5)은 orchestrator 핸드오프 계약 + unit AC로 고정한다 — 별도 R/E/I 문서가 계약 표면을 늘리지 않는다. 구현 중 상태기계·신규 엔티티가 필요해지면 planner에 보고 후 재결정.
- **NFR Requirements — SKIP (planned)**: 동일 무료 Telegram Bot API의 메서드 추가(신규 API/키/과금 없음), 신규 의존성 없음(httpx multipart 내장), 신규 시크릿 없음(기존 bot token 재사용, R13 chokepoint 통과). 캡션 1024-unit·업로드 크기 캡·retry 예산은 unit AC로 고정(AC-142.5/142.6). 이 전제가 깨지면 재결정.

## Fixed Contracts

1. **`send_photo`** — `notifier/_telegram.py`:
   `async def send_photo(client, *, bot_token, chat_id, photo_bytes, filename, caption, parse_mode=None, sleep=asyncio.sleep) -> SendResult`
   - `telegram_api_url(bot_token, "sendPhoto")` + httpx multipart(`files={"photo": (filename, photo_bytes, mime)}`, `data={"chat_id", "caption", …}`). 비-raising: 실패는 `SendResult(ok=False, error=…)`, 모든 에러 문자열은 `_redact_bot_token` 통과 (R13 — sendPhoto URL도 token을 담는다).
   - retry: `send_message`의 루프를 공용 헬퍼(예: `_send_with_retry(send_once)`)로 추출해 **양쪽이 같은** `_MAX_RETRIES`/backoff/`Retry-After` 캡/`retry_budget` 전역 게이트를 공유한다. 파라미터 상수 사본 금지.
   - 방어적 shape 게이트(업로드 직전): PNG/JPEG magic bytes + 크기 캡(store 상한 2MB ≤ Telegram 10MB) 불일치 시 fetch/업로드 없이 `ok=False`. 시그니처 상수는 visuals import 없이 최소 구현하되, u136 L1/DEBT-082(상수 중복 계열)에 항목 추가로 기록.
2. **사진 payload 모델** — `models/`에 frozen `BriefingPhotoNotification`(가칭): `target_date`, `photo_path`, `caption`(min 1, **≤1024 UTF-16 code units** — `BriefingNotification`의 utf-16-le 검증 패턴 재사용, 신규 상수 `TELEGRAM_CAPTION_LIMIT = 1024`), `extra="forbid"`. 기존 `BriefingNotification`은 무변경(텍스트 계약 동결).
3. **캡션 계약** — deterministic 구성: `📷 {target_date} 시황 이미지` + attribution 줄(u141 provenance 캡션의 sanitized 출처/크레딧 — **항상 포함**, 없으면 사진 발송 자체를 포기) + 상세보기 링크. 시황 본문 요약을 캡션에 복제하지 않는다(1024 캡 + 텍스트 메시지와 중복).
4. **발송 순서·상태 의미** — `BriefingPublisher`에 사진 후속-발송 추가: 기존 요약 `sendMessage`(상태 담지자, AC-003 semantics)가 **먼저**, 성공 시에만 `sendPhoto`를 best-effort 후속 발송. 사진 실패는 로그 note로만 남고 pipeline status(SUCCESS/PARTIAL)를 바꾸지 않는다 — 텍스트 실패 시 사진은 시도조차 하지 않는다(고아 사진 방지). 사진 없는 run(입력 None)은 현재 동작과 바이트 동일.
5. **cleared-only 핸드오프** — orchestrator만이 사진 입력을 만든다: u141 히어로 세그먼트 복사본 중 provenance 매니페스트가 clearance-backed external(u137 store 유래)인 파일만 payload로 승격. curated/AI/data-confidence 히어로는 **사진 발송 대상이 아니다** (v1 — 뉴스 실사진 트랙 전용; curated는 사이트 전용 유지). notifier는 전달받은 파일이 무엇인지 재판정하지 않는다(모듈 경계) — 대신 계약 #1의 shape 게이트 + 회귀 테스트(계약 #6)로 이중 방어.
6. **채널 분리·비재게시 회귀 고정** — (a) `OperatorAlerter`에 사진 API가 존재하지 않음(정적 assert + 테스트), (b) metadata-only-만 있는 run에서 `sendPhoto` 호출 0회 — 전 플래그 조합 (httpx transport spy), (c) 사진 payload에 `image_url`(원본 CDN URL) 필드 자체가 없음 — URL 전달형 발송이 타입 차원에서 불가능.

## Implementation Steps

### Step 1 — retry 헬퍼 추출 + `send_photo` `[ ]`
- [ ] `_send_with_retry` 추출(기존 `send_message` 동작 바이트-동일 회귀 고정) + `send_photo` (계약 #1).
- **Acceptance**: MockTransport로 성공/429(`Retry-After` 헤더·body)/5xx/timeout/`ok:false` 경로 + retry_budget 소진 경로 검증; 에러 문자열 token-redaction 고정; magic-byte/크기 캡 거부 시 HTTP 0회.

### Step 2 — payload 모델 + 캡션 빌더 `[ ]`
- [ ] `BriefingPhotoNotification` + 캡션 구성 함수 (계약 #2/#3).
- **Acceptance**: 1024 UTF-16 초과 거부(이모지 2-unit 케이스 포함), attribution 부재 시 payload 미생성, frozen/extra-forbid, R13(캡션에 시크릿 패턴 불가 — sanitized 입력만).

### Step 3 — `BriefingPublisher` 사진 후속-발송 + orchestrator 배선 `[ ]`
- [ ] 계약 #4/#5: 텍스트 성공 후 best-effort 사진, orchestrator의 clearance-backed 승격 필터, `dry_run` 무-I/O.
- **Acceptance**: 텍스트 실패→사진 미시도, 사진 실패→status 불변(SUCCESS 유지 + note), 사진 없는 run 바이트-동일 회귀, 계약 #6(a)/(b)/(c) 고정, run trace/stage note에 사진 발송 결과 기록.

### Step 4 — full gate + 문서 `[ ]`
- [ ] ruff / mypy --strict / pytest / mkdocs build --strict / `check_no_paid_apis`.
- [ ] CONTRIBUTING 런북: 채널에 사진이 실리는 조건(클리어런스→store→u141 히어로→u142 발송 사슬) + 사진이 안 나가는 정상 사유 목록 1절.
- **Acceptance**: 게이트 그린; cleared 실물 1건으로 수동 검증한 채널 발송 스크린샷 확인(운영자)을 code/summary.md에 기록.

## Acceptance Criteria (unit-level)

- AC-142.1: cleared 히어로가 있는 run은 공개 채널에 attribution 캡션(≤1024 UTF-16)을 동반한 사진이 요약 메시지 **후속으로** 업로드 방식으로만 발송된다.
- AC-142.2: cleared-backed 입력이 없는 run(metadata-only 포함 전 조합)은 `sendPhoto` 호출 0회이며 기존 텍스트 발송과 바이트 동일하게 동작한다.
- AC-142.3: 사진 발송 실패(HTTP/API/shape 거부)는 비-raising이고 요약 `SendResult`·pipeline status를 변경하지 않는다.
- AC-142.4: 사진 경로는 `BriefingPublisher` 전용이다 — `OperatorAlerter`와 운영자 chat에는 사진 표면이 존재하지 않는다 (R5).
- AC-142.5: sendPhoto의 모든 에러/로그 문자열은 bot-token redaction chokepoint를 통과한다 (R13).
- AC-142.6: sendPhoto는 `send_message`와 동일한 bounded retry + 전역 `retry_budget`을 공유하며 상수 사본이 없다.

## Deferred / Roadmap (이번에 만들지 않고 기록만)

| 항목 | 분류 | 근거 |
| --- | --- | --- |
| `sendMediaGroup` 다중 사진 | defer | v1은 히어로 1장 — cleared 모수(u141 Q6)가 커지면 재평가 |
| curated/AI 히어로의 사진 발송 | defer | v1은 뉴스 실사진(clearance-backed) 전용 — 채널 톤·빈도 데이터 본 뒤 결정 |
| OG 카드 PNG(u38) 사진 발송 | defer | 자체 생성물이라 법적 게이트는 없지만 채널 소음 — 별도 판단 |
| 사진 전용 알림 설정(끄기 토글) | defer | 운영 요구 발생 시 env 게이트로 |
