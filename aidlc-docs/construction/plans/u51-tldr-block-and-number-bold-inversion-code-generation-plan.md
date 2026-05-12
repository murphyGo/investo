# Code Generation Plan: `u51 tldr-block-and-number-bold-inversion`

**Date**: 2026-05-13
**Unit**: u51 tldr-block-and-number-bold-inversion
**Stage**: Code Generation
**Status**: ✅ Complete
**Source**: 10-subagent quality review of `archive/us-equity/2026/05/2026-05-11.md` (2026-05-13 session). Reader-facing output formatting (scannability + actionability) 결함 5종 도출.
**Estimated Effort**: ~4-5 h
**Dependencies**:
- u7 segmented-briefing (Stage-2 prompt + segmented generator; 본 unit 의 prompt 룰이 얹힘).
- u9 briefing-reader-experience (`_enhance_reader_experience` 의 watermark / segment-nav / anchor 라인 위에 TL;DR 블록 삽입).
- u40 financial-acronym-glossary (`briefing/glossary.py` 의 first-use gloss callout — u51 의 glossary 1회 룰이 본문 dedupe 를 추가; callout 은 그대로 유지).
- u49 deterministic-market-anchor (앵커 수치가 표 cell 의 source — 표 승격 시 anchor 값 재사용).

---

## Goal

`archive/us-equity/2026/05/2026-05-11.md` 평가에서 도출된 reader-facing 결함 5종을 종결한다:

1. **자급식 TL;DR 부재** — `오늘의 결론` 한 줄이 "3대 지수 상승 마감" 류 일반론; 매그니튜드/방향성/액션 미포함.
2. **앵커 prose wall** — 5개 지수+종목 mixed pct/abs 가 250자 한 줄 prose 로 압축 — 가독성 zero.
3. **`**Title** — body` 패턴 만연** — §②/③/④/⑥ 의 sub-headings 가 bold-prefix prose; H3 nav 부재; Telegram에서 wall of text.
4. **bold 반전** — 섹션 타이틀에만 `**...**`, 핵심 숫자 (`+11.51%`, `$81,154.06`, `4.42%`) 는 plain — 스캔 시 시선이 숫자에 안 박힘.
5. **"여부" 가족 어구 비율 폭주** — §⑥ 관전 포인트 5개 중 4개가 `~여부 / ~할 필요가 있다` 종결 — 액션성 zero.
6. **glossary 중복** — `S&P 500(스탠더드앤드푸어스 500 지수)` 글로싱이 같은 파일 내 3회 반복.

solution = Stage-2 system prompt 룰 추가 + publisher post-format 검증/리포매팅 헬퍼 신규.

---

## Persona evidence

> 10-subagent quality 리뷰 (2026-05-13 session, `archive/us-equity/2026/05/2026-05-11.md` 대상):
> - subagent #3 (scannability): "앵커가 길어 표로 빼야 함."
> - subagent #5 (TL;DR): "한 줄 결론에 매그니튜드가 없어 페이지 안 열어보면 모름."
> - subagent #7 (actionability): "§⑥ 5건 중 4건이 '여부' 종결, '무엇을 할지' 모름."
> - subagent #9 (typography): "bold 반전 — 숫자가 굵어야 시선이 정착."
> - subagent #10 (term dedupe): "S&P 500 풀어쓰기가 같은 페이지에 3번 반복."

---

## Definition of Done

- [x] 모든 segmented 시황 상단(워터마크/세그먼트-네비/anchor 라인 다음, 본문 § 시작 전)에 `## 한눈에 보기` H2 블록 + 정확히 3 bullet:
  - bullet 1: 핵심 방향성 + 매그니튜드 (예: "미국 3대 지수 0.7~1.1% 상승, S&P 500 사상 최고 갱신").
  - bullet 2: 가장 의미 있는 단일 사실 (예: "**BTC**가 한 주 +11.51%로 $81,154 회복").
  - bullet 3: 본문에서 확인할 액션 가능한 변수 (예: "**4.42%** 10Y 금리가 위협 임계 — 본문 §② 참조").
  - Telegram 호환: markdown 제거 후에도 의미 보존 (`**...**` 제거시 bullet 본문이 자연스러운 한국어 문장).
