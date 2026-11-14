"""
FORENSIC EARNINGS-QUALITY SCREENER  -  dashboard for a forensic / fraud analyst
Run:  .venv/bin/streamlit run app.py
"""
import sys, re, json, subprocess, os, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, plotly.graph_objects as go, plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
if not (DATA / "metrics_year.csv").exists() and (ROOT / "metrics_year.csv").exists():
    DATA = ROOT          # files were uploaded loose in the repo root instead of data/
sys.path.insert(0, str(ROOT / "src"))
import memo as M
from forensic_engine import WEIGHTS

st.set_page_config(page_title="Forensic Earnings-Quality Screener", layout="wide", page_icon="🔍")

# ------------------------------------------------------------------------------------------ design tokens
NAVY, BLUE, ORANGE = "#1f3a6e", "#2a6fdb", "#d9730d"
TIER_COL = {"Low": "#c6dbef", "Moderate": "#6baed6", "Elevated": "#2171b5", "High": "#08306b"}
TIER_TXT = {"Low": "#1f2937", "Moderate": "#1f2937", "Elevated": "#ffffff", "High": "#ffffff"}
TIER_ICON = {"Low": "🟢", "Moderate": "🟡", "Elevated": "🟠", "High": "🔴"}
COH_COL = {"Nifty 50": BLUE, "Watchlist": ORANGE}
INK, MUTED, GRID = "#1f2937", "#6b7280", "#e5e7eb"
TIERS = ["Low", "Moderate", "Elevated", "High"]

st.markdown("""<style>
.block-container{padding-top:1.1rem;max-width:1280px}
#MainMenu, footer, header[data-testid="stHeader"]{visibility:hidden;height:0}
.hero{background:linear-gradient(120deg,#1f3a6e 0%,#2a6fdb 100%);color:#fff;padding:22px 28px 18px;border-radius:14px;margin-bottom:14px}
.hero .eyebrow{font-size:12px;letter-spacing:.12em;opacity:.8;font-weight:600}
.hero h1{color:#fff;font-size:30px;margin:2px 0 6px;padding:0;line-height:1.2}
.hero p{color:#e8eefc;margin:0 0 10px;font-size:15px;max-width:900px}
.pill{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);padding:3px 11px;border-radius:999px;font-size:12.5px;margin:0 6px 4px 0;color:#fff}
.card{border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;background:#fff;box-shadow:0 1px 3px rgba(16,24,40,.06);height:100%;color:#1f2937}
.card h4{margin:0 0 4px;color:#1f3a6e;font-size:16px}
.card .num{display:inline-block;background:#2a6fdb;color:#fff;border-radius:50%;width:24px;height:24px;text-align:center;line-height:24px;font-weight:700;margin-right:8px;font-size:13px}
.card p{margin:4px 0 0;font-size:14px;color:#374151}
.callout{border-left:4px solid #2a6fdb;background:#f1f6ff;padding:10px 14px;border-radius:6px;margin:6px 0 12px;color:#1f2937;font-size:14.5px}
.callout.warn{border-left-color:#d9730d;background:#fff6ec}
.callout.good{border-left-color:#2f9e6e;background:#effaf4}
.chip{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12.5px;font-weight:600;margin-right:6px}
.verdict{border:1px solid #e5e7eb;border-left:8px solid #2a6fdb;border-radius:10px;padding:14px 18px;background:#fff;margin:6px 0 12px;color:#1f2937;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.verdict .big{font-size:18px;font-weight:700;margin-bottom:4px}
div[data-testid="stMetric"]{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;box-shadow:0 1px 3px rgba(16,24,40,.06)}
div[data-testid="stMetric"] *{color:#1f2937}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid #e5e7eb}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:8px 14px}
h2,h3{color:#1f3a6e}
.sec{font-size:18px;font-weight:700;color:#1f3a6e;margin:14px 0 2px}
.sub{font-size:13.5px;color:#6b7280;margin:0 0 8px}
.foot{font-size:12.5px;color:#6b7280;border-top:1px solid #e5e7eb;margin-top:26px;padding-top:10px}
</style>""", unsafe_allow_html=True)


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=44, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(color=INK, size=12), legend=dict(orientation="h", y=-0.2), title_font=dict(size=14, color=NAVY))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def callout(text, kind=""):
    st.markdown(f'<div class="callout {kind}">{text}</div>', unsafe_allow_html=True)


