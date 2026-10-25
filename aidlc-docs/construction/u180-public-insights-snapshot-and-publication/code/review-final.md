# u180 independent code review — final

작성일: 2026-10-12. 별도 Codex reviewer. 판정: **확인한 미해결 Critical 0 / High 0 / Medium 0**.

초기 전체 검토의 범위·protocols·증거와 발견 이슈는 [review-initial.md](review-initial.md)에 기록되어 있다. 이번 재검토는 초기 High H180-01의 복구 수정에 한정한다. 후속 전체 코드 리뷰나 전체 test suite 재실행으로 표현하지 않는다.

## H180-01 수정 확인

- `_Journal.initial_head`를 backup·record identity와 함께 atomic write/fsync하고 이후 public file promotion을 수행한다.
- no-receipt recovery에서 현재 HEAD와 initial HEAD를 비교한다. 값이 달라 commit 이후 receipt 저장 전 종료 등 불확실한 상태이면 작업 파일·index·journal을 보존하고 `outcome_unknown`으로 반환한다.
- HEAD가 같은 상태에서는 모든 owned 작업 파일·backup hash를 preflight한 뒤 callback이 staged blob hash와 journal.new_hash, 고정된 initial_head의 blob hash와 journal.old_hash를 대조한다. callback 검사 전과 reset 직전에 HEAD가 initial_head와 같은지 다시 확인하며 변경을 발견하면 불확실 상태로 보존한다.
- 검증이 통과한 owned staged paths만 `git reset <literal initial_head SHA> -- <owned paths>`로 되돌린다. 이동 가능한 HEAD 참조를 reset 대상으로 사용하지 않는다. 다른 staged paths는 유지한다. 이후 작업 파일 rollback 및 journal cleanup을 수행한다.
- owned index가 다른 writer의 값으로 바뀐 경우 scoped reset 또는 파일 rollback 전에 실패하고 journal을 보존한다.

해당 변경을 `publisher/insights/store.py`와 `orchestrator/insights_publication.py`에서 직접 읽고 초기 재현 경로와 대조했다. 신규/기존 baseline에서 add 후 종료, unrelated staging 보존, altered owned index 거부, commit 이후 receipt 전 종료에 대한 5개 통합 시나리오의 assertion도 확인했다. **H180-01은 해결되었다.**

## reviewer 직접 실행한 검증

설치된 worktree venv로 다음 명령을 실행했다. uv cache 접근이나 production remote는 사용하지 않았다.

```text
.venv/bin/python -m pytest tests/unit/publisher/test_insights_store_u180.py tests/integration/test_insights_publication_u180.py -q
29 passed in 36.96s
```

시험 원격은 임시 로컬 bare Git이다. 초기 리뷰에서 직접 재현한 두 번의 실패와 비교하여 위 회귀 테스트가 정상 재개/불확실 상태 보호를 확인한다. 전체 suite·resource·Ruff/mypy/actionlint 결과는 lead가 실행한 증거와 구별하며 이 reviewer가 재실행했다고 주장하지 않는다.

위 29개 실행 이후 추가된 검사 전·reset 직전 HEAD 재검사 및 literal SHA 대상 고정은 해당 함수와 두 callsite를 read-only로 다시 대조했다. 이 마지막 보강 뒤 reviewer가 pytest를 재실행한 것은 아니다.

## 한계와 운영 상태

이번 narrowly scoped 재검토에서 새 Critical/High/Medium finding은 없다. 의미·권리·원격 identity·legacy 경계의 앞선 리뷰 범위는 initial 보고서를 따른다. 실제 power-loss 또는 production concurrency 시험을 했다는 의미는 아니다. default-off, 미승인 실제 source 자격, public/private runtime·Pages·5회 scheduled 관찰의 별도 Step 8 pending은 그대로 유지된다. reviewer는 소스/테스트 수정, commit, push, deploy를 하지 않았다.
