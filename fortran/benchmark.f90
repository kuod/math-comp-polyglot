! Fortran benchmark: 11 numerical/linear-algebra operations
! Compile: gfortran -O3 -march=native -framework Accelerate -o fortran/fortran-bench fortran/benchmark.f90
! Run from project root: ./fortran/fortran-bench

PROGRAM benchmark
  USE iso_fortran_env, ONLY: compiler_version, REAL64
  IMPLICIT NONE

  ! External BLAS/LAPACK declarations
  EXTERNAL :: DGEMM, DGETRF, DGETRI, DSYEV, DPOTRF, DGESDD, DGESV, DGEQRF
  DOUBLE PRECISION, EXTERNAL :: DDOT

  INTEGER, PARAMETER :: SEED    = 42
  INTEGER, PARAMETER :: N_WARMUP = 3
  INTEGER, PARAMETER :: N_RUNS   = 10
  DOUBLE PRECISION, PARAMETER :: PI = 3.14159265358979323846D0

  ! Result storage
  INTEGER, PARAMETER :: N_OPS = 11
  CHARACTER(LEN=60)  :: op_names(N_OPS)
  CHARACTER(LEN=120) :: op_descs(N_OPS)
  DOUBLE PRECISION   :: op_mean(N_OPS), op_std(N_OPS), op_min(N_OPS), op_mem(N_OPS)

  INTEGER :: iop
  CHARACTER(LEN=64)  :: ver_str, platform_str
  CHARACTER(LEN=256) :: json_buf
  INTEGER            :: funit

  ! ── Timing variables ─────────────────────────────────────────────────────────
  INTEGER(KIND=8) :: t_start, t_stop, t_rate
  DOUBLE PRECISION :: elapsed_ms
  DOUBLE PRECISION :: times_ms(N_RUNS)
  DOUBLE PRECISION :: t_mean, t_var, t_min, t_sum

  ! ── Loop counters ─────────────────────────────────────────────────────────────
  INTEGER :: i, j, run, warmup

  ! ── Working arrays (allocated per-operation) ─────────────────────────────────
  DOUBLE PRECISION, ALLOCATABLE :: A(:,:), B(:,:), C(:,:), D(:,:)
  DOUBLE PRECISION, ALLOCATABLE :: Atmp(:,:), Btmp(:,:), btmp1(:), btmp2(:)
  DOUBLE PRECISION, ALLOCATABLE :: vec_a(:), vec_b(:), sort_data(:), sort_tmp(:)
  DOUBLE PRECISION, ALLOCATABLE :: S(:), U(:,:), VT(:,:), TAU(:), WORK(:)
  DOUBLE PRECISION, ALLOCATABLE :: WORK_Q(:)
  INTEGER, ALLOCATABLE          :: IPIV(:), IWORK(:)

  ! Scalar temporaries
  DOUBLE PRECISION :: dot_result, dummy
  INTEGER          :: INFO, LWORK, LWORK_Q
  DOUBLE PRECISION :: WORK_QUERY(1)

  ! ─────────────────────────────────────────────────────────────────────────────
  ! Version / platform
  ! ─────────────────────────────────────────────────────────────────────────────
  ver_str      = "GNU Fortran " // TRIM(compiler_version())
  platform_str = "macOS"

  WRITE(*,'(A)') "Fortran benchmark starting..."
  WRITE(*,'(A)') TRIM(ver_str)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 1. Matrix Multiply — DGEMM 1000×1000
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 1
  op_names(iop) = "Matrix Multiply"
  op_descs(iop) = "1000x1000 DGEMM (BLAS/Accelerate)"
  op_mem(iop)   = mat_mb(1000, 1000)

  ALLOCATE(A(1000,1000), B(1000,1000), C(1000,1000))
  CALL fill_randn(A, 1000, 1000, SEED)
  CALL fill_randn(B, 1000, 1000, SEED+1)

  ! Warmup
  DO warmup = 1, N_WARMUP
    CALL DGEMM('N','N',1000,1000,1000,1.0D0,A,1000,B,1000,0.0D0,C,1000)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DGEMM('N','N',1000,1000,1000,1.0D0,A,1000,B,1000,0.0D0,C,1000)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (C(1,1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, B, C)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 2. Matrix Inverse — DGETRF + DGETRI on 500×500 SPD
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 2
  op_names(iop) = "Matrix Inverse"
  op_descs(iop) = "Inversion of 500x500 SPD matrix (DGETRF+DGETRI/Accelerate)"
  op_mem(iop)   = mat_mb(500, 500)

  ALLOCATE(A(500,500), B(500,500), Atmp(500,500), IPIV(500))
  CALL fill_randn(B, 500, 500, SEED+2)
  ! A = B*B^T + 500*I  (SPD)
  CALL DGEMM('N','T',500,500,500,1.0D0,B,500,B,500,0.0D0,A,500)
  DO i = 1, 500
    A(i,i) = A(i,i) + 500.0D0
  END DO
  ! Query LWORK for DGETRI
  Atmp = A
  CALL DGETRF(500,500,Atmp,500,IPIV,INFO)
  LWORK = -1
  CALL DGETRI(500,Atmp,500,IPIV,WORK_QUERY,LWORK,INFO)
  LWORK = INT(WORK_QUERY(1))
  ALLOCATE(WORK(LWORK))
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    CALL DGETRF(500,500,Atmp,500,IPIV,INFO)
    CALL DGETRI(500,Atmp,500,IPIV,WORK,LWORK,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DGETRF(500,500,Atmp,500,IPIV,INFO)
    CALL DGETRI(500,Atmp,500,IPIV,WORK,LWORK,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (Atmp(1,1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, B, Atmp, IPIV, WORK)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 3. LU Decomposition — DGETRF on 500×500
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 3
  op_names(iop) = "LU Decomposition"
  op_descs(iop) = "LU factorisation of 500x500 matrix (DGETRF/Accelerate)"
  op_mem(iop)   = mat_mb(500, 500)

  ALLOCATE(A(500,500), Atmp(500,500), IPIV(500))
  CALL fill_randn(A, 500, 500, SEED+3)
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    CALL DGETRF(500,500,Atmp,500,IPIV,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DGETRF(500,500,Atmp,500,IPIV,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (Atmp(1,1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, Atmp, IPIV)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 4. Eigenvalue Decomp — DSYEV on 300×300 symmetric
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 4
  op_names(iop) = "Eigenvalue Decomp"
  op_descs(iop) = "Full eigendecomposition of 300x300 symmetric matrix (DSYEV/Accelerate)"
  op_mem(iop)   = mat_mb(300, 300) + vec_mb(300)

  ALLOCATE(A(300,300), Atmp(300,300), S(300))
  CALL fill_randn(A, 300, 300, SEED+4)
  ! Make symmetric: A = (A + A^T) / 2
  DO i = 1, 300
    DO j = i+1, 300
      A(i,j) = 0.5D0 * (A(i,j) + A(j,i))
      A(j,i) = A(i,j)
    END DO
  END DO
  ! Query LWORK
  Atmp = A
  LWORK = -1
  CALL DSYEV('V','U',300,Atmp,300,S,WORK_QUERY,LWORK,INFO)
  LWORK = INT(WORK_QUERY(1))
  ALLOCATE(WORK(LWORK))
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    CALL DSYEV('V','U',300,Atmp,300,S,WORK,LWORK,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DSYEV('V','U',300,Atmp,300,S,WORK,LWORK,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (S(1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, Atmp, S, WORK)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 5. Cholesky — DPOTRF on 500×500 SPD
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 5
  op_names(iop) = "Cholesky"
  op_descs(iop) = "Cholesky factorisation of 500x500 SPD matrix (DPOTRF/Accelerate)"
  op_mem(iop)   = mat_mb(500, 500)

  ALLOCATE(A(500,500), B(500,500), Atmp(500,500))
  CALL fill_randn(B, 500, 500, SEED+5)
  CALL DGEMM('N','T',500,500,500,1.0D0,B,500,B,500,0.0D0,A,500)
  DO i = 1, 500
    A(i,i) = A(i,i) + 500.0D0
  END DO
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    CALL DPOTRF('U',500,Atmp,500,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DPOTRF('U',500,Atmp,500,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (Atmp(1,1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, B, Atmp)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 6. SVD — DGESDD on 500×300
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 6
  op_names(iop) = "SVD"
  op_descs(iop) = "Economy SVD of 500x300 matrix (DGESDD/Accelerate; U:500x300)"
  op_mem(iop)   = mat_mb(500, 300) + vec_mb(300) + mat_mb(300, 300)

  ALLOCATE(A(500,300), Atmp(500,300), S(300), U(500,300), VT(300,300), IWORK(2400))
  CALL fill_randn(A, 500, 300, SEED+6)
  ! Query LWORK
  LWORK = -1
  CALL DGESDD('S',500,300,Atmp,500,S,U,500,VT,300,WORK_QUERY,LWORK,IWORK,INFO)
  LWORK = INT(WORK_QUERY(1))
  ALLOCATE(WORK(LWORK))
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    CALL DGESDD('S',500,300,Atmp,500,S,U,500,VT,300,WORK,LWORK,IWORK,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DGESDD('S',500,300,Atmp,500,S,U,500,VT,300,WORK,LWORK,IWORK,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (S(1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, Atmp, S, U, VT, IWORK, WORK)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 7. Linear System Solve — DGESV 1000×1000
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 7
  op_names(iop) = "Linear System Solve"
  op_descs(iop) = "Solve Ax=b for 1000x1000 SPD A, 1000 b (DGESV/Accelerate)"
  op_mem(iop)   = vec_mb(1000)

  ALLOCATE(A(1000,1000), B(1000,1000), btmp1(1000), btmp2(1000), Atmp(1000,1000), IPIV(1000))
  ! Build SPD: A = B*B^T + 1000*I (matches all other languages)
  CALL fill_randn(B, 1000, 1000, SEED+7)
  CALL DGEMM('N','T',1000,1000,1000,1.0D0,B,1000,B,1000,0.0D0,A,1000)
  DO i = 1, 1000
    A(i,i) = A(i,i) + 1000.0D0
  END DO
  CALL fill_randn_vec(btmp1, 1000, SEED+8)
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    btmp2 = btmp1
    CALL DGESV(1000,1,Atmp,1000,IPIV,btmp2,1000,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    btmp2 = btmp1
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DGESV(1000,1,Atmp,1000,IPIV,btmp2,1000,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (btmp2(1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, B, btmp1, btmp2, Atmp, IPIV)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 8. Vector Dot Product — DDOT on 10M elements
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 8
  op_names(iop) = "Vector Dot Product"
  op_descs(iop) = "Dot product of two 10M-element vectors (DDOT/Accelerate)"
  op_mem(iop)   = 8.0D0 / 1024.0D0 / 1024.0D0

  ALLOCATE(vec_a(10000000), vec_b(10000000))
  CALL fill_randn_vec(vec_a, 10000000, SEED+9)
  CALL fill_randn_vec(vec_b, 10000000, SEED+10)
  ! Warmup
  DO warmup = 1, N_WARMUP
    dot_result = DDOT(10000000, vec_a, 1, vec_b, 1)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    CALL SYSTEM_CLOCK(t_start, t_rate)
    dot_result = DDOT(10000000, vec_a, 1, vec_b, 1)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (dot_result > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(vec_a, vec_b)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 9. Hadamard Product — element-wise on 1000×1000
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 9
  op_names(iop) = "Hadamard Product"
  op_descs(iop) = "Element-wise multiply + add on 1000x1000 matrices (Fortran array ops)"
  op_mem(iop)   = mat_mb(1000, 1000)

  ALLOCATE(A(1000,1000), B(1000,1000), C(1000,1000), D(1000,1000))
  CALL fill_randn(A, 1000, 1000, SEED+11)
  CALL fill_randn(B, 1000, 1000, SEED+12)
  CALL fill_randn(D, 1000, 1000, SEED+13)
  ! Warmup
  DO warmup = 1, N_WARMUP
    C = A * B + D
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    CALL SYSTEM_CLOCK(t_start, t_rate)
    C = A * B + D
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (C(1,1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, B, C, D)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 10. QR Decomposition — DGEQRF on 500×500
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 10
  op_names(iop) = "QR Decomposition"
  op_descs(iop) = "QR factorisation of 500x500 matrix (DGEQRF/Accelerate)"
  op_mem(iop)   = mat_mb(500, 500)

  ALLOCATE(A(500,500), Atmp(500,500), TAU(500))
  CALL fill_randn(A, 500, 500, SEED+14)
  ! Query LWORK
  LWORK = -1
  CALL DGEQRF(500,500,Atmp,500,TAU,WORK_QUERY,LWORK,INFO)
  LWORK = INT(WORK_QUERY(1))
  ALLOCATE(WORK(LWORK))
  ! Warmup
  DO warmup = 1, N_WARMUP
    Atmp = A
    CALL DGEQRF(500,500,Atmp,500,TAU,WORK,LWORK,INFO)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    Atmp = A
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL DGEQRF(500,500,Atmp,500,TAU,WORK,LWORK,INFO)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (Atmp(1,1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(A, Atmp, TAU, WORK)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! 11. Sort 10M floats — recursive quicksort
  ! ═══════════════════════════════════════════════════════════════════════════
  iop = 11
  op_names(iop) = "Sort 10M floats"
  op_descs(iop) = "Unstable sort of 10M random float64 values (Fortran quicksort)"
  op_mem(iop)   = vec_mb(10000000)

  ALLOCATE(sort_data(10000000), sort_tmp(10000000))
  CALL fill_randn_vec(sort_data, 10000000, SEED+15)
  ! Warmup
  DO warmup = 1, N_WARMUP
    sort_tmp = sort_data
    CALL quicksort(sort_tmp, 1, 10000000)
  END DO
  ! Timed runs
  DO run = 1, N_RUNS
    sort_tmp = sort_data
    CALL SYSTEM_CLOCK(t_start, t_rate)
    CALL quicksort(sort_tmp, 1, 10000000)
    CALL SYSTEM_CLOCK(t_stop)
    times_ms(run) = DBLE(t_stop - t_start) * 1000.0D0 / DBLE(t_rate)
  END DO
  IF (sort_tmp(1) > 1.0D20) STOP "dead code elimination guard"
  DEALLOCATE(sort_data, sort_tmp)
  CALL compute_stats(times_ms, N_RUNS, t_mean, t_var, t_min)
  op_mean(iop) = t_mean; op_std(iop) = t_var; op_min(iop) = t_min
  WRITE(*,'("  Benchmarking: ",A30," ... ",F8.2," ms  (",F6.2," MB)")') &
       TRIM(op_names(iop)), op_mean(iop), op_mem(iop)

  ! ═══════════════════════════════════════════════════════════════════════════
  ! Write JSON results
  ! ═══════════════════════════════════════════════════════════════════════════
  OPEN(UNIT=10, FILE='results/fortran_results.json', STATUS='REPLACE', ACTION='WRITE')
  WRITE(10,'(A)') '{'
  WRITE(10,'(A)') '  "language": "Fortran",'
  WRITE(10,'(A,A,A)') '  "version": "', TRIM(ver_str), '",'
  WRITE(10,'(A,A,A)') '  "platform": "', TRIM(platform_str), '",'
  WRITE(10,'(A)') '  "operations": ['
  DO iop = 1, N_OPS
    WRITE(10,'(A)') '    {'
    ! Escape any special chars — names/descs are ASCII-safe here
    WRITE(10,'(A,A,A)') '      "name": "',        TRIM(op_names(iop)), '",'
    WRITE(10,'(A,A,A)') '      "description": "', TRIM(op_descs(iop)), '",'
    WRITE(10,'(A,F12.6,A)') '      "mean_ms": ',   op_mean(iop), ','
    WRITE(10,'(A,F12.6,A)') '      "std_ms": ',    op_std(iop),  ','
    WRITE(10,'(A,F12.6,A)') '      "min_ms": ',    op_min(iop),  ','
    WRITE(10,'(A,F12.6)')   '      "memory_mb": ', op_mem(iop)
    IF (iop < N_OPS) THEN
      WRITE(10,'(A)') '    },'
    ELSE
      WRITE(10,'(A)') '    }'
    END IF
  END DO
  WRITE(10,'(A)') '  ]'
  WRITE(10,'(A)') '}'
  CLOSE(10)

  WRITE(*,'(A)') "Results written to results/fortran_results.json"

CONTAINS

  ! ── Memory helpers ────────────────────────────────────────────────────────
  DOUBLE PRECISION FUNCTION mat_mb(n, m)
    INTEGER, INTENT(IN) :: n, m
    mat_mb = DBLE(n) * DBLE(m) * 8.0D0 / 1024.0D0 / 1024.0D0
  END FUNCTION mat_mb

  DOUBLE PRECISION FUNCTION vec_mb(n)
    INTEGER, INTENT(IN) :: n
    vec_mb = DBLE(n) * 8.0D0 / 1024.0D0 / 1024.0D0
  END FUNCTION vec_mb

  ! ── Statistics ───────────────────────────────────────────────────────────
  SUBROUTINE compute_stats(times, n, mean_out, std_out, min_out)
    INTEGER, INTENT(IN)          :: n
    DOUBLE PRECISION, INTENT(IN) :: times(n)
    DOUBLE PRECISION, INTENT(OUT):: mean_out, std_out, min_out
    INTEGER          :: k
    DOUBLE PRECISION :: s, v
    s = 0.0D0
    min_out = times(1)
    DO k = 1, n
      s = s + times(k)
      IF (times(k) < min_out) min_out = times(k)
    END DO
    mean_out = s / DBLE(n)
    v = 0.0D0
    DO k = 1, n
      v = v + (times(k) - mean_out)**2
    END DO
    std_out = SQRT(v / DBLE(n))
  END SUBROUTINE compute_stats

  ! ── RNG: fill 2D matrix with standard normal (Box-Muller) ─────────────────
  SUBROUTINE fill_randn(mat, n, m, seed_in)
    INTEGER, INTENT(IN) :: n, m, seed_in
    DOUBLE PRECISION, INTENT(OUT) :: mat(n, m)
    INTEGER :: sz, k, i, j, idx
    INTEGER, ALLOCATABLE :: seed_arr(:)
    DOUBLE PRECISION :: u1, u2, z0, z1
    DOUBLE PRECISION, ALLOCATABLE :: buf(:)
    INTEGER :: total

    CALL RANDOM_SEED(SIZE=sz)
    ALLOCATE(seed_arr(sz))
    DO k = 1, sz
      seed_arr(k) = seed_in + k - 1
    END DO
    CALL RANDOM_SEED(PUT=seed_arr)
    DEALLOCATE(seed_arr)

    total = n * m
    ALLOCATE(buf(total))
    CALL RANDOM_NUMBER(buf)

    idx = 1
    DO j = 1, m
      DO i = 1, n
        ! Box-Muller needs pairs; use sequential even/odd indexing
        IF (MOD(idx, 2) == 1) THEN
          IF (idx + 1 <= total) THEN
            u1 = MAX(buf(idx),   1.0D-15)
            u2 = buf(idx+1)
            z0 = SQRT(-2.0D0 * LOG(u1)) * COS(2.0D0 * PI * u2)
            z1 = SQRT(-2.0D0 * LOG(u1)) * SIN(2.0D0 * PI * u2)
            mat(i,j) = z0
          ELSE
            u1 = MAX(buf(idx), 1.0D-15)
            u2 = 0.5D0
            mat(i,j) = SQRT(-2.0D0 * LOG(u1)) * COS(2.0D0 * PI * u2)
          END IF
        ELSE
          ! Use the z1 from the previous pair
          u1 = MAX(buf(idx-1), 1.0D-15)
          u2 = buf(idx)
          mat(i,j) = SQRT(-2.0D0 * LOG(u1)) * SIN(2.0D0 * PI * u2)
        END IF
        idx = idx + 1
      END DO
    END DO
    DEALLOCATE(buf)
  END SUBROUTINE fill_randn

  ! ── RNG: fill 1D vector with standard normal (Box-Muller) ─────────────────
  SUBROUTINE fill_randn_vec(vec, n, seed_in)
    INTEGER, INTENT(IN) :: n, seed_in
    DOUBLE PRECISION, INTENT(OUT) :: vec(n)
    INTEGER :: sz, k, idx
    INTEGER, ALLOCATABLE :: seed_arr(:)
    DOUBLE PRECISION :: u1, u2
    DOUBLE PRECISION, ALLOCATABLE :: buf(:)

    CALL RANDOM_SEED(SIZE=sz)
    ALLOCATE(seed_arr(sz))
    DO k = 1, sz
      seed_arr(k) = seed_in + k - 1
    END DO
    CALL RANDOM_SEED(PUT=seed_arr)
    DEALLOCATE(seed_arr)

    ALLOCATE(buf(n))
    CALL RANDOM_NUMBER(buf)

    DO idx = 1, n
      IF (MOD(idx, 2) == 1) THEN
        IF (idx + 1 <= n) THEN
          u1 = MAX(buf(idx),   1.0D-15)
          u2 = buf(idx+1)
          vec(idx) = SQRT(-2.0D0 * LOG(u1)) * COS(2.0D0 * PI * u2)
        ELSE
          u1 = MAX(buf(idx), 1.0D-15)
          vec(idx) = SQRT(-2.0D0 * LOG(u1)) * COS(PI)
        END IF
      ELSE
        u1 = MAX(buf(idx-1), 1.0D-15)
        u2 = buf(idx)
        vec(idx) = SQRT(-2.0D0 * LOG(u1)) * SIN(2.0D0 * PI * u2)
      END IF
    END DO
    DEALLOCATE(buf)
  END SUBROUTINE fill_randn_vec

  ! ── Quicksort (recursive, median-of-three, insertion sort for small) ───────
  RECURSIVE SUBROUTINE quicksort(arr, lo, hi)
    DOUBLE PRECISION, INTENT(INOUT) :: arr(:)
    INTEGER, INTENT(IN) :: lo, hi
    INTEGER :: pivot_idx, mid
    DOUBLE PRECISION :: pivot_val, tmp
    INTEGER :: i, j

    IF (hi - lo < 16) THEN
      ! Insertion sort for small subarrays
      DO i = lo+1, hi
        tmp = arr(i)
        j = i - 1
        DO WHILE (j >= lo .AND. arr(j) > tmp)
          arr(j+1) = arr(j)
          j = j - 1
        END DO
        arr(j+1) = tmp
      END DO
      RETURN
    END IF

    ! Median-of-three pivot
    mid = lo + (hi - lo) / 2
    IF (arr(lo) > arr(mid)) THEN
      tmp = arr(lo); arr(lo) = arr(mid); arr(mid) = tmp
    END IF
    IF (arr(lo) > arr(hi)) THEN
      tmp = arr(lo); arr(lo) = arr(hi); arr(hi) = tmp
    END IF
    IF (arr(mid) > arr(hi)) THEN
      tmp = arr(mid); arr(mid) = arr(hi); arr(hi) = tmp
    END IF
    ! Place pivot at hi-1
    pivot_val = arr(mid)
    tmp = arr(mid); arr(mid) = arr(hi-1); arr(hi-1) = tmp

    i = lo
    j = hi - 1
    DO
      i = i + 1
      DO WHILE (arr(i) < pivot_val)
        i = i + 1
      END DO
      j = j - 1
      DO WHILE (j > lo .AND. arr(j) > pivot_val)
        j = j - 1
      END DO
      IF (i >= j) EXIT
      tmp = arr(i); arr(i) = arr(j); arr(j) = tmp
    END DO
    ! Restore pivot
    tmp = arr(i); arr(i) = arr(hi-1); arr(hi-1) = tmp
    pivot_idx = i

    CALL quicksort(arr, lo, pivot_idx - 1)
    CALL quicksort(arr, pivot_idx + 1, hi)
  END SUBROUTINE quicksort

END PROGRAM benchmark
