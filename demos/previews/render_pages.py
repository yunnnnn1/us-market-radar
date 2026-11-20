"""Render the four reading pages and the index. Terminal is assembled separately."""

from __future__ import annotations

import html
import re
from pathlib import Path

MARKS = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")


def strip_marks(value) -> str:
    return re.sub(r"\s+", " ", MARKS.sub("", "" if value is None else str(value))).strip()

ROOT = Path(__file__).resolve().parents[2]

NAV = [
    ("terminal.html", "看盘：价格、走势、期权"),
    ("macro.html", "宏观：大盘和板块"),
    ("stocks.html", "个股：候选比较"),
    ("predict.html", "模型：分数与适用范围"),
    ("backtest.html", "回测：历史表现与风险"),
]

CSS = """
:root { color-scheme: dark; --bg:#0e1116; --card:#161b22; --line:#2c3442; --text:#e8eaed; --muted:#c5ced8; --accent:#9bb8e8; --up:#8fceaa; --down:#e09a9a; }
* { box-sizing: border-box; }
body { margin:0; font-family:"WenQuanYi Micro Hei","PingFang SC","Microsoft YaHei",sans-serif; font-size:16px; line-height:1.55; color:var(--text); background:var(--bg); }
a { color: var(--accent); }
.banner { background:#1a1814; color:#e6d7b8; padding:10px 20px; font-size:15px; }
.sitenav { display:flex; flex-wrap:wrap; gap:8px; padding:10px 16px; background:#10141b; border-bottom:1px solid var(--line); }
.sitenav a { color:var(--muted); text-decoration:none; border:1px solid var(--line); border-radius:999px; padding:6px 12px; }
.sitenav a[aria-current="page"] { color:var(--text); background:#243044; border-color:#6e8ebc; }
main { width:min(1100px, calc(100% - 32px)); margin:0 auto; padding:22px 0 48px; }
h1 { font-size:28px; line-height:1.3; margin:0 0 8px; }
.purpose { font-size:16px; color:var(--text); margin:0 0 14px; }
.steps { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 18px; padding:0; list-style:none; }
.steps li { background:#161b22; border:1px solid var(--line); border-radius:10px; padding:8px 12px; font-size:15px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px,1fr)); gap:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.card h2 { font-size:18px; margin:0 0 8px; }
.k { color:var(--muted); font-size:15px; }
.num { font-variant-numeric: tabular-nums; }
.up { color:var(--up); } .down { color:var(--down); }
.wrap { overflow-x:auto; border:1px solid var(--line); border-radius:12px; }
table { width:100%; border-collapse:collapse; font-size:15px; min-width:720px; }
th, td { padding:10px 12px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }
th { position:sticky; top:0; background:#1c2430; font-weight:650; }
tr:hover td { background:rgba(255,255,255,0.03); }
.tools { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 12px; }
input, button, select { font:inherit; color:inherit; background:#12161c; border:1px solid var(--line); border-radius:8px; padding:8px 10px; min-height:40px; }
button.on { background:#243044; border-color:#6e8ebc; }
.note { color:var(--muted); font-size:15px; }
details { margin-top:14px; }
summary { cursor:pointer; font-size:16px; }
.page-links { display:grid; gap:12px; }
.page-links a { display:block; text-decoration:none; color:inherit; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.page-links strong { display:block; font-size:18px; margin-bottom:4px; }
.hidden-col { display:none; }
@media (max-width: 800px) { h1 { font-size:24px; } main { width:calc(100% - 20px); } }
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def money(value) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    digits = 2 if abs(number) >= 1 else 4
    return f"{number:,.{digits}f}"


def pct(value) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def cls(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(number) < 0.005:
        return ""
    return "up" if number > 0 else "down"


def shell(title: str, current: str, body: str) -> str:
    links = []
    for href, label in NAV:
        mark = ' aria-current="page"' if href == current else ""
        links.append(f'<a href="{href}"{mark}>{esc(label)}</a>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="banner">设计预览 · 未接入生产 · 不能下单 · 数字来自仓库快照，本页不连接行情</div>
<nav class="sitenav" aria-label="预览页面">{''.join(links)}</nav>
<main>
{body}
</main>
</body>
</html>
"""


