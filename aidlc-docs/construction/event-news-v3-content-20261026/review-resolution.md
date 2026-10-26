# 설계 로컬 검토와 한계

2026-10-26. primary agent가 코드 경로·기존 계약·새 설계를 대조했다. **위임/독립 reviewer0명**이며 인간 수용·코드 리뷰·실행 CI 결과를 주장하지 않는다.

## 검토 과정에서 해소한 충돌

| 검토 항목 | 확인한 충돌 / 누락 | 반영한 결정 |
| --- | --- | --- |
| 기존 두 단계 계약 | 의미 검증을 추가하면서 “추가 LLM0”을 유지하면 모순 | role_v1과 article_v2 분리, C1/C4/C7 개정표와 explicit budget |
| 실제 runner 예산 | default300초만 보면 실제 segment1800초/call·3900/5700초를 놓침 | pipeline의 실제 설정 확인 후 새3900초/5-call allocator·review reserve 정의 |
| 원문 보강 연결 | preview 미연결, production v2-only, capability false | orchestration 공통 준비·별도 preview capability·defaultoff·실제 qualification 분리 |
| HTTP 총량 | 시장별6회를 새로 주면 기존 run cap3배 | run 공유6회, 동일 document 재요청0 |
| 자연스러운 한국어의 proof | refs가 있다는 이유로 의미를 증명했다고 하면 trust 약화 | exact atoms/locator hard gate + 별도 semantic review + actual 사람5/5 |
| 자유로운 편집과 내용 기준 | 역할4칸·최소글자 수로 평가하면 사용자 편집 정책과 충돌 | 내부 주제별 질문, 선택 문단/표/목록, 길이는 상한·권장치만 |
| v1 projection hash | 새 default field를 model_dump에 넣으면 과거 hash 손상 | raw version별 검증/serializer, v1 shape 유지, unsupported version fallback |
| finalizer 이후 본문 변경 | draft의 평가만으로 seal하면 삭제된 핵심 설명을 놓침 | sentence range·exact hashes·terminal coverage 재계산, stale review 거절 |
| source owner 중복 | u184가 qualification을 새로 소유하면 u173과 겹침 | u173 자격 소유, u184는 qualified 기존 source의 bounded 연결만 |
| 완료 상태 | 개발자 reference 승인/모델 supported를 실제 합격으로 오인 | 코드0·actual0/12·slot0/8·운영0 분리, u172 기존 미완료 유지 |

## 검증 범위

문서 변경에 대해 상대 링크 대상, 새 유닛 번호/등록/계획 참조, 모듈·현재 테스트 경로, 고정 수치의 교차 일치, placeholder, `git diff --check`를 검사한다. 변경 문서는 `docs/`와 `aidlc-docs/`뿐이고 MkDocs의 `docs_dir=site_docs`에 포함되지 않으므로 site build/full pytest를 문서 인수로 반복하지 않는다. 실제 코드/정책/워크플로/공개 산출물 변경이 없는지 diff 경로로 확인한다.

남은 불확실성은 실제 원천의 권리·접근/본문 공급, 한국어 의미 검증의 false positive/negative, 추가 호출의 실측 지연·계정 사용량이다. 숫자 상한·bounded retry·기존 source gate·u172 사람/실제 운영 수용으로 확인할 항목이며 문서 검토만으로 해결됐다고 표시하지 않는다. 현재 설계 자체의 열린 선택지 대신 기본값·실패 동작·담당 유닛을 고정했다.

## 문서 검사 결과

변경21개 Markdown(신규10개), 추가 상대 링크52개 모두 대상 존재를 확인했다. 기존 테스트 경로13개는 실제 존재하고 신규 계획 테스트12개는 미작성으로 구별했다. 각 신규 유닛은 등록1개·미완료Step6개·번호별AC6개이며 중복 번호가 없다. placeholder 검색과 `git diff --check`를 통과했다. source/runtime/workflow/site/archive 변경0이며 기존 root의5개 dirty 항목은 보존했다. 실제 pytest·모델·HTTP·사람 검수·배포는 이번 문서 검사에서 실행하지 않았다.
