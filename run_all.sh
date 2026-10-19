#!/usr/bin/env bash
# Run all language benchmarks and generate the HTML report.
# No `set -e`: one failing language must not abort the others or the report.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$ROOT/results"
mkdir -p "$RESULTS"

log()  { echo "[run_all] $*"; }
skip() { echo "[run_all] SKIP – $*"; }

FAILED=()
# run_step <label> <cmd...>: run a command; on failure record it and continue.
run_step() {
    local label="$1"; shift
    if ! "$@"; then
        echo "[run_all] FAILED – $label" >&2
        FAILED+=("$label")
        return 1
    fi
}
# Python scripts need numpy+scipy in addition to their own library.
py_has() { python3 -c "import numpy, scipy, $1" &>/dev/null; }

# ── Python (NumPy) ────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null && py_has numpy; then
    log "Running Python (NumPy) benchmark..."
    cd "$ROOT"
    run_step "Python (NumPy)" python3 python/benchmark.py
else
    skip "python3 with numpy+scipy not found (pip install numpy scipy)"
fi

# ── Python (Pandas) ───────────────────────────────────────────────────────────
if command -v python3 &>/dev/null && py_has pandas; then
    log "Running Python (Pandas) benchmark..."
    cd "$ROOT"
    run_step "Python (Pandas)" python3 python_pandas/benchmark.py
else
    skip "pandas not importable (pip install pandas scipy)"
fi

# ── Python (Polars) ───────────────────────────────────────────────────────────
if command -v python3 &>/dev/null && py_has polars; then
    log "Running Python (Polars) benchmark..."
    cd "$ROOT"
    run_step "Python (Polars)" python3 python_polars/benchmark.py
else
    skip "polars not importable (pip install polars scipy)"
fi

# ── Numba ─────────────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null && py_has numba; then
    log "Running Numba benchmark..."
    cd "$ROOT"
    run_step "Python (Numba)" python3 numba_bench/benchmark.py
else
    skip "numba not importable (pip install numba scipy)"
fi

# ── R ─────────────────────────────────────────────────────────────────────────
if command -v Rscript &>/dev/null; then
    log "Running R benchmark..."
    cd "$ROOT"
    # Ensure jsonlite is installed
    Rscript -e 'if(!requireNamespace("jsonlite",quietly=TRUE)) install.packages("jsonlite",repos="https://cloud.r-project.org")'
    run_step "R" Rscript r/benchmark.R
else
    skip "Rscript not found"
fi

# ── Julia ─────────────────────────────────────────────────────────────────────
JULIA_BIN=""
for p in "$HOME/.juliaup/bin/julia" \
         /Applications/Julia-1.8.app/Contents/Resources/julia/bin/julia \
         /usr/local/bin/julia; do
    if [ -x "$p" ]; then JULIA_BIN="$p"; break; fi
done
# Fallback: try whatever is on PATH
if [ -z "$JULIA_BIN" ] && command -v julia &>/dev/null; then
    JULIA_BIN="$(command -v julia)"
fi

if [ -n "$JULIA_BIN" ]; then
    log "Running Julia benchmark ($JULIA_BIN)..."
    cd "$ROOT"
    "$JULIA_BIN" -e 'import Pkg; Pkg.add(["JSON3","FFTW"])' 2>/dev/null || true
    run_step "Julia" "$JULIA_BIN" julia/benchmark.jl
else
    skip "julia not found"
fi

# ── Rust ──────────────────────────────────────────────────────────────────────
CARGO_BIN=""
for p in cargo ~/.cargo/bin/cargo; do
    if command -v "$p" &>/dev/null 2>&1 || [ -x "${p/#\~/$HOME}" ]; then
        CARGO_BIN="${p/#\~/$HOME}"; break
    fi
done

if [ -n "$CARGO_BIN" ]; then
    log "Building Rust benchmark (release)..."
    cd "$ROOT/rust"
    RUSTFLAGS="-C target-cpu=native" run_step "Rust build" "$CARGO_BIN" build --release -q && {
        log "Running Rust benchmark..."
        cd "$ROOT"
        run_step "Rust" ./rust/target/release/benchmark
    }
    cd "$ROOT"
else
    skip "cargo not found"
fi

# ── C++ ───────────────────────────────────────────────────────────────────────
if command -v c++ &>/dev/null; then
    log "Building C++ benchmark..."
    EIGEN_INC=""
    for p in /opt/homebrew/include/eigen3 /usr/local/include/eigen3 /usr/include/eigen3; do
        [ -f "$p/Eigen/Dense" ] && EIGEN_INC="$p" && break
    done
    if [ -z "$EIGEN_INC" ]; then
        skip "Eigen headers not found (brew install eigen)"
    else
        SDK_FLAGS=""
        SDK=$(xcrun --show-sdk-path 2>/dev/null || true)
        [ -n "$SDK" ] && SDK_FLAGS="-isysroot $SDK -I$SDK/usr/include/c++/v1"
        run_step "C++ build" c++ -std=c++17 -O3 -march=native \
            -I"$EIGEN_INC" $SDK_FLAGS \
            -Wno-deprecated-declarations \
            -o "$ROOT/cpp/build_benchmark" \
            "$ROOT/cpp/benchmark.cpp" && {
            log "Running C++ benchmark..."
            cd "$ROOT"
            run_step "C++" ./cpp/build_benchmark
        }
    fi
