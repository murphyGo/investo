# Code Generation Plan: `u45 segment-routing-exclusivity`

**Date**: 2026-05-10
**Unit**: u45 segment-routing-exclusivity
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 2026-05-09 cron 미국 시황 quality 회고 (사용자 직접). Trace footer 기반 leak 진단 (메인 세션 2026-05-10).
**Estimated Effort**: ~2-3 h
**Dependencies**: 없음 (가장 먼저 착륙해야 후속 가격/anchor 유닛이 깔끔히 routing 됨)

---

## Goal

`segment_items()`가 한 아이템을 여러 세그먼트에 동시 라우팅하는 dual-routing 버그를 종결한다. priority-based + source-anchored 라우팅 룰을 도입해 — (1) 명시적 single-segment source는 항상 그 세그먼트로만, (2) shared source는 명시적 multi-segment allow-list로만, (3) 키워드-driven cross-routing은 강한 신호 (제목 시작 토큰 또는 ticker 직접 언급) 시에만 한쪽 세그먼트로 *이동* (복제 아님) 한다.

---

## Persona evidence

> 사용자 (2026-05-09 cron 회고): "BTC/ETH 얘기가 너무 많음 — us-equity 시황인데 4개 섹션이 크립토 narrative로 지배. 전반적으로 중심 없는 느낌."

오늘 us-equity trace footer 분석으로 확인된 leak (`archive/us-equity/2026/05/2026-05-08.md`):

- **Item #54** — `theblock-crypto: "Hyperliquid loss"` — 본문에 "SEC" 단어가 있어 `_is_us_equity` 의 `_US_MARKET_TERMS` 매치 → us-equity ② 섹션 진입.
- **Item #76** — `yahoo-finance: "Bitcoin and ethereum prices today"` — `yahoo-finance` 가 `_US_SOURCES` 멤버라서 source 매치만으로 us-equity 진입; 본문이 비트코인이어도 us-equity 에 잡힘.
- **Item #82** — `yahoo-finance: "7 ideas from Consensus"` (크립토 컨퍼런스 기사) — 위와 동일.

`segments.py:259-266` 확인: `if/if/if` (NOT `elif/elif/elif`) — 한 item이 `domestic`, `us`, `crypto` list 에 동시 append 가능. `segments.py:373-394` 의 `_is_us_equity` 가 `"sec "`, `"federal reserve"`, `"fomc"`, `"treasury"` 키워드로 광범위 매치 → SEC 규제·Fed 발언 다룬 크립토 뉴스가 us-equity에 진입.

---

## Definition of Done

- [ ] `segment_items()`이 한 `NormalizedItem`을 최대 한 세그먼트로만 라우팅한다 (현재 multi-segment 등록된 shared source — 예: `treasury-rates`, `fred-economic-calendar` — 의 의도적 cross-routing은 *명시적 multi-segment allow-list* 로만 표현).
- [ ] Source-anchored 룰 우선순위:
  - source가 `_CRYPTO_SOURCES` 단독 멤버 (e.g., `theblock-crypto`, `coingecko-events`, `binance-crypto-market`, `defillama-market-structure`) → crypto 세그먼트로만.
  - source가 `_DOMESTIC_SOURCES` 단독 멤버 → domestic-equity 로만.
  - source가 `_US_SOURCES` 단독 멤버 → us-equity 로만 (단 본문에 강한 crypto signal 시 crypto 로 *이동*, 복제 아님; 자세한 룰은 Step 2 참조).
  - source가 명시적 `_SHARED_SOURCES` (treasury-rates / fred-* / us-economic-calendar / fomc-calendar 등 macro·rates 류) → 등록된 모든 세그먼트로 fan-out (현재 의도적 cross-routing 유지).
- [ ] 강한 crypto signal 정의 (us-equity 단독 source의 예외 이동 룰):
  - 제목이 `^(bitcoin|ethereum|btc|eth|crypto|stablecoin|defi)\b` (대소문자 무시, 첫 6 토큰 이내 등장) 으로 시작하거나
  - 본문에 `\bBTC\b` 또는 `\bETH\b` ticker 가 ASCII word boundary 로 등장하거나
  - 제목이 명시적 crypto 가격·차트 phrase (예: `"bitcoin price"`, `"ethereum price"`, `"btc price"`) 와 substring 매치.
  - 위 조건 하나 이상 매치 시 — **us-equity 에서 제거하고 crypto 로 라우팅** (더 이상 us-equity에 안 잡힘).
