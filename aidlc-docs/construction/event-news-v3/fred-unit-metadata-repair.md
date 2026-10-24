# FRED source unit 누락 수리

2026-10-25 KST. 실제 private preview 40119627476의 2회 모델 입출력을 기존 recipient 키로 복호화하고
각 prompt/stdout hash를 확인했다. 두 입력 모두 필수 FRED item 4개에 unit/macro_unit이 없었고,
두 응답 모두 해당 item을 포함하고 source-owned actual·metric·period·status 조건을 충족했지만 unit_refs만 비었다.
같은 `parse_context_classification`으로 재생하면 `context.required_missing`의 unit 조건에서 거절된다.
[닫힌 구조 증거](missing-unit-witness-20261025.json)는 원문·모델 응답·경제 수치를 담지 않는다.

기존 `sources/fred.py`는 observation의 series/value/date/prior만 정규화해 source unit을 전달하지 않았다.
검증기의 단위 요건은 유지하고 기존 기본 series의 공식 단위만 source metadata에 보존한다.
알 수 없는/custom series에는 기본 단위를 붙이지 않는다. 값·float formatting·변화량·관측창·우선순위·요청 수와
API key 연결은 바꾸지 않는다. 원래 요청의 transformation parameter도 그대로다.

## 확인한 primary metadata

| Series | 원래 단위 | 공식 원문 |
| --- | --- | --- |
| DFF | Percent | [FRED DFF](https://fred.stlouisfed.org/series/DFF) |
| UNRATE | Percent | [FRED UNRATE](https://fred.stlouisfed.org/series/UNRATE) |
| CPIAUCSL | Index 1982-1984=100 | [FRED CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) |
| PPIFID | Index Nov 2009=100 | [FRED PPIFID](https://fred.stlouisfed.org/series/PPIFID) |
| DGS10 | Percent | [FRED DGS10](https://fred.stlouisfed.org/series/DGS10) |

공식 series page를 2026-10-25 KST에 조회했다. [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)의
기본 `units=lin`은 변환 없는 수준 값이다. 명시적인 non-lin 응답은 이 단위로 표시할 수 없어 source-side에서 거절한다.
기존 per-series fan-out은 그 실패를 격리하고 정상 sibling을 보존한다. CPI/PPI 지수를 inflation percent로 변환하지 않는다.

## 검증과 남은 수용

Source mock API→NormalizedItem→u167 factory→네 required actual의 실제 unit refs→기존 classifier gate를 통과했다.
5개 기본 series와 unknown/custom, 변환 응답 4종, 정상 sibling 보존을 포함한 로컬 focused 115 PASS(3.31s),
독립 focused 130 PASS와 열린 P1/P2 0을 확인했다. 단위 참조 제거와 잘못된 field 참조는 계속 거절한다.
추가 합성 probe는 네 source-bound 지표의 index 단위까지 실제 native preview/sole finalizer에 전달해
1회 Stage 1, sealed 1개, 최종 issue 0을 확인했다. 실제 시장 문서나 사람 합격으로 세지 않는다.

최종 source SHA의 full/static/policy/docs와 추가 실제 preview 결과는
[재개 session](../../../docs/sessions/2026-10-25-event-v3-private-preview.md)에 기록한다.
source slot·사람 corpus·native viewport·실제 성능·release·genuine scheduled 수용은 그대로 별도다.
