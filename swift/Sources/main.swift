// Benchmark 12 numerical operations using Apple Accelerate (BLAS/LAPACK/vDSP).
// Compile: swiftc -O -whole-module-optimization -o build_benchmark Sources/main.swift -framework Accelerate
import Accelerate
import Foundation

// ── Constants ─────────────────────────────────────────────────────────────────

let N_WARMUP = 3
let N_RUNS   = 10

// ── Seeded RNG (Xorshift64 + Box-Muller) ──────────────────────────────────────

var rngState: UInt64 = 42

func nextU64() -> UInt64 {
    rngState ^= rngState &<< 13
    rngState ^= rngState &>> 7
    rngState ^= rngState &<< 17
    return rngState
}

func nextDouble() -> Double {
    return Double(nextU64()) / Double(UInt64.max)
}

func nextNormal() -> Double {
    let u1 = max(nextDouble(), 1e-15)
    let u2 = nextDouble()
    return sqrt(-2.0 * log(u1)) * cos(2.0 * .pi * u2)
}

func resetRNG() { rngState = 42 }

func randMatrix(_ n: Int, _ m: Int) -> [Double] {
    resetRNG()
    return (0 ..< n * m).map { _ in nextNormal() }
}

func randVec(_ n: Int) -> [Double] {
    resetRNG()
    return (0 ..< n).map { _ in nextNormal() }
}

// Symmetric positive-definite: A*A^T + n*I  (column-major)
func makeSPD(_ n: Int) -> [Double] {
    var A = randMatrix(n, n)
    var C = [Double](repeating: 0, count: n * n)
    // C = A * A^T
    cblas_dgemm(CblasColMajor, CblasNoTrans, CblasTrans,
                Int32(n), Int32(n), Int32(n),
                1.0, &A, Int32(n), &A, Int32(n),
                0.0, &C, Int32(n))
    // Add n*I on diagonal
    for i in 0 ..< n { C[i + i * n] += Double(n) }
    return C
}

// Symmetric: (A + A^T) / 2  (column-major)
func makeSym(_ n: Int) -> [Double] {
    var A = randMatrix(n, n)
    var S = [Double](repeating: 0, count: n * n)
    for i in 0 ..< n {
        for j in 0 ..< n {
            S[i + j * n] = (A[i + j * n] + A[j + i * n]) / 2.0
        }
    }
    return S
}

// ── Timing ────────────────────────────────────────────────────────────────────

func nowMs() -> Double {
    var ts = timespec()
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts)
    return Double(ts.tv_sec) * 1000.0 + Double(ts.tv_nsec) / 1_000_000.0
}

// ── Memory: theoretical output size (Accelerate uses malloc like C++) ─────────

func matMB(_ n: Int, _ m: Int = -1) -> Double {
    let cols = m < 0 ? n : m
    return Double(n * cols * 8) / (1024.0 * 1024.0)
}
func vecMB(_ n: Int) -> Double { Double(n * 8) / (1024.0 * 1024.0) }

// ── Result type ───────────────────────────────────────────────────────────────

struct OpResult {
    let name: String
    let description: String
    let meanMs: Double
    let stdMs: Double
    let minMs: Double
    let memoryMb: Double
}

// ── Benchmark harness ─────────────────────────────────────────────────────────

func bench<D>(
    name: String, description: String, memMB: Double,
    setup: () -> D, op: (inout D) -> Void
) -> OpResult {
    // Warmup
    for _ in 0 ..< N_WARMUP {
        var d = setup()
        op(&d)
    }

    var timesMs = [Double]()
    for _ in 0 ..< N_RUNS {
        var d = setup()
        let t0 = nowMs()
        op(&d)
        timesMs.append(nowMs() - t0)
    }

    let mean = timesMs.reduce(0, +) / Double(N_RUNS)
    let variance = timesMs.map { ($0 - mean) * ($0 - mean) }.reduce(0, +) / Double(N_RUNS)
    let mn = timesMs.min()!

    let padded = name.padding(toLength: 25, withPad: " ", startingAt: 0)
    print(String(format: "  Benchmarking: %@ ... %.2f ms  (%.2f MB)", padded, mean, memMB))
    return OpResult(name: name, description: description,
                    meanMs: mean, stdMs: sqrt(variance), minMs: mn, memoryMb: memMB)
}

