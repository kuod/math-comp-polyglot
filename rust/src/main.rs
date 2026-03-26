use nalgebra::{DMatrix, DVector, SymmetricEigen};
use rustfft::{FftPlanner, num_complex::Complex};
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use rand_distr::{Distribution, StandardNormal};
use serde::{Deserialize, Serialize};
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering::SeqCst};
use std::time::Instant;

// ── Peak-tracking allocator ──────────────────────────────────────────────────

static CURRENT: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);

struct PeakAllocator;

unsafe impl GlobalAlloc for PeakAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let ptr = System.alloc(layout);
        if !ptr.is_null() {
            let prev = CURRENT.fetch_add(layout.size(), SeqCst);
            let cur = prev + layout.size();
            let _ = PEAK.fetch_max(cur, SeqCst);
        }
        ptr
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        System.dealloc(ptr, layout);
        CURRENT.fetch_sub(layout.size(), SeqCst);
    }
}

#[global_allocator]
static ALLOC: PeakAllocator = PeakAllocator;

fn reset_peak() {
    PEAK.store(CURRENT.load(SeqCst), SeqCst);
}

fn peak_since_reset_mb() -> f64 {
    PEAK.load(SeqCst) as f64 / (1024.0 * 1024.0)
}

fn baseline_mb() -> f64 {
    CURRENT.load(SeqCst) as f64 / (1024.0 * 1024.0)
}

// ── RNG helpers ──────────────────────────────────────────────────────────────

const SEED: u64 = 42;

fn make_rng() -> ChaCha8Rng {
    ChaCha8Rng::seed_from_u64(SEED)
}

fn rand_matrix(n: usize, m: usize) -> DMatrix<f64> {
    let mut rng = make_rng();
    let data: Vec<f64> = (0..n * m)
        .map(|_| StandardNormal.sample(&mut rng))
        .collect();
    DMatrix::from_vec(n, m, data)
}

fn rand_vec(n: usize) -> DVector<f64> {
    let mut rng = make_rng();
    let data: Vec<f64> = (0..n)
        .map(|_| StandardNormal.sample(&mut rng))
        .collect();
    DVector::from_vec(data)
}

fn make_spd(n: usize) -> DMatrix<f64> {
    let a = rand_matrix(n, n);
    let mut s = &a * a.transpose();
    for i in 0..n {
        s[(i, i)] += n as f64;
    }
    s
}

fn make_sym(n: usize) -> DMatrix<f64> {
    let a = rand_matrix(n, n);
    (&a + a.transpose()) * 0.5
}

// ── Result types ─────────────────────────────────────────────────────────────

#[derive(Serialize, Deserialize)]
struct OpResult {
    name: String,
    description: String,
    mean_ms: f64,
    std_ms: f64,
    min_ms: f64,
    memory_mb: f64,
}

#[derive(Serialize, Deserialize)]
struct BenchOutput {
    language: String,
    version: String,
    platform: String,
    operations: Vec<OpResult>,
}

// ── Benchmarking harness ─────────────────────────────────────────────────────

const N_WARMUP: usize = 3;
const N_RUNS: usize = 10;

fn bench<S, O, R>(name: &str, description: &str, setup: S, op: O) -> OpResult
where
    S: Fn() -> R,
    O: Fn(R),
{
    // Warmup
    for _ in 0..N_WARMUP {
        let data = setup();
        op(data);
    }

    let mut times_ms = Vec::with_capacity(N_RUNS);
    let mut mem_mbs = Vec::with_capacity(N_RUNS);

    for _ in 0..N_RUNS {
        let data = setup();
        let base = baseline_mb();
        reset_peak();

        let t0 = Instant::now();
        op(data);
        let elapsed_ms = t0.elapsed().as_secs_f64() * 1000.0;

        let peak = peak_since_reset_mb();
        times_ms.push(elapsed_ms);
        mem_mbs.push((peak - base).max(0.0));
    }

    let n = times_ms.len() as f64;
    let mean_ms = times_ms.iter().sum::<f64>() / n;
    let variance = times_ms.iter().map(|&t| (t - mean_ms).powi(2)).sum::<f64>() / n;
    let std_ms = variance.sqrt();
    let min_ms = times_ms.iter().cloned().fold(f64::INFINITY, f64::min);
    let memory_mb = mem_mbs.iter().sum::<f64>() / n;

    OpResult {
        name: name.to_string(),
        description: description.to_string(),
        mean_ms,
        std_ms,
        min_ms,
        memory_mb,
    }
}

// ── Main ─────────────────────────────────────────────────────────────────────

