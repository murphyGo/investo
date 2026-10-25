# u181 independent code review — initial

작성일: 2026-10-25. 별도 reviewer. 상태: **High 1 / Medium 2 — 수정 및 NFR 정합화 필요**.

## 범위

기존 code-review skill의 security-boundary/data-integrity/error-contract/memory/performance 관점을 이번 u181 추가분에 적용했다. u180 구현을 다시 전체 검토하지 않았다. u181 FD business rules/logic, focused NFR 및 기존 공통 C1–C7을 기준으로 다음을 읽었다.

- 신규 `models/insights_macro.py`, `orchestrator/macro_insights.py`, `publisher/insights/macro.py`.
- 기존 Treasury/NYFed/BLS/FRED adapters의 opt-in envelope diff, common projection의 macro binding/monthly 예외, finite decimal exponent 제한, store의 macro renderer/100KiB bound 연결.
- MkDocs nav, hub/awaiting page, `site_docs/assets/insights.css`와 기존 token 이름.
- 추가 중인 synthetic macro helper와 domain projection 테스트. source request/byte parity와 렌더링 테스트의 최종 추가분은 아직 실행 증거가 없는 시점이다.

## Findings

### H181-01 — 파생 spread의 parent 권리 철회가 last-good 복원에서 우회됨

위치: `src/investo/orchestrator/insights_projection.py`의 previous.metrics 복원 분기(초기 검토 시점 약309–332), `src/investo/orchestrator/macro_insights.py`의 parent allowed gate.

새 capture는 parent가 권리 미확인/철회이면 spread를 reject한다. 그러나 previous 복원은 spread 자체의 qualification만 확인하므로 parent 권리가 사라진 spread를 last_good로 다시 공개한다. 파생 이력도 같은 parent 정책이 적용되어야 하며, 다른 모듈만 active인 때 inactive baseline sanitation도 parent 권리 변경을 감지해야 한다. C3와 R181.2의 provenance/권리 경계를 위반한다.

**reviewer 직접 실행:** 같은 유효일 UST10Y=4, UST2Y=3, spread=100bp의 qualified 이전 snapshot을 만들고, UST2Y의 display_allowed만 false로 변경한 뒤 다시 projection했다.

```text
prior [('ust_10y', Decimal('4'), False), ('ust_10y_2y_bp', Decimal('100'), False), ('ust_2y', Decimal('3'), False)]
after_parent_denied [('ust_10y', Decimal('4'), False), ('ust_10y_2y_bp', Decimal('100'), True)]
```

**수정:** 모든 current/last-good/history/inactive rights gate에서 spread의 exact parent definition에 대한 현재 display/public-git/retention 권한도 함께 검증한다. parent runtime failure와 parent permission withdrawal을 구별한다. 회귀: 이전 snapshot+parent revoked/unverified, no-input last-good, inactive module sanitation, parent retention-only withdrawal.

### M181-02 — bounded 원값의 파생 연산 결과 검증 오류가 card-local 경계를 벗어남

위치: `src/investo/orchestrator/macro_insights.py`, `value = (a.value - b.value) * 100` 및 `recipe.metric(value, ...)` 생성.

원값 `1e64`는 현재 finite/adjusted exponent 계약을 통과한다. bp 변환 뒤 `1e66`은 metric validator에서 거부되지만 binder에 예외 격리가 없어 project_module 호출 전체를 ValidationError로 종료한다. 실제 phase에서 이 예상 numeric 오류가 다른 정상 모듈 게시까지 막을 수 있다. R181.6 및 C7의 실패 격리에 맞지 않는다.

**reviewer 직접 실행:** `module(capture({'ust_10y':'1e64'}))`에서 `SourceInsightMetric.value: non-finite or oversized decimal`, input `Decimal('1.000000000000000000000000000E+66')` ValidationError가 전파됨을 확인했다.

**수정:** DecimalException과 derived DTO validation을 spread-local reject로 변환하고 정상 원값/다른 source 카드를 유지한다. 기존 default decimal context가 큰 유효 coefficient에서 연산을 반올림할 수 있으므로 정확한 Decimal 산식을 보장하거나 표현 가능한 정밀도 범위만 명시적으로 받는다. 회귀: bound 내 input→bound 밖 derived output, 고정밀 두 원값의 exact spread, 정상 macro/crypto sibling 보존.

### M181-03 — history lazy-load 명시 NFR과 전체 inline history 생성의 편차

위치: `src/investo/publisher/insights/macro.py:168–199`; NF181.4.

`_history()`는 모든 대상 지표의 최대30 observations에 대해 표와 SVG를 만들어 initial HTML에 넣는다. 닫힌 `<details>`는 표시만 접으며 데이터를 lazy-load하지 않는다. 따라서 NF181.4의 history lazy-load를 구현했다고 기록할 수 없다. 초기 HTML byte guard 자체는 별도로 존재한다.

**수정:** same-origin bounded history를 사용자 요청 때 읽는 progressive enhancement와 no-JS 접근 수단을 제공하거나, 현재 bounded inline/no-JS 방식을 의도한 요구 변경으로 명시하고 해당 NFR/수용 근거를 일치시킨다. latter를 reviewer가 임의 승인한 것은 아니다. 실제 viewport/네트워크 시험은 아직 미수행이다.

## 확인한 구현 경계

13개 recipe, 같은 InsightTime/date·provider·source·origin 및 percent 단위의 spread gate, CPI>0/실업률0..100/FX>0, 5 source-business-day exact baseline과 revision 제외를 읽었다. H.10은 source_date를 date precision으로 전달하며 기존 legacy published_at을 공개 시계로 복사하지 않는다. monthly known target period+미확인 다음 발표 예외는 freshness unknown/limited로 표시하고 update_history가 unknown 관찰을 advance하지 않는다.

새 source fetch 호출은 diff에서 확인되지 않았으며 envelope를 기존 response에서만 만든다. default-off 경로의 request/serialized-byte parity는 코드 흐름상 유지되도록 분기되어 있지만 reviewer가 source별 parity 테스트를 실행한 것은 아니다. labels/attribution/URLs escape, numeric exponent bound 및 scoped CSS도 읽었다. Treasury/BLS 실제 권리 qualification의 최종값은 이 초기 검토 시점 미확정이며 synthetic fixture 허가를 production 권리 근거로 취급하지 않는다.

## reviewer 실행 검증

```text
.venv/bin/python -m pytest tests/unit/orchestrator/test_macro_insights_projection_u181.py -q
12 passed in 1.14s
```

추가로 H181-01 및 M181-02의 위 두 합성 domain 재현을 직접 실행했다. 그 외 full suite, source parity, byte-size/viewport, 실제 권리 확인, production HTTP/Pages/activation은 실행했다고 주장하지 않는다. 소스/테스트 변경·commit·push·activation은 하지 않았으며 이 보고서만 작성했다.
