#!/usr/bin/env bash
# Regression test: a failing step must not abort run_all.sh; failure is
# reported and exit status is non-zero. Uses a sandbox PATH with a python3
# that fails every benchmark but passes the import probe.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/repo/python" "$T/repo/python_pandas"
cp "$ROOT/run_all.sh" "$T/repo/"
# fake python3: `-c` probes succeed, script runs fail
cat > "$T/bin/python3" <<'P'
#!/bin/sh
[ "$1" = "-c" ] && exit 0
echo "fake python3 failing: $*" >&2; exit 3
P
chmod +x "$T/bin/python3"
for tool in bash dirname mkdir; do ln -s "$(command -v $tool)" "$T/bin/$tool"; done
out="$(cd "$T/repo" && PATH="$T/bin" HOME="$T/none" bash ./run_all.sh 2>&1)"; rc=$?
echo "$out" | grep -q "FAILED – Python (NumPy)"  || { echo "FAIL: NumPy failure not reported"; exit 1; }
echo "$out" | grep -q "FAILED – Python (Pandas)" || { echo "FAIL: run aborted before Pandas"; exit 1; }
echo "$out" | grep -q "FAILED – Report generation" || { echo "FAIL: report step not reached"; exit 1; }
[ "$rc" -ne 0 ] || { echo "FAIL: exit status should be non-zero"; exit 1; }
echo "PASS"
