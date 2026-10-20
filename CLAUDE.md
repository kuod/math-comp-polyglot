# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Benchmarks 12 numerical/linear-algebra operations across Python (NumPy), Python (Pandas), Python (Polars), Python (JAX), Python (Numba), Octave, R, Julia, Rust, C++, C, Fortran, Haskell, Swift, and Go. Each language writes a `results/<lang>_results.json` file; `generate_report.py` reads those and produces a self-contained `index.html`.

## Running benchmarks

```bash
# Run every available language and regenerate the report
./run_all.sh

# Run a single language manually (must be run from project root)
python3 python/benchmark.py               # Python (NumPy)
python3 python_pandas/benchmark.py        # requires: pip install pandas scipy
python3 python_polars/benchmark.py        # requires: pip install polars scipy
octave --no-gui octave/benchmark.m
python3 numba_bench/benchmark.py          # requires: pip install -r requirements.txt (numba version bound is there)
python3 python_jax/benchmark.py           # requires: pip install jax
Rscript r/benchmark.R                      # run_all.sh auto-installs the R package jsonlite if missing
~/.juliaup/bin/julia julia/benchmark.jl   # run_all.sh auto-installs Julia pkgs JSON3 and FFTW
./rust/target/release/benchmark          # after building
./cpp/build_benchmark                    # after building
$(cd haskell && cabal list-bin haskell-bench)  # after building
./swift/swift-bench                      # after building
./go/go-bench                            # after building

# Regenerate HTML from existing JSON results (no re-running benchmarks)
python3 generate_report.py
```

## Setup and tests

```bash
pip install -r requirements.txt   # Python deps (scipy is needed by all Python benchmarks)
python3 -m pytest tests            # report generator unit tests
bash tests/test_run_all.sh         # run_all.sh failure-handling test
```

`generate_report.py` skips (with a warning) result files that are not valid JSON or lack required fields. `run_all.sh` continues past failing languages, still builds the report, and exits non-zero listing the failed steps. Exception: the Haskell `cabal build` is not wrapped in `run_step` (its output is filtered through grep and `|| true`), so a Haskell build failure is not listed; it surfaces only as a skip ("Haskell binary not found after build") when no binary exists, and a stale binary from an earlier build would be run.

## Building compiled languages

**C** (requires clang + macOS SDK):
```bash
clang -O3 -march=native -framework Accelerate -DACCELERATE_NEW_LAPACK \
    -Wno-deprecated-declarations \
    -o c/c-bench c/benchmark.c -lm
```

**Fortran** (requires `brew install gcc`):
```bash
gfortran -O3 -march=native -framework Accelerate \
    -o fortran/fortran-bench fortran/benchmark.f90
```

**Rust** (requires `~/.cargo/bin/cargo`):
```bash
cd rust && ~/.cargo/bin/cargo build --release -q
```

**C++** (requires `brew install eigen`):
```bash
c++ -std=c++17 -O3 -march=native \
    -I/opt/homebrew/include/eigen3 \
    -isysroot $(xcrun --show-sdk-path) \
    -I$(xcrun --show-sdk-path)/usr/include/c++/v1 \
    -Wno-deprecated-declarations \
    -o cpp/build_benchmark cpp/benchmark.cpp
```

**Haskell** (requires `brew install ghc cabal-install`):
```bash
cd haskell && cabal build
```
Dependencies are fetched from Hackage on first build. `hmatrix` links against system BLAS/LAPACK (Accelerate on macOS). Haskell does not implement FFT (shows `—` in the report; Fortran also omits FFT and Python (JAX) omits Sort) — `vector-fftw` uses `CDouble` rather than `Double`, making a safe benchmark impractical.

**Swift** (ships with Xcode Command Line Tools on macOS):
```bash
swiftc -O -whole-module-optimization \
    -sdk "$(xcrun --show-sdk-path)" \
    -o swift/swift-bench \
    swift/Sources/main.swift
```
Uses Apple Accelerate (BLAS/LAPACK/vDSP). Deprecation warnings about the CLAPACK interface are expected and harmless.

