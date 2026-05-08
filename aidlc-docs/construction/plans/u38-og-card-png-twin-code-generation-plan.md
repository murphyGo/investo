# Code Generation Plan: `u38 og-card-png-twin`

**Date**: 2026-05-09
**Unit**: u38 og-card-png-twin
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 10-persona evaluation 2026-05-09 — persona #7 (첫 방문자 / share-link surface) + DEBT-058 backlog
**Estimated Effort**: ~1.5-2 h
**Dependencies**:
- Builds directly on `u29 site-discovery-v2` (`visuals/og_card.py` already produces an SVG OG card; `overrides/main.html` already emits the `og:image` meta tag).
- Resolves DEBT-058 (`docs/TECH-DEBT.md` line 22) — OG image PNG twin generation for social-card unfurl.

---

## Goal

Produce a PNG twin (`assets/og-card.png`) alongside the existing `assets/og-card.svg` so that Telegram, Slack, Twitter / X, LinkedIn, and the dominant OG consumers actually render the share-card preview. Today's SVG-only OG meta tag is structurally valid but functionally invisible on those targets — they require raster PNG / JPEG. This is the last unit gating persona #7's "share the link with a friend" first-impression surface.

---

## Persona evidence

> Persona #7 (첫 방문자, P1): "친구가 텔레그램에 링크를 보내줘서 처음 사이트를 봤는데, 미리보기 카드가 그냥 GitHub Pages 기본 favicon 만 떠 있어서 이게 뭔지 알기 어려웠다. 미리보기 카드에서 바로 '오늘 시황' 같은 카피가 보였으면 클릭률이 훨씬 높았을 것 같다."

> DEBT-058 (Source: u29 QA H2 / M5): "the major OG consumers — Telegram, Slack, Twitter / X, LinkedIn — do **not** honour SVG `og:image` payloads in practice; they require a PNG (or JPEG) twin."

---

## Definition of Done

- [ ] `visuals/og_card.py` produces `assets/og-card.png` alongside the existing `assets/og-card.svg` on every publish that regenerates the OG card. Conversion is deterministic — same SVG input → byte-identical PNG output (within tooling tolerance).
- [ ] PNG dimensions are exactly 1200 × 630 (standard OG card aspect) and conform to the `[100, 2000]` `VisualProvenanceManifest` validation range introduced in u24.
- [ ] `overrides/main.html` emits a PNG `og:image` meta tag (`<meta property="og:image" content="https://murphygo.github.io/investo/assets/og-card.png" />`) **as the primary** and retains the SVG as a secondary `og:image:secure_url` for browsers that honour SVG. Both URLs validated by `mkdocs build --strict`.
- [ ] CI runner (`.github/workflows/daily-briefing.yml`) installs the system dependency the conversion path needs (`libcairo2` for the cairosvg path, or `librsvg2-bin` for the rsvg-convert path); a preflight check fails the run early with a clear operator-chat alert if the dependency is missing.
- [ ] DEBT-058 marked **Resolved** in `docs/TECH-DEBT.md` with the resolution date (2026-05-09 or later, depending on landing) and a one-line note pointing at this unit and the chosen path (cairosvg vs rsvg-convert).
- [ ] Manual verification: paste the public site URL into Telegram, Slack, Twitter / X, and LinkedIn share fields and confirm the rendered preview shows the OG card image with the title text legible. Capture screenshots in the unit closeout summary.
- [ ] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Path Decision: cairosvg vs rsvg-convert

- [ ] Decide between (a) Python-side cairosvg (adds `libcairo2` apt dep + `cairosvg` python dep) and (b) GHA-side rsvg-convert (adds `librsvg2-bin` apt dep, no python dep, conversion runs as a workflow step before the Pages deploy).
- [ ] Recommendation: **Option (a) cairosvg** — keeps the conversion inside `visuals/og_card.py` so local `mkdocs serve` and CI behave identically; option (b) couples the PNG twin to GHA infra and breaks local previews.
- [ ] Files affected:
  - `pyproject.toml` (add `cairosvg ~= 2.7` to runtime deps)
  - decision recorded in this plan + the unit summary

### Step 2 — PNG Render Path

