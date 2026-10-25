# 기사의 충실도·신뢰·실패 규칙

`article_v2`에만 적용하는 설계 규칙이다. [공통 v3 계약](../../event-news-v3/contracts.md)의 numeric/entity/source/time/finalization 불변조건은 유지한다.

## B184. 근거 확보

1. 원천 접근 자격, 해당 parser/revision 검증, public derived use, private retention을 별도 확인한다. u173 slot verified는 HTTP 권한을 대신하지 않는다. feed가 공개되어 있다는 이유로 연결된 모든 웹 페이지를 수집하지 않는다.
2. body fetch는 기존 u161의 명시적 공식 host/path allowlist 안에서만 실행한다. feed source 실패와 body 실패·0건·timeout·unqualified는 별도 outcome이다. 1,200→6,000자 보관 확대는 해당 qualification의 extraction/retention 범위를 다시 검토해야 하며 기존 qualified flag만 복사하지 않는다.
3. excerpt는 원문 offset/revision/hash에 묶인 완결 passage다. 인접 문단의 발언 주체·조건·부정을 떨어뜨린 채 단일 문장을 사실로 승격하지 않는다. source 문서 간 상충은 `conflicting_evidence`로 보존하며 다수결로 참을 선택하지 않는다.
4. 사건에 직접 연결되지 않은 최신 가격·월간 재고·주간 COT는 설명용 reference다. 배경을 신규 사건으로 승격하거나 주제가 같다는 이유로 사건 인과를 연결하지 않는다.
5. Stage2 allocation 순서는 `필수 core facts/identity/time → 사건별 필수 설명 질문의 근거 → 선택 설명/관측`이다. 앞 단계 필수 자료가 빠지면 그 사건을 detailed-ready로 표시하지 않는다. 실제 전송되지 않은 ref는 작성/평가에 사용할 수 없다.

## B185. 주제에 맞는 설명과 편집

고정된 내부 질문 family를 canonical event kind에 매핑한다. 모델은 중요 질문을 `not_applicable`로 임의 삭제할 수 없고, policy상 적용 조건과 source 상태가 함께 일치해야 한다. optional 설명은 근거가 있을 때 추가한다.

| 사건 family | 핵심 변경 외에 독자가 알아야 하는 설명 | 확인되지 않았을 때 |
| --- | --- | --- |
| 정책·규제·중앙은행 결정 | 적용 대상·현재 절차/효력, 기존 조치와 달라진 범위 또는 공식 결정 이유 | 시행·법제화·인과를 지어내지 않고 해당 필수 설명 gap 기록 |
| 실적·실제 경제지표 발표 | 기간·단위·비교 기준, 결과를 설명하는 공식 구성 항목/회사 설명 | consensus 없는 surprise 금지; 수치만 있는 brief는 detailed 양성으로 인정하지 않음 |
| 회사·서비스·거래·집행 사건 | 무엇이 실제로 바뀌는지·영향 범위, 실행 조건/상대방/절차 중 사건 성격상 필요한 정보 | 계획과 완료 구별; 기업 일반 소개로 빈 설명을 채우지 않음 |
| 발언·협상·법안 진행 | 누가 어떤 지위에서 무엇을 주장했는지, 진행 상태와 기존 입장 대비 변화/남은 조건 | 발언을 확정 정책으로 바꾸지 않음 |
| 기타 공식 사건 | 대상·변경·시점, 구체적 적용 범위 또는 다음 확인 조건 | unsupported category는 자동 detailed 승격하지 않고 사람 검토 대상으로 남김 |

`what`와 `when/status`는 모든 기사에서 필요하다. detailed 기사에는 위 family의 핵심 설명을 source-backed 문장으로 답해야 한다. `why`는 가격 상승의 원인을 반드시 설명하라는 뜻이 아니라, 그 사건의 확인된 맥락·작동 방식·적용 범위 중 독자가 의미를 이해하는 데 필요한 설명이다. 반응 자료가 없으면 “반응 확인 안 됨”을 반복해 본문을 늘리지 않으며, 가격 관측을 쓸 때만 시간·관측치와 인과 한계를 기사 안에서 명시한다.

질문은 내부 completeness checklist이며 제목이나 문단 순서를 규정하지 않는다. 모든 기사에 배경·의미·반응을 한 칸씩 채우는 방식, 고정 4문단, 정확히 N개 기사, 문자 수 최소값은 합격 조건이 아니다. 2~5문단/대략 600~1,500자라는 writer 안내는 권장치일 뿐이며 짧고 완결된 사건을 부풀리지 않는다. 상한은 [NFR](../nfr-requirements/nfr-requirements.md)로 별도 제한한다.

