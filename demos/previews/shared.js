const SNAPSHOT = __SNAPSHOT__;
const LAYOUT = document.body.dataset.layout;
const BY = Object.fromEntries(SNAPSHOT.items.map((item) => [item.ticker, item]));
const STAR_KEY = "us-radar-layout-preview-stars";
const TABS = [
  ["essentials", "盘面"],
  ["market", "市场"],
  ["sector", "板块"],
  ["ai", "AI"],
  ["options", "期权"],
  ["tactics", "参考"],
];

const state = {
  ticker: "LLY",
  lastStock: "LLY",
  period: "D",
  step: "stock",
  sector: "全部",
  listMode: "stocks",
  tab: "essentials",
  indi: "vol",
  q: "",
  collapsed: false,
  drawerOpen: false,
  open: { essentials: true, market: false, sector: false, ai: false, options: false, tactics: false },
  starred: new Set(),
};

let hover = null;
let geom = null;
let drawing = false;

function plain(value) {
  return String(value ?? "").replace(/\p{Extended_Pictographic}/gu, "").replace(/\s+/g, " ").trim();
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}
function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function money(value) {
  const n = num(value);
  if (n == null) return "—";
  const digits = Math.abs(n) >= 1 ? 2 : 4;
  return n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
function fmtPct(value) {
  const n = num(value);
  if (n == null) return "—";
  return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
}
function clsPct(value) {
  const n = num(value);
  if (n == null || Math.abs(n) < 0.005) return "flat";
  return n > 0 ? "up" : "down";
}
function setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
function sectorName(item) {
  if (item.kind === "etf") return item.cat || "ETF";
  return item.sector_cn || "未进入 AI 板块快照";
}
function current() {
  return BY[state.ticker] || BY.LLY;
}
function loadStars() {
  try {
    const raw = JSON.parse(localStorage.getItem(STAR_KEY) || "[]");
    if (Array.isArray(raw)) state.starred = new Set(raw);
  } catch (err) {
    state.starred = new Set();
  }
}
function saveStars() {
  try { localStorage.setItem(STAR_KEY, JSON.stringify([...state.starred])); } catch (err) { /* preview only */ }
}

function sma(values, n) {
  const out = Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= n) sum -= values[i - n];
    if (i >= n - 1) out[i] = sum / n;
  }
  return out;
}
function ema(values, n) {
  const out = Array(values.length).fill(null);
  const k = 2 / (n + 1);
  let prev = null;
  let seed = 0;
  let count = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null || !Number.isFinite(v)) continue;
    if (prev == null) {
      seed += v;
      count += 1;
      if (count === n) {
        prev = seed / n;
        out[i] = prev;
      }
      continue;
    }
    prev = v * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}
function rsi(values, n = 14) {
  const out = Array(values.length).fill(null);
  if (values.length <= n) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= n; i++) {
    const d = values[i] - values[i - 1];
    if (d >= 0) gain += d;
    else loss -= d;
  }
  let ag = gain / n;
  let al = loss / n;
  out[n] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  for (let i = n + 1; i < values.length; i++) {
    const d = values[i] - values[i - 1];
    ag = (ag * (n - 1) + (d > 0 ? d : 0)) / n;
    al = (al * (n - 1) + (d < 0 ? -d : 0)) / n;
    out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
  }
  return out;
}
function macd(values) {
  const e12 = ema(values, 12);
  const e26 = ema(values, 26);
  const dif = values.map((_, i) => (e12[i] == null || e26[i] == null ? null : e12[i] - e26[i]));
  const dea = ema(dif, 9);
  const hist = dif.map((v, i) => (v == null || dea[i] == null ? null : v - dea[i]));
  return { dif, dea, hist };
}
function isoWeek(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const day = dt.getUTCDay() || 7;
  dt.setUTCDate(dt.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(dt.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((dt - yearStart) / 86400000) + 1) / 7);
  return dt.getUTCFullYear() + "-W" + String(week).padStart(2, "0");
}
function aggregate(bars, period) {
  if (period === "D") return bars;
  const map = new Map();
  const groups = [];
  bars.forEach((bar) => {
    const key = period === "W" ? isoWeek(bar[0]) : bar[0].slice(0, 7);
    const found = map.get(key);
    if (!found) {
      const next = [bar[0], bar[1], bar[2], bar[3], bar[4], bar[5] || 0];
      map.set(key, next);
      groups.push(next);
      return;
    }
    found[0] = bar[0];
    found[2] = Math.max(found[2], bar[2]);
    found[3] = Math.min(found[3], bar[3]);
    found[4] = bar[4];
    found[5] += bar[5] || 0;
  });
  return groups;
}

