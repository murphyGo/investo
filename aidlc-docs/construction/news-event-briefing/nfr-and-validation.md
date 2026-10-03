# NFR·평가·출시 설계

기존NFR-001~008을구체화했으며2026-09-27개발승인. 운영완료는별도. DEBT-090의현재성능미달을숨기거나10분목표를완료로표시하지않는다.

| ID | 고정기준 | 소유유닛 |
|---|---|---|
| NF1 | 기본2단계CLI와provider선택유지. 새유료API/세번째LLM/독립retry없음 |157/158/159|
| NF2 | Stage1 96/24, 추가 detail block 24KiB, stdout64KiB; Stage2 48/14 또는32/8, eventblock8KiB. 같은입력에서모든명시상한assert |157/158|
| NF3 | 새결정론적선정/검증은1000item합성fixture에서총200ms 이하(p95,10회,warm interpreter);end-to-end실측p95회귀10%이하면승인검토가능,절대10분미달은DEBT-090에분리기록 |157~159|
| NF4 | u161 신규HTTPbundle당최대6요청,동시2,응답500KiB,요청8초,총20초(기존pipeline deadline잔여와min),한번fetch+추가retry없음 |161|
| NF5 | u160 news최대7일,초기72h,24h overlap, source별 최대 3페이지/총 20초(기존 deadline과 min), finite RSS 기본 unknown, cap/partial parse는 partial. cursor는committedremote SoT |160|
| NF6 | 출처미상/conflict/unsupported를반영률100%로표시금지. sourcezero와실패구분,denominator0은ratio=null |159/160/161|
| NF7 | rawHTML/본문/privateLLM출력은공개git금지. publichash/count/path/합성fixture만. 기존R13/R10과NFR-008준수 |전체|
| NF8 | 외부요청은정확한승인host/path allowlist,HTTPS,local/private주소금지,redirect동일allowlist만1회,압축해제후크기상한,script실행없음 |161|
| NF9 | 기존numeric/entity/compliance/disclaimer/partial-sibling/hardgate보존;terminal최종byte와DTO일치;모드off에서기존fixturebyte호환 |158/159/162|
| NF10 | enable flag기본off;shadow는 v1 프롬프트/입출력을 유지하고 같은 기록 응답에서 게시 bytes/알림/cursor 불변. v2 preview는 비게시. active는완료된MVP와운영증거에대해서만선택;코드commit≠운영활성화 |전체|

## Golden fixture / acceptance matrix

18편의편집결함을별도평가manifest로고정한다. published18편은출력회귀자료이며원시입력재생자료로오인하지않는다. source입력은R10확보가능한recording또는명시된합성fixture다. 사건정답목록은사람검토로작성하고모델이자기답을채점하게하지않는다.

필수시나리오12개: (1)금리결정+SEP, (2)지정학사건+시장반응미확인, (3)실적actual/estimate/guidance, (4)서비스출시, (5)인사발언과발언자, (6)변화없는월간값/주간COT, (7)동일사건중복·수정기사, (8)뉴스부족, (9)source전부실패, (10)주말/DST/장후발표, (11)containment가사건fact/link제거, (12)금지/숫자조작과valid sibling.

각manifest에는expected_event_ids,required_facts,forbidden_claims,allowed_uncertainty,selected_expected,candidate_visibility,expected_public_status를명시한다. 사건이0개인fixture도합격가능하다. 제품/발언에가격숫자가없어도qualified로남는양성fixture를포함한다.

## 정량·정성 완료 기준

- deterministic suite: 보호선정event의prompt잔존100%,published필수fact/support누락0,syntheticunsupported통과0,동일사건중복본문0,unknown시각조작0.
- annotated offline corpus: 후보에실제존재하는must_include사건100%와required_fact100%; 없는사건추가0; 실제반응으로단정한근거없는인과0; source-backed fallback은detail_limited로정확히계수.
- 사람검토: frozen12개시나리오의what/when/why/react/source5항목각0/1점. eligible supported 사건은what/when/source필수,why는조건부허용,react는명시적unknown허용;5/5 충족. source가없는데세부정보를발명하면즉시실패.
- live shadow에서candidate-visibility와sourcewindow한계를기록한다. 외부주요뉴스포착률은별도사람baseline이있을때만계산하며내부반영률과합치지않는다.

## 테스트·출시 단계

1. u157 모델/선정과syntheticreplay;featureoffbyte호환.
2. u158 provider2종record/replay,actualfinalizer/summaryprojection.
3. u159 golden fixtures와공개quality집계,containment후누락negative.
4. 전체기존테스트·ruff/mypy/policyguard통과. 추가HTTP있는u161은source별qualification완료까지inactive.
5. v2 비게시 preview에서 주석된 사건 품질을 먼저 검증한다. 운영 shadow는명시적으로승인된5개scheduledrun에서검증;적어도뉴스풍부한날1회와주말직후1회가포함되어야한다. 못채우면해당운영AC는pending,합성검증을대신완료로기록하지않는다.
6. active전환과첫3회게시/알림/Pages확인은운영단계의별도실행범위다. rollback은flagoff,기존archive재작성없음. 잘못게시된실제사실수정은별도교정절차다.

2026-09-26에는 계획만 정의했다. 2026-09-27부터 코드·합성 회귀 검증을 수행하며 각 유닛 검증 기록이 현재 증거다. 실제 LLM 및 운영 활성화는 별도 증거가 필요하다.

## 리뷰에서 추가한 경계 fixture

- 한 문서의 두 제품, 뒤늦은 공식 근거 추가에도 event ID 유지, 같은 URL의 다른 사건.
- crypto 사건 5개×2 evidence rows, required fact가 세 번째 문서에만 존재, 보호 정책 25건 이상, input permutation.
- terminal 4/5건에서 DTO 최대 3개 ordered subset, 분류 실패의 null과 정상 0건 구별.
- 80자 첫 문장과 90자 초과 단일 문장, meaning/reaction 각각 refs mismatch, 두 provider의 invalid v2 → valid v2 retry.
- mixed 2카드와 legacy numeric 3~6카드, containment 후 event 0이 되어 numeric fallback 복원.
- pinned/빈/중간 누락 RSS, DART 자정 종료·날짜 정밀도·총 deadline, 지연 기사/동일 URL revision.
- push 성공 후 응답 유실, remote tip 전진, clean rebase의 metadata CAS 변경, shadow 정상 게시에도 cursor bytes 불변.
- feed의 281~1200번째 문자에만 있는 사실이 실제 Stage1/Stage2 근거까지 도달하는 fixture.
