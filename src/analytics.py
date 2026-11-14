"""
DiD / event-study engine and 10-year Screener panel (difference-in-differences, triple DiD, panel data).

Panel  : built from data/screener_long.csv (Screener.in public pages, Rs crore, 2009-2026)
DiD    : (Treated_post - Treated_pre) - (Control_post - Control_pre)
         + regression  y = a + b1*Post + b2*Treat + b3*Post*Treat  with firm-clustered standard errors
         + placebo test on pre-event years (parallel-trends check)
Triple : DiD(high group) - DiD(low group)
"""
import numpy as np, pandas as pd

# outcome label -> (column, unit)   unit "pp" = percentage points (x100), "x" = multiple
OUT = {"Net margin (profit / sales)": ("net_margin", "pp"),
       "Sales growth": ("sales_growth", "pp"),
       "CFO / net income": ("cfo_ni", "x"),
       "Accruals / lagged assets": ("accruals", "pp"),
       "Debt / assets": ("debt_assets", "pp"),
       "Operating cash flow / sales": ("cfo_margin", "pp"),
       "Asset turnover": ("asset_turn", "x"),
       "Return on assets": ("roa", "pp")}


def build_panel(screener_long: pd.DataFrame, uni: pd.DataFrame) -> pd.DataFrame:
    p = screener_long.pivot_table(index=["ticker", "fy"], columns="item", values="value", aggfunc="first").reset_index()
    p = p.sort_values(["ticker", "fy"]).reset_index(drop=True)
    g = p.groupby("ticker")
    consec = (p.fy - g.fy.shift(1)) == 1
    p["ta_l"] = g.ta.shift(1).where(consec); p["sales_l"] = g.sales.shift(1).where(consec)
    div = lambda a, b: (a / b).replace([np.inf, -np.inf], np.nan)
    p["net_margin"] = div(p.ni, p.sales)
    p["cfo_margin"] = div(p.cfo, p.sales)
    p["sales_growth"] = div(p.sales, p.sales_l) - 1
    p["cfo_ni"] = div(p.cfo, p.ni).where(p.ni > 0)
    p["accruals"] = div(p.ni - p.cfo, p.ta_l)
    p["debt_assets"] = div(p.debt, p.ta)
    p["asset_turn"] = div(p.sales, p.ta)
    p["roa"] = div(p.ni, p.ta)
    for c in [v[0] for v in OUT.values()]:                         # winsorise 5/95 so one odd year cannot drive a mean
        lo, hi = p[c].quantile(.05), p[c].quantile(.95); p[c] = p[c].clip(lo, hi)
    p = p.merge(uni[["ticker", "name", "sector", "cohort"]], on="ticker", how="left")
    p["fin"] = p.sector.eq("Financial Services")
    return p