- [x] 앵커 라인이 markdown 표(헤더: 지수·종가·변동·비고)로 렌더; us-equity 4행 최소(3 지수 + 대표 종목 1), crypto 2행 최소(BTC + ETH), domestic-equity 가능시 2행 (KOSPI + KOSDAQ).
- [x] §②/③/④/⑥의 sub-headings 가 H3 (`### Title`)로 승격 — 기존 `**Title** — body` 패턴 제거; H3 라인 뒤 빈 줄 + 본문 paragraph 분리.
- [x] 본문 핵심 숫자 패턴 (`[+-]\d+(?:\.\d+)?%`, `\$[\d,]+(?:\.\d+)?`, `\b\d+\.\d+%`) 이 plain text 일 때 `**숫자**` 로 wrap (post-validation, 코드 블록/표 cell 내부 제외).
- [x] §⑥ 관전 포인트에서 `여부|필요가 있다|관건이다|주목할 필요` 로 끝나는 bullet 비율 ≤ 40% (검증 + 위반 시 publisher가 WARNING 로그 + 회귀 카나리 발화). 위반은 *block* 이 아닌 *flag* — generation 변동성 흡수.
- [x] 글로싱 1회 룰: 같은 파일 내 같은 용어(글로싱 패턴: `\b([가-힣A-Za-z0-9\s\&\.]+?)\(([^)]+)\)`) 의 2번째 이상 출현 시 `(풀어쓰기)` 부분만 strip — base 용어 보존. u40 의 `> **용어 가이드**` callout 은 그대로 (별 surface).
- [x] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +28-36 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Stage-2 prompt 룰 (TL;DR + H3 + bold-number)

- [x] `src/investo/briefing/prompts/` (해당 segment system prompt 파일들) 에 룰 추가:
  - "한눈에 보기 블록" 룰: 시황 본문 § 시작 *전에* `## 한눈에 보기` H2 + 정확히 3 bullet 생성. 각 bullet 의 형식 가이드 + 매그니튜드 강제 (방향성만 쓰면 reject 후보).
  - "H3 sub-headings" 룰: §②/③/④/⑥ 의 sub-section 은 `### {Title}` 형식 (bold-prefix prose 금지).
  - "숫자 bold" 룰: `[+-]\d+\.\d+%`, `\$[\d,]+(?:\.\d+)?`, `\d+\.\d+%` (yield) 형태 숫자는 `**숫자**` 로 wrap.
  - "여부 가족 어구" 룰: §⑥ bullet 의 종결 어미가 `~여부 / ~필요가 있다 / ~관건이다 / ~주목할 필요` 중 40% 이하 — 액션 동사 종결 (`매수 검토 / 비중 축소 / 추세 확인`) 권장.
- [x] 각 segment (us-equity / crypto / domestic-equity) prompt 파일에 동일 룰 사본 (Stage-2 는 segment 별 prompt 분리; 룰 텍스트는 공통).
- [x] **단위 테스트 없음** — prompt 변경은 generation 변동성 흡수, 검증은 post-format 헬퍼 (Step 3) 가 담당.

### Step 2 — 앵커 표 승격

- [x] `src/investo/publisher/` 에 신규 헬퍼 `render_anchor_table(anchors: Sequence[MarketAnchor]) -> str` 추가 (모듈 위치: 기존 `publisher/anchor_line.py` 또는 신규 `publisher/anchor_table.py` — implementation 시 결정).
- [x] 표 헤더: `| 종목 | 종가 | 변동 | 비고 |`. 비고 cell 은 ATH/52w 거리 등 anchor 의 derived field 1개.
- [x] us-equity: 3 지수 + AAPL 또는 가장 큰 % 변동 종목 1; crypto: BTC + ETH; domestic-equity: KOSPI + KOSDAQ (u49 D49-A 해결 후 — 미해결 시 영행).
- [x] orchestrator `_enhance_reader_experience` 의 anchor 라인 삽입 path 를 표 삽입으로 교체 (기존 `> **시장 anchor**: ...` 한 줄 deprecate; backward-compat 위해 anchor 가 비면 라인/표 모두 생략).
- [x] 단위 테스트 `tests/unit/publisher/test_anchor_table.py` (예상 8-10 tests): 빈 anchors → 빈 문자열 / 단일 anchor → 1행 / 5 anchors → 4행 (cap) / 매그니튜드 포맷 / Decimal round-trip / segment 별 헤더 일치.

### Step 3 — Post-format 검증/리포매팅 헬퍼

