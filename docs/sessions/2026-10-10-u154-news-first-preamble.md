# u154 news-first preamble — 2026-10-10

The user requested numeric-table reduction after authorizing main integration,
operational activation and per-unit commit/push. This extends existing u154.
Root dirty work is untouched; scoped worktree starts from main19c89b92.

News summary now precedes hero and one CLOSED “시장 지표 자세히 보기” panel.
The original top market table and ⓪/⓪-A/⓪-B numeric surfaces move into it with
their values, timestamps, links and unavailable labels. Body event figures and
tables remain visible. Duplicate exact titles are removed, while conflicting
titles and unsupported summary content remain fail-closed. Existing archives
are not republished.

No provider, source, event-selection, receipt, cursor, retry or notification
destination change. The exact panel is unwrapped before repeated assembly;
complete asset blocks and body bytes are preserved. Panel children remain
reader_visible for trust checks. Summary and shell region ownership ensure
fallbacks do not corrupt neighboring callouts or remove HTML boundaries.

Independent review CLOSED, no P1/P2 outstanding: focused311/12.98s and final
independent212/9.56s pass. Earlier failing exploratory runs are not counted as
passing validation. Corrected findings include protected-table classification,
news-observation boundary, separate TLDR fallback ownership and u153 H2 context.

| Review category | Result |
| --- | --- |
| Correctness / Safety / Reliability / Maintainability / Test Coverage | PASS; all findings closed |
| Protocols applied | Security Boundary, Data Integrity, Error Contract, Performance |
| Other protocols | Concurrency, Resource Lifecycle and Memory not triggered: no new concurrent work, resource ownership or retained state |

Actual archive samples reduce expanded preamble tables from2→0 in domestic/US
and3→0 in crypto, retaining the original rows inside the panel. Static gates:
Ruff, format680, mypy293, four policy guards, strict MkDocs and Material/theme
rendered-pair checks pass. Actual configured HTML is verified; browser viewport
inspection is not claimed.

Operational applicability: the private runtime was pinned to7bc6d287 when work
started. Public main includes separately gated u163/u164. Exact runtime delivery
must be verified independently; a main push alone does not activate this layout.
Event domestic/US active, crypto shadow/v1 and news-window shadow/enrichment off
remain unchanged. Human acceptance and first active scheduled observations are
not completed by this presentation work.

The scoped runtime backport is commit
`e96ea921c4f1bc5f1aa4286453f62d107c93b95c`, parent7bc6d287. Its eight-file patch
matches the main candidate exactly (`git patch-id --stable`:
`60a5fee13b7f697c5eeb29d5f8adf8bf1b894b9a`). It excludes u163/u164 pending
operational qualification. Runtime local publisher/event regression1880/124.54s,
Ruff/format673/mypy291, policy4, strict docs and Material pass. Exact remote
branch is `codex/u154-runtime-20261010`; full Actions verification precedes any
private runtime pin change.

The first full local run found17 failures (6294 passed/735.46s); it is not a
passing gate. Sixteen came from legacy preamble diagnostics followed by the new
numeric panel: the old parser counted both closing tags as diagnostics closers.
The parser now validates the owned numeric shell first and excludes exactly its
closing offset; unmarked duplicate and unpaired marked closes remain rejected.
One DEBT-060 guard required reuse of the central summary-prefix constants.
Legacy early-diagnostics single/full/partial refinalization and negative shell
tests were added. Initial runtime CI37951792214 also failed and was not promoted.
Corrected focused60/2.76s pass; final full CI and review follow this correction.
