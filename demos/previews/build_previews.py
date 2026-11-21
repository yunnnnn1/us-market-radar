#!/usr/bin/env python3
"""Build standalone layout previews from the committed terminal snapshot.

Reads production artifacts only. Writes HTML under demos/previews/.
Does not touch generators, dashboards, or live processes.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TEMPLATES = OUT / "templates"
HTML_PATH = ROOT / "futu_pro_terminal.html"
AI_PATH = ROOT / "data_cache" / "latest_ai_predictions.json"
PANEL_PATHS = [
    ROOT / "data_cache" / "ml_panel_5y.parquet",
    ROOT / "data_cache" / "ml_extended_panel.parquet",
]

MACRO_ORDER = [
    "QQQ", "SPY", "DIA", "IWM", "SMH", "SOXX", "SOXL", "IGV",
    "TLT", "GLD", "VIXY", "KORU", "SQQQ", "SOXS",
]
INDEX_TICKERS = ["QQQ", "SPY", "DIA", "SMH", "VIXY", "GLD"]
BAR_KEEP = 420

QUOTE_FIELDS = [
    "ticker", "name", "sub", "cat", "last", "pct_change", "active_price", "ext_pct",
    "session_tag", "ma50", "ema20", "bias", "atr", "rsi", "vol_ratio",
    "fib_low", "fib_high", "pit_status", "dist_to_pit", "signal",
    "is_pit", "is_stop", "is_take_profit",
    "optimal_limit", "limit_note", "entry_stop_loss",
    "intraday_status_text", "intraday_reason",
    "vwap", "rsi_5m", "rvol_5m", "rs_20d", "struct_stop",
]
OPTION_FIELDS = [
    "has_options", "options_exp", "call_vol", "put_vol", "call_dollar", "put_dollar",
    "pcr", "dollar_pcr", "pcr_sentiment", "top_call_info", "top_put_info",
    "call_wall", "put_wall", "iv_atm", "exp_move_pct", "exp_low", "exp_high", "exp_move_str",
]
AI_FIELDS = [
    "rank", "short_rank", "sector_cn", "sector_rating", "sector_pf",
    "calibrated_win_rate_pct", "calibrated_short_win_rate_pct",
    "predicted_win_rate_pct", "model_raw_prob_pct", "base_raw_prob_pct",
    "model_raw_short_prob_pct",
    "action", "short_action",
    "target_profit_price", "target_profit_pct", "stop_loss_price", "stop_loss_pct",
    "short_target_profit_price", "short_target_profit_pct",
    "short_stop_loss_price", "short_stop_loss_pct",
    "pcr", "dollar_pcr", "pcr_sentiment", "put_wall", "call_wall",
    "s1", "s2", "sl", "r1", "r2", "scenario_script", "four_h_div", "macro_temp",
]


def grab_const(html: str, name: str):
    token = f"const {name} = "
    i = html.find(token)
    if i < 0:
        raise SystemExit(f"missing {name} in futu_pro_terminal.html")
    i += len(token)
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(html)):
        c = html[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return json.loads(html[i : j + 1])
    raise SystemExit(f"unclosed {name}")


def rnd(value, nd=4):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return round(value, nd)
        return value
    return value


def copy_fields(src: dict, fields: list[str], nd=4) -> dict:
    out = {}
    for key in fields:
        if key not in src:
            continue
        value = src.get(key)
        if isinstance(value, float):
            out[key] = rnd(value, nd)
        else:
            out[key] = value
    return out


def options_of(src: dict) -> dict | None:
    if not src.get("has_options") and src.get("pcr") is None:
        return None
    data = copy_fields(src, OPTION_FIELDS, nd=4)
    if not data.get("has_options") and data.get("pcr") is None:
        return None
    return data


def load_bars(tickers: set[str]) -> tuple[dict, dict, str | None, str | None]:
    grouped: dict[str, list] = {}
    source: dict[str, str] = {}
    for path in PANEL_PATHS:
        table = pq.read_table(
            path, columns=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
        )
        dates = table.column("Date").to_pylist()
        symbols = table.column("Ticker").to_pylist()
        opens = table.column("Open").to_pylist()
        highs = table.column("High").to_pylist()
        lows = table.column("Low").to_pylist()
        closes = table.column("Close").to_pylist()
        volumes = table.column("Volume").to_pylist()
        for i, symbol in enumerate(symbols):
            if symbol not in tickers or symbol in source:
                continue
            close = closes[i]
            if close is None:
                continue
            day = dates[i]
            day_s = day.strftime("%Y-%m-%d") if isinstance(day, datetime) else str(day)[:10]
            grouped.setdefault(symbol, []).append(
                [
                    day_s,
                    rnd(opens[i]),
                    rnd(highs[i]),
                    rnd(lows[i]),
                    rnd(close),
                    int(volumes[i] or 0),
                ]
            )
        for symbol, rows in grouped.items():
            if rows and symbol not in source:
                source[symbol] = path.name
    bars = {}
    all_days = []
    for symbol, rows in grouped.items():
        rows.sort(key=lambda row: row[0])
        # Drop duplicate dates, keeping the later copy.
        dedup = {}
        for row in rows:
            dedup[row[0]] = row
        rows = [dedup[key] for key in sorted(dedup)]
        if len(rows) > BAR_KEEP:
            rows = rows[-BAR_KEEP:]
        if rows:
            bars[symbol] = rows
            all_days.append(rows[0][0])
            all_days.append(rows[-1][0])
    start = min(all_days) if all_days else None
    end = max(all_days) if all_days else None
    return bars, source, start, end


def commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def build_snapshot() -> dict:
    html = HTML_PATH.read_text(encoding="utf-8")
    stocks = grab_const(html, "STOCKS_DATA")
    macros = grab_const(html, "MACRO_DATA")
    ai = json.loads(AI_PATH.read_text(encoding="utf-8"))
    by_ai = ai.get("by_ticker") or {}
    tickers = {s["ticker"] for s in stocks} | set(macros)
    bars, bar_source, panel_start, panel_end = load_bars(tickers)

    def make_item(src: dict, ticker: str, kind: str) -> dict:
        item = copy_fields(src, QUOTE_FIELDS)
        item["ticker"] = ticker
        item["kind"] = kind
        item["name"] = src.get("name") or ticker
        pred = by_ai.get(ticker)
        if pred:
            item["ai"] = copy_fields(pred, AI_FIELDS)
            item["sector_cn"] = pred.get("sector_cn") or ""
        else:
            item["ai"] = None
            item["sector_cn"] = ""
        item["options"] = options_of(src)
        series = bars.get(ticker) or []
        if series:
            item["panel_last"] = series[-1][0]
            item["panel_close"] = series[-1][4]
            item["panel_file"] = bar_source.get(ticker) or ""
        else:
            item["panel_last"] = None
            item["panel_close"] = None
            item["panel_file"] = ""
        return item

    items = [make_item(s, s["ticker"], "stock") for s in stocks]
    macro_items = [make_item(macros[t], t, "etf") for t in macros]
    rank = {t: i for i, t in enumerate(MACRO_ORDER)}
    macro_items.sort(key=lambda it: (rank.get(it["ticker"], 99), it["ticker"]))
    items.extend(macro_items)

    sectors = []
    for row in ai.get("table2") or []:
        sectors.append(
            {
                "name": row.get("sector_name_cn"),
                "tickers_count": row.get("tickers_count"),
                "samples": row.get("oos_total_signals"),
                "high_conviction_signals": row.get("high_conviction_signals"),
                "avg_return": row.get("avg_realized_return_pct"),
                "win": row.get("high_conviction_win_rate_pct"),
                "pf": row.get("profit_factor"),
                "rating": row.get("alpha_rating"),
            }
        )

    weather = ai.get("macro_weather") or {}
    breadth = weather.get("cross_industry_breadth") or ai.get("cross_industry_breadth") or {}
    defensive = weather.get("defensive_flight") or ai.get("defensive_flight") or {}
    kpi = ai.get("kpi") or {}
    sessions = sorted({it.get("session_tag") or "" for it in items if it.get("session_tag")})

    indices = []
    by_item = {it["ticker"]: it for it in items}
    for ticker in INDEX_TICKERS:
        it = by_item.get(ticker)
        if not it:
            continue
        indices.append(
            {
                "ticker": ticker,
                "name": it.get("name"),
                "last": it.get("last"),
                "pct_change": it.get("pct_change"),
                "active_price": it.get("active_price"),
                "ext_pct": it.get("ext_pct"),
                "bias": it.get("bias"),
                "signal": it.get("signal"),
            }
        )

    return {
        "meta": {
            "commit": commit_sha(),
            "sync_time": kpi.get("sync_time") or "",
            "session_tags": sessions,
            "panel_source": "data_cache/ml_panel_5y.parquet + data_cache/ml_extended_panel.parquet",
            "quote_source": "futu_pro_terminal.html 内嵌快照",
            "ai_source": "data_cache/latest_ai_predictions.json",
            "panel_start": panel_start,
            "panel_end": panel_end,
            "stock_count": sum(1 for it in items if it["kind"] == "stock"),
            "etf_count": sum(1 for it in items if it["kind"] == "etf"),
            "bar_count": sum(len(v) for v in bars.values()),
            "table1": [
                {
                    "label": row.get("threshold_label"),
                    "triggers": row.get("trigger_count"),
                    "hit_pct": row.get("win_rate_pct"),
                    "avg_return": row.get("avg_realized_return_pct"),
                    "pf": row.get("profit_factor"),
                }
                for row in (ai.get("table1") or [])
            ],
        },
        "market": {
            "weather_status": weather.get("status") or "",
            "weather_desc": weather.get("desc") or "",
            "weather_date": weather.get("latest_date") or "",
            "defensive_text": defensive.get("banner_text") or defensive.get("alert_text") or "",
            "defensive_score": defensive.get("flight_score"),
            "breadth_tag": breadth.get("status_tag") or "",
            "breadth_text": breadth.get("banner_text") or "",
            "trad_mean": breadth.get("trad_mean_chg"),
            "tech_mean": breadth.get("tech_mean_chg"),
            "trad_components": breadth.get("trad_components") or {},
            "tech_components": breadth.get("tech_components") or {},
            "kpi_win": kpi.get("high_conviction_win_rate"),
            "kpi_pf": kpi.get("profit_factor"),
            "top_sector": kpi.get("top_sector") or "",
            "indices": indices,
        },
        "sectors": sectors,
        "items": items,
        "bars": bars,
    }


def assemble(template_name: str, css: str, js: str, data_json: str) -> str:
    html = (TEMPLATES / template_name).read_text(encoding="utf-8")
    page_js = js.replace("__SNAPSHOT__", data_json, 1)
    if "__SNAPSHOT__" in page_js:
        raise SystemExit("snapshot token left in js")
    html = html.replace("__SHARED_CSS__", css).replace("__SHARED_JS__", page_js)
    return html


def main() -> None:
    snapshot = build_snapshot()
    data_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    css = (OUT / "shared.css").read_text(encoding="utf-8")
    js = (OUT / "shared.js").read_text(encoding="utf-8")
    text = assemble("b.html", css, js, data_json)
    (OUT / "terminal.html").write_text(text, encoding="utf-8")
    print(f"wrote terminal.html {len(text)//1024} KB")
    from render_pages import write_pages
    slim = dict(snapshot)
    slim.pop("bars", None)
    write_pages(slim, OUT)
    for stale in ("a-chart-first.html", "b-balanced.html", "c-reading.html"):
        path = OUT / stale
        if path.exists():
            path.unlink()
            print("removed", stale)
    lly = next(it for it in snapshot["items"] if it["ticker"] == "LLY")
    print(
        "LLY last", lly["last"],
        "panel", lly["panel_last"], lly["panel_close"],
        "bars", len(snapshot["bars"].get("LLY") or []),
        "sync", snapshot["meta"]["sync_time"],
        "panel", snapshot["meta"]["panel_start"], snapshot["meta"]["panel_end"],
    )
    missing = [it["ticker"] for it in snapshot["items"] if not snapshot["bars"].get(it["ticker"])]
    print("missing bars", missing)


if __name__ == "__main__":
    main()
