/*
 * C benchmark — 12 numerical/linear-algebra operations
 * Uses Apple Accelerate (CBLAS + LAPACK + vDSP)
 *
 * Build:
 *   clang -O3 -march=native -framework Accelerate \
 *         -DACCELERATE_NEW_LAPACK \
 *         -Wno-deprecated-declarations \
 *         -o c/c-bench c/benchmark.c -lm
 *
 * Run from project root:
 *   ./c/c-bench
 */

#define ACCELERATE_NEW_LAPACK 1
#include <Accelerate/Accelerate.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <time.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */

#define SEED     42
#define N_WARMUP  3
#define N_RUNS   10

/* ── Anti-optimisation sink ─────────────────────────────────────────────────── */

static volatile double g_sink = 0.0;

/* ── Timing ─────────────────────────────────────────────────────────────────── */

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

/* ── Memory helpers ─────────────────────────────────────────────────────────── */

static double mat_mb(int n, int m) { return (double)n * m * 8.0 / (1024.0 * 1024.0); }
static double vec_mb(int n)        { return (double)n       * 8.0 / (1024.0 * 1024.0); }

/* ── LCG RNG — reproducible standard-normal via Box-Muller ─────────────────── */

typedef struct { uint64_t state; } LCG;

static LCG lcg_init(uint64_t seed) { LCG r; r.state = seed; return r; }

/* LCG multiplier / increment from Knuth MMIX */
static double lcg_uniform(LCG *r) {
    r->state = r->state * 6364136223846793005ULL + 1442695040888963407ULL;
    /* upper 53 bits -> [0,1) */
    return (double)(r->state >> 11) * (1.0 / (double)(1ULL << 53));
}

/* Box-Muller; consumes two uniforms, returns one normal */
static double lcg_normal(LCG *r) {
    double u1, u2;
    do { u1 = lcg_uniform(r); } while (u1 == 0.0);
    u2 = lcg_uniform(r);
    return sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
}

/* Fill n doubles with N(0,1) from a fresh LCG seeded with `seed` */
static void fill_normal(double *buf, int n, uint64_t seed) {
    LCG r = lcg_init(seed);
    for (int i = 0; i < n; i++) buf[i] = lcg_normal(&r);
}

/* Fill n doubles with U(0,1) from a fresh LCG seeded with `seed` */
static void fill_uniform(double *buf, int n, uint64_t seed) {
    LCG r = lcg_init(seed);
    for (int i = 0; i < n; i++) buf[i] = lcg_uniform(&r);
}

/* Build column-major SPD matrix: A = B*B^T + n*I, B is n x n normal */
static void make_spd(double *A, int n, uint64_t seed) {
    double *B = (double *)malloc((size_t)n * n * sizeof(double));
    fill_normal(B, n * n, seed);
    /* A = B * B^T */
    cblas_dgemm(CblasColMajor, CblasNoTrans, CblasTrans,
                n, n, n, 1.0, B, n, B, n, 0.0, A, n);
    /* A += n*I */
    for (int i = 0; i < n; i++) A[i * n + i] += (double)n;
    free(B);
}

/* Build column-major symmetric matrix: sym = (A + A^T)/2 */
static void make_sym(double *S, int n, uint64_t seed) {
    double *A = (double *)malloc((size_t)n * n * sizeof(double));
    fill_normal(A, n * n, seed);
    for (int j = 0; j < n; j++)
        for (int i = 0; i < n; i++)
            S[j * n + i] = 0.5 * (A[j * n + i] + A[i * n + j]);
    free(A);
}

/* ── Benchmark result ────────────────────────────────────────────────────────── */

typedef struct {
    char   name[64];
    char   description[160];
    double mean_ms;
    double std_ms;
    double min_ms;
    double memory_mb;
} OpResult;

/* ── Statistics from raw times ──────────────────────────────────────────────── */

static void compute_stats(double *times, int n,
                           double *mean, double *std, double *mn) {
    double sum = 0.0;
    *mn = times[0];
    for (int i = 0; i < n; i++) {
        sum += times[i];
        if (times[i] < *mn) *mn = times[i];
    }
    *mean = sum / n;
    double var = 0.0;
    for (int i = 0; i < n; i++) {
        double d = times[i] - *mean;
        var += d * d;
    }
    *std = sqrt(var / n);
}

/* ── Comparison function for qsort ─────────────────────────────────────────── */

