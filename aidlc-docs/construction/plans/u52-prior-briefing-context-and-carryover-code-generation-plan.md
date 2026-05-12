# Code Generation Plan: `u52 prior-briefing-context-and-carryover`

**Date**: 2026-05-13
**Unit**: u52 prior-briefing-context-and-carryover
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 사용자 직접 (2026-05-13 evaluation). 2026-05-06 → 05-08 시황 연쇄 평가에서 day-over-day 연속성 부재가 시황을 standalone preview 로 만들고 있다는 결함 적시.
**Estimated Effort**: ~4-5 h
**Dependencies**:
- u34 recent-briefings-context (이미 N=5 영업일 직전 결론/동인을 Stage 2 prompt 에 주입함 — 본 unit 은 그 위에 *구조화된* carryover layer 를 얹음. 두 모듈 공존 — u34 는 narrative continuity, u52 는 event-resolution tracking).
- u35 event-lookahead (Stage 2 prompt 의 "주요 일정" 섹션을 만든 module — 본 unit 의 unresolved 항목 source 중 하나가 어제 시황의 lookahead 표).
- u29 site-discovery-v2 / DEBT-060 후속 (`briefing/extract.py` chokepoint 재사용 — 6번째 consumer 등장; grep-guard test 가 prefix literal 재선언 0건을 강제하므로 본 unit 도 chokepoint 통과 필수).
- u45 segment-routing-exclusivity (segment 별 archive 디렉터리 구조 `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` — 본 unit 의 prior-archive loader 가 같은 segment 안에서만 walk-back).

---

## Goal

오늘 시황 (예: 2026-05-08) 이 어제 시황 (2026-05-07) 의 결론·관전·예고 이벤트를 "알고" 작성되도록, 같은 segment 의 직전 N=3 영업일 archive markdown 을 결정론적으로 파싱하여 (resolved / unresolved) carryover 항목을 추출하고 Stage 2 prompt 에 주입한다. LLM 의 출력에 새 섹션 **"Watchlist Carryover"** 를 § ② 뒤 · § ⑥ 앞에 표 형식으로 박는다. 같은 날짜 같은 segment 의 idempotent 재실행 보장 (FR-006 compat). 첫날 / 휴장 gap / 파일 누락 시 graceful skip.

핵심 결함 (사용자 evaluation 인용):
- 05-06 이 05-05 참조 zero → standalone preview 처럼 읽힘.
- 05-06 의 ARM/APP/UBER/DIS/NVO/WBD 어닝 예고가 05-07/05-08 에서 결과 follow-up zero.
- 05-07 highlighted LNG/VST/TRGP/COIN 을 05-08 reporting 안 함 (새 어닝 셋 등장만).
- 05-07 베어리시 마감 → 05-08 [강세] ATH 경신, 1줄 브릿지, flow-of-funds 설명 zero.
- DGS10/UST/FRED/Regulation FD 용어가 매일 재정의 (per-day 메모리 없음).

u34 가 narrative 결론을 인용시키는 데 비해, u52 는 **event-level lifecycle** (originated → expected → resolved/unresolved/이월) 을 강제한다.

---

## Persona evidence

> 사용자 (2026-05-13 evaluation): "05-06 이 05-05 참조 zero, 05-07 의 LNG/VST/TRGP/COIN 을 05-08 이 reporting 안 함. day-over-day 연속성 부재 문제를 유닛화."

추가 trace:
- 05-08 시황의 ⑥ 관전 포인트 항목 #2 "TM, ENB, BAM, VST, FIS의 실제 EPS 와 가이던스" 가 05-07 에서 어디서 originate 했는지 brief reader 가 모름 (origin date 미표시).
- u35 가 *forward* lookahead 만 다루고, *backward* "어제 예고된 것의 오늘 결과" 표기 surface 없음.
- u34 context loader 가 결론·동인을 인용시키지만 LLM 이 free-form 으로 "어제는 베어리시였다" 같은 1줄 만 쓰고 끝나는 패턴 — 구조화된 표가 없으면 carryover discipline 이 휘발됨.

