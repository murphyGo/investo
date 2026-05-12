# Code Generation Plan: `u56 compliance-language-and-observational-tags`

**Date**: 2026-05-13
**Unit**: u56 compliance-language-and-observational-tags
**Stage**: Code Generation
**Status**: 📋 Planned (re-hardened)
**Source**: 2026-05-13 10-subagent evaluation of generated market briefings, deduplicated against u51/u52/u53/u54/u55. Re-hardened on the same date to absorb evaluation Finding #5 (crypto-specific 면책) and Finding #12 (한국 retail 톤 / 종결 어미 다양성).
**Estimated Effort**: ~5-6 h
**Dependencies**:
- u21 summary-quality-gate (publish-time first-viewport validation; structured WARN logging contract).
- u23 notification-actionability (Telegram summary surface; tag substring extraction).
- u25 summary-fidelity-and-content-trust (conservative wording, baseline P0/P1 inventory).
- u51 tldr-block-and-number-bold-inversion (`publisher/reader_format.py`; §⑥ 액션 ratio carry — 본 unit 의 종결 어미 cap 이 같은 surface 확장).
- u52 prior-briefing-context-and-carryover (carryover 표가 본 unit 의 phrase gate 통과해야 — 무관 surface 지만 cross-test 필요).
- u7 segmented-briefing (Stage-2 segment-aware prompt; 본 unit 의 ActionTag 마이그레이션 + crypto-only P0 가 segment 분기).

---

## Deduplication Boundary

Excluded because already owned elsewhere:
- u51: §⑥ "여부" 가족 어구 비율 (관찰형 종결) — *그대로 둠*. 본 unit 의 종결 어미 다양성 cap 은 **전체 본문 surface** 대상이라 별 metric.
- u52: prior-day bridge and carryover.
- u53: data input expansion.
- u54: source status severity / quality-KPI history.
- u55: numeric/factual verification (별 gate; 본 unit 은 *wording* 만).

This unit owns **regulatory/compliance language risk** + **first-viewport short disclaimer (segment-aware)** + **retail tone caps**. It does NOT own reader scanability (u51), numeric fidelity (u55), or coverage trust (u54).

---

## Goal

Prevent generated briefings and Telegram summaries from drifting into investment-advice wording or 한국 retail 토착 어법, and harden the disclaimer surface so the canonical footer (NFR-004 R5) is necessary-but-no-longer-alone:

1. **Action-instruction wording** — Stage-2 prompt allows `매수 검토 / 비중 축소 / 헤지 확대 / 손절 라인 설정`. P0 phrase gate at publish time.
2. **Korean retail-coded terms** — `평단가 / 추격매수 / 물타기 / 세력 / 김프 진입` 류 (자본시장법 §17, 가상자산이용자보호법 §10 disorderly-market 조항). P0 (특히 crypto-only subset).
3. **Quantified outcome promises** — `30% 이상 수익 가능 / 2배 수익 예상` 류. P0 regex.
4. **Action tags as stance** — `[강세] / [약세]` reads as a buy/sell stance. Replace with observation labels.
5. **Footer-only disclaimer is brittle** — reader scrolling decides on first viewport. Add a *short* segment-aware information-only disclaimer above `## 한눈에 보기`, **without** weakening the canonical footer (verify_disclaimer remains the gate).
6. **Crypto needs its own footer** — 가상자산이용자보호법 §10 / §19 (2024.07.19 시행) 가 가상자산을 별도 카테고리로 명시. 동일 면책 텍스트는 법적 불완전. crypto segment 한정 `DISCLAIMER_CRYPTO` 추가.
7. **단일 종결 어미 일색** — Finding #12. `~다 / ~된다 / ~이다 / 전망이다` 가 ≥ 60% 이면 retail 자동 생성물 톤. WARN-only cap.
8. **Filler phrase family cap** — `여부 / 전망 / 우려 / 가능성 / 작용` per-1000-chars 빈도. WARN-only cap.
9. **Context-aware false positives** — `진입 ("분야 진입")`, `청산 ("회사 청산")`, `목표가 (증권사 PT 인용)` 는 P0 hit 이면 안 됨. 2-pass classifier 로 demote.

