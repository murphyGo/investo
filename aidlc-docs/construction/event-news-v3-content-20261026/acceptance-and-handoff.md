# 실제 자동 기사 수용과 구현 인계

2026-10-26 설계 기준. 기존 u172의 **5/9**, u173의 **6/7**을 완료로 바꾸지 않는다. 새 u184/u185/u186은 각각 구현 **0/6**이다. 이전 reference에 대한 사용자 “승인”은 편집 정책의 승인이고, 이 새로운 pipeline의 실제 내용·source·성능·운영 합격은 아니다.

## 1. 구현 순서와 검증 자료

| 단계 | 산출물 | 통과 증거 / 다음 단계 |
| --- | --- | --- |
| u184 | 허용 원문 보강의 preview/production 공통 준비, packet과 정확한 전달 manifest | private 원문 offset/rights/parser 검증, offline packet·budget 회귀. u185에 실제 근거가 들어간 packet 전달 |
| u185 | typed 한국어 narrative·claim map·version2 public projection | 문장/조건/출처 보존, 모든 reader surface와 old sidecar byte/hash 검증. u186에 후보 전달; 검증기 없이 활성화 불가 |
| u186 | Stage3·최대1회 수정·전역5 calls·terminal readiness | adversarial 오류를 차단하고 유효 기사 보존, 정확한 budget/timeout/부분 실패 결과. u172에 exact SHA·policy·평가 자료 전달 |
| u173 기존 잔여 | source별 권리·접근·parser/slot·실제 runtime 증거 | source/selector/retention scope별 판정. synthetic PASS로 verified 수를 늘리지 않음 |
| u172 기존 Step2/7 | 실제 corpus12·사람 평가·성능·표면 수용 | 아래 record를 결속. 합격 시장만 release 후보 |
| u172 기존 Step8/9 | 승인된 시장별 운영·예약 관찰·구형 제거 | 최초3회/시장, 전체3시장 accepted 및10회 이후 별도 reviewed cleanup |

## 2. source 공급의 구체적 경로

원천 조사 자체는 u173의 기존 owner다. 현재 slot manifest의 8개는 모두 blocked이며 설계로 상태를 변경하지 않는다.

| 기존 slot/source | 이번 packet에서 필요한 내용 | 진행 경로 |
| --- | --- | --- |
| policy.monetary_decision / fomc-rss | 결정·대상·변경폭/적용범위·공식 이유 | u161 공식 body selector의 원문 passage 범위 재검증 후 u184 연결 |
| policy.official_statement / fed-speech-rss | 발언자·발언 내용·조건/귀속 | 같은 공식 body 경로; 발언과 결정 구별 |
| policy.regulatory_action / cftc-policy-rss | 조치·상태·대상·절차/조건 | 같은 공식 body 경로; crypto 적용은 내용·관련성 근거 필요 |
| policy.domestic_announcement / korea-policy-rss | 기관·조치·적용대상·시행 상태 | 기존 feed/API가 충분하면 그 bytes 사용. body가 필요하면 u173의 해당 host/path/parser 검증 후 u161의 닫힌 source enum/selector 확장 |
| earnings.reported_actual / sec-company-facts | 회사·actual·단위·기간·filing locator | 기존 structured API만으로 core 구성. 실적 이유는 연결된 원문 근거가 있을 때만 사용 |
| earnings.guidance / sec-edgar-8k | guidance 내용·기간·발언 주체·조건 | 기존 filing locator로 occurrence 연결. title/8-K 접수만으로 guidance 내용 생성 금지 |
| domestic.disclosure_action / dart-disclosure | 발행자·행위·상태·조건·공시 locator | 기존 수집이 title뿐이면 evidence_gap. 본문 endpoint/권리/parser가 검증된 후 기존 adapter/보강 owner의 bounded 확장 |
| earnings.schedule_context / nasdaq-earnings-calendar | 회사·예정일·분기 | 참고 일정만 담당. 예상치를 actual·결과 설명으로 사용하지 않음 |

국내 정책·DART·SEC filing의 부족한 body 지원은 **u184 Step5의 source별 bounded substep**으로 기록한다. 자격이 확인된 기존 source만 enum/selector/DTO를 확장하며 신규 provider는 추가하지 않는다. scope/endpoint/fixture/HTTP budget이 확정되기 전 해당 substep은 blocked이고, “원문 수집 구현 완료”로 보고하지 않는다. HTTP 권한이 없는 입력은 feed-only 경로로 계속 시험하되 그 시장의 content acceptance를 성공으로 꾸미지 않는다. source gate 때문에 남는 실제 공백이 있으면 program 완료가 아니라 미완료 원인으로 보고한다.

## 3. 실제 검수의 단위와 절차

