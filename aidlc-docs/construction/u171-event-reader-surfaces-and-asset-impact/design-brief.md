# u171 Functional / NFR Design: 독자 표면과 사건별 자산 영향

**Date**: 2026-10-10. **Status**: 설계 작성; 구현 미착수. **Dependencies**: u169 sealed view, u170 story projection.

## 목표와 현재 문제

현재 notifier/summary.py는 sealed conclusion 한 줄과 watchlist 가격을 사용한다. optional events DTO가 존재해도 여러 사건을 전달하는 layout은 별도다. 홈·회고·OG는 기존 callout을 추출하고 일부 시각/관심자산은 Briefing의 free section에 의존한다. v3의 실제 사건·상태·새 변화가 모든 표면에서 같은 원본으로 전달돼야 한다.

## 소유권과 기존 기능

u169가 `models/event_document.py::PublicEditionView`, `models/public_notification.py::EventNotificationSummaryV3`, `models/event_asset_impact.py::EventAssetImpact`를 선언하고 terminal publisher가 최종 projection을 만든다. u171은 봉인 전 asset matcher·EventVisualInput 기반 E1 staging과 봉인 후 표면 formatting을 소유한다. notifier는 generated article이나 source를 다시 읽어 사실을 작성하지 않는다.

기존 u156 예약 Telegram 소유권을 존중한다. 구현 시 current ref를 확인하고 동일 notifier owner에서 v3 event formatting을 통합한다. 별도 bot/dispatcher/retry engine을 만들지 않는다. u154의 뉴스 앞/접힌 가격 자료 구현이 통합돼 있으면 공통 primitive를 재사용하지만 v3에 정확히3요약·anchor-first·7H2 요구를 재도입하지 않는다.

관심자산은 u64/u111의 entity/relevance engine을 재사용한다. u169가 선언한 `EventAssetImpact(event_id,asset_id,relation,mechanism,condition,fact_ids,source_refs)`가 v3의 source-backed 연결을 표현한다. relation은 direct/related/uncertain/rejected이며 공개에는 검증된 direct/related만 쓴다. matcher는 봉인 전에 draft에 typed 입력을 제공하고 finalizer가 소유권과 survivor 일치를 검증한다. price item 또는 ticker 동시 등장만으로 사건 영향 판정을 만들지 않는다. 관련 조건이 없다면 uncertain으로 남긴다.

## 표면별 고정 계약

| 표면 | v3 내용과 책임 |
|---|---|
| 웹 본문 | u169의 기본 순서. 관련 자산·시각은 사건 뒤의 보조 내용. 기본hero없음 |
| Telegram | terminal 사건 digest 최대3개와 링크·시장/가격일·뉴스창 안내. 관심자산 영향은 해당 event 연결이 있을 때만 간결하게 부착 |
| 홈·시장 index | 최상위 terminal digest 또는 해당 availability를 표시. 오래된 가격/callout을 새 사건 요약으로 추론하지 않음 |
| 주간/월간 회고 | 같은 event/story의 verified delta를 묶고 원문 archive 링크를 유지. 일간 내용 그대로 반복하거나 삭제 사건 재등장 금지 |
| OG/visual | 본문 visual은 EventVisualInput으로 E1 stage·used-only seal. OG는 sealed 공개 필드에서 기존 post-seal transaction artifact로 결정론적 생성 |
| 관심자산 일간/index | 어떤 사건이 어떻게 관련되는지, 확인된 사실과 조건을 제공. 가격확인과 뉴스영향을 구별 |

모든 표면은 유효 digest, 없으면 동일 terminal event의 검증된 headline, 사건 0건일 때만 availability를 사용한다. 표현 때문에 digest만 제외된 날을 사건 없음으로 표시하지 않는다. 가격 기준일과 뉴스창은 봉인된 필드에서 읽고 target_date로 달력 추론하지 않는다.

Telegram 최종 text는4096 UTF-16 units다. 필수시장/부분발행상태·상세링크·면책을먼저예약하고, ordered whole-event digest를순서대로추가한다. 여유가없으면후순위digest전체를제외하며문장중간을자르거나숫자/이름일부를삭제하지않는다. 뉴스가0건인경우해당availability를표시하고본문을LLM으로다시요약하지않는다. 기존이미지전송·operator채널분리·retrybudget을유지한다.

EventVisualInput의 선언은 u169가 소유한다. u171은 본문 supplement의 E1 preparation을 확장하고 삭제 사건의 자산을 제외한다. 본문 seal 후 caption·asset·Markdown 재작성은 없다. OG는 현재 publish stage에서 sealed view를 소비하는 별도 reader-page artifact다. 기존 write_og_card의 순서와 transaction rollback을 유지하고 새 LLM·외부 요청·사실 추가 없이 생성한다.

## Historical compatibility와 폐기

v3 live surface는 PublicEditionView를 사용한다. v3의 과거 기록은 C5a의 sidecar/hash를 publisher/event_archive_reader.py에서 검증해 복원한다. 없거나 불일치하면 사건 요약을 제외하고 원문 링크·제한을 표시한다. 회고는 발행 당시 상태와 최신 ledger 상태를 구별한다. immutable v1/v2 archive의 callout/7heading parser는 `LegacyArchiveReader`로 구분한 read-only 경로에만 남는다. u172 cleanup 이후 default runtime의 generated Briefing.free sections를 읽는 fallback은 제거한다. 과거 URL과 이미지 provenance는 보존한다.

소비자 목록은 notifier/summary.py, publisher/site_index/, weekly_digest.py, monthly_index.py, watchlist 영향 renderer, visuals/assets.py/og_card.py/image_selection.py와 현재 grep으로 발견한 추가 consumer를 포함한다. 공유 boundary는 models이며 publisher→visuals/notifier sibling import를 추가하지 않는다.

## NFR와 수용

새 HTTP/LLM단계/secret0, post-seal rewrite0, 기존assetmanifest/used-onlypromotion/transaction원자성을유지한다. 같은finalizedview로웹/알림/홈/회고/OG/관심자산의eventID와상태가일치하는integrationfixture를검증한다. 모바일390×844와desktop1440×900에서첫화면이사건요약을전달하는지실제render로확인하고부재를합격으로기록하지않는다. 세부AC는[계획](../plans/u171-event-reader-surfaces-and-asset-impact-code-generation-plan.md).
