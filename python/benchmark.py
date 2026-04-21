#!/usr/bin/env python3
"""Benchmark 10 numerical operations using NumPy."""

import numpy as np
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
BASE_RNG = np.random.default_rng(SEED)


def fresh_rng():
    return np.random.default_rng(SEED)


def make_matrix(n, m=None, rng=None):
    if rng is None:
        rng = fresh_rng()
    if m is None:
        m = n
    return rng.standard_normal((n, m))


def make_spd(n):
    rng = fresh_rng()
    A = rng.standard_normal((n, n))
    return A @ A.T + n * np.eye(n)


def bench(name, description, setup_fn, op_fn):
    # Warmup
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


OPERATIONS = [
    {
        "name": "Matrix Multiply",
        "description": "1000×1000 dense matrix multiplication (A @ B)",
        "setup": lambda: (make_matrix(1000), make_matrix(1000)),
        "op": lambda d: d[0] @ d[1],
    },
    {
        "name": "Matrix Inverse",
        "description": "Inversion of 500×500 SPD matrix",
        "setup": lambda: (make_spd(500),),
        "op": lambda d: np.linalg.inv(d[0]),
    },
    {
        "name": "LU Decomposition",
        "description": "LU factorisation of 500×500 matrix",
        "setup": lambda: (make_matrix(500),),
        "op": lambda d: scipy_lu(d[0]),
    },
    {
        "name": "Eigenvalue Decomp",
        "description": "Full eigendecomposition of 300×300 symmetric matrix",
        "setup": lambda: (lambda A: (A + A.T) / 2)(make_matrix(300)),
        "op": lambda d: np.linalg.eigh(d),
    },
    {
        "name": "Cholesky",
        "description": "Cholesky factorisation of 500×500 SPD matrix",
        "setup": lambda: (make_spd(500),),
        "op": lambda d: np.linalg.cholesky(d[0]),
    },
    {
        "name": "SVD",
        "description": "Full SVD of 500×300 matrix",
        "setup": lambda: (make_matrix(500, 300),),
        "op": lambda d: np.linalg.svd(d[0], full_matrices=False),
    },
    {
        "name": "Linear System Solve",
        "description": "Solve Ax=b for 1000×1000 A, 1000 b",
        "setup": lambda: (make_spd(1000), fresh_rng().standard_normal(1000)),
        "op": lambda d: np.linalg.solve(d[0], d[1]),
    },
    {
        "name": "Vector Dot Product",
        "description": "Dot product of two 10M-element vectors",
        "setup": lambda: (fresh_rng().standard_normal(10_000_000), fresh_rng().standard_normal(10_000_000)),
        "op": lambda d: np.dot(d[0], d[1]),
    },
    {
        "name": "Hadamard Product",
        "description": "Element-wise multiply + add on 1000×1000 matrices",
        "setup": lambda: (make_matrix(1000), make_matrix(1000), make_matrix(1000)),
        "op": lambda d: d[0] * d[1] + d[2],
    },
    {
        "name": "QR Decomposition",
        "description": "QR factorisation of 500×500 matrix",
        "setup": lambda: (make_matrix(500),),
        "op": lambda d: np.linalg.qr(d[0]),
    },
    {
        "name": "FFT (real, 1M)",
        "description": "Real FFT of 2²⁰=1M-element vector (numpy rfft)",
        "setup": lambda: (fresh_rng().standard_normal(1 << 20),),
        "op": lambda d: np.fft.rfft(d[0]),
    },
    {
        "name": "Sort 10M floats",
        "description": "Unstable sort of 10M random float64 values (numpy sort)",
        "setup": lambda: (fresh_rng().standard_normal(10_000_000),),
        "op": lambda d: np.sort(d[0]),
    },
]


def main():
    print(f"Python {sys.version.split()[0]} / NumPy {np.__version__}")
    results = []
    for op in OPERATIONS:
        print(f"  Benchmarking: {op['name']} ...", end=" ", flush=True)
        r = bench(op["name"], op["description"], op["setup"], op["op"])
        results.append(r)
        print(f"{r['mean_ms']:.2f} ms  ({r['memory_mb']:.2f} MB)")

    out = {
        "language": "Python",
        "version": f"Python {sys.version.split()[0]} / NumPy {np.__version__}",
        "platform": platform.platform(),
        "operations": results,
    }
    os.makedirs("results", exist_ok=True)
    with open("results/python_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Saved results/python_results.json")


if __name__ == "__main__":
    main()
