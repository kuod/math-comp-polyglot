#!/usr/bin/env python3
"""Benchmark numerical operations using Numba JIT-compiled kernels.

Requires: pip install numba>=0.55  (for np.fft.rfft support in @njit)
"""

import numpy as np
from numba import njit, prange
import numba
import json
import time
import tracemalloc
import platform
import sys
import os

SEED = 42
N_WARMUP = 3
N_RUNS = 10


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


# ── Numba JIT kernels ─────────────────────────────────────────────────────────

@njit(cache=True)
def nb_matmul(A, B):
    """Matrix multiply; Numba lowers @ to BLAS dgemm."""
    return A @ B


@njit(cache=True)
def nb_inv(A):
    return np.linalg.inv(A)


@njit(cache=True)
def nb_eigh(A):
    return np.linalg.eigh(A)


@njit(cache=True)
def nb_cholesky(A):
    return np.linalg.cholesky(A)


@njit(cache=True)
def nb_svd(A):
    return np.linalg.svd(A, full_matrices=False)


@njit(cache=True)
def nb_solve(A, b):
    return np.linalg.solve(A, b)


@njit(cache=True)
def nb_dot(a, b):
    return np.dot(a, b)


@njit(parallel=True, cache=True)
def nb_hadamard(A, B, C):
    """Fused element-wise A*B+C using Numba parallel prange."""
    out = np.empty_like(A)
    for i in prange(A.shape[0]):
        for j in range(A.shape[1]):
            out[i, j] = A[i, j] * B[i, j] + C[i, j]
    return out


@njit(cache=True)
def nb_qr(A):
    return np.linalg.qr(A)


def nb_fft(x):
    """Real FFT via NumPy (np.fft.rfft not supported in nopython mode on this Numba version)."""
    return np.fft.rfft(x)


@njit(cache=True)
def nb_sort(x):
    return np.sort(x)


@njit(cache=True)
def nb_lu(A):
    """PLU decomposition in pure Numba (scipy unavailable in nopython mode).
    Uses partial pivoting: P @ A = L @ U."""
    n = A.shape[0]
    U = A.copy()
    L = np.eye(n)
    P = np.eye(n)
    for k in range(n - 1):
        # Find pivot row
        max_val = abs(U[k, k])
        max_idx = k
        for i in range(k + 1, n):
            v = abs(U[i, k])
            if v > max_val:
                max_val = v
                max_idx = i
        if max_idx != k:
            for j in range(n):
                U[k, j], U[max_idx, j] = U[max_idx, j], U[k, j]
                P[k, j], P[max_idx, j] = P[max_idx, j], P[k, j]
            for j in range(k):
                L[k, j], L[max_idx, j] = L[max_idx, j], L[k, j]
        if U[k, k] != 0.0:
            for i in range(k + 1, n):
                L[i, k] = U[i, k] / U[k, k]
                for j in range(k, n):
                    U[i, j] -= L[i, k] * U[k, j]
    return P, L, U


# ── Benchmarking harness ──────────────────────────────────────────────────────

def bench(name, description, setup_fn, op_fn):
    # Warmup — also triggers JIT compilation for first call
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
        "description": "1000×1000 dense matrix multiplication (@njit → BLAS dgemm)",
        "setup": lambda: (make_matrix(1000), make_matrix(1000)),
        "op": lambda d: nb_matmul(d[0], d[1]),
    },
    {
        "name": "Matrix Inverse",
        "description": "Inversion of 500×500 SPD matrix (@njit → np.linalg.inv)",
        "setup": lambda: (make_spd(500),),
        "op": lambda d: nb_inv(d[0]),
    },
    {
        "name": "LU Decomposition",
        "description": "LU factorisation of 500×500 matrix (pure Numba PLU; scipy unavailable in @njit)",
        "setup": lambda: (make_matrix(500),),
        "op": lambda d: nb_lu(d[0]),
    },
    {
        "name": "Eigenvalue Decomp",
        "description": "Full eigendecomposition of 300×300 symmetric matrix (@njit → np.linalg.eigh)",
        "setup": lambda: (lambda A: (A + A.T) / 2)(make_matrix(300)),
        "op": lambda d: nb_eigh(d),
    },
    {
        "name": "Cholesky",
        "description": "Cholesky factorisation of 500×500 SPD matrix (@njit → np.linalg.cholesky)",
        "setup": lambda: (make_spd(500),),
        "op": lambda d: nb_cholesky(d[0]),
    },
    {
        "name": "SVD",
        "description": "Full SVD of 500×300 matrix (@njit → np.linalg.svd)",
        "setup": lambda: (make_matrix(500, 300),),
        "op": lambda d: nb_svd(d[0]),
    },
    {
        "name": "Linear System Solve",
        "description": "Solve Ax=b for 1000×1000 A, 1000 b (@njit → np.linalg.solve)",
        "setup": lambda: (make_spd(1000), fresh_rng().standard_normal(1000)),
        "op": lambda d: nb_solve(d[0], d[1]),
    },
    {
        "name": "Vector Dot Product",
        "description": "Dot product of two 10M-element vectors (@njit → BLAS ddot)",
        "setup": lambda: (fresh_rng().standard_normal(10_000_000), fresh_rng().standard_normal(10_000_000)),
        "op": lambda d: nb_dot(d[0], d[1]),
    },
    {
        "name": "Hadamard Product",
        "description": "Element-wise multiply + add on 1000×1000 matrices (@njit parallel prange)",
        "setup": lambda: (make_matrix(1000), make_matrix(1000), make_matrix(1000)),
        "op": lambda d: nb_hadamard(d[0], d[1], d[2]),
    },
    {
        "name": "QR Decomposition",
        "description": "QR factorisation of 500×500 matrix (@njit → np.linalg.qr)",
        "setup": lambda: (make_matrix(500),),
        "op": lambda d: nb_qr(d[0]),
    },
    {
        "name": "FFT (real, 1M)",
        "description": "Real FFT of 2²⁰=1M-element vector (@njit → np.fft.rfft; requires Numba ≥0.55)",
        "setup": lambda: (fresh_rng().standard_normal(1 << 20),),
        "op": lambda d: nb_fft(d[0]),
    },
    {
        "name": "Sort 10M floats",
        "description": "Unstable sort of 10M random float64 values (@njit → np.sort)",
        "setup": lambda: (fresh_rng().standard_normal(10_000_000),),
        "op": lambda d: nb_sort(d[0]),
    },
]


def main():
    print(f"Python {sys.version.split()[0]} / Numba {numba.__version__} / NumPy {np.__version__}")
    results = []
    for op in OPERATIONS:
        print(f"  Benchmarking: {op['name']} ...", end=" ", flush=True)
        r = bench(op["name"], op["description"], op["setup"], op["op"])
        results.append(r)
        print(f"{r['mean_ms']:.2f} ms  ({r['memory_mb']:.2f} MB)")

    out = {
        "language": "Numba",
        "version": f"Python {sys.version.split()[0]} / Numba {numba.__version__}",
        "platform": platform.platform(),
        "operations": results,
    }
    os.makedirs("results", exist_ok=True)
    with open("results/numba_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Saved results/numba_results.json")


if __name__ == "__main__":
    main()
