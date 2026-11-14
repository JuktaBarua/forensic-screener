"""
FORENSIC EARNINGS-QUALITY SCREENER  -  dashboard for a forensic / fraud analyst
Run:  .venv/bin/streamlit run app.py
"""
import sys, json, subprocess
from pathlib import Path
import numpy as np, pandas as pd, plotly.graph_objects as go, plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "src"))
import memo as M
from forensic_engine import WEIGHTS, BENF, mad_label

st.set_page_config(page_title="Forensic Earnings-Quality Screener", layout="wide", page_icon="🔍")

# ---- palette: one blue ramp for ordinal tiers, two hues for cohort, ink greys for text ----------------------
TIER_COL = {"Low": "#c6dbef", "Moderate": "#6baed6", "Elevated": "#2171b5", "High": "#08306b"}
COH_COL = {"Nifty 50": "#2a6fdb", "Watchlist": "#d9730d"}
INK, MUTED, GRID = "#1f2937", "#6b7280", "#e5e7eb"
TIERS = ["Low", "Moderate", "Elevated", "High"]


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(color=INK, size=12), legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


@st.cache_data
def load(stamp):
    m = pd.read_csv(DATA / "metrics_year.csv")
    return m, pd.read_csv(DATA / "benford_digits.csv"), pd.read_csv(DATA / "validation.csv")


def stamp():
    f = DATA / "last_refresh.txt"
    return f.read_text() if f.exists() else "never"


# ------------------------------------------------------------------------------------------ sidebar
st.sidebar.title("🔍 Filters")
if not str(ROOT).startswith("/mount") and st.sidebar.button("⟳ Refresh live data (Yahoo + NSE)", help="Re-downloads statements and recomputes every score (~3 min)"):
    with st.spinner("Downloading statements and recomputing scores..."):
        for s in ["src/fetch_data.py", "src/forensic_engine.py"]:
            r = subprocess.run([sys.executable, str(ROOT / s)], capture_output=True, text=True)
            if r.returncode: st.sidebar.error(r.stderr[-400:]); break
    st.cache_data.clear(); st.rerun()
st.sidebar.caption(f"Data last refreshed: {stamp()} (hosted copy: refresh runs locally)" if str(ROOT).startswith("/mount") else f"Data last refreshed: {stamp()}")

mall, bdig, valid = load(stamp())
mall = mall.copy()
years = sorted(mall[mall.score.notna() | mall.fin].fy.unique(), reverse=True)
fy = st.sidebar.selectbox("Fiscal year (ending March)", years, index=0)
cohorts = st.sidebar.multiselect("Cohort", ["Nifty 50", "Watchlist"], default=["Nifty 50", "Watchlist"])
sectors = sorted(mall.sector.dropna().unique())
sec_sel = st.sidebar.multiselect("Sector", sectors, default=[])
tier_sel = st.sidebar.multiselect("Risk tier", TIERS, default=TIERS)

with st.sidebar.expander("⚖️ Adjust model weights (what-if)"):
    st.caption("Re-weights the composite live. Weights are re-normalised over available components.")
    W = {k: st.slider(k, 0, 50, v, 5) for k, v in WEIGHTS.items()}

# recompute composite with user weights
sc = pd.DataFrame({k: mall["s_" + k] for k in WEIGHTS})
w = pd.Series(W)
den = sc.notna().mul(w).sum(axis=1)
mall["score_w"] = np.where(mall.score.notna() & (den > 0), (sc * w).sum(axis=1, skipna=True) / den.replace(0, np.nan), np.nan)
mall["tier_w"] = pd.cut(mall.score_w, [-1, 35, 50, 65, 101], labels=TIERS)

yr = mall[mall.fy == fy].copy()
view = yr[yr.cohort.isin(cohorts)]
if sec_sel: view = view[view.sector.isin(sec_sel)]
scored = view[view.score_w.notna()]
scored_tier = scored[scored.tier_w.isin(tier_sel)]
peers = yr[~yr.fin]