The disclaimer footer remains untouched as the *publish gate*; new surfaces (first-viewport short disclaimer, crypto variant) are *additive*, never substitutive.

---

## Persona evidence

> 10-subagent quality 리뷰 (2026-05-13 session, archive 다일 cross-segment 대상). Findings #2/#3/#5/#12 가 본 unit 으로 라우팅:
> - subagent #2 (regulatory language): "`매수 검토 / 비중 축소` 류가 본문 §⑥ 에 평균 3-4건/일 — 단순 footer 면책으론 부족."
> - subagent #3 (token symmetry): "`매도 검토 / 편입 / 차익실현 / 익절 / 손절매 / 리밸런싱` 도 동일 추론 (단방향 banlist 비대칭)."
> - subagent #5 (crypto compliance): "크립토 면책조항이 주식과 byte-equal — 가상자산이용자보호법 reference 누락; 24시간 거래 / 원금 전액 손실 / 비제도권 자산 명시 부재."
> - subagent #7 (forecast hedging): "`30% 이상 수익 예상 / 2배 수익` 류 quantified outcome 이 §⑥ 에서 발견 — regex 로 차단해야."
> - subagent #11 (retail Korean): "`평단가 / 추격매수 / 물타기 / 세력` 같은 retail 토착어 — 자본시장법 §17 부정거래·시세조종 조항과의 거리상 P0."
> - subagent #12 (tone): "`-다` 종결 어미 일색. `여부 / 전망 / 우려` 가족 어구가 §② §③ §⑥ 횡단으로 반복 — 자동 생성물 시그니처."

---

## Definition of Done

- [x] Stage-2 segment-aware prompt forbids direct trading-action instructions and uses observation/check language; ActionTag 5종 (`[관망] [변동성↑] [강세] [약세] [혼조]`) 가 4종 observation 라벨 (`[상승 관찰] [하락 관찰] [혼재] [변동성 확대]`) 로 마이그레이션됨. 구→신 alias map 으로 backward-compat parser 지원.
- [x] `publisher/compliance_language.py` 신규 gate: P0 phrase 발견 시 `ComplianceLanguageError` raise (block publish); P1 phrase 발견 시 WARN + structured extra (segment / phrase / count / line_no); context-aware 2-pass classifier 가 false-positive 를 INFO 로 demote.
- [x] P0 banned phrase 리스트가 **세 카테고리** 로 구조화: (a) Action instruction (대칭 buy/sell), (b) Quantified outcome promise (regex), (c) Korean retail-coded (crypto-only subset 별도).
- [x] First-viewport short disclaimer (segment-aware) 가 `## 한눈에 보기` H2 *직전* 에 1줄 blockquote 로 emit; verify gate (`verify_short_disclaimer_first_viewport`) 가 *추가* — 기존 `verify_disclaimer` 와 직교, byte-equal 보존.
- [x] `briefing/disclaimer.py` 에 `DISCLAIMER_CRYPTO` 신규 상수 (가상자산이용자보호법 §10/§19 reference); `append_disclaimer(markdown, segment)` 시그니처 확장 + segment 별 변형 emit; `verify_disclaimer(briefing_md, segment)` 시그니처 확장; archive backward-compat (2026-05-13 cutoff 전 파일은 legacy=True flag 로 통과).
- [x] 종결 어미 다양성 cap: 단일 종결 어미 (`~했다 / ~된다 / ~이다 / 전망이다` 등 분류 후 dominant 종결) 비율 ≤ 60% — 위반 시 WARN (non-blocking).
- [x] Filler phrase family (`여부 / 전망 / 우려 / 가능성 / 작용`) per-1000-chars 빈도 ≤ 임계 (TBD per-implementation; 기본값 8.0/1000 chars 제안) — 위반 시 WARN (non-blocking).
- [x] 회귀 핀: 면책 footer 누락 → `verify_disclaimer` fail (existing); first-viewport short disclaimer 누락 → 신규 gate fail; crypto segment 에서 us-equity 면책 emit → `verify_disclaimer(segment="crypto")` fail; 셋 모두 충족시에만 publish 통과.
- [x] 전체 quality gate green: `uv run ruff check .` ✅, `uv run ruff format --check .` ✅, `uv run mypy --strict src/` ✅, `uv run pytest -q` ✅ (예상 +52-68 신규 테스트), `uv run mkdocs build --strict` ✅.

