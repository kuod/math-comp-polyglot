#!/usr/bin/env python3
"""Benchmark 12 numerical operations using Polars DataFrames/Series."""

import numpy as np
import polars as pl
import json
import time
import tracemalloc
import platform
import sys
import os

from scipy.linalg import lu as scipy_lu

SEED = 42
N_WARMUP = 3
N_RUNS = 10


def fresh_rng():
    return np.random.default_rng(SEED)


def make_matrix(n, m=None):
    rng = fresh_rng()
    if m is None:
        m = n
    return rng.standard_normal((n, m))


def make_spd(n):
    rng = fresh_rng()
    A = rng.standard_normal((n, n))
    return A @ A.T + n * np.eye(n)


def bench(name, description, setup_fn, op_fn):
    for _ in range(N_WARMUP):
        data = setup_fn()
        op_fn(data)

    times_ms = []
    mem_mbs = []

    for _ in range(N_RUNS):
        data = setup_fn()
        tracemalloc.start()
        t0 = time.perf_counter()
        _ = op_fn(data)
        t1 = time.perf_counter()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times_ms.append((t1 - t0) * 1000)
        mem_mbs.append(peak / (1024 ** 2))

    return {
        "name": name,
        "description": description,
        "mean_ms": float(np.mean(times_ms)),
        "std_ms": float(np.std(times_ms)),
        "min_ms": float(np.min(times_ms)),
        "memory_mb": float(np.mean(mem_mbs)),
    }


# For matrix ops Polars does not have native BLAS kernels; we use numpy on
# .to_numpy() and wrap the result back in a DataFrame where it makes sense.
# Native Polars is used for Sort and Vector Dot Product.

OPERATIONS = [
    {
        "name": "Matrix Multiply",
        "description": "1000×1000 DataFrame matmul (numpy on .to_numpy(), result as DataFrame)",
        "setup": lambda: (pl.DataFrame(make_matrix(1000)), pl.DataFrame(make_matrix(1000))),
        "op": lambda d: pl.DataFrame(d[0].to_numpy() @ d[1].to_numpy()),
    },
    {
        "name": "Matrix Inverse",
        "description": "Inversion of 500×500 SPD DataFrame (numpy on .to_numpy())",
        "setup": lambda: (pl.DataFrame(make_spd(500)),),
        "op": lambda d: pl.DataFrame(np.linalg.inv(d[0].to_numpy())),
    },
    {
        "name": "LU Decomposition",
        "description": "LU factorisation of 500×500 DataFrame (scipy on .to_numpy())",
        "setup": lambda: (pl.DataFrame(make_matrix(500)),),
        "op": lambda d: scipy_lu(d[0].to_numpy()),
    },
    {
        "name": "Eigenvalue Decomp",
        "description": "Full eigendecomposition of 300×300 symmetric DataFrame",
        "setup": lambda: pl.DataFrame((lambda A: (A + A.T) / 2)(make_matrix(300))),
        "op": lambda d: np.linalg.eigh(d.to_numpy()),
    },
    {
        "name": "Cholesky",
        "description": "Cholesky factorisation of 500×500 SPD DataFrame",
        "setup": lambda: (pl.DataFrame(make_spd(500)),),
        "op": lambda d: pl.DataFrame(np.linalg.cholesky(d[0].to_numpy())),
    },
    {
        "name": "SVD",
        "description": "Economy SVD of 500×300 DataFrame (numpy on .to_numpy(); U:500×300)",
        "setup": lambda: (pl.DataFrame(make_matrix(500, 300)),),
        "op": lambda d: np.linalg.svd(d[0].to_numpy(), full_matrices=False),
    },
    {
        "name": "Linear System Solve",
        "description": "Solve Ax=b for 1000×1000 DataFrame A, Series b",
        "setup": lambda: (
            pl.DataFrame(make_spd(1000)),
            pl.Series(fresh_rng().standard_normal(1000)),
        ),
        "op": lambda d: np.linalg.solve(d[0].to_numpy(), d[1].to_numpy()),
    },
    {
        "name": "Vector Dot Product",
        "description": "Dot product of two 10M-element Polars Series ((s1 * s2).sum())",
        "setup": lambda: (
            pl.Series(fresh_rng().standard_normal(10_000_000)),
            pl.Series(fresh_rng().standard_normal(10_000_000)),
        ),
        "op": lambda d: (d[0] * d[1]).sum(),
    },
    {
        "name": "Hadamard Product",
        "description": "Element-wise multiply + add on 1000×1000 DataFrames (numpy via .to_numpy())",
        "setup": lambda: (
            pl.DataFrame(make_matrix(1000)),
            pl.DataFrame(make_matrix(1000)),
            pl.DataFrame(make_matrix(1000)),
        ),
        "op": lambda d: pl.DataFrame(d[0].to_numpy() * d[1].to_numpy() + d[2].to_numpy()),
    },
    {
        "name": "QR Decomposition",
        "description": "QR factorisation of 500×500 DataFrame (numpy on .to_numpy())",
        "setup": lambda: (pl.DataFrame(make_matrix(500)),),
        "op": lambda d: np.linalg.qr(d[0].to_numpy()),
    },
    {
        "name": "FFT (real, 1M)",
        "description": "Real FFT of 1M-element Polars Series (numpy rfft on .to_numpy())",
        "setup": lambda: (pl.Series(fresh_rng().standard_normal(1 << 20)),),
        "op": lambda d: np.fft.rfft(d[0].to_numpy()),
    },
    {
        "name": "Sort 10M floats",
        "description": "Sort 10M-element Polars Series (native radix sort)",
        "setup": lambda: (pl.Series(fresh_rng().standard_normal(10_000_000)),),
        "op": lambda d: d[0].sort(),
    },
]


def main():
    print(f"Python {sys.version.split()[0]} / Polars {pl.__version__}")
    results = []
    for op in OPERATIONS:
        print(f"  Benchmarking: {op['name']} ...", end=" ", flush=True)
        r = bench(op["name"], op["description"], op["setup"], op["op"])
        results.append(r)
        print(f"{r['mean_ms']:.2f} ms  ({r['memory_mb']:.2f} MB)")

    out = {
        "language": "Python (Polars)",
        "version": f"Python {sys.version.split()[0]} / Polars {pl.__version__}",
        "platform": platform.platform(),
        "operations": results,
    }
    os.makedirs("results", exist_ok=True)
    with open("results/python_polars_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Saved results/python_polars_results.json")


if __name__ == "__main__":
    main()
