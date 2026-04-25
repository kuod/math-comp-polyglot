// Benchmark 10 numerical operations using Eigen
#include <Eigen/Dense>
#include <Eigen/QR>
#include <Eigen/LU>
#include <Eigen/Cholesky>
#include <Eigen/SVD>
#include <Eigen/Eigenvalues>
#include <unsupported/Eigen/FFT>
#include <algorithm>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace Eigen;
using Clock = std::chrono::high_resolution_clock;

// ── Anti-optimisation sink ─────────────────────────────────────────────────────
// Prevents the compiler from eliding computations whose results aren't used.
static volatile double g_sink = 0.0;
template<typename T>
void do_not_optimise(const T& val) {
    // Touch one element so the whole computation is retained.
    if constexpr (std::is_arithmetic_v<T>) {
        g_sink += (double)val;
    } else {
        g_sink += val.sum();   // works for Eigen matrices/vectors
    }
}

// ── RNG / matrix builders ─────────────────────────────────────────────────────

static constexpr unsigned SEED = 42;

MatrixXd rand_matrix(int n, int m) {
    std::mt19937_64 rng(SEED);
    std::normal_distribution<double> dist(0.0, 1.0);
    MatrixXd A(n, m);
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < m; ++j)
            A(i, j) = dist(rng);
    return A;
}

VectorXd rand_vec(int n) {
    std::mt19937_64 rng(SEED + 1);
    std::normal_distribution<double> dist(0.0, 1.0);
    VectorXd v(n);
    for (int i = 0; i < n; ++i) v(i) = dist(rng);
    return v;
}

MatrixXd make_spd(int n) {
    MatrixXd A = rand_matrix(n, n);
    return A * A.transpose() + (double)n * MatrixXd::Identity(n, n);
}

MatrixXd make_sym(int n) {
    MatrixXd A = rand_matrix(n, n);
    return (A + A.transpose()) * 0.5;
}

// ── Simple JSON helpers ───────────────────────────────────────────────────────

static std::string jstr(const std::string& s)  { return "\"" + s + "\""; }
static std::string jkv(const std::string& k, double v) {
    std::ostringstream o; o << "\"" << k << "\": " << v; return o.str();
}
static std::string jkvs(const std::string& k, const std::string& v) {
    return "\"" + k + "\": \"" + v + "\"";
}

// ── Memory helpers ────────────────────────────────────────────────────────────
// Eigen uses malloc() directly, so operator new tracking can't capture it.
// We compute output allocation size to keep the metric comparable with other
// languages (Python tracemalloc, Julia @allocated, R gc() — all capture the
// output matrix allocation and any intermediates).
static double mb(size_t bytes) { return (double)bytes / (1024.0 * 1024.0); }
static double mat_mb(int n, int m = -1) {
    if (m < 0) m = n;
    return mb((size_t)n * m * sizeof(double));
}
static double vec_mb(int n) { return mb((size_t)n * sizeof(double)); }

// ── Benchmark harness ─────────────────────────────────────────────────────────

static constexpr int N_WARMUP = 3;
static constexpr int N_RUNS   = 10;

struct OpResult {
    std::string name, description;
    double mean_ms, std_ms, min_ms, memory_mb;
};

template<typename Setup, typename Op>
OpResult bench(const std::string& name, const std::string& desc,
               double output_memory_mb, Setup setup, Op op) {
    for (int i = 0; i < N_WARMUP; ++i) { auto d = setup(); op(d); }

    std::vector<double> times_ms(N_RUNS);

    for (int i = 0; i < N_RUNS; ++i) {
        auto data = setup();
        auto t0 = Clock::now();
        op(data);
        auto t1 = Clock::now();
        times_ms[i] = std::chrono::duration<double, std::milli>(t1 - t0).count();
    }

    double sum = 0; for (double t : times_ms) sum += t;
    double mean = sum / N_RUNS;
    double var  = 0; for (double t : times_ms) var += (t - mean)*(t - mean);
    double mn   = times_ms[0]; for (double t : times_ms) mn = std::min(mn, t);

    std::printf("  Benchmarking: %-25s ... %.2f ms  (%.2f MB)\n",
                name.c_str(), mean, output_memory_mb);

    return { name, desc, mean, std::sqrt(var / N_RUNS), mn, output_memory_mb };
}

// ── Main ──────────────────────────────────────────────────────────────────────