---

## AC ↔ Step traceability

| AC | Step | Verification |
|----|------|--------------|
| Stage-2 prompt forbids action wording | Step 1 | prompt text grep test |
| ActionTag 마이그레이션 (5→4) + alias map | Step 1, Step 7 | enum test + notifier substring test |
| P0 phrase gate (block) | Step 2 | unit test: synthetic P0 input → `ComplianceLanguageError` |
| P1 phrase WARN | Step 2 | caplog test |
| Quantified outcome regex | Step 2 | regex coverage test |
| Context-aware false-positive demote | Step 3 | 6-token-window classifier test |
| First-viewport short disclaimer (segment-aware) | Step 4 | placement + content test |
| `verify_short_disclaimer_first_viewport` gate | Step 4 | regression test: 제거 시 fail |
| `DISCLAIMER_CRYPTO` constant + 가상자산법 reference | Step 5 | constant test |
| `append_disclaimer(md, segment)` 시그니처 확장 | Step 5 | mypy + unit test |
| `verify_disclaimer(md, segment)` 시그니처 확장 | Step 5 | regression test: footer 제거 → fail |
| Archive backward-compat (legacy=True) | Step 5 | cutoff date test |
| 종결 어미 다양성 cap ≤ 60% | Step 6 | metric test: synthetic 균질 input → WARN |
| Filler phrase family per-1000-chars cap | Step 6 | metric test |
| `crypto` segment + us-equity 면책 = fail | Step 5, Step 8 | cross-segment regression |
| Notifier Telegram tag rendering (new ActionTag set) | Step 7 | summary builder test |
| Orchestrator wire-through | Step 8 | integration test |
| Quality gate green | Step 9 | CI |

---

## Steps

### Step 1 — Stage-2 prompt 룰 + ActionTag 마이그레이션 (5종 → 4종)

- [x] `src/investo/briefing/prompts.py` L218-226 의 closed-set ActionTag 5종 + publisher-forced `[데이터부족]` 모두 명시 변경:
  - **before**: `[관망] [변동성↑] [강세] [약세] [혼조]` + `[데이터부족]`
  - **after**: `[상승 관찰] [하락 관찰] [혼재] [변동성 확대]` + `[데이터부족]`
  - `[관망]` deprecate (data 부족과 의미 중복; `[데이터부족]` 로 흡수).
- [x] `src/investo/briefing/action_tag.py` (기존) 에 신규 enum + 구→신 alias map (`{"[강세]": "[상승 관찰]", "[약세]": "[하락 관찰]", "[혼조]": "[혼재]", "[변동성↑]": "[변동성 확대]", "[관망]": "[데이터부족]"}`). 과거 archive (2026-05-13 이전) 의 markdown 은 legacy 유지 — 법은 소급 안 됨; pin-test 업데이트만.
- [x] `prompts.py` 의 시황 작성 룰에 P0 forbid 명시:
  - "다음 어구를 사용하지 말 것: `매수 검토, 매도 검토, 비중 축소, 비중 확대, 편입, 차익실현, 익절, 손절, 손절매, 진입, 청산, 목표가, 리밸런싱, 평단가, 추격매수, 물타기, 반드시, 확실, 보장`"
  - "관찰 동사로 종결: `관찰 / 확인 / 점검 / 비교 / 추세 살피기`"
  - "수치 + 수익/상승 보장 표현 금지 (예: `30% 이상 수익 예상`, `2배 상승`)"
  - CARRY-3 (L347) 의 `[강세] → [약세]` 인용을 `[상승 관찰] → [하락 관찰]` 로 갱신.
- [x] segment 별 prompt 가 분리되어 있다면 (`prompts/us_equity.py`, `prompts/crypto.py`, `prompts/domestic_equity.py`) 동일 룰 사본; crypto prompt 에는 추가 P0 (`세력, 김프 진입, 상폐 임박, 에어드랍 확정, 펌핑`) 명시.
- [x] 단위 테스트 `tests/unit/briefing/test_prompts_p0_forbid.py` (예상 6-8 tests): prompt text 가 P0 phrase 를 *포함하지 않음* (negative grep) / ActionTag 4종이 prompt 에 등장 / 구 tag 가 등장하지 않음.