def page_index(snapshot: dict) -> str:
    sync = snapshot["meta"]["sync_time"]
    cards = [
        ("terminal.html", "看盘", "这只股票的正股价格、日 K 和期权链各是什么？"),
        ("macro.html", "宏观", "大盘和板块环境偏防守，还是还能往下看个股？"),
        ("stocks.html", "个股", "哪些股票离生产页说的回撤带更近，价格和信号怎么比？"),
        ("predict.html", "模型", "这个分数预测的是哪一段价格路径，不能当成什么？"),
        ("backtest.html", "回测", "历史模拟的收益和回撤有多大，和买期权有什么关系？"),
    ]
    links = "".join(
        f'<a href="{href}"><strong>{esc(name)}</strong>{esc(question)}</a>'
        for href, name, question in cards
    )
    body = f"""
<h1>五页分别回答一个问题</h1>
<p class="purpose">看盘页暂用三栏底稿，这个布局还没有选定。其余四页只负责把同一份快照读清楚。数据截至 {esc(sync)}。</p>
<div class="page-links">{links}</div>
"""
    return shell("五页预览", "index.html", body)


def page_macro(snapshot: dict) -> str:
    market = snapshot["market"]
    meta = snapshot["meta"]
    indices = "".join(
        f"""<tr>
          <td>{esc(row['ticker'])}</td><td>{esc(row.get('name') or '')}</td>
          <td class="num">{money(row.get('last'))}</td>
          <td class="num {cls(row.get('pct_change'))}">{pct(row.get('pct_change'))}</td>
          <td class="num {cls(row.get('bias'))}">{pct(row.get('bias'))}</td>
          <td>{esc(strip_marks(row.get('signal')) or '快照没有信号原文')}</td>
        </tr>"""
        for row in market["indices"]
    )
    parts = list(market["trad_components"].items()) + list(market["tech_components"].items())
    chips = " ".join(f'<span class="num {cls(value)}">{esc(key)} {pct(value)}</span>' for key, value in parts)
    sectors = "".join(
        f"""<tr>
          <td>{esc(row['name'])}</td>
          <td class="num">{'快照写着 0 笔' if row.get('high_conviction_signals') in (0, None) else esc(row.get('high_conviction_signals'))}</td>
          <td class="num">{esc(row.get('samples') if row.get('samples') is not None else '—')}</td>
          <td class="num">{'—' if row.get('win') is None else f"{float(row['win']):.1f}%"}</td>
          <td class="num">{'—' if row.get('pf') is None else f"{float(row['pf']):.2f}"}</td>
          <td>{esc(row.get('rating') or '')}</td>
        </tr>"""
        for row in snapshot["sectors"]
    )
    body = f"""
<h1>大盘和板块环境</h1>
<p class="purpose">这页回答：现在是先看防守，还是还能往下看个股。指数涨跌是今天的快照；板块表是历史样本，不是今天的板块涨跌。</p>
<ol class="steps">
  <li>1. 先分清两段原文。天气和宽度不是同一句话。</li>
  <li>2. 再看指数的日盘涨跌，以及相对 50 日均线的偏离。</li>
  <li>3. 最后看板块历史样本。笔数是 0 就写 0，不改成别的意思。</li>
</ol>
<div class="grid">
  <section class="card"><h2>天气原文</h2><p>{esc(market['weather_status'])} · 数据日 {esc(market.get('weather_date') or '—')}</p><p>{esc(market.get('weather_desc') or '')}</p></section>
  <section class="card"><h2>宽度原文</h2><p>{esc(market.get('breadth_tag') or '')}</p><p>{esc(market.get('breadth_text') or '')}</p></section>
  <section class="card"><h2>防御因子原文</h2><p>{esc(market.get('defensive_text') or '快照没有这段文字')}</p><p class="note">分数 {esc(market.get('defensive_score') if market.get('defensive_score') is not None else '—')}。这是快照里的背离分，不是实时警报。</p></section>
</div>
<h2>指数 · 日盘收盘是每股价格</h2>
<p class="note">截至 {esc(meta['sync_time'])}。偏离是相对 50 日均线，单位是百分数。</p>
<div class="wrap"><table>
  <thead><tr><th>代码</th><th>名称</th><th>日盘收盘（美元/股）</th><th>日盘涨跌</th><th>相对 50 日均线</th><th>快照信号原文</th></tr></thead>
  <tbody>{indices}</tbody>
</table></div>
<p class="note" style="margin-top:12px">成分涨跌（百分点，快照原样）：{chips}</p>
<h2>板块历史样本</h2>
<p class="note">命中比例是快照字段。高信念笔数为 0 时，百分比仍照原样列出，本页不解释它为什么还在。</p>
<div class="wrap"><table>
  <thead><tr><th>板块</th><th>高信念笔数</th><th>评估行数</th><th>命中比例</th><th>盈亏比</th><th>快照评级</th></tr></thead>
  <tbody>{sectors}</tbody>
</table></div>
"""
    return shell("宏观：大盘和板块", "macro.html", body)


