# Code Generation Plan: `u57 segment-narrative-scope-and-time-reconciliation`

**Date**: 2026-05-13
**Unit**: u57 segment-narrative-scope-and-time-reconciliation
**Stage**: Code Generation
**Status**: 📋 Planned (re-hardened to u51 precision, 2026-05-13)
**Source**: 2026-05-13 10-subagent evaluation of `archive/.../2026-05-11.md` segmented bundle; deduplicated against u45/u51/u52/u53/u54/u55/u56.
**Estimated Effort**: ~6-8 h (initial ~3-5 h estimate revised after adding BundleContext pre-computation + deterministic linkage lint).
**Dependencies**:
- u7 segmented-briefing (Stage-2 prompt + segmented generator; 본 unit 의 prompt 룰이 얹힘).
- u45 segment-routing-exclusivity (source-item routing 이 이미 segment 단위로 끊겨 있음; 본 unit 은 routed-after 의 narrative scope 만 책임).
- u52 prior-briefing-context-and-carryover (prior-day event lifecycle 와 분리; BundleContext 는 same-run only).
- u49 deterministic-market-anchor (close-state 판정 시 anchor 의 종가 fact 를 보조 근거로 사용).

---

## Deduplication boundary

Excluded because already owned elsewhere:
- u45: source/item routing exclusivity (입력 단계).
- u51: reader layout / actionability formatting (TL;DR / 표 / H3 / bold).
- u52: prior-day carryover (어제 시황 → 오늘 follow-up).
- u53: 신규 데이터 소스 (KRX 외국인 / 섹터 ETF).
- u54: source-status severity / quality KPI.
- u55: numeric / freshness gates.
- u56: compliance / observational tagging.

This unit owns **same-bundle (= 같은 run 으로 생성된 3 segment) narrative scope and time-state reconciliation** after items are already routed at item-level.

---

## Goal

`archive/.../2026-05-11.md` 3-segment bundle 평가에서 도출된 cross-segment narrative 결함 4종을 종결:

1. **Time-state 불일치** — 도메스틱 segment 가 "US 하락 출발" 헤드라인을 core 로 promote 했으나 US segment 는 같은 날 +0.5% 마감 — 같은 run 의 자기모순.
2. **Cross-market promotion 과잉** — 도메스틱 segment 가 Iran/oil/macro 를 §② core 로; native KRX 사실은 background.
3. **Native-link 없는 글로벌 ticker** — 도메스틱 watchlist impact 에 AAPL/TSMC 가 등장하지만 "환율/외인/연관 종목" 같은 도메스틱 linkage 부재.
4. **Shared macro 중복** — UST/oil/Fed schedule 이 us-equity 와 crypto 양쪽 §② 에 동일 wording 으로 등장 — dedupe + segment-specific 1-sentence 재해석 없음.

Solution =
(a) **BundleContext pre-computation** (Stage 2 *전*) 로 3 segment 모두에게 same-run market-state 를 동시 inject.
(b) Time-state 결정론 regex catalogue.
(c) 결정론 cross-segment **linkage lint** (post-Stage-2, publish-gate).
(d) cross-market core-tier **allow-list** (geopolitical-oil / fed / global-systemic) 로 over-demotion 회귀 방지.
(e) Shared macro **dedup block** (BundleContext 가 한 번만 들고, 3 prompt 가 1-sentence 재해석).

---

## Persona evidence

> 10-subagent 평가 (2026-05-13, `archive/.../2026-05-11.md`):
> - subagent #1 (cross-market coherence): "도메스틱이 미국 하락 출발을 core 로 잡았는데 미국 segment 는 같은 날 양봉 마감 — 같은 페이지가 서로 모순."
> - subagent #2 (native fact priority): "KOSPI 종가 / 외국인 수급이 §③ 으로 밀리고 Iran 이 §② core 1번."
> - subagent #4 (ticker linkage): "AAPL · TSMC 가 도메스틱 watchlist 에 있으나 '국내 영향' / '환율 경로' 한 줄도 없음."
> - subagent #6 (dedup): "UST 4.42% 가 us-equity §② 와 crypto §② 에 동일 wording 으로 두 번 — segment-specific 재해석 zero."
> - subagent #8 (macro headroom): "다만 macro 를 너무 빼면 US-equity 가 Iran/oil 같은 material 매크로를 잃음 — allow-list 필요."