### Step 2 — Compliance phrase gate (publisher P0 + P1)

- [x] 신규 모듈 `src/investo/publisher/compliance_language.py`:
  - `BANNED_P0_ACTION: tuple[str, ...]` — 대칭 buy/sell action: `매수 검토, 매도 검토, 비중 축소, 비중 확대, 편입, 차익실현, 익절, 손절, 손절매, 리밸런싱, 진입, 청산, 목표가, 반드시, 확실, 보장, 평단가, 추격매수, 물타기`.
  - `BANNED_P0_CERTAINTY: tuple[str, ...]` — `급등 예상, 급락 임박, 불가피, 필연`.
  - `BANNED_P0_QUANTIFIED_OUTCOME: tuple[re.Pattern, ...]` — `r"\d+%\s*(이상|이상의)?\s*(수익|상승|하락|손실)\s*(예상|가능|기대|보장)"`, `r"\d+\s*배\s*(수익|상승)"`.
  - `BANNED_P0_CRYPTO_ONLY: tuple[str, ...]` — `세력, 김프 진입, 상폐 임박, 에어드랍 확정, 펌핑` (가상자산이용자보호법 §10 disorderly-market 대응; segment="crypto" 일 때만 active).
  - `WARN_P1: tuple[str, ...]` — `직접 반영된다, 작용할 전망` + 폐쇄 인과 regex 카탈로그: `r"(주가|지수|가격)[가-힣\s]{0,4}(때문에|로 인해)[가-힣\s]{0,8}(했다|한다)"`. WARN 만 — soften 자동 변환 *안 함* (LLM 영역 침범 방지).
  - `class ComplianceLanguageError(PublisherError)` — P0 hit 시 raise. publish 차단.
  - `def scan_compliance(markdown: str, segment: SegmentSlug) -> ComplianceReport` — pure 함수 (str + segment → frozen pydantic report). orchestrator 가 호출.
- [x] `compliance_language.py` 의 모든 phrase / regex 는 `src/investo/models/compliance_phrases.py` (신규 또는 기존 models 확장) 에 상수로 export — briefing prompt 와 publisher gate 가 동일 source 참조 (drift 방지). 모듈 경계 룰 (orchestrator 만 cross-import) 위반 없음: phrase list 는 모두가 의존하는 *데이터* 이므로 `models/` 에 위치.
- [x] 단위 테스트 `tests/unit/publisher/test_compliance_language.py` (예상 14-18 tests): 각 P0 카테고리 hit → `ComplianceLanguageError`; crypto-only phrase 가 us-equity segment 에서는 detect 안 됨 / crypto segment 에서만 detect; quantified outcome regex 의 false-positive 검사 (예: `12% 상승했다` 사실 보고는 통과, `12% 상승 예상` 은 P0); P1 phrase → WARN only.

### Step 3 — Context-aware false-positive filter (2-pass classifier)

- [x] `compliance_language.py` 에 `_demote_if_quotative(phrase: str, line: str, position: int) -> Severity` 추가. 6-token window (좌 3 / 우 3) 검사:
  - `진입` 좌우에 `분야 / 시장 / 사업` → INFO (예: "AI 분야 진입").
  - `청산` 좌우에 `회사 / 기업 / 법인 / 파산 / 합병` → INFO (예: "회사 청산").
  - `목표가` 좌측에 `증권사 / 애널리스트 / 보고서 / IR / [A-Z]{2,5}` (증권사 약어 패턴) → INFO (예: "삼성증권 목표가 70,000원" — quotative pattern).
  - `목표가` bare (좌측 quotative marker 없음) → P0 유지 (예: "목표가 7만원").
  - `손절` 좌측에 `손절매 알고리즘 / 손절 라인 / 시스템 손절` → INFO 안 함 (자기 손절 권유 의미 유지 시 P0).
