# Code Generation Plan: `u47 yahoo-finance-news-content-filter`

**Date**: 2026-05-10
**Unit**: u47 yahoo-finance-news-content-filter
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-09 cron 미국 시황 quality 회고 (사용자 직접). yahoo-finance-news 입력 24건 중 ~10건이 개인금융 상품 비교 노이즈.
**Estimated Effort**: ~1-2 h
**Dependencies**: 없음 (어댑터 단독 변경; u45 / u46 와 독립)

---

## Goal

`yahoo-finance-news` 어댑터의 generic feed 에 섞여 들어오는 개인금융 상품 비교 헤드라인 (CD rates / HELOC / mortgage / savings / insurance / retirement) 을 어댑터 fetch 단계에서 차단해, Stage 1 LLM token budget 과 Stage 2 시야 분산을 줄인다. 차단된 항목 비율은 INFO 로그로 노출해 향후 패턴 튜닝의 카나리로 사용한다.

---

## Persona evidence

> 사용자 (2026-05-09 cron 회고): "전반적으로 중심 없는 느낌."

2026-05-08 yahoo-finance-news 입력 24건 중 시장 신호가 아닌 개인금융 헤드라인 ~10건 (확인된 케이스):

- "Best CD rates today, May 8, 2026"
- "HELOC and home equity loan rates today, May 8, 2026"
- "Mortgage and refinance interest rates today, May 8, 2026"
- "Best high-yield savings interest rates today, May 8, 2026"
- "Best money market account rates today, May 8, 2026"
- "Hidden Retirement Costs You Should Plan For"
- "Is $7,000 Per Year Too High for Long-Term Care Insurance?"

Stage 1 LLM 이 거의 다 unassigned 시켰지만 (1) Stage 1 token 소비, (2) Stage 2 가 보는 candidate pool 에 잡음으로 남음, (3) 시장 narrative 가 흐려짐 (사용자 회고 인용). 어댑터 단계 차단이 가장 cheap.

---

## Definition of Done

- [ ] `src/investo/sources/yahoo_finance_news.py` (또는 어댑터 파일 위치) 에 `_PERSONAL_FINANCE_DENY_PATTERNS: tuple[re.Pattern[str], ...]` 또는 substring tuple 신규 등록.
- [ ] 패턴 (모두 case-insensitive 매치):
  - `cd rates`
  - `heloc`
  - `home equity loan rates`
  - `mortgage and refinance` / `mortgage and refi rates`
  - `high-yield savings`
  - `money market account rates`
  - `long-term care insurance`
  - `retirement costs`
  - `personal finance` (broad fallback)
- [ ] Filter 적용 위치: RSS/JSON 파싱 후 `NormalizedItem` 생성 *이전* — Stage 1 LLM 이 아예 보지 못하게.
- [ ] Filter 매치 시 INFO 로그 1줄 emit (배치 단위, item 단위 아님): `yahoo-finance-news: filtered N/M items as personal-finance noise (patterns: ...)` — N=차단 수, M=원래 fetch 수, patterns=hit 한 패턴 union (deduped). 향후 패턴 튜닝의 카나리.
- [ ] 차단 비율 100% (M=N) 인 경우 WARNING 로그 추가 — feed 가 패턴 폭주하거나 (정상 시장 뉴스가 아예 없거나) deny list 가 너무 광범위한 신호; 운영자가 봐야 하는 surface.
- [ ] R10 fixture (record/replay):
  - deny 패턴 각 6개 케이스 fixture (각 패턴이 매치하는 representative 헤드라인 — fabricated 아닌 실제 yahoo 응답에서 발췌 가능 — 실제 응답 record 시 자연스럽게 포함됨)
  - 정상 시장 뉴스 fixture 5개 (e.g., `"S&P 500 reaches new high"`, `"Tesla Q1 earnings beat estimates"`, `"Fed minutes signal cautious tone"`, `"Apple announces new product line"`, `"Bitcoin tops $100,000"`) — 보존 확인 (false positive 방지).
- [ ] 회귀 테스트 (`tests/unit/sources/test_yahoo_finance_news_filter.py`):
  - 9 패턴 각각 매치 케이스 → filter 후 0 items.
  - 5 정상 케이스 → filter 후 5 items 보존.
  - 혼합 fixture (deny 5 + 정상 3) → filter 후 정확히 3 items + INFO 로그 emit 검증.
  - 빈 응답 → filter 후 0 items, 로그 없음.
  - 100% 차단 케이스 → WARNING 로그 emit 검증.
