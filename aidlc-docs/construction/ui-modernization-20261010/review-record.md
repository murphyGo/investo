# UI 유닛 문서 독립 리뷰 — 2026-10-10

## 범위와 판정

등록 대상은 u174–u179 계획, `aidlc-state.md`의 대응 행, 프로그램 README다. 초안 작성자는 `ui_repair_plans`, `ui_home_shell_plans`, `ui_reader_archive_plans`, 독립 리뷰어는 각각 다른 `ui_repair_review`, `ui_home_review`, `ui_reader_review`다. 최종 통합과 지적의 실제 코드 대조는 루트가 담당했다.

최종 판정: **여섯 유닛 모두 문서 등록 범위 APPROVE**, 잔여 P1/P2 없음. 이는 Functional Design 승인, 코드 구현 허가, 테스트 합격, 브라우저 인수 또는 운영 배포가 아니다. 사용자 요청은 “일단 유닛 문서화”이며 모든 구현 체크박스는 미실행 상태다.

| 리뷰 범위 | 확인한 계약 | 최종 결과 |
|---|---|---|
| u174/u175 | historical archive의 실제-config hook, raw SVG/namespace, u154/u143 보호, directory/flat/prefix URL, 실제 JS 행동, lazy fetch, body/HTML 테마 호환, CI gate | APPROVE; 재검토 후 P1/P2 0 |
| u176/u177 | CSS/renderer 소유권, 미국 섹터 메뉴 보존, SegmentBundleState, canonical 품질 입력, None/empty dict, E5 소비·rollback·partial, 가변 요약/확대/no-JS/focus | APPROVE; 재검토 후 P1/P2 0 |
| u178/u179 | immutable 카드·as-of 미확인, neutral boundary, seal 이전 producer/reader_visible/artifact, SVG fallback, shared scanner, 영구 URL/legacy, historical snippet eligibility, 표준 단계 산출물 | APPROVE; 재검토 후 P1/P2 0 |

## 검증하고 반영한 지적

| 지적 | 실제 근거 | 반영 및 재검토 |
|---|---|---|
| P2: u175의 body 존재/attr 부재일 때 HTML fallback live 전환이 누락됨 | 기존 JS의 html reader/observer와 새 계획의 body-only 관찰이 충돌 | body+html을 한 observer로 관찰하고 같은 reader로 유효 scheme을 재평가. body attr 추가·제거/우선순위와 fetch·객체 재생성 0을 Step/AC에 추가. 해소 확인. |
| P2: u177 홈 품질 모순 AC가 수정 권한에 없는 gate 확장을 요구함 | `quality_consistency.check_quality_consistency`/`validate_date_quality_consistency`는 현재 품질 페이지 입력만 받고 pipeline gate도 홈을 전달하지 않음 | quality_consistency의 홈 comparison과 pipeline의 home read/pass-through만 최소 범위로 명시. optional 기본 None/old caller 호환, 새 홈 필수 입력·누락 실패, pre-git 호출을 FD 결정에 추가. 해소 확인. |
| P3: u177의 “기존 renderer 안전 경로”가 실제 runtime owner를 특정하지 않음 | 현재 hero는 Markdown 출력이며 `_escape_inline`은 newline normalization만 함 | build-time Markdown/plain HTML 선택, 문맥별 escaping·safe href owner와 docs-only Markdown 패키지의 runtime 추가 금지를 FD/계약에 명시. 해소 확인. |
| P2: u179 word-boundary/ellipsis가 기존 sentence-bound owner를 누락함 | `_internal/text.py::bound_at_sentence`, u131/u153 single splitter·decimal-safe·완결 문장 계약 | helper의 `require_complete=True`와 None→날짜 link-only를 재사용. 120자 cap은 FD 후보이며 새 splitter를 만들지 않음. 해소 확인. |
| P2: u179 `_escape_inline`을 HTML escaping 정본으로 잘못 서술함 | 실제 `_blocks.py`는 newline 제거/strip만 수행 | normalization/atomic write 재사용과 `html.escape` text/quote context, 검증된 ArchiveLayout href를 분리. exact helper/type는 FD에 고정. 해소 확인. |
| P2: u178/u179 NFR 두 번째 표준 산출물이 누락됨 | planner/NFR 규칙은 `nfr-requirements.md` + `tech-stack-decisions.md`를 요구 | 표준 두 파일로 복원하고 별도 NFR Design 필요성은 PENDING, 필요 시 추가 문서로 작성. 해소 확인. |
| P2: u179의 legacy sentence bounding이 v3 terminal snippet을 숨기거나 다시 절단할 수 있음 | v3 C4는 headline 최대120자/마침표 의무 없음과 digest 최대140자를 구분하고 C5a/u171이 표면 요약 선택·hash 검증을 소유 | D-179.3/4, Fixed6, Step4/5, AC4를 schema별로 분리. legacy만 기존 sentence helper/projection을 사용하고 v3 exact terminal snippet/제한 상태는 escape/layout만 수행. 마침표 없는 headline과 121–140자 digest 유지 회귀를 명시. 독립 재검토에서 해소 확인. |

