#!/usr/bin/env Rscript
# Benchmark 10 numerical operations in base R + Matrix package

suppressPackageStartupMessages({
  library(Matrix)
})

SEED <- 42
N_WARMUP <- 3L
N_RUNS <- 10L

set.seed(SEED)

make_matrix <- function(n, m = n) matrix(rnorm(n * m), n, m)
make_spd <- function(n) {
  set.seed(SEED)
  A <- make_matrix(n)
  A %*% t(A) + n * diag(n)
}

# Memory: use gc() Vcells delta as proxy for heap allocated (in Mb)
vcells_mb <- function() {
  g <- gc(verbose = FALSE)
  g["Vcells", "used"] * 8 / 1024 / 1024  # Vcells in 8-byte doubles -> MB
}

bench <- function(name, description, setup_fn, op_fn) {
  # Warmup
  for (i in seq_len(N_WARMUP)) {
    d <- setup_fn()
    op_fn(d)
  }

  times_ms <- numeric(N_RUNS)
  mem_mbs  <- numeric(N_RUNS)

  for (i in seq_len(N_RUNS)) {
    d <- setup_fn()
    gc(verbose = FALSE, reset = TRUE)
    mem_before <- vcells_mb()
    t0 <- proc.time()[["elapsed"]]
    res <- op_fn(d)
    t1 <- proc.time()[["elapsed"]]
    mem_after <- vcells_mb()
    times_ms[i] <- (t1 - t0) * 1000
    delta <- mem_after - mem_before
    mem_mbs[i] <- max(0, delta)
    rm(res)
  }

  list(
    name        = name,
    description = description,
    mean_ms     = mean(times_ms),
    std_ms      = sd(times_ms),
    min_ms      = min(times_ms),
    memory_mb   = mean(mem_mbs)
  )
}

OPERATIONS <- list(
  list(
    name        = "Matrix Multiply",
    description = "1000×1000 dense matrix multiplication (A %*% B)",
    setup       = function() list(make_matrix(1000), make_matrix(1000)),
    op          = function(d) d[[1]] %*% d[[2]]
  ),
  list(
    name        = "Matrix Inverse",
    description = "Inversion of 500×500 SPD matrix",
    setup       = function() list(make_spd(500)),
    op          = function(d) solve(d[[1]])
  ),
  list(
    name        = "LU Decomposition",
    description = "LU factorisation of 500×500 matrix",
    setup       = function() list(make_matrix(500)),
    op          = function(d) lu(Matrix(d[[1]]))
  ),
  list(
    name        = "Eigenvalue Decomp",
    description = "Full eigendecomposition of 300×300 symmetric matrix",
    setup       = function() { A <- make_matrix(300); list((A + t(A)) / 2) },
    op          = function(d) eigen(d[[1]])
  ),
  list(
    name        = "Cholesky",
    description = "Cholesky factorisation of 500×500 SPD matrix",
    setup       = function() list(make_spd(500)),
    op          = function(d) chol(d[[1]])
  ),
  list(
    name        = "SVD",
    description = "Full SVD of 500×300 matrix",
    setup       = function() list(make_matrix(500, 300)),
    op          = function(d) svd(d[[1]])
  ),
  list(
    name        = "Linear System Solve",
    description = "Solve Ax=b for 1000×1000 A, 1000 b",
    setup       = function() list(make_spd(1000), rnorm(1000)),
    op          = function(d) solve(d[[1]], d[[2]])
  ),
  list(
    name        = "Vector Dot Product",
    description = "Dot product of two 10M-element vectors",
    setup       = function() list(rnorm(1e7), rnorm(1e7)),
    op          = function(d) sum(d[[1]] * d[[2]])
  ),
  list(
    name        = "Hadamard Product",
    description = "Element-wise multiply + add on 1000×1000 matrices",
    setup       = function() list(make_matrix(1000), make_matrix(1000), make_matrix(1000)),
    op          = function(d) d[[1]] * d[[2]] + d[[3]]
  ),
  list(
    name        = "QR Decomposition",
    description = "QR factorisation of 500×500 matrix",
    setup       = function() list(make_matrix(500)),
    op          = function(d) qr(d[[1]])
  ),
  list(
    name        = "FFT (real, 1M)",
    description = "Real FFT of 2^20=1M-element vector (base R fft)",
    setup       = function() list(rnorm(2^20)),
    op          = function(d) fft(d[[1]])
  ),
  list(
    name        = "Sort 10M floats",
    description = "Unstable sort of 10M random float64 values (base R sort, radix)",
    setup       = function() list(rnorm(1e7)),
    op          = function(d) sort(d[[1]], method = "radix")
  )
)

cat(sprintf("R %s\n", R.version$version.string))

results <- vector("list", length(OPERATIONS))
for (i in seq_along(OPERATIONS)) {
  op <- OPERATIONS[[i]]
  cat(sprintf("  Benchmarking: %-25s ... ", op$name), sep = "")
  flush.console()
  r <- bench(op$name, op$description, op$setup, op$op)
  results[[i]] <- r
  cat(sprintf("%.2f ms  (%.2f MB)\n", r$mean_ms, r$memory_mb))
}

out <- list(
  language   = "R",
  version    = R.version$version.string,
  platform   = R.version$platform,
  operations = results
)

dir.create("results", showWarnings = FALSE)
json_str <- jsonlite::toJSON(out, auto_unbox = TRUE, pretty = TRUE)
writeLines(json_str, "results/r_results.json")
cat("Saved results/r_results.json\n")
