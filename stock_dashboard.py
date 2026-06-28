#!/usr/bin/env python3
"""
股票自動儀表板 — GitHub Actions 版
每天台灣時間 08:00 由 GitHub 雲端自動執行
輸出 index.html → 透過 GitHub Pages 用瀏覽器隨時查看

依賴：pip install yfinance  (已在 requirements.txt 指定)
"""

import yfinance as yf
import os
import sys
from datetime import datetime, timezone, timedelta

# ── 設定 ──────────────────────────────────────────────────────────
TICKERS = ["MU", "SNDK", "MRVL"]   # ← 想加股票直接在這裡加

TZ_TAIWAN = timezone(timedelta(hours=8))

ACCENT = {
    "MU":   "#3B82F6",
    "SNDK": "#8B5CF6",
    "MRVL": "#10B981",
}

# ── 格式化工具 ────────────────────────────────────────────────────
def fmt_price(v):
    return f"${v:,.2f}" if v else "—"

def fmt_vol(v):
    if not v or v == 0: return "—"
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000:     return f"{v/1_000:.1f}K"
    return str(int(v))

def fmt_cap(v):
    if not v: return "—"
    if v >= 1_000_000_000_000: return f"${v/1_000_000_000_000:.2f}兆"
    if v >= 1_000_000_000:     return f"${v/1_000_000_000:.1f}B"
    return f"${v/1_000_000:.0f}M"

def fmt_pct(v):
    if v is None: return "—"
    arrow = "▲" if v >= 0 else "▼"
    return f"{arrow} {abs(v):.2f}%"

def pct_clr(v):
    if v is None: return "#6B7280"
    return "#4ADE80" if v >= 0 else "#F87171"


# ── 資料抓取 ──────────────────────────────────────────────────────
def fetch(ticker: str) -> dict:
    print(f"  抓取 {ticker}...", flush=True)
    try:
        stk  = yf.Ticker(ticker)
        info = stk.info

        price   = info.get("currentPrice") or info.get("regularMarketPrice")
        prev    = info.get("previousClose") or info.get("regularMarketPreviousClose")
        chg_pct = ((price - prev) / prev * 100) if (price and prev) else None

        today_vol  = info.get("regularMarketVolume") or info.get("volume") or 0
        avg_vol_3m = info.get("averageVolume") or 0
        avg_10d    = info.get("averageDailyVolume10Day") or 0

        # 7 日歷史
        try:
            hist       = stk.history(period="14d")
            avg_vol_7d = int(hist["Volume"].tail(7).mean()) if len(hist) >= 7 else 0
            closes_7d  = [round(c, 2) for c in hist["Close"].tail(7).tolist()]
            dates_7d   = [d.strftime("%m/%d") for d in hist.index.tail(7)]
        except Exception:
            avg_vol_7d = 0
            closes_7d  = []
            dates_7d   = []

        # 法說 EPS
        try:
            ed = stk.earnings_dates
            if ed is not None and not ed.empty:
                earn_date = ed.index[0].strftime("%Y-%m-%d")
                earn_est  = ed.iloc[0].get("EPS Estimate")
                earn_rep  = ed.iloc[0].get("Reported EPS")
            else:
                earn_date = earn_est = earn_rep = None
        except Exception:
            earn_date = earn_est = earn_rep = None

        print(f"    ✓ {ticker}: ${price} | vol {fmt_vol(today_vol)}", flush=True)
        return dict(
            ticker=ticker, error=None,
            name=info.get("longName", ticker),
            price=price, prev=prev,
            open=info.get("open") or info.get("regularMarketOpen"),
            day_high=info.get("dayHigh") or info.get("regularMarketDayHigh"),
            day_low=info.get("dayLow")  or info.get("regularMarketDayLow"),
            chg_pct=chg_pct,
            today_vol=today_vol, avg_vol_7d=avg_vol_7d,
            avg_vol_3m=avg_vol_3m, avg_10d=avg_10d,
            eps_ttm=info.get("trailingEps"),
            eps_fwd=info.get("forwardEps"),
            pe_ttm=info.get("trailingPE"),
            pe_fwd=info.get("forwardPE"),
            mkt_cap=info.get("marketCap"),
            beta=info.get("beta"),
            hi52=info.get("fiftyTwoWeekHigh"),
            lo52=info.get("fiftyTwoWeekLow"),
            closes_7d=closes_7d, dates_7d=dates_7d,
            earn_date=earn_date, earn_est=earn_est, earn_rep=earn_rep,
        )
    except Exception as e:
        print(f"    ✗ {ticker} 失敗: {e}", flush=True)
        return dict(ticker=ticker, error=str(e), name=ticker,
                    price=None, chg_pct=None, today_vol=0,
                    avg_vol_7d=0, avg_vol_3m=0, eps_ttm=None,
                    eps_fwd=None, pe_ttm=None, mkt_cap=None,
                    hi52=None, lo52=None, closes_7d=[], dates_7d=[])