def section(title, sub=""):
    st.markdown(f'<div class="sec">{title}</div>' + (f'<div class="sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)


def chip(tier):
    return f'<span class="chip" style="background:{TIER_COL[tier]};color:{TIER_TXT[tier]}">{tier}</span>'


def md2html(t):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t).replace("_Screening", "<i>Screening").replace("fraud._", "fraud.</i>")


if not (DATA / "metrics_year.csv").exists():
    st.error("Data files not found. Upload the `data` folder (with metrics_year.csv etc.) to the repo.")
    st.write("Files in repo root:", sorted(p.name for p in ROOT.iterdir()))
    st.write("Files in data/:", sorted(p.name for p in (ROOT / "data").iterdir()) if (ROOT / "data").exists() else "folder missing")
    st.stop()


@st.cache_data
def load(stamp):
    m = pd.read_csv(DATA / "metrics_year.csv")
    return m, pd.read_csv(DATA / "benford_digits.csv"), pd.read_csv(DATA / "validation.csv")


def stamp():
    f = DATA / "last_refresh.txt"
    return f.read_text() if f.exists() else "never"


# ------------------------------------------------------------------------------------------ sidebar
st.sidebar.markdown("### 🔍 Filters")
st.sidebar.info("New here? Open the **🏠 Start here** tab for a 2-minute guided tour.")
COOLDOWN_MIN = 30


def minutes_since_refresh():
    try: return (dt.datetime.now() - dt.datetime.fromisoformat((DATA / "last_refresh.txt").read_text().strip())).total_seconds() / 60
    except Exception: return 1e9


age = minutes_since_refresh()
if st.sidebar.button("⟳ Refresh live data (Yahoo + NSE)", disabled=age < COOLDOWN_MIN,
                     help="Re-downloads statements from NSE / Yahoo Finance and rescores every firm (about 3 minutes)."):
    env = {**os.environ, "WAI_DATA": str(DATA)}
    ok = True
    with st.spinner("Downloading statements and recomputing scores (about 3 minutes)..."):
        for s_ in ["src/fetch_data.py", "src/forensic_engine.py"]:
            r_ = subprocess.run([sys.executable, str(ROOT / s_)], capture_output=True, text=True, env=env, timeout=900)
            if r_.returncode:
                ok = False; st.sidebar.error("Refresh failed (Yahoo Finance may be blocking this server). Showing the previous data. " + r_.stderr[-200:] + r_.stdout[-200:]); break
    if ok:
        st.cache_data.clear(); st.rerun()
st.sidebar.caption(f"Data last refreshed: {stamp()}")
if age < COOLDOWN_MIN: st.sidebar.caption(f"Data is only {age:.0f} min old; refresh unlocks after {COOLDOWN_MIN} min.")

mall, bdig, valid = load(stamp())
mall = mall.copy()
years = sorted(mall[mall.score.notna() | mall.fin].fy.unique(), reverse=True)
fy = st.sidebar.selectbox("Fiscal year (ending March)", years, index=0, help="2026 = year ended 31 March 2026")
cohorts = st.sidebar.multiselect("Cohort", ["Nifty 50", "Watchlist"], default=["Nifty 50", "Watchlist"],
                                 help="Nifty 50 = India's 50 largest listed firms. Watchlist = firms with publicly reported governance or distress episodes (used to test the model).")
sectors = sorted(mall.sector.dropna().unique())
sec_sel = st.sidebar.multiselect("Sector", sectors, default=[], help="Leave empty to include all sectors")
tier_sel = st.sidebar.multiselect("Risk tier", TIERS, default=TIERS)

with st.sidebar.expander("⚖️ Adjust model weights (what-if)"):
    st.caption("Each slider sets how much a test counts in the 0-100 score. Try setting Distress to 0 and watch the ranking change.")
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
all_scored = yr[yr.score_w.notna()]
lab = dict(zip(mall.ticker, mall.name))

# ------------------------------------------------------------------------------------------ hero
st.markdown(f"""<div class="hero">
<div class="eyebrow">IIM RANCHI · FINANCIAL STATEMENT ANALYSIS &amp; FORENSIC AUDITING · WORKING-WITH-AI PROJECT</div>
<h1>Forensic Earnings-Quality Screener</h1>
<p>Which listed Indian companies should a forensic analyst investigate first? This dashboard turns financial statements into
red-flag scores using the tools taught in the course, and explains every number in plain English.</p>
<span class="pill">📅 Data as of {stamp()[:10]}</span><span class="pill">🏢 {yr.ticker.nunique()} companies</span>
<span class="pill">✅ {len(all_scored)} scored (FY{fy})</span><span class="pill">🌐 Live sources: NSE · Yahoo Finance · Screener.in</span>
</div>""", unsafe_allow_html=True)

t0, t1, t2, t3, t4, t5 = st.tabs(["🏠 Start here", "📊 Universe screener", "🏢 Company deep-dive", "⚖️ Peer comparison", "🤖 AI analyst memo", "📘 Method & validation"])

# ------------------------------------------------------------------------------------------ TAB 0: START HERE
with t0:
    section("What is this?", "A screening tool for a forensic / fraud analyst, who has far more companies than time to read every annual report.")
    callout("<b>The idea:</b> accounting manipulation leaves fingerprints in the numbers (profits without cash, receivables growing faster than sales, "
            "unnatural digit patterns). We measure six fingerprints for each company, combine them into a <b>0-100 risk score</b>, and rank companies so the analyst "
            "knows <b>whom to investigate first</b>. A high score is a reason to look closer, <b>never proof of fraud</b>.")

    section("How to use it: three steps")
    c1, c2, c3 = st.columns(3)
    c1.markdown('<div class="card"><h4><span class="num">1</span>Screen</h4><p>Open <b>📊 Universe screener</b>. See every company ranked by risk score. Use the sidebar to filter by year, sector, cohort or tier.</p></div>', unsafe_allow_html=True)
    c2.markdown('<div class="card"><h4><span class="num">2</span>Investigate</h4><p>Open <b>🏢 Company deep-dive</b>. Pick a company to see <i>why</i> it scored high: which tests fired, how it compares to peers, profit versus cash.</p></div>', unsafe_allow_html=True)
    c3.markdown('<div class="card"><h4><span class="num">3</span>Explain</h4><p>Open <b>🤖 AI analyst memo</b> for a short written risk memo with next audit steps. Then <b>📘 Method &amp; validation</b> shows how reliable the screen is.</p></div>', unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1, 1])
    with left:
        section("How to read the risk score")
        st.markdown(
            f'{chip("Low")} <b>below 35</b>: no major test fired; routine monitoring.<br><br>'
            f'{chip("Moderate")} <b>35 to 50</b>: one or two mild signals; check the cause.<br><br>'
            f'{chip("Elevated")} <b>50 to 65</b>: several signals; prioritise for review.<br><br>'
            f'{chip("High")} <b>above 65</b>: many signals; investigate first, but rule out benign causes such as mergers or demergers.<br><br>'
            '<span style="color:#6b7280;font-size:13px">Scores are relative to the companies in this dashboard (a ranking, not an absolute probability). '
            'Banks, NBFCs and insurers are shown but not scored, because the tests assume an operating business.</span>', unsafe_allow_html=True)
    with right:
        section("Key findings (live from the data)")
        tc = all_scored.tier_w.value_counts().to_dict()
        top3 = all_scored.sort_values("score_w", ascending=False).head(3)
        wm = all_scored[all_scored.cohort == "Watchlist"].score_w.median(); nm = all_scored[all_scored.cohort == "Nifty 50"].score_w.median()
        auc = valid.set_index("metric").AUC.get("Composite score", np.nan)
        xr = DATA / "xcheck_ratios.csv"
        xc = f" Inputs were cross-checked against Screener.in: the ratios behind the score agree (rank correlation {pd.read_csv(xr).spearman.min():.2f} to {pd.read_csv(xr).spearman.max():.2f})." if xr.exists() else ""
        st.markdown(
            f"- **{len(all_scored)}** companies scored for FY{fy}: **{tc.get('High', 0)}** High, **{tc.get('Elevated', 0)}** Elevated, **{tc.get('Moderate', 0)}** Moderate, **{tc.get('Low', 0)}** Low.\n"
            f"- Highest scores: **{', '.join(top3.name.str.replace(' Limited', '').str.replace(' Ltd.', ''))}**.\n"
            f"- The watchlist of known troubled firms scores higher on average (median **{wm:.0f}** vs **{nm:.0f}** for the Nifty 50), "
            f"but the back-test is only modest (AUC **{auc:.2f}**, where 0.5 is a coin flip, on ~10 firms).{xc}\n"
            "- The screen is good for **triage**, not for verdicts: some flags are false positives (for example after a company restructures).")

    section("Suggested 2-minute walkthrough")
    st.markdown(
        "1. **📊 Universe screener**: in the sidebar set *Cohort* to **Watchlist**. Which known-troubled firms does the model flag? Hover over a bar for details.\n"
        "2. **🏢 Company deep-dive**: choose **PC Jeweller**. Read the verdict banner, then see where its Beneish bars rise above the peer median and how profit compares with operating cash.\n"
        "3. **⚖️ Peer comparison**: keep the default firms (Zee, Coffee Day, Reliance Infra, TCS) and switch the metric to *Beneish M-score* or *CFO / Net income*.\n"
        "4. **🤖 AI analyst memo**: pick PC Jeweller and flip between *Rule-based* and *Claude-drafted*. Open *Fact sheet* to see exactly which numbers the AI was allowed to use.\n"
        "5. **Sidebar what-if**: open *Adjust model weights*, set *Distress* to 0, and watch the ranking change. This shows the score is a judgement, not a law of nature.\n"
        "6. **📘 Method & validation**: read the back-test and the data cross-check, including the limitations.\n"
        "7. **⟳ Refresh live data** (sidebar) re-downloads the latest statements from NSE and Yahoo Finance (about 3 minutes).")

    with st.expander("📖 Glossary: what each test means in plain English"):
        st.markdown("""
| Term | Plain-English meaning | Red flag when |
|---|---|---|
| **Beneish M-score** | A formula combining 8 year-on-year changes (receivables, margins, asset quality, sales growth, depreciation, overheads, leverage, accruals) that separates likely manipulators from others | M above **−1.78** (likely manipulator); −2.22 to −1.78 is "watch" |
| **DSRI** | Receivables growing faster than sales | above ~1.3 (customers not paying, or sales booked early) |
| **GMI** | Gross margin deteriorating | above ~1.2 (pressure to flatter profits) |
| **AQI** | More assets that are not cash, inventory or plant | above ~1.3 (costs possibly capitalised) |
| **SGI** | Sales growth | very high (pressure to keep growing) |
| **TATA / Sloan accruals** | Profit that is *not* backed by cash, scaled by assets | high positive values |
| **Jones DA (AEM)** | The part of accruals that normal business activity cannot explain (accrual earnings management) | large positive residual |
| **REM** | Real earnings management: cutting discretionary spending or distorting cash flow to hit profit targets | high index |
| **CFO / NI** | Operating cash flow divided by net income over 3 years | well below 1 (profit not turning into cash) |
| **Benford's law** | In natural numbers, about 30% start with digit 1 and 4.6% with 9. Made-up numbers drift from this | MAD above 0.015 = non-conformity (weak signal by itself) |
| **Altman Z″** | Bankruptcy-risk score (emerging-market version) | below 4.15 = distress, which raises the incentive to manipulate |
""")
    callout("<b>Important:</b> this is a screening tool built for learning. Flags can have innocent explanations (mergers, demergers, new accounting standards, one-off items). "
            "Never treat a flag as proof of wrongdoing; the AI memos list benign explanations to check first.", "warn")

