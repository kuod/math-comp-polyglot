#!/usr/bin/env python3
"""Benchmark 12 numerical operations using Python (JAX) with JIT compilation."""

import os
import json
import time
import platform
import sys

import numpy as np
import jax
import jax.numpy as jnp
import jax.scipy.linalg as jsla

SEED = 42
N_WARMUP = 3
N_RUNS = 10


def fresh_np(n, m=None):
    rng = np.random.default_rng(SEED)
    return rng.standard_normal((n, m if m is not None else n))


def make_spd_np(n):
    rng = np.random.default_rng(SEED)
    A = rng.standard_normal((n, n))
    return A @ A.T + n * np.eye(n)


def mat_mb(n, m=None):
    return n * (m if m is not None else n) * 8 / 1024 / 1024


def vec_mb(n):
    return n * 8 / 1024 / 1024


def bench(name, description, mem_mb, setup_fn, op_fn):
    for _ in range(N_WARMUP):
        data = setup_fn()
        jax.block_until_ready(op_fn(data))

    times_ms = []
    for _ in range(N_RUNS):
        data = setup_fn()
        t0 = time.perf_counter()
        jax.block_until_ready(op_fn(data))
        t1 = time.perf_counter()
        times_ms.append((t1 - t0) * 1000)

    return {
        "name": name,
        "description": description,
        "mean_ms": float(np.mean(times_ms)),
        "std_ms": float(np.std(times_ms)),
        "min_ms": float(np.min(times_ms)),
        "memory_mb": float(mem_mb),
    }


OPERATIONS = [
    {
        "name": "Matrix Multiply",
        "description": "1000×1000 matrix multiply (jnp.matmul, XLA/JIT)",
        "mem_mb": mat_mb(1000),
        "setup": lambda: (jnp.array(fresh_np(1000)), jnp.array(fresh_np(1000))),
        "op": lambda d: jnp.matmul(d[0], d[1]),
    },
    {
        "name": "Matrix Inverse",
        "description": "Inversion of 500×500 SPD matrix (jnp.linalg.inv, XLA/JIT)",
        "mem_mb": mat_mb(500),
        "setup": lambda: (jnp.array(make_spd_np(500)),),
        "op": lambda d: jnp.linalg.inv(d[0]),
    },
    {
        "name": "LU Decomposition",
        "description": "LU factorisation of 500×500 matrix (jax.scipy.linalg.lu, XLA/JIT)",
        "mem_mb": mat_mb(500),
        "setup": lambda: (jnp.array(fresh_np(500)),),
        "op": lambda d: jsla.lu(d[0]),
    },
    {
        "name": "Eigenvalue Decomp",
        "description": "Full eigendecomposition of 300×300 symmetric matrix (jnp.linalg.eigh, XLA/JIT)",
        "mem_mb": mat_mb(300) + vec_mb(300),
        "setup": lambda: jnp.array((lambda A: (A + A.T) / 2)(fresh_np(300))),
        "op": lambda d: jnp.linalg.eigh(d),
    },
    {
        "name": "Cholesky",
        "description": "Cholesky factorisation of 500×500 SPD matrix (jnp.linalg.cholesky, XLA/JIT)",
        "mem_mb": mat_mb(500),
        "setup": lambda: (jnp.array(make_spd_np(500)),),
        "op": lambda d: jnp.linalg.cholesky(d[0]),
    },
    {
        "name": "SVD",
        "description": "Economy SVD of 500×300 matrix (jnp.linalg.svd, XLA/JIT; U:500×300)",
        "mem_mb": mat_mb(500, 300) + vec_mb(300) + mat_mb(300),
        "setup": lambda: (jnp.array(fresh_np(500, 300)),),
        "op": lambda d: jnp.linalg.svd(d[0], full_matrices=False),
    },
    {
        "name": "Linear System Solve",
        "description": "Solve Ax=b for 1000×1000 A, 1000 b (jnp.linalg.solve, XLA/JIT)",
        "mem_mb": vec_mb(1000),
        "setup": lambda: (
            jnp.array(make_spd_np(1000)),
            jnp.array(np.random.default_rng(SEED).standard_normal(1000)),
        ),
        "op": lambda d: jnp.linalg.solve(d[0], d[1]),
    },
    {
        "name": "Vector Dot Product",
        "description": "Dot product of two 10M-element vectors (jnp.dot, XLA/JIT)",
        "mem_mb": 8 / 1024 / 1024,
        "setup": lambda: (
            jnp.array(np.random.default_rng(SEED).standard_normal(10_000_000)),
            jnp.array(np.random.default_rng(SEED + 1).standard_normal(10_000_000)),
        ),
        "op": lambda d: jnp.dot(d[0], d[1]),
    },
    {
        "name": "Hadamard Product",
        "description": "Element-wise multiply + add on 1000×1000 matrices (XLA/JIT)",
        "mem_mb": mat_mb(1000),
        "setup": lambda: (
            jnp.array(fresh_np(1000)),
            jnp.array(fresh_np(1000)),
            jnp.array(fresh_np(1000)),
        ),
        "op": lambda d: d[0] * d[1] + d[2],
    },
    {
        "name": "QR Decomposition",
        "description": "QR factorisation of 500×500 matrix (jnp.linalg.qr, XLA/JIT)",
        "mem_mb": mat_mb(500),
        "setup": lambda: (jnp.array(fresh_np(500)),),
        "op": lambda d: jnp.linalg.qr(d[0]),
    },
    {
        "name": "FFT (real, 1M)",
        "description": "Real FFT of 2²⁰=1M-element vector (jnp.fft.rfft, XLA/JIT)",
        "mem_mb": (1 << 20) / 2 * 16 / 1024 / 1024,
        "setup": lambda: (jnp.array(np.random.default_rng(SEED).standard_normal(1 << 20)),),
        "op": lambda d: jnp.fft.rfft(d[0]),
    },
    # Sort omitted: jnp.sort uses XLA's bitonic algorithm, which is GPU-optimised
    # and ~50x slower than numpy.sort on CPU (5900ms vs 60-400ms), distorting
    # the report's heatmap colour scale for the entire Sort column.
]


def main():
    print(f"Python {sys.version.split()[0]} / JAX {jax.__version__}")
    print(f"  JAX backend: {jax.default_backend()}")
    results = []
    for op in OPERATIONS:
        print(f"  Benchmarking: {op['name']} ...", end=" ", flush=True)
        r = bench(op["name"], op["description"], op["mem_mb"], op["setup"], op["op"])
        results.append(r)
        print(f"{r['mean_ms']:.2f} ms  ({r['memory_mb']:.2f} MB)")

    out = {
        "language": "Python (JAX)",
        "version": f"Python {sys.version.split()[0]} / JAX {jax.__version__}",
        "platform": platform.platform(),
        "operations": results,
    }
    os.makedirs("results", exist_ok=True)
    with open("results/python_jax_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Saved results/python_jax_results.json")


if __name__ == "__main__":
    main()