리뷰 지적은 모두 실제 코드/워크플로우와 대조한 후 반영했다. 미결 UI 선호, 아직 작성되지 않은 FD 자체, historical finalized eligibility 미확인 상태를 결함 또는 승인으로 바꾸지 않았다.

## 원격 동시 등록과 최종 통합 리뷰

초기 코드·기획 기준은 `48762793`이었다. 문서 작성 중 원격 main에 사건·뉴스 v3 u167–u173이 등록되어 최종 문서 기준을 `838bed60`으로 fast-forward하고, UI 유닛을 u174–u179로 옮겼다. 동시 등록 문서와 u145 closeout 기록은 수정하지 않았다. 두 SHA 사이 `src/`, `tests/`, `site_docs/`, `mkdocs.yml`, `pyproject.toml`, `.github/workflows/`에 diff가 없어 최초 코드 대조 근거가 유지된다.

세 독립 reviewer에게 번호·링크와 v3 역할 분리 delta를 다시 검토시켰다. repair 및 home/shell은 APPROVE였고, reader/archive에서 위 v3 snippet P2가 발견되어 수정·재검토했다. 최종 결과는 **세 리뷰 범위 모두 APPROVE; 잔여 P1/P2 0**이다. u178의 FD 흐름·heading·Step4도 schema별 producer/순서로 명료화했다. v3 semantic/DTO/hash reader/E1/typed region은 u169/u171, semantic·운영 cutover는 u172 소유이며 UI는 해당 입력의 표현·탐색만 맡는다. 이 판정은 유닛 문서 등록 범위에 한정된다.

## 문서 검증

수행 범위:

- 계획 6개의 필수 10개 섹션과 metadata, 숫자/slug/AC 및 state/README 링크 일치. state의 u167–u179 행은 각각 한 번이며 번호순을 유지한다.
- tracked 문서의 `git diff --check`와 신규 untracked Markdown의 별도 `git diff --no-index --check /dev/null <file>`.
- Markdown 상대 링크의 실제 대상 존재, 현재 source/test owner 경로, 새 파일은 구현 예정으로 표시됐는지 확인.
- 보존 증거 11개 파일의 SHA-256/byte count와 manifest 대조.
- 변경 경로가 `aidlc-docs/` 문서·검토 시안/관측 증거에 한정되는지와 기존 루트 dirty 상태 보존.

초기 untracked metadata의 Markdown hard-break용 trailing spaces는 별도 검사에서 발견해 bullet metadata로 정리했다. 최초 경고를 최종 PASS로 계산하지 않는다.

기존 test 경로 존재 검사는 구현 단계에서 만들 신규 test를 별도로 구분한다. u174의 guard test는 신규 예정 목록과 Step4에 명시했다. 최종 문서 검사에서 상대 링크·신규 Markdown 포함 whitespace·미실행 체크박스·번호·기존 test 경로·증거 11개(712,662 bytes)의 hash·변경 범위를 모두 확인했다. 최종 `git ls-remote origin refs/heads/main`은 문서 기준 `838bed607e1e170893de8f9230634a1f8568a06e`와 일치했다. 문서는 `codex/ui-units-20261010` 격리 작업 트리에 미커밋 상태로 남는다.

구현 테스트, MkDocs 재빌드, 새 브라우저 acceptance, Pages dispatch, private runtime 변경, 커밋/푸시는 이번 문서화에서 수행하지 않았다. 이전 분석의 headless 화면 관측과 시안 측정은 날짜가 고정된 증거로만 보존한다.

후속 작업은 등록된 순서로 진행한다. u174/u175는 기존 동작 복구 계획이며, u176–u179는 각 계획의 FD/NFR 산출물과 미결 결정부터 다룬다.