---

## Definition of Done

- [ ] BundleContext (same-run, per-segment market-state summary) 가 Stage 2 *전*에 계산되어 3 segment prompt 모두에 동일 객체로 inject 됨. 자기 segment 자신은 "pending" 으로 표시 (회귀 방지).
- [ ] Time-state label `pre-market / open / intraday / close / post-close / scheduled` 가 source title regex catalogue 로 결정론적으로 부여; ambiguous 케이스만 LLM 보조 (Stage-2 prompt 내 in-context disambiguation).
- [ ] 도메스틱 segment 의 §② core 가 native KRX 사실 (KOSPI 종가/외국인/업종/종목코드 `[\d{6}]`) 로 시작; cross-market 매크로는 background 로 격하 — 단 `CROSS_MARKET_CORE_ALLOWED` allow-list 항목 (`geopolitical_oil_macro` / `fed_policy_event` / `global_systemic_risk`) 은 core 유지 가능하되 segment-specific 1-sentence 재해석 강제.
- [ ] 도메스틱 segment 본문의 모든 외국 ticker (`AAPL|TSMC|NVDA|MSFT|GOOG|AMZN|META|TSLA|...` 또는 일반 패턴 `[A-Z]{2,5}` allow-list) 출현은 같은 `\n\n` 단락 안에 도메스틱 ticker `\d{6}` 또는 linkage 키워드 `{국내 영향, 환율 경로, 코스피 연관, 수급 영향, 외국인 매매, 환율, 원/달러}` ≥ 1 동반. 위반 시 publish-gate WARNING + 해당 단락 background 강등 또는 reject (config flag 로 선택).
- [ ] BundleContext.`shared_macro_block: str | None` 이 1회만 렌더 — `## ⓪ 오늘의 매크로` H2 surface (segment §① 보다 위) 로 inject; 3 segment 본문은 같은 fact 를 다시 쓰지 않고 자기 관점 1-sentence 재해석만 추가.
- [ ] Same-bundle time-state 모순 detect: us-equity 의 close-state 가 `close` 인데 도메스틱 / crypto 본문이 "US 하락 출발 / 약세 출발" wording 을 core 로 인용한 경우 publish-gate WARNING + 해당 문장 reject 또는 background 강등.
- [ ] Cross-market core-tier allow-list (`CROSS_MARKET_CORE_ALLOWED`) 는 module constant 로 노출, 단위 테스트로 핀; 신규 테마 추가는 후속 unit.
- [ ] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +30-40 신규 테스트), `mkdocs build --strict` ✅.

---

## Untestable AC → measurable proxy (재작성, Critical)

원본 DoD 의 3 항목은 측정 불가 — 본 plan 에서 측정 proxy 로 재작성:

| 원본 AC (untestable) | 측정 proxy (testable) |
|---|---|
| "Cross-market material is downgraded to background unless the link is explicit" | 도메스틱 segment 본문에서 외국 ticker 패턴 매치 → 같은 `\n\n` 단락 안에 `\d{6}` 도메스틱 ticker 또는 linkage 키워드 ≥ 1. 위반은 publish-gate lint 가 WARNING + 강등/reject. AC1 의 단위 테스트로 5+ 케이스 pin. |
| "Native facts ranked above cross-market background" | 각 segment §② 의 첫 H3 (또는 첫 bullet/paragraph) primary noun 이 segment-native entity allowlist 매치 — domestic: `\d{6}` ∪ `{KOSPI, KOSDAQ, KRX, 외국인, 코스피, 코스닥}`; us-equity: `{SPX, SPY, NDX, QQQ, DJI, AAPL, MSFT, NVDA, ...}`; crypto: `{BTC, ETH, ...}`. 위반은 WARN diagnostic. AC2 단위 테스트 pin. |
| "Domestic watchlist impact does not show unrelated global tickers without domestic linkage" | AC1 의 linkage lint 와 동일 mechanism 으로 통합; segment=domestic 또한 §watchlist subsection 한정 strict mode (linkage 키워드 ≥ 1 강제, 위반시 reject). AC3 단위 테스트 pin. |