- [x] 단위 테스트 `tests/unit/publisher/test_compliance_language_context.py` (예상 10-14 tests): 각 demote rule 의 positive/negative; `목표가` quotative vs bare; window 경계 (좌 3 / 우 3 tokens exactly).
- [x] **No code blocks / tables**: 코드 블록 (``` `) / 표 cell (`|...|`) 내부의 P0 hit 는 scan 대상 제외 (LLM 이 발생시킬 가능성 거의 zero 이지만 idempotent 보장).

### Step 4 — First-viewport short disclaimer (segment-aware)

- [x] `src/investo/publisher/reader_format.py` 확장 (u51 inflated):
  - `def emit_first_viewport_disclaimer(text: str, segment: SegmentSlug) -> str` — `## 한눈에 보기` H2 *직전* 에 1줄 blockquote 삽입:
    - us-equity / domestic-equity: `> 정보 제공용 자동 시황이며 매매 권유가 아닙니다.`
    - crypto: `> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. 가상자산은 가격 변동성이 매우 큽니다.`
  - `## 한눈에 보기` 부재 시: anchor table 직전 (fallback) 또는 본문 첫 줄 (fallback²).
  - idempotent: 이미 short disclaimer 가 있으면 noop.
- [x] `src/investo/publisher/verifier.py` 에 신규 함수 `def verify_short_disclaimer_first_viewport(briefing_md: str, segment: SegmentSlug) -> bool`. 첫 30 rendered lines 안에 segment-appropriate short disclaimer substring 이 있는지 검사.
- [x] **Invariant**: 신규 gate 는 *추가*. 기존 `verify_disclaimer` 시그니처 byte-equal 유지 (단, segment 인자 추가 — 다음 step). orchestrator 가 *둘 다* 호출.
- [x] 단위 테스트 `tests/unit/publisher/test_first_viewport_disclaimer.py` (예상 10-12 tests): segment 별 emit 텍스트 정확성 / 위치 (`## 한눈에 보기` 직전) / idempotent / fallback paths / 첫 30 라인 안에 위치 / verify 정확성.

### Step 5 — `DISCLAIMER_CRYPTO` + segment-aware `append_disclaimer` / `verify_disclaimer`

- [x] `src/investo/briefing/disclaimer.py`:
  - 신규 상수 `DISCLAIMER_CRYPTO: Final[str]` — 가상자산이용자보호법 (2024.07.19 시행) §10 (불공정거래) / §19 (이용자 자산 보호) reference + "24시간 거래 / 비제도권 자산 / 가격 변동성 매우 큼 / 원금 전액 손실 가능" 명시.
  - `def append_disclaimer(markdown: str, segment: SegmentSlug = "us-equity") -> str` — segment 별 footer 변형 emit:
    - `crypto` → `DISCLAIMER_CRYPTO`
    - `us-equity` / `domestic-equity` → 기존 `DISCLAIMER` (byte-equal)
  - 기존 `DISCLAIMER` 상수는 *그대로 보존* — 자본시장법 면책 wording 변경 금지 (R5 Rule).
- [x] `src/investo/publisher/verifier.py`:
  - `def verify_disclaimer(briefing_md: str, segment: SegmentSlug = "us-equity", legacy: bool = False) -> bool` — segment 별 expected constant substring 검사:
    - `legacy=True` 이고 archive cutoff (2026-05-13) 전 파일 → 기존 `DISCLAIMER` substring 만 검사 (backward-compat).
    - `legacy=False` 인 신규 출력 → segment-appropriate constant substring 검사 (`crypto` → `DISCLAIMER_CRYPTO`).
  - Default 인자 (`segment="us-equity", legacy=False`) 가 기존 1-arg call site 와 byte-compat — 기존 caller 무파괴.
- [x] 회귀 테스트 `tests/unit/publisher/test_verifier_segment_aware.py` (예상 8-10 tests):
  - `verify_disclaimer(md_with_us_disclaimer, segment="us-equity") == True`
  - `verify_disclaimer(md_with_crypto_disclaimer, segment="crypto") == True`
  - `verify_disclaimer(md_with_us_disclaimer, segment="crypto") == False` (crypto segment 에 us-equity footer = fail)
  - `verify_disclaimer(md_legacy, segment="crypto", legacy=True) == True` (cutoff 전 파일)
  - footer 제거 시 fail (existing pin 유지)
