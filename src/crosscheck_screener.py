"""
ONLINE CROSS-CHECK: Yahoo Finance vs Screener.in public company pages (no Excel, no login).
Polite use: one request / 2 s, run once, results cached in data/screener_long.csv.
Outputs: data/screener_long.csv, xcheck_levels.csv, xcheck_ratios.csv, xcheck_firms.csv
"""
import io, re, sys, time
from pathlib import Path
from urllib.parse import quote
import numpy as np, pandas as pd, requests
from lxml import html

ROOT = Path(__file__).resolve().parents[1]; D = ROOT / "data"
HDR = {"User-Agent": "Mozilla/5.0 (academic practice project)"}
ROWS = {"profit-loss": {"Sales": "sales", "Revenue": "sales", "Net Profit": "ni", "Depreciation": "dep", "Interest": "intexp"},
        "balance-sheet": {"Total Assets": "ta", "Borrowings": "debt"},
        "cash-flow": {"Cash from Operating Activity": "cfo"}}


def table(tree, sid):
    sec = tree.xpath(f'//section[@id="{sid}"]//table')
    if not sec: return None
    df = pd.read_html(io.StringIO(html.tostring(sec[0]).decode()))[0]
    df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.replace(r"[\s\+]+$", "", regex=True).str.replace(r"\s{2,}.*$", "", regex=True)
    return df.set_index(df.columns[0])


def fetch(sym):
    for path in ("consolidated/", ""):
        r = requests.get(f"https://www.screener.in/company/{quote(sym)}/{path}", headers=HDR, timeout=25)
        if r.status_code != 200: continue
        tree = html.fromstring(r.text); out = []
        for sid, m in ROWS.items():
            df = table(tree, sid)
            if df is None: continue
            for lab, key in m.items():
                if lab in df.index:
                    for col, v in df.loc[lab].items():
                        mm = re.match(r"Mar (\d{4})", str(col))
                        if mm:
                            v = pd.to_numeric(str(v).replace(",", ""), errors="coerce")
                            out.append(dict(item=key, fy=int(mm.group(1)), value=v, basis="consolidated" if path else "standalone"))
        if out: return out
    return []


def main():
    uni = pd.read_csv(D / "universe.csv"); rows = []
    for i, t in enumerate(uni.ticker, 1):
        sym = t.replace(".NS", ""); got = fetch(sym)
        print(f"[{i}/{len(uni)}] {sym:14s} {len(got):3d} values {got[0]['basis'] if got else 'NONE'}", flush=True)
        rows += [dict(ticker=t, **g) for g in got]; time.sleep(2)
    pd.DataFrame(rows).to_csv(D / "screener_long.csv", index=False)


def compare():
    s = pd.read_csv(D / "screener_long.csv"); y = pd.read_csv(D / "raw_long.csv"); uni = pd.read_csv(D / "universe.csv")
    ymap = {"sales": ("IS", "Total Revenue"), "ni": ("IS", "Net Income"), "cfo": ("CF", "Operating Cash Flow"), "ta": ("BS", "Total Assets")}
    S = s.pivot_table(index=["ticker", "fy"], columns="item", values="value", aggfunc="first") * 1e7        # crore -> INR
    Y = pd.DataFrame({k: y[(y.statement == st) & (y["item"] == it)].set_index(["ticker", "fy"]).value for k, (st, it) in ymap.items()})
    J = Y.join(S, lsuffix="_y", rsuffix="_s", how="inner")
    inr = set(uni[uni.currency == "INR"].ticker)
    lev = []
    for k in ymap:
        d = J[[f"{k}_y", f"{k}_s"]].dropna().reset_index(); d = d[d.ticker.isin(inr) & (d.fy >= 2024)]
        g = (d[f"{k}_y"] / d[f"{k}_s"] - 1).abs()
        lev.append(dict(item={"sales": "Sales", "ni": "Net income", "cfo": "Operating cash flow", "ta": "Total assets"}[k], n=len(d),
                        within_2pct=round((g <= .02).mean() * 100), within_10pct=round((g <= .10).mean() * 100), median_gap_pct=round(g.median() * 100, 1)))
    pd.DataFrame(lev).to_csv(D / "xcheck_levels.csv", index=False)

    def ratios(df, a, b):
        df = df.reset_index().sort_values(["ticker", "fy"]); g = df.groupby("ticker")
        out = pd.DataFrame({"ticker": df.ticker, "fy": df.fy})
        out["SGI"] = df[f"sales_{a}"] / g[f"sales_{a}"].shift(1)
        out["Accruals/TA"] = (df[f"ni_{a}"] - df[f"cfo_{a}"]) / g[f"ta_{a}"].shift(1)
        out["CFO/NI"] = (df[f"cfo_{a}"] / df[f"ni_{a}"]).where(df[f"ni_{a}"] > 0)
        out["Net margin"] = df[f"ni_{a}"] / df[f"sales_{a}"]
        out["Asset turnover"] = df[f"sales_{a}"] / df[f"ta_{a}"]
        return out.replace([np.inf, -np.inf], np.nan)
    full = Y.join(S, lsuffix="_y", rsuffix="_s", how="outer")
    ry, rs = ratios(full, "y", "s"), ratios(full, "s", "s")           # note: second call recomputed below
    # proper per-source ratios
    fy_ = full[[c for c in full if c.endswith("_y")]]; fs_ = full[[c for c in full if c.endswith("_s")]]
    def mk(f, suf):
        f = f.copy(); f.columns = [c[:-2] + "_x" for c in f.columns]; return ratios(f.rename(columns=lambda c: c.replace("_x", f"_{suf}")), suf, suf)
    ry, rs = mk(fy_, "y"), mk(fs_, "s")
    m = ry.merge(rs, on=["ticker", "fy"], suffixes=("_y", "_s"))
    nonfin = set(uni[uni.sector != "Financial Services"].ticker)
    m = m[m.ticker.isin(nonfin) & (m.fy == 2026)]
    out = []
    for c in ["SGI", "Accruals/TA", "CFO/NI", "Net margin", "Asset turnover"]:
        t = m[[f"{c}_y", f"{c}_s"]].dropna()
        out.append(dict(ratio=c, n=len(t), spearman=round(t.iloc[:, 0].corr(t.iloc[:, 1], method="spearman"), 2),
                        median_abs_diff=round((t.iloc[:, 0] - t.iloc[:, 1]).abs().median(), 3)))
    pd.DataFrame(out).to_csv(D / "xcheck_ratios.csv", index=False)
    m.merge(uni[["ticker", "name", "cohort"]], on="ticker").to_csv(D / "xcheck_firms.csv", index=False)
    print(pd.read_csv(D / "xcheck_levels.csv").to_string(index=False)); print(pd.read_csv(D / "xcheck_ratios.csv").to_string(index=False))


if __name__ == "__main__":
    if "--compare-only" not in sys.argv: main()
    compare()