st.title("Forensic Earnings-Quality Screener")
st.caption("Screening tool for forensic / fraud analysts: Beneish M, accrual & real earnings management, Benford, Altman. "
           "A high score is a reason to investigate, **not** evidence of fraud.")

t1, t2, t3, t4, t5 = st.tabs(["📊 Universe screener", "🏢 Company deep-dive", "⚖️ Peer comparison", "🤖 AI analyst memo", "📘 Method & validation"])

# ------------------------------------------------------------------------------------------ TAB 1
with t1:
    c = st.columns(5)
    c[0].metric("Companies in view", len(view))
    c[1].metric("Scored", len(scored), help="Banks/NBFCs/insurers and firms with insufficient data are not scored")
    c[2].metric("High + Elevated", int(scored.tier_w.isin(["High", "Elevated"]).sum()))
    c[3].metric("Median score", f"{scored.score_w.median():.0f}" if len(scored) else "–")
    c[4].metric("Beneish > -1.78", int((view.MScore > -1.78).sum()))

    n = st.slider("Show top N by risk score", 5, max(6, len(scored_tier)), min(20, max(6, len(scored_tier))))
    top = scored_tier.sort_values("score_w", ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(x=top.score_w, y=top.ticker.str.replace(".NS", ""), orientation="h",
                           marker_color=[TIER_COL[str(t)] for t in top.tier_w],
                           marker_line=dict(color=[COH_COL[x] for x in top.cohort], width=2),
                           customdata=np.c_[top.name, top.tier_w, top.cohort, top.MScore.round(2)],
                           hovertemplate="<b>%{customdata[0]}</b><br>Score %{x:.0f} (%{customdata[1]})<br>%{customdata[2]} · Beneish %{customdata[3]}<extra></extra>"))
    fig.update_layout(title="Composite forensic risk score (bar fill = tier, outline = cohort: blue Nifty 50 / orange Watchlist)",
                      xaxis_title="Risk score (0–100)")
    st.plotly_chart(style(fig, max(320, 22 * len(top) + 80)), width="stretch")

    a, b = st.columns(2)
    sc_df = scored.dropna(subset=["MScore", "sloan"])
    f2 = px.scatter(sc_df, x="MScore", y="sloan", color="cohort", color_discrete_map=COH_COL, hover_name="name",
                    hover_data={"score_w": ":.0f", "cohort": False}, labels={"MScore": "Beneish M-score", "sloan": "Sloan accrual ratio"})
    f2.add_vline(x=-1.78, line_dash="dash", line_color=MUTED, annotation_text="manipulator −1.78")
    f2.add_hline(y=0.1, line_dash="dot", line_color=MUTED)
    f2.update_traces(marker=dict(size=10, line=dict(color="white", width=1.5)))
    f2.update_layout(title="Earnings-manipulation map")
    a.plotly_chart(style(f2), width="stretch")
    cnt = scored.groupby(["tier_w", "cohort"], observed=False).size().reset_index(name="n")
    f3 = px.bar(cnt, x="tier_w", y="n", color="cohort", barmode="group", color_discrete_map=COH_COL,
                category_orders={"tier_w": TIERS}, labels={"tier_w": "Risk tier", "n": "Companies"})
    f3.update_layout(title="Tier distribution by cohort")
    b.plotly_chart(style(f3), width="stretch")

    st.subheader("Screening table")
    cols = ["ticker", "name", "sector", "cohort", "score_w", "tier_w", "MScore", "MScore_flag", "sloan", "DA", "REM",
            "cfo_cum_ni", "Altman", "Altman_zone", "benford_mad", "benford_label"]
    tbl = view[cols].rename(columns={"score_w": "score", "tier_w": "tier"}).sort_values("score", ascending=False)
    st.dataframe(tbl.round(3), width="stretch", hide_index=True, height=380)
    st.download_button("⬇ Download table (CSV)", tbl.to_csv(index=False), f"forensic_screen_FY{fy}.csv")
    if (view.fin).any():
        st.info(f"{int(view.fin.sum())} financial-sector firms (banks/NBFCs/insurers) are **not scored** - these models assume an "
                "operating business. This is a deliberate design choice, not missing data.")