# ------------------------------------------------------------------------------------------ TAB 1
with t1:
    section("Universe screener", f"All companies ranked by composite risk score, FY{fy}. Filters in the sidebar apply here.")
    c = st.columns(5)
    c[0].metric("Companies in view", len(view))
    c[1].metric("Scored", len(scored), help="Banks/NBFCs/insurers and firms with insufficient data are not scored")
    c[2].metric("High + Elevated", int(scored.tier_w.isin(["High", "Elevated"]).sum()), help="Companies to prioritise")
    c[3].metric("Median score", f"{scored.score_w.median():.0f}" if len(scored) else "–")
    c[4].metric("Beneish > −1.78", int((view.MScore > -1.78).sum()), help="Companies the Beneish model labels likely manipulators")

    if len(scored_tier) == 0:
        callout("No scored companies match the current filters. Widen the sidebar filters.", "warn")
    else:
        hi = scored[scored.tier_w.isin(["High", "Elevated"])]
        sec_txt = ""
        if len(hi):
            vc = hi.sector.value_counts(); sec_txt = f" The most common sector among them is <b>{vc.index[0]}</b> ({vc.iloc[0]})."
        callout(f"<b>Takeaway:</b> {len(hi)} of {len(scored)} scored companies are High or Elevated.{sec_txt} "
                f"Highest: <b>{scored.sort_values('score_w', ascending=False).iloc[0]['name']}</b> ({scored.score_w.max():.0f}/100).")
        n = st.slider("Show top N companies", 5, max(6, len(scored_tier)), min(20, max(6, len(scored_tier))))
        top = scored_tier.sort_values("score_w", ascending=False).head(n).iloc[::-1]
        fig = go.Figure(go.Bar(x=top.score_w, y=top.ticker.str.replace(".NS", ""), orientation="h",
                               marker_color=[TIER_COL[str(t)] for t in top.tier_w],
                               marker_line=dict(color=[COH_COL[x] for x in top.cohort], width=2),
                               customdata=np.c_[top.name, top.tier_w, top.cohort, top.MScore.round(2)],
                               hovertemplate="<b>%{customdata[0]}</b><br>Score %{x:.0f} (%{customdata[1]})<br>%{customdata[2]} · Beneish %{customdata[3]}<extra></extra>"))
        fig.update_layout(title="Composite forensic risk score", xaxis_title="Risk score (0–100)")
        st.plotly_chart(style(fig, max(320, 22 * len(top) + 80)), width="stretch")
        st.caption("**How to read:** longer bar = more red flags. Bar **fill** shows the risk tier (darker = higher). Bar **outline** shows the cohort (blue = Nifty 50, orange = Watchlist).")

        a, b = st.columns(2)
        sc_df = scored.dropna(subset=["MScore", "sloan"])
        f2 = px.scatter(sc_df, x="MScore", y="sloan", color="cohort", color_discrete_map=COH_COL, hover_name="name",
                        hover_data={"score_w": ":.0f", "cohort": False}, labels={"MScore": "Beneish M-score", "sloan": "Sloan accrual ratio", "cohort": "Cohort"})
        f2.add_vline(x=-1.78, line_dash="dash", line_color=MUTED, annotation_text="manipulator −1.78")
        f2.add_hline(y=0.1, line_dash="dot", line_color=MUTED)
        f2.update_traces(marker=dict(size=10, line=dict(color="white", width=1.5)))
        f2.update_layout(title="Earnings-manipulation map")
        a.plotly_chart(style(f2), width="stretch")
        a.caption("**How to read:** each dot is a company. **Upper right** = both Beneish and accruals look worrying (right of the dashed line = Beneish flags it; high up = profit not backed by cash).")
        cnt = scored.groupby(["tier_w", "cohort"], observed=False).size().reset_index(name="n")
        f3 = px.bar(cnt, x="tier_w", y="n", color="cohort", barmode="group", color_discrete_map=COH_COL,
                    category_orders={"tier_w": TIERS}, labels={"tier_w": "Risk tier", "n": "Companies", "cohort": "Cohort"})
        f3.update_layout(title="How many companies in each tier")
        b.plotly_chart(style(f3), width="stretch")
        b.caption("**How to read:** if the model works, the orange Watchlist bars should lean towards the higher tiers.")

    section("Screening table", "Sortable (click a column header). The progress bar shows the risk score.")
    d = view.copy(); d["Risk"] = [("⚪ not scored" if pd.isna(t) else f"{TIER_ICON[str(t)]} {t}") for t in d.tier_w]
    tbl = d.sort_values("score_w", ascending=False)[["name", "sector", "cohort", "score_w", "Risk", "MScore", "sloan", "DA", "REM", "cfo_cum_ni", "Altman", "benford_label"]].rename(
        columns={"name": "Company", "sector": "Sector", "cohort": "Cohort", "score_w": "Risk score", "MScore": "Beneish M", "sloan": "Sloan accruals", "DA": "Jones DA",
                 "REM": "REM index", "cfo_cum_ni": "CFO/NI (3y)", "Altman": "Altman Z″", "benford_label": "Benford"})
    st.dataframe(tbl, width="stretch", hide_index=True, height=400, column_config={
        "Risk score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.0f"),
        "Beneish M": st.column_config.NumberColumn(format="%.2f", help="Above −1.78 = likely manipulator"),
        "Sloan accruals": st.column_config.NumberColumn(format="%.3f", help="Profit not backed by cash, scaled by assets"),
        "Jones DA": st.column_config.NumberColumn(format="%.3f"), "REM index": st.column_config.NumberColumn(format="%.3f"),
        "CFO/NI (3y)": st.column_config.NumberColumn(format="%.2f", help="Below ~0.8 = profits not turning into cash"),
        "Altman Z″": st.column_config.NumberColumn(format="%.1f", help="Below 4.15 = distress zone")})
    st.download_button("⬇ Download table (CSV)", tbl.to_csv(index=False), f"forensic_screen_FY{fy}.csv")
    if view.fin.any():
        callout(f"{int(view.fin.sum())} financial-sector firms (banks, NBFCs, insurers) are <b>not scored</b>: these tests assume receivables, inventory and an operating cycle. "
                "This is a deliberate design choice, not missing data.")