표는 canonical fact/기간/단위만 사용하고, 목록은 절차·조건·명확한 비교에 사용한다. 역할 라벨을 기본으로 출력하지 않는다. 제목·digest·lead도 claim 검증 대상이며 제목의 과장된 인과를 무검증 문구로 취급하지 않는다. footer로 옮길 수 있는 것은 문서 공통 안내·면책이고, “예정”, 조건부 해석의 전제, 발언 attribution, 기사별 출처는 삭제하거나 footer에만 숨기지 않는다.

## B186. Claim과 검증

- `fact`: source-backed actor/action/object/value/time/status atoms와 연결한다. 정량 값·단위·기간은 기존 검증을 통과해야 한다.
- `attributed_explanation`: 원천이 말한 이유/해석이며 발언 주체와 modality를 문장에 보존한다. 원천의 견해를 확인된 인과로 바꾸지 않는다.
- `conditional_analysis`: 원문으로 뒷받침되는 mechanism·전제 refs와 명시적 조건 표현을 요구한다. 모델 상식으로 새 mechanism을 보충하지 않는다. observed market cause로 바꾸지 않는다.
- `observation`: asset·측정 시각/window·baseline/value refs가 필요하다. 같은 날 변동은 원인 증거가 아니다.

모든 factual clause가 연결되어야 한다. 문장 하나에 주장 둘이 있으면 claim 둘을 연결한다. 접속 표현만 새 사실 없이 허용하며 고유명·숫자·시각·인과가 있는 문장을 `transition`으로 빼지 못한다. 인용 부호·번역·출처 링크는 그 자체로 proof가 아니다.

Stage3의 supported는 **자동 의미 검사 결과**다. source ref 유효성·숫자 일치·entity/action 일치는 hard gate가 별도로 판정하며 Stage3가 이를 override할 수 없다. verifier가 사실을 새로 만들어 수정 제안에 넣으면 그 제안은 rejected다. 원문에 포함된 모델 지시·광고·script는 trusted instruction이 아니며 tool/HTTP 권한도 없다.

## 판정과 실패 처리

| 상황 | private state / 조치 | 공개·수용 영향 |
| --- | --- | --- |
| 근거 충분, 문장 지원, 필수 설명 모두 답함 | `detailed_ready` | 단일 finalizer로 전달; 사람 수용은 별도 |
| 단순 사건 자체가 완결되고 핵심 사실 검증됨 | `brief_ready` + policy reason | 짧은 기사 허용. 뉴스-rich detailed 양성 횟수에는 포함하지 않음 |
| 중요 사건의 설명 원문이 없음 | `evidence_gap` | verified brief만 남길 수 있으나 issue readiness는 실패; 수집 owner에 전달 |
| 원문에 있는 필수 설명을 writer가 놓침 | `composition_gap` | 1회 수정; 실패하면 detailed-ready 아님 |
| 필수 packet이 budget에서 빠짐 | `budget_deferred` | 외부 must-cover 분모에 유지; quiet로 처리하지 않음 |
| verifier가 부족·불확실 판정, timeout, 형식 오류 | `review_unavailable` 또는 `review_failed` | 검증 전 article_v2는 seal 금지; 기존 market failure/partial outcome 사용 |
| hard unsupported fact/인과/숫자/identity 위반 | 기존 trust finding + claim IDs | 기존 hard block 정책 유지. `unavailable`로 이름만 바꿔 숨기지 않음 |
| 주요 사건은 모두 빠졌고 footer만 남음 | `content_not_ready` | 정상 기사 생성 성공으로 집계하지 않음. 실제 corpus 합격 불가 |
| 정상 관측과 외부 baseline에서 중요 새 사건 없음 | 기존 `quiet` | 억지 기사 생성·추가 검증 호출 불필요 |

새 state는 private readiness enum이며 공개 availability enum을 늘리지 않는다. source_limited는 source 관측 상태, trust_blocked는 finalization 상태, content_not_ready는 준비도다. 서로 대체하지 않는다. 유효 sibling 시장과 기존 partial exit/실패 안내는 보존한다. 출처가 제한됐어도 충분한 기사 하나는 표시할 수 있지만 중요 사건 누락을 숨기고 edition-ready라고 보고하지 않는다.

u172 실제 수용에서는 외부 baseline의 must-cover를 100% 반영하고 required facts 100%, unsupported event/causality 0, 사람 what/when/why/react/source 5/5를 유지한다. brief의 충분성 판정은 사람 annotation과 대조하며 정상 news-rich 사례에서 detailed 기사가 최소 1개 필요하다. 외부 baseline이 없으면 recall은 null이고 100%로 대체하지 않는다.
