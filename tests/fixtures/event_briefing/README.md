# Synthetic event replay

`manifest.json` freezes **12 scenario groups and 25 input replay variants**.
`records.json` contains only AI-authored synthetic source items and recorded
Stage 1/Stage 2 responses. Every URL uses `example.invalid`; synthetic actors,
facts, dates and market reactions are illustrative and are not reporting.
Expected IDs, literal required facts, forbidden claims, uncertainty, public
outcomes and counts live in the manifest independently of replay output.

Run `uv run python scripts/check_event_coverage.py` with the `dev` and `docs`
extras installed. The recording runner cannot launch a CLI, fetch sources or
publish. It calls the real generation pipeline, event finalizer, Markdown HTML
renderer and terminal quality evaluator. The checker prints only identifiers,
counts, states and closed failure codes. Mutation variants deliberately remove
or alter generated text **before the real finalizer**; the production source
tree does not gain an additional public Markdown writer.

The matrix includes 4/5 surviving events with a maximum of 3 notification DTO
events, one unchanged monthly value and COT background report, duplicates,
revision identity, normal zero versus failed collection, classification failure,
both DST transitions, after-hours inclusion, and the current calendar-day
weekend exclusion. The last case records the u158/u159 limitation; it does not
claim the u160 operational observation window has been implemented.

The **18 published output inventory entries are not source-input recordings**.
Only archive paths, source revision and SHA-256 digests are retained from the
2026-09-22 inventory. The original published articles are neither duplicated
here nor passed to the event generator. These historical output references do
not increase the input replay count.

The five-item what/when/why/reaction/source rubric is an **AI-authored rubric**.
`human_review: pending` and `human_semantic_score: null` intentionally remain.
Passing deterministic checks does not establish a human 5/5 semantic review,
worldwide-news recall, live shadow non-interference, Pages/notification delivery
or approval to activate public event mode.

## Historical terminal snapshot

`terminal_snapshots.json`은 reviewed 전환 코드 `ca631e245d0341c09ea1671c32c4286dbd2c9c3a`에서 기존
25개 기록을 같은 replay/generation/finalizer로 실행해 고정한 24개 유효 terminal의 Markdown/HTML/알림과
차단·absence outcome이다. 파일 SHA-256은 `f3688443d205abbf30689192c1775fa361eb948631f895c23f74a6c28e26d3d0`이다.
`basis=historical_output`, `fixture_author=AI-authored synthetic`, `human_review=pending`이다.
새 실제 corpus·ingestion recall·사람 합격·genuine scheduled 관찰에 포함하지 않는다.
legacy 제거 후 read-only historical parser/output 회귀를 위한 자료이며 현재 production generator 제거를 실행하지 않았다.