---

## Definition of Done

- [x] 신규 pydantic v2 모델 (frozen + slots + `extra="forbid"`):
  - `CarryoverItem`: `event_type: Literal["earnings","fed","geopolitics","macro","disclosure","other"]`, `ticker_or_topic: str` (≤ 64 chars), `originated_date: date`, `expected_date: date | None`, `status: Literal["resolved","unresolved","carried_over"]` (한글 라벨 = 확인됨/미확인/이월 — 렌더링 단계 매핑), `note: str | None` (≤ 120 chars, optional context one-liner).
  - `BriefingCarryover`: `prior_resolved: tuple[CarryoverItem, ...]`, `prior_unresolved: tuple[CarryoverItem, ...]`, `lookback_days: int` (실제 walk-back 된 영업일 수), `is_empty: bool` 헬퍼 (양 리스트 모두 비었을 때 True).
  - 위치: `src/investo/models/carryover.py` (신규 파일). `models/__init__.py` 재수출.
- [x] 직전 N=3 영업일 archive 파서 (`src/investo/briefing/carryover_parser.py`, 신규):
  - 입력: `archive_root: Path`, `segment: str`, `today: date`, `lookback: int = 3` (env `INVESTO_CARRYOVER_LOOKBACK_DAYS` clamp `[1, 7]`).
  - Sat/Sun skip + holiday gap silent skip. 21일 캡 (u34 와 동일 walk-back 규칙).
  - 각 직전 영업일 file path `archive/{segment}/YYYY/MM/YYYY-MM-DD.md` 가 없으면 silent skip.
  - 추출 surface:
    - § ⑥ "오늘의 관전 포인트" 본문 — 1..N 번호 list 항목 (정규식 `^\d+\.\s+\*\*(.+?)\*\*[:：]\s*(.+)$`) → unresolved 후보 (originated_date = 해당 파일의 publish date).
    - § ⑥ 의 "이번 주·이번 달 주요 일정" 표 — `| 날짜 | 이벤트 |` (u35 lookahead 표) → `expected_date` 가 `today` 이전 (지난 이벤트) 이면 unresolved 후보; `today` 이거나 이후 면 carried-over.
    - `> **오늘의 결론**:` 한 줄 (u29 `extract_conclusion` chokepoint 재사용) → status 판별 보조 (행동 태그 [강세]/[약세]/[혼조] 추출).
  - 추출된 항목을 오늘 시황의 candidate stream 과 *대조* — `ticker_or_topic` 가 오늘 candidate `raw_metadata` 의 ticker/headline 에 substring 매치되면 `status="resolved"`, 매치 안 되면 그대로 `unresolved`. `expected_date` 가 미래면 `carried_over`.
  - **chokepoint 재사용**: § ⑥ heading detect 는 새 정규식이지만 § 결론 / 워터마크 / 동인 / 주의 추출은 `briefing/extract.py` 의 4 함수를 *반드시* 호출 (DEBT-060 6번째 consumer 등장 — grep guard test 가 새 파일에 prefix literal 재선언이 0건이어야 통과).
  - 파서는 **순수** (Path I/O 만, 시계 의존 없음 — `today` 는 인자 주입).
- [x] orchestrator wire-through (`src/investo/orchestrator/pipeline.py`):
  - `_load_carryover_for_run(now_utc, segments, candidates_by_segment) -> dict[str, BriefingCarryover]` (best-effort, segment 단위 isolation — 한 segment 파서 fail 이 다른 segment 영향 무).
  - `_stage_run_stage2_per_segment` 직전 호출, segment 별 `BriefingCarryover` 를 `generate_briefing(..., carryover=...)` 에 전달.
  - 빈 `BriefingCarryover` (`is_empty=True`) 시 prompt 에 빈 섹션 placeholder 도 주입 안 함 (u34 패턴 동일).
