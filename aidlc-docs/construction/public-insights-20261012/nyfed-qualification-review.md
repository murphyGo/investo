# NY Fed qualification / notice independent review

작성일: 2026-10-26 KST. 별도 reviewer. 초기 Medium 수정 후 현재 확인한 미해결 **Critical 0 / High 0 / Medium 0**.

## 검토 범위

WT `public-insights-data-init-20261025`, branch `codex/public-insights-nyfed-qualification-20261025`, base8e0342b9의 bounded publisher/source-licence follow-up을 code-review의 correctness/security/data-integrity/error-contract 관점으로 검토했다. 제품 source parser·methodology·routing/HTTP를 새로 전수 검토하지 않았다. macro renderer diff, NY Fed3 qualification diff, README/NOTICE, stage plan 및 관련 render/domain/source 회귀를 읽었다.

reviewer가 현재 [NY Fed Terms of Use](https://www.newyorkfed.org/privacy/termsofuse.html)의 Permissible Use(239–243), Conditions(248–256), Reference Rates(281–293)를 직접 조회해 패치 범위와 대조했다. 조건부 저장·복제·배포·파생 허용과 원천 고지/동일 조건/수정 출처 구별 및 reference-rate 비보증 고지에 한정한 대조다. 해당 source의 허용을 다른 provider·content 유형 또는 권한이 필요한 endpoint로 확대하지 않는다.

## M-NYFED-01 — 5영업일 비교의 계산 출처 표기 — 해결

위치: `src/investo/publisher/insights/macro.py`, `_card()`의 `comparison = ... 5원천 영업일 변화 ...`.

패치는 세 spread에 Investo 계산값 표시를 추가한다. 그러나 SOFR/EFFR 원값 카드의 `five_day_change()`도 Investo가 원 관측으로 계산한 별도 수치인데, 유효 baseline이 생기면 계산 주체 표기 없이 공개된다. 새 NY Fed 허용 범위에서 원천 관측과 자체 계산을 분리한다는 계약을 5영업일 변화에도 일관되게 적용해야 한다. Terms Conditions(3)는 변형 내용과 그 출처가 혼동되지 않도록 명시하도록 요구한다.

**reviewer 직접 재현:** 실제 Stage1 qualification을 메모리에서 NY Fed3개만 임시 허용하고 synthetic SOFR exact5 source-business-day history를 만든 후 실제 render_macro를 실행했다.

```text
SOFR five-day comparison: 5원천 영업일 변화 +20.00 bp
SOFR card states Investo calculation: False
```

raw SOFR/EFFR 값은 원천 관측으로 유지하되, 계산된 comparison 문구에 Investo 계산임을 표시하고 SOFR/EFFR의 정확 baseline 양성 회귀를 추가하면 해결할 수 있다. 거래일 비교의 수식·정의·원값을 바꿀 필요가 없다. spread 표시 회귀만으로는 이 경계를 검사하지 못한다.

**수정 후 확인:** 비교 문구에 Investo 계산을 추가했고 SOFR/EFFR 각각 exact5-business-day+20.00bp 및 원 관측값 유지 회귀를 추가했다. reviewer가 변경 코드와 assertion을 읽고 아래4개 test 파일을 다시 실행하여35 passed를 확인했다. 원천 raw SOFR/EFFR 자체를 계산값으로 표시하거나 수식/정의를 변경하지 않는다. 이 finding은 해결되었다.

## 확인한 고지·권리 경계

- 공식 reference-rate notice 및 non-affiliation 고지의 대체 항목에 데이터명/Investo를 넣고 DTCC 관련 정보를 보존한다. 현재924자 attribution은 공통1000자 상한 안에 있고, 같은 고지가 current/history definitions에 따라가는 회귀를 실행했다.
- NY Fed가 표시되는 단기자금 group의 attribution은 numeric cards 앞에 있고, SOFR−EFFR와 두 Treasury spread는 Investo 계산값이며 원천기관 발표 금리차가 아님을 표시한다. escape를 유지한다. lazy history는 기존 공용 reader의 정의별 attribution 표/그래프 인접 표시를 재사용한다.
- README는 MIT 대상을 software로 명시하고 provider-specific data notice에 연결한다. NOTICE는 원천의 기존 permissions/conditions를 유지하고 다른 blocked provider의 재배포 허가를 부여하지 않는다고 명시한다. 이 패치는 NY Fed data에 소프트웨어 MIT를 대신 적용하는 것으로 읽히지 않는다.
- sourcehref/API 식별·데이터 정의·계산 방식은 변하지 않는다. 새 endpoint/API key·원문 fixture 공개·추가 HTTP·LLM 경로도 없다.
- Stage1의 NY Fed3 display/public-Git/rolling-history flag는 모두 false다. 나머지 macro/crypto19개 정의의 기존 flag는 유지된다. 실제 matrix에서 Treasury6/BLS3/Alternative1은 기존 허용, FRED1/crypto8은 계속 차단이다.

plan의 초기 “다른19개 미허용 정의” 문구는 수정되었다. 전체46개에서 NY Fed3개를 제외한43개(기존 허용24/보류19)의 기존 권한을 유지한다는 현재 문구가 실제 matrix와 맞는다. 위 macro/crypto19개는 calendar24개를 제외한 하위 범위 수치이며 서로 구별한다.

## 두 단계 적용 순서

고지 renderer/README/NOTICE를 먼저 배포하되 NY Fed flags=false를 유지하고, 정확 application SHA의 CI 및 private execution pin 승격/readback 뒤 세 정의만 허용하는 순서는 새 숫자가 이전 renderer로 공개되는 위험을 줄인다. 수정된 release plan은 public main과 별도로 기존 production pin0025497d 위에 이번 renderer/notice/같은 회귀만 적용한 bounded runtime branch를 만들고 두 정확 SHA의 CI를 확인한 뒤 runtime을 먼저 pin한다. 최신 main의 무관한 event/source 변경을 이번 runtime 승격에 함께 넣지 않는 경계다. 그 bounded branch를 실제 작성한 최종 diff/CI/실행 pin은 별도 readback 대상이며 reviewer가 존재하지 않는 release SHA를 수용했다고 기록하지 않는다.

policy hash와 application code SHA는 별도로 기록해야 한다. Stage2 직전 기존/queued private owner의 실제 실행 pin도 확인하여 과거 package가 새 policy를 읽는 상황을 운영 경계에서 다뤄야 한다.

Stage2에서 변경할 대상은 NY Fed3개의 세 permission flag뿐이다. 다른 providers·calendar/crypto·event v3/news gates와 현재 application/code/data identity를 함께 확인해야 한다. 이 검토는 Stage2가 실행됐거나 실운영 pin/Pages가 수용됐다는 증거가 아니다.

## reviewer 직접 실행한 검증

변경 WT의 source가 사용되도록 PYTHONPATH=src:.를 명시하고 설치된 기존 통합 venv interpreter로 실행했다.

```text
PYTHONPATH=src:. /Users/user/Desktop/Projects/investo/.tmp/public-insights-main-integration-20261025/.venv/bin/python -m pytest tests/unit/publisher/test_macro_insights_render_u181.py tests/unit/orchestrator/test_macro_insights_projection_u181.py tests/unit/sources/test_macro_insights_envelopes_u181.py tests/unit/sources/test_nyfed_reference_rates.py -q
35 passed in 1.48s
```

초기 같은4개 파일 실행은34 passed in 1.24s였고, 위 수정 후 재실행이35 passed in 1.48s다. 추가로 위 M-NYFED-01의 수정 전 렌더 재현과 actual qualification의 source별 flag count를 직접 확인했다. NY Fed 실제14 source HTTP/probes 및 BLS 회복, 전체 CI/viewport/livePages/원격 pin은 lead의 별도 증거이며 reviewer가 새로 실행했다고 표현하지 않는다. FRED/DeFi/OKX/CG/Bybit의 최신 약관 전체를 이 좁은 리뷰에서 독립 재심사하거나 허용하지 않았다.

아직 발생하지 않은 genuine scheduled 관찰을 증가시키지 않았고0/5 경계를 유지한다. reviewer는 source/test 수정·commit/push·pin/flag 변경·배포 없이 이 보고서만 작성했다.
