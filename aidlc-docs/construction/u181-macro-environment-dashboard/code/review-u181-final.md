# u181 independent code review — focused follow-up

작성일: 2026-10-25. 별도 reviewer. 범위: 초기 3개 findings 수정과 신규 lazy history JS reader 및 정밀도 보강. 현재 확인한 미해결 판정: **Critical 0 / High 0 / Medium 0**.

초기 범위와 재현은 [review-u181-initial.md](review-u181-initial.md)를 따른다. u180 전체 및 실제 source 권리 판정을 다시 검토한 것이 아니다.

## 수정 확인

- **H181-01 해결:** `rights_reason()`이 macro spread의 exact recipe parent에 대한 display/public Git 및 semantic qualification을 재귀 검사한다. 공통 last-good/current/history 및 inactive sanitation에서 이 gate를 소비한다. `retention_allowed()`도 parent retention을 재귀 확인하며 update_history에서 사용한다. parent display 철회 후 last-good 및 history 제거, parent retention-only 철회 시 current 유지/history 제거 회귀를 읽고 실행했다.
- **M181-02 해결:** binder의 파생 계산/DTO 생성에서 DecimalException·ValidationError를 해당 spread reject로 바꾸며 원본 정상 sibling을 유지한다. `1e64` 회귀가 직접 실행한 테스트에 포함되어 통과했다. 추가로 source Treasury/binder/5영업일 비교가 `difference_exact()`의 localcontext.prec=256을 공유하여 아래에서 재현한 exact precision 경계도 해결했다.
- **M181-03 해결:** 초기 HTML의 전체 history table/SVG를 제거했다. 클릭 때만 same-origin manifest/history를 읽고 root의 snapshot/current hash와 manifest entry, history SHA256을 대조한다. definition/comparison identity로 최대30 observations를 선택하고 textContent/DOM API로 표/SVG를 생성한다. 불일치/실패 시 현재 카드 유지 및 재시도/새로고침 안내를 제공한다. JS 없이 current cards/만기표/출처와 JSON 이력 링크가 남는다.

신규 reader는 payload byte/row cap, Number finite, 날짜 key 형식을 확인하며 표에는 원 Decimal 문자열을 보존한다. SVG의 Number 변환을 exact 표와 구별한다. 실제 browser viewport/hash-negative 시험은 lead가 실행 중이라고 보고했으며 reviewer가 실행한 것으로 기록하지 않는다.

## M181-02 정밀도 보강 재검토 — 해결

위치: `src/investo/orchestrator/macro_insights.py`의 spread 산식, `src/investo/sources/treasury_rates.py`의 같은 산식.

common value contract는 최대64자 finite Decimal을 허용하지만 산식은 default precision28을 사용한다. 충분히 긴 유효 coefficient가 들어오면 오류 없이 실제 값과 다른 spread를 만든다. 검산도 같은 context로 계산하므로 이 차이를 발견하지 못한다. Source 데이터가 보통 짧다는 사실로 허용된 typed contract의 exact 산식을 보장할 수 없다.

**reviewer 직접 실행 재현:** synthetic UST10Y `4.12345678901234567890123456789123456789`, UST2Y `4.10`.

```text
derived 2.345678901234567890123456789
exact   2.34567890123456789012345678912345678900
equal False
```

expected는 별도 Decimal localcontext.prec=128로 계산했다. 부모 값은 현재 validator를 통과한다.

**적용된 수정:** `models.insights_macro.difference_exact()`가 localcontext.prec=256으로 계산하고 source Treasury/binder/5영업일 비교가 같은 helper를 사용한다. 현재 지원 coefficient/exponent 범위와 bp scale을 수용하며, DTO의 bounded result 검증은 유지된다. Treasury source helper는 파생 결과만 cap을 넘을 때 유효 base metric을 유지한다. 원천 Decimal 표시도 소수 두 자리 강제 반올림 대신 자릿수를 유지한다. 이 코드와 source/binder 고정밀 기대값·derived overflow sibling 보존 회귀를 reviewer가 직접 확인했다. 위 재현 값은 이제 exact 기대값과 일치하는 회귀 테스트로 통과한다.

## 같은 수정의 추가 좁은 확인

관련 시황 링크 날짜는 고정 remote-confirmed baseline SHA의 ls-tree 결과에서 실제 존재하며 경로와 연/월/일이 맞는 날짜만 선택한다. pending/untracked 작업 파일을 확인 근거로 사용하지 않는다. renderer에는 date만 전달하고 실제 링크에 날짜를 명시하며, 후보가 없으면 archive index 접근만 제공한다. JS의 SVG 생성은 별도의 좁은 catch 안에 있어 optional 그래프 생성 실패가 이미 만든 exact table을 제거하지 않는다. 이 경로와 관련 회귀를 읽었으며 실제 browser UI 성공은 lead의 별도 증거로 구분한다.

## reviewer 직접 실행한 검증

```text
.venv/bin/python -m pytest tests/unit/orchestrator/test_macro_insights_projection_u181.py tests/unit/publisher/test_macro_insights_render_u181.py tests/unit/sources/test_macro_insights_envelopes_u181.py -q
29 passed in 1.46s
```

초기 follow-up에서 24 passed in 0.96s와 위 high-precision 불일치 재현을 직접 실행했고, 보강 후 같은 세 test 파일을 다시 실행하여 위 29 passed를 확인했다. source 4종의 request/기존 JSON bytes parity 및 NYFed 원 JSON Decimal 보존 assertion이 해당 source 테스트에 포함된다. 이 검증은 합성 응답 기반이며 actual source 권리 허가·실운영 HTTP·production activation·Pages·browser viewport 승인과 구별한다. 소스/테스트 변경, commit, push, activation은 하지 않았고 보고서만 작성했다.
