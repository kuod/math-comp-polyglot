{-# LANGUAGE ScopedTypeVariables #-}
-- Benchmark 12 numerical operations using hmatrix (LAPACK/BLAS bindings).
-- Compiled with -with-rtsopts=-T so GHC.Stats is always available.
module Main where

import           Prelude                    hiding ((<>))
import           Control.Exception          (evaluate)
import           Control.Monad              (forM, replicateM_)
import           Data.List                  (intercalate, foldl')
import           Numeric.LinearAlgebra
import           System.Clock               (Clock (Monotonic), getTime,
                                             toNanoSecs)
import           System.Directory           (createDirectoryIfMissing)
import           System.IO                  (hFlush, hSetBuffering, stdout,
                                             BufferMode (..))
import           System.Random              (mkStdGen, randoms)
import           Text.Printf                (printf, hPrintf)
import           GHC.Stats                  (getRTSStats, allocated_bytes)
import           Data.Word                  (Word64)
import qualified Data.Vector.Storable       as VS
import qualified Data.Vector.Algorithms.Intro as VAI

-- ── Constants ──────────────────────────────────────────────────────────────────

nWarmup, nRuns :: Int
nWarmup = 3
nRuns   = 10

mySeed :: Int
mySeed = 42

-- ── Matrix / vector builders ───────────────────────────────────────────────────

randMatrix :: Int -> Int -> Matrix Double
randMatrix n m = (n><m) $ take (n * m) (randoms (mkStdGen mySeed) :: [Double])

randVec :: Int -> Vector Double
randVec n = fromList $ take n (randoms (mkStdGen (mySeed + 1)) :: [Double])

-- Symmetric positive-definite: A*A^T + n*I
makeSPD :: Int -> Matrix Double
makeSPD n =
  let a = randMatrix n n
  in  (a <> tr a) + scalar (fromIntegral n) * ident n

-- Symmetric: (A + A^T) / 2
makeSym :: Int -> Matrix Double
makeSym n =
  let a = randMatrix n n
  in  (a + tr a) / 2

-- ── Timing & memory helpers ────────────────────────────────────────────────────

nowMs :: IO Double
nowMs = (/ 1e6) . fromIntegral . toNanoSecs <$> getTime Monotonic

allocBytes :: IO Word64
allocBytes = allocated_bytes <$> getRTSStats

-- Force a Matrix to WHNF — enough because hmatrix data lives in C memory.
forceM :: Matrix Double -> IO ()
forceM m = evaluate (rows m) >> return ()

forceV :: Vector Double -> IO ()
forceV v = evaluate (size v) >> return ()

forceD :: Double -> IO ()
forceD d = evaluate d >> return ()

forceSV :: VS.Storable a => VS.Vector a -> IO ()
forceSV v = evaluate (VS.length v) >> return ()

-- ── Result type ────────────────────────────────────────────────────────────────

data OpResult = OpResult
  { rName   :: String
  , rDesc   :: String
  , rMeanMs :: Double
  , rStdMs  :: Double
  , rMinMs  :: Double
  , rMemMb  :: Double
  }

-- ── Generic benchmark harness ──────────────────────────────────────────────────

benchOp :: String -> String -> IO a -> (a -> IO ()) -> IO OpResult
benchOp name desc setup forceResult = do
  -- Warmup
  replicateM_ nWarmup $ setup >>= forceResult

  -- Measured runs
  samples <- forM [1 .. nRuns] $ \_ -> do
    d      <- setup
    a0     <- allocBytes
    t0     <- nowMs
    forceResult d
    t1     <- nowMs
    a1     <- allocBytes
    let ms  = t1 - t0
        mb  = fromIntegral (a1 - a0 :: Word64) / (1024 * 1024) :: Double
    return (ms, mb)

  let times = map fst samples
      mems  = map snd samples
      n     = fromIntegral nRuns :: Double
      mean  = sum times / n
      var   = foldl' (\acc t -> acc + (t - mean) ^ (2 :: Int)) 0 times / n
      mem   = sum mems / n

  hPrintf stdout "  Benchmarking: %-25s ... %.2f ms  (%.2f MB)\n" name mean mem
  hFlush stdout

  return OpResult
    { rName   = name
    , rDesc   = desc
    , rMeanMs = mean
    , rStdMs  = sqrt var
    , rMinMs  = minimum times
    , rMemMb  = mem
    }

-- ── Operations ─────────────────────────────────────────────────────────────────

operations :: [IO OpResult]
operations =
  [ benchOp "Matrix Multiply"
            "1000x1000 dense matrix multiplication (A <> B)"
            (do let a = randMatrix 1000 1000; b = randMatrix 1000 1000
                return (a, b))
            (\(a, b) -> forceM (a <> b))

  , benchOp "Matrix Inverse"
            "Inversion of 500x500 SPD matrix"
            (return (makeSPD 500))
            (forceM . inv)

  , benchOp "LU Decomposition"
            "LU factorisation of 500x500 matrix"
            (return (randMatrix 500 500))
            (\m -> let (l, u, _, _) = lu m in forceM l >> forceM u)

  , benchOp "Eigenvalue Decomp"
            "Full eigendecomposition of 300x300 symmetric matrix"
            (return (makeSym 300))
            (\m -> let (vals, vecs) = eigSH (sym m)
                   in  forceV vals >> forceM vecs)

  , benchOp "Cholesky"
            "Cholesky factorisation of 500x500 SPD matrix"
            (return (makeSPD 500))
            (forceM . chol . sym)

  , benchOp "SVD"
            "Full SVD of 500x300 matrix"
            (return (randMatrix 500 300))
            (\m -> let (u, s, v) = thinSVD m
                   in  forceM u >> forceV s >> forceM v)

  , benchOp "Linear System Solve"
            "Solve Ax=b for 1000x1000 A, 1000 b"
            (do let a = makeSPD 1000; b = randVec 1000
                return (a, b))
            (\(a, b) -> case linearSolve a (asColumn b) of
                          Just x  -> forceM x
                          Nothing -> return ())

  , benchOp "Vector Dot Product"
            "Dot product of two 10M-element vectors"
            (do let x = randVec 10000000; y = randVec 10000000
                return (x, y))
            (\(x, y) -> forceD (x <.> y))

  , benchOp "Hadamard Product"
            "Element-wise multiply + add on 1000x1000 matrices"
            (do let a = randMatrix 1000 1000
                    b = randMatrix 1000 1000
                    c = randMatrix 1000 1000
                return (a, b, c))
            (\(a, b, c) -> forceM (a * b + c))

  -- hmatrix's `qr` extracts full Q via Haskell-level Householder products,
  -- which is ~400x slower than LAPACK for n=500. Forcing only R (which binds
  -- directly to LAPACK's dgeqrf output) matches what R/Julia measure.
  , benchOp "QR Decomposition"
            "QR factorisation of 500x500 matrix (R factor, dgeqrf)"
            (return (randMatrix 500 500))
            (\m -> let (_, r) = qr m in forceM r)

  , benchOp "Sort 10M floats"
            "Unstable sort of 10M random float64 values (vector-algorithms)"
            (return (VS.fromList (take 10000000
                      (randoms (mkStdGen mySeed) :: [Double]))))
            (\v -> do
                mv <- VS.thaw v
                VAI.sort mv
                sorted <- VS.freeze mv
                forceSV sorted)
  ]

-- ── JSON serialisation ──────────────────────────────────────────────────────────

opToJSON :: OpResult -> String
opToJSON r = unlines
  [ "    {"
  , printf "      \"name\": \"%s\"," (rName r)
  , printf "      \"description\": \"%s\"," (rDesc r)
  , printf "      \"mean_ms\": %.6f," (rMeanMs r)
  , printf "      \"std_ms\": %.6f," (rStdMs r)
  , printf "      \"min_ms\": %.6f," (rMinMs r)
  , printf "      \"memory_mb\": %.6f" (rMemMb r)
  , "    }"
  ]

writeResults :: String -> [OpResult] -> IO ()
writeResults ghcVer results = do
  -- Write to results/ relative to the working directory (run_all.sh sets cwd
  -- to the project root before invoking the binary).
  createDirectoryIfMissing True "results"
  let opsJSON = intercalate "," (map opToJSON results)
      out = printf
              "{\n  \"language\": \"Haskell\",\n  \"version\": \"%s / hmatrix\",\n  \"platform\": \"native\",\n  \"operations\": [\n%s  ]\n}\n"
              ghcVer opsJSON :: String
  writeFile "results/haskell_results.json" out
  putStrLn "Saved results/haskell_results.json"

-- ── Main ───────────────────────────────────────────────────────────────────────

main :: IO ()
main = do
  hSetBuffering stdout LineBuffering
  let ghcVer = "GHC 9.14.1"
  putStrLn ghcVer
  results <- sequence operations
  writeResults ghcVer results
