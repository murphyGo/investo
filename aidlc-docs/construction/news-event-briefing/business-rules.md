# 처리·실패·소유권 규칙 (Proposed)

## B1 호출/소유권
sources는NormalizedItem/EvidenceDocument를만든다. orchestrator만sources/briefing/publisher/notifier를연결한다. briefing은E2~E6 선택/서술, publisher는terminal event 검증/summary projection, notifier는sealed DTO만소비한다. 공통DTO는models, 순수parsing도형제unitimport없이분리한다.

## B2 입력과 글로벌 관련성
가격/registry는숫자·entity근거로남기고사건경쟁을독점하지않는다. 기존segment배분후중요공유사건후보를추가하는 pure briefing helper를orchestrator에서호출한다. 글로벌공유대상은공식Fed/FOMC 결정/발언으로닫는다. 최대6item/수신segment,Stage1 96예산에포함. 암호화폐전용법안은crypto,기업실적/제품은회사/산업관련segment만. FOMC는 official Fed host의 monetary pressrelease 경로, speech는 official_source=true와 speech 경로를 검증한다. 기존 u74의 cause allowlist는 item 단위 사건 인증이 아니며 geopolitical/systemic용 typed producer가 없으므로 해당 글로벌 공유 lane은 비활성으로 둔다. 단지headline에'war','Fed'가있다는이유로공유하지않는다. 각segment의설명은자산과의관련성을분리하며같은시장방향을복사하지않는다. event selection은segment별이다.

## B3 신뢰와 중요도의 분리
공식성은신뢰의일부이지무조건핵심기사라는뜻이아니다. 숫자의정밀도도중요도의대용지표가아니다. 큰사건이숫자없이도eligible,오래된정확한월간값은background. 현재발표한실적actual/정책결정은사건이며필수숫자를보존한다. 시장반응을확인하지못하면반응미확인으로남긴다.

## B4 생성·retry
E9를 따른다. shadow는 기존 v1의 결정론적 진단만 하고 v2 품질은 비게시 preview에서 검증한다. active는 u157/158/159 통합 후에만 선택한다. Stage1/2는 기존 RetryBudget/timeout을 공유한다. v2 schema 오류는 같은 stage의 기존 재시도 대상이며 독립 retry/세 번째 평가 LLM을 추가하지 않는다.

## B5 누락과 안전문구
선정사건what/필수fact누락은event별재생성feedback에포함한다. 예산소진후구조적누락만있고원래actor/action/title/URL이안전하게확인되면원문제목과'세부설명은원문확인이필요합니다'의deterministic bounded event block을사용하고detail_limited로계수한다. 안전fallback은기존sentence/link/compliance검증을통과해야한다.

E6 사건 validator의 구조화 fact/entity/evidence 위반과 기존 numeric/entity/compliance non-presentation hard finding은요약축약/본문삭제로숨기지않는다. u144/u149 기존hardgate가우선하며새로운editorial fallback으로해당finding을clear하지않는다. 형제segment는계속게시가능하다. gate실패원문은로그/공개fixture에저장하지않는다.

## B6 사건본문과요약
②owned event block은시점·주체·what·필수fact·why·반응·출처를표시한다. 숫자/표는증거로사용하고변화없는배경을반복하지않는다. ③~⑤는사건별상세반응을추가할수있지만②의필수fact를대체하지않는다. 상단3개TL;DR는첫사건,두번째사건또는확인된시장반응,다음일정/수집한계순서이다. 소스가없는빈칸을비슷한뉴스로채우지않는다. 첫bullet의숫자필수는event-mode에서면제하며FR-009의3bullet/숫자표현보호는유지한다.

## B7 상단배치와기존유닛
u158은내용producer만수정하고u154의블록정렬작업을복제하지않는다. u154미구현상태에서도유효eventconclusion이기존preamble에서보여야한다. u154전후모두동일내용contract를검증한다. 주간COT/월간macro의중복은새발표/해당일큰변화가없으면기존⓪/③~⑤배경1곳으로제한하되required_macro본문의무는유지한다.

## B8 terminal 검증
기존 hard-trust finding은 삭제 전에 보존한다. `_repair_projected_draft` 안에서 event survival → 종속 callout/TL;DR/관전 카드 reconciliation → reindex를 수행한다. 제거된 event ID는 재추가하지 않으며 반복은 최초 selected 수+1회 이내다. 안정화되지 않으면 fail-closed다.

수정이 모두 끝난 뒤 `_collect_terminal_hard_gates`, `_validate_repaired_draft`, `_derive_public_notification_summary`를 읽기 전용으로 실행한다. terminal block의 actor/action/time 표시, required fact 값, 근거 link, meaning/reaction 상태를 검사한다. marker/URL만 남은 사건은 qualified가 아니다. source locator가 제거되면 detail_limited이며 hard source 조작은 삭제로 숨기지 않는다. 검증된 terminal survivor만 seal/DTO에 전달한다.

## B9 뉴스와가격시각
u160이active이면정규실행news_end는run_started_atUTC로고정하고가격target_date는기존해석을유지한다. 가격시각과뉴스관측기간은별도watermark에명시한다. manual target_date는역사재생이며별도명시window없는한해당시장calendar-day뉴스를사용하고live cursor를읽거나수정하지않는다. 주말새사건은당일관측상태로보이며금요일가격반응인것처럼설명하지않는다.

## B10 관전포인트
u162의EventWatchpoint는event_id에일치하는source-backed현재상태와다음확인항목을요구한다. 협상진행·법안표결·서비스launch처럼정성상태를숫자로변환하지않는다. bullish/bearish조건이나매매행동을강제하지않는다. NumericWatchpoint는u152규칙그대로. 숫자row를event로재분류해검증을회피하면거부한다.

## B11 관측/게시 트랜잭션
E11의 단일 PublishReceipt/원격 확인 계약을 따른다. pre-commit snapshot 복원과 post-commit pending 보존·reconcile을 구분한다. 사건 receipt와 window cursor는 동일 archive publication에 속한다. u160 cursor는 active이며 실제 소비된 window의 sealed receipt가 있고 source coverage가 full일 때만 전진한다. off/shadow/replay/dry-run은 생산 cursor write 0회다. notifier-only 실패는 이미 remote-confirmed된 상태를 되돌리지 않는다.

## B12 평가와운영전환
단위helper통과만으로완료아님. 수집후보→Stage1fixture→Stage2fixture→실제u144→sealedHTML/notification을끝까지검증한다. runtime구조검사와오프라인의미평가를구분한다. source후보가빈경우,모든source가실패한경우,수집한것중중요사건이없는경우를별도표시한다. 최종 활성화에는 v2 preview 평가 통과와 실제 shadow 비간섭 증거가 필요하다.
