% octave/benchmark.m
% Run from project root: octave --no-gui octave/benchmark.m

N_WARMUP = 3;
N_RUNS   = 10;

% Fixed seed for reproducibility
randn ('state', 42);

ver_str = version ();
printf ('Octave %s\n', ver_str);

results = {};

%% ── 1. Matrix Multiply ──────────────────────────────────────────────────────
name = 'Matrix Multiply';
desc = '1000x1000 dense matrix multiplication (A * B)';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  A = randn (1000, 1000); B = randn (1000, 1000); C = A * B;
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  A = randn (1000, 1000); B = randn (1000, 1000);
  tic; C = A * B; times(k) = toc () * 1000;
end
mem_mb = (1000 * 1000 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 2. Matrix Inverse ───────────────────────────────────────────────────────
name = 'Matrix Inverse';
desc = 'Inversion of 500x500 SPD matrix';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  B = randn (500, 500); A = B * B' + 500 * eye (500); C = inv (A);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  B = randn (500, 500); A = B * B' + 500 * eye (500);
  tic; C = inv (A); times(k) = toc () * 1000;
end
mem_mb = (500 * 500 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 3. LU Decomposition ─────────────────────────────────────────────────────
name = 'LU Decomposition';
desc = 'LU factorisation of 500x500 matrix';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  A = randn (500, 500); [L, U, P] = lu (A);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  A = randn (500, 500);
  tic; [L, U, P] = lu (A); times(k) = toc () * 1000;
end
mem_mb = (500 * 500 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 4. Eigenvalue Decomposition ─────────────────────────────────────────────
name = 'Eigenvalue Decomp';
desc = 'Full eigendecomposition of 300x300 symmetric matrix';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  A = randn (300, 300); A = (A + A') / 2; [V, D] = eig (A);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  A = randn (300, 300); A = (A + A') / 2;
  tic; [V, D] = eig (A); times(k) = toc () * 1000;
end
mem_mb = (300 * 300 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 5. Cholesky ─────────────────────────────────────────────────────────────
name = 'Cholesky';
desc = 'Cholesky factorisation of 500x500 SPD matrix';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  B = randn (500, 500); A = B * B' + 500 * eye (500); L = chol (A, 'lower');
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  B = randn (500, 500); A = B * B' + 500 * eye (500);
  tic; L = chol (A, 'lower'); times(k) = toc () * 1000;
end
mem_mb = (500 * 500 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 6. SVD ──────────────────────────────────────────────────────────────────
name = 'SVD';
desc = 'Economy SVD of 500x300 matrix (U:500x300, S:300, V:300x300)';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  A = randn (500, 300); [U, S, V] = svd (A, 'econ');
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  A = randn (500, 300);
  tic; [U, S, V] = svd (A, 'econ'); times(k) = toc () * 1000;
end
mem_mb = (300 * 300 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 7. Linear System Solve ──────────────────────────────────────────────────
name = 'Linear System Solve';
desc = 'Solve Ax=b for 1000x1000 A, 1000 b';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  B = randn (1000, 1000); A = B * B' + 1000 * eye (1000); b = randn (1000, 1);
  x = A \ b;
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  B = randn (1000, 1000); A = B * B' + 1000 * eye (1000); b = randn (1000, 1);
  tic; x = A \ b; times(k) = toc () * 1000;
end
mem_mb = (1000 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 8. Vector Dot Product ───────────────────────────────────────────────────
name = 'Vector Dot Product';
desc = 'Dot product of two 10M-element vectors';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  a = randn (10000000, 1); b = randn (10000000, 1); s = dot (a, b);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  a = randn (10000000, 1); b = randn (10000000, 1);
  tic; s = dot (a, b); times(k) = toc () * 1000;
end
mem_mb = 8 / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 9. Hadamard Product ─────────────────────────────────────────────────────
name = 'Hadamard Product';
desc = 'Element-wise multiply + add on 1000x1000 matrices';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  A = randn (1000, 1000); B = randn (1000, 1000); C = randn (1000, 1000);
  D = A .* B + C;
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  A = randn (1000, 1000); B = randn (1000, 1000); C = randn (1000, 1000);
  tic; D = A .* B + C; times(k) = toc () * 1000;
end
mem_mb = (1000 * 1000 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 10. QR Decomposition ────────────────────────────────────────────────────
name = 'QR Decomposition';
desc = 'QR factorisation of 500x500 matrix';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  A = randn (500, 500); [Q, R] = qr (A);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  A = randn (500, 500);
  tic; [Q, R] = qr (A); times(k) = toc () * 1000;
end
mem_mb = (500 * 500 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 11. FFT ─────────────────────────────────────────────────────────────────
name = 'FFT (real, 1M)';
desc = 'Full complex FFT sliced to N/2+1 (Octave fft; no native rfft)';
printf ('  Benchmarking: %s ...', name);
N_FFT = 2^20;
for k = 1:N_WARMUP
  v = randn (N_FFT, 1); f = fft (v); f = f(1:N_FFT/2+1);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  v = randn (N_FFT, 1);
  tic; f = fft (v); f = f(1:N_FFT/2+1); times(k) = toc () * 1000;
end
mem_mb = ((N_FFT / 2 + 1) * 16) / 1024^2;  % complex doubles
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── 12. Sort ────────────────────────────────────────────────────────────────
name = 'Sort 10M floats';
desc = 'Sort of 10M random float64 values';
printf ('  Benchmarking: %s ...', name);
for k = 1:N_WARMUP
  v = randn (10000000, 1); s = sort (v);
end
times = zeros (1, N_RUNS);
for k = 1:N_RUNS
  v = randn (10000000, 1);
  tic; s = sort (v); times(k) = toc () * 1000;
end
mem_mb = (10000000 * 8) / 1024^2;
results{end+1} = struct ('name', name, 'description', desc, ...
  'mean_ms', mean (times), 'std_ms', std (times), 'min_ms', min (times), 'memory_mb', mem_mb);
printf (' %.2f ms  (%.2f MB)\n', mean (times), mem_mb);

%% ── Write JSON ──────────────────────────────────────────────────────────────
% Build operations array as JSON string
ops_json = '[';
for k = 1:length (results)
  r = results{k};
  name_esc = strrep (r.name, '"', '\"');
  desc_esc = strrep (r.description, '"', '\"');
  entry = sprintf ('{"name":"%s","description":"%s","mean_ms":%.6f,"std_ms":%.6f,"min_ms":%.6f,"memory_mb":%.6f}', ...
    name_esc, desc_esc, r.mean_ms, r.std_ms, r.min_ms, r.memory_mb);
  if k < length (results)
    ops_json = [ops_json, entry, ','];
  else
    ops_json = [ops_json, entry];
  end
end
ops_json = [ops_json, ']'];

platform_str = computer ();
out = sprintf ('{\n  "language": "Octave",\n  "version": "Octave %s",\n  "platform": "%s",\n  "operations": %s\n}\n', ...
  ver_str, platform_str, ops_json);

[status, ~] = mkdir ('results');
fid = fopen ('results/octave_results.json', 'w');
fputs (fid, out);
fclose (fid);
printf ('Saved results/octave_results.json\n');