def page_stocks(snapshot: dict) -> str:
    rows = []
    for item in snapshot["items"]:
        if item["kind"] != "stock":
            continue
        ai = item.get("ai") or {}
        op = item.get("options") or {}
        score = ai.get("calibrated_win_rate_pct")
        score_txt = "无模型记录" if score is None else f"{float(score):.1f}"
        opt_txt = "无期权缓存" if not op else (op.get("options_exp") or "有缓存但没有到期日")
        rows.append(
            f"""<tr data-name="{esc((item['ticker']+' '+item.get('name','' )).lower())}" data-pit="{'' if item.get('dist_to_pit') is None else item.get('dist_to_pit')}" data-pct="{'' if item.get('pct_change') is None else item.get('pct_change')}" data-score="{'' if score is None else score}">
            <td><a href="terminal.html?ticker={esc(item['ticker'])}">{esc(item['ticker'])}</a></td>
            <td>{esc(item.get('name') or '')}</td>
            <td class="num">{money(item.get('last'))}</td>
            <td class="num {cls(item.get('pct_change'))}">{pct(item.get('pct_change'))}</td>
            <td class="num">{'快照没有' if item.get('dist_to_pit') is None else pct(item.get('dist_to_pit'))}</td>
            <td>{esc(strip_marks(item.get('signal')) or '快照没有信号原文')}</td>
            <td class="more">{money(item.get('active_price')) if item.get('active_price') is not None else '快照没有'}</td>
            <td class="more num {cls(item.get('bias'))}">{pct(item.get('bias'))}</td>
            <td class="more num">{'—' if item.get('rsi') is None else f"{float(item['rsi']):.1f}"}</td>
            <td class="more num">{score_txt}</td>
            <td class="more">{esc(opt_txt)}</td>
            </tr>"""
        )
    body = f"""
<h1>候选标的比较</h1>
<p class="purpose">这页回答：先按正股价格和相对回撤带比较，再决定要不要打开看盘页。回撤带是生产页用 60 日高低点的 0.5 到 0.618 算出来的价格位置，不是已验证的成交密集区。</p>
<ol class="steps">
  <li>1. 先看代码、日盘收盘和涨跌。单位是美元/股。</li>
  <li>2. 再看相对回撤带。正数表示在带上方。</li>
  <li>3. 需要模型分或期权到期日时，再打开附加列。没有记录就写「无」，不写 0。</li>
</ol>
<div class="tools">
  <input id="q" type="search" placeholder="搜索代码或名称" aria-label="搜索">
  <button type="button" id="byPit" class="on">按回撤带排序</button>
  <button type="button" id="byPct">按日盘涨跌</button>
  <button type="button" id="byScore">按规则分</button>
  <button type="button" id="moreBtn">显示附加列</button>
</div>
<p class="note">截至 {esc(snapshot['meta']['sync_time'])}。点代码进入看盘页。附加列默认隐藏。</p>
<div class="wrap"><table id="board">
  <thead><tr>
    <th>代码</th><th>名称</th><th>日盘收盘（美元/股）</th><th>日盘涨跌</th><th>相对回撤带</th><th>快照信号原文</th>
    <th class="more">夜盘参考（美元/股）</th><th class="more">相对 50 日均线</th><th class="more">RSI(14)</th><th class="more">规则调整后的做多分</th><th class="more">期权到期</th>
  </tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table></div>
<script>
const q = document.getElementById('q');
const body = document.querySelector('#board tbody');
function rows() {{ return [...body.querySelectorAll('tr')]; }}
function apply() {{
  const text = q.value.trim().toLowerCase();
  rows().forEach(row => {{ row.hidden = text && !row.dataset.name.includes(text); }});
}}
function sortBy(key) {{
  const list = rows();
  list.sort((a, b) => {{
    const av = a.dataset[key], bv = b.dataset[key];
    if (av === '' && bv === '') return 0;
    if (av === '') return 1;
    if (bv === '') return -1;
    return Number(av) - Number(bv);
  }});
  if (key !== 'pit') list.reverse();
  list.forEach(row => body.appendChild(row));
}}
q.addEventListener('input', apply);
document.getElementById('byPit').onclick = () => sortBy('pit');
document.getElementById('byPct').onclick = () => sortBy('pct');
document.getElementById('byScore').onclick = () => sortBy('score');
document.getElementById('moreBtn').onclick = (event) => {{
  const on = document.body.classList.toggle('show-more');
  event.currentTarget.classList.toggle('on', on);
  document.querySelectorAll('.more').forEach(el => el.classList.toggle('hidden-col', !on));
}};
document.querySelectorAll('.more').forEach(el => el.classList.add('hidden-col'));
sortBy('pit');
</script>
<style>body.show-more .more.hidden-col {{ display: table-cell; }}</style>
"""
    return shell("个股：候选比较", "stocks.html", body)