# ------------------------------------------------------------------------------------------ TAB 2
with t2:
    section("Company deep-dive", "Pick a company to see why it scored the way it did.")
    opts = view.sort_values("name")
    label = {r_.ticker: f"{r_['name']} ({r_.ticker.replace('.NS', '')})" for _, r_ in opts.iterrows()}
    if not label:
        callout("No companies match the sidebar filters.", "warn")
    else:
        keys = list(label)
        tk = st.selectbox("Company", keys, format_func=label.get, index=keys.index("PCJEWELLER.NS") if "PCJEWELLER.NS" in keys else 0)
        hist = mall[mall.ticker == tk].sort_values("fy")
        rr = hist[hist.fy == fy]
        if rr.empty:
            callout("No data for this company in the selected year.", "warn")
        else:
            r = rr.iloc[0]
            row2 = r.copy(); row2["score"], row2["tier"] = r.score_w, r.tier_w
            memo_txt = M.rule_based_memo(row2, peers)
            lines = [l for l in memo_txt.split("\n") if l.strip()]
            tier = str(r.tier_w) if pd.notna(r.tier_w) else None
            border = TIER_COL.get(tier, "#9ca3af")
            body = md2html(lines[0]) if tier else md2html(memo_txt)
            sig = next((md2html(l) for l in lines if l.startswith("**Signals raised")), "")
            st.markdown(f'<div class="verdict" style="border-left-color:{border}"><div class="big">{body}</div><div>{sig}</div></div>', unsafe_allow_html=True)

            c = st.columns(5)
            c[0].metric("Risk score", "n/a" if pd.isna(r.score_w) else f"{r.score_w:.0f}/100", None if pd.isna(r.score_w) else str(r.tier_w), delta_color="off")
            c[1].metric("Beneish M", "n/a" if pd.isna(r.MScore) else f"{r.MScore:.2f}", r.MScore_flag if pd.notna(r.MScore) else None, delta_color="off", help="Above −1.78 = likely manipulator")
            c[2].metric("Altman Z″", "n/a" if pd.isna(r.Altman) else f"{r.Altman:.1f}", None if pd.isna(r.Altman) else str(r.Altman_zone), delta_color="off", help="Bankruptcy-risk score; below 4.15 = distress")
            c[3].metric("Benford", "n/a" if pd.isna(r.benford_mad) else str(r.benford_label), f"MAD {r.benford_mad:.4f}" if pd.notna(r.benford_mad) else None, delta_color="off", help="Do leading digits follow the natural pattern?")
            c[4].metric("CFO / NI (3-yr)", "n/a" if pd.isna(r.cfo_cum_ni) else f"{r.cfo_cum_ni:.2f}", help="Operating cash flow ÷ net income. Well below 1 = profit not turning into cash")

            a, b = st.columns(2)
            comps = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI"]
            med = peers[comps].median()
            f = go.Figure()
            f.add_bar(name="This company", x=comps, y=[r[k] for k in comps], marker_color=BLUE)
            f.add_bar(name="Peer median", x=comps, y=med.values, marker_color="#cbd5e1")
            f.add_hline(y=1, line_dash="dot", line_color=MUTED, annotation_text="1.0 = no change")
            f.update_layout(title="Beneish indices vs peers", barmode="group")
            a.plotly_chart(style(f), width="stretch")
            a.caption("**How to read:** each bar is a year-on-year change. Above the dotted **1.0** line = deteriorating. Blue well above grey = this firm is worse than peers on that test (see Glossary in *Start here*).")
            f = go.Figure()
            usd = str(r.get("currency")) == "USD"; div, unit = (1e6, "USD million") if usd else (1e7, "₹ crore")
            f.add_bar(name="Net income", x=hist.fy, y=hist.ni / div, marker_color=BLUE)
            f.add_bar(name="Operating cash flow", x=hist.fy, y=hist.cfo / div, marker_color=ORANGE)
            f.update_layout(title=f"Profit vs cash ({unit})", barmode="group", xaxis=dict(dtick=1))
            b.plotly_chart(style(f), width="stretch")
            b.caption("**How to read:** healthy firms turn profit into cash, so the two bars are similar. A persistent gap (blue much taller than orange) is a classic red flag.")

            a, b = st.columns(2)
            d_ = bdig[bdig.ticker == tk]
            if len(d_):
                f = go.Figure()
                f.add_bar(name="Observed", x=d_.digit, y=d_.observed * 100, marker_color=BLUE)
                f.add_scatter(name="Benford expected", x=d_.digit, y=d_.expected * 100, mode="lines+markers", line=dict(color=INK, width=2))
                f.update_layout(title="Benford first-digit test", xaxis=dict(dtick=1, title="Leading digit"), yaxis_title="% of numbers")
                a.plotly_chart(style(f), width="stretch")
                a.caption("**How to read:** bars should follow the black line (about 30% of natural numbers start with 1). Big gaps hint at unnatural numbers, but this is a weak signal on its own.")
            comp_cols = {k: r["s_" + k] for k in WEIGHTS}
            f = go.Figure(go.Bar(y=list(comp_cols), x=[0 if pd.isna(v) else v for v in comp_cols.values()], orientation="h", marker_color=BLUE,
                                 text=["n/a" if pd.isna(v) else f"{v:.0f}" for v in comp_cols.values()], textposition="outside"))
            f.update_layout(title="What drives the score", xaxis=dict(range=[0, 110]), yaxis=dict(autorange="reversed"))
            b.plotly_chart(style(f), width="stretch")
            b.caption("**How to read:** the six building blocks, each 0 (benign) to 100 (worst). The score is their weighted average (weights are adjustable in the sidebar).")

            with st.expander("Ratios over time (DuPont, liquidity, leverage, quality)"):
                show = hist.set_index("fy")[["net_margin", "asset_turn", "equity_mult", "roe", "roce", "current_ratio", "de_ratio", "int_cover", "dso", "dio", "MScore", "sloan", "DA"]].T
                show.index = ["Net margin", "Asset turnover", "Equity multiplier", "ROE", "ROCE", "Current ratio", "Debt / equity", "Interest cover", "Receivable days", "Inventory days", "Beneish M", "Sloan accruals", "Jones DA"]
                st.dataframe(show.round(3), width="stretch")
                st.caption("ROE = net margin × asset turnover × equity multiplier (DuPont). Missing values mean the line item is not reported for that company.")

