# Event/news v3 private 수용·전환 절차

2026-10-12 KST. 개발과 비게시 preview를 위한 handoff다. 현재 기본 schema는 2,
v3 preview만 가능하며 active capability는 false다. 이 문서는 release 지시나 사람 점수를 생성하지 않는다.

## 현재 확인할 입력

`ops/event_v3_acceptance.json`은 공개 가능한 count/hash/closed state만 담은 blocked 증거다.
`ops/event_v3_preview_policy.json`은 시장 allowlist가 빈 preview 정책이다.
정확한 구현 SHA와 정책 bytes를 고정한 뒤 다음 읽기 전용 검사로 상태를 확인한다.

```sh
uv run python scripts/check_event_cutover.py \
  --evidence ops/event_v3_acceptance.json \
  --reviewed-code-sha REVIEWED_CODE_SHA \
  --policy ops/event_v3_preview_policy.json
uv run python scripts/check_event_source_slots.py \
  --manifest ops/event_source_slot_qualification.json
```

`--require-ready`는 blocked 상태에서 실패해야 한다. 검사 결과는 활성화 명령이 아니다.
source-slot verified, 기존 body HTTP 자격, cursor 준비, human-ready, runtime pin은 서로 별개다.

## 실제 12개 문서의 수용 자료

원시 입력·원문·CLI 응답은 ignored `.tmp/event-news-v3/corpus/` 또는 기존 암호화 private artifact에만
보관한다. `.tmp/event-news-v3/source-qualification/`도 ignored다. 두 경로의 `git check-ignore`를
확인했다. public synthetic 57개 사례의 author는 AI, human review는 pending이며 실제 corpus에 합산하지 않는다.

schema 3 Codex의 실패 원문을 조사할 때는 `--record-model-io` 또는 private workflow의
`record_model_io=true`를 명시한다. 기본값은 false다. 실제 전달한 prompt와 기존 runner가 검증한 stdout만
`model-recording.json`으로 기록하며 argv·stderr·auth 파일은 수집하지 않는다. 파일은 사전에 ignored 여부를
검사하고 0700 private 경로의 exclusive/no-follow 0600 파일로 저장한 뒤 기존 recipient 키로 암호화한다.
최대 12회/1MiB이며 초과·encoding 실패는 전체 기록을 unavailable로 표시하고 부분 원문을 남기지 않는다.
취소 중 미완료 호출은 incomplete다. recording complete는 입출력 기록의 완전성만 뜻하며 생성·사람 수용 성공이 아니다.
이 기록은 실제 전송 입력의 진단 자료이며 전체 수집 분모·사전 사람 oracle·ingestion recall을 대체하지 않는다.

1. 국내·미국·크립토 각각 실제 4개 이상, 발행 날짜 2개 이상을 확보한다. 시장별 뉴스가 풍부한 정상
   사건, 수집 제한, 주말/장후 사례를 포함한다. 같은 입력의 반복·수동 재생은 실제 사례 수를 늘리지 않는다.
2. 출력 생성 전에 사람이 뉴스창, source 범위, 기대 event/story IDs, must-include, required facts,
   forbidden claims와 expected support를 주석한다. 외부 baseline 부재는 null이며 후보 cap 5로 외부 분모를 줄이지 않는다.
3. 기존 preview 도구에 `--document-schema 3`을 전달한다. 코드 SHA와 remote data baseline SHA를 분리한다.
   수집은 기존 owner가 담당하고 generation은 기존 CLI 두 단계다. archive/Git/Telegram/ledger/cursor 쓰기는 0이다.
   private runtime preview template은 schema 2/3 선택을 제공하되 기본값 2를 유지한다.
4. annotation hash, 원시 recording hash, sealed Markdown hash, projection hash, HTML/DTO와 시각을 결속한다.
   finalizer가 만든 source refs를 원문과 대조하고 본문·digest·반응·후속·자산 영향까지 사람이 읽는다.
5. 사람이 what/when/why/react/source 각 0/1을 기록한다. 미검수는 pending/null이다. why unavailable은 0;
   명시적인 시간·반응 미확인은 해당 rubric의 유효한 답일 수 있다. AI가 사람의 비식별 reviewer ID/점수/시각을 발급하지 않는다.