한 record는 `code SHA + profile/policy/qualification hashes + market/news window + source recording hash + input manifest hash + draft/review hashes + sealed Markdown/projection hashes + human annotation/review hash`를 결속한다. 동일 원문·동일 news window의 재시도/재생은 별도 실제 표본으로 세지 않는다.

1. 출력 생성 전에 사람이 해당 관측창의 중요 사건·required facts·forbidden claims와 필요한 설명 질문을 annotates한다. 알려진 수집 후보만 보지 않고 독립적인 공식 뉴스 목록과 대조해 must-cover를 정한다. 목록을 확보하지 못하면 external recall은 null이다.
2. exact reviewed article_v2 코드와 허용된 source policy로 실제 비게시 실행한다. 사람이 본문을 고치거나 모델의 답을 수동 주입한 경우 actual producer sample에서 제외한다. raw/private evidence는 기존 encrypted artifact 경계에 둔다.
3. 검수 화면에서 **최종 기사**와 source passage를 나란히 대조한다. 제목·lead·본문·선택 표/목록·digest·조건·출처를 검수한다. 일반 운영 안내와 면책은 하단에 있어야 한다. 이 화면은 private review 자료이며 공개 기사에 구현 진단을 노출하지 않는다.
4. 기존 what/when/why/react/source 5개 항목 각각0/1을 사람이 기록한다. why unavailable은0, 근거 없는 반응 설명은0이다. 실제 반응 미확인의 정확한 표시는 기존 rubric에 따른다. “글이 길다”, role 채움, 모델 supported를 사람 점수로 사용하지 않는다.
5. 본문이 source의 중요한 설명을 빠뜨렸는지, 원문 복사/어색한 번역/반복 설명으로 이해를 막는지 함께 rejection reason으로 기록한다. 사람이 고친 문장은 개발용 참고 자료로 분리하고 원래 producer sample의 판정을 덮어쓰지 않는다.
6. 실패를 source gap, selection gap, packet truncation, composition gap, review miss/false rejection, finalizer loss로 귀속해 해당 유닛을 수정한다. 동일 sample replay로 회귀를 확인하되 실제 새로운 표본도 수집해 통과를 확인한다.

corpus는 기존 최소12문서, **시장별4·발행일2 이상·시장별 news-rich 정상 양성**을 유지한다. 각 news-rich 정상 문서에는 적어도1개의 detailed-ready 기사가 있어야 한다. 뉴스가 풍부한 날인데 0기사/brief/면책만 있으면 불합격이다. quiet·source-limited 사례는 robustness 평가에 남기고 정상 양성을 대체하지 않는다. 시나리오별 expected quiet/brief는 사전 annotation으로 정한다.

판정 기준은 must-cover 반영100%, required fact100%, unsupported event/causality0, 사람5/5다. 수집/내부선정/단말생존/외부포착/내용준비도/사람점수의 분모를 각각 기록한다. 등록된5개 기사 cap 때문에 빠진 must-cover를 분모에서 제거하지 않는다. 반드시 같은 문서의 처음부터 끝까지 읽고, approved historical reference2개를 실제12에 합산하지 않는다.

## 4. 표면·운영 인수

u171이 최종 actual HTML을 390×844/1440×900에서 확인한다. HTTP200·DOM존재·브라우저 open만으로 viewport 측정을 대체하지 않는다. 실제 Browser 연결이 불가능하면 해당 증거는 pending으로 남기고 코드/내용 평가와 분리한다.

u172는 성능·source·인증·예산·정책을 고정한 exact code SHA에 대해 release 준비를 판정한다. 운영 전 현재 runtime owner/pin·schema/profile·mode·source allowlist·news cursor·Pages 연결을 다시 readback한다. 다른 작업이 갱신한 pin을 과거 값으로 되돌리지 않는다. 현재 schema2 production을 설계만으로 바꾸지 않는다.

실제 release 이후 시장별 최초3개의 genuine scheduled run에서 generation/finalization/remote publication/Telegram/해당 SHA Pages/story·cursor/exit를 각각 확인한다. 수동 preview는 예약 관찰0회다. 기존 whole-code/policy rollback과 유효 sibling 유지 정책을 사용한다. 세시장 accepted와10회 실제 v3 예약 이전에는 legacy cleanup을 완료하지 않는다.

## 인계 패키지

각 유닛은 numbered AC별 코드·test path·exact SHA·미완료 외부 증거를 제출한다. u186은 추가로 자동 검증 결과와 사람이 재검사한 false-positive/false-negative 사례를 u172에 넘긴다. 이 문서의 체크리스트나 AI 로컬 설계 리뷰는 사용자 검수자의 ID/시각/점수를 생성하지 않는다. **설계 완료, 코드 완료, 실제 내용 합격, 운영 완료를 따로 보고한다.**
