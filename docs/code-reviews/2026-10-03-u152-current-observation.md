# u152 독립 리뷰

기준 `47031596`. 부모가 matrix resolver/parser를 구현하고 독립 작업자들이 fallback·contract fixture·actual finalizer fixture를 작성했다. 통합 후 별도 작성자 두 명이 코드와 테스트/요구사항을 검토했다. 구현 1회/검토 1회이며 교정과 재확인은 같은 wave다.

| 영역 | 결과 |
|---|---|
| Correctness | Pass — 현재값은 자산·지표에 맞는 payload로 치환 |
| Safety | Pass — 기존 hard gate와 봉인 이후 불변성 유지 |
| Reliability | Pass — 충돌·미지원 지표·날짜 누락은 제외 |
| Maintainability | Pass — 기존 resolver/fallback 소유권 유지 |
| Test Coverage | Pass — 실제 finalizer와 독립 반례 재검증 |

확인 및 수정한 P2 네 건:

1. ETH 해시레이트/가스비가 ETH 가격을 차용했다. 가격 신호의 남은 문구를 닫힌 보조어 집합으로 검증한다. unit 및 실제 sealed 문서 음성 대조를 추가했다.
2. AAPL 가격의 출처 Nasdaq을 별도 자산 나스닥 지수로 오인했다. 출처 자체가 공급자명일 때 identity와 분리한다.
3. 출처에만 적힌 미지원 가스비/해시레이트가 가격을 차용했다. 출처 잔여 문구에도 같은 지원 범위를 적용한다.
4. 출처에만 명시된 BTC 펀딩/OI가 관측값을 찾지 못했다. 신호가 정확한 자산을 제공할 때 동일 family의 출처 지표를 매칭한다. 출처만으로 누락 자산을 보충하지 않는다.

첫 검증 리뷰의 교정 재검 15개, 코드 리뷰의 독립 source-slot 반례/대조 14개 및 최종 contract/actual-finalizer 66개가 통과했다. 남은 구체적 P1/P2 없음. 기존 테스트 변경은 numeric passthrough·source paragraph current 제거와 CFTC 날짜 의무에 한정한다. scanner 호출 순서 fixture에는 지원되는 관측 payload를 제공했고 실제 gate를 대체하지 않았다.

적용 프로토콜: error contract(미지원/충돌의 명시적 제외), performance(기존 bounded 후보 집합), data integrity(동일 입력·순열·봉인 문서 반복). 신규 TECH-DEBT 없음. 전체 gate 수치는 `validation.json`에 기록한다.