def ols_cluster(y, X, groups):
    """OLS with cluster-robust (by firm) standard errors, small-sample corrected."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    xtx_inv = np.linalg.pinv(X.T @ X); b = xtx_inv @ X.T @ y; e = y - X @ b
    meat = np.zeros((X.shape[1], X.shape[1])); ug = np.unique(groups)
    for g in ug:
        idx = groups == g; s = X[idx].T @ e[idx]; meat += np.outer(s, s)
    n, k, G = X.shape[0], X.shape[1], len(ug)
    c = G / max(G - 1, 1) * (n - 1) / max(n - k, 1)
    V = c * xtx_inv @ meat @ xtx_inv
    return b, np.sqrt(np.clip(np.diag(V), 0, None))


def _window(panel, tickers_t, tickers_c, col, event, pre, post):
    d = panel[panel.ticker.isin(list(tickers_t) + list(tickers_c))].copy()
    d["treat"] = d.ticker.isin(tickers_t).astype(int)
    d = d[(d.fy >= event - pre) & (d.fy <= event + post - 1)].dropna(subset=[col])
    d["post"] = (d.fy >= event).astype(int)
    ok = d.groupby("ticker").post.nunique(); d = d[d.ticker.isin(ok[ok == 2].index)]   # need >=1 pre and >=1 post year
    return d


def _did_means(d, col):
    m = d.groupby(["treat", "post"])[col].mean().unstack()
    if not {0, 1} <= set(m.index) or not {0, 1} <= set(m.columns): return None
    return (m.loc[1, 1] - m.loc[1, 0]) - (m.loc[0, 1] - m.loc[0, 0]), m


def did_estimate(panel, treated, control, col, event, pre=4, post=3):
    d = _window(panel, treated, control, col, event, pre, post)
    res = _did_means(d, col) if len(d) else None
    if res is None: return None
    est, m = res
    X = np.column_stack([np.ones(len(d)), d.post, d.treat, d.post * d.treat])
    b, se = ols_cluster(d[col].values, X, d.ticker.values)
    by_year = d.groupby(["fy", "treat"])[col].mean().unstack()
    out = dict(est=est, reg=b[3], se=se[3], means=m, by_year=by_year,
               n_t=int(d[d.treat == 1].ticker.nunique()), n_c=int(d[d.treat == 0].ticker.nunique()), data=d,
               d_t=m.loc[1, 1] - m.loc[1, 0], d_c=m.loc[0, 1] - m.loc[0, 0], placebo=None)
    if pre >= 2:                                                  # placebo: pretend the event happened earlier, use pre-years only
        fake = event - max(1, pre // 2)
        dp = _window(panel, treated, control, col, fake, pre - max(1, pre // 2), max(1, pre // 2))
        dp = dp[dp.fy < event]
        if len(dp): 
            r = _did_means(dp, col); out["placebo"] = None if r is None else r[0]
    return out


def triple_did(panel, treated, control, col, event, pre, post, split):
    """split: 'size' (assets) or 'leverage' (debt/assets), measured as the pre-event average, high = above median."""
    d = _window(panel, treated, control, col, event, pre, post)
    key = {"size": "ta", "leverage": "debt_assets"}[split]
    base = panel[(panel.fy < event) & (panel.fy >= event - pre) & panel.ticker.isin(d.ticker.unique())].groupby("ticker")[key].mean()
    hi = set(base[base >= base.median()].index)
    out = {}
    for name, grp in [("High", hi), ("Low", set(base.index) - hi)]:
        r = _did_means(d[d.ticker.isin(grp)], col)
        out[name] = None if r is None else dict(est=r[0], n_t=int(d[d.ticker.isin(grp) & (d.treat == 1)].ticker.nunique()),
                                                n_c=int(d[d.ticker.isin(grp) & (d.treat == 0)].ticker.nunique()))
    if out["High"] and out["Low"]: out["DDD"] = out["High"]["est"] - out["Low"]["est"]
    return out


def window_stats(panel, ticker, fy0, fy1):
    """Mean accruals ratio, CFO/NI and sales CAGR for one firm in a window, vs the non-financial universe median."""
    w = panel[(panel.fy >= fy0) & (panel.fy <= fy1)]
    f = w[w.ticker == ticker]; u = w[~w.fin & (w.ticker != ticker)]
    cagr = lambda d: (d.sales.iloc[-1] / d.sales.iloc[0]) ** (1 / max(len(d) - 1, 1)) - 1 if len(d) > 1 and d.sales.iloc[0] > 0 else np.nan
    return dict(acc=f.accruals.mean(), acc_u=u.groupby("fy").accruals.median().mean(), cfo_ni=f.cfo_ni.mean(),
                cfo_ni_u=u.groupby("fy").cfo_ni.median().mean(), cagr=cagr(f.sort_values("fy")))


FLAGS = {"High accruals (top 20% of firms that year)": "accruals", "Weak cash conversion (CFO/NI below 0.6)": "cash"}


def flag_backtest(panel, flag="accruals", outcome="roa", span=3, fy_min=2012, fy_max=2025):
    """Forensic back-test, DiD style: after a firm-year is red-flagged, does its outcome change differently
    from unflagged firm-years?  Event-time curves (change vs the flag year) + year-demeaned regression with
    firm-clustered SE for horizons 1 and 2.  Financial firms excluded."""
    p = panel[~panel.fin].sort_values(["ticker", "fy"]).copy()
    if flag == "accruals":
        q = p.groupby("fy").accruals.transform(lambda s: s.quantile(.8))
        p["flag"] = (p.accruals >= q) & p.accruals.notna(); ok = p.accruals.notna()
    else:
        p["flag"] = (p.ni > 0) & (p.cfo_ni < 0.6); ok = p.cfo_ni.notna()
    y = p.pivot(index="ticker", columns="fy", values=outcome)
    rows = []
    for r in p[ok & (p.fy >= fy_min) & (p.fy <= fy_max)].itertuples():
        y0 = y.at[r.ticker, r.fy] if r.fy in y.columns else np.nan
        if pd.isna(y0): continue
        for k in range(-span, span + 1):
            yk = y.at[r.ticker, r.fy + k] if (r.fy + k) in y.columns else np.nan
            if pd.notna(yk): rows.append((r.ticker, r.fy, bool(r.flag), k, yk - y0))
    d = pd.DataFrame(rows, columns=["ticker", "fy", "flag", "k", "delta"])
    if d.empty: return None
    curves = d.groupby(["k", "flag"]).delta.agg(["mean", "count"]).reset_index()
    stats = {}
    for h in (1, 2):
        e = d[d.k == h].copy()
        if e.flag.sum() < 5 or (~e.flag).sum() < 5: continue
        e["yd"] = e.delta - e.groupby("fy").delta.transform("mean")                  # year fixed effects
        e["fd"] = e.flag.astype(float) - e.groupby("fy").flag.transform(lambda s: s.astype(float).mean())
        b, se = ols_cluster(e.yd.values, e[["fd"]].values, e.ticker.values)
        stats[h] = dict(beta=b[0], se=se[0], n_flag=int(e.flag.sum()), n_all=len(e),
                        m_flag=e[e.flag].delta.mean(), m_un=e[~e.flag].delta.mean(), firms=int(e[e.flag].ticker.nunique()))
    return dict(curves=curves, stats=stats)