- [x] Archive backward-compat: weekly-digest / monthly-index / site-index 가 archive markdown 재읽기 path 에서 `verify_disclaimer(text, segment=..., legacy=True)` 호출. cutoff 날짜 (2026-05-13) 비교는 archive path (`archive/{segment}/YYYY/MM/YYYY-MM-DD.md`) 의 date 파싱.

### Step 6 — Retail tone caps (Finding #12)

- [x] `src/investo/publisher/reader_format.py` 에 신규 함수:
  - `def check_sentence_ending_diversity(text: str) -> SentenceEndingReport` — 본문 (yaml frontmatter / 표 / 코드 블록 제외) 의 종결 어미 분포 계산. 분류: `~했다 / ~된다 / ~이다 / 전망이다 / 보인다 / 가능성 / etc`. dominant 종결 비율 > 60% → WARN.
  - `def check_filler_phrase_density(text: str) -> FillerDensityReport` — `여부 / 전망 / 우려 / 가능성 / 작용` 빈도 per 1000 chars. 임계 (기본 8.0) 초과 → WARN.
- [x] u51 의 `check_action_bullet_ratio(text, section_marker="⑥")` 는 *§⑥ 한정* — 본 unit 은 *본문 전체* surface. 별 metric, 별 log signature (`tone.sentence_ending_dominance` / `tone.filler_density`). 동일 surface 두 번 측정 안 함.
- [x] 단위 테스트 `tests/unit/publisher/test_retail_tone.py` (예상 8-12 tests):
  - 균질 input (`~했다` 100%) → dominant ratio 1.0 / WARN 발화
  - 분산 input (`~했다` 40%, `~된다` 30%, `~이다` 30%) → no WARN
  - filler 빈도: synthetic 12.0/1000 chars input → WARN; 5.0/1000 chars → no WARN
  - 표 / 코드 블록 / yaml frontmatter 제외 검증
  - empty body → no WARN (no crash)

### Step 7 — Notifier Telegram tag rendering + summary builder

- [x] `src/investo/notifier/summary.py` (Telegram briefing summary builder):
  - ActionTag substring 추출 grep 을 신규 4종 (`[상승 관찰] [하락 관찰] [혼재] [변동성 확대]`) + `[데이터부족]` 대응으로 갱신.
  - 구→신 alias map 통과: 과거 archive 의 legacy `[강세]` 가 Telegram digest 에 inline 인용될 경우 — 본 unit cutoff 이후엔 발생 안 함 (신규 생성물만 신 tag). digest path 가 archive 재읽기 한다면 legacy tag 그대로 surface (법 소급 안 됨).
- [x] 단위 테스트 `tests/unit/notifier/test_summary_action_tag.py` (예상 6-8 tests): 신규 4종 tag 추출 / 구 tag 가 Stage-2 출력에 나오면 fail (negative pin) / alias map round-trip.

### Step 8 — Orchestrator wire-through + integration

- [x] `src/investo/orchestrator/pipeline.py` 의 segmented publish path:
  - `_enhance_reader_experience` 직후, `verify_disclaimer` 직전 chain 에 신규 step 삽입:
    1. `scan_compliance(text, segment)` — P0 raise / P1 WARN
    2. `emit_first_viewport_disclaimer(text, segment)` — short disclaimer prepend
    3. `check_sentence_ending_diversity(text)` — WARN only
    4. `check_filler_phrase_density(text)` — WARN only
    5. `verify_short_disclaimer_first_viewport(text, segment)` — gate
    6. `verify_disclaimer(text, segment, legacy=False)` — 기존 gate (segment 인자 확장됨)
  - 순서 핵심: short disclaimer prepend 가 verify 전. compliance scan 이 가장 처음 (P0 hit 시 publish 차단, 자원 낭비 방지).
- [x] 통합 테스트 `tests/integration/test_compliance_pipeline.py` (예상 6-8 tests):
  - synthetic Stage-2 output (clean) → 모든 gate 통과
  - P0 phrase injection → `ComplianceLanguageError`
  - first-viewport disclaimer 제거 → `verify_short_disclaimer_first_viewport` fail
  - canonical footer 제거 → `verify_disclaimer` fail
  - crypto segment + us-equity footer mismatch → `verify_disclaimer` fail
  - 셋 다 충족 시 publish 성공 (archive write)