- [x] 신규 모듈 `src/investo/publisher/reader_format.py` (또는 기존 `publisher/format_validation.py` 에 함수 추가):
  - `ensure_tldr_block(text: str) -> str`: `## 한눈에 보기` H2 + 3 bullet 부재 시 WARNING 로그 + 기본 placeholder 삽입 (heuristic: 본문 첫 3 paragraph 에서 추출 — best-effort).
  - `enforce_h3_subheadings(text: str) -> str`: `**Title** — body` 패턴 detect → `### Title\n\nbody` 로 변환.
  - `wrap_numbers_bold(text: str) -> str`: regex `(?<!\*)([+-]?\d+\.\d+%|\$[\d,]+(?:\.\d+)?)(?!\*)` → `**\1**`. 코드 블록 (` ``` `) 내부 + 표 cell 내부 (`|...|` 행) 제외. 이미 bold wrap 된 것 (`**...**`) 제외.
  - `check_action_bullet_ratio(text: str, section_marker: str = "⑥") -> tuple[float, list[str]]`: §⑥ bullets 추출 → "여부" 가족 어구 종결 비율 계산 → > 40% 면 WARNING + 위반 bullet list 리턴. *non-blocking* — flag only.
  - `dedupe_glossings(text: str) -> str`: regex `\b([가-힣A-Za-z0-9\s\&\.]{1,30}?)\(([^)]{1,40})\)` → 같은 `(풀어쓰기)` 의 2회차 이상 출현은 괄호 부분만 strip.
- [x] orchestrator publish path 에서 호출 순서: `_enhance_reader_experience` 직후, watermark/anchor-table 다음, `verify_disclaimer` 직전.
- [x] 모든 헬퍼는 pure (str → str); 부수효과 없음; logger 만 외부 (R13 secret hygiene 무영향).
- [x] 단위 테스트 `tests/unit/publisher/test_reader_format.py` (예상 18-22 tests):
  - TL;DR block 존재/부재 detect + placeholder 삽입.
  - H3 변환: 단일 패턴 / 다중 / nested formatting 보존.
  - 숫자 wrap: 표 cell 내부 미적용 / 코드 블록 내부 미적용 / idempotent (이미 wrap 된 것 무영향).
  - "여부" 비율: 5/5 → 1.0 / 2/5 → 0.4 / 0/5 → 0.0; threshold edge case.
  - glossing dedupe: 첫 출현 보존 / 2회차 strip / 3회차 strip / 다른 용어 무영향.

### Step 4 — orchestrator wire-through

- [x] `src/investo/orchestrator/pipeline.py` 의 segmented publish path 에 신규 헬퍼 호출 chain 추가.
- [x] dry-run 에서도 같은 chain 호출 (텍스트 변형만; 부수효과 없으므로 안전).
- [x] 통합 테스트 `tests/integration/test_briefing_reader_format.py` (예상 4-6 tests): synthetic Stage-2 출력 → publish path 통과 → 최종 markdown 이 모든 AC 충족.

### Step 5 — 회귀 카나리 + 로깅

- [x] WARNING 로그 시그니처 표준화: `reader_format.action_ratio_high` / `reader_format.tldr_missing` / `reader_format.glossing_duplicate` — structured `extra={"segment": ..., "ratio": ..., "count": ...}`.
- [x] R13 검증: 모든 WARNING extra 가 secret-shaped substring 미포함 (input 은 LLM output text 만; redaction layer 가 상위에서 이미 적용).
- [x] 카나리 단위 테스트: 의도적으로 위반 input 주입 → WARNING 발화 확인 (caplog).

### Step 6 — Requirements 문서 갱신

- [x] `docs/requirements.md` 에 FR-XXX 추가 (다음 free FR id 확인 후 결정 — 현재 최고 id 읽고 +1):
  - "FR-XXX: Reader-facing 출력 포맷 — TL;DR 블록 / 앵커 표 / H3 sub-heading / 숫자 bold / 글로싱 dedupe / §⑥ 액션 비율 carry."
  - AC: 본 plan 의 DoD 6 항목 그대로 인용.
- [x] FR id 가 inception bridge (`aidlc-docs/inception/requirements/`) 에도 등록되어 있다면 그쪽도 동기화.

### Step 7 — Quality gate + 수동 검증

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (예상 +28-36 신규 테스트)
- [x] `uv run mkdocs build --strict` ✅
- [x] (수동) `mkdocs serve` → `2026-05-11` us-equity 페이지 재생성 시뮬레이션 → 6 AC 시각 확인.

---

## Step Dependency Graph

```
Step 1 (prompt) ─────────┐
                         ├──> Step 4 (wire-through) ──> Step 5 (canary) ──> Step 7 (gate)
Step 2 (anchor table) ───┤
Step 3 (post-format) ────┘                                       ↑
                                                                 │
                                              Step 6 (requirements) ─┘
