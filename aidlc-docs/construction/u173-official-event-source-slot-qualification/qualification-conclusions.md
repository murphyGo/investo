# u173 source-slot qualification 결과

2026-10-12 KST. Qualification 도구와 기존 typed factory 연결을 구현했다. 공개 manifest의 판정은
**verified 0 / blocked 8**, runtime probe는 모두 not_run, activation_ready는 모두 false다.
실제 source 준비·운영 복구 완료를 뜻하지 않는다. 현재 필수 내용을 조사하지 않은 행은 access.not_verified와
schema.unknown/slot.required_missing을 보존했다. 과거 HTTP family qualification을 현재 slot 성공으로 확대하지 않았다.

| Slot | 기존 source | 결론 | 부족한 현재 근거 / 후속 책임 |
| --- | --- | --- | --- |
| policy.monetary_decision | fomc-rss | ship-existing feed / blocked slot | Fed 과거 허용 body family 안의 현재 결정·규모·권리·parser·runtime; u173/u161 owner |
| policy.official_statement | fed-speech-rss | ship-existing feed / blocked slot | speaker/인용·실제 시점·Board 본문 권리·runtime; testimony는 defer-new |
| policy.regulatory_action | cftc-policy-rss | ship-existing feed / blocked slot | authority/action/status/scope와 현재 body; 과거 CFTC family 범위 유지 |
| policy.domestic_announcement | korea-policy-rss | ship-existing feed / blocked slot | 현재 FSC 조치·대상·권리·parser; upstream 상태는 u165, 새 body는 defer-new |
| earnings.reported_actual | sec-company-facts | ship-existing API / blocked slot | issuer/actual/unit/period/filing 연결과 현재 접근·fixture·runtime; u173 source owner |
| earnings.guidance | sec-edgar-8k | ship-existing metadata / defer-new body / blocked slot | release/exhibit의 실제 guidance·기간·path·parser; 새 issuer 경로는 별도 adapter 설계 |
| domestic.disclosure_action | dart-disclosure | ship-existing 접수 목록 / defer-new body / blocked slot | report_nm/접수번호로 action_terms를 만들지 않음; 실제 조건·상태·본문·권리·runtime 필요 |
| earnings.schedule_context | nasdaq-earnings-calendar | ship-existing calendar / blocked slot | issuer/date/bucket·현재 schema/권리/runtime; actual/guidance source로 승격 금지 |

정책·실적·국내공시 모두 필요한 현재 slot 자료는 부족하다. SEC newsroom/commercial body의 이전 denied 결과는
기존 API/feed 전체 실패의 근거가 아니며 이 manifest로 새 HTTP를 열지 않는다.

## 권리·공식 discovery와 판정의 차이

SEC 두 행에는 [SEC 웹사이트 FAQ](https://www.sec.gov/files/about/webmaster-faq.htm)의 정부 작성 자료와 공개 EDGAR
자료 재사용 범위를 기록했다. illustrative stock photograph와 외부 자료로 권리를 확대하지 않는다.
[data.sec.gov](https://data.sec.gov/)와 [Fed 공식 feed 목록](https://www.federalreserve.gov/feeds/feeds.htm)은
discovery 참고 자료다. 문서 조회는 실제 API/body 접근·schema parser·필수 slot·runtime 성공 증거가 아니다.
따라서 endpoint scope/access hash/schema fixture/parser가 없는 현재 행은 계속 blocked다.

## 구현과 검사

`models/enrichment.py`에 frozen qualification row/set과 닫힌 8개 required-field 집합을 추가했다.
64행/64KiB, 정확한 source identity, public HTTPS host/path/query names, 권리/hash/precision과 verified 조건을 검사한다.
`sources/event_evidence.py`의 loader와 `map_source_slot_context`는 기존 u167 factory를 사용하고 원문 ContextRef의
ownership을 확인한다. earnings actual은 subject/metric/value/unit/period/actual의 같은 문맥 결속을 추가 확인한다.
추가 parser·source 등록·LLM·runtime fetch는 없다. 없는 의미·반응·후속은 만들지 않는다.

offline checker는 정상 blocked 행을 자료로 받아들이지만 source-ready로 세지 않는다. source/slot/status/닫힌 reason/count만
출력하며 HTTP/LLM/archive/notify/ledger/cursor 쓰기는 0이다. synthetic mapping 양성/음성과 private 실측은 구분한다.
현재 실제 raw private parser capture는 확보하지 않았으며 후속 evidence로 남겼다.

## 후속 handoff

기존 feed/API는 현재 owner 정책 안에서 소비한다. native reader가 충분한 근거를 받으려면 source owner가 승인된
정확한 host/path에서 bounded capture를 확보하고 public reuse·parser region·필수 field·시간·locator를 검증해야 한다.
키는 기존 secret 이름/연결 여부만 확인하고 raw 응답/headers/모델 출력은 ignored private 경로에 둔다.
새 provider/path/API가 필요하면 등록·window·consumer·secret·비용·권리 계획을 별도 unit으로 검토한다.

u161 body HTTP capability, u160 cursor, u172 사람 수용과 runtime release는 각 소유자의 gate다.
qualification tooling 완료와 source-ready 0/8을 별도로 기록한다.

## 2026-10-25 실제 feed parser capture

기존 adapter와 retry owner만 호출해 정확한 기존 feed 7개 범위에서 private capture를 시도했다.
새 body/provider 경로와 source key는 추가하지 않았다. 30일 창은 parser characterization을 위한 것으로,
실제 production news-window recall이나 현재 monetary decision의 수용 표본이 아니다.

Fed press 1응답/13개, Fed speech·testimony 2응답/11개, CFTC 3응답/12개를 정규화했다.
기존 u167 factory로 36개 typed context를 만들고 source-owned span 84개를 원본 chunk와 대조했다.
국내 FSC feed는 `SourceFetchError`를 반환했다. 이 capture에서 더 구체적인 원인을 판정하지 않았다.

원문·normalized items·typed context는 ignored private 경로에만 저장했다.
[공개 가능한 count/hash 기록](code/feed-parser-capture-20261025.json)은 raw text를 담지 않는다.
이는 feed parser의 현재 증거다. official body 접근·권리·필수 slot field binding·나머지 source/runtime의
검증은 부족하므로 manifest의 verified 0/8과 activation false를 유지한다. Step 4는 부분 진전이며 완료가 아니다.

추가로 기존 SEC companyfacts를 기본 목록의 1개 기업으로 제한해 2응답/1개, SEC 8-K 목록 1응답/36개,
Nasdaq 실적 캘린더의 2026-10-23 한 날짜 1응답/32개를 정규화했다.
[추가 count/hash](code/structured-parser-capture-20261025.json)의 69개 typed context와 원문 span 148개를
대조했다. 합계는 6개 source의 normalized/typed context 105개와 span 232개다. FSC 1개 source는 실패했고
DART는 이 로컬 capture에서 호출하지 않았다. 기존 managed credential을 변경·복사하지 않았다.
8-K 목록을 guidance, 캘린더를 actual, company snapshot을 새로운 reported actual로 승격하지 않았다.
원본의 단위·기간·발생 시점·filing locator의 독립 검증과 body/rights/필수 slot/runtime 수용은 계속 pending이다.
