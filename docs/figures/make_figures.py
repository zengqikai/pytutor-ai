"""生成 docs/figures/results-overview{,-dark}.svg。

数据来源：
  evaluation/rag_eval_results_{tfidf,vector,hybrid}.json
  evaluation/v2_eval_results.json

只依赖标准库。数值改了以后重跑本脚本，再更新 docs/figures/README.md 的表格。
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent

# 来自 references/palette.md 的三槽分类色，已用 validate_palette.js 校验。
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "tile": "#ffffff",
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#6b6a64",
        "grid": "#e6e5e0",
        "axis": "#c9c8c2",
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
        "suffix": "",
    },
    "dark": {
        "surface": "#1a1a19",
        "tile": "#232322",
        "ink": "#f2f1ec",
        "ink2": "#b9b7ae",
        "muted": "#9a988f",
        "grid": "#33332f",
        "axis": "#4a4a44",
        "series": ["#3987e5", "#d95926", "#199e70"],
        "suffix": "-dark",
    },
}

# 30 条可答查询；Hybrid 与 Vector 相同是因为 ENABLE_HYBRID_WEIGHTS=false。
RETRIEVAL = {
    "TF-IDF": (0.900, 0.407, 0.900),
    "Vector": (0.933, 0.501, 0.890),
    "Hybrid": (0.933, 0.501, 0.890),
}
METRICS = ["Hit@5", "Recall@5", "MRR"]

# 同集验证，不是留出集。
AST_TILES = [
    ("47/47", "misconception cases matched"),
    ("1.000", "macro F1 (M1-M8)"),
    ("0/22", "false positives on clean code"),
    ("0.2 ms", "mean diagnosis latency"),
]

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"


def bar_path(x, y, w, baseline):
    """4px 圆角数据端，底部贴基线（不圆角）。"""
    r = 4
    return (
        f"M{x},{baseline} L{x},{y + r} Q{x},{y} {x + r},{y} "
        f"L{x + w - r},{y} Q{x + w},{y} {x + w},{y + r} L{x + w},{baseline} Z"
    )


def build(theme):
    t = THEMES[theme]
    W, H = 1200, 600
    plot_x, plot_y = 80, 112
    plot_w, plot_h = 620, 352
    baseline = plot_y + plot_h

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="figTitle figDesc">'
    )
    p.append(
        '<title id="figTitle">PyTutor retrieval baselines and local AST diagnosis</title>'
    )
    p.append(
        '<desc id="figDesc">Left: Hit@5, Recall@5 and MRR for TF-IDF, vector and hybrid '
        'retrieval on thirty answerable queries. Vector and hybrid both reach Hit@5 0.933, '
        'Recall@5 0.501 and MRR 0.890; TF-IDF reaches 0.900, 0.407 and 0.900. Right: '
        'AST diagnosis matches 47 of 47 misconception cases with no false positives on 22 '
        'clean cases. AST figures are same-set results, not a held-out estimate.</desc>'
    )
    p.append(f'<rect width="{W}" height="{H}" fill="{t["surface"]}"/>')

    p.append(
        f'<text x="40" y="46" font-family="{FONT}" font-size="22" font-weight="600" '
        f'fill="{t["ink"]}">Retrieval baselines and local AST diagnosis</text>'
    )
    p.append(
        f'<text x="40" y="70" font-family="{FONT}" font-size="13" fill="{t["ink2"]}">'
        '30 answerable queries · 41 chunks · same configuration as the demo</text>'
    )

    # ---- 左：分组柱 ----
    p.append(
        f'<text x="{plot_x}" y="96" font-family="{FONT}" font-size="14" font-weight="600" '
        f'fill="{t["ink"]}">Retrieval quality by method (0–1)</text>'
    )

    for i in range(5):
        val = i / 4
        y = baseline - val * plot_h
        p.append(
            f'<line x1="{plot_x}" y1="{y:.1f}" x2="{plot_x + plot_w}" y2="{y:.1f}" '
            f'stroke="{t["grid"]}" stroke-width="1"/>'
        )
        p.append(
            f'<text x="{plot_x - 10}" y="{y + 4:.1f}" text-anchor="end" font-family="{FONT}" '
            f'font-size="11" fill="{t["muted"]}">{val:.2f}</text>'
        )

    group_centers = [200, 390, 580]
    bar_w, gap = 44, 4
    for (name, vals), cx in zip(RETRIEVAL.items(), group_centers):
        total_w = 3 * bar_w + 2 * gap
        x = cx - total_w / 2
        for (mname, color), v in zip(zip(METRICS, t["series"]), vals):
            h = v * plot_h
            y = baseline - h
            p.append(
                f'<path d="{bar_path(x, y, bar_w, baseline)}" fill="{color}">'
                f'<title>{name} · {mname}: {v:.3f}</title></path>'
            )
            # 只标每组 MRR：既给出可读数值，又不至于每根柱子都挂数字。
            if mname == "MRR":
                p.append(
                    f'<text x="{x + bar_w / 2:.1f}" y="{y - 7:.1f}" text-anchor="middle" '
                    f'font-family="{FONT}" font-size="11" fill="{t["ink2"]}">{v:.3f}</text>'
                )
            x += bar_w + gap
        p.append(
            f'<text x="{cx}" y="{baseline + 22}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="12.5" fill="{t["ink"]}">{name}</text>'
        )

    p.append(
        f'<line x1="{plot_x}" y1="{baseline}" x2="{plot_x + plot_w}" y2="{baseline}" '
        f'stroke="{t["axis"]}" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{plot_x}" y="{baseline + 50}" font-family="{FONT}" font-size="10.5" '
        f'fill="{t["muted"]}">Hybrid equals vector while ENABLE_HYBRID_WEIGHTS is off; '
        'this is not evidence for fusion.</text>'
    )

    # 图例（>=2 series 必须有），右对齐到绘图区右缘
    legend_right = plot_x + plot_w
    offsets = [250, 135, 0]  # MRR 最靠近右缘
    for (mname, color), off in zip(zip(METRICS, t["series"]), offsets):
        x = legend_right - off
        p.append(f'<rect x="{x - 74}" y="87" width="10" height="10" rx="2" fill="{color}"/>')
        p.append(
            f'<text x="{x - 58}" y="96" font-family="{FONT}" font-size="11.5" '
            f'fill="{t["ink2"]}">{mname}</text>'
        )

    # ---- 右：AST 统计卡片 ----
    rx = 760
    p.append(
        f'<line x1="{rx - 40}" y1="96" x2="{rx - 40}" y2="520" stroke="{t["grid"]}" stroke-width="1"/>'
    )
    p.append(
        f'<text x="{rx}" y="96" font-family="{FONT}" font-size="14" font-weight="600" '
        f'fill="{t["ink"]}">Local AST diagnosis</text>'
    )

    for i, (value, caption) in enumerate(AST_TILES):
        col, row = i % 2, i // 2
        tx, ty = rx + col * 205, 124 + row * 116
        p.append(
            f'<rect x="{tx}" y="{ty}" width="185" height="98" rx="8" fill="{t["tile"]}" '
            f'stroke="{t["grid"]}"/>'
        )
        p.append(
            f'<text x="{tx + 16}" y="{ty + 46}" font-family="{FONT}" font-size="28" '
            f'font-weight="600" fill="{t["ink"]}">{value}</text>'
        )
        words = caption.split()
        line1, line2 = " ".join(words[:3]), " ".join(words[3:])
        p.append(
            f'<text x="{tx + 16}" y="{ty + 70}" font-family="{FONT}" font-size="11.5" '
            f'fill="{t["ink2"]}">{line1}</text>'
        )
        if line2:
            p.append(
                f'<text x="{tx + 16}" y="{ty + 85}" font-family="{FONT}" font-size="11.5" '
                f'fill="{t["ink2"]}">{line2}</text>'
            )

    p.append(
        f'<text x="{rx}" y="400" font-family="{FONT}" font-size="11" fill="{t["muted"]}">'
        'Same-set validation: rules and cases were</text>'
    )
    p.append(
        f'<text x="{rx}" y="417" font-family="{FONT}" font-size="11" fill="{t["muted"]}">'
        'developed together. Not a held-out estimate.</text>'
    )

    p.append(
        f'<text x="40" y="572" font-family="{FONT}" font-size="10.5" fill="{t["muted"]}">'
        'Source: evaluation/run_rag_eval.py (tfidf, vector, hybrid) · '
        'evaluation/run_v2_eval.py --mode ast-only · 2026-10-22</text>'
    )
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    for theme in THEMES:
        suffix = THEMES[theme]["suffix"]
        out = HERE / f"results-overview{suffix}.svg"
        out.write_text(build(theme), encoding="utf-8")
        print(f"wrote {out.relative_to(HERE.parent.parent)}")