3 proxy 모두 **결정론적 regex lint** — quality gate 통과 가능.

---

## Pipeline ordering 결정

- **Option A (rejected)**: `SEGMENT_ORDER` 를 `(US, CRYPTO, DOMESTIC)` 으로 변경 — US-first 면 도메스틱 prompt 시 close-state 알 수 있음. 단점: KST cron 시점에 US 가 아직 close 가 아닌 케이스 (월요일 아침) 가 여전히 깨지고, ordering coupling 이 강해짐.
- **Option B (adopted)**: `SEGMENT_ORDER` 유지 (`DOMESTIC, US, CRYPTO`). 대신 **BundleContext pre-computation** (Stage 2 전 raw routed items 만으로 모든 segment 의 close-state 결정) 이 ordering 의존성을 제거.

본 plan 은 Option B 를 채택.

---

## Steps

### Step 1 — Time-state vocabulary and regex catalogue

- [ ] 신규 모듈 `src/investo/briefing/time_state.py`:
  - `TimeState = Literal["pre-market", "open", "intraday", "close", "post-close", "scheduled"]`
  - `TIME_STATE_PATTERNS: dict[TimeState, list[re.Pattern]]`:
    - `pre-market`: `(개장\s?전|장\s?전|프리마켓)`
    - `open`: `(\d+(?:\.\d+)?%?\s?(상승|하락)\s?출발|상승\s?출발|하락\s?출발|개장(?!\s?전))`
    - `close`: `(마감|장\s?마감|종가)`
    - `post-close`: `(시간\s?외|애프터마켓|장\s?후)`
    - `scheduled`: `(예정|전망|발표\s?예정)`
  - `detect_time_state(title: str) -> TimeState | None`: 첫 매치 우선; `open` ∩ `close` 충돌 시 `close` 우선 (factual final state).
- [ ] LLM 보조는 ambiguous (= 매치 없음 + 본문에 시간 표현 다수) 케이스만 — Stage-2 prompt 내 in-context resolution 룰로 명시.
- [ ] 단위 테스트 `tests/unit/briefing/test_time_state.py` (예상 12-16 tests):
  - 각 state 별 positive / negative 케이스.
  - `상승 출발 후 하락 마감` → `close` 우선.
  - 한국어 yonhap-style 헤드라인 5+ 실제 sample.
  - 빈 문자열 / nil → `None`.

### Step 1.5 — BundleContext pre-computation (Critical)

- [ ] 신규 모듈 `src/investo/models/bundle_context.py` (모듈 경계: `models/` 에 위치 — orchestrator + briefing + publisher 모두 소비; R3 무위반):
  - `MarketStateSummary`:
    - `segment: SegmentId`
    - `target_date: date`
    - `tz: str`  # `Asia/Seoul` / `America/New_York` / `UTC`
    - `close_state: TimeState | Literal["pending"]`
    - `headline_native_fact: str | None`  # native source 의 가장 신선한 1-line fact (close 가격 / KOSPI 종가 등)
  - `BundleContext`:
    - `bundle_id: str`
    - `target_kst_date: date`
    - `segments: dict[SegmentId, MarketStateSummary]`
    - `shared_macro_block: str | None`  # § ⓪ 렌더용 1 paragraph (UST / oil / Fed schedule) — 3 segment 가 공유, 본문에서 dedupe
    - `cross_market_core_allowed: frozenset[str]`  # `{"geopolitical_oil_macro", "fed_policy_event", "global_systemic_risk"}`