# ------------------------------------------------------------------------------------------ TAB 2
with t2:
    opts = view.sort_values("name")
    label = {r.ticker: f"{r['name']} ({r.ticker.replace('.NS', '')})" for _, r in opts.iterrows()}
    if not label: st.warning("No companies match the filters."); st.stop()
    tk = st.selectbox("Company", list(label), format_func=label.get)
    hist = mall[mall.ticker == tk].sort_values("fy")
    r = hist[hist.fy == fy]
    if r.empty: st.warning("No data for this company in the selected year."); st.stop()
    r = r.iloc[0]

    c = st.columns(5)
    c[0].metric("Risk score", "n/a" if pd.isna(r.score_w) else f"{r.score_w:.0f}/100", None if pd.isna(r.score_w) else str(r.tier_w))
    c[1].metric("Beneish M", "n/a" if pd.isna(r.MScore) else f"{r.MScore:.2f}", r.MScore_flag if pd.notna(r.MScore) else None, delta_color="off")
    c[2].metric("Altman Z'' zone", "n/a" if pd.isna(r.Altman) else f"{r.Altman:.1f}", None if pd.isna(r.Altman) else str(r.Altman_zone), delta_color="off")
    c[3].metric("Benford", "n/a" if pd.isna(r.benford_mad) else str(r.benford_label), f"MAD {r.benford_mad:.4f}" if pd.notna(r.benford_mad) else None, delta_color="off")
    c[4].metric("CFO / NI (3-yr)", "n/a" if pd.isna(r.cfo_cum_ni) else f"{r.cfo_cum_ni:.2f}")
    if r.fin: st.info("Financial-sector firm: only Benford applies. See the Method tab.")

    a, b = st.columns(2)
    # Beneish components vs peer median
    comps = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI"]
    med = peers[comps].median()
    f = go.Figure()
    f.add_bar(name="Company", x=comps, y=[r[k] for k in comps], marker_color=COH_COL["Nifty 50"])
    f.add_bar(name="Peer median", x=comps, y=med.values, marker_color="#cbd5e1")
    f.add_hline(y=1, line_dash="dot", line_color=MUTED, annotation_text="1.0 = no change")
    f.update_layout(title="Beneish indices vs peer median (>1 = deteriorating)", barmode="group")
    a.plotly_chart(style(f), width="stretch")
    # NI vs CFO
    f = go.Figure()
    usd = str(r.get("currency")) == "USD"; div, unit = (1e6, "USD million (Yahoo reports this firm in USD)") if usd else (1e7, "₹ crore")
    f.add_bar(name="Net income", x=hist.fy, y=hist.ni / div, marker_color=COH_COL["Nifty 50"])
    f.add_bar(name="Operating cash flow", x=hist.fy, y=hist.cfo / div, marker_color=COH_COL["Watchlist"])
    f.update_layout(title=f"Profit vs cash ({unit}) - a persistent gap is a red flag", barmode="group", xaxis=dict(dtick=1))
    b.plotly_chart(style(f), width="stretch")

    a, b = st.columns(2)
    d = bdig[bdig.ticker == tk]
    if len(d):
        f = go.Figure()
        f.add_bar(name="Observed", x=d.digit, y=d.observed * 100, marker_color=COH_COL["Nifty 50"])
        f.add_scatter(name="Benford expected", x=d.digit, y=d.expected * 100, mode="lines+markers", line=dict(color=INK, width=2))
        f.update_layout(title="Benford first-digit test (all statement line items, all years)", xaxis=dict(dtick=1, title="Leading digit"), yaxis_title="% of numbers")
        a.plotly_chart(style(f), width="stretch")
    comp_cols = {k: r["s_" + k] for k in WEIGHTS}
    f = go.Figure(go.Bar(y=list(comp_cols), x=[0 if pd.isna(v) else v for v in comp_cols.values()], orientation="h",
                         marker_color=COH_COL["Nifty 50"],
                         text=["n/a" if pd.isna(v) else f"{v:.0f}" for v in comp_cols.values()], textposition="outside"))
    f.update_layout(title="Risk-score building blocks (0 = benign, 100 = worst)", xaxis=dict(range=[0, 110]))
    b.plotly_chart(style(f), width="stretch")

    st.subheader("DuPont & quality ratios over time")
    show = hist.set_index("fy")[["net_margin", "asset_turn", "equity_mult", "roe", "roce", "current_ratio", "de_ratio", "int_cover", "dso", "dio", "MScore", "sloan", "DA"]].T
    st.dataframe(show.round(3), width="stretch")