def page_predict(snapshot: dict) -> str:
    rows = []
    ranked = []
    for item in snapshot["items"]:
        ai = item.get("ai")
        if not ai or ai.get("calibrated_win_rate_pct") is None:
            continue
        ranked.append(item)
    ranked.sort(key=lambda item: float(item["ai"]["calibrated_win_rate_pct"]), reverse=True)
    for item in ranked[:12]:
        ai = item["ai"]
        rows.append(
            f"""<tr>
            <td><a href="terminal.html?ticker={esc(item['ticker'])}">{esc(item['ticker'])}</a> {esc(item.get('name') or '')}</td>
            <td class="num">{float(ai['calibrated_win_rate_pct']):.1f}</td>
            <td class="num">{'—' if ai.get('model_raw_prob_pct') is None else f"{float(ai['model_raw_prob_pct']):.1f}"}</td>
            <td class="num">{'—' if ai.get('predicted_win_rate_pct') is None else f"{float(ai['predicted_win_rate_pct']):.1f}"}</td>
            <td class="num">{'—' if ai.get('calibrated_short_win_rate_pct') is None else f"{float(ai['calibrated_short_win_rate_pct']):.1f}"}</td>
            <td>{esc(ai.get('action') or '快照没有原文')}</td>
            </tr>"""
        )
    thresholds = "".join(
        f"""<tr>
          <td>{esc(strip_marks(row['label']))}</td>
          <td class="num">{esc(row['triggers'])}</td>
          <td class="num">{'—' if row.get('hit_pct') is None else f"{float(row['hit_pct']):.1f}%"}</td>
          <td class="num {cls(row.get('avg_return'))}">{'—' if row.get('avg_return') is None else f"{float(row['avg_return']):.2f}%"}</td>
          <td class="num">{'—' if row.get('pf') is None else f"{float(row['pf']):.2f}"}</td>
        </tr>"""
        for row in snapshot["meta"].get("table1") or []
    )
    body = f"""
<h1>模型分数与适用范围</h1>
<p class="purpose">这页回答：分数说的是未来最多 5 个交易日的正股价格路径，不是期权会不会赚钱。下面不解释某一只股票今天为什么是这个分。</p>
<ol class="steps">
  <li>1. 先看分数适用什么、不适用什么。</li>
  <li>2. 再看历史上过线之后，标签记为命中的比例和平均收益。</li>
  <li>3. 最后看个别股票的原始分和规则调整后的分。点代码回到看盘页。</li>
</ol>
<div class="grid">
  <section class="card"><h2>适用</h2><p>比较模型对正股路径的规则分。标签定义是：下一交易日开盘进场，最多看 5 个交易日。先碰到止盈轨记为命中；先碰到止损、同一天两边都碰到，或 5 日都没碰到，记为未命中。</p></section>
  <section class="card"><h2>不适用</h2><p>不能当成 Call 或 Put 的已实现盈亏，也不能当成当日到期合约的胜率。分数没有按期权权利金校准。</p></section>
  <section class="card"><h2>止盈和止损轨</h2><p>止盈至少是进场价的 3%，或 1.35 倍有效波动。止损至少是 2.2%，或 1 倍有效波动。最后 5 个交易日没有标签。</p></section>
</div>
<h2>历史样本里，过线之后发生了什么</h2>
<p class="note">命中比例高、平均收益仍可能为负。快照 KPI 写的高信念数字是 {esc(snapshot['market'].get('kpi_win'))}，和表里「≥ 60%」那一行的命中比例相同。这不是本页新算的。</p>
<div class="wrap"><table>
  <thead><tr><th>规则分阈值</th><th>触发次数</th><th>标签记为命中</th><th>平均实现收益</th><th>盈亏比</th></tr></thead>
  <tbody>{thresholds or '<tr><td colspan="5">快照没有这张表</td></tr>'}</tbody>
</table></div>
<h2>规则调整后的做多分，从高到低看 12 只</h2>
<p class="note">做多分 = 模型原始输出，加上结构加减，再乘赛道盈亏比，并加上 4 小时启发式调整。做空分还有期权比和宏观加减，并截断在 10 到 95。都不是实证校准过的期权胜率。</p>
<div class="wrap"><table>
  <thead><tr><th>代码</th><th>规则调整后的做多分</th><th>模型原始输出</th><th>结构加减后</th><th>规则调整后的做空分</th><th>快照动作原文</th></tr></thead>
  <tbody>{''.join(rows) or '<tr><td colspan="6">快照没有模型行</td></tr>'}</tbody>
</table></div>
<details>
  <summary>这些价位和标签在源码里是怎么来的</summary>
  <p>支撑和阻力把回撤、均线、20 日成交量分箱的估算峰值和期权行权价拼在一起。4 小时标签在没有 4 小时 K 线时，会退回日线规则，甚至用日线 RSI 乘 0.95 再加 2.5。所以它不是已核对的背离。</p>
</details>
"""
    return shell("模型：分数与适用范围", "predict.html", body)