// ── LAPACK helpers ────────────────────────────────────────────────────────────

// Work-array query pattern shared by many LAPACK routines
func lworkQuery(_ query: (_ lwork: inout Int32) -> Void) -> Int {
    var lwork: Int32 = -1
    query(&lwork)
    return Int(lwork)
}

// ── Operations ────────────────────────────────────────────────────────────────

var results = [OpResult]()

// 1. Matrix Multiply (cblas_dgemm)
results.append(bench(
    name: "Matrix Multiply",
    description: "1000\u{d7}1000 dense matrix multiplication (cblas_dgemm)",
    memMB: matMB(1000)
) {
    (randMatrix(1000, 1000), randMatrix(1000, 1000))
} op: { d in
    var (A, B) = d
    var C = [Double](repeating: 0, count: 1000 * 1000)
    cblas_dgemm(CblasColMajor, CblasNoTrans, CblasNoTrans,
                1000, 1000, 1000,
                1.0, &A, 1000, &B, 1000,
                0.0, &C, 1000)
    withExtendedLifetime(C) {}
})

// 2. Matrix Inverse (dgetrf + dgetri)
results.append(bench(
    name: "Matrix Inverse",
    description: "Inversion of 500\u{d7}500 SPD matrix (dgetrf + dgetri)",
    memMB: matMB(500)
) {
    makeSPD(500)
} op: { A in
    var m = Int32(500), n = Int32(500), lda = Int32(500), info = Int32(0)
    var ipiv = [Int32](repeating: 0, count: 500)
    dgetrf_(&m, &n, &A, &lda, &ipiv, &info)
    var lwork = Int32(-1), wkopt = 0.0
    dgetri_(&n, &A, &lda, &ipiv, &wkopt, &lwork, &info)
    lwork = Int32(wkopt)
    var work = [Double](repeating: 0, count: Int(lwork))
    dgetri_(&n, &A, &lda, &ipiv, &work, &lwork, &info)
    withExtendedLifetime(A) {}
})

// 3. LU Decomposition (dgetrf)
results.append(bench(
    name: "LU Decomposition",
    description: "LU factorisation of 500\u{d7}500 matrix (dgetrf)",
    memMB: matMB(500)
) {
    randMatrix(500, 500)
} op: { A in
    var m = Int32(500), n = Int32(500), lda = Int32(500), info = Int32(0)
    var ipiv = [Int32](repeating: 0, count: 500)
    dgetrf_(&m, &n, &A, &lda, &ipiv, &info)
    withExtendedLifetime(A) {}
})

// 4. Eigenvalue Decomposition (dsyev — symmetric)
results.append(bench(
    name: "Eigenvalue Decomp",
    description: "Full eigendecomposition of 300\u{d7}300 symmetric matrix (dsyev)",
    memMB: matMB(300) + vecMB(300)
) {
    makeSym(300)
} op: { A in
    var jobz: Int8 = Int8(UInt8(ascii: "V"))
    var uplo: Int8 = Int8(UInt8(ascii: "U"))
    var n = Int32(300), lda = Int32(300), info = Int32(0)
    var w = [Double](repeating: 0, count: 300)
    var lwork = Int32(-1), wkopt = 0.0
    dsyev_(&jobz, &uplo, &n, &A, &lda, &w, &wkopt, &lwork, &info)
    lwork = Int32(wkopt)
    var work = [Double](repeating: 0, count: Int(lwork))
    dsyev_(&jobz, &uplo, &n, &A, &lda, &w, &work, &lwork, &info)
    withExtendedLifetime(w) {}
})

