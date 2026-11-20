# 主终端布局预览

这里只有设计预览，不接入生产生成器，也不改 `futu_pro_terminal.html` / `index.html`。

三套页面共用仓库里已经提交的终端快照、AI 预测快照，以及 `data_cache/ml_panel_5y.parquet` 和 `data_cache/ml_extended_panel.parquet` 里的日 K。页面不连接行情，不加载 TradingView，不能下单。K 线在本地画布上绘制；面板里没有的代码会明确写「没有日 K」，不会编一根假 K 线。

| 文件 | 布局 |
|---|---|
| `index.html` | 对比入口 |
| `a-chart-first.html` | A 大图看盘 |
| `b-balanced.html` | B 均衡三栏 |
| `c-reading.html` | C 分区阅读 |

直接用浏览器打开即可。改 `shared.css` / `shared.js` / `templates/` 之后，在仓库根目录运行：

```bash
python3 demos/previews/build_previews.py
```

生成脚本只读生产快照，只写本目录下的三份 HTML。
