# u182 주요 일정 구현

2026-10-25 · 격리 branch `codex/public-insights-unit-design-20261012` · 로컬 구현·검증 6/7, 운영 Step7 별도.

사용자 후속 “진행시켜” 지시로 기존 FD/NFR/code plan을 채택해 u180/u181 기반 위에 주요 일정 화면을 구현했다. 기본 modeoff, commit/push·실제 배포·private pin/mode 변경은 수행하지 않았다.

## 제공 동작

- 경제지표/중앙은행/국채 입찰, 기본7일·선택30일, 최대128개를 제공한다. 초과분을 날짜·kind·source identity로 결정적으로 선택하고 제외 건수를 표시한다.
- 기존 네 어댑터 응답의 opt-in envelope만 사용한다. source HTTP·query/key·routing/registry·legacy JSON bytes와 기존 lookahead/cap를 유지한다. 원천이 방출하지 않은 행을 추가하지 않는다.
- Fed의 days 전체가 파싱될 때만 날짜/range를 보존한다. 회의·성명·기자회견·의사록을 구별한다. 같은 발표자·같은 날 두 연설은 원천 time/location/description의 정규화 hash로 구별하며 정확한 공개 시각으로 승격하지 않는다.
- BEA의 명시된 Year와 유효 ET 시각만 zoneinfo로 KST 변환한다. 날짜-only는 미국 동부 현지 날짜·시간 미정으로 표시하며 synthetic UTC00:00을 KST09:00 일정으로 만들지 않는다. 명시된 월/분기만 대상 기간으로 쓰며 FRED의 기존 추정 기간은 전달하지 않는다.
- 확인된 동일 family/kind/현지 날짜·range/period가 일치할 때만 BEA-FRED 원천 참조를 묶는다. 서로 다른 원천의 유사 제목은 병합하지 않는다. 중복된 동일 identity의 상충은 제외·집계한다.
- 실패·0건·건너뜀에서 자격 있는 이전 일정만 원래 수집 시각으로 유지한다. 권한 철회는 primary·병합 참조와 비활성 모듈 정리에도 적용한다. 일정 경과·목록 누락으로 actual/발표 완료/취소를 단정하지 않는다.
- 각 카드의 날짜 기준·고정 확인 가이드·원천 링크·수집 시각, 원천별 상태/조회 상한/미확인 범위를 제공한다. Calendar 분석 이력은 생성하지 않는다.
- noJS는30일 전체 목록과 앵커, JS는 native button 기반7/30일·분류 필터를 제공한다. 필터는 DOM만 사용하며 추가 fetch0, 메뉴 재진입 시 한 번 초기화한다. 기존 macro/미국 섹터 URL과 테마를 유지한다.

## 검증

현재 수집되는 전체7,092개 테스트를 네 full shard와 최종 focused 회귀의 node별 최신 결과로 대조해 **7,091 passed / 기존1 skipped**, 누락·미해결 실패0을 확인했다. full checkpoint는7,091개(7,090pass/1skip), Fed 수정 후 최종 focused는236pass/79.00초다. 중복 집계를 하지 않으며 하나의 최종 full 실행이라고 표시하지 않는다. [validation](validation.json)에 시점과 범위를 기록한다. 초기 관련 회귀의 macro qualification 건수13 고정 테스트는 macro 정의만 선택하도록 수정했다. Calendar24개 추가를 기존 macro 권한 변경으로 취급하지 않는다.

독립 리뷰의 Medium1(Fed title-only identity 충돌)을 기존 실제 recording의 두 행사로 재현해 수정했다. 초기 reviewer45 tests와 수정 후 해당 회귀1 test를 별도로 확인했고 최종 미해결 C/H/M0이다. [초기 리뷰](review-u182-initial.md), [최종 재검토](review-u182-final.md).

실제 임시 Chromium154에서390×844/1440×900, light/dark, JS유무, 100%/200% 상당 확대의16조합을 검사했다. 200%는 절반 CSS viewport+DPR2의 등가 확대다. overflow·새 page error·데이터 요청0, 7/30·분류 keyboard Enter·aria-pressed·noJS30·날짜/range/KST·텍스트 대비4.5:1·메뉴 재진입·실제 테마 토글·섹터HTTP200을 확인했다. [화면 증거](browser-evidence.json), [재현 코드](../../../../tests/browser/upcoming_insights.cjs).

Browser connector는 설치 경로 오류로 실행되지 않았다. 별도의 임시 headless profile에서 합성 일정만 검증했으며 사용자의 브라우저/로그인 세션을 제어하거나 u145 waiver를 승계하지 않았다. 소스 실제 응답, 합성 UI, 로컬 Git 원격 확인, production Pages 수용은 별개 증거다.

Ruff/format·mypy·policy·strict MkDocs/Material/Calendar 및 current256KiB/128선택을 검증했다. 합성128개에서 current126,460bytes, HTML81,048bytes(120KiB 이하), 공통insights CSS+calendar JSgzip2,153bytes(15KiB 이하)다. 최대3module 자원시험은 추가RSS43,728,896bytes/CPU2.162초/wall7.846초로 상한을 지켰다. [자원](resource-evidence.json), [요구사항 대조](../../../../docs/cross-checks/2026-10-25-u182-upcoming-events-dashboard.md).

## 원천과 운영 경계

Calendar24 정의 중 Fed/BEA/Treasury14 허용, FRED10 차단을 유지한다. 분석 이력은 보관하지 않는다. 세 공개 endpoint의 개발 조회200과 실제 응답 재생을 기록했고 FRED 키 조회/실제 요청은 하지 않았다. [원천 조건](source-qualification.md), [probe](source-probes.json).

작업 base55c00fc8과 이번 시작 시 origin/main817b356c를 구별한다. 원격의 별도 변경을 통합·푸시한 결과가 아니다. u180/u181 미커밋 변경과 root의 별도 작업을 보존한다.

Step7의 최신 main 통합/정확한 application SHA·source 조건·reviewed private pin/mode·실제 Pages·5회 scheduled 관찰은 pending이다. 신규 ADR/debt로 넘긴 미해결 코드 finding은 없다. 다음 코드 유닛은 **u183 크립토 시장 내부**다.