- [x] Stage 2 prompt 확장 (`src/investo/briefing/prompts.py`):
  - 신규 헬퍼 `format_carryover_section(carryover: BriefingCarryover) -> str` — 한국어 표 + 결정론적 line 형식 (LLM 이 그대로 인용 가능).
  - `STAGE2_USER_TEMPLATE` 에 `{carryover_context}` placeholder 추가 (기존 `{recent_context}`, `{lookahead_context}` 형제).
  - `STAGE2_SYSTEM` 에 새 룰 4 항:
    1. "어제 § ⑥ 에 있던 항목 중 오늘 결과가 확인된 것은 § ② 본문 첫 2 줄 안에 explicit 인용 (예: '어제(YYYY-MM-DD) 예고한 X 가 오늘 ...로 확인되었다')."
    2. "확인 안 된 항목은 § ⑥ 의 'Watchlist Carryover' 표에 status='미확인'으로 carry-over."
    3. "어제 [강세/약세] → 오늘 반대 방향이면 § ② 첫 단락에 1-2 문장 bridge (반전 동인 + flow-of-funds 1줄)."
    4. "carryover 표의 ticker_or_topic / originated_date / expected_date 는 발명 금지 — 입력 carryover_context 의 row 만 인용."
  - `BriefingDocument` 출력 모델은 *수정 안 함* — Stage 2 가 markdown 안에 직접 표를 박고, post-process 단계가 검증/insert.
- [x] Carryover 섹션 렌더러 (`src/investo/publisher/carryover.py`, 신규):
  - 순수 헬퍼 `render_carryover_block(carryover: BriefingCarryover) -> str` — Markdown 표:
    ```
    ## Watchlist Carryover

    | 이벤트 | 발원일 | 기대일 | 상태 |
    |--------|--------|--------|------|
    | ARM 어닝 | 2026-05-06 | 2026-05-07 | 확인됨 |
    | LNG 어닝 | 2026-05-07 | 2026-05-08 | 미확인 |
    | FOMC 의사록 | 2026-05-08 | 2026-05-20 | 이월 |
    ```
  - 빈 carryover → 빈 문자열 반환 (orchestrator 가 빈 문자열은 insert skip).
  - `inject_carryover_block(markdown: str, block: str) -> str` — § ② 종료 / § ⑥ 시작 사이 정확 위치 insert. 이미 "## Watchlist Carryover" 가 있으면 (idempotent re-run) 기존 블록 replace.
  - HTML/Markdown escape: `ticker_or_topic` 의 `|` `[` `]` 등 표 깨는 문자 escape (`\\|` 등).
- [x] orchestrator post-process: Stage 2 결과 markdown 에서 LLM 이 표를 *생성* 했어도, deterministic renderer 가 *override* (LLM 발명 row 차단). LLM 의 자유 row 가 0 / partial / extra 일 수 있으므로 deterministic 표가 single source of truth.
- [x] 회귀 테스트:
  - **C1** (`tests/unit/models/test_carryover.py`): `CarryoverItem` / `BriefingCarryover` pydantic invariant — frozen / extra=forbid / Literal 값 / `is_empty` 헬퍼 (양 리스트 모두 빈 경우).
  - **C2** (`tests/unit/briefing/test_carryover_parser.py`): 5+ shape — (a) 정상 1-day walk-back, (b) 3-day walk-back, (c) Sat/Sun skip, (d) 누락 파일 skip, (e) 빈 § ⑥ 섹션, (f) malformed list (number 누락) → 항목 skip 만.
  - **C3** (same): 오늘 candidate 와 substring 매치 → status=resolved 전환.
  - **C4** (same): `expected_date` 미래 → status=carried_over.
  - **C5** (`tests/unit/briefing/test_extract_no_redeclare.py` 기존 grep-guard test 가 통과해야 함 — 본 unit 의 `carryover_parser.py` 는 prefix literal 재선언 0건).
  - **C6** (`tests/unit/publisher/test_carryover_renderer.py`): `render_carryover_block` markdown shape; `inject_carryover_block` idempotent (2회 호출 = 1회 호출 결과); 빈 carryover → 빈 문자열 + insert skip.
  - **C7** (`tests/unit/orchestrator/test_carryover_wire.py`): pipeline 통합 — segment 별 isolation (한 segment 파서 fail 이 다른 segment 영향 무), `is_empty=True` 시 markdown 변경 없음.
  - **C8** (orchestrator 동일): idempotent — 같은 (segment, date) 재실행 시 markdown byte-equal (FR-006).
  - **C9** (`tests/unit/briefing/test_prompts_carryover.py`): `format_carryover_section` 빈 / non-empty / Korean 라벨 정확.
