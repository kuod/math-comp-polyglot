#!/usr/bin/env bash
# clean.sh — free up disk space by removing build artifacts and generated outputs.
# Everything removed here can be regenerated (see CLAUDE.md or run_all.sh).
#
# Usage:
#   ./clean.sh          # dry run — shows what would be deleted
#   ./clean.sh --force  # actually deletes

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=true
[[ "${1:-}" == "--force" ]] && DRY_RUN=false

$DRY_RUN && echo "Dry run — pass --force to actually delete."
$DRY_RUN || echo "Deleting..."
echo

action() { $DRY_RUN && echo "  [dry]" || echo "  [del]"; }

fmt_size() {
  local path="$1"
  du -sh "$path" 2>/dev/null | cut -f1
}

remove_dir() {
  local path="$1" desc="$2"
  if [[ -e "$path" ]]; then
    echo "  $(action) ${path#"$ROOT"/}/  ($(fmt_size "$path"))  — $desc"
    $DRY_RUN || rm -rf "$path"
  else
    echo "  [skip] ${path#"$ROOT"/}/  — not present"
  fi
}

remove_file() {
  local path="$1" desc="$2"
  if [[ -f "$path" ]]; then
    echo "  $(action) ${path#"$ROOT"/}  ($(fmt_size "$path"))  — $desc"
    $DRY_RUN || rm -f "$path"
  else
    echo "  [skip] ${path#"$ROOT"/}  — not present"
  fi
}

remove_dir  "$ROOT/rust/target"            "Rust build artifacts (cargo build --release)"
remove_dir  "$ROOT/haskell/dist-newstyle"  "Haskell build artifacts (cabal build)"
remove_dir  "$ROOT/go/pkg"                 "Go module cache (go build)"
remove_file "$ROOT/cpp/build_benchmark"    "C++ compiled binary"
remove_file "$ROOT/swift/swift-bench"      "Swift compiled binary"
remove_file "$ROOT/go/go-bench"            "Go compiled binary"
remove_file "$ROOT/index.html"             "Generated report (python3 generate_report.py)"

# results/*.json
shopt -s nullglob
json_files=("$ROOT"/results/*.json)
if [[ ${#json_files[@]} -gt 0 ]]; then
  names=$(printf "%s " "${json_files[@]##*/}")
  echo "  $(action) results/*.json  ($(fmt_size "$ROOT/results"))  — benchmark output ($names)"
  $DRY_RUN || rm -f "${json_files[@]}"
else
  echo "  [skip] results/*.json  — not present"
fi

echo
$DRY_RUN && echo "  Run './clean.sh --force' to delete."
