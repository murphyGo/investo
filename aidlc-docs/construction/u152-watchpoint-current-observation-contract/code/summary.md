# u152 실제 관측값 계약

u162가 요구한 선행 계약이 기존 branch/main에 없어, u161을 전달한 후 독립 유닛으로 구현했다. 새로 범위를 넓히지 않고 기존 계획의 여덟 fixed contract를 따른다.

관전 포인트의 현재값은 숫자가 들어 있다는 이유로 통과하지 않는다. 이미 수집된 payload에서 자산과 지표가 일치하는 관측을 찾아 모든 current를 canonical 값으로 대체한다. 자산명만 있는 신호는 가격으로 해석하지만 지원하지 않는 지표는 제외한다. 동등한 우선순위의 값이 충돌하면 입력 순서에 관계없이 제외하고, 같은 값의 중복은 안정적으로 처리한다.

출처·현재·상방·하방·영향을 분리하며 빈 current에 전체 문장을 복사하지 않는다. CFTC는 유효한 기준일/공개일과 주간 지연을 표시하고 신뢰도를 보통 이하로 제한한다. 기존 최대6개 카드, zero-row 최대2개 fallback, supplements, compliance와 terminal hard gates는 유지한다. F&G fallback도 같은 관측 resolver를 통과한다.

새 API/LLM/데이터 소스/과거 archive 변경은 없다. finalizer 테스트는 봉인 본문의 관측값과 terminal notification 일관성을 각각 검사한다. notification DTO에 없는 current 필드를 새로 전달한다고 주장하지 않는다. 최종 수치와 리뷰 결과는 validation.json에 기록한다.