# ------------------------------------------------------------------------------------------ TAB 3
with t3:
    section("Peer comparison", "Put up to five companies side by side on any metric, year by year.")
    METRICS = {"Beneish M-score": "MScore", "Sloan accrual ratio": "sloan", "Jones discretionary accruals": "DA",
               "Real earnings mgmt index": "REM", "Altman Z″ (EM)": "Altman", "Risk score": "score_w", "Net margin": "net_margin",
               "ROE": "roe", "ROCE": "roce", "Debt / equity": "de_ratio", "Receivable days (DSO)": "dso", "CFO / Net income": "cfo_to_ni"}
    allt = sorted(mall.ticker.unique())
    defaults = [t for t in ["ZEEL.NS", "COFFEEDAY.NS", "RELINFRA.NS", "TCS.NS"] if t in allt]
    cc1, cc2 = st.columns([2, 1])
    pick = cc1.multiselect("Companies (up to 5)", allt, default=defaults, max_selections=5, format_func=lambda t: lab[t])
    met = cc2.selectbox("Metric", list(METRICS))
    col = METRICS[met]
    palette = ["#2a6fdb", "#d9730d", "#2f9e6e", "#8a5cc2", "#c2415c"]
    f = go.Figure()
    for i, t in enumerate(pick):
        h = mall[mall.ticker == t].sort_values("fy")
        f.add_bar(name=lab[t], x=h.fy, y=h[col], marker_color=palette[i])
    f.update_layout(title=f"{met} by fiscal year", barmode="group", xaxis=dict(dtick=1))
    if col == "MScore": f.add_hline(y=-1.78, line_dash="dash", line_color=MUTED, annotation_text="manipulator threshold")
    st.plotly_chart(style(f, 420), width="stretch")
    st.caption("**How to read:** compare bars within a year to see who is better or worse, and across years to see the trend. For Beneish, Sloan, Jones, REM and Risk score, **higher = worse**. For Altman, CFO/NI and margins, **higher = healthier**.")
    if pick:
        st.dataframe(mall[mall.ticker.isin(pick)].pivot(index="name", columns="fy", values=col).round(3), width="stretch")

