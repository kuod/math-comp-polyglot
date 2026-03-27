#!/usr/bin/env python3
"""Read per-language JSON results and emit a self-contained HTML report."""

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"

LANG_META = {
    "Python":  {"color": "#3776AB", "bg": "#EBF3FB", "logo": "🐍"},
    "R":       {"color": "#276DC3", "bg": "#EBF0FA", "logo": "📊"},
    "Julia":   {"color": "#9558B2", "bg": "#F3EBF9", "logo": "∑"},
    "Rust":    {"color": "#CE422B", "bg": "#FCECEA", "logo": "⚙"},
    "C++":     {"color": "#00599C", "bg": "#EBF4FA", "logo": "⚡"},
    "Haskell": {"color": "#5D4F85", "bg": "#F0EDF8", "logo": "λ"},
    "Swift":   {"color": "#F05138", "bg": "#FEF0ED", "logo": "🦅"},
    "Go":      {"color": "#00ACD7", "bg": "#E6F7FC", "logo": "🐹"},
}

LANG_MEMORY_NOTE = {
    "Python":  "tracemalloc (Python-managed heap)",
    "R":       "gc() Vcells delta (R heap)",
    "Julia":   "@allocated (total bytes allocated)",
    "Rust":    "custom GlobalAlloc peak tracker",
    "C++":     "output matrix size (Eigen uses malloc directly)",
    "Haskell": "GHC allocated_bytes delta (total bytes allocated by GC)",
    "Swift":   "output matrix size (Accelerate uses malloc directly)",
    "Go":      "runtime.TotalAlloc delta (cumulative bytes allocated)",
}

FILE_MAP = {
    "Python":  "python_results.json",
    "R":       "r_results.json",
    "Julia":   "julia_results.json",
    "Rust":    "rust_results.json",
    "C++":     "cpp_results.json",
    "Haskell": "haskell_results.json",
    "Swift":   "swift_results.json",
    "Go":      "go_results.json",
}


def load_results():
    data = {}
    for lang, fname in FILE_MAP.items():
        path = RESULTS_DIR / fname
        if path.exists():
            with open(path) as f:
                data[lang] = json.load(f)
    return data


def heat_color(value, lo, hi, invert=False):
    """Return a CSS background color: green=fast/low, red=slow/high."""
    if hi == lo:
        return "#f0f0f0"
    t = (value - lo) / (hi - lo)
    if invert:
        t = 1 - t
    # green → yellow → red
    if t < 0.5:
        r = int(255 * t * 2)
        g = 200
    else:
        r = 200
        g = int(200 * (1 - (t - 0.5) * 2))
    return f"rgba({r},{g},80,0.35)"


def fmt(val, decimals=2):
    if val is None:
        return "N/A"
    if val < 0.01:
        return f"{val:.4f}"
    return f"{val:.{decimals}f}"