```

Step 1 / 2 / 3 는 병렬 가능. Step 4 는 1+2+3 머지 후. Step 6 는 Step 4 와 병렬.

---

## NFR AC coverage map

- **NFR-001 (Readability KPI)**: AC 1-4 직접 달성 (scannability + actionability).
- **NFR-002 (운영비 0원)**: 신규 외부 호출 0건. LLM 추가 호출 없음 (Stage-2 prompt 룰 수정만).
- **NFR-003 (재현성)**: post-format 헬퍼 전부 pure; 동일 input → 동일 output (idempotent test 포함).
- **NFR-004 (mypy strict)**: 모든 신규 모듈 strict 준수.
- **NFR-005 (R13 secret hygiene)**: WARNING extra 에 raw_metadata 미포함 — Step 5 회귀 카나리로 핀.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관 — prompt 룰 추가만, runtime LLM 호출 path 미변경.
- **모듈 경계**: 신규 `publisher/reader_format.py` 는 `publisher/` 내부. `orchestrator` 만 import. `briefing/` / `notifier/` / `sources/` 미관여.
- **R8 (no raw stdlib XML)**: 무관 — text 처리만.
- **R10**: 신규 외부 호출 없음.
- **R13**: WARNING 로그 extra 에 secret-shaped substring 미포함 검증 (Step 5).
- **무료 API only**: 무관.
- **Disclaimer enforcement**: post-format chain 이 `verify_disclaimer` *이전* 에 위치 — disclaimer 가 헬퍼에 의해 제거되지 않음을 단위 테스트로 핀.
- **Telegram 채널 분리**: 무관 — 본 unit 은 텍스트 포맷; notifier 경로 미변경.

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **per-segment dominance cap** (예: us-equity 시황에서 crypto narrative 비중 ≤ 20%) — 별 unit (u45 routing fix 가 입력 단계에서 대부분 해결; 재발 시 별 unit 격상).
- **차트 위/아래 위치 조정** — u50 의 차트 placement 는 본 unit 무관.
- **LLM 재시도 / regeneration** — 본 unit 은 post-format heuristic; "여부" 비율 위반 시 regenerate 하지 않음 (regenerate path 는 별 unit).
- **Telegram 메시지 포맷 변경** — notifier 의 summary 빌더 (`notifier/summary.py`) 는 본 unit 무관; TL;DR 블록은 site/archive 페이지에만 가시.
- **u40 glossary callout 의 룰 변경** — `> **용어 가이드**` callout 은 그대로 유지; 본 unit 은 본문 inline 글로싱 dedupe 만.

---

## Open questions

- **TL;DR 부재 시 publisher 의 fallback 전략** — heuristic placeholder 삽입 vs WARNING only / 빈 블록? 권장: heuristic placeholder (본문 첫 paragraph 추출) + WARNING. implementation 시 확정.
- **§⑥ 액션 비율 carry — 위반 시 blocking?** 본 plan 은 *flag only*. 사용자 회고에서 "엄격 block" 요구가 나오면 별 unit 으로 확장 (regenerate path).
- **앵커 표의 비고 cell 후보** — ATH 거리 / 52w 거리 / MTD / YTD / 거래량 z-score 중 어느 것? 권장: ATH 거리 (가장 narrative-rich); implementation 시 anchor 의 어떤 derived field 가 가장 안정적인지 검증.
- **FR id 할당** — `docs/requirements.md` 의 현재 free id 미확인. Step 6 진입 전 확인 필요.
- **DEBT 후보**: 
  - 한국어 종결 어미 stemmer 가 단순 regex 가 아닌 형태소 분석 (KoNLPy 등) 으로 갈 경우 정확도 향상 — 무료 룰 위반 없음, 단 의존 무게 증가.
  - 숫자 wrap regex 의 false-negative (예: `5%` 단일 digit) — implementation 시 확정.
  - 글로싱 dedupe 의 false-positive — 같은 표기지만 의도적 재정의 (예: 본문 §② 의 "S&P 500" 과 §⑥ 의 표 cell "S&P 500") 가 둘 다 dedupe 대상이 될 가능성. ratio cap (예: 첫 출현 후 2개까지 허용) 으로 완화 검토.

---

## How to approve

본 plan 의 6 AC 와 7 step 분해를 검토 후:

1. **Request Changes** — AC 조정 / step 분해 변경 / out-of-scope 항목 재분류.
2. **Continue to Next Stage** — developer 가 Step 1 부터 implementation 시작.

승인 시 `aidlc-state.md` 의 u51 행이 "📋 Planned" → "⚙️ In Progress" 로 전이.