# ------------------------------------------------------------------------------------------ TAB 3
with t3:
    METRICS = {"Beneish M-score": "MScore", "Sloan accrual ratio": "sloan", "Jones discretionary accruals": "DA",
               "Real earnings mgmt index": "REM", "Altman Z'' (EM)": "Altman", "Risk score": "score_w", "Net margin": "net_margin",
               "ROE": "roe", "ROCE": "roce", "Debt / equity": "de_ratio", "Receivable days (DSO)": "dso", "CFO / Net income": "cfo_to_ni"}
    METRICS["CFO / Net income"] = "cfo_to_ni" if "cfo_to_ni" in mall else "cfo_to_ni"
    allt = sorted(mall.ticker.unique())
    lab = dict(zip(mall.ticker, mall.name))
    defaults = [t for t in ["ZEEL.NS", "COFFEEDAY.NS", "RELINFRA.NS", "TCS.NS"] if t in allt]
    pick = st.multiselect("Choose up to 5 companies", allt, default=defaults, max_selections=5, format_func=lambda t: lab[t])
    met = st.selectbox("Metric", list(METRICS))
    col = METRICS[met] if METRICS[met] in mall else "cfo_to_ni"
    palette = ["#2a6fdb", "#d9730d", "#2f9e6e", "#8a5cc2", "#c2415c"]
    f = go.Figure()
    for i, t in enumerate(pick):
        h = mall[mall.ticker == t].sort_values("fy")
        f.add_bar(name=lab[t], x=h.fy, y=h[col], marker_color=palette[i])
    f.update_layout(title=f"{met} by fiscal year", barmode="group", xaxis=dict(dtick=1))
    if col == "MScore": f.add_hline(y=-1.78, line_dash="dash", line_color=MUTED, annotation_text="manipulator threshold")
    st.plotly_chart(style(f, 420), width="stretch")
    st.dataframe(mall[mall.ticker.isin(pick)].pivot(index="name", columns="fy", values=col).round(3), width="stretch")

# ------------------------------------------------------------------------------------------ TAB 4
with t4:
    st.markdown("### AI red-flag narrator")
    st.caption("Every memo is generated from the same numeric fact sheet. The AI is instructed to use **only** those numbers.")
    tk2 = st.selectbox("Company", sorted(yr.ticker), format_func=lambda t: lab.get(t, t), key="memo_co",
                       index=sorted(yr.ticker).index("ZEEL.NS") if "ZEEL.NS" in set(yr.ticker) else 0)
    row = yr[yr.ticker == tk2].iloc[0].copy()
    row["score"], row["tier"] = row.score_w, row.tier_w
    layer = st.radio("Memo source", ["Rule-based (deterministic)", "Claude-drafted (pre-generated)", "Live Claude API"], horizontal=True)
    if layer.startswith("Rule"):
        st.markdown(M.rule_based_memo(row, peers))
    elif layer.startswith("Claude-drafted"):
        p = DATA / "ai_memos.json"
        memos = json.loads(p.read_text()) if p.exists() else {}
        if tk2 in memos:
            st.markdown(memos[tk2]["memo"])
            st.caption(f"⚠️ Drafted by {memos[tk2]['model']} on {memos[tk2]['date']} from the FY{memos[tk2]['fy']} fact sheet. "
                       "AI-generated - verify against filings before use.")
        else:
            st.info("No pre-generated memo for this company yet. Use the rule-based or live option.")
    else:
        if st.button("Generate with Claude"):
            try:
                st.markdown(M.live_claude_memo(row, peers))
            except Exception as e:
                st.error(f"Live call unavailable: {e}. Set ANTHROPIC_API_KEY and `pip install anthropic`.")
    with st.expander("Fact sheet sent to the AI"):
        st.json(M.fact_sheet(row, peers))
    with st.expander("Prompt template (for your prompt log)"):
        st.code(M.PROMPT)

