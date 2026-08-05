# u143 Step 6 — Cumulative quality gate and closeout

## Outcome

- Swept all `.assets/`-related tests; no stale `ok: 18 files` assertion remains.
- Added a built-output contract gate for Material's two fragment hiding rules
  and wired strict documentation build plus the gate into the Quality workflow.
- Added the theme parity contract to `docs/DESIGN.md` (TD-013 after main
  integration) and moved DEBT-049/061 from active to
  resolved. Active debt counts are now Medium 0 and Low 33.
- Kept existing archives untouched. No production market document was
  fabricated merely to create a GitHub rendering fixture.

## Built-site acceptance

Material 9.7.6 built successfully. An ephemeral exact-pair page produced both
HTML sources exactly:

```text
src="card.svg#gh-light-mode-only"
src="card-dark.svg#gh-dark-mode-only"
```

The repository site's built CSS then passed
`scripts/check_material_theme_contract.py`, which requires the exact light-hide
and dark-hide rules. On every invocation the script also builds the exact pair
through the installed MkDocs Material and fails if either built-HTML `src` is
missing. Its unit tests pin green, missing-rule, missing-build, exact-pair, and
rewritten-fragment states. CI runs it after `mkdocs build --strict`, so future
Material or Markdown upgrades cannot silently remove AC-143.1(a) or (b).

## Review corrections

- **AC-143.1(a) persistence**: the initial closeout had only one-time ephemeral
  HTML evidence. The final CI guard now performs that ephemeral MkDocs build on
  every run and verifies both exact fragment sources fail-closed.
- **Legacy backfill neutrality**: `scripts/backfill_2026_05_06_visuals.py` is
  rerunnable and still emits fragment-free single links. Its renderer call now
  explicitly uses `variant="auto"`, preserving the pre-u143 OS-theme behavior;
  a structural regression test pins that argument.

## Raw GitHub boundary

No post-u143 production archive exists before main integration and the plan
explicitly forbids archive backfill. [GitHub's current official documentation](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/quickstart-for-writing-on-github)
uses the HTML `<picture>` mechanism for responsive theme images, not the legacy
`gh-*` fragments. Therefore the first post-u143 production archive remains the
first honest page on which to observe legacy-fragment behavior. If GitHub ignores
the fragments, the two images stack; that is the user-ratified accepted fallback.
Pages remains the canonical reader surface and is fully guarded here.

## Full validation

- `uv lock --check`: passed (65 packages).
- Ruff check and format: passed (569 Python files formatted).
- Strict mypy: passed (252 source files).
- Full pytest: **4,319 passed in 267.90 seconds**.
- Anthropic SDK guard: passed.
- Paid API guard: passed.
- Curated assets guard: passed (19 filed, 0 deferred; 15 legacy + 4
  evidence-backed).
- Image store guard: passed (0 binaries, 0 sidecars).
- `mkdocs build --strict`: passed.
- Built Material theme contract: passed (2 minified stylesheets + executable
  exact-pair MkDocs HTML render).
- `git diff --check`: passed.
- Post-suite generated-file sweep: no `archive/` or `site_docs/` residue.

## Next boundary

Run the requirements cross-check, commit/push its report, then integrate the
validated branch into `main` from an isolated worktree and verify the exact-SHA
Quality workflow.

## Final fresh-eyes approval

Approved after both corrections with zero remaining Critical/High/Medium/Low
findings. Independent review revalidated 65 focused tests, the live combined
CSS + built-HTML guard, scoped mypy, all-repository Ruff/format, diff check,
debt counts, document consistency, and the absence of generated residue.
