#!/usr/bin/env python3
"""
股票自動儀表板 v2 — GitHub Actions 版
追蹤：MU / SNDK / MRVL / GLW / ALAB
每天台灣時間 08:00 由 GitHub 雲端自動執行
輸出 index.html → 透過 GitHub Pages 用瀏覽器隨時查看
"""

import yfinance as yf
from datetime import datetime, timezone, timedelta

# ── 設定 ──────────────────────────────────────────────────────────
TICKERS = ["MU", "SNDK", "MRVL", "GLW", "ALAB"]   # ← 想加減股票在這裡改

TZ_TAIWAN = timezone(timedelta(hours=8))

ACCENT = {
    "MU":   "#3B82F6",
    "SNDK": "#8B5CF6",
    "MRVL": "#10B981",
    "GLW":  "#F59E0B",
    "ALAB": "#EC4899",
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

        try:
            hist       = stk.history(period="14d")
            avg_vol_7d = int(hist["Volume"].tail(7).mean()) if len(hist) >= 7 else 0
            closes_7d  = [round(c, 2) for c in hist["Close"].tail(7).tolist()]
        except Exception:
            avg_vol_7d = 0
            closes_7d  = []

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
            today_vol=today_vol, avg_vol_7d=avg_vol_7d, avg_vol_3m=avg_vol_3m,
            eps_ttm=info.get("trailingEps"),
            eps_fwd=info.get("forwardEps"),
            pe_ttm=info.get("trailingPE"),
            pe_fwd=info.get("forwardPE"),
            mkt_cap=info.get("marketCap"),
            beta=info.get("beta"),
            hi52=info.get("fiftyTwoWeekHigh"),
            lo52=info.get("fiftyTwoWeekLow"),
            closes_7d=closes_7d,
            earn_date=earn_date, earn_est=earn_est, earn_rep=earn_rep,
        )
    except Exception as e:
        print(f"    ✗ {ticker} 失敗: {e}", flush=True)
        return dict(ticker=ticker, error=str(e), name=ticker,
                    price=None, chg_pct=None, today_vol=0,
                    avg_vol_7d=0, avg_vol_3m=0, eps_ttm=None,
                    eps_fwd=None, pe_ttm=None, mkt_cap=None,
                    hi52=None, lo52=None, closes_7d=[])


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


# ── 靜態分析內容（可自行編輯更新）───────────────────────────────
ANALYSES = {
    "MU": {
        "headline": "Micron — HBM超週期主力，缺貨延續至2027年後",
        "body": "公司預期記憶體與儲存供給短缺將延續至2027年之後，較先前展望進一步延伸。自身擴產（愛達荷2027年中、新加坡HBM封裝廠同期）在此期間屬營收增項而非稀釋定價權，因產業整體仍處缺貨狀態。南韓三星/海力士的新一輪超級擴產計畫要到5年後才會顯著影響供需，不影響2026-2027窗口。",
        "tags": [("HBM缺貨延續至27年後","bull"),("MU自身擴產=營收增項","bull"),("分析師目標價快速上修","bull"),("集體訴訟尾部風險","bear"),("需留意法說後波動","watch")],
    },
    "SNDK": {
        "headline": "SanDisk — 長約保護結構，波動度全場最高",
        "body": "Bernstein分析師估算公司已鎖定約每GB $0.29的底價保護，約60%預期出貨量受長期協議保障，即使極端價格崩跌情境獲利仍優於舊合約結構。但作為純NAND生產商缺乏DRAM/HBM業務緩衝，近期已出現多次單日±10%以上的劇烈波動，OpenAI融資疑慮曾引發連續下跌。",
        "tags": [("長約鎖定底價保護","bull"),("Bernstein目標$3,000","bull"),("波動度全場最高","bear"),("純NAND無業務緩衝","bear"),("8/13下季法說","watch")],
    },
    "MRVL": {
        "headline": "Marvell — Jensen Huang公開背書，估值透支疑慮",
        "body": "COMPUTEX期間獲Nvidia CEO公開稱為「下一個兆元公司」，帶動單日暴漲。FY27/28營收指引成長率全場最高，資料中心互連業務加速。但現價已超越多數分析師均值目標，加上財務長近期出售自家股票，代表這個利多需要後續合約與訂單實際兌現來驗證。",
        "tags": [("Nvidia公開背書","bull"),("FY28營收目標$150億","bull"),("現價超越均值目標","bear"),("財務長近期售股","bear"),("8/20下季法說","watch")],
    },
    "GLW": {
        "headline": "Corning — 7/2單日重挫13.6%，估值消化開始",
        "body": "GLW近日從高點回落逾13%，主因追蹤本益比達106倍、遠期本益比80倍，加上Q4/Q3/Q1連續三季營收不如預期，估值缺乏容錯空間。CHRO等高管在下跌前密集出售股票，三個月內共出售逾5,400萬美元且零買進，機構信心指標轉弱。GlassBridge技術鞏固長期材料供應地位，但不會加速CPO量產時程；Nvidia認股權證與Amazon/Meta長約仍是結構性支撐。",
        "tags": [("Nvidia認股權證","bull"),("Amazon/Meta長約","bull"),("7/2單日跌13.6%","bear"),("本益比106倍偏高","bear"),("高管密集售股","bear"),("7/28下季法說觀察","watch")],
    },
    "ALAB": {
        "headline": "Astera Labs — 拋物線式上漲，估值透支最明顯",
        "body": "納入Nasdaq-100指數帶動被動資金強制買入，股價年初至今上漲逾250%。2026年營收成長預期達81%，PCIe 6.0轉換與AI連接需求提供真實基本面支撐。但即使UBS大幅調高目標價至$400，仍維持中立評級，反映連分析師都認為現階段估值已充分反映樂觀情境，是七檔中「故事跑贏數字」風險最高的一檔。",
        "tags": [("納入Nasdaq-100指數","bull"),("2026營收成長81%","bull"),("UBS目標$400但仍中立","bear"),("估值透支風險最高","bear"),("8/11下季法說","watch")],
    },
}

