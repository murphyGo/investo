# u182 Tech stack decisions

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 후속 진행 지시로 설계 채택. 로컬 구현·검증 진행 중이며 운영 활성화는 별도다.

| 영역 | 선택 | 이유 |
| --- | --- | --- |
| 모델·검증 | 기존 Python3.11+ / Pydantic2 / Decimal / zoneinfo | strict 숫자·clock·typed public/private 경계; 신규 dependency 없음 |
| 수집 | 기존 httpx·source registry·callback, opt-in same-response envelope | request/비용/키와 routing 을 확대하지 않음 |
| 정적 화면 | MkDocs Material / deterministic Markdown+HTML+필요한 SVG, u176/u178 tokens | 기존 Pages·테마·noJS 읽기 재사용 |
| 보관·게시 | u180 bounded JSON·manifest·기존 PublicationRequest/Receipt | 모델과원격증거 일치·다중파일 회복·범위보존 |
| 검증 | 기존 pytest fixtures / Ruff / mypy / 정책 guard / 실제 build·viewport | source 의미·snapshot·배포를 서로 다른 수용으로 확인 |

SPA/backend/database·회원/계좌·외부 telemetry·추가 LLM/유료 provider 를 도입하지 않는다. 기존 lock/dependencies 변경 0 을 기본으로 하며 범위 밖 새 dependency 가 필요하면 설계 변경으로 기록한다.
