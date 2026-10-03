# u161 공식 사건 근거 보강

u160 `79b9f039` 원격 확인 뒤 순차 개발했다. 기존 피드에서 280자 요약 뒤에 있는 사실을 typed evidence로 보존하고, 이용 근거와 본문 구조가 확인된 공식 출처에만 추가 HTTP를 허용한다. 운영 활성화는 별도다.

## 소스 판정

- CNBC 기존 피드와 공식 RSS 안내는 현재 403이다. 다른 제공자로 바꾸거나 접근 우회를 추가하지 않고 blocked로 기록했다.
- 금융위 기존 HTTP 주소는 같은 제공자의 HTTPS로 302 이동하며, 현재 XML은 `pubDate` 대신 시간대 없는 `dc:date`를 제공한다. 기본 URL을 HTTPS로 수정하고 날짜 정밀도로 해석한다. 이전 parser의 같은 날짜 0개가 수정 후 실제 기본 HTTPS 단발 호출에서 7개로 회복됐다. 운영 scheduled 회복까지 주장하지 않는다.
- FOMC 보도자료, 연준 연설, CFTC 보도자료는 공식 feed의 직접 링크, 기관 이용 근거, 정확한 host/path/MIME, 유일한 본문 영역과 실제 본문 SHA를 확인했다. SEC 본문은 403이라 blocked다. 범위 밖의 연준 증언, CFTC 연설/첨부, 실적 첨부·기업 IR·상업 매체 본문은 가져오지 않는다.

## 데이터 흐름

기존 여섯 adapter는 v2가 명시적으로 전달한 관측 clock이 있을 때 원래 RSS description에서 정규화한 최대 1200자를 `NormalizedItem.event_evidence`에 담는다. 기존 summary 280자와 raw metadata, source/category/routing은 유지한다. off/shadow는 원래 item과 직렬화 bytes를 보존한다. 금융위의 확인된 transport/date 수리는 별도 명시적 호환 변경이다.

공통 evidence identity/factory는 models로 옮기고 briefing의 기존 import API는 유지했다. sources→briefing 의존성을 추가하지 않는다. SourceCollectionReport→CollectStage→수신 시장→GenerationInput→Stage1의 실제 buffer→Stage2의 실제 선정 span으로 운반한다. 시장/실패 source의 근거를 다른 item에 붙이지 않는다.

추가 본문은 collection 후 generation 전에만 요청한다. 모델이 소유한 EnrichmentPolicy와 닫힌 qualification manifest를 사용하며 max6 HTTP(redirect 포함), 동시2, source당2기사, 요청8초, 합계20초, decoded500KiB, excerpt1200, retry0, 동일 allowlist redirect1회를 적용한다. 가능한 기존 실행 deadline도 상한에 반영한다. 실패는 원래 feed item과 수집 성공 상태를 보존하고 별도 닫힌 enrichment outcome을 남긴다. 사건 발생 시각/actual/예상/guidance를 추출기에서 생성하지 않는다.

본문 수집 후보는 qualification·URL 적격성을 통과한 뒤 source당 최신2개를 선정한다. malformed HTML은 해당 보강만 unavailable로 남긴다. feed의 증거화 불가능한 URL은 opt-in 경로에서 그 기사만 제외하며 정상 sibling을 유지한다. shared streaming helper가 이미 해제한 압축 응답을 다시 해제하지 않도록 응답 헤더를 맞추고, 압축 해제 후 크기 제한은 유지했다.

`INVESTO_EVENT_ENRICHMENT_MODE`는 기본 off다. shadow는 새 HTTP·manifest read 없이 동작한다. active는 v2와 별도 operational capability를 요구하며 현재 false다. Source qualification은 실제 활성화 허가가 아니다.

## 검증

실제 RSS parsing·collection·generation·finalizer 경로에서 281~1200번째 문자에만 있는 사실이 최종 본문과 알림 DTO에 도달하는 합성 사례를 검증한다. 실제 원문 세 개는 private bytes를 구현 parser로 재생해 정확한 영역과 963/1200/1126자 상한 및 독립 검사와 같은 hash를 확인했다. raw 본문은 public Git에 넣지 않는다. 전체 gate와 독립 검토 수치는 최종 `validation.json`에 기록한다.

실제 LLM, 운영 end-to-end p95, scheduled shadow와 active 게시/알림은 미실행이다. 기존 DEBT-090의 10분 성능 미달을 이 오프라인 검증으로 해결했다고 표시하지 않는다.
