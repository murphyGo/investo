# u180 observation metadata capture independent review

작성일: 2026-10-25. 별도 reviewer. 현재 검토 범위의 확정 미해결 **Critical 0 / High 0 / Medium 0**.

## 범위와 기준

dev-investo Step5.1/code-review 및 security-boundary, data-integrity, error-contract, resource-lifecycle, concurrency, memory/performance protocol 관점으로 검토했다. 기준은 observation-capture-plan.md, 기존 C1–C7/u155/R13와 actual source·delivery·scheduled acceptance를 구별하는 계약이다.

- public WT: `public-insights-data-init-20261025`, base0b3780e5의 production template·u155 test exception·신규 observation test.
- private WT: `public-insights-runtime-20261025`, baseb58c7f9의 실제 daily workflow diff.
- 애플리케이션 pin0025497d의 제품 코드를 다시 전수 검토하거나 변경하지 않았다. 현재 단계는 genuine scheduled0/5를 위한 증거 수집 준비이며 수용 완료가 아니다.

public/private diff가 Ensure Pages의 step id 추가 및 observation capture/upload 두 단계에 한정되고 기존 cron/private owner/main/enabled gate, auth/queue:max, pipeline/Pages allowance, 최종 exit 재발급을 바꾸지 않음을 확인했다.

## 확인 결과

### 권한·privacy

관찰 코드는 isolated Python의 stdlib와 local Git만 사용한다. Git command는 list args이며 고정 workspace checkout, 검증된 SHA 및 closed module의 고정 blob 경로를 읽는다. 원천 HTTP·LLM·Telegram·remote Git fetch/push·추가 secret 접근은 없다. capture step env는 mode/modules와 기존 step outputs뿐이고 secrets expression을 추가하지 않는다.

report는 run/attempt/event, 실제 runtime-code HEAD와 expected pin 일치, private workflow SHA, 고정 enum 상태, module clock/count/hash만 직접 구성한다. 원문·model output·raw metadata·환경 전체·exception 내용을 복사하지 않는다. invalid evidence는 고정 unavailable report로 축소한다. SHA/identifier/clock 검증과 duplicate/nonfinite JSON 거부, blob256KiB/report16KiB 상한을 확인했다. source time 목록도 원문 대신 hash로만 저장한다.

tempfile.mkdtemp의0700 directory와 O_EXCL0600 observation.json 한 파일만 artifact_path로 전달한다. 업로드는 해당 단일 파일 경로, include-hidden-files=false, retention7일이며 glob/auth cache/통째 workspace 예외를 열지 않는다. private job owner guard와 private artifact가 그대로 유지된다. canary를 환경 및 fake provider body에 넣어도 보고서에 포함되지 않는 회귀를 직접 실행했다.

### truth·identity

실제 runtime-code Git HEAD가 REVIEWED_CODE_SHA와 같아야 하며, 단순 설정값을 execution SHA로 복사하지 않는다. confirmed step output이 true이고 mode가 active일 때만 고정 published SHA의 manifest/current blobs를 읽는다. current hash·canonical snapshot identity·schema/module·clock 순서·개수 상한을 대조한다. unconfirmed/invalid/old module/manual/retry 조건의 negative를 실행했다.

**scheduled_candidate는 수용 판정이 아니다.** schedule/attempt1과 현재 run의 collection clock을 만족한 검토 후보만 표시하고 acceptance는 pending_source_receipt_and_pages_review로 유지한다. source 성공/권리·remote ancestry/실제 receipt·Pages 배포 snapshot 및 run conclusion을 이 코드가 독립 인증하거나5회로 자동 합산하지 않는다. Pages ensure의 outcome은 dispatch/확인 단계 결과이며 실제 배포 완료와 구별해야 한다.

index_hash/history_hash는 검증된 manifest에서 읽은 선언값이다. 관찰 코드는 current bytes를 재해시하고 index/history bytes를 독립 재해시하지 않는다. 이 범위를 별도 reviewer의 전달·Pages/receipt 대조와 구별해야 한다. 따라서 artifact 자체를 전체 bundle의 독립 readback 성공 또는 source 수용 완료로 기록해서는 안 된다. 현재 계획의 candidate/후속 대조 계약과 일치하는 범위다.

### 예산·실패·exit code

225분 work allowance에서75초 이상 남은 경우만 시작한다. Git call은 10초 monotonic deadline의 남은 시간과 각3초 timeout 중 작은 값을 사용한다. capture 완료 후 deadline 및 잔여65초를 다시 확인하고, 파일 작성 후 artifact_path emit 전에도 잔여65초를 확인한다. 부족하면 upload를 열지 않는다. upload step은1분이며, capture/upload 모두 continue-on-error이고 마지막 always() exit step이 원래0/1/2를 그대로 재발급한다.

새 observer가 실패하거나 생략되면 observation 증거가 없거나 unavailable일 뿐, 기존 정상 시황 상태를 실패로 바꾸거나 기존 실패를 성공으로 바꾸지 않는다. 단일 run의 bounded temp metadata는 runner 수명과 private artifact7일 보존에 한정한다.

## reviewer 직접 실행한 검증

새 WT에 venv가 없어 기존 통합 WT의 설치된 interpreter를 사용했다. 테스트는 새 public WT의 실제 변경 파일을 대상으로 실행했다.

```text
/Users/user/Desktop/Projects/investo/.tmp/public-insights-main-integration-20261025/.venv/bin/python -m pytest tests/unit/orchestrator/test_insights_observation_u180.py tests/unit/orchestrator/test_private_publication_u155.py -q
41 passed in 16.64s
```

해당 실행에는 local Git 정상/invalid identity·hash/snapshot/duplicate/nonfinite/cap·manual/retry/old snapshot·canary·0700/0600·allowance skip 및 기존0/1/2 exit 재발급이 포함된다. 실제 GitHub artifact 업로드나 scheduled 실행을 한 것은 아니다.

추가로 inline observer를 추출해 capture 이후 monotonic deadline 초과 및 wall-clock 잔여 reserve 부족을 각각 주입했다. 두 경우 모두 artifact_path를 만들기 전에 다음 결과로 종료함을 직접 확인했다.

```text
deadline [('capture_status', 'skipped_allowance')]
reserve  [('capture_status', 'skipped_allowance')]
```

public/private capture step 및 upload step의 파싱된 전체 설정을 비교해 동일함을 확인했다. capture run block SHA256은 양쪽 모두 다음과 같다.

```text
00cd3f5d266535bb905cb3123b7ed532c3a1ca7fa0ead541750642f626f23662
```

diff --check도 통과했다. lead가 제공한 Ruff/format/bash-n·focused 로그와 원격 적용/CI 결과는 reviewer의 직접 실행과 구분한다.

## 적용 이후 수용 경계

이 검토는 로컬 workflow 수정의 code review다. 원격 private workflow 적용·앱 pin 보존 readback·실제 private artifact 접근/retention·실제 scheduled run/event/attempt·remote receipt·Pages identity는 적용 후 별도로 확인해야 한다. 현재0/5를 증가시키거나 미래 cron의 run ID/성공을 생성하지 않았다. reviewer는 소스/테스트 수정·commit/push·workflow dispatch·실운영 변수/배포 변경 없이 이 보고서만 작성했다.