TAG_STYLE = {
    "bull":  ("#052E16", "#4ADE80", "#166534"),
    "bear":  ("#2D0A0A", "#F87171", "#7F1D1D"),
    "watch": ("#1C1402", "#FCD34D", "#854D0E"),
}


# ── HTML 生成 ─────────────────────────────────────────────────────
def build_html(stocks, ts):
    cards = ""
    for s in stocks:
        tk  = s["ticker"]
        clr = ACCENT.get(tk, "#6B7280")
        if s.get("error"):
            cards += f'<div class="card" style="border-left:3px solid {clr}"><div class="tk" style="color:{clr}">{tk}</div><p class="err">❌ 資料抓取失敗</p></div>'
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
        diff = (tv/a7 - 1)*100 if a7 else 0
        dc   = "#4ADE80" if diff >= 0 else "#F87171"
        r7   = min(tv/a7,  3)/3*100
        vols += f"""
<div class="vr">
  <div class="vhd">
    <span class="vtk" style="color:{clr}">{tk}</span>
    <span class="vv">{fmt_vol(tv)}</span>
    <span class="vd" style="color:{dc}">{'▲' if diff>=0 else '▼'}{abs(diff):.0f}% vs 7日均</span>
  </div>
  <div class="bg">
    <div class="bl"><span class="bm">今日</span><div class="bt"><div class="bf" style="width:{r7:.0f}%;background:{clr}"></div></div><span class="bv">{fmt_vol(tv)}</span></div>
    <div class="bl"><span class="bm">7日均</span><div class="bt"><div class="bf" style="width:{min(a7/max(tv,1),1)*100:.0f}%;background:{clr}88"></div></div><span class="bv">{fmt_vol(a7)}</span></div>
    <div class="bl"><span class="bm">3月均</span><div class="bt"><div class="bf" style="width:{min(a3m/max(tv,1),1)*100:.0f}%;background:{clr}44"></div></div><span class="bv">{fmt_vol(a3m)}</span></div>
  </div>
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

    # 分析卡片
    analysis_cards = ""
    for tk in TICKERS:
        a = ANALYSES.get(tk)
        if not a: continue
        clr = ACCENT.get(tk, "#6B7280")
        tags_html = "".join(
            f'<span class="tag" style="background:{TAG_STYLE[c][0]};color:{TAG_STYLE[c][1]};border:1px solid {TAG_STYLE[c][2]}">{t}</span>'
            for t, c in a["tags"]
        )
        analysis_cards += f"""
<div class="acard" style="border-left:3px solid {clr}">
  <div class="ahd"><span class="atk" style="color:{clr}">{tk}</span><span class="atitle">{a["headline"]}</span></div>
  <p class="abody">{a["body"]}</p>
  <div class="atags">{tags_html}</div>
</div>"""

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
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}
@media(max-width:1000px){{.cards{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:680px){{.cards{{grid-template-columns:1fr}}}}
.card{{background:#161B22;border:1px solid #21262D;border-radius:10px;padding:13px 14px}}
.ctop{{display:flex;justify-content:space-between;align-items:start;margin-bottom:5px}}
.tk{{font-size:13px;font-weight:700}}.nm{{font-size:9px;color:#484F58;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pr{{font-size:18px;font-weight:700}}.chg{{font-size:10px;font-weight:600}}
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
.tw{{background:#161B22;border:1px solid #21262D;border-radius:10px;overflow:hidden;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:10px}}
thead tr{{background:#0D1117}}
th{{padding:8px 10px;text-align:left;color:#484F58;font-weight:500;white-space:nowrap}}
td{{padding:7px 10px;border-top:1px solid #1A1A2A;white-space:nowrap}}
tr:nth-child(even) td{{background:#0D1117}}
.acards{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
@media(max-width:800px){{.acards{{grid-template-columns:1fr}}}}
.acard{{background:#161B22;border:1px solid #21262D;border-radius:10px;padding:13px 15px}}
.ahd{{display:flex;align-items:center;gap:7px;margin-bottom:8px}}
.atk{{font-size:12px;font-weight:700}}.atitle{{font-size:11px;font-weight:600;color:#E6EDF3}}
.abody{{font-size:11px;color:#8B949E;line-height:1.7;margin-bottom:10px}}
.atags{{display:flex;flex-wrap:wrap;gap:5px}}
.tag{{font-size:9px;padding:2px 8px;border-radius:10px;font-weight:500}}
.ft{{margin-top:14px;font-size:9px;color:#30363D;text-align:right}}
</style></head><body>

<div class="hdr">
  <h1>📊 持股監控</h1>
  <span class="sub">MU · SNDK · MRVL · GLW · ALAB</span>
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

<div class="sec">最新分析整理</div>
<div class="acards">{analysis_cards}</div>

<p class="ft">資料來源：Yahoo Finance (yfinance) · GitHub Actions 自動執行 · 分析內容需人工定期更新 · 非投資建議</p>
</body></html>"""


def main():
    now_tw = datetime.now(TZ_TAIWAN)
    ts     = now_tw.strftime("%Y-%m-%d %H:%M")
    print(f"\n===== 股票儀表板 {ts} =====", flush=True)

    stocks = [fetch(tk) for tk in TICKERS]
    html   = build_html(stocks, ts)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ 已輸出 index.html", flush=True)

if __name__ == "__main__":
    main()
