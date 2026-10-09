# Event/news v3 — 비기능 요구와 설계

**Date**: 2026-10-10. **Status**: 설계 작성; 구현/측정 미실행. 현재 NFR-001~008을 재사용하며 새 제품 구조의 구체적인 적용을 고정한다.

## N1. 성능과 실행 예산

LLM은 기존 두 단계다. provider별 timeout/attempt/backoff와 전체 deadline을 그대로 전달하고 새 평가·요약·수리 단계를 무제한 추가하지 않는다. Stage1 evidence24KiB, v3 Stage2 protected16KiB는 실제 UTF-8 직렬화로 계산한다. chunk text만 세고 ID/ref/header overhead를 빼지 않는다.

source body는 기존 u161 max6요청/동시2/20초/decoded500KiB/소스당2/redirect1/retry0를 따른다. source-slot 판정이 이 상한을 자동 확대하지 않는다. document/history/story cap은 C3/C4/C6을 적용한다. buffer·ledger 초과를 silentlytruncate해 완전한 이력/설명을 주장하지 않는다.

최종 code acceptance는 실제 source collection→generation→finalization→publish end-to-end 시간을 측정한다. 기존 NFR-001의10분 목표와 DEBT-090은 그대로 유지한다. 목표 미달은 성능 제한으로 기록하고 offline helper 테스트만으로 p95 달성을 주장하지 않는다.

## N2. 결정론과 단일 원본

동일 typed input과 기록된 두 단계 응답은 같은 선정·본문·digest·survivor·story delta·SHA를 만든다. 모든 동점 정렬은 canonical ID와 source key에 의존하고 set/dict iteration에 의존하지 않는다. publication clock과sourceeventtime을구별한다.

최종 public text는 u144 단일 finalizer에서만 조립/수리/투영/검증/봉인한다. seal 후 rewrite0회다. v3 JSON과별도freeMarkdown을동시에원본으로보관하지않는다. 최종view를받은웹/알림/홈/회고/시각은자체LLM요약으로새사실을추가하지않는다.

## N3. 신뢰와 부분 실패

numeric/entity/freshness/actual-forecast/compliance/disclaimer/structure/notification/asset/remote gate는 새 schema의 claim/region 소유권에 맞춰 적용한다. 필수7H2의폐기는구조검증삭제가아니다. schema3의필수marker/metadata/availability/article또는empty상태/면책을대신검증한다.

현재 국내 numeric-only containment와링크/표현국소수리의권한은기존owner에있다. US/crypto numeric hard failure를자동국소수리로바꾸지않는다. original hard finding을수집하기전에article을삭제해위반을숨기지않는다. 한시장의진짜신뢰차단/generationabsence는validsibling게시·partial·exit2·Pagesdispatch로표시한다. notification-onlyfailure는기존정책을유지한다.

## N4. source 권한·비용·private 자료

무료 source와 기존 CLI/provider 경계를 유지한다. SDK/유료 API/key fallback을 추가하지 않는다. source의 reachable 상태, public reuse, MIME/schema/parser/실제내용/시각은 각각 검증한다. SEC나상업매체의403을우회하지않는다. slotverified와bodyqualified/HTTPactive는별개의gate다.

raw body,chunk buffer,private fixture,실제LLM실패문장,token/secret은publicGit/log/history/summary에쓰지않는다. 공개qualification/evaluation에는sourceID·status·hash·날짜·boundedreason·SHA만포함한다. 실제privatecorpus는기존암호화artifact/허용private경로에서검수하며합성publicfixture와혼동하지않는다.

## N5. 상태의 진실성과 설명 가능성

content/time/novelty/locator/meaning/reaction 축을구별하고0/null/unknown을보존한다. failed/zero/skipped는현재 source lifecycle owner의literal을재사용한다. 중요사건0과수집부족0을같은문구로표시하지않는다. internallyselected최대5의생존률을외부중요뉴스포착률로표시하지않는다.

freeprose의의미/인과는regex·hash·URL잔존만으로증명되지않는다. 기존사람what/when/why/react/source5/5,requiredfact100%,근거없는사건/인과0을유지하고실제12문서/균형36case로평가한다. 사람검수미채점은pending이고operatorreleaseexception은score변경이아니다.

## N6. 모듈 경계와 호환 폐기

모든컴포넌트간공유타입은models에있다. sources→briefing/publisher,briefing→publisher,notifier/visuals→publisher의새siblingimport를추가하지않는다. neutral_internal의pure검증은existingmoduleboundaryguard의정식allowlist와역할을확인한다.

u168foundation이sharedstoryDTO를먼저선언하고u169renderer/finalizer,u170reducer/ledger가이를소비해의존cycle을없앤다. v3는한payloadvariant이며7개dummyfields로기존API를속이지않는다. legacy생성은전환기간뒤제거하고historicalread-onlyparser만보존한다.

## N7. ledger·원격 확인·출판 원자성

새identity/storymetadata는같은publicationtransaction에서확정한다. priorhash/CAS와PushReceipt의원격ancestry확인을재사용한다. push응답유실에서불확실하면receipt/state를임의로확정하지않는다. 실제terminalsurvivor에표시된storyproposal/nextrecord/hash/refs만ledger에반영한다. preview/shadow/미게시/수집-onlyproposal은writes0/freshnessupdate0다.

archive/asset/ledger/readerpages는pre-gitrollback과post-commitfailure를구별한다. source/cursorgate를documentmode로대체하지않는다. budget을넘는metadata와casconflict는명시적인운영outcome으로처리하고과거state를조용히덮어쓰지않는다.

## N8. 독자 표면과 관측

Telegram은최종4096UTF-16units를검증하고필수상태/링크/면책을예약한뒤완성event단위로추가한다. 실패시장/수집한계안내를수치목록뒤에숨기지않는다. 공개채널/운영자채널은분리한다.

실제finalHTML의390×844/1440×900viewport와알림text를확인한다. screenshot/browser가없으면미검증이고MkDocsPASS로대체하지않는다. publishedSHA/PagesSHA/documentSHA/DTO/eventID/storyreceipt와실제예약run을연결한다. manualreplay로first3/10scheduled횟수를채우지않는다.

## 단위별 적용과 검증

u167:N1/N2/N4/N5/N6/N7, u168:N2/N4/N5/N6/N7, u169:N1~N8, u170:N2/N3/N4/N5/N6/N7, u171:N2/N3/N4/N5/N6/N8, u172:N1~N8, u173:N1/N4/N5/N6/N7. 자세한예정test경로·명령·실제운영증거는각unitplan과[수용계획](acceptance-and-rollout.md)에있다. 이번문서작업에서그구현검증을실행했다고보고하지않는다.
