#!/usr/bin/env bash
# Run all language benchmarks and generate the HTML report.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$ROOT/results"
mkdir -p "$RESULTS"

log()  { echo "[run_all] $*"; }
skip() { echo "[run_all] SKIP – $*"; }

# ── Python ────────────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    log "Running Python benchmark..."
    cd "$ROOT"
    python3 python/benchmark.py
else
    skip "python3 not found"
fi

# ── R ─────────────────────────────────────────────────────────────────────────
if command -v Rscript &>/dev/null; then
    log "Running R benchmark..."
    cd "$ROOT"
    # Ensure jsonlite is installed
    Rscript -e 'if(!requireNamespace("jsonlite",quietly=TRUE)) install.packages("jsonlite",repos="https://cloud.r-project.org")'
    Rscript r/benchmark.R
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
    "$JULIA_BIN" julia/benchmark.jl
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
    "$CARGO_BIN" build --release -q
    log "Running Rust benchmark..."
    cd "$ROOT"
    ./rust/target/release/benchmark
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
        c++ -std=c++17 -O3 -march=native \
            -I"$EIGEN_INC" $SDK_FLAGS \
            -Wno-deprecated-declarations \
            -o "$ROOT/cpp/build_benchmark" \
            "$ROOT/cpp/benchmark.cpp"
        log "Running C++ benchmark..."
        cd "$ROOT"
        ./cpp/build_benchmark
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
        "$BIN"
    else
        skip "Haskell binary not found after build"
    fi
else
    skip "cabal or ghc not found"
fi

# ── Swift ─────────────────────────────────────────────────────────────────────
if command -v swiftc &>/dev/null; then
    log "Building Swift benchmark..."
    swiftc -O -whole-module-optimization \
        -sdk "$(xcrun --show-sdk-path)" \
        -o "$ROOT/swift/swift-bench" \
        "$ROOT/swift/Sources/main.swift"
    log "Running Swift benchmark..."
    cd "$ROOT"
    ./swift/swift-bench
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
    "$GO_BIN" build -o go-bench .
    log "Running Go benchmark..."
    cd "$ROOT"
    ./go/go-bench
else
    skip "go not found"
fi

# ── Generate HTML report ──────────────────────────────────────────────────────
log "Generating HTML report..."
cd "$ROOT"
python3 generate_report.py

log "Done! Open report.html in your browser."
