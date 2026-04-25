#!/usr/bin/env julia
# Benchmark 10 numerical operations in Julia (LinearAlgebra stdlib)

using LinearAlgebra
using Random
using Statistics
using Printf
using JSON3
using FFTW

const SEED = 42
const N_WARMUP = 3
const N_RUNS = 10

rng() = MersenneTwister(SEED)

make_matrix(n, m=n) = randn(rng(), Float64, n, m)
make_spd(n) = (A = randn(rng(), Float64, n, n); A * A' + n * I)

struct BenchResult
    name::String
    description::String
    mean_ms::Float64
    std_ms::Float64
    min_ms::Float64
    memory_mb::Float64
end

function bench(name, description, setup_fn, op_fn)
    # Warmup (important for Julia JIT)
    for _ in 1:N_WARMUP
        d = setup_fn()
        op_fn(d)
    end

    times_ms  = zeros(N_RUNS)
    mem_bytes = zeros(N_RUNS)

    for i in 1:N_RUNS
        d = setup_fn()
        GC.gc()
        t0    = time_ns()
        alloc = @allocated op_fn(d)
        t1    = time_ns()
        times_ms[i]  = (t1 - t0) / 1e6
        mem_bytes[i] = alloc
    end

    BenchResult(
        name, description,
        mean(times_ms), std(times_ms), minimum(times_ms),
        mean(mem_bytes) / (1024^2)
    )
end

OPERATIONS = [
    (
        "Matrix Multiply",
        "1000×1000 dense matrix multiplication (A * B)",
        () -> (make_matrix(1000), make_matrix(1000)),
        d -> d[1] * d[2]
    ),
    (
        "Matrix Inverse",
        "Inversion of 500×500 SPD matrix",
        () -> (make_spd(500),),
        d -> inv(d[1])
    ),
    (
        "LU Decomposition",
        "LU factorisation of 500×500 matrix",
        () -> (make_matrix(500),),
        d -> lu(d[1])
    ),
    (
        "Eigenvalue Decomp",
        "Full eigendecomposition of 300×300 symmetric matrix",
        () -> begin A = make_matrix(300); ((A + A') / 2,) end,
        d -> eigen(Symmetric(d[1]))
    ),
    (
        "Cholesky",
        "Cholesky factorisation of 500×500 SPD matrix",
        () -> (make_spd(500),),
        d -> cholesky(d[1])
    ),
    (
        "SVD",
        "Economy SVD of 500×300 matrix (U:500×300, S:300, Vt:300×300)",
        () -> (make_matrix(500, 300),),
        d -> svd(d[1])
    ),
    (
        "Linear System Solve",
        "Solve Ax=b for 1000×1000 A, 1000 b",
        () -> (make_spd(1000), randn(rng(), 1000)),
        d -> d[1] \ d[2]
    ),
    (
        "Vector Dot Product",
        "Dot product of two 10M-element vectors",
        () -> (randn(rng(), 10_000_000), randn(rng(), 10_000_000)),
        d -> dot(d[1], d[2])
    ),
    (
        "Hadamard Product",
        "Element-wise multiply + add on 1000×1000 matrices",
        () -> (make_matrix(1000), make_matrix(1000), make_matrix(1000)),
        d -> d[1] .* d[2] .+ d[3]
    ),
    (
        "QR Decomposition",
        "QR factorisation of 500×500 matrix",
        () -> (make_matrix(500),),
        d -> qr(d[1])
    ),
    (
        "FFT (real, 1M)",
        "Real FFT of 2²⁰=1M-element vector (FFTW.jl rfft)",
        () -> (randn(rng(), 1 << 20),),
        d -> rfft(d[1])
    ),
    (
        "Sort 10M floats",
        "Unstable sort of 10M random float64 values (Julia sort!)",
        () -> (randn(rng(), 10_000_000),),
        d -> sort!(copy(d[1]))
    ),
]

println("Julia $(VERSION)")

results = BenchResult[]
for (name, desc, setup, op) in OPERATIONS
    print("  Benchmarking: $(rpad(name, 25)) ... ")
    flush(stdout)
    r = bench(name, desc, setup, op)
    push!(results, r)
    @printf("%.2f ms  (%.2f MB)\n", r.mean_ms, r.memory_mb)
end

ops_json = [
    Dict(
        "name"        => r.name,
        "description" => r.description,
        "mean_ms"     => r.mean_ms,
        "std_ms"      => r.std_ms,
        "min_ms"      => r.min_ms,
        "memory_mb"   => r.memory_mb,
    )
    for r in results
]

out = Dict(
    "language"   => "Julia",
    "version"    => string("Julia ", VERSION),
    "platform"   => string(Sys.MACHINE),
    "operations" => ops_json,
)

mkpath("results")
open("results/julia_results.json", "w") do f
    JSON3.write(f, out)
end
println("Saved results/julia_results.json")
