"""
STEP 2 - FORENSIC ANALYTICS ENGINE  (every tool here was taught in FSAFA)

  Session 1-5  : ratios, DuPont, cash-flow quality, red-flag trends
  Session 7-8  : revenue / asset manipulation  -> Beneish M-Score (DSRI, AQI, SGI ...)
  Session 11-12: anomaly detection             -> Benford's Law (MAD / chi-square)
  Post mid-term: accrual earnings mgmt (AEM)   -> Modified Jones model, Sloan accruals
                 real earnings mgmt  (REM)     -> Roychowdhury abnormal CFO & discretionary exp.
  Credit overlay                               -> Altman Z'' (emerging-market version)

Outputs (data/):  metrics_year.csv, scores.csv, benford_digits.csv, validation.csv
"""
import re
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import os
DATA = Path(os.getenv("WAI_DATA", ROOT / "data"))

# ----------------------------------------------------------------------------- mapping
MAP = {
    "sales":  [("IS", "Total Revenue"), ("IS", "Operating Revenue")],
    "cogs":   [("IS", "Cost Of Revenue")],
    "sga":    [("IS", "Selling General And Administration")],
    "dep":    [("IS", "Depreciation And Amortization In Income Statement"), ("CF", "Depreciation And Amortization")],
    "ni":     [("IS", "Net Income")],
    "ebit":   [("IS", "EBIT")],
    "intexp": [("IS", "Interest Expense")],
    "recv":   [("BS", "Accounts Receivable")],
    "inv":    [("BS", "Inventory")],
    "ta":     [("BS", "Total Assets")],
    "ppe":    [("BS", "Net PPE")],
    "ca":     [("BS", "Current Assets")],
    "cl":     [("BS", "Current Liabilities")],
    "tl":     [("BS", "Total Liabilities Net Minority Interest")],
    "ltd":    [("BS", "Long Term Debt And Capital Lease Obligation")],
    "debt":   [("BS", "Total Debt")],
    "re":     [("BS", "Retained Earnings")],
    "equity": [("BS", "Stockholders Equity"), ("BS", "Common Stock Equity")],
    "cfo":    [("CF", "Operating Cash Flow")],
    "capex":  [("CF", "Capital Expenditure")],
}
FIN_SECTORS = {"Financial Services"}          # Beneish / Jones / Altman are not meaningful for banks, NBFCs, insurers
NON_AMOUNT = re.compile(r"EPS|Shares|Share Issued|Rate|Number|Tax Effect", re.I)


def wide(raw: pd.DataFrame) -> pd.DataFrame:
    """long -> one row per (ticker, fy) with standard variable names"""
    piv = raw.pivot_table(index=["ticker", "fy"], columns=["statement", "item"], values="value", aggfunc="first")
    out = pd.DataFrame(index=piv.index)
    for var, options in MAP.items():
        s = pd.Series(np.nan, index=piv.index)
        for key in options:
            if key in piv.columns:
                s = s.fillna(piv[key])
        out[var] = s
    return out.reset_index().sort_values(["ticker", "fy"])