- [ ] 신규 함수 `compute_bundle_context(routed: SegmentedRoutedItems, *, now_kst: datetime) -> BundleContext` (위치: `src/investo/orchestrator/bundle_context.py` — 라우팅 직후 호출):
  - 각 segment 의 raw items → time_state.detect → 가장 freshness 가 높은 native item 으로 `close_state` 결정.
  - 자기 segment 자신은 *생성 시점에는* `pending` 으로 inject (회귀 안전: 도메스틱 prompt 시점에 도메스틱 자신을 "이미 close" 라고 단정하지 않음).
  - shared macro 후보 detect (UST yield / WTI Brent / Fed FOMC schedule) — 같은 source title 패턴 ≥ 2 segment 출현 시 shared 로 격리.
- [ ] `compute_bundle_context` 는 pure (input → output); 부수효과 없음; logger 만 외부.
- [ ] 단위 테스트 `tests/unit/orchestrator/test_bundle_context.py` (예상 10-14 tests):
  - 빈 input → `segments = {}`, `shared_macro_block = None`.
  - 도메스틱 only → us / crypto `close_state = "pending"`.
  - US `마감` 헤드라인 ≥ 2건 + 도메스틱 본문 → us `close`, 도메스틱 자신은 `pending`.
  - shared macro detect: 같은 UST title 이 us + crypto 양쪽에 들어왔을 때 격리.
  - `cross_market_core_allowed` constant 핀.

### Step 2 — Stage-2 prompt 룰 (per-segment, BundleContext-aware)

- [ ] `src/investo/briefing/prompts/{domestic_equity,us_equity,crypto}.py` 각각에 룰 추가 (룰 텍스트는 공통, 예시는 segment-specific):
  - "BundleContext 사용 룰": prompt 헤더에 `BundleContext` JSON dump 가 inject 됨. 자기 segment 의 `close_state = "pending"` 인 경우 자기 close 를 단정하지 말 것. 타 segment 의 `close_state = "close"` 인 경우 "출발 / 하락 출발 / 상승 출발" wording 을 core 로 인용하지 말 것 (background 로만).
  - "Native fact 우선 룰": §② 의 첫 H3 (또는 첫 bullet) 의 primary noun 은 segment-native entity allowlist 매치. 도메스틱: KRX 종목코드 또는 KOSPI/KOSDAQ/외국인 등. US: SPX/NDX/DJI 또는 주요 US ticker. Crypto: BTC/ETH 또는 주요 chain.
  - "Cross-market allow-list 룰": `BundleContext.cross_market_core_allowed` 항목 (`geopolitical_oil_macro` / `fed_policy_event` / `global_systemic_risk`) 만 cross-market 매크로를 core 로 promote 가능. 단 segment-specific 1-sentence 재해석 (`{이 사실이 우리 segment 에 무엇을 의미}`) 강제.
  - "Linkage 강제 룰" (domestic only): 외국 ticker 인용 시 같은 단락에 도메스틱 linkage (도메스틱 ticker `\d{6}` 또는 키워드 `{국내 영향, 환율 경로, 코스피 연관, 수급 영향, 외국인 매매, 환율}`) ≥ 1 동반.
  - "Shared macro dedupe 룰": `BundleContext.shared_macro_block` 이 non-null 이면 본문에서 같은 fact 의 raw 재서술 금지; 자기 관점 1-sentence 재해석만 허용.
- [ ] **단위 테스트 없음** — prompt 변경은 generation 변동성 흡수; 검증은 Step 3 의 deterministic lint 가 담당 (u51 패턴과 동일).

### Step 3 — Cross-segment linkage lint (deterministic, post-Stage-2)