# ------------------------------------------------------------------------------------------ TAB 4
with t4:
    section("AI analyst memo", "A short written risk memo for any company, in the style of a forensic analyst's note.")
    callout("<b>How the AI is kept honest:</b> every memo is built from the same numeric <i>fact sheet</i>. The AI is instructed to use <b>only</b> those numbers, to treat flags as signals not proof, "
            "and to list benign explanations. Open <i>Fact sheet</i> below to see exactly what it was given.")
    ykeys = sorted(yr.ticker)
    tk2 = st.selectbox("Company", ykeys, format_func=lambda t: lab.get(t, t), key="memo_co", index=ykeys.index("PCJEWELLER.NS") if "PCJEWELLER.NS" in ykeys else 0)
    row = yr[yr.ticker == tk2].iloc[0].copy()
    row["score"], row["tier"] = row.score_w, row.tier_w
    layer = st.radio("Memo source", ["Rule-based (deterministic)", "Claude-drafted (pre-generated)", "Live Claude API"], horizontal=True,
                     help="Rule-based: fixed text rules, no AI. Claude-drafted: written by Claude from the fact sheet. Live: calls the API if a key is configured.")
    if layer.startswith("Rule"):
        st.markdown(M.rule_based_memo(row, peers))
    elif layer.startswith("Claude-drafted"):
        p = DATA / "ai_memos.json"
        memos = json.loads(p.read_text()) if p.exists() else {}
        if tk2 in memos:
            st.markdown(memos[tk2]["memo"])
            st.caption(f"⚠️ Drafted by {memos[tk2]['model']} on {memos[tk2]['date']} from the FY{memos[tk2]['fy']} fact sheet. AI-generated: verify against filings before use.")
        else:
            callout("No pre-generated Claude memo for this company. Memos exist for PC Jeweller, Zee, Coffee Day, Reliance Infra, Tata Motors PV, Adani Enterprises, TCS and Vodafone Idea. Use the rule-based option for others.")
    else:
        if st.button("Generate with Claude"):
            try:
                st.markdown(M.live_claude_memo(row, peers))
            except Exception as e:
                st.error(f"Live call unavailable on this deployment ({e}). It needs an ANTHROPIC_API_KEY.")
    with st.expander("Fact sheet given to the AI"):
        st.json(M.fact_sheet(row, peers))
    with st.expander("Prompt template"):
        st.code(M.PROMPT)

