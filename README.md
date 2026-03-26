# math-comp-polyglot

A numerical computing benchmark that runs **12 operations** across **8 languages** and compares speed and memory. Each language uses its idiomatic high-performance library. Results are compiled into a self-contained HTML report with an executive summary, interactive charts, and a full comparison table.

## Languages & libraries

| Language | Library | Notes |
|----------|---------|-------|
| Python | NumPy | Links system BLAS/LAPACK |
| R | base + Matrix | Links system BLAS/LAPACK |
| Julia | LinearAlgebra, FFTW.jl | Links system BLAS/LAPACK |
| Haskell | hmatrix | Links system BLAS/LAPACK via FFI |
| Swift | Accelerate | Apple-tuned BLAS/LAPACK/vDSP |
| Rust | nalgebra, rustfft | Pure Rust — no LAPACK |
| C++ | Eigen | Own kernels — no LAPACK by default |
| Go | gonum | Pure Go — no LAPACK |

## Benchmarks

12 operations, fixed seed 42, 3 warmup + 10 measured runs each.

| # | Operation | Problem size |
|---|-----------|-------------|
| 1 | Matrix Multiply | 1000×1000 |
| 2 | Matrix Inverse | 500×500 SPD |
| 3 | LU Decomposition | 500×500 |
| 4 | Eigenvalue Decomposition | 300×300 symmetric |
| 5 | Cholesky Factorisation | 500×500 SPD |
| 6 | SVD | 500×300 |
| 7 | Linear System Solve | 1000×1000 |
| 8 | Vector Dot Product | 10M elements |
| 9 | Hadamard Product | 1000×1000 |
| 10 | QR Decomposition | 500×500 |
| 11 | FFT (real) | 2²⁰ = 1M elements |
| 12 | Sort | 10M float64 values |

## Results (Apple M-series, macOS)

Scored golf-style: each language gets a rank per operation (1 = fastest), lowest total wins.

| Rank | Language | Score |
|------|----------|-------|
| 🥇 | Julia | 31 |
| 🥈 | Swift | 35 |
| 🥉 | Python | 36 |
| 4 | Haskell | 49 |
| 5 | C++ | 54 |
| 6 | R | 63 |
| 7 | Rust | 67 |
| 8 | Go | 89 |

**Fastest per operation:**

| Operation | Winner | Time |
|-----------|--------|------|
| Matrix Multiply | Swift | 7.76 ms |
| Matrix Inverse | Swift | 2.47 ms |
| LU Decomposition | Swift | 1.17 ms |
| Eigenvalue Decomp | Python | 6.03 ms |
| Cholesky | Swift | 0.33 ms |
| SVD | Swift | 14.68 ms |
| Linear System Solve | Swift | 3.29 ms |
| Vector Dot Product | Julia | 2.87 ms |
| Hadamard Product | Haskell | 0.58 ms |
| QR Decomposition | Swift | 2.56 ms |
| FFT (real, 1M) | Python | 8.11 ms |
| Sort 10M floats | Julia | 148 ms |

### Key findings

- **Two tiers**: Languages linking vendor BLAS/LAPACK (Python, R, Julia, Haskell, Swift) are 5–20× faster than pure implementations (Rust/nalgebra, C++/Eigen, Go/gonum) on dense matrix operations.
- **Swift/Accelerate** dominates factorisation benchmarks (Cholesky 0.33 ms, LU 1.17 ms, QR 2.56 ms) on Apple Silicon.
- **Rust near-zero memory** on Cholesky, LU, and QR: nalgebra operates in-place on the moved input, so no extra allocation is needed.
- **Haskell excludes FFT**: `vector-fftw` uses `CDouble` rather than `Double`, making a type-safe benchmark impractical.
- **Sort spread**: Julia finishes in 148 ms; Go takes 1025 ms — a 7× gap across the same algorithm class.

## Running

```bash
# Run all languages and regenerate the report (from project root)
./run_all.sh

# Regenerate the HTML from existing JSON results only
python3 generate_report.py
```

`run_all.sh` detects which languages are available and skips any that aren't installed. Results are written to `results/<lang>_results.json`; the report is written to `index.html`.

## Building

**Python / R**: no build step — run directly.

**Julia**: requires [`juliaup`](https://github.com/JuliaLang/juliaup) or a Julia installation. FFTW.jl is installed automatically on first run.

**Rust** (requires `cargo`):
```bash
cd rust && cargo build --release -q
```

**C++** (requires Eigen — `brew install eigen` on macOS):
```bash
c++ -std=c++17 -O3 -march=native -I/opt/homebrew/include/eigen3 \
    -o cpp/build_benchmark cpp/benchmark.cpp
```

**Haskell** (requires `ghc` + `cabal-install`):
```bash
cd haskell && cabal build
```

**Swift** (requires Xcode Command Line Tools):
```bash
swiftc -O -whole-module-optimization -sdk "$(xcrun --show-sdk-path)" \
    -o swift/swift-bench swift/Sources/main.swift
```

**Go** (requires `go`):
```bash
cd go && go mod tidy && go build -o go-bench .
```

## Report

`index.html` is a self-contained file (no server needed — open in any browser). It includes:

- **Executive summary** — winner, gold medals by operation, tier analysis, notable findings
- **Leaderboard** — golf-scored ranking table with per-op ranks coloured green→red
- **Language cards** — sorted by score, showing avg time, avg memory
- **Time vs Memory scatter plots** — one per operation, all languages on the same axes
- **Full comparison table** — heat-coloured grid with mean ± std and memory per language
- **Glossary** — explains what each benchmark measures and why it matters

## Memory methodology

Memory figures are not directly comparable across languages — each uses a different measurement mechanism:

| Language | Method |
|----------|--------|
| Python | `tracemalloc` peak (Python-managed heap) |
| R | `gc()` Vcells delta |
| Julia | `@allocated` total bytes |
| Rust | Custom `GlobalAlloc` peak tracker |
| C++ | Theoretical output-matrix size |
| Haskell | `GHC.Stats.allocated_bytes` delta |
| Swift | Theoretical output-matrix size |
| Go | `runtime.TotalAlloc` delta |