fn main() {
    // Try rustc on PATH, then fallback to ~/.cargo/bin/rustc
    let rustc_ver = ["rustc", "~/.cargo/bin/rustc"]
        .iter()
        .find_map(|cmd| {
            std::process::Command::new(
                if cmd.starts_with('~') {
                    std::path::PathBuf::from(std::env::var("HOME").unwrap_or_default())
                        .join(".cargo/bin/rustc")
                } else {
                    std::path::PathBuf::from(cmd)
                }
            )
            .arg("--version")
            .output()
            .ok()
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        })
        .unwrap_or_else(|| "Rust (unknown)".into());
    let version = format!("{} / nalgebra 0.33", rustc_ver);
    println!("{version}");

    let mut results = Vec::new();

    use std::hint::black_box;

    // 1. Matrix Multiply
    {
        let r = bench(
            "Matrix Multiply",
            "1000×1000 dense matrix multiplication (A * B)",
            || (rand_matrix(1000, 1000), rand_matrix(1000, 1000)),
            |(a, b)| { black_box(&a * &b); },
        );
        print_result(&r);
        results.push(r);
    }

    // 2. Matrix Inverse
    {
        let r = bench(
            "Matrix Inverse",
            "Inversion of 500×500 SPD matrix",
            || make_spd(500),
            |a| { black_box(a.try_inverse().unwrap()); },
        );
        print_result(&r);
        results.push(r);
    }

    // 3. LU Decomposition
    {
        let r = bench(
            "LU Decomposition",
            "LU factorisation of 500×500 matrix",
            || rand_matrix(500, 500),
            |a| { black_box(a.lu()); },
        );
        print_result(&r);
        results.push(r);
    }

    // 4. Eigenvalue Decomposition (symmetric)
    {
        let r = bench(
            "Eigenvalue Decomp",
            "Full eigendecomposition of 300×300 symmetric matrix",
            || make_sym(300),
            |a| { black_box(SymmetricEigen::new(a)); },
        );
        print_result(&r);
        results.push(r);
    }

    // 5. Cholesky
    {
        let r = bench(
            "Cholesky",
            "Cholesky factorisation of 500×500 SPD matrix",
            || make_spd(500),
            |a| { black_box(a.cholesky().unwrap()); },
        );
        print_result(&r);
        results.push(r);
    }

    // 6. SVD
    {
        let r = bench(
            "SVD",
            "Full SVD of 500×300 matrix",
            || rand_matrix(500, 300),
            |a| { black_box(a.svd(true, true)); },
        );
        print_result(&r);
        results.push(r);
    }

    // 7. Linear System Solve
    {
        let r = bench(
            "Linear System Solve",
            "Solve Ax=b for 1000×1000 A, 1000 b",
            || (make_spd(1000), rand_vec(1000)),
            |(a, b)| { black_box(a.lu().solve(&b).unwrap()); },
        );
        print_result(&r);
        results.push(r);
    }

    // 8. Vector Dot Product
    {
        let r = bench(
            "Vector Dot Product",
            "Dot product of two 10M-element vectors",
            || (rand_vec(10_000_000), rand_vec(10_000_000)),
            |(x, y)| { black_box(x.dot(&y)); },
        );
        print_result(&r);
        results.push(r);
    }

    // 9. Hadamard Product
    {
        let r = bench(
            "Hadamard Product",
            "Element-wise multiply + add on 1000×1000 matrices",
            || (rand_matrix(1000, 1000), rand_matrix(1000, 1000), rand_matrix(1000, 1000)),
            |(a, b, c)| { black_box(a.component_mul(&b) + c); },
        );
        print_result(&r);
        results.push(r);
    }

    // 10. QR Decomposition
    {
        let r = bench(
            "QR Decomposition",
            "QR factorisation of 500×500 matrix",
            || rand_matrix(500, 500),
            |a| { black_box(a.qr()); },
        );
        print_result(&r);
        results.push(r);
    }

    // 11. FFT (real, 1M)
    {
        let r = bench(
            "FFT (real, 1M)",
            "Real FFT of 2\u{00b2}\u{2070}=1M-element vector (rustfft)",
            || {
                let mut rng = make_rng();
                (0..(1 << 20))
                    .map(|_| StandardNormal.sample(&mut rng))
                    .collect::<Vec<f64>>()
            },
            |data| {
                let mut planner = FftPlanner::new();
                let fft = planner.plan_fft_forward(data.len());
                let mut buf: Vec<Complex<f64>> =
                    data.iter().map(|&x| Complex::new(x, 0.0)).collect();
                fft.process(&mut buf);
                black_box(buf);
            },
        );
        print_result(&r);
        results.push(r);
    }

    // 12. Sort 10M floats
    {
        let r = bench(
            "Sort 10M floats",
            "Unstable sort of 10M random float64 values (pdqsort)",
            || {
                let mut rng = make_rng();
                (0..10_000_000)
                    .map(|_| StandardNormal.sample(&mut rng))
                    .collect::<Vec<f64>>()
            },
            |mut data| {
                data.sort_unstable_by(|a, b| a.partial_cmp(b).unwrap());
                black_box(data);
            },
        );
        print_result(&r);
        results.push(r);
    }

    let out = BenchOutput {
        language: "Rust".to_string(),
        version,
        platform: std::env::consts::OS.to_string(),
        operations: results,
    };

    std::fs::create_dir_all("results").unwrap();
    let json = serde_json::to_string_pretty(&out).unwrap();
    std::fs::write("results/rust_results.json", json).unwrap();
    println!("Saved results/rust_results.json");
}

fn print_result(r: &OpResult) {
    println!(
        "  Benchmarking: {:<25} ... {:.2} ms  ({:.2} MB)",
        r.name, r.mean_ms, r.memory_mb
    );
}
