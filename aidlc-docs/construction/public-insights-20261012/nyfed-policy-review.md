# NY Fed Stage2 policy independent review

작성일: 2026-10-26 KST. 별도 reviewer. 검토 범위의 확정 미해결 **Critical 0 / High 0 / Medium 0**.

## 정확한 검토 범위

WT `public-insights-nyfed-policy-20261026`의 `e6ede833b0b471c0748dac5f69f6278db2039024` → `7470923e83d3d321138cef3be03780fb458fbae2`를 검토했다. 로컬 준비 상태부터 읽었고, lead가 커밋한 뒤 같은 content/hash와3개 변경 파일을 다시 대조했다.

- NY Fed3 definition의 display_allowed/public_git_history_allowed/retention_allowed 아홉 boolean만 false→true.
- macro default qualification 회귀를12허용/FRED차단·필수 고지 보존으로 갱신.
- qualification decision 문서 추가.

code-review의 correctness/security/data-integrity/error-contract 관점으로 policy·loader·parent rights/retention·current/history/renderer/notice 전달 경계를 대조했다. source/parser/정의/계산/endpoint/routing/HTTP·application 코드 변경은 이 delta에 없다. reviewer는 추가 network를 사용하지 않았으며 source/test·Git index·commit·deployment를 수정하지 않았다.

## 변경 범위와 rights 계약

baseline JSON과 현재 JSON을 definition별 대조하여 **변경3개/permission9개/나머지43개 definition 객체 전체 동일**을 직접 확인했다. 대상 public ID는 sofr/effr/sofr_effr_bp뿐이고, notice/checked date/runtime probe/evidence href/endpoint/field scope/methodology는 Stage1과 같다. 다른 source에 NY Fed 허용을 상속하지 않는다. 결과는 기존24허용+NY Fed3=27허용이며19보류가 유지된다.

Stage1에서 검토한 source-specific 조건과924자 attribution/NOTICE/software MIT 구분을 그대로 소비한다. current display뿐 아니라 공개 Git 영구 이력 허용과 rolling analytics history를 각각 명시적으로 여는 변경이다. 이를 무조건적·철회 불가능한 권리로 해석하지 않으며, 다른 source의 차단을 해제하지 않는다. 이번 리뷰에서 원천 약관을 다시 네트워크 조회하거나 FRED/crypto 보류 조건을 재판정하지 않았다.

SOFR/EFFR 동일일 관측으로 계산하는 spread는 두 부모의 semantic/권리 gate를 통과해야 한다. reviewer가 실제 Stage2 policy를 사용해 다음을 직접 실행했다.

- SOFR 권리 철회: SOFR 및 spread가 current와 history에서 제거되고 EFFR은 유지됨.
- SOFR rolling retention만 철회: SOFR/spread current는 유지하지만 두 history chain은 제거되고 EFFR history는 유지됨.

이 확인은 in-memory synthetic 관측이며 실제 공개 데이터를 쓰지 않았다. 고지는 JSON의 current metric/history definition에 보존되고, Stage1 renderer의 그룹별 값 이전 notice·자체 spread/5영업일 계산 표시 및 source-condition 링크를 재사용한다.

## application SHA와 policy hash의 분리

bounded runtime `873cea37c878da3f9363d2457aa2a4c5a01db3fb`의 Git blob에서 loader의 기본 경로가 상대 `ops/insights_source_qualification.json`이고, phase가 별도 override 없이 이 loader를 호출함을 직접 읽었다. runtime workflow의 working directory 계약인 public-data cwd policy를 읽으며 runtime-code checkout의 bundled policy가 authoritative하다고 가정하지 않는다.

같은 imported loader 코드로 임시 cwd에 Stage1 policy를 놓으면 NY Fed 허용0개, Stage2 cwd에서는3개가 됨을 실행 확인했다. 따라서 실제 실행 code SHA와 current public-data policy commit/hash가 독립된 검토 증거여야 한다.

Stage1 bounded runtime과 public e6ede833의 macro renderer/README/NOTICE Git diff가 없음을 확인했다. 아래 Stage2 정책 바이트 hash는 이번 검토의 고정 기준이다.

```text
qualification SHA256:
2ac7295452d2fdc5f5c86af850d667f363bfd0a16537950e1dbe98988c7e28f5
```

## reviewer 직접 실행한 회귀

변경 WT source를 사용하도록 PYTHONPATH=src:.를 지정하고 기존 설치된 통합 venv interpreter를 사용했다.

```text
PYTHONPATH=src:. /Users/user/Desktop/Projects/investo/.tmp/public-insights-main-integration-20261025/.venv/bin/python -m pytest tests/unit/orchestrator/test_macro_insights_projection_u181.py tests/unit/publisher/test_macro_insights_render_u181.py tests/unit/sources/test_macro_insights_envelopes_u181.py tests/unit/sources/test_nyfed_reference_rates.py -q
35 passed in 1.54s
```

해당4개 파일은 positive12/current/history/parent permission/정확 계산/고지·escape/byte cap·기존 source parity 회귀를 포함한다. 별도 JSON delta 검증·cwd loader seam·두 parent 철회 seam 및 `git diff --check e6ede833..7470923e`도 통과했다.

lead가 제공한 bounded runtime import 조합88개 및 최신 main 조합88개 결과는 reviewer의 직접 실행과 구별한다. program의 실제14HTTP200+12 projection metadata는 읽었으며 개발 조회/임시 in-memory qualification라는 kind와 public write0 표기를 확인했다. 새로운 live source 요청은 하지 않았다.

## 전달 및 운영 수용 경계

Stage2 branch의 Quality CI는 main의 public-data policy를 바꾸지 않는 검증 단계다. production 정책을 main으로 전달하기 전 아래 조건은 별도 exact-SHA 증거로 확인해야 한다.

1. public Stage1 e6ede833 및 bounded runtime873cea37의 CI 성공.
2. private REVIEWED_CODE_SHA가873cea37로 승격되고 실제 checkout/execution pin이 읽기 검증됨. 기존/queued owner가 이전 package로 새 policy를 읽지 않는지도 확인.
3. 그 뒤 Stage2 main policy의 commit/hash가 위 검토 범위와 일치하고 NY Fed3개의 아홉 flag 외 변경이 없음.
4. macro-only publication의 remote-confirmed receipt, JSON/HTML/history/NOTICE 및 실제 Pages/HTTPS identity를 대조. calendar/crypto와 다른 activation gates는 보존.

이번 로컬 code review는 위 CI/pin/원격 전달이 완료됐다는 판정이 아니다. reviewer는 push/활성화/추가 network를 수행하지 않았다. 수동 source probe·CI·게시를 genuine scheduled로 합산하지 않으며 관찰0/5 경계를 유지한다.
