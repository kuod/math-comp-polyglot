import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generate_report as gr  # noqa: E402


def _op(name, ms, mem=1.0):
    return {"name": name, "description": "", "mean_ms": ms, "std_ms": 0.0,
            "min_ms": ms, "memory_mb": mem}


def _table(spec):
    return {l: {n: _op(n, v) for n, v in ops.items()} for l, ops in spec.items()}


def test_missing_op_is_penalised_not_rewarded():
    # B is faster on 'a' and slower on 'b' than A would be... but skips 'c'.
    table = _table({"A": {"a": 1, "b": 1, "c": 1}, "B": {"a": 2, "b": 2}})
    scores = gr.compute_golf_scores(["A", "B"], ["a", "b", "c"], table, "mean_ms")
    assert scores == {"A": 3, "B": 2 + 2 + 2}  # B charged worst+1 = 2 for 'c'
    # Skipping an op must never beat an otherwise-identical full entry
    table["B"]["c"] = _op("c", 2)
    full = gr.compute_golf_scores(["A", "B"], ["a", "b", "c"], table, "mean_ms")
    assert scores["B"] >= full["B"]


def test_scores_basic_ranking():
    table = _table({"A": {"x": 5}, "B": {"x": 1}, "C": {"x": 3}})
    s = gr.compute_golf_scores(["A", "B", "C"], ["x"], table, "mean_ms")
    assert s == {"B": 1, "C": 2, "A": 3}


def _write(d, name, doc):
    (d / name).write_text(doc if isinstance(doc, str) else json.dumps(doc))


def test_load_results_skips_malformed_and_invalid(tmp_path, capsys):
    good = {"language": "Go", "operations": [_op("x", 1.0)]}
    _write(tmp_path, "go_results.json", "{bad")
    _write(tmp_path, "rust_results.json", {"operations": [{"name": "x"}]})
    _write(tmp_path, "cpp_results.json", {"operations": [_op("x", float("nan"))]})
    _write(tmp_path, "swift_results.json", {"operations": []})
    _write(tmp_path, "julia_results.json", good)
    data = gr.load_results(tmp_path)
    assert list(data) == ["Julia"]
    err = capsys.readouterr().err
    for f in ("go_results", "rust_results", "cpp_results", "swift_results"):
        assert f in err


def test_committed_results_are_valid_and_report_builds():
    data = gr.load_results()
    assert len(data) == len(gr.FILE_MAP)
    html = gr.generate_html(data)
    assert "<html" in html
