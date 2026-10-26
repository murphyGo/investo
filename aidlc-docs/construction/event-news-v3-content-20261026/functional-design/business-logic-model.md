# 처리 모델과 모듈 책임

2026-10-26 설계. 아래 신규 파일·함수·타입은 **구현 예정**이며 존재하는 API로 가정하지 않는다. 기존 owner의 기능은 재사용한다.

## 1. 실행 경계

`EventExecutionConfig`에 private generation profile `role_v1|article_v2`를 추가한다. default는 `role_v1`, `article_v2`는 schema3에서만 유효하다. profile mismatch는 생성 전 configuration error다. active+article_v2는 u172의 해당 profile/code/policy/시장 수용 record를 요구한다. 현재 active readiness와 source capability를 문서나 profile 선택만으로 true로 만들지 않는다.

off/shadow는 새 HTTP/LLM 0회다. preview는 게시·Telegram·production receipt/story/cursor 갱신 0회다. fixture replay는 네트워크 0회이며 actual corpus에 포함하지 않는다. preview와 production은 같은 orchestrator preparation 함수를 호출해 수집에서 모델까지의 차이를 제거한다.

## 2. 원문과 사건 근거 묶음 — u184

1. 기존 CollectStage/preview collection에서 source outcomes, news window, 수신 clock을 보존한다. 실패한 feed를 body fetch 성공으로 바꾸지 않는다.
2. 신규 `orchestrator/event_evidence.py::prepare_event_evidence`가 기존 `_enrich_collected_events`의 orchestration을 공유 함수로 옮겨 호출한다. sources import와 HTTP client 소유는 orchestrator에 남긴다. briefing/publisher는 네트워크를 소유하지 않는다.
3. 기존 `sources/event_evidence.py::enrich_event_evidence`를 재사용한다. `EnrichmentPolicy`에 별도의 `preview` mode와 default-false preview capability를 추가하고, 명시된 source allowlist·qualification policy hash·run deadline을 요구한다. 기존 active capability와 별개다. preview 기본은 off; recording mode는 저장된 문서만 재생한다. 기존 active 검사를 우회해 직접 fetch하지 않는다.
4. selector를 통과한 본문에서 완결 문단을 선택한다. 원문 앞 1,200자만 잘라 쓰는 대신 source 문서당 최대 6개 passage/합계 6,000 codepoints를 보존한다. 앞부분·섹션 heading·canonical fact/날짜·변경/범위/조건과 인접 문단을 결정론적으로 우선한다. 없는 이유·맥락을 모델로 생성해 evidence에 넣지 않는다.
5. Stage1에는 document별 압축 synopsis·source metadata·핵심 원문 span을 보낸다. source-diverse round robin, required actual 우선, recurring statistics reference-only라는 기존 수리를 유지한다. 24KiB 실전송 cap을 넘기지 않는다. 6,000자 전체를 Stage1에 무조건 넣지 않는다.
6. Stage1 뒤 u168 canonical binding과 기존 fixed editorial order를 사용한다. 같은 event에 최대 4개 source documents를 묶고 `EventEvidencePacket`을 생성한다. 동일 entity/topic만으로 다른 occurrence를 합치지 않는다. 기존 known source links/canonical occurrence 관계만 사용하며 Stage1 이후 모델이 요청한 URL을 새로 fetch하지 않는다.
7. packet에서 core facts, 적용 범위·상태, 주제별 중요한 설명 질문을 정한다. 모든 질문을 공개 소제목으로 출력하지 않는다. Stage2에는 질문별 필요한 passage를 우선 배정하며, required core와 필요한 설명 passage가 맞지 않는 후순위 사건은 `budget_deferred`로 남긴다. optional role을 일률적으로 meaning→reaction→background 순으로 버리는 배정은 새 profile에서 폐기한다.

stage별 전달된 document/ref IDs, 직렬화 bytes, dropped reason을 private manifest에 남긴다. `collected → routed → Stage1 → canonical → packet → composed → reviewed → terminal` 각각 다른 분모다. 후보·자료가 있었는데 누락됐으면 source_limited가 아니라 해당 selection/packet owner 문제로 기록한다.

## 3. 기사 구성과 claim 연결 — u185

`briefing/event_document.py::generate_event_document`의 article_v2 분기에서 Stage2가 `ArticleComposition`을 반환한다. 기본은 제목·lead·연결된 문단이다. 비교가 필요한 부분만 목록/typed fact table을 사용한다. stage1과 packet의 event/fact/ref 집합은 모델이 늘릴 수 없다.

작성 문장마다 `SentenceClaim`을 붙인다. 수치·고유명·날짜·상태·부정·발언 주체·조건은 typed claim atom과 원문 span에 연결한다. `ContextRef`의 240자 locator는 유지하고 긴 문맥은 여러 locator를 담은 `EvidencePassage`로 전달한다. 한국어 번역의 품질은 reference가 존재한다는 사실만으로 통과하지 않는다.

what_changed 원문 복사는 article_v2에서 폐기한다. 원문 assertion은 private evidence로 유지하고, 독자용 lead는 검증된 한국어 문장으로 작성한다. 정확한 회사명·티커는 보존하며 한국어 기관명은 기존 entity registry의 승인된 alias를 사용한다. 등록되지 않은 alias는 임의 허용하지 않는다. 과거 what_changed/meaning/reaction 출력과 새 본문을 둘 다 생성해 공개하지 않는다.

