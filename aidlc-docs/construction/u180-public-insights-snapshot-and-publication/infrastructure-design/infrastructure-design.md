# u180 Focused infrastructure integration design

작성일 2026-10-12. 사용자 후속 진행 지시로 설계 채택; 로컬 template/output 구현 및 검증. 기존 private collector/Pages 에 대한 설계이며 새 runtime/workflow 의 생성·배포 기록이 아니다.

## 적용 대상

현재 public application source 의 `src/investo/__main__.py`, `models/results.py`, `orchestrator/pipeline.py`, 기존 배포용 `ops/private-runtime/production-briefing.yml`만 확장한다. public `.github/workflows/pages.yml`은 기존 static build 를 재사용한다. 새 source HTTP job·scheduler·environment·token·database 가 없다. 현재 source FRED_API_KEY 경로를 재사용하며 값을 공개 출력에 넣지 않는다.

## 결과 신호

1. collector 종료 후 opt-in dashboard prepare/publication 을 수행하고 InsightRunOutcome 을 stage accumulated output 에 보존한다. 이후 generation early-return/실패에도 결과를 PipelineResult.insights 에 결속한다.
2. legacy publication_committed 와 published_segments/exit0/1/2 는 briefing 의미를 보존한다. __main__ GHA output 의 insights_publication_committed 는 remote_confirmed receipt 가 있을 때만 true 이고 insights_published_sha 는 해당 receipt.local_sha 다. mode off 에는 optional output 를 생략한다.
3. 기존 workflow 는 pipeline_rc 를 저장한 뒤 shell step 에서 exit0 하고 Pages 이후에 원 종료코드를 재발급한다. 이 구조를 유지하고 Pages 조건에 insights_publication_committed 를 OR 한다. pending/unknown/preview/dry-run/replay 는 false 다.
4. Pages target 은 briefing 게시가 있을 때 기존 published_sha, briefing 게시가 없으면 insights_published_sha 를 쓴다. local HEAD/미확인 push/dirty working tree 를 insights 확정 SHA 로 쓰지 않는다. event+insights 둘 다 게시된 경우 최신 확인한 descendant public HEAD 의 deploy 를 확인한다.
5. 기존 같은 SHA Pages 탐지·필요시 dispatch·225 분 work allowance·private/public token 분리와 source/Telegramkey 격리를보존한다. 데이터게시와 Pages 실패를별도기록한다.

## 모드와 활성화

INVESTO_INSIGHTS_MODE 기본 off, MODULES 기본 macro. shadow/public write0. mode/modules 읽기는 reviewed private runtime 의 input/변수에서만 수행하며 코드 pin 승격·변수설정·실제발행은후속운영요청범위다. u181macro→u182calendar→u183verifiedcrypto 순서만 권장한다. 배포조건미충족카드를활성화하지않는다.

## 추가 검증

modeoff output/template parity, generation 실패+dashboard 확정+Pages 필요신호, unknownpushfalse, 모듈중일부실패, publicHEAD 동시진전, Pages 실패+기존 exitcode 재발급, expired allowance, dryrun/replaywrite0 를 fixtures 로검증한다. actionlint 와 기존 private-runtime CI checks 를실행한다. 이문서로현재배포 pin 이나 secret 을변경하지않았다.
