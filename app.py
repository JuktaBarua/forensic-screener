"""
FORENSIC EARNINGS-QUALITY SCREENER  -  dashboard for a forensic / fraud analyst
Run:  .venv/bin/streamlit run app.py
"""
import sys, re, io, json, zipfile, subprocess, os, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, plotly.graph_objects as go, plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
if not (DATA / "metrics_year.csv").exists() and (ROOT / "metrics_year.csv").exists():
    DATA = ROOT          # files were uploaded loose in the repo root instead of data/
sys.path.insert(0, str(ROOT / "src"))
import memo as M
import analytics as A
import decision as D
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
PCFG = {"displayModeBar": False}

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
div[data-testid="stMetricValue"]{font-size:1.55rem}
div[data-testid="stMetric"] [data-testid="stMarkdownContainer"], div[data-testid="stMetric"] p, div[data-testid="stMetric"] label,
div[data-testid="stMetricLabel"] *, div[data-testid="stMetricValue"] *, div[data-testid="stMetricDelta"] *{white-space:normal !important;overflow:visible !important;text-overflow:clip !important;overflow-wrap:break-word;word-break:normal;line-height:1.25}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid #e5e7eb}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:8px 14px}
h2,h3{color:#1f3a6e}
.sec{font-size:18px;font-weight:700;color:#1f3a6e;margin:14px 0 2px}
.sub{font-size:13.5px;color:#6b7280;margin:0 0 8px}
.foot{font-size:12.5px;color:#6b7280;border-top:1px solid #e5e7eb;margin-top:26px;padding-top:10px}
@media (max-width:1250px){div[data-testid="stMetricValue"]{font-size:1.3rem} div[data-testid="stMetricLabel"] *{font-size:.8rem !important}}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:10px;margin:4px 0 10px}
.kpis .k1{border:1px solid #e5e7eb;border-radius:12px;padding:10px 12px;background:#fff;color:#1f2937;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.kpis .k1 .l{font-size:13px;color:#4b5563;line-height:1.2}
.kpis .k1 .v{font-size:28px;font-weight:700;color:#1f3a6e;line-height:1.15}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:4px 0 14px}
.trio .cell{border:1px solid #e5e7eb;border-top:4px solid #2a6fdb;border-radius:10px;padding:12px 14px;background:#fff;color:#1f2937;font-size:14.5px;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.trio .k{font-size:11.5px;letter-spacing:.1em;color:#6b7280;font-weight:700;margin-bottom:4px}
.acts{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:6px 0 12px}
.acts .a{border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;background:#fff;color:#1f2937;font-size:13.5px;box-shadow:0 1px 3px rgba(16,24,40,.06)}
.acts .a b.t{display:block;font-size:15px;margin-bottom:2px}
.acts .a .n{font-size:26px;font-weight:700;color:#1f3a6e;line-height:1.1}
@media (max-width:760px){.trio,.acts{grid-template-columns:1fr}}
</style>""", unsafe_allow_html=True)


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=44, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(color=INK, size=12), legend=dict(orientation="h", y=-0.2), title_font=dict(size=14, color=NAVY), hoverlabel=dict(namelength=-1))
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
st.sidebar.info("New here? The **🎯 Decision desk** answers the key questions in seconds. **ℹ️ Guide** has a walkthrough and glossary.")
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
# Forensic Priority Index: 50% risk score + 25% share of tests in the red zone + 25% AI anomaly percentile
mall["fpi_w"] = np.where(mall.score_w.notna(), 0.5 * mall.score_w + 25 * (mall.red_n / mall.red_of).fillna(0) + 0.25 * mall.anomaly_pct.fillna(50), np.nan)

yr = mall[mall.fy == fy].copy()
yr = yr.join(pd.DataFrame([D.action_for(r_) for _, r_ in yr.iterrows()], index=yr.index, columns=["action", "why", "first"]))
view = yr[yr.cohort.isin(cohorts)]
if sec_sel: view = view[view.sector.isin(sec_sel)]
scored = view[view.score_w.notna()]
scored_tier = scored[scored.tier_w.isin(tier_sel)]
peers = yr[~yr.fin]
all_scored = yr[yr.score_w.notna()]
lab = dict(zip(mall.ticker, mall.name))
uni = pd.read_csv(DATA / "universe.csv")
alerts_df = D.build_alerts(mall, fy)


@st.cache_data
def panel_data(_k):
    sp = DATA / "screener_long.csv"
    return A.build_panel(pd.read_csv(sp), pd.read_csv(DATA / "universe.csv")) if sp.exists() else None


panel = panel_data("v1")

# ------------------------------------------------------------------------------------------ hero
st.markdown(f"""<div class="hero">
<div class="eyebrow">FORENSIC ANALYTICS · EARNINGS-QUALITY SCREENING · INDIAN LISTED COMPANIES</div>
<h1>Forensic Earnings-Quality Screener</h1>
<p>Decision support for forensic and credit-risk analysts: which listed Indian companies deserve an investigation this quarter, why, and what to check first. Six forensic tests and an AI anomaly detector feed one Forensic Priority Index.</p>
<span class="pill">📅 Data as of {stamp()[:10]}</span><span class="pill">🏢 {yr.ticker.nunique()} companies</span>
<span class="pill">✅ {len(all_scored)} scored (FY{fy})</span><span class="pill">🌐 Live sources: NSE · Yahoo Finance · Screener.in</span>
</div>""", unsafe_allow_html=True)

tdesk, t1, t2, t3, tai, tval, tmeth, tguide = st.tabs(["🎯 Decision desk", "📊 Triage board", "🏢 Company brief", "⚖️ Compare", "🤖 AI analyst", "🧪 Validation & cases", "📘 Method & data", "ℹ️ Guide"])
with tval:
    tdid, tcase = st.tabs(["🧪 History test & DiD", "📚 Case studies"])

# ------------------------------------------------------------------------------------------ TAB 0: START HERE
with tguide:
    section("What is this?", "A screening tool for a forensic / fraud analyst, who has far more companies than time to read every annual report.")
    callout("<b>The idea:</b> accounting manipulation leaves fingerprints in the numbers (profits without cash, receivables growing faster than sales, "
            "unnatural digit patterns). We measure six fingerprints for each company, combine them into a <b>0-100 risk score</b>, and rank companies so the analyst "
            "knows <b>whom to investigate first</b>. A high score is a reason to look closer, <b>never proof of fraud</b>.")

    section("How to use it: three steps")
    c1, c2, c3 = st.columns(3)
    c1.markdown('<div class="card"><h4><span class="num">1</span>Triage</h4><p>Start at <b>🎯 Decision desk</b>: the priority queue, alerts and recommended actions. <b>📊 Triage board</b> lists every company; use the sidebar to filter.</p></div>', unsafe_allow_html=True)
    c2.markdown('<div class="card"><h4><span class="num">2</span>Investigate</h4><p>Open <b>🏢 Company brief</b> to see <i>why</i> a company ranks where it does: tests that fired, peers, profit versus cash, closest twins and the full calculation.</p></div>', unsafe_allow_html=True)
    c3.markdown('<div class="card"><h4><span class="num">3</span>Explain and trust</h4><p><b>🤖 AI analyst</b> writes a memo and shows how AI was checked. <b>🧪 Validation &amp; cases</b> and <b>📘 Method &amp; data</b> show how reliable the screen is.</p></div>', unsafe_allow_html=True)

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
        "1. **🎯 Decision desk**: read the three boxes (who, problem, decision), then the priority queue. Which firms are marked Investigate, and why?\n"
        "2. **📊 Triage board**: in the sidebar set *Cohort* to **Watchlist**. Does the model flag the known-troubled firms? Switch *Rank by* between the priority index and the plain risk score.\n"
        "3. **🏢 Company brief**: choose **PC Jeweller**. Read the recommended action, see which Beneish bars rise above peers, then open *Show the calculation* to verify the M-score by hand.\n"
        "4. **⚖️ Compare**: keep the default firms and switch the metric to *Beneish M-score* or *CFO / Net income*.\n"
        "5. **🤖 AI analyst**: open a Claude-drafted memo and read the grounding check; then *How reliability was checked*.\n"
        "6. **Sidebar what-if**: open *Adjust model weights*, set *Distress* to 0, and watch the priority queue change. The score is a judgement, not a law of nature.\n"
        "7. **🧪 Validation & cases**: start with the history test (do high-accrual firms see profits fall afterwards?), then open a case such as *Café Coffee Day* or *Zee*.\n"
        "8. **📘 Method & data**: read the back-test and download the audit pack.\n"
        "9. **⟳ Refresh live data** (sidebar) re-downloads the latest statements from NSE and Yahoo Finance (about 3 minutes).")

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
| **DiD / triple DiD** | (Forensic use: does a red flag predict later trouble, or did a rule change earnings quality?) Compares the change in an exposed group with the change in a similar, unexposed comparison group; triple DiD adds a second split | Result only credible if pre-event trends were parallel (check the placebo) |
| **Forensic Priority Index (FPI)** | The new decision metric: 50% risk score + 25% share of tests in the red zone + 25% AI anomaly percentile | Higher = investigate sooner |
| **AI anomaly percentile** | How unusual a company's whole fingerprint is vs peers, from an unsupervised Isolation Forest | 90 or higher = statistical outlier |
| **Grounding check** | Automatic test that every number in an AI memo appears in the fact sheet | Any number not traced is flagged |
| **Altman Z″** | Bankruptcy-risk score (emerging-market version) | below 4.15 = distress, which raises the incentive to manipulate |
""")
    callout("<b>Important:</b> this is a screening tool for triage, not a verdict engine. Flags can have innocent explanations (mergers, demergers, new accounting standards, one-off items). "
            "Never treat a flag as proof of wrongdoing; the AI memos list benign explanations to check first.", "warn")

# ------------------------------------------------------------------------------------------ TAB: DECISION DESK
ACT_COL = {"Investigate": "#08306b", "Review": "#2171b5", "Monitor": "#6baed6", "Routine": "#c6dbef", "Not scored": "#d1d5db", "Insufficient data": "#d1d5db"}
snm = lambda n: str(n).replace(" Limited", "").replace(" Ltd.", "")
with tdesk:
    sv = view[view.score_w.notna()].sort_values("fpi_w", ascending=False)
    counts = view.action.value_counts()
    st.markdown('''<div class="trio">
<div class="cell"><div class="k">WHO USES THIS</div>A forensic or credit-risk analyst at a lender, audit firm or investor, covering listed Indian companies.</div>
<div class="cell"><div class="k">THE PROBLEM</div>Hundreds of filings, a few analyst-days. Reported profit can hide weak cash backing, aggressive accruals or distress, and any single ratio gives false alarms.</div>
<div class="cell"><div class="k">THE DECISION</div><b>Which companies get a forensic review this quarter, and what to check first.</b></div></div>''', unsafe_allow_html=True)
    st.caption(f"**What you are looking at:** {len(view)} listed Indian companies (FY{fy}), each run through six forensic tests and an AI anomaly detector, then ranked by the **Forensic Priority Index (FPI)**. Filters on the left apply to every page.")

    section("1 · How is the universe doing?", "Where each company lands after the tests, the AI detector and the action rules.")
    kp = [("🔴 Investigate", counts.get("Investigate", 0), D.MEANING["Investigate"]), ("🟠 Review", counts.get("Review", 0), D.MEANING["Review"]), ("🟡 Monitor", counts.get("Monitor", 0), D.MEANING["Monitor"]),
          ("🟢 Routine", counts.get("Routine", 0), D.MEANING["Routine"]), ("⚪ Not scored", counts.get("Not scored", 0) + counts.get("Insufficient data", 0), "Banks, NBFCs, insurers (different business model) and firms with missing data")]
    st.markdown('<div class="kpis">' + "".join(f'<div class="k1" title="{t}"><div class="l">{l}</div><div class="v">{int(v)}</div></div>' for l, v, t in kp) + "</div>", unsafe_allow_html=True)

    if sv.empty:
        callout("No scored companies match the current filters. Widen the sidebar filters.", "warn")
    else:
        section("2 · Where are the risks?", "The ten highest-priority companies, and which sectors concentrate the risk.")
        a, b = st.columns([3, 2])
        top8 = sv.head(10).iloc[::-1]
        f = go.Figure(go.Bar(x=top8.fpi_w, y=[snm(n) for n in top8.name], orientation="h", marker_color=[ACT_COL[x] for x in top8.action], text=top8.action, textposition="inside",
                             insidetextfont=dict(color="white", size=11), customdata=np.c_[top8.score_w.round(0), top8.red_n, top8.red_of, top8.anomaly_pct.round(0)],
                             hovertemplate="<b>%{y}</b><br>Priority index %{x:.0f}<br>Risk score %{customdata[0]} · %{customdata[1]:.0f} of %{customdata[2]:.0f} tests red · AI outlier percentile %{customdata[3]}<extra></extra>"))
        f.update_layout(title="Top 10 by Forensic Priority Index", xaxis_title="Priority index (0–100)")
        a.plotly_chart(style(f, 400), width="stretch", config=PCFG)
        a.caption("**How to read:** longer bar = higher investigation priority. The label inside each bar is the recommended action.")
        hs = sv.groupby("sector").fpi_w.agg(["mean", "count"]); hs = hs[hs["count"] >= 2].sort_values("mean")
        if len(hs):
            f = go.Figure(go.Bar(x=hs["mean"], y=hs.index, orientation="h", marker_color=BLUE, text=[f"n={int(c)}" for c in hs["count"]], textposition="outside"))
            f.update_layout(title="Average priority index by sector", xaxis=dict(range=[0, max(100, hs['mean'].max() + 15)], title="Average priority index"))
            b.plotly_chart(style(f, 400), width="stretch", config=PCFG)
            b.caption("**How to read:** sectors with at least two scored firms. A high bar means the whole sector carries more red flags.")

        section("3 · What deserves investigation first?", "Your queue: highest priority first, with the reason and the first documents to check.")
        cap = st.slider("Reviews your team can take on this quarter", 3, 20, 8, key="cap", help="Sets the length of your investigation list below")
        q = sv.head(cap).copy(); q["Action"] = q.action.map(lambda x: f"{D.ICON[x]} {x}")
        q = q.rename(columns={"name": "Company", "fpi_w": "Priority index", "why": "Why", "first": "Check first"})[["Company", "Action", "Priority index", "Why", "Check first"]]
        st.dataframe(q, hide_index=True, width="stretch", height=min(390, 38 * len(q) + 40), column_config={"Priority index": st.column_config.ProgressColumn("Priority index", min_value=0, max_value=100, format="%.0f"),
                     "Why": st.column_config.TextColumn(width="medium"), "Check first": st.column_config.TextColumn(width="large")})
        callout(f"<b>Your investigation list for this quarter ({cap} reviews):</b> " + ", ".join(snm(n) for n in q["Company"]) + ". Everything below the cut-off stays on desk review or monitoring.", "good")
        st.caption("Open **🏢 Company brief** for the full evidence on any firm, and **🤖 AI analyst** for a written memo.")

        section("4 · What should I do?", "The action bands turn the priority index into a decision. Each company gets exactly one action.")
        nm = lambda a_: ", ".join(snm(n) for n in sv[sv.action == a_].name.head(4)) + ("…" if (sv.action == a_).sum() > 4 else "") or "none"
        st.markdown(f'''<div class="acts">
<div class="a"><b class="t">🔴 Investigate · <span class="n">{int(counts.get("Investigate", 0))}</span></b>{D.MEANING["Investigate"]}<br><i style="color:#6b7280">{nm("Investigate")}</i></div>
<div class="a"><b class="t">🟠 Review · <span class="n">{int(counts.get("Review", 0))}</span></b>{D.MEANING["Review"]}<br><i style="color:#6b7280">{nm("Review")}</i></div>
<div class="a"><b class="t">🟡 Monitor · <span class="n">{int(counts.get("Monitor", 0))}</span></b>{D.MEANING["Monitor"]}<br><i style="color:#6b7280">{nm("Monitor")}</i></div>
<div class="a"><b class="t">🟢 Routine · <span class="n">{int(counts.get("Routine", 0))}</span></b>{D.MEANING["Routine"]}<br><i style="color:#6b7280">{nm("Routine")}</i></div></div>''', unsafe_allow_html=True)
        st.caption("**Rule:** the action follows the priority index: **65 or more = Investigate, 50 to 65 = Review, 35 to 50 = Monitor, below 35 = Routine.** The index already blends the risk score, how many tests agree, and the AI outlier percentile.")

        section("5 · What changed since last year?", "Alerts generated automatically from year-on-year movements.")
        al = alerts_df[alerts_df.ticker.isin(view.ticker)] if len(alerts_df) else alerts_df
        if len(al):
            n_hi = int((al.severity == "High").sum())
            show = al.copy(); show["Severity"] = show.severity.map({"High": "🔴 High", "Medium": "🟠 Medium", "Low": "⚪ Low"})
            show = show.rename(columns={"name": "Company", "alert": "Alert", "action": "Suggested action"})[["Severity", "Company", "Alert", "Suggested action"]]
            st.dataframe(show.head(8), hide_index=True, width="stretch", height=330)
            with st.expander(f"All {len(al)} alerts"):
                st.dataframe(show, hide_index=True, width="stretch")
        else:
            n_hi = 0; st.info("No alerts for the current selection.")

        clean = sv[(sv.action == "Routine") & (sv.red_n == 0)].sort_values("fpi_w").head(5)
        if len(clean): callout("<b>Where effort can be saved:</b> the cleanest earnings profiles (no test in the red zone) are " + ", ".join(snm(n) for n in clean.name) + ". Routine monitoring is enough.", "good")

        out = sv[sv.anomaly_pct >= 90]; dis = out[out.tier_w.isin(["Low", "Moderate"])]; t1_ = sv.iloc[0]
        brief = (f"In FY{fy}, <b>{int(counts.get('Investigate', 0) + counts.get('Review', 0))}</b> of {len(sv)} scored companies need action: <b>{int(counts.get('Investigate', 0))}</b> to investigate and <b>{int(counts.get('Review', 0))}</b> for desk review. "
                 f"<b>{snm(t1_['name'])}</b> leads the queue (priority index {t1_.fpi_w:.0f}; {int(t1_.red_n)} of {int(t1_.red_of)} tests in the red zone"
                 + (f"; unusual on {t1_.anomaly_drivers}" if isinstance(t1_.anomaly_drivers, str) and t1_.anomaly_drivers else "") + "). "
                 + (f"The AI detector rates <b>{len(out)}</b> companies as statistical outliers; <b>{len(dis)}</b> of them ({', '.join(snm(n) for n in dis.name.head(3))}) score only Low or Moderate on the rules, so they deserve a second look. " if len(out) and len(dis) else "")
                 + f"There are <b>{n_hi}</b> high-severity alerts versus last year. Treat this as triage and confirm with documents before concluding anything.")
        callout("<b>🤖 AI briefing (auto-generated from the numbers above):</b> " + brief)
        st.caption("The priority index = 50% risk score + 25% share of tests in the red zone + 25% AI anomaly percentile. See *Method & data* for the formula and its back-test.")

# ------------------------------------------------------------------------------------------ TAB 1
with t1:
    section("Triage board", f"All companies ranked for FY{fy}. Rank by the Forensic Priority Index (risk score + agreement between tests + AI anomaly) or by the plain risk score.")
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
        rank_by = st.radio("Rank by", ["Forensic Priority Index", "Risk score"], horizontal=True, key="rank_by")
        rk, rk_lab = ("fpi_w", "Forensic Priority Index") if rank_by.startswith("Forensic") else ("score_w", "Risk score")
        n = st.slider("Show top N companies", 5, max(6, len(scored_tier)), min(20, max(6, len(scored_tier))))
        top = scored_tier.sort_values(rk, ascending=False).head(n).iloc[::-1]
        fig = go.Figure(go.Bar(x=top[rk], y=top.ticker.str.replace(".NS", ""), orientation="h",
                               marker_color=[TIER_COL[str(t)] for t in top.tier_w],
                               marker_line=dict(color=[COH_COL[x] for x in top.cohort], width=2),
                               customdata=np.c_[top.name, top.tier_w, top.cohort, top.MScore.round(2)],
                               hovertemplate="<b>%{customdata[0]}</b><br>Score %{x:.0f} (%{customdata[1]})<br>%{customdata[2]} · Beneish %{customdata[3]}<extra></extra>"))
        fig.update_layout(title=rk_lab, xaxis_title=rk_lab + " (0–100)")
        st.plotly_chart(style(fig, max(320, 22 * len(top) + 80)), width="stretch", config=PCFG)
        st.caption("**How to read:** longer bar = more red flags. Bar **fill** shows the risk tier (darker = higher). Bar **outline** shows the cohort (blue = Nifty 50, orange = Watchlist).")

        a, b = st.columns(2)
        sc_df = scored.dropna(subset=["MScore", "sloan"])
        f2 = px.scatter(sc_df, x="MScore", y="sloan", color="cohort", color_discrete_map=COH_COL, hover_name="name",
                        hover_data={"score_w": ":.0f", "cohort": False}, labels={"MScore": "Beneish M-score", "sloan": "Sloan accrual ratio", "cohort": "Cohort"})
        f2.add_vline(x=-1.78, line_dash="dash", line_color=MUTED, annotation_text="manipulator −1.78")
        f2.add_hline(y=0.1, line_dash="dot", line_color=MUTED)
        f2.update_traces(marker=dict(size=10, line=dict(color="white", width=1.5)))
        f2.update_layout(title="Earnings-manipulation map")
        a.plotly_chart(style(f2), width="stretch", config=PCFG)
        a.caption("**How to read:** each dot is a company. **Upper right** = both Beneish and accruals look worrying (right of the dashed line = Beneish flags it; high up = profit not backed by cash).")
        cnt = scored.groupby(["tier_w", "cohort"], observed=False).size().reset_index(name="n")
        f3 = px.bar(cnt, x="tier_w", y="n", color="cohort", barmode="group", color_discrete_map=COH_COL,
                    category_orders={"tier_w": TIERS}, labels={"tier_w": "Risk tier", "n": "Companies", "cohort": "Cohort"})
        f3.update_layout(title="How many companies in each tier")
        b.plotly_chart(style(f3), width="stretch", config=PCFG)
        b.caption("**How to read:** if the model works, the orange Watchlist bars should lean towards the higher tiers.")

    section("Triage table", "Sortable (click a column header). Default order: highest Forensic Priority Index first.")
    d = view.copy(); d["Action"] = d.action.map(lambda x: f"{D.ICON[x]} {x}"); d["Tests red"] = [("" if pd.isna(a_) else f"{int(a_)} of {int(b_)}") for a_, b_ in zip(d.red_n, d.red_of)]
    tbl = d.sort_values("fpi_w", ascending=False)[["name", "sector", "cohort", "Action", "fpi_w", "score_w", "Tests red", "anomaly_pct", "MScore", "sloan", "cfo_cum_ni", "Altman", "benford_label"]].rename(
        columns={"name": "Company", "sector": "Sector", "cohort": "Cohort", "fpi_w": "Priority index", "score_w": "Risk score", "anomaly_pct": "AI outlier %ile", "MScore": "Beneish M", "sloan": "Sloan accruals",
                 "cfo_cum_ni": "CFO/NI (3y)", "Altman": "Altman Z″", "benford_label": "Benford"})
    st.dataframe(tbl, width="stretch", hide_index=True, height=420, column_config={
        "Priority index": st.column_config.ProgressColumn("Priority index", min_value=0, max_value=100, format="%.0f", help="50% risk score + 25% share of tests in red zone + 25% AI anomaly percentile"),
        "Risk score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.0f"),
        "AI outlier %ile": st.column_config.NumberColumn(format="%.0f", help="How unusual the firm's whole fingerprint is vs peers (Isolation Forest). 90+ = outlier"),
        "Beneish M": st.column_config.NumberColumn(format="%.2f", help="Above −1.78 = likely manipulator"),
        "Sloan accruals": st.column_config.NumberColumn(format="%.3f", help="Profit not backed by cash, scaled by assets"),
        "CFO/NI (3y)": st.column_config.NumberColumn(format="%.2f", help="Below ~0.8 = profits not turning into cash"),
        "Altman Z″": st.column_config.NumberColumn(format="%.1f", help="Below 4.15 = distress zone")})
    st.download_button("⬇ Download table (CSV)", tbl.to_csv(index=False), f"forensic_triage_FY{fy}.csv")
    if view.fin.any():
        callout(f"{int(view.fin.sum())} financial-sector firms (banks, NBFCs, insurers) are <b>not scored</b>: these tests assume receivables, inventory and an operating cycle. "
                "This is a deliberate design choice, not missing data.")

# ------------------------------------------------------------------------------------------ TAB 2
with t2:
    section("Company brief", "Pick a company to see why it ranks where it does, what to do about it, and the evidence behind every number.")
    opts = view.sort_values("name")
    label = {r_.ticker: f"{r_['name']} ({r_.ticker.replace('.NS', '')})" for _, r_ in opts.iterrows()}
    if not label:
        callout("No companies match the sidebar filters.", "warn")
    else:
        keys = list(label)
        tk = st.selectbox("Company", keys, format_func=label.get, index=keys.index("PCJEWELLER.NS") if "PCJEWELLER.NS" in keys else 0, key="brief_co")
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

            act, why_, first_ = D.action_for(r)
            st.markdown(f'<div class="verdict" style="border-left-color:{ACT_COL.get(act, "#9ca3af")}"><div class="big">{D.ICON[act]} Recommended action: {act}</div><div>{D.MEANING[act]} <i>Why:</i> {why_}.<br><b>Check first:</b> {first_}.</div></div>', unsafe_allow_html=True)
            c = st.columns(6)
            c[0].metric("Risk score", "n/a" if pd.isna(r.score_w) else f"{r.score_w:.0f}/100", None if pd.isna(r.score_w) else str(r.tier_w), delta_color="off")
            c[1].metric("Beneish M", "n/a" if pd.isna(r.MScore) else f"{r.MScore:.2f}", {"Likely manipulator": "Flag", "Watch": "Watch", "Unlikely": "Clear"}.get(r.MScore_flag, r.MScore_flag) if pd.notna(r.MScore) else None, delta_color="off", help="Above −1.78 = likely manipulator (Flag); −2.22 to −1.78 = Watch; below −2.22 = Clear")
            c[2].metric("Altman Z″", "n/a" if pd.isna(r.Altman) else f"{r.Altman:.1f}", None if pd.isna(r.Altman) else str(r.Altman_zone), delta_color="off", help="Bankruptcy-risk score; below 4.15 = distress")
            c[3].metric("Benford", "n/a" if pd.isna(r.benford_mad) else str(r.benford_label), f"MAD {r.benford_mad:.4f}" if pd.notna(r.benford_mad) else None, delta_color="off", help="Do leading digits follow the natural pattern?")
            c[4].metric("CFO / NI (3-yr)", "n/a" if pd.isna(r.cfo_cum_ni) else f"{r.cfo_cum_ni:.2f}", help="Operating cash flow ÷ net income. Well below 1 = profit not turning into cash")
            c[5].metric("Priority index", "n/a" if pd.isna(r.fpi_w) else f"{r.fpi_w:.0f}/100", None if pd.isna(r.anomaly_pct) else f"AI outlier {r.anomaly_pct:.0f}th pct", delta_color="off", help="50% risk score + 25% share of tests in red zone + 25% AI anomaly percentile")

            a, b = st.columns(2)
            comps = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI"]
            med = peers[comps].median()
            f = go.Figure()
            f.add_bar(name="This company", x=comps, y=[r[k] for k in comps], marker_color=BLUE)
            f.add_bar(name="Peer median", x=comps, y=med.values, marker_color="#cbd5e1")
            f.add_hline(y=1, line_dash="dot", line_color=MUTED, annotation_text="1.0 = no change")
            f.update_layout(title="Beneish indices vs peers", barmode="group")
            a.plotly_chart(style(f), width="stretch", config=PCFG)
            a.caption("**How to read:** each bar is a year-on-year change. Above the dotted **1.0** line = deteriorating. Blue well above grey = this firm is worse than peers on that test (see the *Guide* tab).")
            f = go.Figure()
            usd = str(r.get("currency")) == "USD"; div, unit = (1e6, "USD million") if usd else (1e7, "₹ crore")
            f.add_bar(name="Net income", x=hist.fy, y=hist.ni / div, marker_color=BLUE)
            f.add_bar(name="Operating cash flow", x=hist.fy, y=hist.cfo / div, marker_color=ORANGE)
            f.update_layout(title=f"Profit vs cash ({unit})", barmode="group", xaxis=dict(dtick=1))
            b.plotly_chart(style(f), width="stretch", config=PCFG)
            b.caption("**How to read:** healthy firms turn profit into cash, so the two bars are similar. A persistent gap (blue much taller than orange) is a classic red flag.")

            a, b = st.columns(2)
            d_ = bdig[bdig.ticker == tk]
            if len(d_):
                f = go.Figure()
                f.add_bar(name="Observed", x=d_.digit, y=d_.observed * 100, marker_color=BLUE)
                f.add_scatter(name="Benford expected", x=d_.digit, y=d_.expected * 100, mode="lines+markers", line=dict(color=INK, width=2))
                f.update_layout(title="Benford first-digit test", xaxis=dict(dtick=1, title="Leading digit"), yaxis_title="% of numbers")
                a.plotly_chart(style(f), width="stretch", config=PCFG)
                a.caption("**How to read:** bars should follow the black line (about 30% of natural numbers start with 1). Big gaps hint at unnatural numbers, but this is a weak signal on its own.")
            comp_cols = {k: r["s_" + k] for k in WEIGHTS}
            f = go.Figure(go.Bar(y=list(comp_cols), x=[0 if pd.isna(v) else v for v in comp_cols.values()], orientation="h", marker_color=BLUE,
                                 text=["n/a" if pd.isna(v) else f"{v:.0f}" for v in comp_cols.values()], textposition="outside"))
            f.update_layout(title="What drives the score", xaxis=dict(range=[0, 110]), yaxis=dict(autorange="reversed"))
            b.plotly_chart(style(f), width="stretch", config=PCFG)
            b.caption("**How to read:** the six building blocks, each 0 (benign) to 100 (worst). The score is their weighted average (weights are adjustable in the sidebar).")

            with st.expander("Ratios over time (DuPont, liquidity, leverage, quality)"):
                show = hist.set_index("fy")[["net_margin", "asset_turn", "equity_mult", "roe", "roce", "current_ratio", "de_ratio", "int_cover", "dso", "dio", "MScore", "sloan", "DA"]].T
                show.index = ["Net margin", "Asset turnover", "Equity multiplier", "ROE", "ROCE", "Current ratio", "Debt / equity", "Interest cover", "Receivable days", "Inventory days", "Beneish M", "Sloan accruals", "Jones DA"]
                st.dataframe(show.round(3), width="stretch")
                st.caption("ROE = net margin × asset turnover × equity multiplier (DuPont). Missing values mean the line item is not reported for that company.")

            section("Closest financial twins", "Companies with the most similar forensic fingerprint (nearest-neighbour matching): the fairest comparison group.")
            FEAT = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA", "sloan", "DA", "REM", "lev", "roa", "cfo_cum_ni"]
            fx = peers[peers.score_w.notna()].set_index("ticker").copy(); fx["lev"] = fx.debt / fx.ta; fx["roa"] = fx.ni / fx.ta
            X_ = fx[FEAT].replace([np.inf, -np.inf], np.nan); X_ = X_.clip(X_.quantile(.05), X_.quantile(.95), axis=1); Z_ = ((X_ - X_.mean()) / X_.std()).fillna(0)
            if tk in Z_.index:
                dist = (((Z_ - Z_.loc[tk]) ** 2).sum(axis=1) ** .5).drop(tk).nsmallest(3)
                tw = fx.loc[dist.index, ["name", "sector", "fpi_w", "action"]].reset_index(drop=True).assign(Distance=dist.round(2).values)
                tw["action"] = tw.action.map(lambda x: f"{D.ICON[x]} {x}")
                st.dataframe(tw.rename(columns={"name": "Company", "sector": "Sector", "fpi_w": "Priority index", "action": "Action", "Distance": "Distance (smaller = more alike)"}), hide_index=True, width="stretch",
                             column_config={"Priority index": st.column_config.NumberColumn(format="%.0f")})
            else:
                st.caption("Twins are available for scored non-financial companies.")

            with st.expander("🔍 Show the calculation: Beneish M-score, step by step"):
                rp_ = hist[hist.fy == fy - 1]
                if bool(r.fin) or rp_.empty or pd.isna(r.MScore):
                    st.info("Needs a scored non-financial company with the previous year's statements.")
                else:
                    p_ = rp_.iloc[0]; dv = 1e6 if usd else 1e7; un = "USD m" if usd else "₹ crore"
                    nm_ = {"sales": "Sales", "cogs": "Cost of sales", "sga": "SG&A", "dep": "Depreciation", "recv": "Receivables", "ppe": "Net PPE", "ca": "Current assets", "ta": "Total assets",
                           "cl": "Current liabilities", "ltd": "Long-term debt", "ni": "Net income", "cfo": "Operating cash flow"}
                    st.dataframe(pd.DataFrame({"Input": list(nm_.values()), f"FY{fy - 1} ({un})": [p_[k] / dv for k in nm_], f"FY{fy} ({un})": [r[k] / dv for k in nm_]}).round(1), hide_index=True, width="stretch")
                    sd = lambda a, b: a / b if b not in (0, None) and pd.notna(b) and pd.notna(a) else np.nan
                    idx_ = {"DSRI": sd(sd(r.recv, r.sales), sd(p_.recv, p_.sales)), "GMI": sd(sd(p_.sales - p_.cogs, p_.sales), sd(r.sales - r.cogs, r.sales)),
                            "AQI": sd(1 - sd(r.ca + r.ppe, r.ta), 1 - sd(p_.ca + p_.ppe, p_.ta)), "SGI": sd(r.sales, p_.sales),
                            "DEPI": sd(sd(p_.dep, p_.dep + p_.ppe), sd(r.dep, r.dep + r.ppe)), "SGAI": sd(sd(r.sga, r.sales), sd(p_.sga, p_.sales)),
                            "LVGI": sd(sd(r.cl + r.ltd, r.ta), sd(p_.cl + p_.ltd, p_.ta)), "TATA": sd(r.ni - r.cfo, r.ta)}
                    meaning = {"DSRI": "Receivables vs sales", "GMI": "Gross-margin deterioration", "AQI": "Share of assets that are not cash/plant", "SGI": "Sales growth", "DEPI": "Depreciation rate slowing",
                               "SGAI": "Overheads vs sales", "LVGI": "Leverage change", "TATA": "Accruals: (profit − operating cash) ÷ assets"}
                    coef = {"DSRI": 0.920, "GMI": 0.528, "AQI": 0.404, "SGI": 0.892, "DEPI": 0.115, "SGAI": -0.172, "LVGI": -0.327, "TATA": 4.679}
                    used_ = {k: (0.0 if k == "TATA" else 1.0) if pd.isna(v) else float(np.clip(v, -0.5, 0.5) if k == "TATA" else np.clip(v, 0.2, 5)) for k, v in idx_.items()}
                    m_calc = -4.84 + sum(coef[k] * used_[k] for k in coef)
                    st.dataframe(pd.DataFrame({"Index": list(idx_), "Meaning": [meaning[k] for k in idx_], "Value": [idx_[k] for k in idx_], "Used (capped)": [used_[k] for k in idx_],
                                               "Coefficient": [coef[k] for k in idx_], "Contribution": [coef[k] * used_[k] for k in idx_]}).round(3), hide_index=True, width="stretch")
                    ok_ = abs(m_calc - r.MScore) < 1e-6
                    st.markdown(f"**M = −4.84 + Σ contributions = {m_calc:.3f}**  ·  engine value {r.MScore:.3f}  ·  " + ("✅ recalculation matches" if ok_ else "⚠️ differs (a missing index was set to neutral)"))
                    st.caption("Any index that cannot be computed is set to neutral (1, or 0 for TATA); indices are capped to [0.2, 5] and TATA to [−0.5, 0.5]. Flag if M is above −1.78.")

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
    st.plotly_chart(style(f, 420), width="stretch", config=PCFG)
    st.caption("**How to read:** compare bars within a year to see who is better or worse, and across years to see the trend. For Beneish, Sloan, Jones, REM and Risk score, **higher = worse**. For Altman, CFO/NI and margins, **higher = healthier**.")
    if pick:
        st.dataframe(mall[mall.ticker.isin(pick)].pivot(index="name", columns="fy", values=col).round(3), width="stretch")

# ------------------------------------------------------------------------------------------ TAB: DiD LAB
with tdid:
    section("Back-test & difference-in-differences", "Validate the red flags, and measure whether an event or rule changed earnings quality for exposed firms.")
    callout("<b>In plain English:</b> this tab uses history to answer two questions. <b>(1) Do the red flags actually work?</b> When a company is flagged, does its profitability really get worse afterwards? "
            "<b>(2) Did a specific event matter?</b> For example, a rule change or a shock: did earnings quality change for the firms it hit? "
            "Both compare a group of firms with a comparison group, before and after. That 'difference between two differences' is called <b>difference-in-differences (DiD)</b>. "
            "It describes groups of firms; it does <u>not</u> tell you whether one company cheated.")
    dbt, d2 = st.tabs(["1️⃣ Do the red flags work? (history test)", "2️⃣ Did an event matter? (event study)"])

    with dbt:
        if panel is None:
            callout("The 10-year Screener panel (data/screener_long.csv) is not available in this deployment.", "warn")
        else:
            section("Do the red flags actually work?", "A history test of the screener's own warning signs, using about 10 years of data.")
            st.markdown(
                "**The question.** If a company's profits look good but are not backed by cash (a red flag), does its profitability really get worse afterwards?\n\n"
                "**How we test it, in three steps**\n"
                "1. **Flag.** Every year, mark the companies that show the red flag (for example, the 20% with the highest accruals, i.e. profit least backed by cash).\n"
                "2. **Follow.** Track each flagged company's profitability for the next 1 to 3 years.\n"
                "3. **Compare.** Compare with companies that were *not* flagged in the same year. If flagged companies do clearly worse afterwards, the flag is a useful early warning.")
            with st.expander("Plain-English glossary for this test"):
                st.markdown("- **Accruals:** the part of profit that is *not* backed by cash. Large accruals mean profit is running ahead of cash.\n"
                            "- **ROA (return on assets):** profit ÷ total assets. A simple measure of how profitable the business is.\n"
                            "- **pp (percentage points):** a drop in ROA from 8% to 6.5% is 1.5 pp.\n"
                            "- **Flag year:** the year a company is flagged. Year 0 on the chart.\n"
                            "- **Why DiD?** We compare the *change* for flagged companies with the *change* for the others. Using changes removes effects that hit every company alike, such as a boom or recession.\n"
                            "- **Clear / not clear:** whether the gap is big enough relative to normal ups and downs to trust (statisticians call this the t-value; about 2 or more is 'clear').")
            q1, q2 = st.columns(2)
            fl = q1.selectbox("1. Which red flag?", list(A.FLAGS), key="bt_flag", help="High accruals = profit running ahead of cash. Weak cash conversion = operating cash flow below 60% of net income.")
            ocb = q2.selectbox("2. What to track afterwards?", ["Return on assets", "Net margin (profit / sales)", "Operating cash flow / sales"], key="bt_out",
                               help="For the first two, a working flag should be followed by a FALL. For operating cash flow, a working accrual flag is followed by a RISE as cash catches up with earlier profit.")
            colb = A.OUT[ocb][0]
            BT = A.flag_backtest(panel, A.FLAGS[fl], colb)
            if BT is None or not BT["stats"]:
                callout("Not enough flagged firm-years for this combination.", "warn")
            else:
                st1, st2 = BT["stats"].get(1), BT["stats"].get(2)
                clarity = lambda t: "Clear difference" if abs(t) >= 2 else ("Suggestive" if abs(t) >= 1.5 else "Not clear")
                short = {"Return on assets": "ROA", "Net margin (profit / sales)": "net margin", "Operating cash flow / sales": "cash flow margin"}[ocb]
                k = st.columns(4)
                if st1:
                    k[0].metric(f"Extra change in {short}, 1 year later", f"{st1['beta'] * 100:+.2f} pp", clarity(st1["beta"] / st1["se"]), delta_color="off",
                                help="How much more (+) or less (-) the outcome moved for flagged companies than for unflagged ones, one year after the flag. "
                                     f"Statistical t-value = {st1['beta'] / st1['se']:.1f}.")
                    k[1].metric("Likely range (95%)", f"{(st1['beta'] - 1.96 * st1['se']) * 100:+.1f} to {(st1['beta'] + 1.96 * st1['se']) * 100:+.1f} pp", help="The true gap probably lies in this range. If it stays on one side of zero, the effect is clear.")
                if st2: k[2].metric(f"Extra change, 2 years later", f"{st2['beta'] * 100:+.2f} pp", clarity(st2["beta"] / st2["se"]), delta_color="off")
                if st1: k[3].metric("Flagged cases tested", f"{st1['n_flag']}", f"from {st1['firms']} companies", delta_color="off", help="Each case is one company in one year.")
                cv = BT["curves"].copy(); cv["mean"] = cv["mean"] * 100
                f = go.Figure()
                for flg, nm, colr in [(True, "Flagged companies", ORANGE), (False, "Not flagged", BLUE)]:
                    z = cv[cv.flag == flg].sort_values("k")
                    f.add_scatter(x=z.k, y=z["mean"], mode="lines+markers", name=nm, line=dict(color=colr, width=3), marker=dict(size=9))
                f.add_vline(x=0, line_dash="dot", line_color=MUTED, annotation_text="flag year", annotation_position="top left")
                f.add_hline(y=0, line_color=GRID)
                f.update_layout(title=f"What happened to {short} before and after the flag", xaxis=dict(dtick=1, title="Years since the flag year (0 = the year of the flag)"),
                                yaxis_title=f"Change in {short} vs flag year (pp)")
                st.plotly_chart(style(f, 380), width="stretch", config=PCFG)
                st.caption("**How to read:** the chart shows the average movement of each group relative to the flag year (0). If the orange line moves away from the blue line after year 0, "
                           "flagged companies behaved differently from the rest once flagged.")
                if st1:
                    tt = st1["beta"] / st1["se"]
                    expect_neg = colb in ("roa", "net_margin")
                    right = (st1["beta"] < 0) if expect_neg else (st1["beta"] > 0)
                    direction = "lower" if st1["beta"] < 0 else "higher"
                    msg = (f"<b>Result:</b> one year after being flagged, flagged companies' {short} ended up <b>{abs(st1['beta']) * 100:.2f} percentage points {direction}</b> "
                           f"than that of unflagged companies ({st1['n_flag']} cases from {st1['firms']} companies). ")
                    if abs(tt) >= 2 and right:
                        callout(msg + "<b>In other words:</b> " + ("the flag was a useful early warning: profitability tended to weaken afterwards." if expect_neg else "cash flow tended to catch up afterwards, as earlier accrual-driven profit reversed."), "good")
                    elif abs(tt) >= 2:
                        callout(msg + "<b>In other words:</b> this is the <b>opposite</b> of what a working red flag predicts, so be cautious about relying on it.", "warn")
                    else:
                        callout(msg + "<b>In other words:</b> the gap is <b>not clear enough</b> to call this flag a reliable early warning in this sample.")
            callout("<b>Read with care:</b> (1) the sample is small and large-cap (Nifty 50 plus a watchlist); (2) flagged companies had often just had an unusually good year, so some fall afterwards would happen anyway "
                    "('mean reversion'); (3) this shows a flag is <i>informative</i>, not that any flagged company manipulated its numbers.", "warn")
            callout("<b>So what for the analyst:</b> treat these flags as early warnings that reported earnings may not last. That matters for lending, valuation and audit planning. Then confirm with documents.", "good")

    with d2:
        if panel is None:
            callout("The 10-year Screener panel (data/screener_long.csv) is not available in this deployment.", "warn")
        else:
            nfu = uni[uni.sector != "Financial Services"]
            n50 = nfu[nfu.cohort == "Nifty 50"]
            sec_t = lambda secs: list(n50[n50.sector.isin(secs)].ticker)
            allnf = list(n50.ticker)
            PRESETS = {
                "COVID-19 shock (event FY2021)": dict(
                    t=sec_t(["Consumer Cyclical", "Industrials"]), c=sec_t(["Technology", "Healthcare", "Consumer Defensive"]), out="Sales growth", ev=2021, pre=4, post=1,
                    note="Exposed: consumer-cyclical and industrial firms (autos, travel, retail, capital goods). Comparison: IT, pharma and staples that kept trading. FY2021 = year ended March 2021."),
                "Corporate tax cut, Sept 2019 (event FY2020)": dict(
                    t=sec_t(["Consumer Cyclical", "Consumer Defensive", "Industrials", "Utilities", "Basic Materials"]), c=sec_t(["Technology", "Healthcare"]), out="Net margin (profit / sales)", ev=2020, pre=4, post=1,
                    note="Tests whether domestic-facing firms gained relative to exporters. We only have sectors as a proxy for domestic revenue share, and many firms did not switch to the lower rate, so expect a weak signal."),
                "Hindenburg report on the Adani group, Jan 2023 (event FY2024)": dict(
                    t=["ADANIENT.NS", "ADANIPORTS.NS"], c=[t for t in allnf if t not in ("ADANIENT.NS", "ADANIPORTS.NS")], out="Debt / assets", ev=2024, pre=4, post=3,
                    note="Only two exposed firms, so this is descriptive, not statistical. The allegations were contested; this tests nothing about wrongdoing, only whether financing ratios moved differently."),
                "Custom (choose your own)": dict(t=[], c=allnf, out="Accruals / lagged assets", ev=2021, pre=4, post=2, note="<b>Forensic use:</b> choose firms hit by an event (an enforcement action, a rule change, a fraud disclosure in their sector) as exposed, similar firms as comparison, and track <b>accruals</b> or <b>CFO / net income</b> to see whether earnings quality changed."),
            }
            st.caption("The first three events are illustrations of the method. For forensic work, use *Custom* and track accruals or cash conversion.")
            pn = st.selectbox("Choose an event", list(PRESETS), key="ev_preset"); P0 = PRESETS[pn]; kk = str(abs(hash(pn)) % 10 ** 6)
            callout(P0["note"])
            lab_t = dict(zip(uni.ticker, uni.name)); fmt = lambda t: lab_t.get(t, t)
            g1, g2 = st.columns(2)
            treated = g1.multiselect("Exposed firms (hit by the event)", list(nfu.ticker), default=P0["t"], format_func=fmt, key="ev_t" + kk)
            control = g2.multiselect("Comparison firms (similar, not hit)", list(nfu.ticker), default=P0["c"], format_func=fmt, key="ev_c" + kk)
            o1, o2, o3, o4 = st.columns(4)
            outc = o1.selectbox("Outcome", list(A.OUT), index=list(A.OUT).index(P0["out"]), key="ev_o" + kk)
            ev = o2.slider("Event fiscal year", 2012, 2025, P0["ev"], key="ev_y" + kk, help="First fiscal year (ending March) affected by the event")
            pre = o3.slider("Years before", 2, 6, P0["pre"], key="ev_p" + kk)
            post = o4.slider("Years after", 1, 4, P0["post"], key="ev_q" + kk)
            col, unit = A.OUT[outc]; sc_ = 100 if unit == "pp" else 1; ul = "pp" if unit == "pp" else "×"
            overlap = set(treated) & set(control)
            if not treated or not control:
                callout("Choose at least one exposed and one comparison firm.", "warn")
            elif overlap:
                callout("A firm cannot be both exposed and a comparison firm. Remove: " + ", ".join(fmt(t) for t in overlap), "warn")
            else:
                R = A.did_estimate(panel, treated, control, col, ev, pre, post)
                if R is None:
                    callout("Not enough data for this combination (each firm needs at least one year before and one after). Try fewer years or a different event year.", "warn")
                else:
                    est, se_ = R["est"] * sc_, R["se"] * sc_; plc = None if R["placebo"] is None else R["placebo"] * sc_
                    k = st.columns(5)
                    k[0].metric("Exposed firms: change", f"{R['d_t'] * sc_:+.2f} {ul}"); k[1].metric("Comparison firms: change", f"{R['d_c'] * sc_:+.2f} {ul}")
                    k[2].metric("Event effect (DiD)", f"{est:+.2f} {ul}", help="(exposed firms after − before) − (comparison firms after − before)")
                    k[3].metric("95% interval", f"{est - 1.96 * se_:+.1f} to {est + 1.96 * se_:+.1f}", help="Firm-clustered standard errors; unreliable with few exposed firms")
                    k[4].metric("Placebo (pre-event)", "n/a" if plc is None else f"{plc:+.2f} {ul}", help="DiD using only pre-event years with a fake event date. Should be near zero if trends were parallel.")
                    by = R["by_year"] * sc_
                    f = go.Figure()
                    f.add_vrect(x0=ev - 0.5, x1=by.index.max() + 0.5, fillcolor="#f1f6ff", opacity=0.9, line_width=0)
                    f.add_scatter(x=by.index, y=by[1], mode="lines+markers", name=f"Exposed (n={R['n_t']})", line=dict(color=BLUE, width=3), marker=dict(size=8))
                    f.add_scatter(x=by.index, y=by[0], mode="lines+markers", name=f"Comparison (n={R['n_c']})", line=dict(color=ORANGE, width=3), marker=dict(size=8))
                    prey = by[by.index < ev]; postx = by[by.index >= ev]
                    if len(prey) and len(postx):
                        cf = prey[1].mean() + (postx[0] - prey[0].mean())
                        f.add_scatter(x=postx.index, y=cf, mode="lines", name="Exposed if they had followed the comparison group", line=dict(color=BLUE, width=2, dash="dash"))
                    f.add_vline(x=ev - 0.5, line_dash="dot", line_color=MUTED, annotation_text=f"event: FY{ev}", annotation_position="top left")
                    f.update_layout(title=f"{outc}: average by fiscal year", xaxis=dict(dtick=1, title="Fiscal year (ending March)"), yaxis_title=f"{outc} ({ul})")
                    st.plotly_chart(style(f, 400), width="stretch", config=PCFG)
                    st.caption("**How to read:** before the shaded area the two lines should move together (parallel trends). In the shaded area, the gap between the solid blue line and the dashed counterfactual is the DiD effect.")
                    # plain-English verdict
                    flags = []
                    if R["n_t"] < 10: flags.append(f"only <b>{R['n_t']}</b> exposed firms: treat the result as descriptive, not statistical")
                    if plc is not None and abs(plc) >= 0.5 * abs(est): flags.append(f"the placebo gap ({plc:+.2f}) is as large as the estimate ({est:+.2f}), so <b>pre-event trends were not parallel</b> and the estimate is not credible")
                    elif plc is not None and abs(plc) >= 0.25 * abs(est): flags.append(f"the pre-event placebo gap ({plc:+.2f}) is {abs(plc) / abs(est):.0%} of the estimate, so <b>part of it may reflect trends that already differed before the event</b> (look at the chart before the shaded area)")
                    sig = (est - 1.96 * se_ > 0) or (est + 1.96 * se_ < 0)
                    verdict = (f"After FY{ev}, exposed firms' {outc.lower()} changed by <b>{R['d_t'] * sc_:+.2f} {ul}</b> versus <b>{R['d_c'] * sc_:+.2f} {ul}</b> for comparison firms, "
                               f"so the event effect (DiD) is <b>{est:+.2f} {ul}</b>. ")
                    if flags: callout(verdict + "<b>Caution:</b> " + "; ".join(flags) + ".", "warn")
                    elif sig: callout(verdict + "The interval excludes zero and the placebo is small, so the data are <b>consistent with an effect</b> of the event (association, not proof of causation).", "good")
                    else: callout(verdict + "The interval includes zero, so the effect is <b>not distinguishable from noise</b> with this sample.")

                    with st.expander("➕ Triple difference: which exposed firms are most affected?"):
                        sp_ = st.radio("Split firms by", ["size", "leverage"], horizontal=True, key="ev_split" + kk, help="High = above the median of the pre-event average (total assets or debt/assets)")
                        T3 = A.triple_did(panel, treated, control, col, ev, pre, post, sp_)
                        if T3.get("DDD") is None:
                            st.info("Not enough exposed and comparison firms in both halves for a triple difference.")
                        else:
                            kk3 = st.columns(3)
                            kk3[0].metric(f"DiD, high {sp_}", f"{T3['High']['est'] * sc_:+.2f} {ul}", f"{T3['High']['n_t']} exposed / {T3['High']['n_c']} comparison", delta_color="off")
                            kk3[1].metric(f"DiD, low {sp_}", f"{T3['Low']['est'] * sc_:+.2f} {ul}", f"{T3['Low']['n_t']} exposed / {T3['Low']['n_c']} comparison", delta_color="off")
                            kk3[2].metric("Triple difference", f"{T3['DDD'] * sc_:+.2f} {ul}", help="DiD(high) − DiD(low)")
                            st.caption("Same logic as the calculator: the effect of the event is estimated separately for high and low groups, and the gap between them is the triple difference. Small groups make this very noisy.")
                    with st.expander("Firms included"):
                        inc = R["data"].groupby("ticker").agg(group=("treat", lambda s: "Exposed" if s.iloc[0] else "Comparison"), years=("fy", "count")).reset_index()
                        inc["Company"] = inc.ticker.map(fmt); st.dataframe(inc[["Company", "group", "years"]], hide_index=True, width="stretch")
            st.caption("Source: Screener.in public pages (Rs crore, consolidated where available), non-financial firms; ratios winsorised at 5th/95th percentile. DiD shows association under the parallel-trends assumption, not proof of cause.")

# ------------------------------------------------------------------------------------------ TAB: CASE LAB
with tcase:
    section("Case lab", "Known cases tested against the numbers. Each case shows the story, what the screen sees, and whether widely reported patterns show up in the data.")
    callout("<b>Why cases matter:</b> a screen is only credible if it can be checked against known stories. Here we use <b>10+ years</b> of Screener.in history (longer than the main dashboard) "
            "to test widely reported patterns. Where the screen is blind, the case says so: that is the lesson.")
    CASES = {
        "TCS: a clean-profile benchmark (Beneish and Benford)": dict(tk="TCS.NS", kind="tcs"),
        "Infosys: whistleblower allegations (2019)": dict(tk="INFY.NS", kind="window", w=(2018, 2020), mark=(2019, 2020),
            ctx=["In October 2019 anonymous whistleblowers alleged that senior management pushed aggressive accounting to lift short-term revenue and profit (public record).",
                 "Analysts tested the allegations by applying forensic algorithms (Beneish M and others) to the published numbers.",
                 "As publicly reported, the audit committee's independent investigation did not substantiate the allegations. Check the original reports for the exact conclusions."],
            lesson="A statement-based screen can show whether the *numbers* look unusual; it cannot prove or disprove claims about *instructions and intent*. Pair it with document review and interviews.",
            nxt=["Compare unbilled revenue and large-deal margins in the notes.", "Trace revenue recognition policy changes and auditor key audit matters.", "Compare against the three closest peers, not the whole universe."]),
        "Café Coffee Day: money out through the back door": dict(tk="COFFEEDAY.NS", kind="window", w=(2017, 2019), mark=(2019, 2019),
            ctx=["Per SEBI and NFRA orders and press reports: about ₹3,535 crore moved from CCD's subsidiaries to MACEL, a company owned by the founder's family, as 'loans' and 'advances'.",
                 "At March 2019 MACEL gave 'repayment' cheques of ₹1,706 crore that were not backed by funds and were not cashed before year-end, so the loan looked smaller (window dressing).",
                 "The founder died in July 2019. SEBI fined the company ₹26 crore; NFRA fined the FY2019 auditor ₹10 crore and the FY2020 auditor ₹2 crore. These are regulator findings, some under appeal."],
            claim="Hypothesis: accruals were not high and cash flow looked healthy, because the problem sat in related-party advances, not in the profit line.",
            lesson="Clean profits do not mean clean balance sheets. A cash-flow and accruals screen sees nothing when the diversion is booked as an asset (advances to a related party).",
            nxt=["Read the related-party and 'advances' notes first.", "Confirm balances and year-end cheques with counterparties.", "Compare subsidiary cash with what the consolidated statements show."]),
        "Zee Entertainment: the company as the promoters' safety net": dict(tk="ZEEL.NS", kind="window", w=(2017, 2019), mark=(2019, 2019),
            ctx=["As reported: promoter-group companies borrowed against Zee shares (over 90% pledged in 2019), creating pressure to keep the share price up.",
                 "Case A: a ₹200 crore Zee fixed deposit was taken by Yes Bank against a letter of comfort for group loans; SEBI says the board did not know. Case B: Zee land was pledged for ₹726 crore of loans taken by promoter-linked companies, allegedly without approvals or related-party disclosure.",
                 "SEBI's final order (31 July 2026) bars the chairman and CEO for a year and fines ₹1.48 crore in total. It is under appeal and Zee denies wrongdoing."],
            claim="Hypothesis: FY17-FY19 showed high accruals, with profit well above cash flow.",
            lesson="Look past the company to the promoter's debt. Here the warning sign (profit far above cash) is visible in FY17-19, but the main facts were off the main statements: a letter, a pledge, a deposit.",
            nxt=["Track promoter pledge levels every quarter.", "Test every related-party disclosure against board and audit-committee minutes.", "Confirm bank deposits and liens directly with the bank."]),
        "Reliance Infrastructure: distress and group exposure": dict(tk="RELINFRA.NS", kind="window", w=(2017, 2019), mark=(2018, 2020),
            ctx=["Reliance Infrastructure has been widely discussed in connection with red flags and stress across the Reliance group (public reports).", "The screen's own reading of recent years is dominated by financial distress rather than accounting-quality signals (see numbers below)."],
            lesson="High leverage and distress raise the incentive to manipulate (the fraud triangle's pressure), even when accrual and cash tests look unremarkable. Route distress to credit teams and still audit related-party exposure.",
            nxt=["Examine inter-corporate loans and group exposures.", "Test recoverability of receivables and arbitration awards.", "Read auditor qualifications and key audit matters."]),
        "Wirecard and Ricoh India: where this screen is blind": dict(kind="text"),
    }
    cname = st.selectbox("Choose a case", list(CASES), key="case_sel"); C = CASES[cname]

    def case_charts(tk, mark):
        pd_ = panel[(panel.ticker == tk) & (panel.fy >= 2015)].sort_values("fy")
        a, b = st.columns(2)
        f = go.Figure(); f.add_bar(name="Net income", x=pd_.fy, y=pd_.ni, marker_color=BLUE); f.add_bar(name="Operating cash flow", x=pd_.fy, y=pd_.cfo, marker_color=ORANGE)
        if mark: f.add_vrect(x0=mark[0] - 0.5, x1=mark[1] + 0.5, fillcolor="#fff6ec", opacity=0.9, line_width=0)
        f.update_layout(title="Profit vs operating cash flow (₹ crore)", barmode="group", xaxis=dict(dtick=1))
        a.plotly_chart(style(f, 340), width="stretch", config=PCFG)
        a.caption("**How to read:** shaded years = the period in the case. When blue towers over orange, profit is not turning into cash.")
        raw = panel[(panel.ticker == tk) & (panel.fy >= 2015)].sort_values("fy")
        f = go.Figure(); f.add_scatter(x=raw.fy, y=raw.accruals * 100, name="Accruals / lagged assets", mode="lines+markers", line=dict(color=BLUE, width=3))
        f.add_scatter(x=raw.fy, y=raw.debt_assets * 100, name="Debt / assets", mode="lines+markers", line=dict(color=ORANGE, width=3))
        if mark: f.add_vrect(x0=mark[0] - 0.5, x1=mark[1] + 0.5, fillcolor="#fff6ec", opacity=0.9, line_width=0)
        f.add_hline(y=0, line_color=MUTED, line_dash="dot")
        f.update_layout(title="Accruals and leverage (% of assets)", xaxis=dict(dtick=1), yaxis_title="%")
        b.plotly_chart(style(f, 340), width="stretch", config=PCFG)
        b.caption("**How to read:** accruals well above 0 = profit not backed by cash. A rising orange line = debt building up relative to assets.")

    if C["kind"] == "tcs":
        callout("<b>TCS as a benchmark:</b> a large, cash-generative firm that shows what a clean profile looks like. Compare it with direct competitors, check its Beneish M-score, and check Benford conformity.")
        peers_ = ["TCS.NS", "INFY.NS", "HCLTECH.NS", "TECHM.NS"]
        t_ = yr[yr.ticker.isin(peers_)].set_index("ticker").loc[[p for p in peers_ if p in set(yr.ticker)]]
        tbl_ = pd.DataFrame({"Net margin": t_.net_margin, "ROE": t_.roe, "Receivable days": t_.dso, "CFO / NI": t_.cfo_to_ni, "Debt / equity": t_.de_ratio, "Beneish M": t_.MScore,
                             "Benford MAD": t_.benford_mad, "Altman Z″": t_.Altman, "Risk score": t_.score_w}).rename(index=lab).round(3)
        section("TCS vs its competitors (FY" + str(fy) + ")", "Same sector, same business model, so ratios are directly comparable.")
        st.dataframe(tbl_, width="stretch")
        st.caption("Infosys and HCL Tech report in USD in Yahoo's data, but all of these are ratios, so currency does not matter.")
        tr = yr[yr.ticker == "TCS.NS"].iloc[0]
        a, b = st.columns(2)
        comps = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI"]
        f = go.Figure(); f.add_bar(name="TCS", x=comps, y=[tr[k] for k in comps], marker_color=BLUE); f.add_bar(name="Peer median (all non-financials)", x=comps, y=peers[comps].median().values, marker_color="#cbd5e1")
        f.add_hline(y=1, line_dash="dot", line_color=MUTED); f.update_layout(title="Beneish indices: TCS vs peers", barmode="group")
        a.plotly_chart(style(f, 340), width="stretch", config=PCFG)
        a.caption(f"**Reading:** M-score = **{tr.MScore:.2f}**, below the −2.22 watch level, so the model does not flag TCS. The only index noticeably above 1 is AQI; check whether acquisitions or leases explain it.")
        d_ = bdig[bdig.ticker == "TCS.NS"]
        f = go.Figure(); f.add_bar(name="Observed", x=d_.digit, y=d_.observed * 100, marker_color=BLUE)
        f.add_scatter(name="Benford expected", x=d_.digit, y=d_.expected * 100, mode="lines+markers", line=dict(color=INK, width=2))
        f.update_layout(title="Benford first-digit test: TCS", xaxis=dict(dtick=1, title="Leading digit"), yaxis_title="% of numbers")
        b.plotly_chart(style(f, 340), width="stretch", config=PCFG)
        b.caption(f"**Reading:** MAD = **{tr.benford_mad:.4f}** ({tr.benford_label}). With Yahoo's derived line items (totals repeated, rounded aggregates) this is more likely a data artefact than manipulation, which is why Benford carries only 10% weight.")
        callout("<b>Take-away for the answer:</b> TCS looks financially strong (high margins, cash-backed profit) and unremarkable on Beneish. The Benford miss is a weak signal that needs raw filing data before drawing any conclusion.", "good")
    elif C["kind"] == "text":
        c1, c2 = st.columns(2)
        c1.markdown('<div class="card"><h4>Wirecard</h4><p>A German payments company whose reported cash held in trustee accounts could not be found; it collapsed in 2020 (public record). '
                    'It is not an Indian listed company, so it is not in this dashboard.</p><p><b>Lesson:</b> ratio screens look at reported numbers. When the cash itself is fictitious, only direct '
                    'confirmation with banks and trustees finds it. This is the screen\'s deepest blind spot.</p></div>', unsafe_allow_html=True)
        c2.markdown('<div class="card"><h4>Ricoh India</h4><p>A documented case of financial reporting irregularities. '
                    'The company is delisted, so free data sources have no current statements.</p><p><b>Lesson:</b> apply the same Beneish indices (especially DSRI and SGI) to the published case numbers by hand; '
                    'that is exactly what the screen automates for living firms.</p></div>', unsafe_allow_html=True)
        st.write("")
        callout("<b>Design point:</b> the screen cannot test these two cases, and that is itself informative. Screens work on listed firms with available data and reported numbers; frauds that hide outside the statements, or firms that "
                "have left the market, need other tools (confirmations, forensic accounting, regulator orders).", "warn")
    else:
        tk = C["tk"]; fy0, fy1 = C["w"]
        section("The story", None)
        for x in C["ctx"]: st.markdown("- " + x)
        st.caption("Facts are regulator findings or allegations as recorded in regulator orders and press reports; some are under appeal. Verify against the original orders before quoting.")
        W = A.window_stats(panel, tk, fy0, fy1)
        section(f"What the screen sees (FY{fy0}-FY{fy1})", "Screener.in 10-year history, compared with the median non-financial firm over the same years.")
        k = st.columns(4)
        k[0].metric("Accruals / lagged assets", f"{W['acc']:.1%}", f"typical firm {W['acc_u']:.1%}", delta_color="off", help="Profit not backed by cash; higher = riskier")
        k[1].metric("CFO / net income", "n/a" if pd.isna(W["cfo_ni"]) else f"{W['cfo_ni']:.2f}", f"typical firm {W['cfo_ni_u']:.2f}", delta_color="off", help="Below 1 = profit not turning into cash")
        k[2].metric("Sales CAGR", f"{W['cagr']:.1%}")
        rowc = yr[yr.ticker == tk]
        k[3].metric(f"Risk score FY{fy}", "n/a" if rowc.empty or pd.isna(rowc.iloc[0].score_w) else f"{rowc.iloc[0].score_w:.0f}/100", None if rowc.empty or pd.isna(rowc.iloc[0].score_w) else str(rowc.iloc[0].tier_w), delta_color="off")
        case_charts(tk, C["mark"])
        if "claim" in C:
            high_acc = W["acc"] > W["acc_u"] + 0.03 and (pd.isna(W["cfo_ni"]) or W["cfo_ni"] < 0.7 * W["cfo_ni_u"])
            clean = W["acc"] <= W["acc_u"] + 0.02 and (not pd.isna(W["cfo_ni"])) and W["cfo_ni"] >= W["cfo_ni_u"]
            expect_high = tk == "ZEEL.NS"
            ok = high_acc if expect_high else clean
            st.markdown(f"**Test of the reported pattern.** {C['claim']}")
            callout(f"<b>Data (FY{fy0}-{fy1}):</b> accruals averaged <b>{W['acc']:.1%}</b> of assets vs <b>{W['acc_u']:.1%}</b> for the typical firm; CFO/NI averaged <b>{W['cfo_ni']:.2f}</b> vs <b>{W['cfo_ni_u']:.2f}</b>. "
                    + ("✅ <b>The data support the hypothesis.</b>" if ok else "⚠️ <b>The data do not clearly support the hypothesis</b>; check the definitions and years."), "good" if ok else "warn")
            if tk == "COFFEEDAY.NS":
                dd = panel[(panel.ticker == tk) & panel.fy.isin([2016, 2019])].set_index("fy").debt
                if {2016, 2019} <= set(dd.index): st.markdown(f"Debt rose from **₹{dd[2016]:,.0f} crore (FY2016)** to **₹{dd[2019]:,.0f} crore (FY2019)**, a {dd[2019] / dd[2016]:.1f}× increase, consistent with reports that debt nearly doubled in three years.")
        else:
            st.markdown(f"**What to look for.** Over FY{fy0}-{fy1} accruals averaged **{W['acc']:.1%}** vs **{W['acc_u']:.1%}** typical, and CFO/NI **{W['cfo_ni']:.2f}** vs **{W['cfo_ni_u']:.2f}** typical. "
                        "These are modest differences, not the extreme pattern seen in classic manipulation cases. This is what a statement-based screen can and cannot say.")
        c1, c2 = st.columns(2)
        c1.markdown("**Lesson**"); c1.info(C["lesson"])
        c2.markdown("**What to check next**"); c2.markdown("\n".join("- " + x for x in C["nxt"]))

# ------------------------------------------------------------------------------------------ TAB: AI ANALYST
def _mrow(r_):
    r2 = r_.copy(); r2["score"], r2["tier"] = r_.score_w, r_.tier_w
    return r2


@st.cache_data
def grounding_stats(_yr, _peers, key):
    memos = json.loads((DATA / "ai_memos.json").read_text()) if (DATA / "ai_memos.json").exists() else {}
    rows = []
    for _, r_ in _yr[_yr.score_w.notna()].iterrows():
        g = M.grounding_check(M.rule_based_memo(_mrow(r_), _peers), M.fact_sheet(_mrow(r_), _peers)); rows.append(("Rule-based memo", r_.ticker, g))
        if r_.ticker in memos:
            g2 = M.grounding_check(memos[r_.ticker]["memo"], M.fact_sheet(_mrow(r_), _peers)); rows.append(("Claude-drafted memo", r_.ticker, g2))
    out = {}
    for kind in ("Rule-based memo", "Claude-drafted memo"):
        sel = [g for k_, _, g in rows if k_ == kind]
        out[kind] = (len(sel), sum(g["total"] for g in sel), sum(g["grounded"] for g in sel), [(t, g["ungrounded"]) for k_, t, g in rows if k_ == kind and g["ungrounded"]])
    return out


with tai:
    section("AI analyst", "AI is used in four ways here. This page shows each one, and how its reliability was checked.")
    ai1, ai2, ai3 = st.tabs(["📝 Company memo", "🧠 Where AI is used", "✅ How reliability was checked"])

    with ai1:
        callout("<b>Guard-rails:</b> every memo is built from one numeric <i>fact sheet</i>. The AI may use <b>only</b> those numbers, must treat flags as signals not proof, and must list benign explanations. "
                "After each memo an automatic <b>grounding check</b> confirms that every number in it traces back to the fact sheet.")
        ykeys = sorted(yr.ticker)
        tk2 = st.selectbox("Company", ykeys, format_func=lambda t: lab.get(t, t), key="memo_co", index=ykeys.index("PCJEWELLER.NS") if "PCJEWELLER.NS" in ykeys else 0)
        row = _mrow(yr[yr.ticker == tk2].iloc[0])
        facts = M.fact_sheet(row, peers)
        layer = st.radio("Memo source", ["Rule-based (deterministic)", "Claude-drafted (pre-generated)", "Live Claude API"], horizontal=True,
                         help="Rule-based: fixed text rules, no AI. Claude-drafted: written by Claude from the fact sheet. Live: calls the API if a key is configured.")
        memo_txt = None
        if layer.startswith("Rule"):
            memo_txt = M.rule_based_memo(row, peers); st.markdown(memo_txt)
        elif layer.startswith("Claude-drafted"):
            p = DATA / "ai_memos.json"; memos = json.loads(p.read_text()) if p.exists() else {}
            if tk2 in memos:
                memo_txt = memos[tk2]["memo"]; st.markdown(memo_txt)
                st.caption(f"⚠️ Drafted by {memos[tk2]['model']} on {memos[tk2]['date']} from the FY{memos[tk2]['fy']} fact sheet. AI-generated: verify against filings before use.")
            else:
                callout("No pre-generated Claude memo for this company. Memos exist for PC Jeweller, Zee, Coffee Day, Reliance Infra, Tata Motors PV, Adani Enterprises, TCS and Vodafone Idea. Use the rule-based option for others.")
        else:
            if st.button("Generate with Claude"):
                try:
                    memo_txt = M.live_claude_memo(row, peers); st.markdown(memo_txt)
                except Exception as e:
                    st.error(f"Live call unavailable on this deployment ({e}). It needs an ANTHROPIC_API_KEY.")
        if memo_txt:
            g = M.grounding_check(memo_txt, facts)
            if g["total"] == 0: st.caption("Grounding check: no company-specific numbers in this text.")
            elif not g["ungrounded"]: callout(f"<b>✅ Grounding check passed:</b> all {g['total']} numbers in this memo trace back to the fact sheet (within rounding).", "good")
            else: callout(f"<b>⚠️ Grounding check:</b> {g['grounded']} of {g['total']} numbers trace to the fact sheet. Not found: <b>{', '.join(g['ungrounded'])}</b>. Verify these before use.", "warn")
        with st.expander("Fact sheet given to the AI (the only numbers it may use)"):
            st.json(facts)
        with st.expander("Prompt template"):
            st.code(M.PROMPT)

    with ai2:
        st.markdown("""
| AI component | What it does | Where you see it |
|---|---|---|
| **Anomaly detector** (Isolation Forest, unsupervised machine learning) | Looks at a company's whole financial fingerprint (14 forensic features) and scores how unusual it is against peers, with **no hand-set weights**. Also names the two features that make it unusual. | Priority index, Triage board, alerts |
| **Alert engine** | Compares each company with last year and raises alerts: risk-score jumps, Beneish threshold crossings, new distress, falling cash conversion, AI outliers. | Decision desk |
| **Closest financial twins** (nearest-neighbour matching) | Finds the companies whose fingerprint is most similar, for like-for-like comparison. | Company brief |
| **LLM memo writer** (Claude) | Turns the fact sheet into a short analyst memo with benign explanations and next audit steps. | Company memo |
| **AI-assisted build** (Claude Code) | Wrote the data pipeline, tests and this dashboard under human direction. | Whole product |
""")
        section("The new metric: Forensic Priority Index (FPI)", "Combines what the rules say, how many tests agree, and what the AI detector says.")
        st.markdown("**FPI = 50% × Risk score + 25% × share of tests in the red zone + 25% × AI anomaly percentile**  (each 0 to 100).")
        st.caption("Why three parts? The risk score is a weighted judgement. Corroboration rewards firms where *independent* tests agree. The anomaly percentile is a second opinion that does not depend on any hand-chosen weights.")
        sc2 = yr[yr.score_w.notna() & yr.anomaly_pct.notna()].copy()
        f = px.scatter(sc2, x="score_w", y="anomaly_pct", color="cohort", color_discrete_map=COH_COL, hover_name="name",
                       labels={"score_w": "Rule-based risk score", "anomaly_pct": "AI anomaly percentile", "cohort": "Cohort"})
        f.add_vline(x=65, line_dash="dash", line_color=MUTED, annotation_text="High tier", annotation_position="top left")
        f.add_hline(y=90, line_dash="dash", line_color=MUTED, annotation_text="AI outlier", annotation_position="bottom right")
        f.update_traces(marker=dict(size=10, line=dict(color="white", width=1.5)))
        f.update_layout(title="Where AI and the rules agree and disagree")
        st.plotly_chart(style(f, 400), width="stretch", config=PCFG)
        dis2 = sc2[(sc2.anomaly_pct >= 90) & (sc2.score_w < 65)]
        st.caption("**How to read:** top-right = both agree the firm is unusual and risky. **Top-left** = unusual patterns the rules rate lower (a second look is worthwhile): "
                   + (", ".join(snm(n) for n in dis2.name) if len(dis2) else "none this year") + ". Bottom-right = rules flag it, AI sees nothing unusual.")
        with st.expander("Significant prompts and workflow (how AI was used to build this)"):
            st.markdown("""
| Step | What the AI was asked to do | How a human checked it |
|---|---|---|
| 1. Scope | Propose the stakeholder, universe, data sources; ask clarifying questions | Chose forensic analyst, Nifty 50 plus watchlist, free live sources |
| 2. Build engine | Implement Beneish, accruals, REM, Benford, Altman and a composite score | First run ranked a finance company as the riskiest; the human caught that financials must be excluded, and the rule was added |
| 3. Cross-check data | Re-fetch every firm from a second online source and compare | Found Yahoo reports two firms in USD; fixed currency handling |
| 4. Add AI layer | Add an unsupervised anomaly detector, alerts and nearest-neighbour peers | Replaced misleading features (debt/equity with negative equity) after inspecting the explanations |
| 5. Memos | Draft memos from a fact sheet with a strict "only these numbers" prompt | Automatic grounding check plus a rule-based baseline |
| 6. Test | Back-test the score and the new index against the watchlist | Reported modest results honestly, with the small-sample caveat |
""")

    with ai3:
        gs = grounding_stats(yr, peers, (fy, stamp(), tuple(W.values())))
        section("Check 1 · Every number in an AI memo is traceable", "An automatic test run on every memo in this dashboard.")
        c1, c2 = st.columns(2)
        for col_, kind in [(c1, "Rule-based memo"), (c2, "Claude-drafted memo")]:
            n_, tot_, good_, bad_ = gs[kind]
            col_.metric(kind + "s", f"{good_} of {tot_} numbers traced", f"{(good_ / tot_ * 100 if tot_ else 100):.0f}% grounded · {n_} memos", delta_color="off")
        bad_all = gs["Claude-drafted memo"][3] + gs["Rule-based memo"][3]
        if bad_all: st.caption("Not traced: " + "; ".join(f"{t.replace('.NS', '')}: {', '.join(b)}" for t, b in bad_all[:6]) + ". Thresholds and model weights are treated as method constants, not company facts.")
        else: st.caption("No ungrounded numbers. Thresholds and model weights are treated as method constants, not company facts.")
        section("Check 2 · The input data agrees with an independent source", "Yahoo Finance versus Screener.in, same companies.")
        xr_ = DATA / "xcheck_ratios.csv"
        if xr_.exists():
            xv = pd.read_csv(xr_); st.markdown(f"Cash flow and total assets match almost exactly; the five ratios behind the tests rank-correlate **{xv.spearman.min():.2f} to {xv.spearman.max():.2f}** across sources (see *Method & data*).")
        section("Check 3 · The scores are back-tested", "Does each measure rank the watchlist of troubled firms above the Nifty 50? (AUC, 0.5 = coin flip)")
        vv = valid.set_index("metric").AUC
        st.markdown(f"Rule-based composite **{vv.get('Composite score', float('nan')):.2f}** · AI anomaly detector **{vv.get('AI anomaly detector (Isolation Forest)', float('nan')):.2f}** · Priority index **{vv.get('Forensic Priority Index (new)', float('nan')):.2f}**.")
        callout("<b>Read honestly:</b> only about 10 watchlist firms can be scored, so these AUCs are indicative. The anomaly detector scores highest partly because troubled firms are often structurally unusual (distress, restructuring), "
                "which is not the same as manipulation. That is why the priority index blends all three views instead of trusting any one.", "warn")
        section("Check 4 · Human review and disclosure", "What stays with the analyst.")
        st.markdown("- Every AI memo is labelled AI-generated and must list **benign explanations** before suggesting audit steps.\n- A rule-based memo (no AI) is always available as a baseline to compare with.\n"
                    "- Written text from the language model never influences a ranking. Ranking uses only the calculated score and index (the index includes the machine-learning anomaly percentile, which is a calculation, not generated text).\n- The analyst confirms any flag against filings before acting. A flag is a reason to look, never evidence of wrongdoing.")

# ------------------------------------------------------------------------------------------ TAB 5
with tmeth:
    section("Method & data", "How the score and the priority index are built, how well they work, where the data comes from, and where it can mislead.")
    st.markdown("""
| Block | Default weight | Tool | Red-flag rule |
|---|---|---|---|
| Beneish | 30 | 8-variable M-score | M > −1.78 flag, > −2.22 watch; needs ≥ 6 of 8 indices |
| Accruals | 20 | Sloan ratio + modified Jones DA (AEM) | higher peer percentile = riskier |
| Cash divergence | 15 | 3-yr CFO / net income | lower conversion = riskier |
| REM | 10 | Roychowdhury abnormal CFO and discretionary spend | low CFO and low SG&A |
| Benford | 10 | First-digit MAD, Nigrini bands | ≤0.006 close, ≤0.012 acceptable, ≤0.015 marginal, above = non-conformity |
| Distress | 15 | Altman Z″ emerging-market | < 4.15 distress, 4.15-5.85 grey |

Tiers: **Low** below 35 · **Moderate** 35-50 · **Elevated** 50-65 · **High** above 65. Weights are adjustable in the sidebar.
""")
    section("The Forensic Priority Index (FPI)", "The new decision metric: it ranks companies for investigation.")
    st.markdown("**FPI = 50% × Risk score + 25% × share of tests in the red zone + 25% × AI anomaly percentile.** Risk score = weighted average of six tests. Red zone = a test scores 60 or more out of 100. "
                "AI anomaly percentile = how unusual the company's whole fingerprint is versus peers (Isolation Forest).")
    st.markdown("**Recommended action (bands on the index):** 65 or more = Investigate · 50 to 65 = Review · 35 to 50 = Monitor · below 35 = Routine.")
    section("Back-test: does the screen rank the watchlist above the Nifty 50?", "AUC = chance that a random watchlist firm scores higher than a random Nifty firm. 0.5 = coin flip, 1.0 = perfect.")
    v = valid.copy(); v["AUC"] = v.AUC.round(2)
    f = px.bar(v.sort_values("AUC"), x="AUC", y="metric", orientation="h", color_discrete_sequence=[BLUE], text="AUC", labels={"metric": ""})
    f.add_vline(x=0.5, line_dash="dash", line_color=MUTED, annotation_text="0.5 = coin-flip")
    f.update_layout(title="Back-test result by test", xaxis=dict(range=[0, 1]))
    st.plotly_chart(style(f, 340), width="stretch", config=PCFG)
    vm_ = valid.set_index("metric").AUC
    callout(f"<b>Honest reading:</b> the rule-based composite scores {vm_.get('Composite score', float('nan')):.2f}, the AI anomaly detector {vm_.get('AI anomaly detector (Isolation Forest)', float('nan')):.2f} and the priority index {vm_.get('Forensic Priority Index (new)', float('nan')):.2f} (0.5 = coin flip). "
            "Only about 10 watchlist firms can be scored, and several of their episodes were distress or governance issues, not accounting manipulation; anomaly detection also rewards structural oddness. Treat the screen as a prioritisation aid, not a detector.", "warn")
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
    @st.cache_data
    def audit_zip(_k):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f_ in ["DATA_DICTIONARY.md", "universe.csv", "raw_long.csv", "metrics_year.csv", "scores.csv", "benford_digits.csv", "screener_long.csv", "xcheck_levels.csv", "xcheck_ratios.csv", "xcheck_firms.csv", "validation.csv", "ai_memos.json", "last_refresh.txt"]:
                if (DATA / f_).exists(): z.write(DATA / f_, arcname="audit_pack/" + f_)
        return buf.getvalue()

    section("Data & calculation audit pack", "Everything needed to verify the source of every number and re-run every calculation.")
    st.download_button("⬇ Download the audit pack (zip)", audit_zip(stamp()), "forensic_screener_audit_pack.zip", mime="application/zip")
    st.caption("Contains the raw statements, every intermediate calculation (one row per company-year), the Screener.in history, the cross-check results, the AI memos, and a dictionary with all formulas. "
               "The *Company brief* tab also shows the Beneish M-score recalculated step by step for any company.")
    if (DATA / "DATA_DICTIONARY.md").exists():
        with st.expander("Data dictionary and formulas"): st.markdown((DATA / "DATA_DICTIONARY.md").read_text())
    section("Sources & references", "Where the data and methods come from.")
    st.markdown("""**Data**
- NSE India: current Nifty 50 constituents (archives.nseindia.com).
- Yahoo Finance (via the open-source `yfinance` library): annual income statement, balance sheet and cash flow.
- Screener.in public company pages: independent cross-check of the inputs and 10 years of history for the back-test and case studies.

**Methods**
- Beneish, M. D. (1999). The detection of earnings manipulation. *Financial Analysts Journal*, 55(5), 24-36.
- Sloan, R. G. (1996). Do stock prices fully reflect information in accruals and cash flows about future earnings? *The Accounting Review*, 71(3), 289-315.
- Dechow, P. M., Sloan, R. G., & Sweeney, A. P. (1995). Detecting earnings management. *The Accounting Review*, 70(2), 193-225.
- Roychowdhury, S. (2006). Earnings management through real activities manipulation. *Journal of Accounting and Economics*, 42(3), 335-370.
- Nigrini, M. J. (2012). *Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection*. Wiley.
- Altman, E. I. (1968), *Journal of Finance*, 23(4), 589-609; Altman, Hartzell & Peck (1995), emerging-markets scoring model.
- Bertrand, M., Duflo, E., & Mullainathan, S. (2004). How much should we trust differences-in-differences estimates? *Quarterly Journal of Economics*, 119(1), 249-275.

**Case studies**
- SEBI orders on Coffee Day Enterprises (January 2023) and Zee Entertainment (June 2023 interim; July 2026 final); NFRA orders on BSR & Associates and Venkatesh & Co, as reported by Moneylife, Outlook Business, Business Standard and BusinessToday. Several matters are under appeal; verify against the original orders before quoting.
""")
    st.markdown("""**Limitations (read before trusting any number)**
- The watchlist has only ~10 scoreable firms, so the back-test is indicative.
- Yahoo Finance gives 4-5 fiscal years; accrual models use ~40 non-financial firms per year (small and noisy).
- Peer percentiles are relative to this universe, not the whole market.
- Mergers, demergers and other restructurings break year-on-year comparisons and cause false positives.
- Related-party and cash-misappropriation frauds (Wirecard-type) are mostly invisible to ratio screens; they need cash confirmations and document review.
- Banks, NBFCs and insurers are not scored.""")

st.markdown('<div class="foot">Data: NSE India, Yahoo Finance, Screener.in. Methods and references: see Method &amp; data, Sources &amp; references. For analyst review: screening signals only, not investment advice and not evidence of wrongdoing.</div>', unsafe_allow_html=True)
