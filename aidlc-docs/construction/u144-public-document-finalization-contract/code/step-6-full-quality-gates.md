# Step 6.9 — Full quality gates

## Scope

The final gate ran from a detached, clean `fe6635e` worktree so concurrent
u140 documents and generated archive/site artifacts in the primary worktree
could not influence the result. Gate-driven repairs were committed separately:

- `fb0ef0b` added the NFR-required deterministic finalizer benchmark;
- `ac41fb0` moved numeric verification and source-outcome scoping to neutral
  `_internal` owners, eliminating both publisher-to-briefing imports;
- `fe6635e` aligned the `investo.models` public-export drift guard with the
  three u144 outcome types already exported by the package.

## Validation

| Gate | Result |
|---|---|
| U144 focused plus declared owner/integration scope | `677 passed` |
| Full pytest | `4062 passed` |
| u114 import-boundary module | `13 passed` |
| Ruff | all checks passed |
| Ruff format | 545 files already formatted |
| mypy | no issues in 246 source files |
| no-paid guard | exit 0 |
| MkDocs strict, clean tree | exit 0 |
| `git diff --check` | exit 0 |

## Reproducible benchmark

Both runs used three segments, one warm-up, and five measured iterations on
Python 3.11.9 / macOS 15.5 arm64.

| Input per segment | Median | Max | Peak RSS delta |
|---|---:|---:|---:|
| 100 KiB | 132.593 ms | 134.199 ms | 4,849,664 bytes |
| 200 KiB | 254.380 ms | 259.829 ms | 7,471,104 bytes |

The 200/100 median ratio is 1.919, below the 3.0 closeout threshold. The
largest observed RSS delta is 7.13 MiB, below the 64 MiB threshold. Identical
inputs produced stable input and sealed-output SHA-256 digests across every
iteration.

Commands:

```bash
uv run python scripts/benchmark_public_document_finalizer.py \
  --segments 3 --bytes-per-segment 102400 --warmup 1 --iterations 5
uv run python scripts/benchmark_public_document_finalizer.py \
  --segments 3 --bytes-per-segment 204800 --warmup 1 --iterations 5
```

## Result

Step 6 is complete at 9/9. The implementation is eligible for Step 7
production closeout.