현재 `validate_event_edition`의 what_changed `require_assertion=True` 및 모든 actor/object 원문 이름의 lead 내 포함 검사는 **version1에서 유지**한다. version2에서는 동일 canonical 사실의 원문 proof를 그대로 검증하고, 한국어 표현의 full narrative claim/alias/atom 검증과 u186 semantic verdict를 추가로 요구하는 명시적 분기로 대체한다. 단순히 require_assertion을 false로 바꾸는 구현은 허용하지 않는다. Stage1 canonical fact 생성 자체의 source proof는 어느 profile에서도 생략하지 않는다.

`models/event_document.py`가 공통 `ArticleNarrative`를 소유하고 `models/event_article.py`가 private claim/assessment를 소유한다. 본문 text의 canonical source는 narrative blocks다. 기존 소비자용 what_changed는 lead와 동일하고, 의미/반응 facets는 해당 claim을 참조하는 제한된 projection이다. full body에 없는 새 설명을 projection에서 만들지 않는다.

## 4. 검증·수정 — u186

결정론적 precheck는 event/fact/ref membership, 원문 revision/hash/span, numeric value/unit/period, entity aliases, 시각·actual/forecast·부정/조건 atom, 모든 reader sentence의 claim 연결을 검사한다. 현재 hard finding을 수집하는 owner와 numeric containment를 유지한다. 이 단계가 통과해도 자유로운 한국어의 entailment를 증명했다고 부르지 않는다.

추가 Stage3는 별도 CLI 호출에 **출처 packet + draft + claim map + 고정 질문**을 입력한다. writer의 confidence/self-score/chain of thought는 전달하지 않는다. 각 claim의 supported/contradicted/insufficient, 각 설명 질문의 answered/missing/not_applicable, 근거 span IDs와 짧은 reason code를 받는다. 판정 누락·unknown ID·형식 오류·timeout은 통과가 아니다. 같은 모델의 오류 상관성은 실제 사람 검수로 보완한다.

고칠 수 있는 내용 누락·번역·조건 누락은 모든 사건을 모아 **한 번의 수정 호출**에 전달한다. 원래 packet과 selected event/fact set은 고정한다. 수정 후 전체 precheck와 Stage3를 한 번 더 통과해야 한다. 이 두 호출의 잔여 예산을 함께 확보하지 못하면 수정을 시작하지 않는다. root trust violation의 원본 finding은 남겨 기존 finalizer 정책을 적용하며, 수정을 이용해 hard block을 숨기지 않는다.

새 material fact/evidence가 필요한 실패는 같은 근거로 반복 작성하지 않는다. `evidence_gap`으로 u184/u173에 인계한다. 기사 하나당 따로 재시도하지 않으며 전체 market 실행은 최대 5회 CLI 호출이다.

## 5. 최종화와 표면

검증을 통과한 typed article만 기존 `finalize_public_bundle` 입력이 된다. 중요한 설명이 빠진 기사를 normal detailed로 포장하지 않는다. 적법한 brief는 명시적으로 brief로 남고, 원래 detailed가 필요한 중요 사건의 brief 대체는 readiness 실패다. 논리상 필수 fact가 실패한 기사와 hard trust는 기존 block/partial policy를 따른다.

`publisher/event_edition.py`가 narrative를 렌더하고 각 sentence/claim의 실제 byte/character ranges를 반환한다. finalizer의 숫자 containment가 문장을 바꾸거나 제거하면 그 문장·claim·question coverage·digest·asset/story projection을 결정론적으로 다시 계산한다. 사실 내용이 바뀐 새 문장을 자동 작성하지 않는다. 의미를 바꾸는 수정은 삭제/차단만 가능하며 기존 semantic certificate를 재사용하지 않는다.

seal 직전 최종 narrative/packet/policy/review hash와 terminal survivor 집합을 대조한다. 검증되지 않은 본문, orphan summary, 삭제 사실의 ledger 진전은 허용하지 않는다. public projection에는 한국어 reader text·공개 가능한 source locator만 있고 원문 packet/모델 평가 문장은 없다. 봉인 후 rewrite 0이다.

## 6. 책임 표

| owner | 변경 책임 | 금지되는 책임 이동 |
| --- | --- | --- |
| models/enrichment.py, sources/event_evidence.py | preview access policy, bounded passage extraction | 새로운 provider를 자동 qualified 처리 |
| orchestrator/event_evidence.py (신규) | 기존 수집 보강 공유·deadline·source outcomes | publisher/briefing의 HTTP |
| models/event_article.py (신규), models/event_document.py | packet/claim/assessment와 reader narrative | duplicate canonical fact/story 타입 |
| briefing/event_context.py, _internal/event_context.py | input synopsis/packet allocation | evidence 생성·사후 fetch |
| briefing/event_article.py (신규) | Stage2 구성·question plan | hard gate·source qualification 소유 |
| briefing/event_article_review.py (신규), briefing/_core/orchestration.py | Stage3·5-call budget·단일 수정 | 새 provider SDK·별도 재시도 예산 |
| _internal/event_v3_contract.py | private/public shared invariant validation | LLM 의미 판정을 결정론적 proof로 표시 |
| publisher/event_edition.py, public_document.py, event_archive_reader.py | render·terminal check·versioned projection·seal | 두 번째 finalizer·과거 archive rewrite |
| models/event_quality.py, publisher/event_quality.py, scripts/_event_coverage_replay.py | readiness·실제 corpus 연계 | human 5/5 자동 생성 |
