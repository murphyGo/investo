# u158 사건 중심 설명과 최종 요약

2026-09-27 사용자 요청에 따라 u157 원격 전달 후 순차 개발했다. 구현 7/7, 독립 리뷰 및 cross-check를 완료했다. 운영 활성화는 별도다.

원격 전달: `c3f2e5efe91d1a1284d9e859eedba71728a7d64b`, `origin/codex/news-event-design-20260926`의 정확한 SHA 일치를 확인했다.

## 구현

- Stage2는 명시적 JSON v2를 사용한다. 다섯 section body와 선정 순서가 동일한 event 배열을 받아 ②를 한 곳에서 렌더한다. actor/action/object refs, 필수 fact, 필드별 근거, actual/forecast/period/unit을 검증한다. 잘못된 출력은 기존 재시도 안에서 전체 JSON을 재요청하며 오류에 원문을 싣지 않는다.
- 사건의 완전한 첫 문장(80자 이내)을 상단 결론으로 사용한다. 사건이 없다는 판단과 수집 부족을 구분한다. 가격 숫자가 없어도 사건을 요약할 수 있다. LLM 단계는 기존 2개이며 추가 평가 호출은 없다.
- 원문 제목·요약보다 뒤에 있는 detail 근거도 정확한 span과 함께 전달한다. 실제 전달한 행을 macro lineage에 반영하고 보호된 근거를 grouped/unassigned에서 중복 전송하지 않는다. 기존 off/shadow 프롬프트와 출력은 유지한다.
- GenerationResult의 frozen event payload를 PublicDocumentContext로 전달한다. 기존 finalizer가 사건 생존, 상단 요약, TL;DR, optional PublicEventSummary를 최종 문서 기준으로 일치시킨다. 생성기의 Briefing 필드를 terminal 사실 원본으로 재사용하지 않는다.
- 구조적 누락과 미지원 사실을 구분한다. 기존 numeric/entity/compliance hard finding을 삭제 전에 검사하며 제거된 사건은 재삽입하지 않는다. 문서 seal 시 살아 있는 사건의 identity receipt만 만든다.
- `orchestrator.event_preview.preview_event_briefing(GenerationInput)`은 supplied inputs와 timezone-aware clock을 받아 실제 생성·finalizer를 수행한다. collect/GenerateStage/PublishStage/NotifyStage, archive·Git·cursor 쓰기를 호출하지 않는다. 공개 main/run_pipeline에서는 preview가 capability와 관계없이 차단된다.

## 다음 유닛과 운영 경계

기본 event mode는 off다. 비게시 preview capability만 구현했으며 active capability는 false다. u159가 terminal coverage, 12 golden 시나리오와 E11 운영 handoff를 연결한다. 현재 선정 창은 수신 시장의 기존 calendar-day이며 주말·장후 관측 확대는 u160이 소유한다. 예를 들어 같은 FOMC 발표가 미국 날짜 창에는 포함되고 한국 날짜 창에는 포함되지 않을 수 있으며 공유 후보라는 이유로 창을 우회하지 않는다.

source span·구조·숫자·명칭 검증은 자유 서술의 모든 의미를 자동 증명하지 않는다. 의미의 적합성은 주석 fixture와 별도 평가로 확인한다. u154 배치, u156 알림 레이아웃, 실시간 소스, 과거 archive, credentials 및 운영 workflow는 이 유닛의 변경 대상이 아니다.

## 검증 기록

최종 전체 5,521개 테스트가 402.28초에 통과했다. Ruff/format 626개, mypy 278 source, 정책 검사, strict MkDocs 및 Material 계약 검사를 통과했다. 사건 선정부터 terminal 검사까지 1,000개 입력 benchmark의 p95는 69.97ms였다(한도 200ms). 두 wave 독립 리뷰의 미해결 P1/P2는 0건이다. 자세한 결과는 `validation.json`, 코드 리뷰 및 cross-check 보고서에 기록했다. 실제 LLM 서비스 호출·운영 게시·Telegram·Pages·scheduled shadow는 이번 오프라인 검증에 포함하지 않는다.