- [ ] 신규 모듈 `src/investo/publisher/cross_segment_lint.py`:
  - `FOREIGN_TICKER_PATTERN = re.compile(r"\b(AAPL|MSFT|NVDA|GOOG|GOOGL|AMZN|META|TSLA|TSMC|AMD|INTC|NFLX|...)\b")` (확장 가능 allowlist).
  - `DOMESTIC_LINKAGE_KEYWORDS = frozenset({"국내 영향", "환율 경로", "코스피 연관", "수급 영향", "외국인 매매", "환율", "원/달러", "원달러"})`
  - `DOMESTIC_TICKER_PATTERN = re.compile(r"\b\d{6}\b")`
  - `lint_domestic_foreign_linkage(text: str) -> list[LintViolation]`: 도메스틱 segment 본문을 `\n\n` 단락 단위로 split → 외국 ticker 매치 단락 → 같은 단락 안에 `DOMESTIC_TICKER_PATTERN` 매치 또는 `DOMESTIC_LINKAGE_KEYWORDS` 매치 ≥ 1 없으면 violation.
  - `lint_native_fact_priority(text: str, segment: SegmentId) -> list[LintViolation]`: §② 의 첫 H3 (또는 첫 bullet) primary noun 이 segment-native entity allowlist 매치하지 않으면 WARN-tier violation.
  - `lint_time_state_consistency(text: str, ctx: BundleContext) -> list[LintViolation]`: 본문에 "하락 출발 / 상승 출발" wording 매치 → 인용 대상 segment 의 `close_state == "close"` 이면 violation.
- [ ] `LintViolation`: `severity: Literal["WARN", "REJECT"]`, `kind: str`, `paragraph: str`, `evidence: str`.
- [ ] orchestrator publish path 에서 호출 순서: Stage-2 출력 → `cross_segment_lint` → severity=REJECT 면 paragraph 강등 또는 paragraph 제거 (config flag `INVESTO_LINT_STRICT` 로 reject vs demote 선택; default `demote`) → publish.
- [ ] 단위 테스트 `tests/unit/publisher/test_cross_segment_lint.py` (예상 16-20 tests):
  - 외국 ticker + 도메스틱 ticker 같은 단락 → pass.
  - 외국 ticker + linkage 키워드 같은 단락 → pass.
  - 외국 ticker 단독 → violation.
  - §② 첫 H3 가 native noun → pass.
  - §② 첫 H3 가 Iran / oil → violation (단 `geopolitical_oil_macro` allow-list 인 경우 WARN-only).
  - "US 하락 출발" 인용 + us `close_state = close` → violation.
  - "US 하락 출발" 인용 + us `close_state = open` → pass.
  - 빈 텍스트 / 단일 단락 / nested formatting edge case.

### Step 4 — Cross-market allow-list 핀

- [ ] `src/investo/models/bundle_context.py` 의 `CROSS_MARKET_CORE_ALLOWED` constant 노출:
  - `frozenset({"geopolitical_oil_macro", "fed_policy_event", "global_systemic_risk"})`
- [ ] BundleContext 가 이 constant 를 그대로 carry; prompt + lint 양쪽에서 동일 객체 참조 (single source of truth).
- [ ] 단위 테스트 `tests/unit/models/test_bundle_context_allowlist.py` (예상 4-6 tests):
  - constant 값 핀.
  - 신규 항목 추가는 별 unit 임을 docstring 으로 명시.
  - lint 가 allow-list 항목 매크로에 대해 WARN-only 로 downgrade 하는지 확인.

### Step 5 — Shared macro dedupe block

- [ ] BundleContext.`shared_macro_block` 값이 non-null 이면 publish path 가 segment §① 위 (또는 워터마크 직후, TL;DR 직후 — u51 의 layout 과 호환) 에 `## ⓪ 오늘의 매크로` H2 + 단일 paragraph 로 inject.
- [ ] 같은 fact 가 segment 본문에 다시 등장하면 lint 가 dedupe candidate 로 flag (WARN-only; 자동 strip 은 false-positive 우려로 미적용 — implementation 시 결정).
- [ ] 단위 테스트 `tests/unit/publisher/test_shared_macro_block.py` (예상 6-8 tests):
  - `shared_macro_block = None` → § ⓪ 미렌더.
  - non-null → § ⓪ 1회만 렌더, 위치 검증.
  - segment 본문에 동일 fact 재등장 시 WARN.

### Step 6 — orchestrator wire-through + integration fixture