- [ ] In `visuals/og_card.py`, add `render_og_card_png(svg_bytes: bytes, *, output_path: Path) -> Path` that uses `cairosvg.svg2png` with `output_width=1200, output_height=630`.
- [ ] Wire `render_og_card_png` into the existing `regenerate_og_card` (or equivalent) chokepoint so SVG and PNG land atomically. If PNG render fails, the SVG write is also rolled back so the on-disk pair stays consistent.
- [ ] Stamp PNG with the same `VisualProvenanceManifest` sidecar (`og-card.png.json`) so u24's manifest invariant continues to hold across both formats.
- [ ] Files affected:
  - `src/investo/visuals/og_card.py`
- [ ] Unit tests added at `tests/unit/visuals/test_og_card_png.py`:
  - PNG dimensions are exactly 1200 × 630.
  - Same SVG input → byte-identical PNG (deterministic).
  - PNG sidecar manifest has `source_type: "generated_svg"` and the same `generator` / `version` as the SVG sidecar.
  - SVG-write rollback fires when PNG render raises.

### Step 3 — OG Meta Tag Update

- [ ] Update `overrides/main.html` to emit the PNG URL as the primary `og:image` and retain SVG as the secondary `og:image:secure_url`. Add `og:image:type` (`image/png`) and `og:image:width=1200` / `og:image:height=630` for unfurl reliability.
- [ ] Files affected:
  - `overrides/main.html`
- [ ] Verification: `mkdocs build --strict` validates both absolute URLs and confirms the rendered HTML contains both meta tags.

### Step 4 — CI Dependency Install

- [ ] Add an `apt-get install -y libcairo2 libcairo2-dev` step to `.github/workflows/daily-briefing.yml` before the Python install step.
- [ ] Add a preflight check (`python -c "import cairosvg; cairosvg.svg2png(bytestring=b'<svg/>')"` or equivalent) that fails the run early with a clear error if the install regressed; the orchestrator's existing operator-alert path catches the boot-time failure via u31 boot-alert dedup.
- [ ] Files affected:
  - `.github/workflows/daily-briefing.yml`
- [ ] Verification: workflow run logs show the apt install line and the preflight passing.

### Step 5 — DEBT-058 Resolution

- [ ] Move DEBT-058 from `## High Priority` to `## Resolved Items` in `docs/TECH-DEBT.md` with `**Resolved**: YYYY-MM-DD — u38 landed cairosvg PNG twin; OG card now unfurls correctly on Telegram / Slack / Twitter / X / LinkedIn.`
- [ ] Cross-reference the unit summary path so future readers can trace the closure.
- [ ] Files affected:
  - `docs/TECH-DEBT.md`

### Step 6 — Verification

- [ ] Run targeted visuals tests + the full quality gate.
- [ ] Manual share-link unfurl verification on the four dominant OG consumers (screenshots attached to the unit summary).

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable — no LLM call introduced.
- **Module boundary**: changes are within `visuals/`; no new cross-module import.
- **R10 (record/replay fixtures, no fabrication)**: not applicable — PNG conversion is local; no new external HTTP source.
- **R13 (secret hygiene)**: not applicable — no new env var, no secret.
- **Disclaimer enforcement**: not relevant to OG card surface.
- **No paid APIs**: cairosvg + libcairo2 are GPL/LGPL free dependencies; no service call.

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅ (cairosvg ships partial type stubs; if mypy strict mode trips, add a narrow `# type: ignore[import-untyped]` with a comment pointing at the upstream issue)
- [ ] `uv run pytest -q` ✅ (expect ~5-8 new tests)
- [ ] `uv run mkdocs build --strict` ✅ (validates both `og:image` and `og:image:secure_url` URLs)

---

## Out of scope

- **JPEG twin** — only PNG is produced. JPEG is structurally redundant when PNG already unfurls correctly; revisit only if a specific consumer is found that prefers JPEG.
- **Per-day OG card variation** — the OG card remains a single static asset (refreshed when the hero copy changes); per-day OG cards (`og-card-2026-05-09.png`) are a future visual unit if persona feedback demands it.
- **Animated OG card** — not requested by any persona; out of scope.
- **librsvg-based GHA-side conversion** — option (b) explicitly deferred. If cairosvg install proves brittle on the GHA runner, fall back to option (b) in a follow-up unit.

---

## Open questions

- **cairosvg version pin**: target `cairosvg ~= 2.7` (latest 2.x at time of writing). If the strict mypy run trips on cairosvg's partial stubs, a `py.typed` audit may be needed; record the outcome in the unit summary.
- **PNG byte-determinism**: cairosvg's output is deterministic for the same input + version pin, but a libcairo2 upgrade on the runner could shift bytes. The unit test pins on dimensions and manifest, not on byte hash, to avoid a CI flake on libcairo2 minor bumps.