- [ ] `_US_MARKET_TERMS` (`"sec "`, `"federal reserve"`, `"fomc"`, `"treasury"`) 단독 매치는 더 이상 us-equity 라우팅을 트리거하지 않는다 — source allow-list 에 들어있어야 only routing 된다 (키워드는 *추가 신호*, 단독 entry 자격 아님).
- [ ] `_CRYPTO_CROSS_MARKET_TERMS` 의 Fed/FOMC 결합 룰은 `_is_crypto` 에서만 평가 — `_is_us_equity` 가 같은 키워드를 다시 매치해 두 세그먼트 동시 routing 을 일으키는 일은 없다.
- [ ] 회귀 테스트 (`tests/unit/briefing/test_segments_exclusivity.py`):
  - **R1**: `theblock-crypto` source + 본문 `"SEC charges Hyperliquid"` → crypto 만, us-equity 없음 (Item #54 anti-regression).
  - **R2**: `yahoo-finance` source + 제목 `"Bitcoin and ethereum prices today"` → crypto 만, us-equity 없음 (Item #76 anti-regression).
  - **R3**: `yahoo-finance` source + 제목 `"S&P 500 reaches new high"` → us-equity 만, crypto 없음.
  - **R4**: `treasury-rates` source (shared) → us-equity + crypto 양쪽 라우팅 유지 (의도적 cross-routing 보존).
  - **R5**: `cnbc` source + 본문 `"Federal Reserve hints at rate cut"` → us-equity 만 (Fed 키워드 단독은 us-equity 에서만 평가, crypto 동시 진입 안 함; 단 `_CRYPTO_CROSS_MARKET_TERMS` 가 본문에 *없으면* crypto 로 가지 않음).
  - **R6**: `theblock-crypto` source + 본문 `"Federal Reserve and BTC"` → crypto 만 (source-anchored 우선; us-equity 진입 안 함).
  - **R7**: 어느 세그먼트에도 안 잡히는 item (e.g., 일반 매크로 헤드라인 + non-allow-list source) → 모든 세그먼트 0 — orphan 폐기 동작 보존.
- [ ] 한 item 이 두 세그먼트에 동시에 들어가지 않음을 보장하는 invariant 테스트: `for item in items: count = sum(item in seg for seg in [domestic, us, crypto]); assert count <= 1` (단 shared-source 등록 item 은 명시적 예외 처리).
- [ ] Trace footer / 시황 ② 섹션의 leak 재현 테스트는 closed; 향후 `_US_MARKET_TERMS` 확장 시 anti-regression 자동 발동.
- [ ] 전체 quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅ (예상 +12-18 신규 테스트), `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Source allow-list 정리

- [ ] `segments.py` 의 source 상수를 명시적 single vs shared 로 재구성:
  - `_CRYPTO_ONLY_SOURCES` (single-segment crypto)
  - `_DOMESTIC_ONLY_SOURCES` (single-segment domestic)
  - `_US_ONLY_SOURCES` (single-segment us-equity)
  - `_SHARED_SOURCES_BY_SEGMENT: Mapping[MarketSegment, frozenset[str]]` — 현재 cross-routing 되는 shared source (treasury-rates / fred-economic-calendar / us-economic-calendar / fomc-calendar 등) 의 명시적 등록.
- [ ] 기존 `_DOMESTIC_SOURCES` / `_US_SOURCES` / `_CRYPTO_SOURCES` 상수는 single + shared 합집합으로 derive (backward-compat — 외부 import 가 있으면 깨지면 안 됨; `segment_source_outcomes` 가 사용 중).
- [ ] 파일: `src/investo/briefing/segments.py`.

### Step 2 — Routing 결정 로직 재작성

- [ ] `segment_items()` 의 `if/if/if` 를 priority-based + crypto signal override 로 교체:

```
for item in items:
    text = _item_text(item)
    title_lower = item.title.lower()

    # 1) shared sources fan-out (treasury / fred / fomc-calendar 등)
    matched_shared = _matched_shared_segments(item)
    if matched_shared:
        for seg in matched_shared:
            buckets[seg].append(item)
        continue

    # 2) source-anchored single-segment routing
    if item.source_name in _CRYPTO_ONLY_SOURCES:
        crypto.append(item)
        continue
    if item.source_name in _DOMESTIC_ONLY_SOURCES:
        domestic.append(item)
        continue
    if item.source_name in _US_ONLY_SOURCES:
        if _has_strong_crypto_signal(item, title_lower, text):
            crypto.append(item)        # 이동, 복제 아님
        else:
            us.append(item)
        continue

    # 3) 어느 source allow-list 도 매치 못한 item — keyword fallback
    if _is_domestic_equity_keyword_only(item, text):
        domestic.append(item)
    elif _has_strong_crypto_signal(item, title_lower, text):
        crypto.append(item)
    elif _is_us_equity_keyword_only(item, text):
        us.append(item)
    # else: orphan 폐기
```

- [ ] 신규 헬퍼 `_has_strong_crypto_signal(item, title_lower, text) -> bool`:
  - `_CRYPTO_TITLE_PREFIX_RE = re.compile(r"^\s*(bitcoin|ethereum|btc|eth|crypto|stablecoin|defi)\b", re.IGNORECASE)` — 제목 시작 매치.
  - `_CRYPTO_TICKER_RE = re.compile(r"\b(BTC|ETH)\b")` — title + summary ASCII word-boundary 매치 (`text.upper()` 위에 evaluate).
  - `_CRYPTO_PRICE_PHRASES = ("bitcoin price", "ethereum price", "btc price", "eth price", "bitcoin and ethereum")` — substring 매치 (lower-case).
- [ ] `_is_us_equity` 의 `_US_MARKET_TERMS` 매치는 keyword-fallback path 에서만 평가 — source-anchored item 이 키워드만으로 us-equity 에 들어가는 경로는 사라진다 (R1, R2 leak 차단).
- [ ] `_is_crypto` 의 `_CRYPTO_CROSS_MARKET_TERMS` + Fed 결합 룰은 keyword-fallback path 에서만 평가; source allow-list 매치한 item 은 그 source 의 segment 로만.

### Step 3 — Anti-regression 테스트

- [ ] 신규 `tests/unit/briefing/test_segments_exclusivity.py` (R1-R7 케이스 전부).
- [ ] 추가: invariant 테스트 — fixture mix (각 source 카테고리 ≥1 item) 에 대해 `assert sum(membership) <= 1 for non-shared items`.
- [ ] 기존 `tests/unit/briefing/test_segments.py` 는 변경 없이 통과해야 함 (현행 동작 중 valid 한 부분은 유지). 회귀 발생 시 fix.

### Step 4 — 검증

- [ ] `ruff check`, `ruff format --check`, `mypy --strict`, `pytest -q`, `mkdocs build --strict` 전부 green.
- [ ] 2026-05-08 archive trace footer 재처리 시뮬레이션: Item #54 / #76 / #82 가 us-equity 에서 사라지고 crypto 에 (또는 orphan 으로) 들어가는지 확인.

---

## Project rule compliance

- **Anthropic SDK ban**: 무관.
- **모듈 경계**: `briefing/segments.py` 만 수정 — `sources/` / `notifier/` / `publisher/` import 추가 없음.
- **R8 (no raw stdlib XML)**: 무관 (텍스트 키워드 매치만).
- **R10**: live API 호출 없음; 기존 fixture 의 normalized item shape 만 사용.
- **R13**: 신규 secret 없음.
- **무료 API only**: 무관.

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (예상 +12-18 신규 테스트)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **신규 가격 source 도입** — u46 stooq-price-primary 에서 처리.
- **결정론적 시장 anchor 계산** — u49 deterministic-market-anchor.
- **개인금융 노이즈 필터** — u47 yahoo-finance-news-content-filter.
- **차트 임베드** — u50.
- **Stage 2 prompt 의 BTC/ETH narrative balance 강제 룰** — 라우팅 fix 만으로 입력 dominance 가 사라지면 prompt 수정 불필요. 향후 재발 시 별 unit.

---

## Open questions

- **Shared source 등록 검증**: 현재 cross-routing 되는 source 가 정확히 `treasury-rates`, `fred-economic-calendar`, `us-economic-calendar`, `fomc-calendar` 4개인지, `_CRYPTO_SOURCES` 와 `_US_SOURCES` 양쪽에 등록된 모든 source 를 grep 해 확인할 것 (Step 1 의 `_SHARED_SOURCES_BY_SEGMENT` 에 빠진 source 가 있으면 의도적 cross-routing 이 깨짐).
- **`_US_MARKET_TERMS` 의 보존**: Fed/FOMC/Treasury 키워드는 keyword-fallback path 에서만 us-equity 라우팅을 트리거하지만, 이 path 는 어느 source allow-list 에도 안 잡힌 item (현실적으로 매우 드뭄) 에만 발동. 사실상 dead path 가 될 수 있음 — 만약 통계상 0건이 길게 지속되면 후속 cleanup unit 으로 제거 검토.
- **DEBT 후보**: `_has_strong_crypto_signal` 의 prefix regex 는 영어 title 가정 — 향후 한국어 크립토 뉴스 (e.g., 한경코인) source 추가 시 한국어 prefix 룰 확장 필요. plan 종료 시 candidate DEBT 등록.
