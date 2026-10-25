# u181 매크로 환경판 구현

2026-10-25 · 격리 branch `codex/public-insights-unit-design-20261012` · 로컬 구현·검증 **7/8**, 운영 Step 8 대기.

사용자 “진행시켜” 지시로 기존 u181 설계를 채택하고 u180 위에 매크로 화면을 구현했다. 기본 모드는 `off`이며 commit/push·실서비스 배포·private pin/mode 변경은 수행하지 않았다.

## 화면과 데이터

- 미 국채 3M/2Y/10Y/30Y, 두 국채 금리차, SOFR/EFFR와 금리차, H.10 원달러, CPI/근원 CPI 계절조정 지수, 실업률의 **13개 슬롯**을 제공한다.
- 기존 네 어댑터의 응답에서만 private envelope를 만든다. source request·registry·key 경로와 기존 item JSON bytes를 유지한다. Treasury XML과 NY Fed JSON의 원래 Decimal 자릿수를 보존한다.
- 같은 원천·같은 유효일의 값으로만 금리차를 계산한다. source와 binder가 precision256의 같은 산식을 쓰며 범위를 넘는 파생값은 해당 카드만 제외한다. 부모 권한 철회는 파생값의 last-good·이력에도 적용한다.
- 월간 실제값은 대상 월과 계절조정을 표시한다. 다음 공식 발표일이 없으면 “최신 여부 미확인”이며 이력을 진전시키지 않는다. 원천 시각 자체를 알 수 없는 값·미래 clock·미지원 연도의 새 값은 계속 억제한다.
- 첫 발행부터 현재 값만으로 볼 수 있다. 정확히 5원천 영업일 전의 호환 이력과 현재 관측이 있을 때만 변화를 표시하며, 수정되거나 빠진 관측을 채우지 않는다.
- 국채 네 만기의 SVG와 동일 값의 표, 모바일 주요 4카드 2열, 좁은 확대 화면의 1열, 기존 테마·키보드를 제공한다. 관련 시황 날짜는 원격 확정 Git tree에 실제 있는 문서에서만 고른다.
- 이력은 사용자 선택 후 same-origin manifest/snapshot/current hash/history SHA256을 확인하고 최대 30개 관측을 표와 SVG로 보여준다. 검증 실패 시 현재 카드를 보존한다. JavaScript 없이 현재 카드·만기표·출처·이력 JSON 링크를 사용할 수 있다.
- 대시보드 모음과 메뉴를 추가하고 기존 `미국 섹터` 이름 및 `/sectors/` 경로를 유지했다. 일정·크립토의 미구현 화면 링크는 추가하지 않았다.

## 검증과 범위

현재 수집되는 전체 **7,046개 테스트**를 네 파일 shard, 실패 shard 수정 재실행, 최종 scoped 회귀로 대조했다. 중복 node를 제거한 결과 **7,045 passed / 1 known skipped**, 누락·미해결 실패 0이다. 최종 scoped suite는 112 passed다. 처음 발견한 메뉴명 회귀와 수정 시점도 [validation](validation.json)에 구별한다.

독립 리뷰에서 부모 권한의 last-good 전파, 파생 계산 범위/정밀도, 이력 지연 로드 문제를 수정했다. reviewer 직접 29 tests를 확인했고 최종 미해결 Critical/High/Medium은 0이다. [초기 리뷰](review-u181-initial.md), [최종 재검토](review-u181-final.md).

실제 임시 Chromium154에서 390×844/1440×900, light/dark, JS 유무, 100%/200% 상당 확대의 16조합을 렌더했다. 200%는 절반 CSS viewport와 DPR2로 구현한 등가 확대다. 가로 넘침, 새 페이지 오류, 사용자 선택 전 이력 요청이 없음을 확인했다. 테마 전환 완료 후 메뉴·카드 제목·관측일의 텍스트 대비 4.5:1 이상도 검사했다. 키보드·실제 테마 전환·메뉴 재진입·기존 섹터 URL, 이력의 hash/snapshot 불일치 차단도 확인했다. [화면 증거](browser-evidence.json), [재현 코드](../../../../tests/browser/macro_insights.cjs).

Browser connector는 설치된 경로와 도구 내부 경로의 불일치로 실행되지 않았다. 사용자의 브라우저를 제어하거나 u145 waiver를 승계하지 않고, 별도의 임시 headless Chromium에서 검증했다. source/API 실제 응답, 합성 fixture와 UI, 로컬 Git 게시, production 수용은 서로 다른 증거다.

Ruff/format 763 files, mypy 322 source files, 정책 guards, strict MkDocs/Material/Calendar, 자원 상한 시험을 확인했다. 상세 결과와 수정 입력 fingerprint는 [validation](validation.json), [resource](resource-evidence.json), [AC 대조](../../../../docs/cross-checks/2026-10-25-u181-macro-environment-dashboard.md)에 기록한다.

## 공개 자격과 운영 대기

현재 qualification은 13개 정의 중 Treasury/BLS 9개를 근거 확인 범위에 허용한다. NY Fed 3개는 재배포 고지 조건 충족 전, FRED 1개는 사용 조건 해석 전 기본 차단한다. 이는 collector 등록이나 runtime 활성화가 아니다. [소스 기록](source-qualification.md).

개발 조회에서 Treasury XML을 실제 읽어 2026-10-23 자료의 typed 지표 6개를 확인했다. SOFR endpoint는 HTTP200, BLS CPI endpoint는 HTTP503이었다. BLS의 현재 정상 수집·나머지 endpoint 접근을 이 결과로 주장하지 않는다. FRED key 조회·API 호출은 하지 않았다. [개발 원천 증거](source-probes.json).

운영 Step 8의 최신 main 통합/정확한 implementation SHA, 남은 source 조건, reviewed private pin/mode, 실제 Pages·5회 예약 관찰은 대기다. 현재 작업의 base는 `55c00fc8`이며 시작 시 원격 `dd113ae4`의 별도 v3 변경을 확인했다. 원격 최신판에 통합·푸시했다고 표시하지 않는다. 다음 코드 대상은 **u182 주요 일정**이다.