- [ ] **R10 invariant**: deny 패턴 fixture 는 fabricated 가 아닌 yahoo-finance-news 의 실제 record 에서 발췌. 정상 케이스도 마찬가지 — `tests/fixtures/sources/yahoo_finance_news/personal_finance_noise.json` 와 `..._market_signal.json` 두 fixture 파일에 분리.
- [ ] 어댑터 외 변경 없음: `briefing/segments.py`, `orchestrator/`, `notifier/`, `publisher/` 미수정.
- [ ] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +8-12 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Deny 패턴 정의 + 적용 위치 결정

- [ ] `_PERSONAL_FINANCE_DENY_PATTERNS` 모듈 상수 정의 (substring tuple — 정규식보다 빠르고 디버깅 용이).
- [ ] `_is_personal_finance_noise(title: str) -> tuple[str, ...]` 헬퍼 — 매치된 패턴 list 반환 (빈 tuple = 노이즈 아님). 매치 우선순위 없이 union 반환 (로그 카나리에 사용).
- [ ] Filter 적용: `fetch()` 의 RSS/JSON parse loop 안, `NormalizedItem` 생성 *직전*.
- [ ] 파일: `src/investo/sources/yahoo_finance_news.py` (또는 정확한 어댑터 파일 — sources/ ls 로 확인).

### Step 2 — Fixture 녹화 (R10)

- [ ] 기존 yahoo-finance-news fixture 가 있다면 그 안의 노이즈 헤드라인 발췌하여 `personal_finance_noise.json` 생성 (또는 신규 record).
- [ ] 정상 시장 뉴스 5개 fixture (record 또는 기존 fixture 발췌).
- [ ] `_meta.json` sidecar (recorded_at + sha256).

### Step 3 — Filter + 로그 emit + 테스트

- [ ] 어댑터 fetch loop 에 filter 통합.
- [ ] INFO / WARNING 로그 emit (logging module — `redact_text(STRICT)` 적용 필요 없음; 패턴 매치는 secret-shaped 가 아님).
- [ ] 회귀 테스트 작성.

### Step 4 — 검증

- [ ] 전체 quality gate green.
- [ ] (수동) 2026-05-08 fixture 재처리 시뮬레이션: 24건 중 ~10건이 차단되고 ~14건이 통과하는지 INFO 로그 확인.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관.
- **모듈 경계**: `sources/yahoo_finance_news.py` 만 수정 — 다른 unit 파일 import 추가 없음.
- **R8 (no raw stdlib XML)**: yahoo-finance-news 가 RSS 인 경우 기존 `defusedxml.ElementTree` 사용 유지; filter 추가가 XML 파싱 룰을 변경하지 않음.
- **R10 (record/replay fixtures, no fabrication)**: deny 패턴 fixture 와 정상 시장 뉴스 fixture 모두 live-recorded byte-equal 본을 사용.
- **R13**: 신규 secret 없음 (yahoo-finance-news 인증 없음).
- **R14**: 무관 (UA 정책 변경 없음).
- **무료 API only**: 무관.

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (예상 +8-12 신규 테스트)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **다른 어댑터의 노이즈 필터** (cnbc, nasdaq-stocks-news, theblock-crypto 등) — 별 unit. Yahoo 가 가장 generic feed 이고 가장 노이즈 비율이 높음.
- **다른 노이즈 카테고리** (헬스 / 연예 / 가십 / 정치-비경제) — 별 unit. 이번 wave 는 개인금융 상품 비교만.
- **Stage 1 LLM 의 unassigned 룰 강화** — 어댑터 단계 차단으로 충분; LLM 룰 변경은 별 unit.
- **운영자 dashboard 통한 패턴 hit 통계** — INFO 로그가 GHA Step Summary 에 capture 되면 충분; 별 dashboard 불필요.

---

## Open questions

- **`personal finance` 패턴의 false-positive 위험**: "Personal Finance Q1 earnings" 같은 시장 헤드라인이 매치할 가능성 — fixture 5 정상 케이스로 검증; 실제 false-positive 발견 시 패턴을 더 좁힘 (e.g., `personal finance tip`, `personal finance advice`).
- **Localization**: 이 unit 은 영어 헤드라인만 대응. 한국어 yahoo / 네이버 금융 노이즈는 별 unit.
- **DEBT 후보**: deny 패턴이 시간이 지나면 stale 해질 수 있음 — quarterly review 룰 또는 자동 카나리 (차단 비율 < N% 면 alert) 등록 검토. Implementation closeout 시점에 candidate DEBT 로 등록.