### Step 9 — Requirements 문서 갱신 + Quality gate

- [x] `docs/requirements.md` 에 신규 FR 추가:
  - **FR-012: Compliance language enforcement + segment-aware disclaimer (u56)**
  - Description: 시황의 advisory wording / quantified outcome / Korean retail-coded language 를 publish 게이트에서 차단; first-viewport short disclaimer (segment-aware) 추가; crypto segment 에 가상자산이용자보호법 reference 면책 footer (`DISCLAIMER_CRYPTO`) 분리; 종결 어미 다양성 / filler phrase family WARN cap; ActionTag 5종→4종 마이그레이션 (alias map backward-compat).
  - AC: 본 plan 의 DoD 9 항목 그대로 인용.
  - Priority: Must-have (Rule 2 disclaimer enforcement 강화 — 기존 footer + 신규 first-viewport + segment 분기).
- [x] inception bridge (`aidlc-docs/inception/requirements/`) 가 FR id 를 등록한다면 동기화.
- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (예상 +52-68 신규 테스트)
- [x] `uv run mkdocs build --strict` ✅
- [x] (수동) `mkdocs serve` → 임의 segment briefing 페이지 → first-viewport short disclaimer + canonical footer + ActionTag observation 라벨 시각 확인.

---

## Step Dependency Graph

```
Step 1 (prompt + ActionTag) ──┐
Step 2 (P0/P1 gate) ──────────┤
Step 3 (context filter) ──────┤
Step 4 (short disclaimer) ────┼──> Step 8 (orchestrator wire) ──> Step 9 (gate)
Step 5 (DISCLAIMER_CRYPTO) ───┤                                         ↑
Step 6 (tone caps) ───────────┤                                         │
Step 7 (notifier) ────────────┘                                         │
                                                                        │
                                            Step 9 (requirements doc) ──┘
```

Step 1-7 모두 병렬 가능 (각자 별 surface). Step 8 은 1-7 머지 후. Step 9 (FR doc 등록) 는 Step 8 와 병렬.

---

## NFR AC coverage map

- **NFR-001 (운영비 0원)**: 신규 외부 호출 0건; LLM 추가 호출 없음 (Stage-2 prompt 룰 확장 + 신규 publisher-side gate 들).
- **NFR-003 (graceful degradation)**: 신규 P1/tone gate 들은 모두 *WARN-only* (non-blocking) — generation 변동성 흡수. P0 만 blocking — 명백히 compliance-critical.
- **NFR-004 (Compliance / Disclaimer)**: **본 unit 의 핵심 surface**. 기존 footer (R5) 가 *추가* surface (first-viewport short + crypto variant) 로 hardened. `verify_disclaimer` byte-compat (default 인자) — 기존 caller 무파괴.
- **NFR-005 (Maintainability)**: phrase list 가 `models/compliance_phrases.py` 에 단일 source. briefing prompt + publisher gate 가 동일 import — drift 자동 차단.
- **NFR-006 (Testing)**: pure 함수 위주 (idempotent scan / segment-aware verifier / regex-based detection); PBT 일부 적용 가능 (`scan_compliance` round-trip).
- **NFR-007 (Secret hygiene R13)**: WARN extra 가 LLM output text 만 carry (segment / phrase / count / line_no). raw_metadata 미포함. 카나리 테스트 (Step 9 quality gate) 로 핀.

---

## Project rule compliance

