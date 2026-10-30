# 우선순위별 데이터 확장 실행 계획

## Stage Decision
- Functional Design: Required, 완료. 새 활동 모델과 native/legacy 표시, KRX 계약 유형을 정의함.
- NFR Requirements: Required, 완료. 시간·숫자·공개 조건·실패 격리·검증 경계를 정의함.
- NFR Design: 기존 source retry/registry/finalizer 패턴으로 충족.
- Infrastructure Design: Skipped. 새 서비스·키·상시 수집 없음.
- Source of requirements: 사용자 “우선수위별로 적용하자”, 후속 검토 보고서, FR-001/002, US-008, NFR-002/003/004.
- 사용자 승인은 설계·구현·검증을 포함한다. 이번 신규 확장의 commit/push/배포는 별도 실행 범위로 남긴다.

## 실행
- [x] 1. 기존 코드·조사·사용 조건 대조, FD/NFR 고정.
- [x] 2. Coin Metrics 활동 모델·adapter·registry/routing 구현.
- [x] 3. legacy/native deterministic 표시·가격 검증·출처 고지 연결.
- [x] 4. EF 조건 판정 기록, KRX 공식 연간 근거 확인과 위클리 구현.
- [x] 5. synthetic source/model 오류 및 end-to-end 발행 회귀, live read-only 확인.
- [x] 6. 독립 코드 리뷰·수정·전체 품질 검사.
- [x] 7. baseline 대조 공유 작업공간 통합, state/audit/cross-check/session 기록.

## Release authorization

On 2026-10-30 the user explicitly requested commit and deployment. Release will preserve unrelated root changes and the current production schema/profile, validate both the public-main integration and a bounded runtime commit, and then update only the reviewed runtime code pin. The earlier implementation-only status is historical.
