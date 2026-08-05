# u143 Step 0 — Measured baseline and Material contract

## Outcome

- Measured a complete four-card archive asset directory and projected the
  bounded storage increase from dark companions.
- Built the site with the locked documentation dependency set and confirmed
  Material's four light/dark fragment selectors in generated CSS.
- Snapshotted the exact pre-u143 `_CARD_STYLE` bytes for the Step 1
  compatibility test.
- Confirmed that `mkdocs.yml` remains unchanged.

## Storage evidence

The representative directory is
`archive/us-equity/2026/08/2026-08-04.assets/`, the latest complete four-card
set at the Step 0 snapshot.

| Payload | Files | Bytes |
| --- | ---: | ---: |
| Primary SVG cards | 4 | 13,003 |
| Primary SVG manifests | 4 | 1,686 |
| Projected dark companions | 4 | 13,003 |
| Projected dark manifests | 0 | 0 |

At three segments per run, the projected increment is 39,009 bytes per run.
The current six-runs-per-week schedule projects 1,014,234 bytes per average
26-run month and 12,170,808 bytes per 312-run year. Step 2 will report the
actual forced-dark byte total rather than assuming parity with the primary
files.

## Material CSS evidence

`uv run --extra docs mkdocs build --strict` completed successfully with
Material 9.7.6. The built CSS contains:

```css
[data-md-color-scheme=slate] img[src$="#gh-light-mode-only"],[data-md-color-scheme=slate] img[src$="#only-light"]{display:none}
[data-md-color-scheme=default] img[src$="#gh-dark-mode-only"],[data-md-color-scheme=default] img[src$="#only-dark"]{display:none}
```

This confirms both GitHub-compatible fragments and both Material aliases.
No custom CSS, JavaScript, or `mkdocs.yml` change is required.

## Compatibility fixture

`tests/fixtures/u143_card_style_auto.txt` stores the exact current style
string. Its terminal newline is fixture framing; Step 1 removes that one
framing newline before asserting byte equality with `build_card_style("auto")`.

## Validation

- Strict MkDocs build: passed.
- Four required fragment selectors: present.
- `mkdocs.yml` SHA-256 unchanged:
  `d6a1a767426199da7e1ec639903ebfd91dca021f6867b1235b5172efecdb495d`.
- Existing visual render regression: 13 passed.
- `git diff --check`: passed.