function visibleItems() {
  const q = state.q.trim().toLowerCase();
  return SNAPSHOT.items.filter((item) => {
    if (state.listMode === "stocks" && item.kind !== "stock") return false;
    if (state.listMode === "etf" && item.kind !== "etf") return false;
    if (state.listMode === "star" && !state.starred.has(item.ticker)) return false;
    if (state.sector !== "全部" && sectorName(item) !== state.sector) return false;
    if (!q) return true;
    const blob = `${item.ticker} ${item.name} ${item.sub || ""} ${item.cat || ""} ${item.sector_cn || ""}`.toLowerCase();
    return blob.includes(q);
  });
}

function quoteFacts(item) {
  const sector = item.kind === "etf" ? (item.cat || "ETF") : (item.sector_cn || "未进入 AI 板块快照");
  return `
    <div class="quote-id">
      <div class="sym" id="quoteSym">${esc(item.ticker)}</div>
      <div>
        <div class="qname">${esc(item.name)}</div>
        <div class="qsub">${esc(item.sub || "")}</div>
      </div>
    </div>
    <div class="px-pair">
      <div>
        <div class="px-label">日盘收盘</div>
        <div class="px-main num ${clsPct(item.pct_change)}">${money(item.last)}</div>
        <div class="px-chg num ${clsPct(item.pct_change)}">${fmtPct(item.pct_change)}</div>
      </div>
      <div>
        <div class="px-label">夜盘参考</div>
        <div class="px-sub num">${money(item.active_price)}</div>
        <div class="px-chg num ${clsPct(item.ext_pct)}">${fmtPct(item.ext_pct)}</div>
      </div>
    </div>
    <div class="quote-facts">
      <div><span>板块</span><b>${esc(sector)}</b></div>
      <div><span>快照信号</span><b>${esc(plain(item.signal) || "快照没有")}</b></div>
      <div><span>会话标记</span><b>${esc(item.session_tag || "—")} · 非本页实时</b></div>
    </div>
    <button type="button" class="star ${state.starred.has(item.ticker) ? "on" : ""}" data-act="star">${state.starred.has(item.ticker) ? "已记在本页" : "记在本页"}</button>`;
}
function metricsHTML(item) {
  const cells = [
    ["50 日均线", money(item.ma50)],
    ["MA50 偏离", fmtPct(item.bias)],
    ["EMA20", money(item.ema20)],
    ["14 日 RSI", item.rsi == null ? "—" : Number(item.rsi).toFixed(1)],
    ["14 日 ATR", money(item.atr)],
    ["成交量比", item.vol_ratio == null ? "—" : Number(item.vol_ratio).toFixed(2)],
  ];
  const panel = item.panel_last
    ? `面板最后交易日 ${item.panel_last} 收盘 ${money(item.panel_close)}。上面的日盘收盘来自终端快照。两套来源不同，本页没有改写成同一个价格。`
    : "日 K 面板里没有这个代码。";
  return `
    <div class="metrics">${cells.map(([label, value]) => `<div class="metric"><span class="lbl">${label}</span><span class="val num">${esc(value)}</span></div>`).join("")}</div>
    <p class="src">${esc(panel)}</p>`;
}
function marketParts() {
  const m = SNAPSHOT.market;
  const names = Object.entries(m.trad_components).concat(Object.entries(m.tech_components));
  const indices = `<div class="index-grid">
        ${m.indices.map((row) => `<button type="button" class="idx-card ${row.ticker === state.ticker ? "on" : ""}" data-act="ticker" data-ticker="${esc(row.ticker)}">
          <div class="tk">${esc(row.ticker)} ${esc(row.name || "")}</div>
          <div class="px num ${clsPct(row.pct_change)}">${money(row.last)}</div>
          <div class="num ${clsPct(row.pct_change)}">日盘 ${fmtPct(row.pct_change)}</div>
        </button>`).join("")}
      </div>`;
  const chips = `<div class="chips">${names.map(([ticker, pct]) => `<span class="num ${clsPct(pct)}">${esc(ticker)} ${fmtPct(pct)}</span>`).join("")}</div>`;
  const note = `<p class="src">成分涨跌是快照里写好的百分点。KPI 高信念胜率 ${m.kpi_win == null ? "—" : Number(m.kpi_win).toFixed(1) + "%"}，盈亏比 ${m.kpi_pf == null ? "—" : Number(m.kpi_pf).toFixed(2)}。这是预测快照的历史统计，不是单票实时概率。领先板块原文：${esc(m.top_sector)}</p>`;
  const detail = `<div class="stack">
      <div class="card"><h3>天气原文</h3><div>${esc(m.weather_status)} · 数据日 ${esc(m.weather_date || "—")}</div><p>${esc(m.weather_desc)}</p></div>
      <div class="card"><h3>宽度原文</h3><div>${esc(m.breadth_tag)}</div><p>${esc(m.breadth_text)}</p></div>
      <div class="card"><h3>防御因子原文</h3><p>${esc(m.defensive_text || "快照没有这段文字")}${m.defensive_score == null ? "" : " · 分数 " + Number(m.defensive_score).toFixed(2)}</p></div>
      ${note}
    </div>`;
  const brief = `<div class="stack">${indices}<p>${esc(m.weather_status)} · 数据日 ${esc(m.weather_date || "—")} · ${esc(m.breadth_tag)} · ${esc(m.defensive_text || "")}</p>${chips}</div>`;
  return { brief, detail, all: `<div class="stack">${indices}${chips}</div>${detail}` };
}
function sectorHTML() {
  const active = state.sector;
  const rows = SNAPSHOT.sectors.map((row) => `
    <button type="button" class="srow ${active === row.name ? "on" : ""}" data-act="sector" data-sector="${esc(row.name)}">
      <strong>${esc(row.name)}</strong>
      <span class="stats">
        <span>命中比例 ${row.win == null ? "—" : Number(row.win).toFixed(1) + "%"}</span>
        <span>样本 ${row.samples == null ? "—" : Number(row.samples).toLocaleString("en-US")}</span>
        <span>高信念信号 ${row.high_conviction_signals == null ? "—" : row.high_conviction_signals}</span>
        <span>盈亏比 ${row.pf == null ? "—" : Number(row.pf).toFixed(2)}</span>
        <span>${esc(row.rating || "")}</span>
      </span>
    </button>`).join("");
  return `
    <div class="stack">
      <button type="button" class="plain" data-act="clear-sector">全部板块</button>
      ${rows}
      <p class="src">表里的百分比是历史样本的命中比例，括号里的星级来自快照。高信念信号笔数见每一行。这不是今天的上涨概率。</p>
    </div>`;
}
function aiHTML(item) {
  const ai = item.ai;
  if (!ai) return `<p class="empty">该标的不在 AI 5 年快照里。</p>`;
  const levels = [
    ["做多止盈价（美元/股）", ai.target_profit_price, ai.target_profit_pct],
    ["做多止损价（美元/股）", ai.stop_loss_price, ai.stop_loss_pct == null ? null : -Math.abs(ai.stop_loss_pct)],
    ["做空止盈价（美元/股）", ai.short_target_profit_price, ai.short_target_profit_pct == null ? null : -Math.abs(ai.short_target_profit_pct)],
    ["做空止损价（美元/股）", ai.short_stop_loss_price, ai.short_stop_loss_pct],
  ];
  return `
    <div class="stack">
      <div class="card">
        <h3>快照原文：${esc(ai.action || "没有动作原文")}</h3>
        <div class="kv">
          <span class="k" title="模型原始输出经过结构加减，再乘赛道盈亏比并加上 4 小时启发式调整。不是用历史 Call/Put 盈亏校准出来的胜率。">规则调整后的做多分</span><span class="num">${ai.calibrated_win_rate_pct == null ? "—" : Number(ai.calibrated_win_rate_pct).toFixed(1)} · 排序 ${ai.rank ?? "—"}</span>
          <span class="k" title="空头原始输出再按赛道、期权比、宏观和形态规则加减，并截断在 10 到 95。">规则调整后的做空分</span><span class="num">${ai.calibrated_short_win_rate_pct == null ? "—" : Number(ai.calibrated_short_win_rate_pct).toFixed(1)} · 排序 ${ai.short_rank ?? "—"}</span>
          <span class="k">模型原始输出 / 做空原始输出</span><span class="num">${ai.model_raw_prob_pct == null ? "—" : Number(ai.model_raw_prob_pct).toFixed(1)} / ${ai.model_raw_short_prob_pct == null ? "—" : Number(ai.model_raw_short_prob_pct).toFixed(1)}</span>
          <span class="k">结构加减后的做多分</span><span class="num">${ai.predicted_win_rate_pct == null ? "—" : Number(ai.predicted_win_rate_pct).toFixed(1)}</span>
          <span class="k">做空原文</span><span>${esc(ai.short_action || "—")}</span>
          <span class="k">4 小时启发式标签</span><span>${esc(ai.four_h_div || "快照没有")}</span>
        </div>
        <p class="src">分数预测的是最多 5 个交易日内，价格先碰到止盈轨还是止损轨。它不是期权盈利概率。4 小时标签由日线或缓存 K 线的规则打出，不是已核对的背离或成交分布。</p>
      </div>
      <div class="metrics">
        ${levels.map(([label, price, pct]) => `<div class="metric"><span class="lbl">${label}</span><span class="val num">${money(price)}</span><span class="src">${pct == null ? "" : fmtPct(pct)}</span></div>`).join("")}
      </div>
      <div class="card">
        <h3>规则估算的价位（美元/股）</h3>
        <div class="kv">
          <span class="k" title="由回撤、均线和估算成交峰拼出来的价位，不是交易所的成交分布。">支撑 1 / 支撑 2</span><span class="num">${money(ai.s1)} / ${money(ai.s2)}</span>
          <span class="k">阻力 1 / 阻力 2</span><span class="num">${money(ai.r1)} / ${money(ai.r2)}</span>
          <span class="k">防守价</span><span class="num">${money(ai.sl)}</span>
          <span class="k" title="这是模型字段。期权链缺失时，源码会用收盘价的约 105% 和 95% 填上。">模型字段里的行权价</span><span class="num">Call ${money(ai.call_wall)} · Put ${money(ai.put_wall)}</span>
          <span class="k">模型字段里的张数比</span><span>${ai.pcr == null ? "—" : Number(ai.pcr).toFixed(2)} · ${esc(ai.pcr_sentiment || "")}</span>
        </div>
        <p class="src">上面的行权价和张数比来自模型快照。下面期权链是另一份缓存。两边不同就分开看，本页不把它们合成一个结论。天气原文：${esc(ai.macro_temp || "—")}</p>
      </div>
      <details>
        <summary>点位原文（规则估算，不是已验证的成交密集区）</summary>
        <blockquote class="script">${esc(ai.scenario_script || "快照没有这段原文")}</blockquote>
      </details>
    </div>`;
}
function optionsHTML(item) {
  const op = item.options;
  if (!op) return `<p class="empty">这份快照没有期权链。这里留空，不显示 0。</p>`;
  return `
    <div class="stack">
      <div class="card">
        <h3>${esc(op.pcr_sentiment || "快照没有多空字样")}</h3>
        <p class="src">这句是源码按张数比和权利金比写的标签，不是机构方向。</p>
        <div class="kv">
          <span class="k">到期日</span><span>${esc(op.options_exp || "快照没有")}</span>
          <span class="k" title="Put 张数除以 Call 张数。权利金比是成交金额之比。都不是胜率。">张数比 / 权利金比</span><span class="num">${op.pcr == null ? "—" : Number(op.pcr).toFixed(2)} / ${op.dollar_pcr == null ? "—" : Number(op.dollar_pcr).toFixed(2)}</span>
          <span class="k">Call / Put 张数</span><span class="num">${op.call_vol == null ? "—" : Number(op.call_vol).toLocaleString("en-US")} / ${op.put_vol == null ? "—" : Number(op.put_vol).toLocaleString("en-US")}</span>
          <span class="k" title="平值附近 Call 和 Put 的隐含波动率，单位是百分数。">平值隐含波动</span><span class="num">${op.iv_atm == null ? "—" : Number(op.iv_atm).toFixed(1) + "%"}</span>
          <span class="k" title="用平值跨式权利金估算的正股价格区间，不是权利金本身。">正股波动区间</span><span>${esc(op.exp_move_str || "—")}</span>
          <span class="k" title="该到期日里，成交权利金最集中的行权价。行权价的单位是正股价格。这不是 GEX，也不是机构方向。">权利金最集中的行权价</span><span class="num">Call ${money(op.call_wall)} · Put ${money(op.put_wall)}</span>
        </div>
      </div>
      <div class="card"><h3>Call 权利金最高的一档</h3><p>${esc(op.top_call_info || "快照没有")}</p><p class="src">括号里的金额是权利金，不是正股价格。</p></div>
      <div class="card"><h3>Put 权利金最高的一档</h3><p>${esc(op.top_put_info || "快照没有")}</p><p class="src">源码优先选大约 2 到 11 天的周五合约，并跳过已经收盘的当日到期合约。</p></div>
    </div>`;
}
function tacticsHTML(item) {
  const rows = [
    ["位置原文", item.pit_status || "快照没有"],
    ["相对回撤带", item.dist_to_pit == null ? "快照没有" : fmtPct(item.dist_to_pit)],
    ["0.5–0.618 回撤带（美元/股）", item.fib_low == null ? "快照没有" : `${money(item.fib_low)} – ${money(item.fib_high)}`],
    ["正股参考价（美元/股）", item.optimal_limit == null ? "快照没有" : money(item.optimal_limit)],
    ["参考说明", item.limit_note || "—"],
    ["参考防守", item.entry_stop_loss == null ? "—" : money(item.entry_stop_loss)],
    ["结构防守", item.struct_stop == null ? "—" : money(item.struct_stop)],
    ["日内状态原文", item.intraday_status_text || "—"],
    ["日内说明原文", item.intraday_reason || "—"],
    ["VWAP", item.vwap == null ? "—" : money(item.vwap)],
    ["5 分 RSI / 量比", `${item.rsi_5m == null ? "—" : Number(item.rsi_5m).toFixed(1)} / ${item.rvol_5m == null ? "—" : Number(item.rvol_5m).toFixed(2)}`],
    ["20 日相对强度", item.rs_20d == null ? "—" : Number(item.rs_20d).toFixed(2)],
  ];
  return `
    <div class="stack">
      <div class="kv">${rows.map(([k, v]) => `<span class="k">${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>
      <p class="src">这些是正股价格。生产页的 25% 是股票仓位上限，不是期权买多少张。本页不能下单。</p>
    </div>`;
}

function renderStepper() {
  const steps = [["market", "1 市场环境"], ["sector", "2 选标的"], ["stock", "3 看走势"], ["options", "4 查期权"]];
  setHTML("stepper", steps.map(([id, label]) =>
    `<button type="button" class="step ${state.step === id ? "on" : ""}" data-act="step" data-step="${id}" ${state.step === id ? 'aria-current="step"' : ""}>${label}</button>`
  ).join(""));
}
function renderFilters() {
  const modes = [["all", "全部"], ["stocks", "个股"], ["etf", "ETF"], ["star", "本页标记"]];
  setHTML("filters", modes.map(([id, label]) =>
    `<button type="button" class="chip ${state.listMode === id ? "on" : ""}" data-act="mode" data-mode="${id}">${label}</button>`
  ).join(""));
}
function renderWatch() {
  const collapsed = LAYOUT === "a" && state.collapsed && window.innerWidth > 1180;
  const rows = visibleItems();
  if (!rows.length) {
    setHTML("watchList", `<div class="empty">没有匹配的标的。</div>`);
    return;
  }
  setHTML("watchList", rows.map((item) => {
    const price = money(item.last);
    const pct = fmtPct(item.pct_change);
    if (collapsed) {
      return `<button type="button" class="row ${item.ticker === state.ticker ? "on" : ""}" data-act="ticker" data-ticker="${esc(item.ticker)}" title="${esc(item.name)}">
        <span class="tk">${esc(item.ticker)}</span><span class="pc num ${clsPct(item.pct_change)}">${pct}</span>
      </button>`;
    }
    return `<button type="button" class="row ${item.ticker === state.ticker ? "on" : ""}" data-act="ticker" data-ticker="${esc(item.ticker)}" title="${esc(item.sub || item.name)}">
      <span class="tk">${esc(item.ticker)}</span><span class="px num">${price}</span>
      <span class="nm">${esc(item.name)}</span><span class="pc num ${clsPct(item.pct_change)}">${pct}</span>
    </button>`;
  }).join(""));
}
function renderPeriods() {
  const periods = [
    ["D", "日K", false],
    ["W", "周K", false],
    ["M", "月K", false],
    ["I", "分时", true],
    ["5", "5分", true],
  ];
  setHTML("periods", periods.map(([id, label, disabled]) =>
    `<button type="button" class="seg ${state.period === id ? "on" : ""}" data-act="period" data-period="${id}" ${disabled ? 'disabled title="快照面板只有日线。分时没有收录，这里不编造。"' : ""}>${label}</button>`
  ).join(""));
  const indis = [["vol", "成交量"], ["rsi", "RSI"], ["macd", "MACD"]];
  setHTML("indis", indis.map(([id, label]) =>
    `<button type="button" class="seg ${state.indi === id ? "on" : ""}" data-act="indi" data-indi="${id}">${label}</button>`
  ).join(""));
}
function renderTabs() {
  setHTML("tabs", TABS.map(([id, label]) =>
    `<button type="button" role="tab" data-act="tab" data-tab="${id}" aria-selected="${state.tab === id ? "true" : "false"}" class="${state.tab === id ? "on" : ""}">${label}</button>`
  ).join(""));
}
function summaries(item) {
  const ai = item.ai || {};
  const op = item.options || {};
  return {
    essentials: `日盘 ${money(item.last)} · ${fmtPct(item.pct_change)} · RSI ${item.rsi == null ? "—" : Number(item.rsi).toFixed(1)}`,
    market: `${SNAPSHOT.market.weather_status} · QQQ 日盘 ${fmtPct(BY.QQQ ? BY.QQQ.pct_change : null)}`,
    sector: sectorName(item),
    ai: ai.calibrated_win_rate_pct == null ? "快照没有这只股票的模型分" : `规则调整后的做多分 ${Number(ai.calibrated_win_rate_pct).toFixed(1)}，不是期权胜率`,
    options: op.pcr == null ? "这份快照没有期权链，不显示 0" : `到期 ${op.options_exp || "—"} · 张数比 ${Number(op.pcr).toFixed(2)} · 权利金比 ${op.dollar_pcr == null ? "—" : Number(op.dollar_pcr).toFixed(2)}`,
    tactics: `正股参考价 ${item.optimal_limit == null ? "快照没有" : money(item.optimal_limit)} · 不是期权张数`,
  };
}
function chartNote(item) {
  const raw = SNAPSHOT.bars[item.ticker] || [];
  if (!raw.length) return "离线图表：5 年面板里没有这个代码的日 K。本页不编造 K 线，也不加载 TradingView。";
  const name = state.period === "D" ? "日K" : state.period === "W" ? "周K" : "月K";
  const file = item.panel_file ? `data_cache/${item.panel_file}` : SNAPSHOT.meta.panel_source;
  return `图上是离线${name}，最后一根是面板交易日 ${raw[raw.length - 1][0]}。这不是看盘软件的时钟，也不是模型分数。来源 ${file}。周K和月K由这些日K聚合。`;
}
function syncPanels() {
  document.querySelectorAll(".drawer [data-panel]").forEach((el) => {
    el.classList.toggle("on", el.dataset.panel === state.tab);
  });
  document.querySelectorAll("#tabs [data-tab]").forEach((el) => {
    const on = el.dataset.tab === state.tab;
    el.classList.toggle("on", on);
    el.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".acc").forEach((el) => {
    el.classList.toggle("open", !!state.open[el.dataset.acc]);
  });
}
function renderJump() {
  const sel = document.getElementById("jump");
  if (!sel) return;
  if (!sel.options.length) {
    SNAPSHOT.items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.ticker;
      option.textContent = `${item.ticker} ${item.name}`;
      sel.appendChild(option);
    });
  }
  sel.value = state.ticker;
}
function render() {
  const item = current();
  document.body.classList.toggle("is-collapsed", state.collapsed);
  document.body.classList.toggle("drawer-open", !!state.drawerOpen);
  const collapse = document.getElementById("btnCollapse");
  if (collapse) collapse.textContent = state.collapsed ? "展开列表" : "收起列表";
  setText("topMeta", `市场快照：${plain(SNAPSHOT.market.weather_status)}。QQQ 日盘 ${fmtPct(BY.QQQ ? BY.QQQ.pct_change : null)}。截至 ${SNAPSHOT.meta.sync_time}`);
  const quoteInner = LAYOUT === "c" ? quoteFacts(item) + metricsHTML(item) : quoteFacts(item);
  setHTML("quoteHost", `<div class="quote">${quoteInner}</div>`);
  setHTML("essentialsHost", metricsHTML(item));
  setHTML("keyline", `${esc(plain(item.signal) || "无信号原文")} · MA50 偏离 ${fmtPct(item.bias)} · RSI ${item.rsi == null ? "—" : Number(item.rsi).toFixed(1)} · ${esc(plain(item.pit_status) || "位置未记录")}`);
  const market = marketParts();
  setHTML("marketHost", LAYOUT === "c" ? market.brief : market.all);
  setHTML("marketDetail", market.detail);
  setHTML("sectorHost", sectorHTML());
  setHTML("aiHost", aiHTML(item));
  setHTML("optionsHost", optionsHTML(item));
  setHTML("tacticsHost", tacticsHTML(item));
  const sums = summaries(item);
  Object.entries(sums).forEach(([key, text]) => setText("sum-" + key, text));
  setText("chartNote", chartNote(item));
  setText("footnote", `报价同步 ${SNAPSHOT.meta.sync_time}，会话标记：${(SNAPSHOT.meta.session_tags || []).join("、") || "—"}。报价、日K和模型分是三套数字。生产页「AI高胜率」会列出全部有模型记录的代码，并不是筛过的高分名单；「做空榜 Top 5」在当前代码里也没有截成 5 只。本页不沿用这两个名字。不能下单。`);
  renderStepper();
  renderFilters();
  renderWatch();
  renderPeriods();
  renderTabs();
  renderJump();
  syncPanels();
  requestAnimationFrame(drawChart);
}

function drawLine(ctx, xs, values, color, yOf) {
  ctx.beginPath();
  let started = false;
  values.forEach((v, i) => {
    if (v == null) return;
    const x = xs(i);
    const y = yOf(v);
    if (!started) { ctx.moveTo(x, y); started = true; }
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  ctx.stroke();
}
function drawChart() {
  if (drawing) return;
  const canvas = document.getElementById("chart");
  const empty = document.getElementById("chartEmpty");
  if (!canvas) return;
  const frame = canvas.parentElement;
  const w = frame.clientWidth;
  const h = frame.clientHeight;
  if (w < 20 || h < 20) return;
  drawing = true;
  try {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#10141a";
    ctx.fillRect(0, 0, w, h);
    const item = current();
    const raw = SNAPSHOT.bars[item.ticker] || [];
    const agg = aggregate(raw, state.period);
    if (agg.length < 2) {
      empty.hidden = false;
      empty.textContent = raw.length
        ? "聚合后的 K 线不足，无法作图。"
        : "离线图表：面板没有该标的日 K。未加载外部图表，也没有编造 K 线。";
      geom = null;
      setText("ohlcReadout", "无 K 线");
      return;
    }
    empty.hidden = true;
    const closes = agg.map((bar) => bar[4]);
    const ma20 = sma(closes, 20);
    const ma50 = sma(closes, 50);
    const rsiAll = rsi(closes, 14);
    const macdAll = macd(closes);
    const show = state.period === "D" ? 110 : state.period === "W" ? 70 : 36;
    const start = Math.max(0, agg.length - show);
    const bars = agg.slice(start);
    const s20 = ma20.slice(start);
    const s50 = ma50.slice(start);
    const left = 68;
    const right = 16;
    const top = 28;
    const bottom = 28;
    const pane = state.indi === "vol" ? Math.round(h * 0.22) : Math.round(h * 0.28);
    const priceBottom = h - bottom - pane - 10;
    let lo = Math.min(...bars.map((bar) => bar[3]));
    let hi = Math.max(...bars.map((bar) => bar[2]));
    const op = item.options || {};
    const walls = [];
    [["Call 墙", op.call_wall], ["Put 墙", op.put_wall]].forEach(([label, wall]) => {
      if (wall == null) return;
      if (wall <= hi * 1.05 && wall >= lo * 0.95) walls.push([label, wall]);
    });
    walls.forEach(([, wall]) => { lo = Math.min(lo, wall); hi = Math.max(hi, wall); });
    const pad = (hi - lo) * 0.06 || 1;
    lo -= pad;
    hi += pad;
    const plotW = w - left - right;
    const slot = plotW / bars.length;
    const yOf = (price) => top + (hi - price) / (hi - lo) * (priceBottom - top);
    const xOf = (i) => left + slot * (i + 0.5);
    geom = { left, slot, n: bars.length };
    ctx.font = '14px "WenQuanYi Micro Hei", sans-serif';
    ctx.fillStyle = "#9aa3b2";
    ctx.textAlign = "left";
    ctx.fillText("离线快照 · 非实时", left, 18);
    ctx.textAlign = "right";
    ctx.fillStyle = "#d7b07a";
    ctx.fillText("MA20", w - right - 64, 18);
    ctx.fillStyle = "#9bb8e8";
    ctx.fillText("MA50", w - right, 18);
    ctx.strokeStyle = "#222833";
    ctx.lineWidth = 1;
    ctx.textAlign = "right";
    for (let g = 0; g < 4; g++) {
      const price = lo + (hi - lo) * (g / 3);
      const y = yOf(price);
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(w - right, y);
      ctx.stroke();
      ctx.fillStyle = "#9aa3b2";
      ctx.fillText(money(price), left - 8, y + 4);
    }
    if (state.indi === "vol") {
      const maxV = Math.max(...bars.map((bar) => bar[5] || 0), 1);
      bars.forEach((bar, i) => {
        const bh = (bar[5] || 0) / maxV * (pane - 8);
        ctx.fillStyle = bar[4] >= bar[1] ? "rgba(125,206,160,0.45)" : "rgba(224,139,139,0.45)";
        ctx.fillRect(xOf(i) - Math.max(1, slot * 0.28), h - bottom - bh, Math.max(1.5, slot * 0.56), bh);
      });
    } else if (state.indi === "rsi") {
      const yR = (v) => priceBottom + 16 + (100 - v) / 100 * (h - bottom - priceBottom - 24);
      [30, 70].forEach((level) => {
        ctx.strokeStyle = "#2c3442";
        ctx.beginPath();
        ctx.moveTo(left, yR(level));
        ctx.lineTo(w - right, yR(level));
        ctx.stroke();
      });
      drawLine(ctx, xOf, rsiAll.slice(start), "#c3b1d4", yR);
      ctx.fillStyle = "#9aa3b2";
      ctx.textAlign = "left";
      ctx.fillText("RSI 由面板收盘价计算", left, priceBottom + 16);
    } else {
      const series = macdAll.hist.slice(start);
      const vals = series.filter((v) => v != null);
      const span = vals.length ? Math.max(...vals.map((v) => Math.abs(v)), 0.01) : 0.01;
      const mid = priceBottom + (h - bottom - priceBottom) / 2;
      series.forEach((v, i) => {
        if (v == null) return;
        const bh = v / span * (pane * 0.45);
        ctx.fillStyle = v >= 0 ? "rgba(125,206,160,0.7)" : "rgba(224,139,139,0.7)";
        ctx.fillRect(xOf(i) - Math.max(1, slot * 0.28), v >= 0 ? mid - bh : mid, Math.max(1.5, slot * 0.56), Math.abs(bh));
      });
      ctx.fillStyle = "#9aa3b2";
      ctx.textAlign = "left";
      ctx.fillText("MACD 柱由面板收盘价计算", left, priceBottom + 16);
    }
    ctx.save();
    ctx.beginPath();
    ctx.rect(left - 4, top, w - left - right + 8, Math.max(10, priceBottom - top));
    ctx.clip();
    bars.forEach((bar, i) => {
      const up = bar[4] >= bar[1];
      const x = xOf(i);
      ctx.strokeStyle = up ? "#7dcea0" : "#e08b8b";
      ctx.fillStyle = up ? "#1e6b45" : "#8a3e3e";
      ctx.beginPath();
      ctx.moveTo(x, yOf(bar[2]));
      ctx.lineTo(x, yOf(bar[3]));
      ctx.stroke();
      const y1 = yOf(bar[1]);
      const y2 = yOf(bar[4]);
      const topY = Math.min(y1, y2);
      const height = Math.max(1, Math.abs(y2 - y1));
      ctx.fillRect(x - Math.max(1, slot * 0.28), topY, Math.max(1.5, slot * 0.56), height);
    });
    drawLine(ctx, xOf, s20, "#d7b07a", yOf);
    drawLine(ctx, xOf, s50, "#9bb8e8", yOf);
    ctx.setLineDash([4, 4]);
    walls.forEach(([label, wall]) => {
      const y = yOf(wall);
      ctx.strokeStyle = label.startsWith("Call") ? "#7dcea0" : "#e08b8b";
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(w - right, y);
      ctx.stroke();
      ctx.fillStyle = ctx.strokeStyle;
      ctx.textAlign = "left";
      ctx.fillText(label + " " + money(wall), left + 8, y - 4);
    });
    ctx.restore();
    ctx.setLineDash([]);
    ctx.fillStyle = "#9aa3b2";
    ctx.textAlign = "left";
    ctx.fillText(bars[0][0], left, h - 8);
    ctx.textAlign = "right";
    ctx.fillText(bars[bars.length - 1][0], w - right, h - 8);
    const pick = hover != null && bars[hover] ? bars[hover] : bars[bars.length - 1];
    const suffix = state.period === "D" ? "" : " · 由日K聚合";
    setText("ohlcReadout", `${pick[0]}${suffix}  开 ${money(pick[1])}  高 ${money(pick[2])}  低 ${money(pick[3])}  收 ${money(pick[4])}`);
    if (hover != null && bars[hover]) {
      const x = xOf(hover);
      ctx.strokeStyle = "rgba(232,234,237,0.35)";
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, h - bottom);
      ctx.stroke();
    }
  } finally {
    drawing = false;
  }
}

function selectTicker(ticker) {
  const item = BY[ticker];
  if (!item) return;
  state.ticker = ticker;
  if (item.kind === "stock") state.lastStock = ticker;
  hover = null;
  render();
}
function setStep(step) {
  state.step = step;
  if (step === "market") state.open.market = true;
  else if (step === "sector") state.open.sector = true;
  else if (step === "stock") state.open.essentials = true;
  else if (step === "options") state.open.options = true;
  render();
  if (step === "sector") document.getElementById("search")?.focus();
  if (step === "stock") document.getElementById("chart")?.scrollIntoView({ block: "nearest" });
  if (step === "options") document.querySelector("[data-acc=options]")?.scrollIntoView({ block: "nearest" });
}
function onClick(event) {
  const target = event.target.closest("[data-act]");
  if (!target || target.disabled) return;
  const act = target.dataset.act;
  if (act === "ticker") selectTicker(target.dataset.ticker);
  else if (act === "step") setStep(target.dataset.step);
  else if (act === "mode") { state.listMode = target.dataset.mode; render(); }
  else if (act === "sector") {
    state.sector = target.dataset.sector;
    state.listMode = "stocks";
    state.step = "sector";
    state.tab = "sector";
    state.open.sector = true;
    state.drawerOpen = true;
    render();
  } else if (act === "clear-sector") { state.sector = "全部"; render(); }
  else if (act === "period") { state.period = target.dataset.period; hover = null; render(); }
  else if (act === "indi") { state.indi = target.dataset.indi; drawChart(); renderPeriods(); }
  else if (act === "tab") {
    if (state.drawerOpen && state.tab === target.dataset.tab) state.drawerOpen = false;
    else { state.tab = target.dataset.tab; state.drawerOpen = true; }
    document.body.classList.toggle("drawer-open", !!state.drawerOpen);
    syncPanels();
  }
  else if (act === "acc") {
    const name = target.dataset.acc;
    state.open[name] = !state.open[name];
    syncPanels();
  } else if (act === "star") {
    if (state.starred.has(state.ticker)) state.starred.delete(state.ticker);
    else state.starred.add(state.ticker);
    saveStars();
    render();
  }
}

function boot() {
  loadStars();
  const asked = new URLSearchParams(location.search).get("ticker");
  if (asked && BY[asked.toUpperCase()]) {
    state.ticker = asked.toUpperCase();
    if (BY[state.ticker].kind === "stock") state.lastStock = state.ticker;
  }
  document.body.addEventListener("click", onClick);
  const search = document.getElementById("search");
  if (search) search.addEventListener("input", (event) => { state.q = event.target.value; renderWatch(); });
  const jump = document.getElementById("jump");
  if (jump) jump.addEventListener("change", (event) => selectTicker(event.target.value));
  const collapse = document.getElementById("btnCollapse");
  if (collapse) collapse.addEventListener("click", () => { state.collapsed = !state.collapsed; render(); });
  const canvas = document.getElementById("chart");
  if (canvas) {
    canvas.addEventListener("mousemove", (event) => {
      if (!geom) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const i = Math.round((x - geom.left) / geom.slot - 0.5);
      const next = i >= 0 && i < geom.n ? i : null;
      if (next !== hover) { hover = next; drawChart(); }
    });
    canvas.addEventListener("mouseleave", () => { hover = null; drawChart(); });
  }
  const frame = document.querySelector(".chart-frame");
  if (frame && "ResizeObserver" in window) new ResizeObserver(() => drawChart()).observe(frame);
  render();
}
boot();