**Go** (requires `brew install go`):
```bash
cd go && go mod tidy && go build -o go-bench .
```
Uses `gonum.org/v1/gonum` (pure Go, no external LAPACK).

## Architecture

### Data flow
```
<lang>/benchmark.<ext>  →  results/<lang>_results.json  →  generate_report.py  →  index.html
```

`results/*.json` and `index.html` are generated outputs, but they ARE tracked on purpose: `index.html` is the GitHub Pages site and `results/` is the data it is built from. Regenerate and commit them together after re-running benchmarks. Build artifacts (binaries, `__pycache__`) are gitignored; `./clean.sh` removes them.

### JSON schema (each `results/*.json`)
```json
{
  "language": "Python",
  "version": "...",
  "platform": "...",
  "operations": [
    { "name": "...", "description": "...", "mean_ms": 0.0, "std_ms": 0.0, "min_ms": 0.0, "memory_mb": 0.0 }
  ]
}
```

### Adding a new language

1. Write `<lang>/benchmark.<ext>` outputting the JSON schema above to `results/<lang>_results.json`
2. In `generate_report.py`, add entries to `LANG_META`, `FILE_MAP`, and `LANG_MEMORY_NOTE`
3. Add a build + run block to `run_all.sh`

### Report structure (`generate_report.py`)

The report is one self-contained HTML file built in `generate_html()`. Sections in order:

| Section | What it is |
|---------|------------|
| Executive Summary | Data-driven highlights: winner, gold medals per op, two performance tiers, notable findings |
| Leaderboard | Golf-scoring table — rank per op (1 = fastest), summed; lowest total wins. Langs missing an op (Haskell/FFT, Fortran/FFT, JAX/Sort) are charged worst+1 for it (`compute_golf_scores`) |
| Language Summary | Cards sorted by score showing avg time, avg MB, score |
| Overview Charts | Two grouped bar charts across all ops (time + memory) |
| Per-Operation: Time vs Memory | One scatter plot per op — x = time (ms), y = memory (MB), one point per language |
| Full Comparison Table | Heat-coloured grid, time ± std and memory per lang per op |
| Glossary | One card per operation explaining what it computes and what it stresses |

Key dicts that drive rendering — edit these when adding/changing languages:
- `LANG_META` — color, background, chart label, inline SVG logo
- `FILE_MAP` — maps language name → results JSON filename
- `LANG_MEMORY_NOTE` — one-line description of memory measurement method

### Memory measurement — not apples-to-apples

| Language | Mechanism |
|----------|-----------|
| Python (NumPy/Pandas/Polars) | `tracemalloc` peak (Python-managed heap; large NumPy arrays may be under-counted) |
| Octave   | Theoretical output-matrix size |
| R        | `gc()` Vcells delta |
| Julia    | `@allocated` total bytes |
| Rust     | Custom `GlobalAlloc` peak tracker |
| C++      | Theoretical output-matrix size (Eigen calls `malloc` directly) |
| C        | Theoretical output-matrix size (malloc directly) |
| Fortran  | Theoretical output-matrix size (ALLOCATE/LAPACK directly) |
| Haskell  | `GHC.Stats.allocated_bytes` delta |
| Swift    | Theoretical output-matrix size (same rationale as C++) |
| Go       | `runtime.TotalAlloc` delta (cumulative bytes allocated) |
| Numba    | `tracemalloc` peak (Python-managed heap; output arrays via NumPy) |
| Python (JAX) | Theoretical output size (XLA allocations bypass tracemalloc) |

### Performance context

Python/R/Julia/Haskell/Swift link against system BLAS/LAPACK (Accelerate on macOS) and outperform nalgebra (Rust), Eigen (C++), and gonum (Go) on dense linear algebra. Swift/Accelerate is particularly fast on Cholesky, LU, and QR on Apple Silicon.

Rust's nalgebra performs Cholesky, QR, and LU **in-place** on the moved input — near-zero memory allocation for those ops is correct, not a measurement gap.

**Haskell QR**: forces only the R factor (directly from LAPACK's `dgeqrf`) rather than the full Q, which hmatrix would form via ~500 Haskell-level Householder multiplications (~400× slower). The description field in the JSON records this.