- **Rule 1 (Anthropic SDK ban)**: 무관 — prompt 룰 확장 + 신규 publisher gate, runtime LLM 호출 path 미변경.
- **Rule 2 (Disclaimer enforcement)**: **본 unit 의 핵심**. 기존 `publisher.verify_disclaimer` 가 *유지* + segment 인자 확장 (byte-compat default). 신규 `verify_short_disclaimer_first_viewport` 가 *추가* gate. crypto segment 에 `DISCLAIMER_CRYPTO` 분리. 셋 다 충족시에만 publish 통과 (Step 8).
- **Rule 3 (Module boundary)**: 신규 `publisher/compliance_language.py` 는 `publisher/` 내부. phrase list 는 `models/compliance_phrases.py` (foundation; 모두 import 가능). orchestrator 만 cross-import (Step 8).
- **Rule 4 (무료 API only)**: 무관.
- **Rule 5 (Telegram 채널 분리)**: 무관 — notifier 의 tag rendering 만 갱신 (BriefingPublisher chat). OperatorAlerter chat 무영향.
- **Rule 6 (no raw stdlib XML)**: 무관 — text 처리만.
- **Rule 7 (R13 secret hygiene)**: WARN extra 에 raw_metadata 미포함 검증 (Step 9 가 모든 신규 logger.warning extra 를 grep).

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **§⑥ 관전 포인트 "여부" 가족 어구 비율** — u51 owns. 본 unit 의 "filler phrase family per-1000-chars" 는 *본문 전체* surface (별 metric, 별 log).
- **Numeric/factual verification** — u55 owns.
- **Segment routing / time reconciliation** — u57 owns.
- **Soften P1 자동 변환** — 본 unit 은 WARN-only. 자동 rewrite 는 LLM 영역 침범 + 환각 risk; regenerate path 는 별 unit 후보.
- **법률 자문 / 변호사 검토** — 본 unit 의 wording 은 *조문 reference + 사실 명시* 수준. 정식 법률 검토는 운영자 (1인) 책임; tech-debt 후보 (DEBT-D56-A).
- **과거 archive (2026-05-13 이전) 면책 재작성** — legacy=True flag 로 통과. 재작성 안 함 (법 소급 무).

---

## Open questions

- **Filler phrase per-1000-chars 임계의 정확값** — 본 plan 은 8.0/1000 chars 기본값 제안. archive 다일 sample 측정 후 implementation 시점 confirm (u51 §⑥ "여부" 40% 와 유사한 evidence-driven tuning).
- **종결 어미 분류기 정확도** — 단순 regex (`~다 / ~된다 / ~이다 / 전망이다`) 면 한국어 형태론 false-positive (예: `필요하다` 의 `~다`) 가능. implementation 시 KoNLPy 등 형태소 분석 의존 여부 결정 — 무료 룰 무위반, 의존 무게 trade-off. DEBT-D56-B 후보.
- **`목표가` quotative pattern 의 증권사 약어 화이트리스트** — `삼성증권 / 미래에셋 / 한투 / [A-Z]{2,5}` 패턴. 누락된 증권사 약어 false-positive risk. Step 3 implementation 시 한국 증권사 약어 표 (예: KRX 정회원사 리스트) 참조.
- **Crypto segment cutoff 정의** — 가상자산이용자보호법 시행일 2024.07.19 가 절대 cutoff. 본 unit 은 2026-05-13 부터 적용 — implementation 시 cutoff date constant (`COMPLIANCE_CUTOFF_DATE: date = date(2026, 5, 13)`) 명시.
- **`DISCLAIMER_CRYPTO` wording 의 변호사 검토** — Step 9 manual review 단계에서 운영자 판단. Implementation 후 cross-check 단계에서 wording 보강 가능 (DEBT-D56-A).
- **DEBT 후보**:
  - D56-A: `DISCLAIMER_CRYPTO` wording 의 정식 법률 검토 (변호사 자문).
  - D56-B: 종결 어미 분류기 형태소 분석 (regex → KoNLPy 등).
  - D56-C: P0 phrase list 의 정기 갱신 cadence (분기? 반기?) — 자본시장법 / 가상자산법 개정 추적.
  - D56-D: Quantified outcome regex 의 다국어 case (예: `30% return expected` 영문 혼용) — MVP 한국어만.

---

## How to approve

본 plan 의 9 AC + 9 step + crypto-only P0 카테고리 + tone cap 2종 분해를 검토 후:

1. **Request Changes** — AC 조정 / step 분해 변경 / phrase 카탈로그 조정 / out-of-scope 항목 재분류 / 임계값 조정 (예: 종결 어미 dominance 60% → 55%).
2. **Continue to Next Stage** — developer 가 Step 1 부터 implementation 시작.

승인 시 `aidlc-state.md` 의 u56 행이 "📋 Planned" → "⚙️ In Progress" 로 전이.
