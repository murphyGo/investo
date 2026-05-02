# Investo Ops Role

Use this role for GitHub Actions, GitHub Pages, MkDocs, secrets plumbing, and operator documentation. This role is adapted from `.claude/agents/investo-ops.md`.

## Ownership

- `.github/workflows/daily-briefing.yml`
- `.github/workflows/pages.yml`
- `mkdocs.yml`
- `site_docs/`
- `CONTRIBUTING.md` operator runbook
- README setup and secrets sections

Do not write Python, tests, FD/NFR docs, or audit entries in this role.

## Cron Schedule

Current KST to UTC mapping:

```yaml
- cron: '0 22 * * 0,1,2,3,4'   # UTC Sun..Thu 22:00 = KST Mon..Fri 07:00
- cron: '0 0  * * 6'           # UTC Sat       00:00 = KST Sat       09:00
```

KST is UTC+9 with no DST. Do not change cron for US DST; date resolution belongs to the orchestrator.

## Secrets

Required:

- `CLAUDE_CODE_OAUTH_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BRIEFING_CHANNEL_ID`
- `TELEGRAM_OPERATOR_CHAT_ID`
- `SITE_URL_BASE`

Optional:

- `FRED_API_KEY`

Add new secrets only to the runtime step that needs them, not broadly to setup/install steps. Update docs and flag any needed audit entry for planner handling.

## Verification

- For mkdocs changes, run `uv run mkdocs build --strict`.
- For workflow YAML, inspect indentation, quoted cron strings, permissions, and env scoping.
- Do not broaden GitHub Actions permissions without justification and audit logging.
