# u185 Code Generation Plan — 근거 기반 한국어 기사 구성

2026-10-26. **설계 작성; 구현0/6.** 승인된 사건별 산문·선택적 목록/표·하단 안내 정책을 실제 자동 기사에 적용한다.

## 문제·목표·Coverage

현재 what_changed 원문 assertion 강제와 각 설명180자 역할 필드가 자연스러운 한국어 기사와 주제별 구성을 제한한다. display_blocks만 바꾸는 수리는 이미 완료됐다. 이번 유닛은 검증 가능한 **sentence claim + typed narrative**로 생성 계약을 확장하고 reader projection/version/hash를 보존한다.

US-002/003/004/006/007/009; FR-002/003/004/006/009/012/013/017/018/024/025; NFR-003/004/005/006/007/008. u169/u171 확장이고 u167/u168 source/fact/entity와 u144 finalizer를 재사용한다. 새 finalizer, 자유 Markdown, claim 없는 본문, 모든 기사의 고정4문단, human 점수 자동화, production activation은 범위 밖이다.

Functional Design/NFR **EXECUTE — 공통 설계 작성됨**: [흐름](../event-news-v3-content-20261026/functional-design/business-logic-model.md), [규칙](../event-news-v3-content-20261026/functional-design/business-rules.md), [타입](../event-news-v3-content-20261026/functional-design/domain-entities.md), [NFR](../event-news-v3-content-20261026/nfr-requirements/nfr-requirements.md). u184 packet 타입/전송 계약 선행, u186 verifier는 최종 사용의 hard dependency다. verifier 미구현 상태에서는 v2 narrative를 정상 공개/active로 연결하지 않는다.

## Module map

기존 `models/event_document.py`, `models/event_context.py`, `briefing/event_document.py::render_event_document_prompt/generate_event_document`, `_internal/event_v3_contract.py::validate_event_edition`, `publisher/event_edition.py`, `publisher/public_document.py`, `publisher/event_archive_reader.py`, `models/public_notification.py`를 수정한다. `models/event_article.py`의 u184 타입에 claim을 추가하고 신규 `briefing/event_article.py`가 composition schema/prompt/parse를 담당한다. source HTTP·canonical identity·story reducer를 이동하지 않는다.

## 구현 순서

- [ ] **Step1 — claim/narrative 타입**: frozen atoms/claims/sentences/paragraph·bullets·fact_table을 선언한다. event/fact/ref 집합과 문장별 모든 주장 연결, core/facet 단일 text owner를 검증한다. 기존 EventArticle v1은 그대로 허용한다.
- [ ] **Step2 — Stage2 작성**: article_v2에서 raw assertion copy 대신 한국어 narrative를 생성한다. 원문 근거·숫자·조건·귀속은 private packet에 보존한다. 기본 산문, 선택 목록·typed표, headline/digest claim 검증, 비어 있는 역할 미노출을 prompt/schema에 고정한다. 모델이 source/fact/event/필수 질문을 추가·삭제하지 못한다.
- [ ] **Step3 — 결정론적 precheck**: typed source ownership·span·entity alias·numeric/time/status 검사와 완전한 claim coverage를 연결한다. 기존 hard finding을 지우지 않는다. 새 한국어 문장의 의미 검증은 u186의 별도 결과가 필요하고 refs 존재만으로 supported를 발급하지 않는다.
- [ ] **Step4 — renderer/finalizer 연결**: version2 narrative만 한 번 렌더하며 실제 sentence ranges를 반환한다. 삭제/containment 뒤 coverage와 digest/asset/story를 재계산한다. 기사 조건은 본문에, 공통 안내·canonical 면책은 하단1회로 유지한다. u186 readiness hash가 없거나 stale이면 seal 거절이다.
- [ ] **Step5 — public version/reader**: schema3/content_contract2를 추가하고 v1 raw shape/hash를 유지한다. v1에 새 default를 넣어 옛 hash를 다시 계산하지 않는다. home/Telegram/OG/회고/sidecar가 동일 terminal 자료를 소비하고 미지원 version은 archive link fallback이다. raw packet/review text는 공개되지 않는다.
- [ ] **Step6 — 검증·인계**: 아래 byte/hash·adversarial·finalizer·표면 회귀, exact-source CI와 local review를 완료한다. u186에 후보/claim/range/hash 계약을 전달하고 실제 source/human/viewport는 u172/u173 pending으로 남긴다.

## Acceptance Criteria

1. **AC-185.1**: 충분한 private packet으로 한국어 제목·lead·연결된 문단을 생성한다. source role명을 의무 소제목으로 쓰지 않고 topic별 표/목록을 선택한다. 임의 추가 사실·최소분량 채우기가 없다.
2. **AC-185.2**: 모든 reader factual clause와 headline/digest가 claim/refs를 갖고 조건·부정·attribution·시간을 보존한다. unsupported 수식절/인과를 끼운 음성은 차단된다.
3. **AC-185.3**: 같은 atom의 영어 원문과 허용된 한국어 표현이 각자 근거에 연결된다. alias/숫자 일치와 의미 supported는 별도 판정이며 Stage3 부재에서 seal0이다.
4. **AC-185.4**: text 삭제/숫자 containment가 readiness와 모든 projection을 갱신하고 stale review를 거절한다. seal 두 번의 bytes/outcome은 동일하며 봉인 뒤 rewrite0이다.
5. **AC-185.5**: v1 실제 archive fixture의 bytes/hash/reader 결과가 동일하다. v2 round-trip, unknown version, rollback reader 실패가 명시적으로 처리된다.
6. **AC-185.6**: 본문·알림·home·OG·회고의 terminal IDs/text가 일치한다. footer canonical1회와 private raw 비노출이 유지된다.

## Tests / Validation

기존 `tests/integration/test_event_document_claim_boundaries_v3.py`, `tests/integration/test_event_document_v3_replay_u172.py`, `tests/integration/test_event_preview_native_v3.py`, `tests/unit/orchestrator/test_event_preview_boundary.py`를 포함한다. 기존 renderer/archive/notification test 파일은 구현 시 `rg --files tests`에서 해당 owner를 찾아 함께 실행한다.

신규: `tests/unit/models/test_event_article_narrative_u185.py`(AC1/2), `tests/unit/briefing/test_event_article_composition_u185.py`(AC1/2/3), `tests/unit/publisher/test_event_article_projection_u185.py`(AC4/5/6), `tests/integration/test_event_article_surfaces_u185.py`(AC4/6). 합성 조건부 설명·법안/시행·귀속·multi-clause·비교기간·source role mixing을 포함한다.

u184와 같은 extras 설치 후 위 파일 `uv run python -m pytest -q`, Ruff check/format, `uv run mypy src`, `git diff --check`를 수행한다. 새 source/runtime 승인이나 실제 사람이 합격했다는 기록은 만들지 않는다. full/policy/docs/exact-SHA 인수는 u186/u172와 동일 결과에 결속한다.
