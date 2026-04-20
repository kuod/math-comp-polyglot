#!/usr/bin/env python3
"""Read per-language JSON results and emit a self-contained HTML report."""

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"

def _svg(path):
    return (f'<svg class="lang-svg" viewBox="0 0 24 24" '
            f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
            f'fill="currentColor"><path d="{path}"/></svg>')

_JULIA_SVG = (
    '<svg class="lang-svg" viewBox="0 0 24 24" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<circle cx="5.569" cy="17.569" r="5.569" fill="#CB3C33"/>'
    '<circle cx="12" cy="6.431" r="5.569" fill="#9558B2"/>'
    '<circle cx="18.431" cy="17.569" r="5.569" fill="#389826"/>'
    '</svg>'
)

_NUMBA_SVG = (
    '<svg class="lang-svg" viewBox="0 0 24 24" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" fill="currentColor">'
    '<path d="M13 2 L3 14 H10 L8 22 L21 8 H14 Z"/>'
    '</svg>'
)

LANG_META = {
    "Python":  {"color": "#3776AB", "bg": "#EBF3FB", "chart_label": "🐍",
                "logo": _svg("M14.25.18l.9.2.73.26.59.3.45.32.34.34.25.34.16.33.1.3.04.26.02.2-.01.13V8.5l-.05.63-.13.55-.21.46-.26.38-.3.31-.33.25-.35.19-.35.14-.33.1-.3.07-.26.04-.21.02H8.77l-.69.05-.59.14-.5.22-.41.27-.33.32-.27.35-.2.36-.15.37-.1.35-.07.32-.04.27-.02.21v3.06H3.17l-.21-.03-.28-.07-.32-.12-.35-.18-.36-.26-.36-.36-.35-.46-.32-.59-.28-.73-.21-.88-.14-1.05-.05-1.23.06-1.22.16-1.04.24-.87.32-.71.36-.57.4-.44.42-.33.42-.24.4-.16.36-.1.32-.05.24-.01h.16l.06.01h8.16v-.83H6.18l-.01-2.75-.02-.37.05-.34.11-.31.17-.28.25-.26.31-.23.38-.2.44-.18.51-.15.58-.12.64-.1.71-.06.77-.04.84-.02 1.27.05zm-6.3 1.98l-.23.33-.08.41.08.41.23.34.33.22.41.09.41-.09.33-.22.23-.34.08-.41-.08-.41-.23-.33-.33-.22-.41-.09-.41.09zm13.09 3.95l.28.06.32.12.35.18.36.27.36.35.35.47.32.59.28.73.21.88.14 1.04.05 1.23-.06 1.23-.16 1.04-.24.86-.32.71-.36.57-.4.45-.42.33-.42.24-.4.16-.36.09-.32.05-.24.02-.16-.01h-8.22v.82h5.84l.01 2.76.02.36-.05.34-.11.31-.17.29-.25.25-.31.24-.38.2-.44.17-.51.15-.58.13-.64.09-.71.07-.77.04-.84.01-1.27-.04-1.07-.14-.9-.2-.73-.25-.59-.3-.45-.33-.34-.34-.25-.34-.16-.33-.1-.3-.04-.25-.02-.2.01-.13v-5.34l.05-.64.13-.54.21-.46.26-.38.3-.32.33-.24.35-.2.35-.14.33-.1.3-.06.26-.04.21-.02.13-.01h5.84l.69-.05.59-.14.5-.21.41-.28.33-.32.27-.35.2-.36.15-.36.1-.35.07-.32.04-.28.02-.21V6.07h2.09l.14.01zm-6.47 14.25l-.23.33-.08.41.08.41.23.33.33.23.41.08.41-.08.33-.23.23-.33.08-.41-.08-.41-.23-.33-.33-.23-.41-.08-.41.08z")},
    "R":       {"color": "#276DC3", "bg": "#EBF0FA", "chart_label": "R",
                "logo": _svg("M12 2.746c-6.627 0-12 3.599-12 8.037 0 3.897 4.144 7.144 9.64 7.88V16.26c-2.924-.915-4.925-2.755-4.925-4.877 0-3.035 4.084-5.494 9.12-5.494 5.038 0 8.757 1.683 8.757 5.494 0 1.976-.999 3.379-2.662 4.272.09.066.174.128.258.216.169.149.25.363.372.544 2.128-1.45 3.44-3.437 3.44-5.631 0-4.44-5.373-8.038-12-8.038zm-2.111 4.99v13.516l4.093-.002-.002-5.291h1.1c.225 0 .321.066.549.25.272.22.715.982.715.982l2.164 4.063 4.627-.002-2.864-4.826s-.086-.193-.265-.383a2.22 2.22 0 00-.582-.416c-.422-.214-1.149-.434-1.149-.434s3.578-.264 3.578-3.826c0-3.562-3.744-3.63-3.744-3.63zm4.127 2.93l2.478.002s1.149-.062 1.149 1.127c0 1.165-1.149 1.17-1.149 1.17h-2.478zm1.754 6.119c-.494.049-1.012.079-1.54.088v1.807a16.622 16.622 0 002.37-.473l-.471-.891s-.108-.183-.248-.394c-.039-.054-.08-.098-.111-.137z")},
    "Julia":   {"color": "#9558B2", "bg": "#F3EBF9", "chart_label": "∿",
                "logo": _JULIA_SVG},
    "Rust":    {"color": "#CE422B", "bg": "#FCECEA", "chart_label": "⚙",
                "logo": _svg("M23.8346 11.7033l-1.0073-.6236a13.7268 13.7268 0 00-.0283-.2936l.8656-.8069a.3483.3483 0 00-.1154-.578l-1.1066-.414a8.4958 8.4958 0 00-.087-.2856l.6904-.9587a.3462.3462 0 00-.2257-.5446l-1.1663-.1894a9.3574 9.3574 0 00-.1407-.2622l.49-1.0761a.3437.3437 0 00-.0274-.3361.3486.3486 0 00-.3006-.154l-1.1845.0416a6.7444 6.7444 0 00-.1873-.2268l.2723-1.153a.3472.3472 0 00-.417-.4172l-1.1532.2724a14.0183 14.0183 0 00-.2278-.1873l.0415-1.1845a.3442.3442 0 00-.49-.328l-1.076.491c-.0872-.0476-.1742-.0952-.2623-.1407l-.1903-1.1673A.3483.3483 0 0016.256.955l-.9597.6905a8.4867 8.4867 0 00-.2855-.086l-.414-1.1066a.3483.3483 0 00-.5781-.1154l-.8069.8666a9.2936 9.2936 0 00-.2936-.0284L12.2946.1683a.3462.3462 0 00-.5892 0l-.6236 1.0073a13.7383 13.7383 0 00-.2936.0284L9.9803.3374a.3462.3462 0 00-.578.1154l-.4141 1.1065c-.0962.0274-.1903.0567-.2855.086L7.744.955a.3483.3483 0 00-.5447.2258L7.009 2.348a9.3574 9.3574 0 00-.2622.1407l-1.0762-.491a.3462.3462 0 00-.49.328l.0416 1.1845a7.9826 7.9826 0 00-.2278.1873L3.8413 3.425a.3472.3472 0 00-.4171.4171l.2713 1.1531c-.0628.075-.1255.1509-.1863.2268l-1.1845-.0415a.3462.3462 0 00-.328.49l.491 1.0761a9.167 9.167 0 00-.1407.2622l-1.1662.1894a.3483.3483 0 00-.2258.5446l.6904.9587a13.303 13.303 0 00-.087.2855l-1.1065.414a.3483.3483 0 00-.1155.5781l.8656.807a9.2936 9.2936 0 00-.0283.2935l-1.0073.6236a.3442.3442 0 000 .5892l1.0073.6236c.008.0982.0182.1964.0283.2936l-.8656.8079a.3462.3462 0 00.1155.578l1.1065.4141c.0273.0962.0567.1914.087.2855l-.6904.9587a.3452.3452 0 00.2268.5447l1.1662.1893c.0456.088.0922.1751.1408.2622l-.491 1.0762a.3462.3462 0 00.328.49l1.1834-.0415c.0618.0769.1235.1528.1873.2277l-.2713 1.1541a.3462.3462 0 00.4171.4161l1.153-.2713c.075.0638.151.1255.2279.1863l-.0415 1.1845a.3442.3442 0 00.49.327l1.0761-.49c.087.0486.1741.0951.2622.1407l.1903 1.1662a.3483.3483 0 00.5447.2268l.9587-.6904a9.299 9.299 0 00.2855.087l.414 1.1066a.3452.3452 0 00.5781.1154l.8079-.8656c.0972.0111.1954.0203.2936.0294l.6236 1.0073a.3472.3472 0 00.5892 0l.6236-1.0073c.0982-.0091.1964-.0183.2936-.0294l.8069.8656a.3483.3483 0 00.578-.1154l.4141-1.1066a8.4626 8.4626 0 00.2855-.087l.9587.6904a.3452.3452 0 00.5447-.2268l.1903-1.1662c.088-.0456.1751-.0931.2622-.1407l1.0762.49a.3472.3472 0 00.49-.327l-.0415-1.1845a6.7267 6.7267 0 00.2267-.1863l1.1531.2713a.3472.3472 0 00.4171-.416l-.2713-1.1542c.0628-.0749.1255-.1508.1863-.2278l1.1845.0415a.3442.3442 0 00.328-.49l-.49-1.076c.0475-.0872.0951-.1742.1407-.2623l1.1662-.1893a.3483.3483 0 00.2258-.5447l-.6904-.9587.087-.2855 1.1066-.414a.3462.3462 0 00.1154-.5781l-.8656-.8079c.0101-.0972.0202-.1954.0283-.2936l1.0073-.6236a.3442.3442 0 000-.5892zm-6.7413 8.3551a.7138.7138 0 01.2986-1.396.714.714 0 11-.2997 1.396zm-.3422-2.3142a.649.649 0 00-.7715.5l-.3573 1.6685c-1.1035.501-2.3285.7795-3.6193.7795a8.7368 8.7368 0 01-3.6951-.814l-.3574-1.6684a.648.648 0 00-.7714-.499l-1.473.3158a8.7216 8.7216 0 01-.7613-.898h7.1676c.081 0 .1356-.0141.1356-.088v-2.536c0-.074-.0536-.0881-.1356-.0881h-2.0966v-1.6077h2.2677c.2065 0 1.1065.0587 1.394 1.2088.0901.3533.2875 1.5044.4232 1.8729.1346.413.6833 1.2381 1.2685 1.2381h3.5716a.7492.7492 0 00.1296-.0131 8.7874 8.7874 0 01-.8119.9526zM6.8369 20.024a.714.714 0 11-.2997-1.396.714.714 0 01.2997 1.396zM4.1177 8.9972a.7137.7137 0 11-1.304.5791.7137.7137 0 011.304-.579zm-.8352 1.9813l1.5347-.6824a.65.65 0 00.33-.8585l-.3158-.7147h1.2432v5.6025H3.5669a8.7753 8.7753 0 01-.2834-3.348zm6.7343-.5437V8.7836h2.9601c.153 0 1.0792.1772 1.0792.8697 0 .575-.7107.7815-1.2948.7815zm10.7574 1.4862c0 .2187-.008.4363-.0243.651h-.9c-.09 0-.1265.0586-.1265.1477v.413c0 .973-.5487 1.1846-1.0296 1.2382-.4576.0517-.9648-.1913-1.0275-.4717-.2704-1.5186-.7198-1.8436-1.4305-2.4034.8817-.5599 1.799-1.386 1.799-2.4915 0-1.1936-.819-1.9458-1.3769-2.3153-.7825-.5163-1.6491-.6195-1.883-.6195H5.4682a8.7651 8.7651 0 014.907-2.7699l1.0974 1.151a.648.648 0 00.9182.0213l1.227-1.1743a8.7753 8.7753 0 016.0044 4.2762l-.8403 1.8982a.652.652 0 00.33.8585l1.6178.7188c.0283.2875.0425.577.0425.8717zm-9.3006-9.5993a.7128.7128 0 11.984 1.0316.7137.7137 0 01-.984-1.0316zm8.3389 6.71a.7107.7107 0 01.9395-.3625.7137.7137 0 11-.9405.3635z")},
    "C++":     {"color": "#00599C", "bg": "#EBF4FA", "chart_label": "C++",
                "logo": _svg("M22.394 6c-.167-.29-.398-.543-.652-.69L12.926.22c-.509-.294-1.34-.294-1.848 0L2.26 5.31c-.508.293-.923 1.013-.923 1.6v10.18c0 .294.104.62.271.91.167.29.398.543.652.69l8.816 5.09c.508.293 1.34.293 1.848 0l8.816-5.09c.254-.147.485-.4.652-.69.167-.29.27-.616.27-.91V6.91c.003-.294-.1-.62-.268-.91zM12 19.11c-3.92 0-7.109-3.19-7.109-7.11 0-3.92 3.19-7.11 7.11-7.11a7.133 7.133 0 016.156 3.553l-3.076 1.78a3.567 3.567 0 00-3.08-1.78A3.56 3.56 0 008.444 12 3.56 3.56 0 0012 15.555a3.57 3.57 0 003.08-1.778l3.078 1.78A7.135 7.135 0 0112 19.11zm7.11-6.715h-.79v.79h-.79v-.79h-.79v-.79h.79v-.79h.79v.79h.79zm2.962 0h-.79v.79h-.79v-.79h-.79v-.79h.79v-.79h.79v.79h.79z")},
    "Haskell": {"color": "#5D4F85", "bg": "#F0EDF8", "chart_label": "λ",
                "logo": _svg("M0 3.535L5.647 12 0 20.465h4.235L9.883 12 4.235 3.535zm5.647 0L11.294 12l-5.647 8.465h4.235l3.53-5.29 3.53 5.29h4.234L9.883 3.535zm8.941 4.938l1.883 2.822H24V8.473zm2.824 4.232l1.882 2.822H24v-2.822z")},
    "Swift":   {"color": "#F05138", "bg": "#FEF0ED", "chart_label": "🦅",
                "logo": _svg("M7.508 0c-.287 0-.573 0-.86.002-.241.002-.483.003-.724.01-.132.003-.263.009-.395.015A9.154 9.154 0 0 0 4.348.15 5.492 5.492 0 0 0 2.85.645 5.04 5.04 0 0 0 .645 2.848c-.245.48-.4.972-.495 1.5-.093.52-.122 1.05-.136 1.576a35.2 35.2 0 0 0-.012.724C0 6.935 0 7.221 0 7.508v8.984c0 .287 0 .575.002.862.002.24.005.481.012.722.014.526.043 1.057.136 1.576.095.528.25 1.02.495 1.5a5.03 5.03 0 0 0 2.205 2.203c.48.244.97.4 1.498.495.52.093 1.05.124 1.576.138.241.007.483.009.724.01.287.002.573.002.86.002h8.984c.287 0 .573 0 .86-.002.241-.001.483-.003.724-.01a10.523 10.523 0 0 0 1.578-.138 5.322 5.322 0 0 0 1.498-.495 5.035 5.035 0 0 0 2.203-2.203c.245-.48.4-.972.495-1.5.093-.52.124-1.05.138-1.576.007-.241.009-.481.01-.722.002-.287.002-.575.002-.862V7.508c0-.287 0-.573-.002-.86a33.662 33.662 0 0 0-.01-.724 10.5 10.5 0 0 0-.138-1.576 5.328 5.328 0 0 0-.495-1.5A5.039 5.039 0 0 0 21.152.645 5.32 5.32 0 0 0 19.654.15a10.493 10.493 0 0 0-1.578-.138 34.98 34.98 0 0 0-.722-.01C17.067 0 16.779 0 16.492 0H7.508zm6.035 3.41c4.114 2.47 6.545 7.162 5.549 11.131-.024.093-.05.181-.076.272l.002.001c2.062 2.538 1.5 5.258 1.236 4.745-1.072-2.086-3.066-1.568-4.088-1.043a6.803 6.803 0 0 1-.281.158l-.02.012-.002.002c-2.115 1.123-4.957 1.205-7.812-.022a12.568 12.568 0 0 1-5.64-4.838c.649.48 1.35.902 2.097 1.252 3.019 1.414 6.051 1.311 8.197-.002C9.651 12.73 7.101 9.67 5.146 7.191a10.628 10.628 0 0 1-1.005-1.384c2.34 2.142 6.038 4.83 7.365 5.576C8.69 8.408 6.208 4.743 6.324 4.86c4.436 4.47 8.528 6.996 8.528 6.996.154.085.27.154.36.213.085-.215.16-.437.224-.668.708-2.588-.09-5.548-1.893-7.992z")},
    "Go":      {"color": "#00ACD7", "bg": "#E6F7FC", "chart_label": "🐹",
                "logo": _svg("M1.811 10.231c-.047 0-.058-.023-.035-.059l.246-.315c.023-.035.081-.058.128-.058h4.172c.046 0 .058.035.035.07l-.199.303c-.023.036-.082.07-.117.07zM.047 11.306c-.047 0-.059-.023-.035-.058l.245-.316c.023-.035.082-.058.129-.058h5.328c.047 0 .07.035.058.07l-.093.28c-.012.047-.058.07-.105.07zm2.828 1.075c-.047 0-.059-.035-.035-.07l.163-.292c.023-.035.07-.07.117-.07h2.337c.047 0 .07.035.07.082l-.023.28c0 .047-.047.082-.082.082zm12.129-2.36c-.736.187-1.239.327-1.963.514-.176.046-.187.058-.34-.117-.174-.199-.303-.327-.548-.444-.737-.362-1.45-.257-2.115.175-.795.514-1.204 1.274-1.192 2.22.011.935.654 1.706 1.577 1.835.795.105 1.46-.175 1.987-.77.105-.13.198-.27.315-.434H10.47c-.245 0-.304-.152-.222-.35.152-.362.432-.97.596-1.274a.315.315 0 01.292-.187h4.253c-.023.316-.023.631-.07.947a4.983 4.983 0 01-.958 2.29c-.841 1.11-1.94 1.8-3.33 1.986-1.145.152-2.209-.07-3.143-.77-.865-.655-1.356-1.52-1.484-2.595-.152-1.274.222-2.419.993-3.424.83-1.086 1.928-1.776 3.272-2.02 1.098-.2 2.15-.07 3.096.571.62.41 1.063.97 1.356 1.648.07.105.023.164-.117.2m3.868 6.461c-1.064-.024-2.034-.328-2.852-1.029a3.665 3.665 0 01-1.262-2.255c-.21-1.32.152-2.489.947-3.529.853-1.122 1.881-1.706 3.272-1.95 1.192-.21 2.314-.095 3.33.595.923.63 1.496 1.484 1.648 2.605.198 1.578-.257 2.863-1.344 3.962-.771.783-1.718 1.273-2.805 1.495-.315.06-.63.07-.934.106zm2.78-4.72c-.011-.153-.011-.27-.034-.387-.21-1.157-1.274-1.81-2.384-1.554-1.087.245-1.788.935-2.045 2.033-.21.912.234 1.835 1.075 2.21.643.28 1.285.244 1.905-.07.923-.48 1.425-1.228 1.484-2.233z")},
    "Numba":   {"color": "#27AE60", "bg": "#E9F7EF", "chart_label": "⚡",
                "logo": _NUMBA_SVG},
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
    "Numba":   "tracemalloc peak (Python-managed heap; output arrays via NumPy)",
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
    "Numba":   "numba_results.json",
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
        meta = LANG_META.get(lang, {"color": "#888", "bg": "#eee", "chart_label": "?", "logo": '<svg class="lang-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor" opacity=".4"/></svg>'})
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
            meta = LANG_META.get(lang, {"color": "#888", "chart_label": "?", "logo": '<svg class="lang-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor" opacity=".4"/></svg>'})
            t = round(op_table[lang][op]["mean_ms"], 4)
            m = round(op_table[lang][op]["memory_mb"], 4)
            scatter_datasets.append({
                "label": f'{meta.get("chart_label", lang)} {lang}',
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
        meta = LANG_META.get(lang, {"color": "#888", "bg": "#eee", "chart_label": "?", "logo": '<svg class="lang-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor" opacity=".4"/></svg>'})
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
            meta = LANG_META.get(lang, {"color": "#888", "chart_label": "?", "logo": '<svg class="lang-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor" opacity=".4"/></svg>'})
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
  .lang-logo  {{ margin-bottom: .2rem; line-height: 1; }}
  .lang-svg   {{ display: inline-block; vertical-align: middle; fill: currentColor; }}
  .lang-logo .lang-svg          {{ width: 2rem; height: 2rem; }}
  .badge .lang-svg,
  .lb-lang .lang-svg,
  .gloss-badge .lang-svg        {{ width: 0.85em; height: 0.85em; vertical-align: -0.1em; }}
  th .lang-svg                  {{ width: 1em; height: 1em; vertical-align: -0.15em; }}
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
  <strong>Hardware:</strong> Apple M1 &nbsp;|&nbsp; 16 GB RAM &nbsp;|&nbsp; macOS 26.3.1<br>
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
