# 结果图

对应完善任务清单 **16（结果包）**。所有数字来自仓库内结果文件，不手工抄写：

| 文件 | 用途 |
|------|------|
| `results-overview.svg` | 浅色版，用于 README / 论文 / PPT 白底 |
| `results-overview-dark.svg` | 深色版，用于深色主题页面 |
| `make_figures.py` | 生成上面两个文件（只依赖标准库） |

重新生成：

```bash
python docs/figures/make_figures.py
```

## 图表说明

左图：三种检索器在 30 条可答查询上的 Hit@5 / Recall@5 / MRR，共用 0–1 纵轴。
右图：AST 误区诊断的同集结果，用统计卡片而不是图表（四个独立标量，画成柱状图没有信息增益）。

图里有三处刻意的取舍：

1. **Hybrid 与 Vector 完全相同**。`ENABLE_HYBRID_WEIGHTS=false` 时混合检索就是"向量优先拼接"，
   Top-5 被向量结果占满。图上把这件事直接写出来，避免被读成"融合有效"。
2. **AST 标注为 same-set**。规则是照着这 47 + 22 条调的，不是留出集准确率。
3. **只给 MRR 柱直接标数值**。其余数值由图例、纵轴和下面的表格提供——
   每根柱子都挂数字会盖住图形本身。

## 表格视图（无障碍等价物）

配色校验中 `#1baf7a`（MRR）对浅色底的对比度是 2.74:1，低于 3:1，
按 dataviz 规则必须提供可见标签或表格视图。图中给三根 MRR 柱直接标了数值，
下面再给出完整表格，两种 relief 都有：

| 检索器 | Hit@5 | Recall@5 | MRR | 平均延迟 | 备注 |
|--------|-------|----------|-----|----------|------|
| TF-IDF | 0.900 | 0.407 | 0.900 | 0.1 ms | 纯内存关键词检索 |
| Vector | 0.933 | 0.501 | 0.890 | 635.6 ms | 含 DashScope embedding 调用 |
| Hybrid | 0.933 | 0.501 | 0.890 | 641.1 ms | flag 关闭时等于 Vector |

| AST 诊断 | 值 | 口径 |
|----------|----|------|
| 误区正例 | 47/47 exact match | 同集 |
| macro-F1 | 1.000 | M1–M8 八类 |
| 干净代码误报 | 0/22 | 同集 |
| 平均耗时 | 0.20 ms（最大 0.53 ms） | 47 条，单次诊断 |

留出集（另写 30 条正例 + 15 条干净代码，未据此调规则）：

| AST 诊断 · 留出集 | 值 | 口径 |
|-------------------|----|------|
| exact match | 25/30 = 0.833 | 单作者新写 |
| macro-F1 | 0.883 | M1–M8 |
| 干净代码误报 | 0/15 | 留出干净代码 |
| M5 recall | 0.250（1/4） | 主要缺口：`range` 右边界 |
| M6 recall | 0.500（2/4） | 主要缺口：`print` / `return` |

完整机器可读版本见 [`evaluation/results_summary.csv`](../../evaluation/results_summary.csv)
（40 行，覆盖 AST 同集/留出集 / RAG / Multi-Judge / 忠实度）。

## 配色与校验

三槽分类色来自 dataviz skill 的默认调色板，固定顺序、不循环：

| 模式 | Hit@5 | Recall@5 | MRR | 画布 |
|------|-------|----------|-----|------|
| light | `#2a78d6` | `#eb6834` | `#1baf7a` | `#fcfcfb` |
| dark | `#3987e5` | `#d95926` | `#199e70` | `#1a1a19` |

校验命令与结果（亮度带、色度、CVD 分离、常视觉分离均 PASS；深色版对比度全部 ≥3:1。
浅色版 MRR `#1baf7a` 对底色的对比度是 2.74:1，触发 WARN——这正是上面表格视图的来源）：

```bash
node <dataviz>/scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light
node <dataviz>/scripts/validate_palette.js "#3987e5,#d95926,#199e70" --mode dark
```

## 导出 PNG（放进 PPT 时）

直接用浏览器打开 SVG 再截图会带 8px 页面边距并缩放。正确做法是套一层零边距 HTML：

```html
<!doctype html><meta charset="utf-8">
<style>html,body{margin:0}svg{display:block;width:1200px;height:600px}</style>
<!-- 这里粘贴 SVG 内容 -->
```

然后用 Chrome headless 截图：

```bash
chrome --headless=new --window-size=1200,600 \
  --screenshot=results-overview.png results-overview.html
```

## 数据出处

- RAG：`evaluation/rag_eval_results_{tfidf,vector,hybrid}.json`（2026-10-22 跑）
- AST（同集）：`evaluation/v2_eval_results.json`
- AST（留出集）：`evaluation/v2_holdout_results.json`
- 口径与限制：[`docs/REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) §6、[`docs/DATA_CARD.md`](../DATA_CARD.md)
