// Benchmark 12 numerical operations using gonum (pure-Go linear algebra).
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"math/cmplx"
	"os"
	"runtime"
	"slices"
	"time"

	"gonum.org/v1/gonum/dsp/fourier"
	"gonum.org/v1/gonum/mat"
)

// ── Constants ──────────────────────────────────────────────────────────────────

const (
	nWarmup = 3
	nRuns   = 10
)

// ── RNG / matrix builders ──────────────────────────────────────────────────────
// xorshift64 + Box-Muller: reproducible standard-normal values, no external RNG dep.

func randSlice(n int, s uint64) []float64 {
	state := s
	next := func() float64 {
		state ^= state << 13
		state ^= state >> 7
		state ^= state << 17
		return float64(state>>11+1) / float64(1<<53)
	}
	out := make([]float64, n)
	for i := 0; i+1 < n; i += 2 {
		u1, u2 := next(), next()
		r := math.Sqrt(-2 * math.Log(u1))
		out[i] = r * math.Cos(2*math.Pi*u2)
		out[i+1] = r * math.Sin(2*math.Pi*u2)
	}
	if n%2 == 1 {
		u1, u2 := next(), next()
		out[n-1] = math.Sqrt(-2*math.Log(u1)) * math.Cos(2*math.Pi*u2)
		_ = u2
	}
	return out
}

func randMatrix(n, m int) *mat.Dense {
	return mat.NewDense(n, m, randSlice(n*m, 42))
}

func randVec(n int) *mat.VecDense {
	return mat.NewVecDense(n, randSlice(n, 43))
}

func makeSPD(n int) *mat.SymDense {
	a := randMatrix(n, n)
	var aat mat.Dense
	aat.Mul(a, a.T())
	for i := 0; i < n; i++ {
		aat.Set(i, i, aat.At(i, i)+float64(n))
	}
	sym := mat.NewSymDense(n, nil)
	for i := 0; i < n; i++ {
		for j := i; j < n; j++ {
			sym.SetSym(i, j, aat.At(i, j))
		}
	}
	return sym
}

func makeSym(n int) *mat.SymDense {
	a := randMatrix(n, n)
	sym := mat.NewSymDense(n, nil)
	for i := 0; i < n; i++ {
		for j := i; j < n; j++ {
			sym.SetSym(i, j, (a.At(i, j)+a.At(j, i))*0.5)
		}
	}
	return sym
}

// ── Result types ──────────────────────────────────────────────────────────────

type OpResult struct {
	Name        string  `json:"name"`
	Description string  `json:"description"`
	MeanMs      float64 `json:"mean_ms"`
	StdMs       float64 `json:"std_ms"`
	MinMs       float64 `json:"min_ms"`
	MemoryMb    float64 `json:"memory_mb"`
}

type BenchOutput struct {
	Language   string     `json:"language"`
	Version    string     `json:"version"`
	Platform   string     `json:"platform"`
	Operations []OpResult `json:"operations"`
}

// ── Memory helper ─────────────────────────────────────────────────────────────

func totalAllocMb() float64 {
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	return float64(ms.TotalAlloc) / (1024 * 1024)
}

// ── Benchmark harness ─────────────────────────────────────────────────────────
// setupFn() allocates inputs and returns a closure (op) that performs the work.
// This separates setup time from measured time cleanly.

func bench(name, desc string, setupFn func() func()) OpResult {
	for i := 0; i < nWarmup; i++ {
		setupFn()()
	}

	timesMs := make([]float64, nRuns)
	memMbs := make([]float64, nRuns)

	for i := 0; i < nRuns; i++ {
		op := setupFn()
		runtime.GC()
		m0 := totalAllocMb()
		t0 := time.Now()
		op()
		elapsed := time.Since(t0).Seconds() * 1000.0
		m1 := totalAllocMb()
		timesMs[i] = elapsed
		memMbs[i] = math.Max(0, m1-m0)
	}

	sum := 0.0
	for _, t := range timesMs {
		sum += t
	}
	mean := sum / float64(nRuns)
	varSum := 0.0
	for _, t := range timesMs {
		varSum += (t - mean) * (t - mean)
	}
	minT := timesMs[0]
	for _, t := range timesMs {
		if t < minT {
			minT = t
		}
	}
	memSum := 0.0
	for _, m := range memMbs {
		memSum += m
	}

	r := OpResult{
		Name:        name,
		Description: desc,
		MeanMs:      mean,
		StdMs:       math.Sqrt(varSum / float64(nRuns)),
		MinMs:       minT,
		MemoryMb:    memSum / float64(nRuns),
	}
	fmt.Printf("  Benchmarking: %-25s ... %.2f ms  (%.2f MB)\n", r.Name, r.MeanMs, r.MemoryMb)
	return r
}

// ── main ──────────────────────────────────────────────────────────────────────