# ── 迷你折線 SVG ──────────────────────────────────────────────────
def sparkline(closes, w=88, h=30):
    if len(closes) < 2: return ""
    mn, mx = min(closes), max(closes)
    rng = mx - mn or 1
    pts = []
    for i, c in enumerate(closes):
        x = i / (len(closes)-1) * w
        y = h - ((c - mn) / rng * h)
        pts.append(f"{x:.1f},{y:.1f}")
    clr = "#4ADE80" if closes[-1] >= closes[0] else "#F87171"
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none">'
            f'<polyline points="{" ".join(pts)}" stroke="{clr}" '
            f'stroke-width="1.8" fill="none"/></svg>')


# ── HTML 生成 ─────────────────────────────────────────────────────
def build_html(stocks, ts):
    # 個股卡片
    cards = ""
    for s in stocks:
        tk  = s["ticker"]
        clr = ACCENT.get(tk, "#6B7280")
        if s.get("error"):
            cards += f'<div class="card" style="border-left:3px solid {clr}"><div class="tk" style="color:{clr}">{tk}</div><p class="err">❌ {s["error"]}</p></div>'
            continue

        hi = s["hi52"] or 0; lo = s["lo52"] or 0; p = s["price"] or 0
        w52 = max(0, min(100, (p-lo)/(hi-lo)*100)) if hi > lo else 50

        e_row = ""
        if s.get("earn_date"):
            rep = f"${s['earn_rep']:.2f}" if s.get("earn_rep") else "—"
            est = f"${s['earn_est']:.2f}" if s.get("earn_est") else "—"
            e_row = f'<div class="mr"><span class="ml">最近法說</span><span class="mv">{s["earn_date"]}｜實{rep}/估{est}</span></div>'

        cards += f"""
<div class="card" style="border-left:3px solid {clr}">
  <div class="ctop">
    <div><div class="tk" style="color:{clr}">{tk}</div><div class="nm">{s["name"]}</div></div>
    <div style="text-align:right"><div class="pr">{fmt_price(s["price"])}</div>
    <div class="chg" style="color:{pct_clr(s['chg_pct'])}">{fmt_pct(s['chg_pct'])}</div></div>
  </div>
  <div class="sp">{sparkline(s["closes_7d"])}</div>
  <div class="w52w"><span class="wl">{fmt_price(lo)}</span>
    <div class="wt"><div class="wf" style="width:{w52:.0f}%;background:{clr}"></div></div>
    <span class="wl">{fmt_price(hi)}</span></div>
  <div class="wlb">52 週區間</div>
  <div class="meta">
    <div class="mr"><span class="ml">日高/低</span><span class="mv">{fmt_price(s["day_high"])} / {fmt_price(s["day_low"])}</span></div>
    <div class="mr"><span class="ml">市值</span><span class="mv">{fmt_cap(s["mkt_cap"])}</span></div>
    <div class="mr"><span class="ml">Beta</span><span class="mv">{f'{s["beta"]:.2f}' if s.get("beta") else "—"}</span></div>
  </div>
  <div class="eps" style="border-color:{clr}33">
    <div class="et" style="color:{clr}">EPS</div>
    <div class="eg">
      <div><div class="el">TTM</div><div class="ev">{fmt_price(s["eps_ttm"])}</div></div>
      <div><div class="el">預估</div><div class="ev">{fmt_price(s["eps_fwd"])}</div></div>
      <div><div class="el">P/E</div><div class="ev">{f'{s["pe_ttm"]:.1f}x' if s.get("pe_ttm") else "—"}</div></div>
      <div><div class="el">今日量</div><div class="ev">{fmt_vol(s["today_vol"])}</div></div>
    </div>
    {e_row}
  </div>
</div>"""

    # 成交量條
    vols = ""
    for s in stocks:
        if s.get("error"): continue
        tk  = s["ticker"]; clr = ACCENT.get(tk, "#6B7280")
        tv  = s["today_vol"] or 0
        a7  = s["avg_vol_7d"] or 1
        a3m = s["avg_vol_3m"] or 1
        diff = (tv/a7 - 1)*100
        dc   = "#4ADE80" if diff >= 0 else "#F87171"
        r7   = min(tv/a7,   3)/3*100
        r3m  = min(tv/a3m,  3)/3*100
        vols += f"""
<div class="vr">
  <div class="vhd">
    <span class="vtk" style="color:{clr}">{tk}</span>
    <span class="vv">{fmt_vol(tv)}</span>
    <span class="vd" style="color:{dc}">{'▲' if diff>=0 else '▼'}{abs(diff):.0f}% vs 7日均</span>
  </div>
  <div class="bg"><div class="bl"><span class="bm">今日</span><div class="bt"><div class="bf" style="width:{r7:.0f}%;background:{clr}"></div></div><span class="bv">{fmt_vol(tv)}</span></div>
  <div class="bl"><span class="bm">7日均</span><div class="bt"><div class="bf" style="width:{min(a7/max(tv,1),1)*100:.0f}%;background:{clr}88"></div></div><span class="bv">{fmt_vol(a7)}</span></div>
  <div class="bl"><span class="bm">3月均</span><div class="bt"><div class="bf" style="width:{min(a3m/max(tv,1),1)*100:.0f}%;background:{clr}44"></div></div><span class="bv">{fmt_vol(a3m)}</span></div></div>
</div>"""

    # 彙整表格
    trows = ""
    for s in stocks:
        if s.get("error"): continue
        tk  = s["ticker"]; clr = ACCENT.get(tk, "#6B7280")
        trows += f"""<tr>
<td style="color:{clr};font-weight:700">{tk}</td>
<td>{fmt_price(s["price"])}</td>
<td style="color:{pct_clr(s['chg_pct'])}">{fmt_pct(s['chg_pct'])}</td>
<td>{fmt_price(s["eps_ttm"])}</td>
<td>{fmt_price(s["eps_fwd"])}</td>
<td>{f'{s["pe_ttm"]:.1f}x' if s.get("pe_ttm") else "—"}</td>
<td>{fmt_vol(s["today_vol"])}</td>
<td>{fmt_vol(s["avg_vol_7d"])}</td>
<td>{fmt_cap(s["mkt_cap"])}</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>持股監控 · {ts}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'IBM Plex Mono',Menlo,'Courier New',monospace;background:#0D1117;color:#E6EDF3;padding:18px 14px;min-height:100vh}}
.hdr{{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding-bottom:12px;border-bottom:1px solid #21262D;margin-bottom:16px}}
h1{{font-size:16px;font-weight:700}}
.sub{{font-size:10px;color:#484F58;background:#161B22;border:1px solid #30363D;padding:2px 8px;border-radius:4px}}
.ts{{margin-left:auto;font-size:10px;color:#3FB950}}
.sec{{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#484F58;margin:16px 0 8px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
@media(max-width:680px){{.cards{{grid-template-columns:1fr}}}}
.card{{background:#161B22;border:1px solid #21262D;border-radius:10px;padding:13px 14px}}
.ctop{{display:flex;justify-content:space-between;align-items:start;margin-bottom:5px}}
.tk{{font-size:13px;font-weight:700}}.nm{{font-size:9px;color:#484F58;margin-top:1px}}
.pr{{font-size:19px;font-weight:700}}.chg{{font-size:10px;font-weight:600}}
.sp{{margin:5px 0 6px}}.err{{font-size:11px;color:#F87171;margin-top:8px}}
.w52w{{display:flex;align-items:center;gap:5px;margin-bottom:2px}}
.wl{{font-size:8px;color:#484F58;white-space:nowrap}}
.wt{{flex:1;height:4px;background:#21262D;border-radius:2px;overflow:hidden}}
.wf{{height:100%;border-radius:2px}}.wlb{{font-size:8px;color:#484F58;margin-bottom:8px}}
.meta{{margin-bottom:9px}}
.mr{{display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #21262D22}}
.ml{{font-size:9px;color:#484F58}}.mv{{font-size:9px;color:#E2E8F0;font-weight:500}}
.eps{{background:#0D1117;border:1px solid;border-radius:7px;padding:9px 11px}}
.et{{font-size:9px;font-weight:700;margin-bottom:6px}}
.eg{{display:grid;grid-template-columns:1fr 1fr;gap:5px 0}}
.el{{font-size:8px;color:#484F58}}.ev{{font-size:10px;font-weight:600}}
.vsec{{background:#161B22;border:1px solid #21262D;border-radius:10px;padding:13px 14px}}
.vr{{margin-bottom:12px}}.vr:last-child{{margin-bottom:0}}
.vhd{{display:flex;align-items:center;gap:8px;margin-bottom:5px}}
.vtk{{font-size:11px;font-weight:700;min-width:44px}}
.vv{{font-size:10px;color:#E6EDF3;font-weight:600}}.vd{{font-size:9px}}
.bg{{display:flex;flex-direction:column;gap:3px}}
.bl{{display:flex;align-items:center;gap:5px}}
.bm{{font-size:8px;color:#484F58;width:30px;flex-shrink:0}}
.bt{{flex:1;height:5px;background:#21262D;border-radius:3px;overflow:hidden}}
.bf{{height:100%;border-radius:3px}}.bv{{font-size:8px;color:#8B949E;width:36px;text-align:right}}
.tw{{background:#161B22;border:1px solid #21262D;border-radius:10px;overflow:hidden}}
table{{width:100%;border-collapse:collapse;font-size:10px}}
thead tr{{background:#0D1117}}
th{{padding:8px 10px;text-align:left;color:#484F58;font-weight:500;white-space:nowrap}}
td{{padding:7px 10px;border-top:1px solid #1A1A2A}}
tr:nth-child(even) td{{background:#0D1117}}
.ft{{margin-top:14px;font-size:9px;color:#30363D;text-align:right}}
</style></head><body>

<div class="hdr">
  <h1>📊 持股監控</h1>
  <span class="sub">MU · SNDK · MRVL</span>
  <span class="ts">● {ts}（台灣時間）· 每 5 分鐘自動重整</span>
</div>

<div class="sec">即時報價 &amp; 個股摘要</div>
<div class="cards">{cards}</div>

<div class="sec">成交量比較 · 今日 vs 7日均 vs 3月均</div>
<div class="vsec">{vols}</div>

<div class="sec">指標彙整</div>
<div class="tw"><table>
<thead><tr>
<th>股票</th><th>股價</th><th>漲跌</th>
<th>EPS TTM</th><th>預估 EPS</th><th>P/E</th>
<th>今日量</th><th>7日均量</th><th>市值</th>
</tr></thead>
<tbody>{trows}</tbody>
</table></div>

<p class="ft">資料來源：Yahoo Finance (yfinance) · GitHub Actions 自動執行 · 非投資建議</p>
</body></html>"""


# ── 主程式 ────────────────────────────────────────────────────────
def main():
    now_tw = datetime.now(TZ_TAIWAN)
    ts     = now_tw.strftime("%Y-%m-%d %H:%M")
    print(f"\n===== 股票儀表板 {ts} =====", flush=True)

    stocks = [fetch(tk) for tk in TICKERS]
    html   = build_html(stocks, ts)

    # GitHub Actions 環境：輸出到 index.html（repo 根目錄）
    out = "index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ 已輸出：{out}", flush=True)

if __name__ == "__main__":
    main()