// 5. Cholesky (dpotrf)
results.append(bench(
    name: "Cholesky",
    description: "Cholesky factorisation of 500\u{d7}500 SPD matrix (dpotrf)",
    memMB: matMB(500)
) {
    makeSPD(500)
} op: { A in
    var uplo: Int8 = Int8(UInt8(ascii: "U"))
    var n = Int32(500), lda = Int32(500), info = Int32(0)
    dpotrf_(&uplo, &n, &A, &lda, &info)
    withExtendedLifetime(A) {}
})

// 6. SVD (dgesdd — divide and conquer)
results.append(bench(
    name: "SVD",
    description: "Full SVD of 500\u{d7}300 matrix (dgesdd, thin)",
    memMB: matMB(500, 300) + vecMB(300) + matMB(300)
) {
    randMatrix(500, 300)
} op: { A in
    var jobz: Int8 = Int8(UInt8(ascii: "S"))
    var m = Int32(500), n = Int32(300), lda = Int32(500)
    var ldu = Int32(500), ldvt = Int32(300), info = Int32(0)
    var s = [Double](repeating: 0, count: 300)
    var u = [Double](repeating: 0, count: 500 * 300)
    var vt = [Double](repeating: 0, count: 300 * 300)
    var iwork = [Int32](repeating: 0, count: 8 * 300)
    var lwork = Int32(-1), wkopt = 0.0
    dgesdd_(&jobz, &m, &n, &A, &lda, &s, &u, &ldu, &vt, &ldvt,
            &wkopt, &lwork, &iwork, &info)
    lwork = Int32(wkopt)
    var work = [Double](repeating: 0, count: Int(lwork))
    dgesdd_(&jobz, &m, &n, &A, &lda, &s, &u, &ldu, &vt, &ldvt,
            &work, &lwork, &iwork, &info)
    withExtendedLifetime(s) {}
})

// 7. Linear System Solve (dpotrs using Cholesky — SPD system)
results.append(bench(
    name: "Linear System Solve",
    description: "Solve Ax=b for 1000\u{d7}1000 SPD A (dpotrf + dpotrs)",
    memMB: vecMB(1000)
) {
    (makeSPD(1000), randVec(1000))
} op: { d in
    var (A, b) = d
    var uplo: Int8 = Int8(UInt8(ascii: "U"))
    var n = Int32(1000), nrhs = Int32(1), lda = Int32(1000), info = Int32(0)
    dpotrf_(&uplo, &n, &A, &lda, &info)
    var ldb = n
    dpotrs_(&uplo, &n, &nrhs, &A, &lda, &b, &ldb, &info)
    withExtendedLifetime(b) {}
})

// 8. Vector Dot Product (cblas_ddot)
results.append(bench(
    name: "Vector Dot Product",
    description: "Dot product of two 10M-element vectors (cblas_ddot)",
    memMB: vecMB(1)
) {
    (randVec(10_000_000), randVec(10_000_000))
} op: { d in
    var (x, y) = d
    let v = cblas_ddot(10_000_000, &x, 1, &y, 1)
    withExtendedLifetime(v) {}
})

// 9. Hadamard Product (vDSP element-wise multiply + add)
results.append(bench(
    name: "Hadamard Product",
    description: "Element-wise multiply + add on 1000\u{d7}1000 matrices (vDSP)",
    memMB: matMB(1000)
) {
    (randMatrix(1000, 1000), randMatrix(1000, 1000), randMatrix(1000, 1000))
} op: { d in
    var (A, B, C) = d
    var result = [Double](repeating: 0, count: 1000 * 1000)
    let n = vDSP_Length(1000 * 1000)
    vDSP_vmulD(&A, 1, &B, 1, &result, 1, n)
    var out = [Double](repeating: 0, count: 1000 * 1000)
    vDSP_vaddD(&result, 1, &C, 1, &out, 1, n)
    withExtendedLifetime(out) {}
})