- [ ] `src/investo/orchestrator/pipeline.py` 의 segmented publish path:
  - 라우팅 직후 `compute_bundle_context` 호출.
  - BundleContext 를 Stage-2 prompt 에 inject (각 segment prompt builder 가 BundleContext 를 받도록 signature 확장).
  - Stage-2 출력 → `cross_segment_lint` chain → shared macro inject → u51 `_enhance_reader_experience` → watermark/anchor-table → `verify_disclaimer`.
- [ ] dry-run 에서도 동일 chain (텍스트 변형만; 부수효과 없으므로 안전).
- [ ] 통합 fixture 전략:
  - 합성 (synthetic) fixture 로 unit 우선; live LLM cassette 는 1회만 녹화.
  - 3 segment 각각 독립 cassette (live Claude call 3개) → frozen input bundle + deterministic `BundleContext` 로 replay.
  - 통합 테스트 `tests/integration/test_bundle_reconciliation.py` (예상 4-6 tests):
    - synthetic same-date 3-segment bundle (도메스틱 + us + crypto) → publish path 통과 → 최종 markdown 이 모든 AC 충족.
    - US `close` + 도메스틱 본문 "하락 출발" → REJECT 또는 demote.
    - shared macro UST 매치 → § ⓪ 1회만, 본문 재서술 WARN.
    - 도메스틱 본문 AAPL 단독 → linkage lint REJECT.
    - 도메스틱 본문 AAPL + "환율 경로" → pass.

### Step 7 — 회귀 카나리 + 로깅 + R13

- [ ] WARNING / REJECT 로그 시그니처 표준화: `cross_segment_lint.foreign_ticker_no_linkage` / `cross_segment_lint.native_priority_violated` / `cross_segment_lint.time_state_contradiction` / `cross_segment_lint.shared_macro_duplicate` — structured `extra={"segment": ..., "kind": ..., "evidence_len": ..., "paragraph_index": ...}`.
- [ ] R13 검증: 모든 extra 가 secret-shaped substring 미포함 (input 은 LLM output text + routed item title 만; raw_metadata 미경유).
- [ ] 카나리 단위 테스트: 의도적 위반 input 주입 → 정확한 시그니처로 발화 (caplog).
- [ ] NFR-002 영향: 별도 LLM call 없음. Stage-2 prompt 길이 ~500 토큰 증가 (BundleContext JSON dump 포함). 비용 영향 미미.

### Step 8 — Requirements 문서 + quality gate

- [ ] `docs/requirements.md` 에 **FR-013** 추가 (FR-009=u51, FR-010=u54, FR-011=u55, FR-012=u56 점유):
  - "FR-013: 세그먼트 narrative scope + time-state 일관성 — same-bundle BundleContext / cross-segment linkage lint / cross-market allow-list / shared macro dedupe."
  - AC: 본 plan 의 DoD 8 항목 + 측정 proxy 3개.
- [ ] inception bridge (`aidlc-docs/inception/requirements/`) 동기화 (해당 파일 존재 시).
- [ ] `aidlc-docs/aidlc-state.md` u57 행: `📋 Planned` 유지 (개발 착수 시 `⚙️ In Progress` 로 전이).
- [ ] Quality gate:
  - [ ] `uv run ruff check .` ✅
  - [ ] `uv run ruff format --check .` ✅
  - [ ] `uv run mypy --strict src/` ✅
  - [ ] `uv run pytest -q` ✅ (예상 +30-40 신규 테스트)
  - [ ] `uv run mkdocs build --strict` ✅
  - [ ] (수동) `mkdocs serve` → 2026-05-11 3-segment bundle 재생성 시뮬레이션 → 8 AC 시각 확인.

---

## AC ↔ Step traceability