def _div(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        r = a / b
    return r.replace([np.inf, -np.inf], np.nan)


def winsor(s, lo=0.02, hi=0.98):
    if s.notna().sum() < 5:
        return s
    return s.clip(s.quantile(lo), s.quantile(hi))


# ----------------------------------------------------------------------------- ratios + Beneish
def add_ratios(w: pd.DataFrame) -> pd.DataFrame:
    g = w.groupby("ticker")
    L = lambda c: g[c].shift(1)                       # value in t-1 (requires consecutive years)
    consecutive = (w["fy"] - g["fy"].shift(1)) == 1
    for c in ["sales", "cogs", "sga", "dep", "recv", "ta", "ppe", "ca", "cl", "ltd", "inv", "ni", "cfo"]:
        w[c + "_l"] = L(c).where(consecutive)

    # --- classic ratios (sessions 2-4) ------------------------------------------------
    w["gross_margin"] = _div(w.sales - w.cogs, w.sales)
    w["net_margin"] = _div(w.ni, w.sales)
    w["asset_turn"] = _div(w.sales, w.ta)
    w["equity_mult"] = _div(w.ta, w.equity)
    w["roe"] = _div(w.ni, w.equity)
    w["roce"] = _div(w.ebit, w.ta - w.cl)
    w["current_ratio"] = _div(w.ca, w.cl)
    w["de_ratio"] = _div(w.debt, w.equity)
    w["int_cover"] = _div(w.ebit, w.intexp.abs())
    w["dso"] = _div(w.recv, w.sales) * 365
    w["dio"] = _div(w.inv, w.cogs) * 365
    w["cfo_to_ni"] = _div(w.cfo, w.ni)

    # --- Beneish 8-variable M-Score (Beneish 1999) -----------------------------------
    w["DSRI"] = _div(_div(w.recv, w.sales), _div(w.recv_l, w.sales_l))
    w["GMI"] = _div(_div(w.sales_l - w.cogs_l, w.sales_l), _div(w.sales - w.cogs, w.sales))
    w["AQI"] = _div(1 - _div(w.ca + w.ppe, w.ta), 1 - _div(w.ca_l + w.ppe_l, w.ta_l))
    w["SGI"] = _div(w.sales, w.sales_l)
    w["DEPI"] = _div(_div(w.dep_l, w.dep_l + w.ppe_l), _div(w.dep, w.dep + w.ppe))
    w["SGAI"] = _div(_div(w.sga, w.sales), _div(w.sga_l, w.sales_l))
    w["LVGI"] = _div(_div(w.cl + w.ltd, w.ta), _div(w.cl_l + w.ltd_l, w.ta_l))
    w["TATA"] = _div(w.ni - w.cfo, w.ta)             # cash-flow version of total accruals / TA
    idx = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI"]
    comps = idx + ["TATA"]
    w["n_comp"] = w[comps].notna().sum(axis=1)
    f = w[idx].clip(0.2, 5).fillna(1.0)               # neutral value when a component is unavailable
    tata = w["TATA"].clip(-0.5, 0.5).fillna(0.0)
    w["MScore"] = (-4.84 + 0.920 * f.DSRI + 0.528 * f.GMI + 0.404 * f.AQI + 0.892 * f.SGI
                   + 0.115 * f.DEPI - 0.172 * f.SGAI + 4.679 * tata - 0.327 * f.LVGI)
    w.loc[w.n_comp < 6, "MScore"] = np.nan            # require >= 6 of 8 components
    w["fin"] = False
    return w


# ----------------------------------------------------------------------------- accruals (AEM) & REM
def _ols_resid(y, X):
    ok = y.notna() & X.notna().all(axis=1)
    res = pd.Series(np.nan, index=y.index)
    if ok.sum() < 12:
        return res
    yy, XX = winsor(y[ok]), X[ok].apply(winsor)
    XX = XX.assign(const=1.0) if False else XX     # (no intercept in Jones-type models: 1/A term carries it)
    beta, *_ = np.linalg.lstsq(XX.values, yy.values, rcond=None)
    res[ok] = yy.values - XX.values @ beta
    return res


def add_aem_rem(w: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional models, estimated year-by-year on the non-financial universe."""
    w["TA_scaled"] = _div(w.ni - w.cfo, w.ta_l)                       # total accruals / A(t-1)
    w["sloan"] = _div(w.ni - w.cfo, (w.ta + w.ta_l) / 2)              # Sloan (1996) accrual ratio
    w["DA"] = np.nan; w["abn_cfo"] = np.nan; w["abn_disx"] = np.nan
    for fy, idx in w[~w.fin].groupby("fy").groups.items():
        d = w.loc[idx]
        inv_a = _div(pd.Series(1.0, index=d.index), d.ta_l)
        dS, dAR = d.sales - d.sales_l, d.recv - d.recv_l
        # Modified Jones (Dechow-Sloan-Sweeney 1995):  TA/A = a1(1/A) + a2((dS-dAR)/A) + a3(PPE/A)
        X = pd.DataFrame({"inv_a": inv_a, "dsdar": _div(dS - dAR.fillna(0), d.ta_l), "ppe": _div(d.ppe, d.ta_l)})
        w.loc[idx, "DA"] = _ols_resid(d.TA_scaled, X)
        # Roychowdhury (2006) abnormal CFO:  CFO/A = a1(1/A) + b1(S/A) + b2(dS/A)
        X2 = pd.DataFrame({"inv_a": inv_a, "s": _div(d.sales, d.ta_l), "ds": _div(dS, d.ta_l)})
        w.loc[idx, "abn_cfo"] = _ols_resid(_div(d.cfo, d.ta_l), X2)
        # Abnormal discretionary expenses (SG&A proxy):  DISX/A = a1(1/A) + b1(S(t-1)/A)
        X3 = pd.DataFrame({"inv_a": inv_a, "s_l": _div(d.sales_l, d.ta_l)})
        w.loc[idx, "abn_disx"] = _ols_resid(_div(d.sga, d.ta_l), X3)
    w["REM"] = -w.abn_cfo - w.abn_disx      # high = lower-than-normal CFO and discretionary spend (income-increasing REM)
    return w


# ----------------------------------------------------------------------------- Altman Z'' (EM)
def add_altman(w):
    x1, x2 = _div(w.ca - w.cl, w.ta), _div(w.re, w.ta)
    x3, x4 = _div(w.ebit, w.ta), _div(w.equity, w.tl)
    w["Altman"] = 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    w["Altman_zone"] = pd.cut(w.Altman, [-np.inf, 4.15, 5.85, np.inf], labels=["Distress", "Grey", "Safe"])
    return w


# ----------------------------------------------------------------------------- Benford's law
BENF = np.log10(1 + 1 / np.arange(1, 10))


def first_digit(v):
    v = np.abs(np.asarray(v, float)); v = v[v >= 1]
    return (v // 10 ** np.floor(np.log10(v))).astype(int)


def benford_table(raw: pd.DataFrame):
    """Per company: observed first-digit frequencies, MAD and chi-square (Nigrini 2012)."""
    r = raw.dropna(subset=["value"]).copy()
    r = r[~r["item"].str.contains(NON_AMOUNT)]
    summ, digs = [], []
    for t, d in r.groupby("ticker"):
        d = d.drop_duplicates(subset=["fy", "value"])          # totals repeated across rows would bias counts
        dg = first_digit(d.value.values)
        n = len(dg)
        if n < 100:
            continue
        cnt = np.bincount(dg, minlength=10)[1:10]
        obs = cnt / n
        mad = np.mean(np.abs(obs - BENF))
        chi2 = float(((cnt - n * BENF) ** 2 / (n * BENF)).sum())   # 8 d.o.f.; 5% critical value = 15.51
        summ.append(dict(ticker=t, benford_n=n, benford_mad=mad, benford_chi2=chi2))
        digs += [dict(ticker=t, digit=i + 1, observed=obs[i], expected=BENF[i], count=int(cnt[i])) for i in range(9)]
    return pd.DataFrame(summ), pd.DataFrame(digs)


def mad_label(m):
    return ("Close conformity" if m <= 0.006 else "Acceptable" if m <= 0.012 else
            "Marginal" if m <= 0.015 else "Non-conformity")


# ----------------------------------------------------------------------------- composite risk score
def pct(s, invert=False):
    r = s.rank(pct=True) * 100
    return 100 - r if invert else r


def scale(x, lo, hi):
    return ((x - lo) / (hi - lo)).clip(0, 1) * 100


WEIGHTS = {"Beneish": 30, "Accruals": 20, "Cash divergence": 15, "REM": 10, "Benford": 10, "Distress": 15}


def composite(df: pd.DataFrame) -> pd.DataFrame:
    """df: one row per ticker for a single fiscal year (with benford columns merged)."""
    c = pd.DataFrame(index=df.index)
    c["Beneish"] = scale(df.MScore, -3.0, -1.0)                       # -1.78 threshold sits at ~61
    c["Accruals"] = pd.concat([pct(df.sloan), pct(df.DA)], axis=1).mean(axis=1)
    c["Cash divergence"] = pd.concat([pct(df.cfo_cum_ni, invert=True)], axis=1).mean(axis=1)
    c["REM"] = pct(df.REM)
    c["Benford"] = scale(df.benford_mad, 0.006, 0.015)
    c["Distress"] = scale(-df.Altman, -7, -3)                          # Altman 5.85=safe edge -> ~25, 4.15 -> ~60
    for k in c: c[k] = c[k].where(~df.fin)       # banks / NBFCs / insurers: NOT scored (tools assume an operating business)
    w = pd.Series(WEIGHTS)
    num = (c * w).sum(axis=1, skipna=True)
    den = c.notna().mul(w).sum(axis=1)
    df = df.copy()
    df["coverage"] = den                                   # % of model weight backed by data
    ok = (den >= 60) & (c["Beneish"].notna() | (c["Accruals"].notna() & c["REM"].notna()))
    df["score"] = (num / den).where(ok)                    # need core earnings-quality inputs, else "insufficient data"
    for k in c: df["s_" + k] = c[k]
    df["tier"] = pd.cut(df.score, [-1, 35, 50, 65, 101], labels=["Low", "Moderate", "Elevated", "High"])
    blocks = ["s_" + k for k in WEIGHTS]
    df["red_n"] = (df[blocks] >= 60).sum(axis=1).where(df.score.notna())          # independent tests in the red zone
    df["red_of"] = df[blocks].notna().sum(axis=1).where(df.score.notna())
    return df


# ----------------------------------------------------------------------------- AI anomaly detector + priority index
ANOM_FEATS = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA", "sloan", "DA", "REM", "lev", "roa", "cfo_cum_ni"]
ANOM_NAMES = {"DSRI": "receivables vs sales", "GMI": "gross margin", "AQI": "asset quality", "SGI": "sales growth", "DEPI": "depreciation rate", "SGAI": "overheads",
              "LVGI": "leverage change", "TATA": "total accruals", "sloan": "accruals", "DA": "discretionary accruals", "REM": "real earnings mgmt",
              "lev": "leverage (debt/assets)", "roa": "return on assets", "cfo_cum_ni": "cash conversion"}


def add_anomaly(df: pd.DataFrame) -> pd.DataFrame:
    """Unsupervised Isolation Forest on the standardised forensic feature vector of every scored firm-year.
    It needs no hand-set weights, so it is an independent second opinion on the rule-based score.
    Also reports the two features that make each firm unusual (robust z-scores)."""
    df = df.copy()
    df["lev"] = (df.debt / df.ta).replace([np.inf, -np.inf], np.nan); df["roa"] = (df.ni / df.ta).replace([np.inf, -np.inf], np.nan)
    X = df[ANOM_FEATS].replace([np.inf, -np.inf], np.nan)
    ok = df.score.notna() & ~df.fin
    Xo = X[ok]
    lo, hi = Xo.quantile(.01), Xo.quantile(.99)
    Xo = Xo.clip(lo, hi, axis=1)
    med = Xo.median(); mad = ((Xo - med).abs().median() * 1.4826).replace(0, np.nan)
    Z = ((Xo - med) / mad).clip(-8, 8).fillna(0.0)
    try:
        from sklearn.ensemble import IsolationForest
        model = IsolationForest(n_estimators=400, random_state=7, contamination="auto").fit(Z)
        raw = -model.score_samples(Z)
    except Exception:                                                   # fallback if scikit-learn is unavailable
        raw = Z.abs().mean(axis=1).values
    df["anomaly_raw"] = np.nan; df.loc[ok, "anomaly_raw"] = raw
    df["anomaly_pct"] = df.groupby("fy").anomaly_raw.rank(pct=True) * 100
    drv = pd.Series("", index=df.index)
    for i, row in Z.iterrows():
        top = row.abs().sort_values(ascending=False).head(2)
        drv[i] = ", ".join(f"{ANOM_NAMES[k]} {'high' if row[k] > 0 else 'low'}" for k in top.index if abs(row[k]) >= 1.5)
    df["anomaly_drivers"] = drv
    corr = (df.red_n / df.red_of).fillna(0)
    df["fpi"] = (0.5 * df.score + 25 * corr + 0.25 * df.anomaly_pct).where(df.score.notna())   # Forensic Priority Index (default weights)
    return df


def auc(pos, neg):
    """Mann-Whitney AUC: probability a random watchlist firm scores above a random Nifty firm."""
    pos, neg = pos.dropna().values, neg.dropna().values
    if len(pos) < 3 or len(neg) < 3: return np.nan
    return float(np.mean([(p > neg).mean() + 0.5 * (p == neg).mean() for p in pos]))


# ----------------------------------------------------------------------------- pipeline
def run():
    raw = pd.read_csv(DATA / "raw_long.csv")
    uni = pd.read_csv(DATA / "universe.csv")
    w = wide(raw)
    w = add_ratios(w)
    w = w.merge(uni[["ticker", "name", "sector", "cohort", "currency"]], on="ticker", how="left")
    w["fin"] = w.sector.isin(FIN_SECTORS)
    for c in ["MScore", "Altman"]: w.loc[w.fin, c] = np.nan
    w = add_aem_rem(w)
    w = add_altman(w); w.loc[w.fin, ["Altman", "Altman_zone"]] = np.nan
    cum_cfo = w.groupby("ticker").cfo.transform(lambda s: s.rolling(3, min_periods=2).sum())
    cum_ni = w.groupby("ticker").ni.transform(lambda s: s.rolling(3, min_periods=2).sum())
    w["cfo_cum_ni"] = _div(cum_cfo, cum_ni).where(cum_ni > 0)       # cash conversion undefined when cumulative profit <= 0
    w["MScore_flag"] = np.where(w.MScore > -1.78, "Likely manipulator", np.where(w.MScore > -2.22, "Watch", "Unlikely"))

    bsum, bdig = benford_table(raw)
    w = w.merge(bsum, on="ticker", how="left")
    w["benford_label"] = w.benford_mad.apply(lambda m: mad_label(m) if pd.notna(m) else np.nan)

    scored = pd.concat([composite(g) for _, g in w.groupby("fy")])
    scored = add_anomaly(scored)
    keep = scored.drop(columns=[c for c in scored.columns if c.endswith("_l")])
    keep.to_csv(DATA / "metrics_year.csv", index=False)
    bdig.to_csv(DATA / "benford_digits.csv", index=False)

    latest = keep.sort_values("fy").groupby("ticker").tail(1)
    latest.to_csv(DATA / "scores.csv", index=False)

    # ---- validation: does the screen rank the watchlist higher than Nifty 50? --------
    rows = []
    nf, wl = latest[latest.cohort == "Nifty 50"], latest[latest.cohort == "Watchlist"]
    for col, lab in [("score", "Composite score"), ("MScore", "Beneish M"), ("sloan", "Sloan accruals"), ("DA", "Jones DA"),
                     ("REM", "REM"), ("benford_mad", "Benford MAD"), ("s_Distress", "Distress (Altman)"),
                     ("anomaly_pct", "AI anomaly detector (Isolation Forest)"), ("fpi", "Forensic Priority Index (new)")]:
        rows.append(dict(metric=lab, AUC=auc(wl[col], nf[col]), watch_median=wl[col].median(), nifty_median=nf[col].median(),
                         n_watch=int(wl[col].notna().sum()), n_nifty=int(nf[col].notna().sum())))
    # composite without the distress overlay (so the test isn't driven only by obvious bankruptcy-type stress)
    pure = latest.copy(); pure["s_Distress"] = np.nan
    num = (pure[[f"s_{k}" for k in WEIGHTS]] * pd.Series({f"s_{k}": v for k, v in WEIGHTS.items()})).sum(axis=1)
    den = pure[[f"s_{k}" for k in WEIGHTS]].notna().mul(pd.Series({f"s_{k}": v for k, v in WEIGHTS.items()})).sum(axis=1)
    pure["score_nodistress"] = (num / den).where(den >= 25)
    rows.append(dict(metric="Composite excl. distress", AUC=auc(pure[pure.cohort == "Watchlist"].score_nodistress,
                                                              pure[pure.cohort == "Nifty 50"].score_nodistress),
                     watch_median=pure[pure.cohort == "Watchlist"].score_nodistress.median(),
                     nifty_median=pure[pure.cohort == "Nifty 50"].score_nodistress.median(),
                     n_watch=int(pure[pure.cohort == "Watchlist"].score_nodistress.notna().sum()),
                     n_nifty=int(pure[pure.cohort == "Nifty 50"].score_nodistress.notna().sum())))
    pd.DataFrame(rows).to_csv(DATA / "validation.csv", index=False)
    return keep, latest


if __name__ == "__main__":
    keep, latest = run()
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(latest.sort_values("score", ascending=False)[["ticker", "cohort", "fy", "MScore", "sloan", "DA", "REM", "Altman", "benford_mad", "score", "tier"]].round(3).to_string())
    print(pd.read_csv(DATA / "validation.csv").round(3).to_string())