- [x] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (1872 → 1910, +38 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — 모델 + 직렬화 (`models/carryover.py`)

- [x] `src/investo/models/carryover.py` 작성 — `CarryoverItem` + `BriefingCarryover` (frozen + slots + `extra="forbid"`).
- [x] `event_type` Literal 닫힌 셋 6 (earnings / fed / geopolitics / macro / disclosure / other) — 7번째 등장 시 별 unit 격상.
- [x] `status` Literal 닫힌 셋 3 + 한글 라벨 매핑 헬퍼 `status_label_kr(status) -> str`.
- [x] `models/__init__.py` 재수출.
- [x] **AC 매핑**: AC#1.
- [x] **영향 파일**: `src/investo/models/carryover.py` (신규), `src/investo/models/__init__.py`.

### Step 2 — Archive 파서 (`briefing/carryover_parser.py`)

- [x] § ⑥ heading detector — 정규식 `^## ⑥\s+오늘의 관전 포인트\s*$`.
- [x] § ⑥ 본문 list item 추출 — 정규식 `^\d+\.\s+\*\*(.+?)\*\*[:：]\s*(.+)$` (한국어 콜론 변종 포함).
- [x] u35 lookahead 표 추출 — `| 날짜 | 이벤트 |` 헤더 detect + 후속 행 ISO date parse.
- [x] `briefing/extract.py` 의 `extract_conclusion` / `extract_watermark` 호출 (chokepoint preservation).
- [x] Walk-back: KST trading-day calendar 재사용 (u34 의 `_iter_recent_business_days` 패턴 모방 — duplicate 회피 위해 helper 재사용 검토; 안 되면 본 unit 의 private copy + DEBT 후보).
- [x] event_type classifier — `ticker_or_topic` substring 룰:
  - earnings: `\b(EPS|어닝|실적|prelim)\b` 또는 알파벳 ticker 3-5 chars uppercase.
  - fed: `\b(Fed|FOMC|Powell|Waller|Bowman|연준|기준금리)\b`.
  - geopolitics: `\b(이란|중동|러시아|우크라이나|북한|관세|tariff)\b`.
  - macro: `\b(CPI|PPI|NFP|GDP|PCE|DGS10|UST|국채금리)\b`.
  - disclosure: `\b(8-K|10-K|10-Q|공시|DART)\b`.
  - other: fallback.
- [x] 미매칭 (classifier 가 빈 매치) → `event_type="other"` (drop 안 함 — carryover 신호는 유지).
- [x] **AC 매핑**: AC#2, AC#6.
- [x] **영향 파일**: `src/investo/briefing/carryover_parser.py` (신규).

### Step 3 — Stage 2 prompt + 출력 가이드 (`briefing/prompts.py`)

- [x] `format_carryover_section(carryover)` 헬퍼 — 빈 carryover 시 빈 문자열, non-empty 시 한국어 표 + 4 룰 reminder 1줄.
- [x] `STAGE2_USER_TEMPLATE` 에 `{carryover_context}` placeholder 추가 (기존 placeholder 시그니처 검증 test 갱신).
- [x] `STAGE2_SYSTEM` 에 4-rule block 삽입 (DoD 의 4 항 그대로). 룰 ID prefix `CARRY-` 로 grep 용이.
- [x] `BriefingDocument` 모델 변경 *없음* — markdown post-process 가 표 insert.
- [x] **AC 매핑**: AC#3.
- [x] **영향 파일**: `src/investo/briefing/prompts.py`, `src/investo/briefing/pipeline.py` (signature 확장).

### Step 4 — Publisher renderer (`publisher/carryover.py`)

- [x] `render_carryover_block(carryover)` — Markdown 표 + 표 escape.
- [x] `inject_carryover_block(markdown, block)`:
  - § ② heading 종료 후 다음 § (보통 ③) 의 시작 *전* (즉 § ②와 § ③ 사이) 가 1st 후보 — 하지만 § ⑥ 앞 / § ② 뒤 사이는 § ③, § ④, § ⑤ 가 끼어 있어 명확치 않음.
  - **결정**: § ② 종료 직후 (§ ③ 시작 직전) 에 박는다. AC#4 의 "§② 뒤, §⑥ 앞" 범위 안에 들어가며, reader 가 carryover 를 본 후 sector / 지표 / 종목을 읽도록 reading order 유지.
  - 이미 "## Watchlist Carryover" 가 있으면 (idempotent re-run) replace.
- [x] 빈 block → markdown 무수정 (단 stale block 있으면 strip).
- [x] **AC 매핑**: AC#4, AC#5.
- [x] **영향 파일**: `src/investo/publisher/carryover.py` (신규).

### Step 5 — Orchestrator wire-through (`orchestrator/pipeline.py`)

- [x] `_load_carryover_for_run(now_utc, segments, candidates_by_segment, archive_root) -> dict[str, BriefingCarryover]` — segment 별 isolation.
- [x] Stage 2 호출 직전 `BriefingCarryover` 를 `generate_briefing` 에 전달, Stage 2 결과 markdown 에 `inject_carryover_block` 적용.
- [x] 빈 carryover (`is_empty=True`) → orchestrator 가 inject 자체 skip — markdown 변경 없음.
- [x] env override `INVESTO_CARRYOVER_LOOKBACK_DAYS` (default 3, clamp `[1, 7]`, invalid → warning log + default).
- [x] **AC 매핑**: AC#2, AC#5, AC#6.
- [x] **영향 파일**: `src/investo/orchestrator/pipeline.py`.

### Step 6 — 회귀 테스트 + quality gate

- [x] `tests/unit/models/test_carryover.py` (C1).
- [x] `tests/unit/briefing/test_carryover_parser.py` (C2 + C3 + C4) — fixture archive markdown 3 파일 합성 (실제 archive 의 일부 ② / ⑥ 섹션을 잘라 sanitize 한 mini 샘플).
- [x] `tests/unit/publisher/test_carryover_renderer.py` (C6).
- [x] `tests/unit/orchestrator/test_carryover_wire.py` (C7 + C8 idempotent).
- [x] `tests/unit/briefing/test_prompts_carryover.py` (C9).
- [x] `tests/unit/briefing/test_extract.py` (C5) — 기존 grep guard 가 신규 파일 포함 통과 확인 (`test_no_surface_redeclares_prefix_literal`).
- [x] Full gate.
- [x] **AC 매핑**: AC#7.
- [x] **영향 파일**: `tests/unit/...` (신규 5 파일).

### Step 7 — (선택) FR 등록

- [ ] `aidlc-docs/inception/requirements/` bridge 에 신규 FR-XXX "day-over-day carryover" 추가 검토 — 현 cross-check 흐름상 FR 등록 필수는 아님 (사용자 회고 → unit 으로 직접 매핑). 본 step 은 implementation 후 cross-check 시점에 다시 결정. (DEFERRED — planner 가 cross-check 단계에서 처리)
- [ ] **영향 파일**: (조건부) `docs/requirements.md`, `aidlc-docs/inception/requirements/bridge.md`. (DEFERRED)

---

## Step Dependency Graph

```
Step 1 (모델)
   │
   ├──► Step 2 (파서) ──┐
   │                    │
   ├──► Step 3 (prompt) ─┤
   │                    │
   └──► Step 4 (renderer) ─┤
                          │
                          ▼
                       Step 5 (orchestrator wire)
                          │
                          ▼
                       Step 6 (테스트 + gate)
                          │
                          ▼
                       Step 7 (선택 FR 등록 — 별도)
```

Step 1 은 prerequisite (모델). Step 2/3/4 는 Step 1 만 의존 — 병렬 가능. Step 5 는 2/3/4 모두 의존. Step 6 은 마지막. Step 7 은 implementation 후 cross-check 단계.

---

## NFR AC Coverage Map

본 unit 은 신규 NFR AC 를 추가하지 않음. 기존 NFR AC 호환:
- **NFR-001 (운영비 0)**: 새 LLM 호출 / 새 외부 API 호출 없음 — archive markdown 만 읽음.
- **NFR-002 (Anthropic SDK ban)**: 무관 (LLM 호출 surface 변경 없음, prompt 만 확장).
- **NFR R6 (idempotent FR-006)**: `inject_carryover_block` idempotent + orchestrator deterministic 표 override — 같은 (segment, date) 재실행 byte-equal (C8 핀).
- **NFR R10 (record/replay)**: 무관 (외부 API 호출 없음).
- **NFR R13 (secret hygiene)**: 무관 (carryover 항목은 public archive markdown 만 source).

---

## Project rule compliance

- **Anthropic SDK ban**: 무관 (LLM 호출 surface 변경 없음).
- **모듈 경계**: `models/carryover.py` (foundation) ← `briefing/carryover_parser.py` ← `briefing/prompts.py` / `briefing/pipeline.py` ← `orchestrator/pipeline.py` ← `publisher/carryover.py`. `briefing` → `publisher` import 금지 룰 보존 — orchestrator 가 양쪽 호출.
- **R8 (no raw stdlib XML)**: 무관 (markdown parsing 만, XML 부재).
- **R10**: 신규 외부 API 호출 없음.
- **R13**: archive markdown 은 publish 시점에 u27 redaction 통과 — carryover 추출은 정제된 후 surface 를 다시 읽으므로 신규 leak vector 무. 단 `note` 필드는 LLM 이 발명할 가능성 → deterministic 표가 LLM 발명 override 함 (DoD).
- **R14**: 무관.
- **무료 API only**: 무관.
- **Disclaimer enforcement**: § ⑦ disclaimer 위치 미변경 (carryover 표는 § ② / § ③ 사이).
- **DEBT-060 chokepoint**: 6번째 consumer 등장 — `briefing/extract.py` 의 4 함수 모두 재사용; 신규 파일에 prefix literal 재선언 0건 (C5 grep guard 가 자동 enforce).

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (1872 → 1910, +38 신규 테스트)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **N>7 일 walk-back / 주간 retrospective rollup** — u44 `monthly_retrospective` 와 별 surface. 본 unit 은 daily 3-day window 만.
- **Cross-segment carryover** (us-equity 의 어닝 이슈가 crypto 시황에 carry-over) — 같은 segment 내 walk-back 만; cross-segment 는 별 unit.
- **LLM-driven event classification** — `event_type` 은 결정론 regex 만. LLM classification 은 비결정성 + 환각 risk.
- **자동 hit-rate 측정** — 어제의 예고가 오늘 실제 어떤 결과로 끝났는지 (price action) 측정은 u44 `accuracy.py` surface 와 중복. carryover 는 *언급 여부* 만 track; price-action verification 은 out of scope.
- **Telegram carryover 표 임베드** — Telegram 페이로드 길이 제약 + reader UX 가 한 화면 압축인 점 고려. 표는 사이트만; Telegram 은 § ② 의 bridge 문장 (LLM 이 룰 #3 에 의해 자동 생성) 으로만 노출.
- **시각화 (carryover Sankey / timeline)** — 표 형식이 MVP. visual surface 는 별 unit.
- **DEBT-067 (lookahead adapter 부재)** 와 의존 — carryover 표의 unresolved 항목 source 는 § ⑥ 본문 + u35 lookahead 표; lookahead 표가 비어있으면 unresolved 항목이 적어질 뿐, 본 unit 의 핵심 기능 (어제 예고된 것의 오늘 결과 인용) 은 영향 없음.

---

## Open questions

- **archive 파서 견고성** — § ⑥ 본문이 LLM 출력 free-form 이라 정규식 hit-rate 가 100% 가 아닐 수 있음. 합성 fixture 로 6 shape 핀 (DoD C2 5 shape + 1 malformed) 했지만 *실제 archive* 회귀 검증 필요. 권장: Step 6 끝나면 `archive/us-equity/2026/05/` 의 실제 4 파일 (05-06/05-07/05-08/05-11) 에 파서 dry-run + 추출 결과 sanity check 1회 (Code Generation closeout 시점).
- **u51 segmented-format 호환** — u51 (병렬 작성 중) 이 segmented briefing 의 출력 markdown format 을 바꾸면 본 unit 의 § ⑥ heading 정규식 / § ⑥ 본문 list-item 정규식이 깨질 risk. 권장: u51 plan 확정 시점에 본 unit 의 Step 2 영향 분석 1회; 깨질 경우 u51 implementation 직후 본 unit re-plan. 대안: 파서를 markdown-tree 기반 (e.g., `markdown-it-py`) 으로 작성하면 heading depth 만 의존하므로 robustness 향상 — 단 신규 dep 추가 (pyproject) 가 무료/순수 stdlib 룰 (NFR R10 spirit) 와 trade-off. **MVP 결정**: 정규식 + § heading 텍스트 anchor. u51 충돌 시 re-plan.
- **status="resolved" 판정의 정밀도** — `ticker_or_topic` substring 매치는 false-positive risk (ticker `TM` 이 일반 단어 `tm` 매치). 권장: ASCII ticker 는 word-boundary `\b` + uppercase preservation; 한국어 토픽 (예: "FOMC 의사록") 은 substring + ≥4-char 길이 요건. 정밀도 부족 시 DEBT-D52-A 후보.
- **event_type 닫힌 셋 6 의 충분성** — 사용자 evaluation 의 5 결함 중 "DGS10/UST/FRED/Regulation FD 용어가 매일 재정의" 는 carryover event 가 아닌 *용어 메모리* 문제 — u40 `financial-acronym-glossary` 가 부분 cover. 본 unit 의 `event_type` 셋은 ticker/이벤트 carryover 만 — terminology carryover 는 별 unit (u40 확장).
- **§ ② 뒤 / § ⑥ 앞 insert 위치 정확 결정** — DoD 는 "§ ② 종료 직후 (§ ③ 시작 직전)" 라고 fix 했지만 reader UX 가 다를 수 있음. 권장: Step 4 implementation 후 mkdocs serve 수동 비교 — § ② 뒤 vs § ⑤ 뒤 vs § ⑥ 직전. AC#4 의 "§② 뒤, §⑥ 앞" 만족하면 OK.
- **u34 와의 prompt 충돌** — u34 가 `{recent_context}` 로 narrative 결론을 인용시키는데, 본 unit 이 `{carryover_context}` 로 표를 더 강하게 박으면 LLM 이 둘 다 따르려다 prompt overflow / 한쪽 누락 risk. 권장: Step 3 implementation 시 STAGE2_SYSTEM 의 룰 ordering 명시 — carryover 룰을 narrative 룰보다 *뒤에* 두고 "carryover 표는 § ⑥ 직전이며 narrative bridge 는 § ②" 라고 surface 분리 강조.
- **DEBT 후보** — (D52-A) substring 매치 정밀도, (D52-B) event_type 셋 확장 (예: ESG / regulation), (D52-C) markdown-tree 파서 전환. Implementation closeout 시점에 등록 검토.

---

## How to Approve

Step 6 의 quality gate 통과 + 사용자 archive sanity check (Open question #1) 통과 후, lead 에게 "Step 1-6 완료, sanity check OK" 보고. lead 가 "1. Request Changes / 2. Continue to Next Stage" 2-옵션 제시. 사용자가 "2" 선택 시 본 unit closeout 처리 (summary.md + aidlc-state 행 Complete 마킹 + audit entry).
