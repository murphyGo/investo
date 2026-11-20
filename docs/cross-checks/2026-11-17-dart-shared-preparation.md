# DART 공통 준비 경로 검수

범위는 u173 Step4/u184 Step5의 명시적 preview source preparation이다. [계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-preparation-20261117/plan.md), [세션](../sessions/2026-11-17-dart-shared-preparation.md), [독립 코드 검수](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-preparation-20261117/code-review.json)를 대조했다. 전체 FR-024 운영 수용을 완료한 보고서는 아니다.

| 요구사항·계약 | 구현·검사 증거 | 판정 |
| --- | --- | --- |
| FR-001/FR-024·동일 준비 owner | orchestrator/event_evidence.py: prepare_event_evidence; test_shared_preparation_retains_all_five_slots_in_native_passage | 구현 통과 |
| FR-017·관측 최신성과 근거 추적 | _dart_evidence.py: _latest_entry/prepare_dart_item; 최신성14실패·013모순·원문0회/trace clock/hash 검사 | 구현 통과 |
| FR-024·실패의 기사 재유입 방지 | generic selector/fact_context guard와 source_limited; test_superseded_item_reaches_native_source_limited_without_model_calls | 구현 통과 |
| FR-024/u184·완결 field 전달 | dart_runtime_evidence의 LF1:1변환·source locator25refs·29XML binding·한 문단·상한초과거절 | 지원 양식 구현 통과 |
| NFR-002·무료·추가 모델0 | 기존 OpenDART credential, 무료 API 최대5calls 진단·SDK/paid guard PASS | 구현 통과 |
| NFR-003·실패/자원 경계 | test_five_sources_ten_candidates_share_six_requests_and_two_connections·cancel drain·6/2/20/8·raw/ZIP/XML cap | 구현 통과 |
| NFR-005/006·호환성과 검사 | 기존 policy JSON/hash·flagfalse생략·parser bytes 보존; 집중338/통합29/root49/독립300PASS·mypy373 | 구현 통과 |
| NFR-007/008·비밀/권한/원문 | typed transport와 slot hash 결속·canonical logger filter·0700/0600·crypto preflight·암호문1일·HTML ZIP금지 유지 | 구현 통과 |
| 정확한 전달 코드 검증 | eff7b5c0 / CI43915660414·8,087PASS/1skip·562.90초·Node39·정적/정책/docs PASS | 통과 |
| 실제 source 차단 경계 |44781000456·4GET/200·1.401445초·원래target missing/XML0·별도candidate 정정표 거절·두입력선정0 | 차단 경계 통과 |
| positive native·운영 수용 | enriched/native0·runtime0·human0/12·v3예약0 | 미완료 |

독립 검수는 C/H/M/L0이다. locator 오연결·excerpt cap 누락·진단 JSON shape·deadline 성공 영수증 문제는 수정하고 회귀로 확인했다. 저장한 과거 원문의 offline 재생은 새 source/runtime 수용 건수에 포함하지 않는다.

실제 암호문을 즉시 확보하고 목록·원문 clock/hash 및 차단 결과를 재생했다. 최신 후보의 원문은 지원 정정표와 달라 `dart.correction_mismatch`로 거절했다. positive body 검증이나 새 양식 자격을 얻은 것이 아니므로 기존 과거 local3/8과 canonical 자격표는 그대로다. 만료된 앞선2run은 수용0이다.  다른5source·뉴스가 충분한 실제12문서/사람 인수·표면/성능·예약 관찰·운영 전환은 기존 u172/u173/u184 잔여로 유지하며 중복 유닛을 만들지 않는다.


암호문19,317bytes/SHA46d37cb9…와 private5파일은ignored0700/0600이며 [실측 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-preparation-20261117/evidence.json)에 count/hash/clock/closedcode만 공개한다. 새 source 요청 없이 보관된 새 정정표 변형을 검토하고 기존 u173/u184에서 versioned parser 지원 여부를 판정하는 후속이 남는다.


독립actual검수C/H/M0. 보관된prepareditems를비게시preview로재생해source_limited·모델0을확인했다. 원문거절은8행정정표중현재v1허용집합밖고유7행에의한정상guard이며날짜/문단변환오탐이아니다. boundedsubplan6/6만완료했고상위unit·positive5slot/native·운영수용은미완료다.