int main() {
    std::string version = "C++17 / Eigen " +
        std::to_string(EIGEN_WORLD_VERSION) + "." +
        std::to_string(EIGEN_MAJOR_VERSION) + "." +
        std::to_string(EIGEN_MINOR_VERSION);
    std::cout << version << "\n";

    std::vector<OpResult> results;

    // 1. Matrix Multiply — result: 1000×1000
    results.push_back(bench(
        "Matrix Multiply", "1000×1000 dense matrix multiplication (A * B)",
        mat_mb(1000),
        []{ return std::make_pair(rand_matrix(1000,1000), rand_matrix(1000,1000)); },
        [](auto& d){ MatrixXd c = d.first * d.second; do_not_optimise(c); }
    ));

    // 2. Matrix Inverse — result: 500×500
    results.push_back(bench(
        "Matrix Inverse", "Inversion of 500×500 SPD matrix",
        mat_mb(500),
        []{ return make_spd(500); },
        [](auto& a){ MatrixXd inv = a.inverse(); do_not_optimise(inv); }
    ));

    // 3. LU — stores L+U in 500×500 matrix
    results.push_back(bench(
        "LU Decomposition", "LU factorisation of 500×500 matrix",
        mat_mb(500),
        []{ return rand_matrix(500, 500); },
        [](auto& a){ PartialPivLU<MatrixXd> lu(a); do_not_optimise(lu.matrixLU()); }
    ));

    // 4. Eigenvalue — eigenvectors 300×300 + eigenvalues 300
    results.push_back(bench(
        "Eigenvalue Decomp", "Full eigendecomposition of 300×300 symmetric matrix",
        mat_mb(300) + vec_mb(300),
        []{ return make_sym(300); },
        [](auto& a){ SelfAdjointEigenSolver<MatrixXd> es(a); do_not_optimise(es.eigenvalues()); }
    ));

    // 5. Cholesky — lower triangle 500×500
    results.push_back(bench(
        "Cholesky", "Cholesky factorisation of 500×500 SPD matrix",
        mat_mb(500),
        []{ return make_spd(500); },
        [](auto& a){ LLT<MatrixXd> llt(a); do_not_optimise(llt.matrixL().toDenseMatrix()); }
    ));

    // 6. SVD — U:500×300, S:300, Vt:300×300
    results.push_back(bench(
        "SVD", "Economy SVD of 500×300 matrix (ComputeThinU|ComputeThinV; U:500×300)",
        mat_mb(500,300) + vec_mb(300) + mat_mb(300),
        []{ return rand_matrix(500, 300); },
        [](auto& a){ BDCSVD<MatrixXd> svd(a, ComputeThinU | ComputeThinV); do_not_optimise(svd.singularValues()); }
    ));

    // 7. Linear Solve — result: vector 1000
    results.push_back(bench(
        "Linear System Solve", "Solve Ax=b for 1000×1000 A, 1000 b",
        vec_mb(1000),
        []{ return std::make_pair(make_spd(1000), rand_vec(1000)); },
        [](auto& d){ VectorXd x = d.first.llt().solve(d.second); do_not_optimise(x); }
    ));

    // 8. Vector Dot Product — result: scalar
    results.push_back(bench(
        "Vector Dot Product", "Dot product of two 10M-element vectors",
        vec_mb(1),
        []{ return std::make_pair(rand_vec(10'000'000), rand_vec(10'000'000)); },
        [](auto& d){ double v = d.first.dot(d.second); do_not_optimise(v); }
    ));

    // 9. Hadamard — result: 1000×1000
    results.push_back(bench(
        "Hadamard Product", "Element-wise multiply + add on 1000×1000 matrices",
        mat_mb(1000),
        []{ return std::make_tuple(rand_matrix(1000,1000), rand_matrix(1000,1000), rand_matrix(1000,1000)); },
        [](auto& d){
            MatrixXd r = std::get<0>(d).cwiseProduct(std::get<1>(d)) + std::get<2>(d);
            do_not_optimise(r);
        }
    ));

    // 10. QR — Q:500×500 + R:500×500
    results.push_back(bench(
        "QR Decomposition", "QR factorisation of 500×500 matrix",
        mat_mb(500),
        []{ return rand_matrix(500, 500); },
        [](auto& a){ HouseholderQR<MatrixXd> qr(a); do_not_optimise(qr.matrixQR()); }
    ));

    // 11. FFT (real, 1M)
    results.push_back(bench(
        "FFT (real, 1M)", "Real FFT of 2^20=1M-element vector (Eigen::FFT / KissFFT)",
        (vec_mb(1 << 20) / 2.0 + vec_mb(1)) * 2,  // ~complex output size
        []{ return rand_vec(1 << 20); },
        [](auto& v) {
            Eigen::FFT<double> fft;
            std::vector<std::complex<double>> out;
            std::vector<double> in(v.data(), v.data() + v.size());
            fft.fwd(out, in);
            do_not_optimise(out[0].real());
        }
    ));

    // 12. Sort 10M floats
    results.push_back(bench(
        "Sort 10M floats", "Unstable sort of 10M random float64 values (std::sort)",
        0.0,
        []{ return rand_vec(10'000'000); },
        [](auto& v) {
            std::vector<double> data(v.data(), v.data() + v.size());
            std::sort(data.begin(), data.end());
            do_not_optimise(data[0]);
        }
    ));

    // ── Write JSON ────────────────────────────────────────────────────────────
    std::filesystem::create_directories("results");
    std::ofstream out("results/cpp_results.json");
    out << "{\n";
    out << "  " << jkvs("language", "C++") << ",\n";
    out << "  " << jkvs("version", version) << ",\n";
    out << "  " << jkvs("platform", "native") << ",\n";
    out << "  \"operations\": [\n";
    for (size_t i = 0; i < results.size(); ++i) {
        const auto& r = results[i];
        out << "    {\n";
        out << "      " << jkvs("name", r.name) << ",\n";
        out << "      " << jkvs("description", r.description) << ",\n";
        out << "      " << jkv("mean_ms", r.mean_ms) << ",\n";
        out << "      " << jkv("std_ms", r.std_ms) << ",\n";
        out << "      " << jkv("min_ms", r.min_ms) << ",\n";
        out << "      " << jkv("memory_mb", r.memory_mb) << "\n";
        out << "    }" << (i + 1 < results.size() ? "," : "") << "\n";
    }
    out << "  ]\n}\n";
    out.close();
    std::cout << "Saved results/cpp_results.json\n";
    return 0;
}