# ------------------------------------------------------------------------------------------ TAB 5
with t5:
    st.markdown("### Method")
    st.markdown("""
| Block | Tool (course session) | Rule |
|---|---|---|
| Beneish M (30) | 8-variable model, sessions 7-8 | flag > −1.78, watch > −2.22; needs ≥ 6 of 8 indices |
| Accruals (20) | Sloan ratio + Modified Jones DA, AEM | peer percentile (higher = riskier) |
| Cash divergence (15) | 3-yr CFO / net income, sessions 4-5 | lower conversion = riskier |
| REM (10) | Roychowdhury abnormal CFO & discretionary exp. | low CFO and low SG&A = income-increasing |
| Benford (10) | first-digit MAD, Nigrini bands, sessions 11-12 | ≤0.006 close, ≤0.012 acceptable, ≤0.015 marginal |
| Distress (15) | Altman Z″ (emerging markets) | < 4.15 distress, 4.15-5.85 grey |

*Weights in brackets are defaults; change them in the sidebar.* Tiers: Low < 35 ≤ Moderate < 50 ≤ Elevated < 65 ≤ High.
""")
    st.markdown("### Back-test: does the screen rank the watchlist above the Nifty 50?")
    v = valid.copy(); v["AUC"] = v.AUC.round(2)
    f = px.bar(v.sort_values("AUC"), x="AUC", y="metric", orientation="h", color_discrete_sequence=[COH_COL["Nifty 50"]],
               text="AUC", labels={"metric": ""})
    f.add_vline(x=0.5, line_dash="dash", line_color=MUTED, annotation_text="0.5 = coin-flip")
    f.update_layout(title="AUC: P(random watchlist firm scores above random Nifty firm)", xaxis=dict(range=[0, 1]))
    st.plotly_chart(style(f, 340), width="stretch")
    st.dataframe(v.round(3), hide_index=True, width="stretch")
    xl, xr = DATA / "xcheck_levels.csv", DATA / "xcheck_ratios.csv"
    if xl.exists() and xr.exists():
        st.markdown("### Data check: Yahoo Finance vs Screener.in (independent online source)")
        st.caption("All firms re-fetched from Screener.in public pages. Levels compared FY2024-26 (rupee-reporting firms); ratios compared for FY2026 on non-financial firms.")
        c1, c2 = st.columns(2)
        c1.markdown("**Line items: share of firm-years within tolerance**"); c1.dataframe(pd.read_csv(xl), hide_index=True, width="stretch")
        c2.markdown("**Screen inputs: rank agreement (Spearman)**"); c2.dataframe(pd.read_csv(xr), hide_index=True, width="stretch")
        st.success("Cash flow and total assets match almost exactly; the ratios the screen relies on correlate 0.98-1.00 across sources. "
                   "Sales gaps above 10% occur only for financial firms (revenue is defined differently) and Infosys (Yahoo reports in USD). "
                   "Caveat: both sites draw on the same company filings, so this proves transcription consistency, not that the filings are right.")
    st.warning("""**Limitations (read before trusting any number)**
- Watchlist is ~10 scoreable firms: AUCs are *indicative*, with wide uncertainty. Their episodes are mostly distress / governance, not pure accounting manipulation.
- Yahoo Finance gives only 4-5 fiscal years and different line-item definitions from other providers; cross-sectional models use ~40 non-financial firms per year (small, noisy).
- Peer percentiles are *relative to this universe*, not to the whole market.
- Corporate restructurings (mergers, demergers) break year-on-year indices and cause false positives.
- Related-party / cash-misappropriation frauds (Wirecard-type) are largely invisible to ratio screens - the course's point about cash confirmation.
- Banks, NBFCs and insurers are not scored.""")
