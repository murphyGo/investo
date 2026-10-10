# Independent code review — u145 flat groups

Status: PASS, no unresolved blocker or new TECH-DEBT.
Reviewed implementation: `ee10d36d501eec21324651830e2a1b9aa31c5bde` from base
`ea402465df9a186b11094cc59c5fb4a0312a64f2`;40changed files,23 source/test/runtime assets.
Review used a separate read-only agent under dev-investo Step5.1 and code-review protocols.

| Protocol | Evidence / result |
| --- | --- |
| Concurrency | One36-attempt budget, concurrency2, ownership-aware cancel/drain preserved |
| Data integrity | Both views hashed/canonical; existing recoverable two-file store reused |
| Error contract | Parent failure holds prior pair; missing extra group publishes explicit partial/exit2 |
| Security boundary | Closed ticker/kind metadata, ETF/EQUITY validation, escaping, secret/raw exclusion |
| Resource lifecycle | Client/response/task ownership and cleanup preserved |
| Memory | Response/row/window/request/group/member limits remain bounded |
| Performance | Fixed collection/math loops; filters do not recalculate ranks or scales |

Found P2: schema3 retained12-ETF provenance despite collecting23assets. Resolved by closed
versioned12/23 request/support sets, accurate ETF/equity attribution and snapshot/provenance
version parity. Four forgery tests and legacy golden-byte checks pass. Same-hash TOC navigation
was also repaired and accepted after actual Material regression across four viewport/theme variants.

Validation: pre-provenance full6,751 PASS957.89s; post-fix affected paths202 PASS391.10s;
lint/format/mypy306, policies, maximum-shape benchmark and supplemental UI pass. The two
test runs have different code points and are not mislabeled as one final-head full execution.
Exact implementation quality[38024527395](https://github.com/murphyGo/investo/actions/runs/38024527395)
is PASS:6,755 tests in661.95s, Ruff/format711, mypy306, four policies, strict docs/Material.
Integrated-current-main quality remains a separate activation gate until observed PASS.

Integration quality[38025047604](https://github.com/murphyGo/investo/actions/runs/38025047604)
is now PASS:6,836 tests583.37s, Ruff/format724, mypy311, four policies and strict docs/Material.
Five exact25eb9220 probes qualify all23assets/11sectors/14groups. No review or nonvisual
activation validation item remains open; real publication/live closure is recorded separately.

Concurrent main`bb5711f9` added separate event/news foundation. Integration`25eb9220` keeps
both audit histories; dashboard models/source/CLI/workflows/config/CSS/JS/tests are byte-identical
to the reviewed implementation. Ruff and mypy311 pass on integration. Exact integration quality,
five source probes and live publication verification are tracked separately in operational evidence.