6. `measure_event_quality_v3`의 자동 required-fact 100%/unsupported 0과 사람 5/5를 별개로 기록한다.
   `semantic_records_hash`로 annotation/review 컬렉션을 결속한다. 세 시장 모두의 뉴스 풍부한 정상 양성이 필요하다.

원시 입력이 없는 과거 발행본은 output regression이다. ingestion recall·source 접근·사람 합격을 복원하지 않는다.
현재 실제 corpus와 사람 review는 0개이며 대기 상태다.

## 배포 전 확인과 운영 관찰

code-ready에는 exact SHA의 전체·집중·정적·정책·문서 검사와 실제 end-to-end 성능 비교가 필요하다.
오프라인 1,000개 입력 warm 10회 p95 측정은 source collection→실제 CLI→publish 성능을 대체하지 않는다.
DEBT-090은 미완료 상태를 유지한다. final HTML의 390×844, 1440×900 viewport도 실제로 확인해야 한다.

human/source/cursor 준비와 명시적인 release 지시가 확보되면 별도 reviewed 변경으로 active capability,
runtime owner/pin, schema 3와 합격 시장 allowlist를 연결한다. 현재 production pin과 workflow에는 이 변경을 하지 않았다.
코인은 자체 합격 증거가 있어야 allowlist에 들어간다. 이전 schema 2의 전체 code SHA와 정확한 policy hash도 고정한다.

각 시장의 최초 3개 서로 다른 genuine scheduled run에서 다음을 한 receipt로 결속한다:
생성 schema와 outcome, remote-confirmed publication SHA, Telegram, 해당 publication의 Pages SHA,
identity/story metadata와 기존 news cursor. 수동·재시도·취소·skip을 새 예약 관찰로 세지 않는다.
generation/finalization/publish/notification/Pages/exit code와 유효 sibling은 각각 기록한다.
현재 예약 관찰은 0회다.

## 전체 복구와 최종 폐기

hard trust, 사건 재노출, 무근거 story 전진, 필수 fact 누락이나 schema/policy 불일치가 발생하면 해당 시장의
promotion을 멈추고 이전 reviewed schema 2 **전체 commit과 policy**로 복귀한다. 같은 실행에 추가 LLM 단계로
legacy 재생을 붙이지 않는다. runtime auth owner/pin readback과 게시·알림·Pages를 다시 확인하고 기존 archive를 재작성하지 않는다.
복구 rehearsal의 실제 실행 증거가 없는 동안 이 항목은 pending이다.

세 시장 accepted와 서로 다른 실제 v3 예약 관찰 10회, reviewed cleanup SHA가 확보되어야 최종 폐기한다.
그 전에는 default 2와 legacy 생성 호환을 유지한다. `tests/fixtures/event_briefing/terminal_snapshots.json`에
reviewed 전환 코드의 v2 합성 25개 사례·24개 terminal을 historical_output으로 고정했다.
폐기 시에는 그 snapshot/hash를 확인하고
generator/free-section strings/빈 bridge/활성 rewrite를 제거하며 default 3, retired policy 거부,
read-only archive 회귀, 이전 commit/policy 복구를 검증한다. cleanup은 현재 실행하지 않았다.

## 후속 책임과 남은 증거

| 항목 | 후속 책임 | 현재 상태 |
| --- | --- | --- |
| 실제 corpus·사람 rubric | u172 운영 검수자 | 0/12, pending |
| 출처 access/rights/parser/필수 slot·runtime | u173 source owner + 기존 u161/u165 운영 owner | verified 0/8 |
| end-to-end p95·DEBT-090 | 기존 runtime/performance owner + u172 | baseline/표본 미확보 |
| native viewport | u171 reader QA | 미실행 |
| reviewed capability/pin/release | 기존 private runtime owner + u172 | active false |
| genuine scheduled·Pages·Telegram·ledger/cursor | u172 운영 owner | 0회 |
| legacy 최종 폐기 | u172 reviewed cleanup | 선행 수용 대기 |
