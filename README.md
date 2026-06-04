# Numerical Computing Benchmark

**[Live report →](https://kuod.github.io/math-comp-polyglot/)**

Benchmarks 12 numerical/linear-algebra operations across 15 language implementations, measuring speed and memory on Apple Silicon (macOS).

## Languages

| Language | Library |
|---|---|
| Python (NumPy) | NumPy + SciPy + system BLAS |
| Python (Pandas) | Pandas (delegates to NumPy for decompositions) |
| Python (Polars) | Polars (delegates to NumPy for decompositions) |
| Python (JAX) | JAX / XLA (JIT-compiled) |
| Python (Numba) | Numba JIT |
| Octave | Built-in BLAS/LAPACK |
| R | R + BLAS |
| Julia | LinearAlgebra.jl + FFTW |
| Rust | nalgebra + realfft |
| C++ | Eigen |
| C | CBLAS + LAPACK + vDSP (Accelerate) |
| Fortran | BLAS + LAPACK (Accelerate) |
| Haskell | hmatrix (BLAS/LAPACK) |
| Swift | Accelerate |
| Go | gonum |

## Operations

Matrix Multiply · Matrix Inverse · LU Decomposition · Eigenvalue Decomp · Cholesky · SVD · Linear System Solve · Vector Dot Product · Hadamard Product · QR Decomposition · FFT (real, 1M) · Sort 10M floats

## Running

```bash
./run_all.sh        # run all languages and regenerate report
python3 generate_report.py  # regenerate report from existing results
```

See [CLAUDE.md](CLAUDE.md) for per-language build instructions.
