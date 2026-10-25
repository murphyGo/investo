# u180 Business rules

작성일: 2026-10-12 · u180 · 상태: 사용자 “유닛 하나씩 진행시켜” 지시로 설계 채택, 로컬 구현·검증 진행. 공개/운영 활성화는 pending.

- R180.1: source-specific 원 응답은 sources 에서만 해석한다. envelope 를 public serialization 이나 LLM prompt 에 포함하지 않는다. 기본 모델/serializer bytes 를 보존한다.
- R180.2: capture 위치는 collector 종료 직후이며 synthetic clock 를 source time 으로 만들지 않는다. empty collect 에도 source outcome 을 보존하되 기존 EmptyCollectError 의 시황 의미는 바꾸지 않는다.
- R180.3: display/retention 범위와 카드 의미가 검증되어야 available 이다. source ok·free access 만으로 허가하지 않는다. permission revoked 시 last-good 와 history 에도 적용한다.
- R180.4: module/current/history/index 와 manifest hash 를 함께 게시한다. pending/unknown receipt·로컬 git 성공만으로 이력을 진전시키지 않는다.
- R180.5: baseline metadata_paths 는 insights manifest 만 포함한다. 기존 source specs, sector pair, event/story/news metadata 와 archive bytes 를 보존한다.
- R180.6: JSON/Decimal·metric/events·clock·payload cap 은 C1–C5 로 검증한다. naive timestamp/NaN/bool/owner mismatch 는 해당 관찰을 차단한다.
- R180.7: same run 에서 capture/prepare/publication 순서를 고정하고 추가 source HTTP/LLM 호출 0. private runtime hook 은 opt-in 이며 defaults 와 source budgets 를 증가시키지 않는다. dry-run/선언된 replay 는 공개 write0.
- R180.8: 새 코드의 예상 오류만 module/dashboard 로 격리하고 unexpected bug 는 기존 error owner 로 전달한다. silent success0.

[공통 C1–C7](../../public-insights-20261012/contracts.md)이 숫자·시간·권리·상태·보관·게시의 기본 계약이다. 여기서 정의한 source/metric/event 의미를 다른 module 에서 재정의하지 않는다. 충돌하는 raw metadata 는 검증 실패이며 임의 보정을 하지 않는다.