def generate_html(data: dict) -> str:
    langs = list(data.keys())
    if not langs:
        sys.exit("No result files found. Run run_all.sh first.")

    # Collect operation names (ordered by first language found)
    op_names = []
    op_descs = {}
    for lang in langs:
        for op in data[lang]["operations"]:
            if op["name"] not in op_names:
                op_names.append(op["name"])
                op_descs[op["name"]] = op["description"]

    # Build lookup: op_table[lang][op_name] = {mean_ms, memory_mb, ...}
    op_table = {}
    for lang in langs:
        op_table[lang] = {}
        for op in data[lang]["operations"]:
            op_table[lang][op["name"]] = op

    # ── Chart.js datasets ──────────────────────────────────────────────────────
    chart_labels = json.dumps(op_names)

    time_datasets = []
    mem_datasets = []
    for lang in langs:
        meta = LANG_META.get(lang, {"color": "#888", "bg": "#eee", "logo": "?"})
        time_vals = [round(op_table[lang][op]["mean_ms"], 3) if op in op_table[lang] else None
                     for op in op_names]
        mem_vals  = [round(op_table[lang][op]["memory_mb"], 3) if op in op_table[lang] else None
                     for op in op_names]
        time_datasets.append({
            "label": lang,
            "data": time_vals,
            "backgroundColor": meta["color"] + "CC",
            "borderColor": meta["color"],
            "borderWidth": 1,
        })
        mem_datasets.append({
            "label": lang,
            "data": mem_vals,
            "backgroundColor": meta["color"] + "99",
            "borderColor": meta["color"],
            "borderWidth": 1,
        })

    time_ds_json = json.dumps(time_datasets)
    mem_ds_json  = json.dumps(mem_datasets)

    # ── Individual operation scatter charts (time vs memory) ──────────────────
    op_charts_js = []
    for idx, op in enumerate(op_names):
        # One dataset per language so each gets its own color + legend entry.
        # Skip languages that have no result for this op.
        scatter_datasets = []
        for lang in langs:
            if op not in op_table.get(lang, {}):
                continue
            meta = LANG_META.get(lang, {"color": "#888", "logo": "?"})
            t = round(op_table[lang][op]["mean_ms"], 4)
            m = round(op_table[lang][op]["memory_mb"], 4)
            scatter_datasets.append({
                "label": f'{meta["logo"]} {lang}',
                "data": [{"x": t, "y": m}],
                "backgroundColor": meta["color"] + "CC",
                "borderColor":     meta["color"],
                "pointRadius": 7,
                "pointHoverRadius": 10,
            })
        op_charts_js.append(f"""
        (function() {{
            var ctx = document.getElementById('opscatter_{idx}').getContext('2d');
            new Chart(ctx, {{
                type: 'scatter',
                data: {{ datasets: {json.dumps(scatter_datasets)} }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'right',
                            labels: {{ boxWidth: 10, font: {{ size: 10 }}, padding: 6 }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(ctx) {{
                                    return ctx.dataset.label + ': '
                                        + ctx.parsed.x.toFixed(2) + ' ms, '
                                        + ctx.parsed.y.toFixed(2) + ' MB';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            beginAtZero: true,
                            title: {{ display: true, text: 'Time (ms)', font: {{ size: 10 }} }},
                            ticks: {{ font: {{ size: 9 }} }}
                        }},
                        y: {{
                            beginAtZero: true,
                            title: {{ display: true, text: 'Memory (MB)', font: {{ size: 10 }} }},
                            ticks: {{ font: {{ size: 9 }} }}
                        }}
                    }}
                }}
            }});
        }})();""")

    op_charts_js_str = "\n".join(op_charts_js)

    # ── Summary table rows ─────────────────────────────────────────────────────
    table_rows = []
    for op in op_names:
        cells_time = []
        cells_mem  = []
        time_vals_row = {
            lang: op_table[lang][op]["mean_ms"]
            for lang in langs if op in op_table.get(lang, {})
        }
        mem_vals_row = {
            lang: op_table[lang][op]["memory_mb"]
            for lang in langs if op in op_table.get(lang, {})
        }
        t_lo = min(time_vals_row.values()) if time_vals_row else 0
        t_hi = max(time_vals_row.values()) if time_vals_row else 1
        m_lo = min(mem_vals_row.values()) if mem_vals_row else 0
        m_hi = max(mem_vals_row.values()) if mem_vals_row else 1

        for lang in langs:
            if op in op_table.get(lang, {}):
                t  = op_table[lang][op]["mean_ms"]
                sd = op_table[lang][op]["std_ms"]
                m  = op_table[lang][op]["memory_mb"]
                tc = heat_color(t, t_lo, t_hi, invert=False)
                mc = heat_color(m, m_lo, m_hi, invert=False)
                winner_t = "🥇 " if t == t_lo else ""
                winner_m = "🥇 " if m == m_lo else ""
                cells_time.append(
                    f'<td style="background:{tc};text-align:center">'
                    f'{winner_t}<strong>{fmt(t)}</strong>'
                    f'<br><span style="font-size:0.75em;color:#666">±{fmt(sd)}</span></td>'
                )
                cells_mem.append(
                    f'<td style="background:{mc};text-align:center">'
                    f'{winner_m}{fmt(m)}</td>'
                )
            else:
                cells_time.append('<td style="text-align:center;color:#bbb">—</td>')
                cells_mem.append('<td style="text-align:center;color:#bbb">—</td>')

        desc = op_descs.get(op, "")
        row = (
            f'<tr><td class="op-name">{op}<br>'
            f'<span style="font-weight:normal;font-size:0.78em;color:#666">{desc}</span></td>'
            f'{"".join(cells_time)}'
            f'{"".join(cells_mem)}</tr>'
        )
        table_rows.append(row)

    table_rows_html = "\n".join(table_rows)

    # ── Lang header cells ──────────────────────────────────────────────────────
    lang_headers_time = "".join(
        f'<th style="background:{LANG_META.get(l,{}).get("color","#888")}22;'
        f'color:{LANG_META.get(l,{}).get("color","#333")};text-align:center">'
        f'{LANG_META.get(l,{}).get("logo","?")} {l}<br>'
        f'<span style="font-weight:normal;font-size:0.7em">'
        f'{data[l].get("version","")}</span></th>'
        for l in langs
    )
    lang_headers_mem = "".join(
        f'<th style="background:{LANG_META.get(l,{}).get("color","#888")}22;'
        f'color:{LANG_META.get(l,{}).get("color","#333")};text-align:center">'
        f'{l}</th>'
        for l in langs
    )

    # ── Op cards (mini charts) ─────────────────────────────────────────────────
    op_cards = []
    for idx, op in enumerate(op_names):
        desc = op_descs.get(op, "")
        op_cards.append(f"""
        <div class="op-card">
            <div class="op-card-title">{op}</div>
            <div class="op-card-desc">{desc}</div>
            <canvas id="opscatter_{idx}" height="180"></canvas>
        </div>""")

    op_cards_html = "\n".join(op_cards)

    # ── Golf-style scores: rank each lang per op (1=fastest), sum ranks ──────
    # Langs missing an op are excluded from that op's ranking (no penalty).
    golf_scores = {lang: 0 for lang in langs}
    for op in op_names:
        participating = [
            (op_table[l][op]["mean_ms"], l)
            for l in langs if op in op_table.get(l, {})
        ]
        participating.sort()          # ascending by time
        for rank, (_, l) in enumerate(participating, start=1):
            golf_scores[l] += rank

    # Sort langs by golf score (ascending = better) for the leaderboard
    ranked_langs = sorted(langs, key=lambda l: golf_scores[l])

    # ── Memory golf scores: rank each lang per op by memory_mb ───────────────
    mem_golf_scores = {lang: 0 for lang in langs}
    for op in op_names:
        participating_mem = [
            (op_table[l][op]["memory_mb"], l)
            for l in langs if op in op_table.get(l, {})
        ]
        participating_mem.sort()      # ascending by memory
        for rank, (_, l) in enumerate(participating_mem, start=1):
            mem_golf_scores[l] += rank

    mem_ranked_langs = sorted(langs, key=lambda l: mem_golf_scores[l])

    # Assign overall place (1-indexed)
    overall_place = {l: i + 1 for i, l in enumerate(ranked_langs)}
    place_medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    # ── Language summary cards ─────────────────────────────────────────────────
    lang_cards = []
    for lang in ranked_langs:
        meta = LANG_META.get(lang, {"color": "#888", "bg": "#eee", "logo": "?"})
        ops = data[lang]["operations"]
        avg_time = sum(o["mean_ms"] for o in ops) / len(ops) if ops else 0
        avg_mem  = sum(o["memory_mb"] for o in ops) / len(ops) if ops else 0
        score = golf_scores[lang]
        place = overall_place[lang]
        medal = place_medals.get(place, f"#{place}")
        lang_cards.append(f"""
        <div class="lang-card" style="border-top:4px solid {meta['color']}">
            <div class="lang-logo" style="color:{meta['color']}">{meta['logo']}</div>
            <div class="lang-name" style="color:{meta['color']}">{lang}</div>
            <div class="lang-version">{data[lang].get('version','')}</div>
            <div class="lang-stats">
                <div class="stat"><span class="stat-val">{fmt(avg_time)}</span><span class="stat-lbl">avg ms</span></div>
                <div class="stat"><span class="stat-val">{fmt(avg_mem)}</span><span class="stat-lbl">avg MB</span></div>
                <div class="stat"><span class="stat-val">{medal} {score}</span><span class="stat-lbl">score (lower=better)</span></div>
            </div>
        </div>""")

    lang_cards_html = "\n".join(lang_cards)

    # ── Per-op rank matrix (speed) ────────────────────────────────────────────
    op_ranks = {l: {} for l in langs}  # op_ranks[lang][op] = 1-based rank
    for op in op_names:
        ordered = sorted(
            [(op_table[l][op]["mean_ms"], l) for l in langs if op in op_table.get(l, {})],
        )
        for rank, (_, l) in enumerate(ordered, start=1):
            op_ranks[l][op] = rank

    # ── Per-op rank matrix (memory) ───────────────────────────────────────────
    mem_op_ranks = {l: {} for l in langs}
    for op in op_names:
        ordered_mem = sorted(
            [(op_table[l][op]["memory_mb"], l) for l in langs if op in op_table.get(l, {})],
        )
        for rank, (_, l) in enumerate(ordered_mem, start=1):
            mem_op_ranks[l][op] = rank

    def rank_bg(rank, n):
        """Green for low rank (fast), red for high rank (slow)."""
        t = (rank - 1) / max(n - 1, 1)
        if t < 0.5:
            r = int(40 + 200 * t * 2)
            g = 185
        else:
            r = 200
            g = int(185 * (1 - (t - 0.5) * 2))
        return f"rgba({r},{g},40,0.35)"

    # ── Leaderboard tables ────────────────────────────────────────────────────
    op_abbrev = {
        "Matrix Multiply":      "MatMul",
        "Matrix Inverse":       "Inv",
        "LU Decomposition":     "LU",
        "Eigenvalue Decomp":    "Eigen",
        "Cholesky":             "Chol",
        "SVD":                  "SVD",
        "Linear System Solve":  "LinSolve",
        "Vector Dot Product":   "Dot",
        "Hadamard Product":     "Hadamard",
        "QR Decomposition":     "QR",
        "FFT (real, 1M)":       "FFT",
        "Sort 10M floats":      "Sort",
    }
    lb_op_headers = "".join(
        f'<th title="{op}">{op_abbrev.get(op, op)}</th>' for op in op_names
    )

    def build_lb_rows(ranked, scores, ranks_dict):
        rows = []
        for i, lang in enumerate(ranked):
            meta = LANG_META.get(lang, {"color": "#888", "logo": "?"})
            place = i + 1
            medal = place_medals.get(place, f"#{place}")
            score = scores[lang]
            cells = []
            for op in op_names:
                if op in ranks_dict[lang]:
                    r = ranks_dict[lang][op]
                    n = sum(1 for l in langs if op in ranks_dict[l])
                    gold = " lb-gold" if r == 1 else ""
                    cells.append(
                        f'<td class="lb-rank{gold}" style="background:{rank_bg(r,n)}">{r}</td>'
                    )
                else:
                    cells.append('<td style="color:#ccc;text-align:center">—</td>')
            rows.append(
                f'<tr>'
                f'<td class="lb-place">{medal}</td>'
                f'<td class="lb-lang" style="color:{meta["color"]}">'
                f'{meta["logo"]} {lang}</td>'
                f'<td class="lb-score"><strong>{score}</strong></td>'
                f'{"".join(cells)}'
                f'</tr>'
            )
        return rows

    speed_rows = build_lb_rows(ranked_langs, golf_scores, op_ranks)
    mem_rows   = build_lb_rows(mem_ranked_langs, mem_golf_scores, mem_op_ranks)

    def lb_table(rows):
        return (
            f'<div class="table-wrap">'
            f'<table class="lb-table">'
            f'<thead><tr>'
            f'<th>Rank</th><th>Language</th><th>Score</th>'
            f'{lb_op_headers}'
            f'</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div>'
        )

    leaderboard_html = f"""
<div class="section">
  <h2>Leaderboard — Golf Scoring (1st = 1 pt · lowest score wins)</h2>
  <p style="font-size:.85rem;color:#666;margin-bottom:1.5rem">
    Each cell shows a language's finishing position for that operation.
    Scores are summed across all operations. Languages missing an operation (Haskell/FFT)
    are excluded from that op's ranking and receive no penalty points.
  </p>

  <h3 style="margin-bottom:.5rem">⚡ Speed Ranking</h3>
  <p style="font-size:.82rem;color:#666;margin-bottom:.75rem">Ranked by mean execution time (ms) — lower is faster.</p>
  {lb_table(speed_rows)}

  <h3 style="margin-top:2rem;margin-bottom:.5rem">💾 Memory Ranking</h3>
  <p style="font-size:.82rem;color:#666;margin-bottom:.75rem">Ranked by peak memory usage (MB) — lower is leaner. Note: memory measurements are not apples-to-apples across languages (see Glossary).</p>
  {lb_table(mem_rows)}
</div>"""

    # ── Executive summary ──────────────────────────────────────────────────────
    winner = ranked_langs[0]
    runner_up = ranked_langs[1] if len(ranked_langs) > 1 else ""
    third = ranked_langs[2] if len(ranked_langs) > 2 else ""
    winner_meta = LANG_META.get(winner, {"color": "#888"})
    mem_winner = mem_ranked_langs[0]
    mem_runner_up = mem_ranked_langs[1] if len(mem_ranked_langs) > 1 else ""
    mem_third = mem_ranked_langs[2] if len(mem_ranked_langs) > 2 else ""
    mem_winner_meta = LANG_META.get(mem_winner, {"color": "#888"})

    # Languages that link system BLAS/LAPACK (fast on dense ops)
    blas_langs = {"Python", "R", "Julia", "Haskell", "Swift"}
    pure_langs  = {"Rust", "C++", "Go"}

    # Find top performer per op
    op_winners = {}
    for op in op_names:
        ordered = sorted(
            [(op_table[l][op]["mean_ms"], l) for l in langs if op in op_table.get(l, {})],
        )
        if ordered:
            op_winners[op] = ordered[0][1]

    # Count gold medals per lang
    gold_counts = {}
    for op, w in op_winners.items():
        gold_counts[w] = gold_counts.get(w, 0) + 1

    # Fastest BLAS op (Cholesky tends to separate best)
    chol_winner = op_winners.get("Cholesky", "Swift")

    # Sort winner / loser
    sort_op = "Sort 10M floats"
    sort_ordered = sorted(
        [(op_table[l][sort_op]["mean_ms"], l) for l in langs if sort_op in op_table.get(l, {})],
    )
    sort_winner   = sort_ordered[0][1]  if sort_ordered else "Julia"
    sort_slowest  = sort_ordered[-1][1] if sort_ordered else "Go"

    # Rust near-zero memory ops
    rust_zero_ops = [op for op in ["Cholesky", "LU Decomposition", "QR Decomposition"]
                     if op in op_table.get("Rust", {}) and op_table["Rust"][op]["memory_mb"] < 0.05]
    rust_zero_str = ", ".join(rust_zero_ops) if rust_zero_ops else ""

    # Build bullet insights
    blas_present = sorted(blas_langs & set(langs))
    pure_present  = sorted(pure_langs & set(langs))

    gold_bullets = "".join(
        f'<li><strong>{l}</strong> leads {gold_counts[l]} operation{"s" if gold_counts[l]>1 else ""}: '
        f'{", ".join(op for op in op_names if op_winners.get(op)==l)}</li>'
        for l in ranked_langs if l in gold_counts
    )

    exec_summary_html = f"""
<div class="section exec-summary">
  <h2>Executive Summary</h2>
  <div class="exec-grid">

    <div class="exec-card exec-winner">
      <div class="exec-label">⚡ Speed Winner</div>
      <div class="exec-hero" style="color:{winner_meta['color']}">
        🥇 {winner}
      </div>
      <div class="exec-sub">Score: {golf_scores[winner]} &nbsp;|&nbsp;
        Runner-up: {runner_up} ({golf_scores.get(runner_up,'')}) &nbsp;|&nbsp;
        3rd: {third} ({golf_scores.get(third,'')})
      </div>
    </div>

    <div class="exec-card exec-winner">
      <div class="exec-label">💾 Memory Winner</div>
      <div class="exec-hero" style="color:{mem_winner_meta['color']}">
        🥇 {mem_winner}
      </div>
      <div class="exec-sub">Score: {mem_golf_scores[mem_winner]} &nbsp;|&nbsp;
        Runner-up: {mem_runner_up} ({mem_golf_scores.get(mem_runner_up,'')}) &nbsp;|&nbsp;
        3rd: {mem_third} ({mem_golf_scores.get(mem_third,'')})
      </div>
    </div>

    <div class="exec-card">
      <div class="exec-label">Gold Medals by Operation</div>
      <ul class="exec-list">{gold_bullets}</ul>
    </div>

    <div class="exec-card">
      <div class="exec-label">Two Performance Tiers</div>
      <p><strong>BLAS/LAPACK-linked</strong> ({", ".join(blas_present)}): call
        hand-optimised vendor routines (Apple Accelerate on this machine) for
        dense matrix work — typically 5–20× faster than pure implementations on
        large factorisation benchmarks.</p>
      <p style="margin-top:.5rem"><strong>Pure implementations</strong>
        ({", ".join(pure_present)}): Rust/nalgebra, C++/Eigen, Go/gonum implement
        their own algorithms without calling LAPACK. Slower on BLAS-heavy ops, but
        competitive on element-wise and algorithm-class workloads.</p>
    </div>

    <div class="exec-card">
      <div class="exec-label">Notable Findings</div>
      <ul class="exec-list">
        <li><strong>Swift/Accelerate</strong> dominates factorisation ops
          (Cholesky, LU, QR) thanks to Apple Silicon-tuned Accelerate — even
          beating Python/NumPy and Julia on several ops.</li>
        <li><strong>Sort</strong>: {sort_winner} is fastest; {sort_slowest} and Swift
          are ~4–5× slower, exposing meaningful differences in standard-library
          sort implementations at 10M elements.</li>
        {"<li><strong>Rust near-zero memory</strong> for " + rust_zero_str +
          ": nalgebra performs these factorisations in-place on the moved input, so no extra allocation is needed — correct behaviour, not a gap in measurement.</li>"
          if rust_zero_str else ""}
        <li><strong>Haskell</strong> is excluded from FFT (shows —): the
          vector-fftw library uses CDouble rather than Haskell Double, making
          a safe, comparable benchmark impractical.</li>
        <li><strong>Go/gonum</strong> scores last: gonum is a pure-Go library
          with no LAPACK linkage, resulting in the highest scores across the
          board on dense linear algebra.</li>
      </ul>
    </div>

  </div>
</div>"""

    # ── Glossary ───────────────────────────────────────────────────────────────
    glossary_entries = [
        ("Matrix Multiply", "A × B where A, B are 1000×1000",
         "The canonical dense linear algebra kernel. Measures peak BLAS DGEMM throughput. "
         "BLAS-linked languages call <code>cblas_dgemm</code> (O(n³) with SIMD/multi-core "
         "optimisation); pure implementations use naive or cache-blocked loops. "
         "Results vary by 2–10× depending on whether vendor BLAS is used."),

        ("Matrix Inverse", "A⁻¹ for a 500×500 symmetric positive-definite (SPD) matrix",
         "Computed via LU factorisation (DGETRF) followed by triangular solve (DGETRI). "
         "Matrix inversion is rarely used directly in practice — solving Ax=b with "
         "<em>Linear System Solve</em> is numerically preferable — but it is a standard "
         "benchmark for full LAPACK integration."),

        ("LU Decomposition", "A = P·L·U factorisation of a 500×500 matrix",
         "Partial-pivot LU (DGETRF) is the workhorse factorisation underlying matrix "
         "inversion and general linear solves. Measures LAPACK integration and cache "
         "efficiency on a medium-sized problem. Often the fastest path for non-symmetric "
         "systems."),

        ("Eigenvalue Decomp", "Full symmetric eigendecomposition of a 300×300 matrix",
         "Computes all eigenvalues and eigenvectors of a symmetric matrix (DSYEV/DSYEVD). "
         "Used in PCA, graph algorithms, quantum mechanics, and structural analysis. "
         "Iterative reduction to tridiagonal form makes this slower than Cholesky but "
         "faster than general (non-symmetric) eigen for the same size."),

        ("Cholesky", "L·Lᵀ factorisation of a 500×500 SPD matrix",
         "The fastest dense factorisation for symmetric positive-definite matrices "
         "(DPOTRF). Half the cost of LU due to symmetry exploitation. Used in Kalman "
         "filters, Gaussian processes, and least-squares problems. A sensitive indicator "
         "of raw BLAS Level-3 throughput."),

        ("SVD", "Full thin SVD of a 500×300 matrix (U, Σ, Vᵀ)",
         "Singular Value Decomposition (DGESDD) is the foundation of dimensionality "
         "reduction (PCA/LSA), pseudo-inverse computation, and low-rank approximation. "
         "Uses a divide-and-conquer algorithm internally. More expensive than Cholesky "
         "or LU due to iterative bidiagonalisation."),

        ("Linear System Solve", "Solve Ax = b for 1000×1000 SPD A and 1000-element b",
         "The practical alternative to matrix inversion: factorises A (Cholesky for SPD "
         "or LU for general) then performs triangular solves. The correct numerical "
         "approach for Ax=b. Larger problem size (1000) than the factorisation benchmarks "
         "to stress memory bandwidth alongside compute."),

        ("Vector Dot Product", "x·y for two 10-million-element vectors",
         "A memory-bandwidth-bound BLAS Level-1 operation (DDOT). At 10M doubles the "
         "vectors exceed typical L3 cache, so performance reflects RAM bandwidth and "
         "SIMD utilisation rather than arithmetic throughput. Exposes overhead from "
         "interpreted dispatch (R, Python) vs compiled tight loops."),

        ("Hadamard Product", "C = A ⊙ B + C for three 1000×1000 matrices",
         "Element-wise (pointwise) multiply-then-add — not a BLAS operation, so every "
         "language must loop over 1M doubles itself. Tests compiler vectorisation "
         "(SIMD auto-vectorisation in Rust/C++/Julia) and interpreter overhead "
         "(Python, R). Julia and Rust typically win here."),

        ("QR Decomposition", "Householder QR of a 500×500 matrix (R factor)",
         "QR factorisation (DGEQRF) underpins least-squares solvers, eigenvalue "
         "algorithms, and orthogonalisation. Only the compact R factor is forced in "
         "all languages; forming the full Q is significantly more expensive. Haskell "
         "in particular would be ~400× slower if Q were materialised via its "
         "Haskell-level Householder products."),

        ("FFT (real, 1M)", "Real FFT of 2²⁰ = 1 048 576 samples",
         "Fast Fourier Transform (O(n log n)) is the backbone of signal processing, "
         "audio/image analysis, spectral methods, and fast polynomial multiplication. "
         "Completely different algorithm class from BLAS. Implementations range from "
         "FFTW (near-optimal, used by Python/NumPy and Julia/FFTW.jl) to RustFFT "
         "(pure-Rust) and gonum's pure-Go FFT. Haskell is excluded (N/A)."),

        ("Sort 10M floats", "Unstable sort of 10 million random float64 values",
         "A pure-algorithm, comparison-based sort workload with no linear-algebra "
         "library involvement. Tests the quality of each language's standard-library "
         "sort (introsort, pdqsort, radix sort). At 10M elements the working set "
         "exceeds L3 cache, making memory-access pattern and branch-prediction "
         "efficiency critical. Results span a 7× range across languages."),
    ]

    glossary_cards = []
    for i, (name, signature, body) in enumerate(glossary_entries, start=1):
        op_winner_name = op_winners.get(name, "")
        op_winner_meta = LANG_META.get(op_winner_name, {"color": "#888"})
        fastest_badge = (
            f'<span class="gloss-badge" style="background:{op_winner_meta["color"]}">'
            f'Fastest: {op_winner_meta.get("logo","")} {op_winner_name}</span>'
            if op_winner_name else ""
        )
        # Best time for this op
        best_ms = ""
        if op_winner_name and name in op_table.get(op_winner_name, {}):
            best_ms = f'{op_table[op_winner_name][name]["mean_ms"]:.2f} ms'

        glossary_cards.append(f"""
    <div class="gloss-card">
      <div class="gloss-num">{i:02d}</div>
      <div class="gloss-body">
        <div class="gloss-title">{name}
          {fastest_badge}
          {"<span class='gloss-best'>" + best_ms + "</span>" if best_ms else ""}
        </div>
        <div class="gloss-sig"><code>{signature}</code></div>
        <p class="gloss-text">{body}</p>
      </div>
    </div>""")

    glossary_html = f"""
<div class="section">
  <h2>Glossary — What Each Benchmark Measures</h2>
  <div class="gloss-grid">
    {"".join(glossary_cards)}
  </div>
</div>"""

    # ── Memory notes for footer ────────────────────────────────────────────────
    mem_note_parts = []
    for l in langs:
        col = LANG_META.get(l, {}).get("color", "#888")
        note = LANG_MEMORY_NOTE.get(l, "")
        mem_note_parts.append(f'<span style="color:{col}">{l}</span>: {note}')
    mem_notes_html = " &nbsp;·&nbsp; ".join(mem_note_parts)

    # ── Assemble HTML ──────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Numerical Computing Benchmark: 8 Languages · 12 Operations</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f6f9;
    color: #1a1a2e;
    line-height: 1.5;
  }}
  header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    color: #fff;
    padding: 2.5rem 2rem 2rem;
    text-align: center;
  }}
  header h1 {{ font-size: 2rem; letter-spacing: -0.5px; margin-bottom: .4rem; }}
  header p  {{ opacity: .8; font-size: .95rem; }}
  .badge {{
    display: inline-block;
    padding: .2em .7em;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 600;
    margin: .2em;
    color: #fff;
  }}
  .section {{ max-width: 1400px; margin: 2rem auto; padding: 0 1.5rem; }}
  h2 {{ font-size: 1.2rem; margin-bottom: 1rem; color: #16213e; border-left: 4px solid #0f3460; padding-left: .6rem; }}

  /* ── Language summary cards ── */
  .lang-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .lang-card {{
    background: #fff;
    border-radius: 12px;
    padding: 1.2rem 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
    text-align: center;
  }}
  .lang-logo  {{ font-size: 2rem; margin-bottom: .2rem; }}
  .lang-name  {{ font-size: 1.1rem; font-weight: 700; }}
  .lang-version {{ font-size: .7rem; color: #888; margin: .2rem 0 .8rem; min-height: 1.2em; }}
  .lang-stats {{ display: flex; justify-content: space-around; }}
  .stat       {{ display: flex; flex-direction: column; align-items: center; }}
  .stat-val   {{ font-weight: 700; font-size: .95rem; }}
  .stat-lbl   {{ font-size: .65rem; color: #999; }}

  /* ── Overview charts ── */
  .charts-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }}
  @media(max-width:800px) {{ .charts-row {{ grid-template-columns: 1fr; }} }}
  .chart-box {{
    background: #fff;
    border-radius: 12px;
    padding: 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
  }}
  .chart-box h3 {{ font-size: .95rem; margin-bottom: .8rem; color: #444; }}

  /* ── Op cards ── */
  .op-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 1.2rem;
    margin-bottom: 2rem;
  }}
  @media(max-width:500px) {{ .op-grid {{ grid-template-columns: 1fr; }} }}
  .op-card {{
    background: #fff;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
  }}
  .op-card-title {{ font-weight: 700; font-size: 1rem; margin-bottom: .1rem; }}
  .op-card-desc  {{ font-size: .75rem; color: #888; margin-bottom: .6rem; }}
  .chart-label {{ font-size: .7rem; color: #aaa; text-align: center; margin-bottom: .2rem; }}

  /* ── Summary table ── */
  .table-wrap {{ overflow-x: auto; margin-bottom: 2rem; }}
  table {{
    border-collapse: collapse;
    min-width: 860px;
    width: 100%;
    font-size: .83rem;
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
  }}
  thead tr {{ background: #16213e; color: #fff; }}
  th {{ padding: .7rem .6rem; font-weight: 600; }}
  td {{ padding: .6rem .6rem; border-bottom: 1px solid #f0f0f0; }}
  tr:last-child td {{ border-bottom: none; }}
  .op-name {{ font-weight: 600; min-width: 160px; }}
  tr:hover {{ background: #fafbff; }}

  /* ── Legend ── */
  .legend {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    font-size: .8rem;
    margin-bottom: 1.5rem;
    align-items: center;
  }}
  .legend-item {{ display: flex; align-items: center; gap: .3rem; }}
  .swatch {{ width: 14px; height: 14px; border-radius: 3px; }}

  footer {{
    text-align: center;
    padding: 2rem;
    font-size: .8rem;
    color: #999;
  }}

  /* ── Executive summary ── */
  .exec-summary {{ margin-bottom: 0; }}
  .exec-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  @media(max-width:700px) {{ .exec-grid {{ grid-template-columns: 1fr; }} }}
  .exec-card {{
    background: #fff;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
    font-size: .88rem;
    line-height: 1.6;
  }}
  .exec-winner {{ grid-column: 1 / -1; text-align: center; }}
  .exec-label {{ font-size: .7rem; font-weight: 700; text-transform: uppercase;
                 letter-spacing: .08em; color: #999; margin-bottom: .4rem; }}
  .exec-hero  {{ font-size: 2.2rem; font-weight: 800; margin: .3rem 0; }}
  .exec-sub   {{ font-size: .82rem; color: #666; }}
  .exec-list  {{ padding-left: 1.2rem; }}
  .exec-list li {{ margin-bottom: .35rem; }}

  /* ── Leaderboard table ── */
  .lb-table {{ font-size: .82rem; }}
  .lb-table thead th {{ font-size: .75rem; padding: .5rem .4rem; }}
  .lb-place {{ text-align: center; font-size: 1.1rem; width: 2rem; }}
  .lb-lang  {{ font-weight: 700; white-space: nowrap; padding-left: .6rem; }}
  .lb-score {{ text-align: center; font-size: 1rem; padding: .4rem .6rem;
               background: #f8f8ff; }}
  .lb-rank  {{ text-align: center; font-weight: 600; padding: .4rem .35rem;
               min-width: 2.2rem; }}
  .lb-gold  {{ font-weight: 800; }}

  /* ── Glossary ── */
  .gloss-grid {{
    display: flex;
    flex-direction: column;
    gap: .85rem;
    margin-bottom: 2rem;
  }}
  .gloss-card {{
    background: #fff;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 6px rgba(0,0,0,.06);
    display: flex;
    gap: 1rem;
    align-items: flex-start;
  }}
  .gloss-num {{
    font-size: 1.4rem;
    font-weight: 800;
    color: #d0d4e0;
    min-width: 2.2rem;
    text-align: right;
    line-height: 1.2;
    padding-top: .1rem;
  }}
  .gloss-body {{ flex: 1; }}
  .gloss-title {{
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: .2rem;
    display: flex;
    align-items: center;
    gap: .5rem;
    flex-wrap: wrap;
  }}
  .gloss-badge {{
    font-size: .68rem;
    color: #fff;
    padding: .15em .55em;
    border-radius: 999px;
    font-weight: 600;
  }}
  .gloss-best {{
    font-size: .72rem;
    color: #888;
    font-weight: 400;
  }}
  .gloss-sig {{
    font-size: .78rem;
    color: #666;
    margin-bottom: .4rem;
  }}
  .gloss-sig code {{ background: #f4f6f9; padding: .1em .4em; border-radius: 4px; }}
  .gloss-text {{ font-size: .84rem; color: #444; line-height: 1.6; }}
  .gloss-text code {{ background: #f4f6f9; padding: .1em .35em; border-radius: 3px;
                      font-size: .92em; }}
  .gloss-text em {{ font-style: italic; }}

  /* ── Appendix / Changelog ── */
  .chg-list {{ list-style: none; display: flex; flex-direction: column; gap: .7rem; margin-bottom: 2rem; }}
  .chg-item {{
    background: #fff;
    border-radius: 10px;
    padding: .9rem 1.2rem;
    box-shadow: 0 2px 6px rgba(0,0,0,.06);
    display: grid;
    grid-template-columns: 7rem 1fr;
    gap: .5rem 1rem;
    font-size: .84rem;
    align-items: start;
  }}
  @media(max-width:600px) {{ .chg-item {{ grid-template-columns: 1fr; }} }}
  .chg-date {{ font-weight: 700; color: #999; font-size: .75rem; padding-top: .15rem; }}
  .chg-body {{ line-height: 1.6; }}
  .chg-body strong {{ color: #16213e; }}
  .chg-body a {{ color: #0f3460; text-decoration: none; }}
  .chg-body a:hover {{ text-decoration: underline; }}
  .chg-tag {{
    display: inline-block;
    font-size: .65rem;
    font-weight: 700;
    padding: .1em .5em;
    border-radius: 999px;
    margin-right: .3em;
    vertical-align: middle;
    color: #fff;
  }}
  .chg-fix  {{ background: #e05252; }}
  .chg-feat {{ background: #2ecc71; }}
  .chg-data {{ background: #3498db; }}
</style>
</head>
<body>

<header>
  <h1>Numerical Computing Benchmark</h1>
  <p>{len(op_names)} operations &nbsp;·&nbsp; {len(langs)} languages &nbsp;·&nbsp; speed &amp; memory comparison</p>
  <div style="margin-top:1rem">
    {"".join(f'<span class="badge" style="background:{LANG_META.get(l,{}).get("color","#888")}">{LANG_META.get(l,{}).get("logo","?")} {l}</span>' for l in langs)}
  </div>
</header>

{exec_summary_html}

{leaderboard_html}

<!-- ── Language cards ── -->
<div class="section">
  <h2>Language Summary</h2>
  <div class="lang-grid">
    {lang_cards_html}
  </div>
</div>

<!-- ── Overview charts ── -->
<div class="section">
  <h2>Overview: All Operations</h2>
  <div class="charts-row">
    <div class="chart-box">
      <h3>Execution Time (ms) — lower is better</h3>
      <canvas id="timeChart" height="260"></canvas>
    </div>
    <div class="chart-box">
      <h3>Memory Allocated (MB) — lower is better</h3>
      <canvas id="memChart" height="260"></canvas>
    </div>
  </div>
</div>

<!-- ── Per-operation scatter charts ── -->
<div class="section">
  <h2>Per-Operation: Time vs Memory</h2>
  <div class="op-grid">
    {op_cards_html}
  </div>
</div>

<!-- ── Summary table ── -->
<div class="section">
  <h2>Full Comparison Table</h2>
  <div class="legend">
    <span>Time (ms): 🥇 fastest &nbsp; background: <span style="background:rgba(0,200,80,0.35);padding:1px 6px;border-radius:3px">fast</span> → <span style="background:rgba(200,80,80,0.35);padding:1px 6px;border-radius:3px">slow</span></span>
    &nbsp;|&nbsp;
    <span>Same scale for Memory (MB)</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th rowspan="2" style="text-align:left">Operation</th>
          <th colspan="{len(langs)}" style="border-bottom:1px solid #ffffff33">Time (ms) mean ± std</th>
          <th colspan="{len(langs)}" style="border-bottom:1px solid #ffffff33">Memory (MB)</th>
        </tr>
        <tr>
          {lang_headers_time}
          {lang_headers_mem}
        </tr>
      </thead>
      <tbody>
        {table_rows_html}
      </tbody>
    </table>
  </div>
</div>

{glossary_html}

<div class="section">
  <h2>Appendix — Changelog</h2>
  <ul class="chg-list">
    <li class="chg-item">
      <span class="chg-date">2026-03-26</span>
      <span class="chg-body">
        <span class="chg-tag chg-fix">fix</span>
        <strong>Haskell — LU Decomposition benchmark corrected</strong><br>
        A pull-request from
        <a href="https://github.com/jonocarroll" target="_blank">@jonocarroll</a>
        switched the LU harness to <code>luPacked</code> + <code>evaluate</code>.
        However, GHC's <code>evaluate</code> only forces the outermost constructor
        to WHNF; the underlying LAPACK <code>dgetrf</code> call remained a thunk,
        producing spurious 0.00 ms / 0.00 MB results.
        Fixed by forcing the explicit L and U factor matrices
        (<code>lu m</code> with <code>forceM l &gt;&gt; forceM u</code>),
        which drives evaluation all the way through.
        Corrected timings: <strong>17.29 ms</strong>, <strong>130.36 MB</strong>.
        Thanks <a href="https://github.com/jonocarroll" target="_blank">@jonocarroll</a>
        for the contribution!
      </span>
    </li>
  </ul>
</div>

<footer>
  Generated by generate_report.py &nbsp;|&nbsp; Fixed seed 42 &nbsp;|&nbsp;
  Times: mean of 10 runs after 3 warmup rounds<br>
  <strong>Memory methodology:</strong> &nbsp; {mem_notes_html}
</footer>

<script>
// ── Overview charts ────────────────────────────────────────────────────────────
(function() {{
  var labels = {chart_labels};
  var timeDs = {time_ds_json};
  var memDs  = {mem_ds_json};

  var shortLabels = labels.map(function(l) {{
    return l.length > 14 ? l.substring(0,13)+'…' : l;
  }});

  new Chart(document.getElementById('timeChart').getContext('2d'), {{
    type: 'bar',
    data: {{ labels: shortLabels, datasets: timeDs }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ position: 'top', labels: {{ boxWidth: 12 }} }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{ return ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(2) + ' ms'; }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ font: {{ size: 10 }} }} }},
        y: {{ beginAtZero: true, title: {{ display: true, text: 'ms' }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('memChart').getContext('2d'), {{
    type: 'bar',
    data: {{ labels: shortLabels, datasets: memDs }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ position: 'top', labels: {{ boxWidth: 12 }} }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{ return ctx.dataset.label + ': ' + (ctx.parsed.y||0).toFixed(2) + ' MB'; }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ font: {{ size: 10 }} }} }},
        y: {{ beginAtZero: true, title: {{ display: true, text: 'MB' }} }}
      }}
    }}
  }});
}})();

// ── Per-op mini charts ─────────────────────────────────────────────────────────
{op_charts_js_str}
</script>
</body>
</html>"""

    return html


if __name__ == "__main__":
    data = load_results()
    if not data:
        print("No result files found in results/. Run run_all.sh first.")
        sys.exit(1)
    print(f"Loaded results for: {', '.join(data.keys())}")
    html = generate_html(data)
    out_path = ROOT / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Report written to {out_path}")