else
    skip "c++ compiler not found"
fi

# ── Haskell ───────────────────────────────────────────────────────────────────
if command -v cabal &>/dev/null && command -v ghc &>/dev/null; then
    log "Building Haskell benchmark..."
    cd "$ROOT/haskell"
    cabal build -v0 2>&1 | grep -v "^Warning\|^ld:\|^In order" || true
    BIN=$(cabal list-bin haskell-bench 2>/dev/null)
    if [ -n "$BIN" ] && [ -x "$BIN" ]; then
        log "Running Haskell benchmark..."
        cd "$ROOT"
        run_step "Haskell" "$BIN"
    else
        skip "Haskell binary not found after build"
    fi
else
    skip "cabal or ghc not found"
fi

# ── Swift ─────────────────────────────────────────────────────────────────────
if command -v swiftc &>/dev/null; then
    log "Building Swift benchmark..."
    run_step "Swift build" swiftc -O -whole-module-optimization \
        -sdk "$(xcrun --show-sdk-path)" \
        -o "$ROOT/swift/swift-bench" \
        "$ROOT/swift/Sources/main.swift" && {
        log "Running Swift benchmark..."
        cd "$ROOT"
        run_step "Swift" ./swift/swift-bench
    }
else
    skip "swiftc not found"
fi

# ── Go ────────────────────────────────────────────────────────────────────────
GO_BIN=""
for p in go /opt/homebrew/bin/go /usr/local/go/bin/go; do
    if command -v "$p" &>/dev/null 2>&1 || [ -x "$p" ]; then
        GO_BIN="$p"; break
    fi
done

if [ -n "$GO_BIN" ]; then
    log "Building Go benchmark..."
    cd "$ROOT/go"
    run_step "Go build" "$GO_BIN" build -o go-bench . && {
        log "Running Go benchmark..."
        cd "$ROOT"
        run_step "Go" ./go/go-bench
    }
    cd "$ROOT"
else
    skip "go not found"
fi

# ── Python (JAX) ─────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null && py_has jax; then
    log "Running Python (JAX) benchmark..."
    cd "$ROOT"
    run_step "Python (JAX)" python3 python_jax/benchmark.py
else
    skip "jax not importable (pip install jax)"
fi

# ── C (Accelerate) ───────────────────────────────────────────────────────────
if command -v clang &>/dev/null; then
    log "Building C benchmark..."
    run_step "C build" clang -O3 -march=native -framework Accelerate -DACCELERATE_NEW_LAPACK \
        -Wno-deprecated-declarations \
        -o "$ROOT/c/c-bench" "$ROOT/c/benchmark.c" -lm && {
        log "Running C benchmark..."
        cd "$ROOT"
        run_step "C" ./c/c-bench
    }
else
    skip "clang not found"
fi

# ── Fortran (Accelerate) ─────────────────────────────────────────────────────
GFORTRAN_BIN=""
for p in gfortran /opt/homebrew/bin/gfortran /usr/local/bin/gfortran; do
    if command -v "$p" &>/dev/null 2>&1 || [ -x "$p" ]; then
        GFORTRAN_BIN="$p"; break
    fi
done

if [ -n "$GFORTRAN_BIN" ]; then
    log "Building Fortran benchmark..."
    run_step "Fortran build" "$GFORTRAN_BIN" -O3 -march=native -framework Accelerate \
        -o "$ROOT/fortran/fortran-bench" "$ROOT/fortran/benchmark.f90" && {
        log "Running Fortran benchmark..."
        cd "$ROOT"
        run_step "Fortran" ./fortran/fortran-bench
    }
else
    skip "gfortran not found (brew install gcc)"
fi

# ── Octave ───────────────────────────────────────────────────────────────────
if command -v octave &>/dev/null; then
    log "Running Octave benchmark..."
    cd "$ROOT"
    run_step "Octave" octave --no-gui octave/benchmark.m
else
    skip "octave not found (brew install octave)"
fi

# ── Generate HTML report ──────────────────────────────────────────────────────
log "Generating HTML report..."
cd "$ROOT"
run_step "Report generation" python3 generate_report.py

if [ ${#FAILED[@]} -gt 0 ]; then
    log "Done with failures: ${FAILED[*]}"
    exit 1
fi
log "Done! Open index.html in your browser."