def page_backtest() -> str:
    engine = (ROOT / "backtest_5y_engine.py").read_text(encoding="utf-8")
    radar = (ROOT / "integrated_market_radar.py").read_text(encoding="utf-8")
    slip = re.search(r"SLIPPAGE_RATE = ([0-9.]+)", engine).group(1)
    position = re.search(r"POSITION_PCT = ([0-9.]+)", engine).group(1)
    capital = re.search(r"INITIAL_CAPITAL = ([0-9.]+)", engine).group(1)
    max_pos = re.search(r"MAX_POSITION_PCT = ([0-9.]+)", radar).group(1)
    equity = re.search(r"TOTAL_ACCOUNT_EQUITY = ([0-9.]+)", radar).group(1)
    rows = [
        ["期末资产", "$130,441.41", "$187,910.80", "$216,696.43"],
        ["净利润", "+$30,441.41", "+$87,910.80", "+$116,696.43"],
        ["年化收益", "+5.77%", "+14.24%", "+17.73%"],
        ["最大回撤", "-11.31%", "-19.03%", "-29.56%"],
        ["盈亏比", "1.68", "1.38", "战报没有"],
        ["盈利笔数比例", "58.33%（84 笔）", "55.41%（74 笔）", "战报没有"],
        ["夏普", "0.36", "0.73", "0.68"],
        ["卡尔玛", "0.51", "0.75", "0.60"],
        ["战报写的摩擦成本", "$658.22", "$2,190.24", "$0.00"],
    ]
    body_rows = "".join(
        "<tr>" + "".join(f"<td class='num'>{esc(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    body = f"""
<h1>历史表现与风险</h1>
<p class="purpose">这页回答：已提交战报里，股票账户的历史模拟赚过多少、回撤多大。它不是期权买方的成绩，也不能保证以后。</p>
<ol class="steps">
  <li>1. 先看限制：区间、笔数、成本和它不是什么。</li>
  <li>2. 再看三列对照。买入持有纳指的期末资产更高，回撤也更深。</li>
  <li>3. 战报和引擎源码的滑点、仓位不一致，两边都照原样列出。</li>
</ol>
<div class="grid">
  <section class="card"><h2>区间和样本</h2><p>战报区间 2021-10-29 至 2026-10-28，1,194 个交易日，本金 $100,000。纯股一列 84 笔，纳指增强一列 74 笔。</p></section>
  <section class="card"><h2>成本按哪份文字</h2><p>战报写佣金 $0、滑点 1.5 个基点。引擎源码 <code>SLIPPAGE_RATE = {esc(slip)}</code>，按成交价的 {float(slip)*100:.1f}% 计。本页不把两套数字合成一个。</p></section>
  <section class="card"><h2>和期权无关的仓位</h2><p>看盘程序写单股上限 {float(max_pos)*100:.0f}%，参考账户 ${float(equity):,.0f}。回测引擎写单笔 {float(position)*100:.0f}% 资金、初始资金 ${float(capital):,.0f}。战报另写 25% 上限和 1.5% 账户风险。这些都是股票仓位，不是期权张数。</p></section>
</div>
<h2>战报对照表</h2>
<p class="note">来源 <code>backtest_report_5y.md</code>。盈利笔数比例是模拟交易里赚钱的笔数占比，和模型页的规则分不是同一个数。</p>
<div class="wrap"><table>
  <thead><tr><th>项目</th><th>纯股模拟</th><th>纳指增强模拟</th><th>买入持有纳指</th></tr></thead>
  <tbody>{body_rows}</tbody>
</table></div>
<details>
  <summary>战报里的几笔股票交易摘录</summary>
  <p>ASML 2025-12-22 至 2026-02-04，+30.90%。NVDA 2023-01-10 至 2023-02-15，+44.28%。这些是战报列出的股票价差，不是期权权利金收益。</p>
</details>
"""
    return shell("回测：历史表现与风险", "backtest.html", body)


def write_pages(snapshot: dict, out_dir: Path) -> None:
    pages = {
        "index.html": page_index(snapshot),
        "macro.html": page_macro(snapshot),
        "stocks.html": page_stocks(snapshot),
        "predict.html": page_predict(snapshot),
        "backtest.html": page_backtest(),
    }
    for name, text in pages.items():
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"wrote {name} {len(text)//1024} KB")