| AC (DoD) | 측정 mechanism | 책임 Step |
|---|---|---|
| BundleContext pre-comp + inject | `compute_bundle_context` + prompt signature | Step 1.5 + Step 2 + Step 6 |
| Time-state label catalogue | `TIME_STATE_PATTERNS` regex | Step 1 |
| Native-fact priority (§② 첫 H3) | `lint_native_fact_priority` | Step 3 |
| Cross-market allow-list (allow-list 외 demote) | `CROSS_MARKET_CORE_ALLOWED` + lint | Step 3 + Step 4 |
| Linkage lint (외국 ticker → 도메스틱 키워드 동반) | `lint_domestic_foreign_linkage` | Step 3 |
| Shared macro dedupe (§ ⓪ 1회만) | `shared_macro_block` inject + dedup WARN | Step 5 |
| Time-state 모순 detect | `lint_time_state_consistency` | Step 3 |
| Quality gate green | ruff / mypy / pytest / mkdocs | Step 8 |

---

## Step dependency graph

```
Step 1 (time_state regex) ─┐
                           ├─> Step 1.5 (BundleContext) ─┐
Step 4 (allow-list const) ─┘                             │
                                                         ├─> Step 6 (wire-through) ─> Step 7 (canary) ─> Step 8 (gate)
Step 2 (prompt rules) ───────────────────────────────────┤
Step 3 (lint module) ────────────────────────────────────┤
Step 5 (shared macro inject) ────────────────────────────┘
```

Step 1 + Step 4 병렬. Step 1.5 는 Step 1 + Step 4 직후. Step 2 / 3 / 5 는 Step 1.5 직후 병렬. Step 6 은 머지 후. Step 7 / 8 직렬.

---

## NFR AC coverage map

- **NFR-001 (Readability KPI)**: cross-segment narrative coherence 직접 달성 — 같은 페이지 모순 / cross-market 과잉 / 글로벌 ticker 외톨이 모두 lint pin.
- **NFR-002 (운영비 0원)**: 신규 LLM 호출 0건. Stage-2 prompt 길이 ~500 토큰 증가 (BundleContext JSON). 외부 API 호출 없음.
- **NFR-003 (재현성)**: BundleContext + 모든 lint 가 pure (input → output); 동일 input → 동일 output (idempotent test 포함).
- **NFR-004 (mypy strict)**: 신규 모듈 (`time_state.py`, `bundle_context.py`, `cross_segment_lint.py`) 모두 strict.
- **NFR-005 (R13 secret hygiene)**: lint WARNING extra 에 raw_metadata 미포함 — Step 7 카나리로 핀.

---

## Project rule compliance

- **R1 Anthropic SDK ban**: 무관 — prompt 룰 + post-Stage-2 lint; runtime LLM 호출 path 미변경.
- **R3 모듈 경계**: `BundleContext` 는 `models/` 에 위치 (foundation; orchestrator + briefing + publisher 모두 import 허용). `cross_segment_lint.py` 는 `publisher/` 내부. `time_state.py` 는 `briefing/` 내부. orchestrator 만 cross-module 연결.
- **R8 (no raw stdlib XML)**: 무관 — text + regex 처리만.
- **R10 (free APIs only)**: 신규 외부 호출 없음.
- **R13 (secret hygiene)**: lint extra 에 secret-shaped substring 미포함 검증 (Step 7).
- **Disclaimer enforcement**: lint chain 이 `verify_disclaimer` *이전* 위치 — disclaimer 가 lint 에 의해 제거되지 않음을 단위 테스트로 핀.
- **Telegram 채널 분리**: 무관 — site/archive 페이지 전용; notifier 의 summary builder 는 본 unit 무관.

---

## 영향 파일 + 예상 test count