// 10. QR Decomposition (dgeqrf)
results.append(bench(
    name: "QR Decomposition",
    description: "QR factorisation of 500\u{d7}500 matrix (dgeqrf, compact form)",
    memMB: matMB(500)
) {
    randMatrix(500, 500)
} op: { A in
    var m = Int32(500), n = Int32(500), lda = Int32(500), info = Int32(0)
    var tau = [Double](repeating: 0, count: 500)
    var lwork = Int32(-1), wkopt = 0.0
    dgeqrf_(&m, &n, &A, &lda, &tau, &wkopt, &lwork, &info)
    lwork = Int32(wkopt)
    var work = [Double](repeating: 0, count: Int(lwork))
    dgeqrf_(&m, &n, &A, &lda, &tau, &work, &lwork, &info)
    withExtendedLifetime(tau) {}
})

// 11. FFT (real, 1M) — vDSP real-to-complex FFT
results.append(bench(
    name: "FFT (real, 1M)",
    description: "Real FFT of 2\u{00b2}\u{2070}=1M-element vector (vDSP Accelerate)",
    memMB: vecMB((1 << 20) / 2 + 1) * 2   // complex output
) {
    randVec(1 << 20)
} op: { signal in
    let log2N = vDSP_Length(20)
    let n = 1 << 20
    let nOver2 = n / 2

    guard let setup = vDSP_create_fftsetupD(log2N, FFTRadix(kFFTRadix2)) else { return }
    defer { vDSP_destroy_fftsetupD(setup) }

    var realOut = [Double](repeating: 0, count: nOver2)
    var imagOut = [Double](repeating: 0, count: nOver2)

    signal.withUnsafeBufferPointer { sigBuf in
        realOut.withUnsafeMutableBufferPointer { rBuf in
            imagOut.withUnsafeMutableBufferPointer { iBuf in
                var splitComplex = DSPDoubleSplitComplex(
                    realp: rBuf.baseAddress!,
                    imagp: iBuf.baseAddress!)
                // Pack real signal into split-complex
                sigBuf.baseAddress!.withMemoryRebound(to: DSPDoubleComplex.self,
                                                       capacity: nOver2) { cPtr in
                    vDSP_ctozD(cPtr, 2, &splitComplex, 1, vDSP_Length(nOver2))
                }
                vDSP_fft_zripD(setup, &splitComplex, 1, log2N,
                               FFTDirection(kFFTDirection_Forward))
            }
        }
    }
    withExtendedLifetime(realOut) {}
})

// 12. Sort 10M floats (Swift Array.sort — introsort)
results.append(bench(
    name: "Sort 10M floats",
    description: "Unstable sort of 10M random float64 values (Swift Array.sort)",
    memMB: 0.0   // in-place
) {
    randVec(10_000_000)
} op: { v in
    v.sort()
    withExtendedLifetime(v) {}
})

// ── JSON output ───────────────────────────────────────────────────────────────

func escapeJSON(_ s: String) -> String { s.replacingOccurrences(of: "\"", with: "\\\"") }

let opsJSON = results.map { r -> String in
    """
        {
          "name": "\(escapeJSON(r.name))",
          "description": "\(escapeJSON(r.description))",
          "mean_ms": \(r.meanMs),
          "std_ms": \(r.stdMs),
          "min_ms": \(r.minMs),
          "memory_mb": \(r.memoryMb)
        }
    """
}.joined(separator: ",\n")

let swiftVersion = "Swift / Accelerate (Apple vDSP+BLAS+LAPACK)"
let jsonOut = """
{
  "language": "Swift",
  "version": "\(swiftVersion)",
  "platform": "macOS arm64",
  "operations": [
\(opsJSON)
  ]
}
"""

let fm = FileManager.default
try! fm.createDirectory(atPath: "results", withIntermediateDirectories: true)
try! jsonOut.write(toFile: "results/swift_results.json", atomically: true, encoding: .utf8)
print("Saved results/swift_results.json")