# ------------------------------------------------------------------------------------------ TAB 5
with t5:
    section("Method & validation", "How the score is built, how well it works, and where it can mislead.")
    st.markdown("""
| Block | Default weight | Tool (course session) | Red-flag rule |
|---|---|---|---|
| Beneish | 30 | 8-variable M-score (sessions 7-8) | M > −1.78 flag, > −2.22 watch; needs ≥ 6 of 8 indices |
| Accruals | 20 | Sloan ratio + modified Jones DA (AEM) | higher peer percentile = riskier |
| Cash divergence | 15 | 3-yr CFO / net income (sessions 4-5) | lower conversion = riskier |
| REM | 10 | Roychowdhury abnormal CFO and discretionary spend | low CFO and low SG&A |
| Benford | 10 | First-digit MAD, Nigrini bands (sessions 11-12) | ≤0.006 close, ≤0.012 acceptable, ≤0.015 marginal, above = non-conformity |
| Distress | 15 | Altman Z″ emerging-market | < 4.15 distress, 4.15-5.85 grey |

Tiers: **Low** below 35 · **Moderate** 35-50 · **Elevated** 50-65 · **High** above 65. Weights are adjustable in the sidebar.
""")
    section("Back-test: does the screen rank the watchlist above the Nifty 50?", "AUC = chance that a random watchlist firm scores higher than a random Nifty firm. 0.5 = coin flip, 1.0 = perfect.")
    v = valid.copy(); v["AUC"] = v.AUC.round(2)
    f = px.bar(v.sort_values("AUC"), x="AUC", y="metric", orientation="h", color_discrete_sequence=[BLUE], text="AUC", labels={"metric": ""})
    f.add_vline(x=0.5, line_dash="dash", line_color=MUTED, annotation_text="0.5 = coin-flip")
    f.update_layout(title="Back-test result by test", xaxis=dict(range=[0, 1]))
    st.plotly_chart(style(f, 340), width="stretch")
    callout("<b>Honest reading:</b> the combined score beats a coin flip (about 0.65) but not by a lot, using only ~10 watchlist firms. Several watchlist episodes were distress or governance issues, "
            "not accounting manipulation. Treat the screen as a prioritisation aid, not a detector.", "warn")
    with st.expander("Back-test details"):
        st.dataframe(v.round(3), hide_index=True, width="stretch")
    xl, xr = DATA / "xcheck_levels.csv", DATA / "xcheck_ratios.csv"
    if xl.exists() and xr.exists():
        section("Data check: Yahoo Finance vs Screener.in", "All firms re-fetched from Screener.in's public pages as an independent online source.")
        c1, c2 = st.columns(2)
        c1.markdown("**Line items: share of firm-years within tolerance (FY2024-26)**"); c1.dataframe(pd.read_csv(xl), hide_index=True, width="stretch")
        c2.markdown("**Screen inputs: rank agreement between sources (FY2026)**"); c2.dataframe(pd.read_csv(xr), hide_index=True, width="stretch")
        callout("Cash flow and total assets match almost exactly, and the ratios the screen relies on correlate 0.98-1.00 across sources. Sales gaps above 10% occur only for financial firms "
                "(revenue is defined differently) and Infosys (Yahoo reports it in USD). Caveat: both sites draw on the same company filings, so this shows consistent transcription, not that the filings are accurate.", "good")
    st.markdown("""**Limitations (read before trusting any number)**
- The watchlist has only ~10 scoreable firms, so the back-test is indicative.
- Yahoo Finance gives 4-5 fiscal years; accrual models use ~40 non-financial firms per year (small and noisy).
- Peer percentiles are relative to this universe, not the whole market.
- Mergers, demergers and other restructurings break year-on-year comparisons and cause false positives.
- Related-party and cash-misappropriation frauds (Wirecard-type) are mostly invisible to ratio screens; they need cash confirmations and document review.
- Banks, NBFCs and insurers are not scored.""")

st.markdown('<div class="foot">Sources: NSE India (Nifty 50 list), Yahoo Finance (financial statements), Screener.in (cross-check). Methods: Beneish (1999), Sloan (1996), '
            'Dechow-Sloan-Sweeney (1995), Roychowdhury (2006), Nigrini (2012), Altman (1968/1995). Educational project for IIM Ranchi FSAFA; not investment advice and not evidence of wrongdoing.</div>', unsafe_allow_html=True)