| 파일 | 신규/수정 | 예상 라인 |
|---|---|---|
| `src/investo/briefing/time_state.py` | 신규 | ~80 |
| `src/investo/models/bundle_context.py` | 신규 | ~120 |
| `src/investo/orchestrator/bundle_context.py` | 신규 | ~180 |
| `src/investo/briefing/prompts/{domestic_equity,us_equity,crypto}.py` | 수정 | +30 each |
| `src/investo/publisher/cross_segment_lint.py` | 신규 | ~250 |
| `src/investo/orchestrator/pipeline.py` | 수정 | +60 |
| `tests/unit/briefing/test_time_state.py` | 신규 | 12-16 tests |
| `tests/unit/orchestrator/test_bundle_context.py` | 신규 | 10-14 tests |
| `tests/unit/publisher/test_cross_segment_lint.py` | 신규 | 16-20 tests |
| `tests/unit/publisher/test_shared_macro_block.py` | 신규 | 6-8 tests |
| `tests/unit/models/test_bundle_context_allowlist.py` | 신규 | 4-6 tests |
| `tests/integration/test_bundle_reconciliation.py` | 신규 | 4-6 tests |
| **테스트 총합 (예상)** | | **+52~70** (보수치 +30~40) |

---

## Out of scope

- 소스 routing bugs before segment generation (u45 owns).
- Prior-day event carryover (u52 owns).
- 신규 source adapter (u53 owns).
- Numeric truth / freshness gates (u55 owns).
- Compliance language / observational tags (u56 owns).
- Telegram summary 포맷 변경 — notifier 의 summary builder 는 본 unit 무관.
- **per-segment dominance cap** (예: us-equity 시황에서 crypto narrative 비중 ≤ 20%) — u45 가 입력단에서 대부분 해결; 재발 시 별 unit 격상.
- **CROSS_MARKET_CORE_ALLOWED 항목 추가** — 본 plan 은 3 항목 (`geopolitical_oil_macro` / `fed_policy_event` / `global_systemic_risk`) 만 핀; 신규 테마 (예: `currency_crisis_macro`, `commodity_shock`) 추가는 후속 unit.

---

## Open questions

- **Strict mode default** — config flag `INVESTO_LINT_STRICT` 의 default 가 `demote` (paragraph 강등) vs `reject` (전체 publish 중단)? 권장: `demote` (자동화 신뢰성 우선); 사용자 회고에서 strict 요구 시 별 unit.
- **Foreign ticker allowlist 폭** — 본 plan 의 패턴은 well-known mega-cap 중심 (`AAPL|MSFT|NVDA|...`). small/mid-cap (`PLTR|RBLX|...`) 누락 가능. 권장: implementation 시 sources/ 의 known ticker registry 와 align.
- **Shared macro auto-strip vs WARN-only** — segment 본문에 shared macro 재서술 시 자동 strip 은 false-positive 우려 (segment-specific 재해석을 잘못 strip). 권장: WARN-only.
- **BundleContext JSON dump 크기** — Stage-2 prompt 길이 영향. 권장: 핵심 필드만 dump (≤ 500 토큰).
- **§ ⓪ 위치 vs u51 TL;DR 블록** — u51 `## 한눈에 보기` 와 § ⓪ 가 동시 존재 시 layout 순서? 권장: TL;DR → § ⓪ → § ① (TL;DR 이 reader 가 가장 먼저 봄).
- **DEBT 후보**:
  - `FOREIGN_TICKER_PATTERN` 의 정적 allowlist — sources/ ticker registry 와 자동 sync 미적용 (manual maintenance burden).
  - `lint_native_fact_priority` 의 "primary noun" 추출 — 한국어 형태소 분석 (KoNLPy 등) 미사용; regex 기반 false-negative 가능.
  - `lint_time_state_consistency` 의 wording match — `\d+(?:\.\d+)?%\s?(상승|하락)\s?출발` 외의 시간-state 표현 false-negative.
- **Live cassette 재녹화 주기** — Claude prompt 변경 시 3 segment 각각 재녹화 비용; CI 에는 mock-only.

---

## How to approve

본 plan 의 8 AC + 8 step 분해 + AC↔Step traceability 표 + 측정 proxy 재작성 + open questions 검토 후:

1. **Request Changes** — AC 조정 / step 분해 변경 / allow-list 항목 조정 / out-of-scope 재분류 / strict mode default 변경.
2. **Continue to Next Stage** — developer 가 Step 1 부터 implementation 시작.

승인 시 `aidlc-docs/aidlc-state.md` 의 u57 행이 `📋 Planned` → `⚙️ In Progress` 로 전이.
