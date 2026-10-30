# 검증 기록

작업 사본: `/private/tmp/investo-data-priorities-20261030`, base `b121ca01f6eb23246d2f7e4593f509221b5827ff`. 공유 root의 기존 변경은 포함하지 않고 이 사본에서 검증했다.

- Python 3.11.9 (운영 minor 대응), root의 동일 pinned dependency 환경, Cairo/Node 경로 명시.
- 전체 pytest: **7,653 passed, 1 known skip, 780.97s**. 기존 dataset migration skip 한 건이며 새 skip은 없다.
- 전체 실행 이후 수능일 제외 및 non-UTC cutoff 정규화를 보완했다. 수능 보완 후 관련 **85 passed**, 최종 UTC/aggregator/생성 패널 교체 보완 후 신규 source/integration **43 passed**.
- Ruff 전체 check / format: 통과. Mypy: **363 source files** 통과. `git diff --check`: 통과.
- Node client tests: **39/39** 통과.
- Anthropic SDK, paid API, curated assets, image store, Material theme, calendar render guards: 통과.
- MkDocs `build --strict`: 통과(5.07s).
- 실제 Coin Metrics read-only 조회: BTC/ETH × 활성 주소/거래 건수 = 4행, 직전 7일 비교 가능. 원천의 검토 상태와 수정시각은 미제공으로 표시. [기록](live-check.json).
- 전체 회귀 이후 작은 경계 보완에는 영향 받는 source/model/발행 테스트를 재실행했다. 전체 회귀를 최종 보완 뒤 다시 돌렸다고 주장하지 않는다.

검증 범위: 숫자 문자열 경계, 부분 결측, 비연속 비교구간, 중복 충돌, 16행/64KiB, 잘못된 UTC/미완료·오래된 일자, HTTP 실패 분류, activity 실패 시 flow 보존, 주어진 cutoff의 UTC 정규화, 정확한 source 행만 numeric masking, 정상/변조 USD 검증, source가 생성 패널 값을 교체, crypto 전용 표시, KRX 월물 중복 배제·휴장 양방향·연말·전체 2026 일별 조회·수능일 제외·최대2개 우선 선택.

기존 운영 runtime pin, schema/profile, workflow, cron, 소스별 대시보드 공개·보존 권한은 이번 실행에서 변경하지 않았다. 실제 게시/메시지 발송/배포 완료를 검증 결과로 주장하지 않는다.

## Integrated workspace validation

All 27 owned integration targets matched their captured root baseline and the isolated clone base before copying. Root source/plugin/lifecycle/native/legacy/public-document tests: **163 passed (1.90s)**. Root-wide Ruff check/format (858 files) and mypy (363 source files) passed. [Independent review](review.md): Pass with 43 tests independently executed. Existing HEAD, index and unrelated dirty work were preserved.
