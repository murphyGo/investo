# 실행 예산·권리·성능 계약

2026-10-26 **article_v2 설계 개정**. 기존 profile에는 적용하지 않는다. 아래 값은 실행 상한이지 측정된 성능이나 운영 승인 결과가 아니다.

## N184. HTTP와 evidence

| 자원 | 고정 상한 / 기본값 |
| --- | --- |
| 신규 body HTTP | 기존 u161: 실행당6 requests, 동시2, 소스당2 items, redirect1 포함 request count, retries0 |
| fetch timeout | request8초, 전체20초; 전체 workflow deadline이 더 짧으면 그 값 |
| 응답 | decoded500KiB/document, HTML allowlist parser만; zip/PDF/JS 실행 없음 |
| 보관 excerpt | article_v2만 source당 최대6 passages/6,000 codepoints, passage당1,200; 기존 role_v1은1,200 유지 |
| packet passage | 위 body6개와 기존 feed summary1개/source, source4개에서 최대28 passages; exact refs64·48KiB 한도 유지 |
| Stage1 | 기존96 candidates/source24/lookahead12, typed drafts12; evidence24KiB, 전체 prompt32KiB |
| Stage2 | evidence48KiB, 전체 prompt64KiB; required packet 우선, 초과 후순위 event deferred |
| 수정 호출 | 같은 evidence48KiB + 이전 draft/검토 feedback 포함 전체 prompt96KiB; 새 source 추가 없음 |
| Stage3 / 재검증 | 같은 evidence48KiB + draft/claim map 포함 전체 prompt96KiB |
| 본문 | article 최대5, source4/article, facts8/article, sentences24/article, blocks8/article, body3,200자/article |
| 모델 응답 | 각 응답 UTF-8 128KiB cap. 초과는 parsing failure; 잘라 JSON 복구하지 않음 |
| private recording | 기존12 calls/1MiB, 새 profile은 실제 최대5 calls; 초과 시 recording unavailable이고 actual corpus 인수 불가 |

evidence bytes는 실제 직렬화한 UTF-8 기준이며 별칭 metadata/ref 목록도 포함한다. 같은 passage는 batch에서 한 번 저장하고 ID로 참조한다. instruction/schema/draft/claim map까지 전체 prompt cap으로 추가 제한한다. 초과를 허용한 뒤 model context window에 맡기지 않는다. packet이 작아서 재시도 기회를 추가하지 않는다.

HTTP6회는 **전체 run 공유** 상한이다. production에서 세 시장별6회로 늘리지 않는다. 공통 collection preparation의 결과를 시장에 분배하고 동일 document를 재요청하지 않는다. preview의 각 market job도 자기 run의 상한을 지킨다. cache는 기존 private run 범위에만 두며 새로운 cross-run 원문 저장소를 만들지 않는다.

권한이 확인된 raw만 private buffer에 저장하며 live excerpt 확대는 qualification에 해당 selector/version/retention 범위가 확인된 경우에만 가능하다. 공개 synthetic fixtures는 독립 작성한 소규모 예제로 만들고 공식 원문 corpus를 public git에 복사하지 않는다.

## N185. 모델 호출·시간 예산

현재 `SEGMENT_GENERATION_POLICIES`의 timeout1800초, 국내/crypto total5700초·attempt3, 미국3900초·attempt2는 기존 두 단계용이다. 이를 복사하면 세 번째 호출이 잔여 예산 admission에서 막힐 수 있다. 새 profile은 **한 시장 총3900초·총5 calls**의 명시적 allocator를 사용한다. 기존 profile과 공통 RetryBudget의 clock/accounting을 재사용하되 각 stage 자체 retry loop는 max_attempts1로 고정한다.

| call | 목적 | 최대 timeout |
| --- | --- | --- |
| 1 | Stage1 classification | 600초 |
| 2 | Stage2 composition | 900초 |
| 3 | Stage3 review | 600초 |
| 4 | 필요한 경우 전체 batch 1회 수정 | 900초 |
| 5 | 수정 batch 전체 재검증 | 600초 |

최악의 모델 timeout 합계3600초. 3900초 중300초는 source20초와 preparation/finalization·accounting 여유다. **3900초는 source preparation 시작부터 pre-publication finalization 종료까지**의 market deadline이며, production의 기존 publication/auth cleanup reserve와 workflow deadline을 별도로 침범하지 않는다. 유효 deadline은 두 값 중 빠른 값이다. 세 시장 serial budget을 단일 preview job에 더하지 않고 기존 market matrix를 유지한다.

초기 composition은 composition900+필수 review600+local/finalization reserve60초를 모두 남겨야 시작한다. 수정은 repair900+review600+reserve60초 모두 남아야 시작한다. 실제 경과시간, 취소, parser 실패도 총량에 포함한다. timeout/transport/schema 실패를 숨겨 호출을 다시 세지 않는다. call1 실패는 생성 실패, call3 실패는 review unavailable이다. call2의 구조 오류는 유효한 candidate가 없으므로 실패 처리한다. 별도 repair는 검토된 candidate의 고칠 수 있는 gap에만 허용한다. legacy 생성 fallback 호출은0회다.

same CLI/model `gpt-6-astra`와 기존 private auth owner를 사용한다. 새 SDK/API subscription/secret을 추가하지 않는다. call 증가가 구독·Actions 사용량에 미치는 영향은 관측해야 하며 추가 비용0을 측정 없이 단정하지 않는다. account billing 확인은 기존 u155 owner에 남긴다.

## N186. 성능과 회귀 인수

NFR-001의 단일 실행10분 목표와 DEBT-090을 유지한다. 3900초 cap은 목표 완화가 아니다. 실제 preview에서 stage별 wall time·prompt/response bytes·calls·source20초·finalizer·auth cleanup 시간을 기록한다. 같은 clock/source recording으로 role_v1과 article_v2의 offline 동작을 비교하고, 별도 실제 실행을 최소2일/시장별4문서 확보해 지연·실패 원인을 보고한다. 표본12의 p95는 기술 통계이며 안정적 장기 SLA 근거가 아니다. deadline 초과·schedule overlap·auth cleanup 손상은 release blocker다. 기존10분 미달은 DEBT-090 및 u172 운영 판정에 명시하고 미해결을 합격으로 고치지 않는다.

회귀 검증은 actual source bytes/revision, 원문 부정/귀속/시제, 숫자/기간, 잘못 연결된 event, stale review hash, 온전한 문장에 끼운 unsupported 절, source prompt injection, budget 경계, sibling partial, seal idempotence, v1 hash와 새 narrative 표면 일치까지 포함한다. 이미 통과한 전체 테스트를 문서 작성 때문에 다시 실행하지 않는다. 구현 단계에서 정확한 최종 SHA의 집중/full/static/policy/docs CI를 수행한다.

## 보안·운영 불변조건

HTTP host/path/redirect/content type/size와 XML parser 정책은 기존 owner를 유지한다. source text를 delimiter 안의 untrusted data로 전달하고 source의 명령으로 tool 호출·파일 접근·추가 URL fetch를 하지 않는다. CLI stdout의 typed 결과만 받고 auth/argv/stderr를 recording에 넣지 않는다. recording은 기존0700 directory/0600 file/no-follow/exclusive write/recipient encryption을 유지한다.

private review artifact에 human reviewer ID/점수를 자동으로 넣지 않는다. public manifest는 allowlisted counts/hash/closed codes만 기록한다. live runtime enable/preview permission/qualified sources/market allowlist는 별도 hash에 결속한다. profile이 같아도 code·source/parser·prompt·policy가 달라지면 해당 acceptance evidence를 그대로 재사용하지 않는다.