static int cmp_double(const void *a, const void *b) {
    double x = *(const double *)a;
    double y = *(const double *)b;
    if (x < y) return -1;
    if (x > y) return  1;
    return 0;
}

/* ══════════════════════════════════════════════════════════════════════════════
 *  main
 * ══════════════════════════════════════════════════════════════════════════════ */

int main(void) {

    /* ── Version / platform ─────────────────────────────────────────────────── */
    char version_str[128];
    snprintf(version_str, sizeof(version_str), "C (clang/Accelerate)");

    struct utsname uts;
    uname(&uts);
    char platform_str[256];
    snprintf(platform_str, sizeof(platform_str),
             "%s %s %s", uts.sysname, uts.release, uts.machine);

    printf("C benchmark -- %s\n", version_str);
    printf("Platform: %s\n\n", platform_str);

    OpResult results[12];
    int nresults = 0;
    double times[N_RUNS];

    /* ────────────────────────────────────────────────────────────────────────
     * 1. Matrix Multiply  — cblas_dgemm  1000x1000
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 1000;
        double *A = (double *)malloc((size_t)N * N * sizeof(double));
        double *B = (double *)malloc((size_t)N * N * sizeof(double));
        double *C = (double *)malloc((size_t)N * N * sizeof(double));
        fill_normal(A, N * N, SEED);
        fill_normal(B, N * N, SEED + 1);

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++)
            cblas_dgemm(CblasColMajor, CblasNoTrans, CblasNoTrans,
                        N, N, N, 1.0, A, N, B, N, 0.0, C, N);

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            double t0 = now_ms();
            cblas_dgemm(CblasColMajor, CblasNoTrans, CblasNoTrans,
                        N, N, N, 1.0, A, N, B, N, 0.0, C, N);
            times[r] = now_ms() - t0;
            g_sink += C[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Matrix Multiply", sizeof(op->name) - 1);
        strncpy(op->description, "1000x1000 DGEMM (CBLAS/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(N, N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A); free(B); free(C);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 2. Matrix Inverse  — DGETRF + DGETRI  500x500 SPD
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 500;
        double *A_orig = (double *)malloc((size_t)N * N * sizeof(double));
        double *A      = (double *)malloc((size_t)N * N * sizeof(double));
        int   *ipiv    = (int *)malloc((size_t)N * sizeof(int));
        make_spd(A_orig, N, SEED);

        /* Query workspace size */
        int lwork_q = -1, info = 0, n = N, lda = N;
        double work_q;
        dgetri_(&n, A, &lda, ipiv, &work_q, &lwork_q, &info);
        int lwork = (int)work_q;
        double *work = (double *)malloc((size_t)lwork * sizeof(double));

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            dgetrf_(&n, &n, A, &lda, ipiv, &info);
            dgetri_(&n, A, &lda, ipiv, work, &lwork, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            double t0 = now_ms();
            dgetrf_(&n, &n, A, &lda, ipiv, &info);
            dgetri_(&n, A, &lda, ipiv, work, &lwork, &info);
            times[r] = now_ms() - t0;
            g_sink += A[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Matrix Inverse", sizeof(op->name) - 1);
        strncpy(op->description, "Inversion of 500x500 SPD matrix (DGETRF+DGETRI/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(N, N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A_orig); free(A); free(ipiv); free(work);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 3. LU Decomposition  — DGETRF  500x500
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 500;
        double *A_orig = (double *)malloc((size_t)N * N * sizeof(double));
        double *A      = (double *)malloc((size_t)N * N * sizeof(double));
        int   *ipiv    = (int *)malloc((size_t)N * sizeof(int));
        fill_normal(A_orig, N * N, SEED);

        int n = N, lda = N, info = 0;

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            dgetrf_(&n, &n, A, &lda, ipiv, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            double t0 = now_ms();
            dgetrf_(&n, &n, A, &lda, ipiv, &info);
            times[r] = now_ms() - t0;
            g_sink += A[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "LU Decomposition", sizeof(op->name) - 1);
        strncpy(op->description, "LU factorisation of 500x500 matrix (DGETRF/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(N, N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A_orig); free(A); free(ipiv);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 4. Eigenvalue Decomp  — DSYEV  300x300 symmetric
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 300;
        double *sym_orig = (double *)malloc((size_t)N * N * sizeof(double));
        double *A        = (double *)malloc((size_t)N * N * sizeof(double));
        double *w        = (double *)malloc((size_t)N * sizeof(double));
        make_sym(sym_orig, N, SEED);

        /* Query workspace */
        char jobz = 'V', uplo = 'U';
        int n = N, lda = N, info = 0, lwork_q = -1;
        double work_q;
        dsyev_(&jobz, &uplo, &n, A, &lda, w, &work_q, &lwork_q, &info);
        int lwork = (int)work_q;
        double *work = (double *)malloc((size_t)lwork * sizeof(double));

        /* warmup */
        for (int ww = 0; ww < N_WARMUP; ww++) {
            memcpy(A, sym_orig, (size_t)N * N * sizeof(double));
            dsyev_(&jobz, &uplo, &n, A, &lda, w, work, &lwork, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, sym_orig, (size_t)N * N * sizeof(double));
            double t0 = now_ms();
            dsyev_(&jobz, &uplo, &n, A, &lda, w, work, &lwork, &info);
            times[r] = now_ms() - t0;
            g_sink += w[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Eigenvalue Decomp", sizeof(op->name) - 1);
        strncpy(op->description, "Full eigendecomposition of 300x300 symmetric matrix (DSYEV/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(N, N) + vec_mb(N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(sym_orig); free(A); free(w); free(work);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 5. Cholesky  — DPOTRF  500x500 SPD
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 500;
        double *spd_orig = (double *)malloc((size_t)N * N * sizeof(double));
        double *A        = (double *)malloc((size_t)N * N * sizeof(double));
        make_spd(spd_orig, N, SEED);

        char uplo = 'L';
        int n = N, lda = N, info = 0;

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(A, spd_orig, (size_t)N * N * sizeof(double));
            dpotrf_(&uplo, &n, A, &lda, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, spd_orig, (size_t)N * N * sizeof(double));
            double t0 = now_ms();
            dpotrf_(&uplo, &n, A, &lda, &info);
            times[r] = now_ms() - t0;
            g_sink += A[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Cholesky", sizeof(op->name) - 1);
        strncpy(op->description, "Cholesky factorisation of 500x500 SPD matrix (DPOTRF/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(N, N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(spd_orig); free(A);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 6. SVD  — DGESDD  500x300 ("economy" S)
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int M = 500, N = 300;
        int minmn = (M < N) ? M : N;  /* 300 */
        double *A_orig = (double *)malloc((size_t)M * N * sizeof(double));
        double *A      = (double *)malloc((size_t)M * N * sizeof(double));
        double *S      = (double *)malloc((size_t)minmn * sizeof(double));
        double *U      = (double *)malloc((size_t)M * minmn * sizeof(double));
        double *VT     = (double *)malloc((size_t)minmn * N * sizeof(double));
        fill_normal(A_orig, M * N, SEED);

        char jobz = 'S';
        int m = M, n = N, lda = M, ldu = M, ldvt = minmn, info = 0;
        int *iwork = (int *)malloc((size_t)(8 * minmn) * sizeof(int));

        /* Query workspace */
        int lwork_q = -1;
        double work_q;
        memcpy(A, A_orig, (size_t)M * N * sizeof(double));
        dgesdd_(&jobz, &m, &n, A, &lda, S, U, &ldu, VT, &ldvt,
                &work_q, &lwork_q, iwork, &info);
        int lwork = (int)work_q;
        double *work = (double *)malloc((size_t)lwork * sizeof(double));

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(A, A_orig, (size_t)M * N * sizeof(double));
            dgesdd_(&jobz, &m, &n, A, &lda, S, U, &ldu, VT, &ldvt,
                    work, &lwork, iwork, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, A_orig, (size_t)M * N * sizeof(double));
            double t0 = now_ms();
            dgesdd_(&jobz, &m, &n, A, &lda, S, U, &ldu, VT, &ldvt,
                    work, &lwork, iwork, &info);
            times[r] = now_ms() - t0;
            g_sink += S[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "SVD", sizeof(op->name) - 1);
        strncpy(op->description, "Economy SVD of 500x300 matrix (DGESDD/Accelerate; U:500x300)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(M, N) + vec_mb(minmn) + mat_mb(minmn, minmn);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A_orig); free(A); free(S); free(U); free(VT); free(iwork); free(work);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 7. Linear System Solve  — DGESV  1000x1000
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 1000;
        double *A_orig = (double *)malloc((size_t)N * N * sizeof(double));
        double *b_orig = (double *)malloc((size_t)N * sizeof(double));
        double *A      = (double *)malloc((size_t)N * N * sizeof(double));
        double *b      = (double *)malloc((size_t)N * sizeof(double));
        int   *ipiv    = (int *)malloc((size_t)N * sizeof(int));
        make_spd(A_orig, N, SEED);
        fill_normal(b_orig, N, SEED + 99);

        int n = N, nrhs = 1, lda = N, ldb = N, info = 0;

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            memcpy(b, b_orig, (size_t)N * sizeof(double));
            dgesv_(&n, &nrhs, A, &lda, ipiv, b, &ldb, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            memcpy(b, b_orig, (size_t)N * sizeof(double));
            double t0 = now_ms();
            dgesv_(&n, &nrhs, A, &lda, ipiv, b, &ldb, &info);
            times[r] = now_ms() - t0;
            g_sink += b[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Linear System Solve", sizeof(op->name) - 1);
        strncpy(op->description, "Solve Ax=b for 1000x1000 A, 1000 b (DGESV/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = vec_mb(N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A_orig); free(b_orig); free(A); free(b); free(ipiv);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 8. Vector Dot Product  — cblas_ddot  10M
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 10000000;
        double *a = (double *)malloc((size_t)N * sizeof(double));
        double *b = (double *)malloc((size_t)N * sizeof(double));
        fill_normal(a, N, SEED);
        fill_normal(b, N, SEED + 1);

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++)
            g_sink += cblas_ddot(N, a, 1, b, 1);

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            double t0 = now_ms();
            double v = cblas_ddot(N, a, 1, b, 1);
            times[r] = now_ms() - t0;
            g_sink += v;
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Vector Dot Product", sizeof(op->name) - 1);
        strncpy(op->description, "Dot product of two 10M-element vectors (cblas_ddot/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = 8.0 / (1024.0 * 1024.0);  /* scalar output */
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(a); free(b);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 9. Hadamard Product  — element-wise multiply+add  1000x1000
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 1000 * 1000;
        double *A = (double *)malloc((size_t)N * sizeof(double));
        double *B = (double *)malloc((size_t)N * sizeof(double));
        double *D = (double *)malloc((size_t)N * sizeof(double));
        double *C = (double *)malloc((size_t)N * sizeof(double));
        fill_normal(A, N, SEED);
        fill_normal(B, N, SEED + 1);
        fill_normal(D, N, SEED + 2);

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            for (int i = 0; i < N; i++) C[i] = A[i] * B[i] + D[i];
            g_sink += C[0];
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            double t0 = now_ms();
            for (int i = 0; i < N; i++) C[i] = A[i] * B[i] + D[i];
            times[r] = now_ms() - t0;
            g_sink += C[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Hadamard Product", sizeof(op->name) - 1);
        strncpy(op->description, "Element-wise multiply + add on 1000x1000 matrices", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(1000, 1000);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A); free(B); free(D); free(C);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 10. QR Decomposition  — DGEQRF  500x500
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 500;
        double *A_orig = (double *)malloc((size_t)N * N * sizeof(double));
        double *A      = (double *)malloc((size_t)N * N * sizeof(double));
        double *tau    = (double *)malloc((size_t)N * sizeof(double));
        fill_normal(A_orig, N * N, SEED);

        /* Query workspace */
        int m = N, n = N, lda = N, lwork_q = -1, info = 0;
        double work_q;
        memcpy(A, A_orig, (size_t)N * N * sizeof(double));
        dgeqrf_(&m, &n, A, &lda, tau, &work_q, &lwork_q, &info);
        int lwork = (int)work_q;
        double *work = (double *)malloc((size_t)lwork * sizeof(double));

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            dgeqrf_(&m, &n, A, &lda, tau, work, &lwork, &info);
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(A, A_orig, (size_t)N * N * sizeof(double));
            double t0 = now_ms();
            dgeqrf_(&m, &n, A, &lda, tau, work, &lwork, &info);
            times[r] = now_ms() - t0;
            g_sink += A[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "QR Decomposition", sizeof(op->name) - 1);
        strncpy(op->description, "QR factorisation of 500x500 matrix (DGEQRF/Accelerate)", sizeof(op->description) - 1);
        op->memory_mb = mat_mb(N, N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(A_orig); free(A); free(tau); free(work);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 11. FFT (real, 1M)  — vDSP_fft_zripD
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N_FFT = 1 << 20;  /* 1M = 2^20 */
        const int LOG2N = 20;
        const int HALF  = N_FFT / 2;

        double *x = (double *)malloc((size_t)N_FFT * sizeof(double));
        fill_uniform(x, N_FFT, SEED);

        /* Split-complex buffers — allocated once outside the loop */
        double *realp = (double *)malloc((size_t)HALF * sizeof(double));
        double *imagp = (double *)malloc((size_t)HALF * sizeof(double));
        DSPDoubleSplitComplex z = { realp, imagp };

        /* Setup — outside timing */
        FFTSetupD fft_setup = vDSP_create_fftsetupD(LOG2N, FFT_RADIX2);

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            vDSP_ctozD((DSPDoubleComplex *)x, 2, &z, 1, HALF);
            vDSP_fft_zripD(fft_setup, &z, 1, LOG2N, FFT_FORWARD);
            g_sink += realp[0];
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            double t0 = now_ms();
            vDSP_ctozD((DSPDoubleComplex *)x, 2, &z, 1, HALF);
            vDSP_fft_zripD(fft_setup, &z, 1, LOG2N, FFT_FORWARD);
            times[r] = now_ms() - t0;
            g_sink += realp[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "FFT (real, 1M)", sizeof(op->name) - 1);
        strncpy(op->description, "Real FFT of 2^20=1M samples (vDSP_fft_zripD/Accelerate; double precision)", sizeof(op->description) - 1);
        op->memory_mb = (double)(HALF + 1) * 16.0 / (1024.0 * 1024.0);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        vDSP_destroy_fftsetupD(fft_setup);
        free(x); free(realp); free(imagp);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * 12. Sort 10M floats  — qsort
     * ──────────────────────────────────────────────────────────────────────── */
    {
        const int N = 10000000;
        double *orig = (double *)malloc((size_t)N * sizeof(double));
        double *buf  = (double *)malloc((size_t)N * sizeof(double));
        fill_uniform(orig, N, SEED);

        /* warmup */
        for (int w = 0; w < N_WARMUP; w++) {
            memcpy(buf, orig, (size_t)N * sizeof(double));
            qsort(buf, N, sizeof(double), cmp_double);
            g_sink += buf[0];
        }

        /* timed runs */
        for (int r = 0; r < N_RUNS; r++) {
            memcpy(buf, orig, (size_t)N * sizeof(double));
            double t0 = now_ms();
            qsort(buf, N, sizeof(double), cmp_double);
            times[r] = now_ms() - t0;
            g_sink += buf[0];
        }

        OpResult *op = &results[nresults++];
        strncpy(op->name, "Sort 10M floats", sizeof(op->name) - 1);
        strncpy(op->description, "Unstable sort of 10M random float64 values (qsort/stdlib)", sizeof(op->description) - 1);
        op->memory_mb = vec_mb(N);
        compute_stats(times, N_RUNS, &op->mean_ms, &op->std_ms, &op->min_ms);
        printf("  Benchmarking: %-35s ... %.2f ms  (%.2f MB)\n",
               op->name, op->mean_ms, op->memory_mb);

        free(orig); free(buf);
    }

    /* ── Write JSON ──────────────────────────────────────────────────────────── */

    FILE *fp = fopen("results/c_results.json", "w");
    if (!fp) {
        fprintf(stderr, "Error: cannot open results/c_results.json for writing\n");
        return 1;
    }

    fprintf(fp, "{\n");
    fprintf(fp, "  \"language\": \"C\",\n");
    fprintf(fp, "  \"version\": \"%s\",\n", version_str);
    fprintf(fp, "  \"platform\": \"%s\",\n", platform_str);
    fprintf(fp, "  \"operations\": [\n");

    for (int i = 0; i < nresults; i++) {
        OpResult *op = &results[i];
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"name\": \"%s\",\n", op->name);
        fprintf(fp, "      \"description\": \"%s\",\n", op->description);
        fprintf(fp, "      \"mean_ms\": %g,\n", op->mean_ms);
        fprintf(fp, "      \"std_ms\": %g,\n", op->std_ms);
        fprintf(fp, "      \"min_ms\": %g,\n", op->min_ms);
        fprintf(fp, "      \"memory_mb\": %g\n", op->memory_mb);
        fprintf(fp, "    }%s\n", (i + 1 < nresults) ? "," : "");
    }

    fprintf(fp, "  ]\n}\n");
    fclose(fp);

    printf("\nSaved results/c_results.json\n");
    printf("(sink=%g)\n", g_sink);   /* prevent entire program from being optimised away */
    return 0;
}