func main() {
	version := fmt.Sprintf("Go %s / gonum 0.15", runtime.Version()[2:])
	fmt.Println(version)

	var results []OpResult

	// 1. Matrix Multiply — 1000×1000
	results = append(results, bench(
		"Matrix Multiply",
		"1000x1000 dense matrix multiplication (A * B)",
		func() func() {
			a, b := randMatrix(1000, 1000), randMatrix(1000, 1000)
			return func() {
				var c mat.Dense
				c.Mul(a, b)
				_ = c.At(0, 0)
			}
		},
	))

	// 2. Matrix Inverse — 500×500
	results = append(results, bench(
		"Matrix Inverse",
		"Inversion of 500x500 SPD matrix",
		func() func() {
			spd := makeSPD(500)
			a := mat.NewDense(500, 500, nil)
			for i := 0; i < 500; i++ {
				for j := 0; j < 500; j++ {
					a.Set(i, j, spd.At(i, j))
				}
			}
			return func() {
				var inv mat.Dense
				if err := inv.Inverse(a); err != nil {
					panic(err)
				}
				_ = inv.At(0, 0)
			}
		},
	))

	// 3. LU Decomposition — 500×500
	results = append(results, bench(
		"LU Decomposition",
		"LU factorisation of 500x500 matrix",
		func() func() {
			a := randMatrix(500, 500)
			return func() {
				var lu mat.LU
				lu.Factorize(a)
				var l, u mat.TriDense
				lu.LTo(&l)
				lu.UTo(&u)
				_ = l.At(0, 0)
				_ = u.At(0, 0)
			}
		},
	))

	// 4. Eigenvalue Decomposition — 300×300 symmetric
	results = append(results, bench(
		"Eigenvalue Decomp",
		"Full eigendecomposition of 300x300 symmetric matrix",
		func() func() {
			s := makeSym(300)
			return func() {
				var eig mat.EigenSym
				if !eig.Factorize(s, true) {
					panic("eigen failed")
				}
				vals := eig.Values(nil)
				_ = vals[0]
			}
		},
	))

	// 5. Cholesky — 500×500 SPD
	results = append(results, bench(
		"Cholesky",
		"Cholesky factorisation of 500x500 SPD matrix",
		func() func() {
			s := makeSPD(500)
			return func() {
				var chol mat.Cholesky
				if !chol.Factorize(s) {
					panic("cholesky failed")
				}
				var l mat.TriDense
				chol.LTo(&l)
				_ = l.At(0, 0)
			}
		},
	))

	// 6. SVD — 500×300
	results = append(results, bench(
		"SVD",
		"Full SVD of 500x300 matrix",
		func() func() {
			a := randMatrix(500, 300)
			return func() {
				var svd mat.SVD
				if !svd.Factorize(a, mat.SVDThin) {
					panic("svd failed")
				}
				vals := svd.Values(nil)
				_ = vals[0]
			}
		},
	))

	// 7. Linear System Solve — 1000×1000
	results = append(results, bench(
		"Linear System Solve",
		"Solve Ax=b for 1000x1000 A, 1000 b",
		func() func() {
			s := makeSPD(1000)
			b := randVec(1000)
			return func() {
				var chol mat.Cholesky
				if !chol.Factorize(s) {
					panic("cholesky for solve failed")
				}
				var x mat.VecDense
				if err := chol.SolveVecTo(&x, b); err != nil {
					panic(err)
				}
				_ = x.AtVec(0)
			}
		},
	))

	// 8. Vector Dot Product — 10M elements
	results = append(results, bench(
		"Vector Dot Product",
		"Dot product of two 10M-element vectors",
		func() func() {
			x, y := randVec(10_000_000), randVec(10_000_000)
			return func() {
				v := mat.Dot(x, y)
				_ = v
			}
		},
	))

	// 9. Hadamard Product — 1000×1000
	results = append(results, bench(
		"Hadamard Product",
		"Element-wise multiply + add on 1000x1000 matrices",
		func() func() {
			a, b, c := randMatrix(1000, 1000), randMatrix(1000, 1000), randMatrix(1000, 1000)
			return func() {
				var r mat.Dense
				r.MulElem(a, b)
				r.Add(&r, c)
				_ = r.At(0, 0)
			}
		},
	))

	// 10. QR Decomposition — 500×500
	results = append(results, bench(
		"QR Decomposition",
		"QR factorisation of 500x500 matrix",
		func() func() {
			a := randMatrix(500, 500)
			return func() {
				var qr mat.QR
				qr.Factorize(a)
				var r mat.Dense
				qr.RTo(&r)
				_ = r.At(0, 0)
			}
		},
	))

	// 11. FFT (real, 1M)
	results = append(results, bench(
		"FFT (real, 1M)",
		"Real FFT of 2^20=1M-element vector (gonum fourier)",
		func() func() {
			data := randSlice(1<<20, 42)
			return func() {
				fft := fourier.NewFFT(len(data))
				coeff := fft.Coefficients(nil, data)
				_ = cmplx.Abs(coeff[0])
			}
		},
	))

	// 12. Sort 10M floats
	results = append(results, bench(
		"Sort 10M floats",
		"Unstable sort of 10M random float64 values (slices.Sort)",
		func() func() {
			data := randSlice(10_000_000, 42)
			return func() {
				slices.Sort(data)
				_ = data[0]
			}
		},
	))

	// ── Write JSON ────────────────────────────────────────────────────────────
	out := BenchOutput{
		Language:   "Go",
		Version:    version,
		Platform:   runtime.GOOS,
		Operations: results,
	}
	if err := os.MkdirAll("results", 0755); err != nil {
		panic(err)
	}
	data, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile("results/go_results.json", data, 0644); err != nil {
		panic(err)
	}
	fmt.Println("Saved results/go_results.json")
}
