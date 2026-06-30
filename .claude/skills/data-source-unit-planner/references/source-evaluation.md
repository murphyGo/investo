# Source Evaluation Reference

Use this reference when ranking candidate Investo data sources or writing source-addition AIDLC units.

## Scorecard

Classify each candidate against these gates before proposing a unit:

| Gate | Ship-now bar |
| --- | --- |
| Provenance | Official agency, exchange, issuer, standards body, protocol, or clearly licensed data owner. |
| Cost | Free access is sufficient for the planned use. No paid-tier dependency. |
| Structure | API, CSV, JSON, RSS/Atom, downloadable official file, or stable machine-readable endpoint. |
| Auth | No key preferred. Key-required is acceptable only with an existing or clearly documented optional env path. |
| Rate limit | Documented or operationally low-risk for daily briefing cadence. |
| Fields | Adds fields Investo can actually render, validate, route, or use in prompts. |
| Freshness | Update cadence matches the user-facing claim. Do not invent consensus, surprise, or realtime fields. |
| Overlap | Improves trust, geography, asset class, granularity, or fallback coverage beyond existing adapters. |
| Degradation | Missing key, network failure, or malformed payload degrades into visible coverage diagnostics without breaking sibling sources. |
| Compliance | Passes the repo's no-paid-source guardrails and can be documented in source metadata. |

## Dispositions

- `ship-now`: clears the scorecard and maps to a bounded adapter/unit with testable acceptance criteria.
- `defer`: promising but blocked by unclear terms, key acquisition, unstable endpoint, high overlap, missing schema, or runtime risk.
- `reject`: paid-only, scrape-only without stable structured feed, terms-incompatible, unmaintained, or not useful for Investo outputs.

## Source Fact Template

Use this in research notes or AIDLC plans:

```markdown
| Field | Value |
| --- | --- |
| Source owner |  |
| Data family | news / macro / prices / filings / chart / rates / crypto / calendar / other |
| Docs URL |  |
| Endpoint URL |  |
| Auth | none / optional key / required key |
| Cost and no-paid evidence |  |
| Rate limit |  |
| Format | JSON / CSV / RSS / XML / file / other |
| Key fields |  |
| Update cadence |  |
| License or terms note |  |
| Existing Investo overlap |  |
| Proposed source_name |  |
| Proposed adapter path |  |
| Routing surfaces | registry / tier map / market window / segment allow-list / config / diagnostics |
| Degradation behavior |  |
```

## Candidate Families

Prefer official or primary sources:

- Macro/economic indicators: central banks, statistics agencies, treasury/finance ministries, labor agencies, and official release calendars.
- Market prices and charts: exchanges, official index providers with free feeds, public exchange directories, and existing vetted data vendors only when no-paid access is clear.
- Company facts and filings: securities regulators, exchange disclosure feeds, issuer filings, and official issuer calendars.
- News and releases: official agency feeds, exchange notices, central-bank releases, regulator RSS, and company IR feeds before broad web news scraping.
- Crypto/on-chain: protocol-owned endpoints, foundation feeds, public chain explorers with clear free API terms, and open data APIs with documented no-paid use.

## Repo Surfaces To Check

For every source unit, verify whether each surface needs an explicit step:

- source adapter module and tests
- `src/investo/sources/__init__.py`
- `src/investo/sources/aggregator.py`
- source tier maps and config
- market-window routing
- `src/investo/briefing/segments.py`
- coverage/fetch diagnostics
- no-paid API checker and contribution docs
- fixtures and plugin-contract tests

## Common Failure Modes

- Treating "public web page" as "stable structured source".
- Adding a source that duplicates current coverage without improving trust or reader output.
- Filling model fields such as consensus, surprise, or realtime status without a real source-of-record.
- Planning only the adapter and forgetting registry, routing, segment allow-list, diagnostics, or tests.
- Keeping auth failures silent instead of surfacing coverage degradation.
- Reusing stale research from an aborted or pre-refactor thread without checking the current repo.
