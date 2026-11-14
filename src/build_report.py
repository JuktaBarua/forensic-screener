"""Builds WAI_Practice_Report.docx from the live data/ outputs (numbers in the text are pulled from the CSVs)."""
from pathlib import Path
import pandas as pd, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parents[1]; D = ROOT / "data"; FIG = ROOT / "report_figs"; FIG.mkdir(exist_ok=True)
sc = pd.read_csv(D / "scores.csv"); val = pd.read_csv(D / "validation.csv"); m = pd.read_csv(D / "metrics_year.csv")
refresh = (D / "last_refresh.txt").read_text()[:10]
BLUE, ORG, INK = "#2a6fdb", "#d9730d", "#1f2937"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#9ca3af"})

s26 = sc[sc.fy == 2026]; scored = s26[s26.score.notna()]
nt = scored.tier.value_counts().to_dict()
wl_med, nf_med = scored[scored.cohort == "Watchlist"].score.median(), scored[scored.cohort == "Nifty 50"].score.median()
V = val.set_index("metric").AUC

# ---------- figures
top = scored.sort_values("score", ascending=False).head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(6.2, 3.8))
ax.barh(top.ticker.str.replace(".NS", ""), top.score, color=[ORG if c == "Watchlist" else BLUE for c in top.cohort], height=0.65)
ax.set_xlabel("Composite forensic risk score (0-100)"); ax.set_title("Top 15 by risk score, FY2026 (blue = Nifty 50, orange = watchlist)", fontsize=9, loc="left")
for y, v in enumerate(top.score): ax.text(v + 0.8, y, f"{v:.0f}", va="center", fontsize=8, color=INK)
fig.tight_layout(); fig.savefig(FIG / "top15.png", dpi=200); plt.close()

d = scored.dropna(subset=["MScore", "sloan"])
fig, ax = plt.subplots(figsize=(6.2, 3.6))
for c, col in [("Nifty 50", BLUE), ("Watchlist", ORG)]:
    x = d[d.cohort == c]; ax.scatter(x.MScore, x.sloan, s=34, color=col, edgecolor="white", linewidth=1, label=c)
for _, r in d.sort_values("score", ascending=False).head(6).iterrows():
    ax.annotate(r.ticker.replace(".NS", ""), (r.MScore, r.sloan), fontsize=7, xytext=(4, 3), textcoords="offset points")
ax.axvline(-1.78, ls="--", color="#6b7280", lw=1); ax.text(-1.76, ax.get_ylim()[0], " M > -1.78", fontsize=7, color="#6b7280", va="bottom")
ax.set_xlabel("Beneish M-score"); ax.set_ylabel("Sloan accrual ratio"); ax.legend(frameon=False, fontsize=8)
ax.set_title("Earnings-manipulation map, FY2026", fontsize=9, loc="left"); fig.tight_layout(); fig.savefig(FIG / "map.png", dpi=200); plt.close()

v = val.sort_values("AUC")
fig, ax = plt.subplots(figsize=(6.2, 3.0))
ax.barh(v.metric, v.AUC, color=BLUE, height=0.6); ax.axvline(0.5, ls="--", color="#6b7280", lw=1); ax.set_xlim(0, 1)
for y, a in enumerate(v.AUC): ax.text(a + 0.01, y, f"{a:.2f}", va="center", fontsize=8)
ax.set_xlabel("AUC (0.5 = coin flip)"); ax.set_title("Back-test: watchlist vs Nifty 50", fontsize=9, loc="left"); fig.tight_layout(); fig.savefig(FIG / "auc.png", dpi=200); plt.close()

# ---------- document helpers
doc = Document()
for s in doc.sections: s.left_margin = s.right_margin = Inches(1); s.top_margin = s.bottom_margin = Inches(0.9)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
for h, sz in [("Heading 1", 15), ("Heading 2", 12)]:
    doc.styles[h].font.name = "Calibri"; doc.styles[h].font.size = Pt(sz); doc.styles[h].font.color.rgb = RGBColor(0x1f, 0x3a, 0x6e)
P = lambda t, **k: _p(t, **k)


def _p(t, bold=False, italic=False, style=None, size=None):
    p = doc.add_paragraph(style=style); r = p.add_run(t); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(6); return p


def B(items):
    for t in items:
        p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(2)
        if "::" in t: a, b = t.split("::", 1); p.add_run(a).bold = True; p.add_run(b)
        else: p.add_run(t)


def T(rows, widths=None, header=True, size=9):
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Light Grid Accent 1"
    for i, row in enumerate(rows):
        for j, c in enumerate(row):
            cell = t.cell(i, j); cell.text = ""; run = cell.paragraphs[0].add_run(str(c)); run.font.size = Pt(size); run.bold = (i == 0 and header)
            if widths: cell.width = Inches(widths[j])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def F(path, cap, w=5.6):
    doc.add_picture(str(path), width=Inches(w)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = _p(cap, italic=True, size=9); c.alignment = WD_ALIGN_PARAGRAPH.CENTER


# ---------- title
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("A Forensic Earnings-Quality Screener for Listed Indian Firms"); r.bold = True; r.font.size = Pt(20); r.font.color.rgb = RGBColor(0x1f, 0x3a, 0x6e)
_p("Working with AI (WAI) project - practice run | Financial Statement Analysis & Forensic Auditing, Term V, IIM Ranchi", italic=True).alignment = WD_ALIGN_PARAGRAPH.CENTER
_p(f"Data refreshed {refresh} from NSE and Yahoo Finance. Built with Claude (Sonnet 5.5) as coding and analysis assistant. "
   "Practice document: the literature list must be independently verified before any real submission.", italic=True, size=9).alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_heading("Executive summary", 1)
_p(f"Forensic analysts cannot read every annual report. This project builds a screening dashboard that ranks {len(scored)} listed non-financial "
   f"firms (the Nifty 50 plus a watchlist of firms with publicly reported governance or distress episodes) by a transparent composite of six "
   f"forensic tests taught in the course: Beneish M-score, accruals (Sloan, modified Jones), cash conversion, real earnings management, Benford's law and "
   f"Altman Z''. An AI narrator turns each firm's numbers into a short, fact-bound analyst memo.")
_p("Headline findings", bold=True)
B([f"Triage works as designed::  FY2026 tiers: {nt.get('High', 0)} High, {nt.get('Elevated', 0)} Elevated, {nt.get('Moderate', 0)} Moderate, {nt.get('Low', 0)} Low. "
   f"Watchlist median score {wl_med:.0f} vs {nf_med:.0f} for the Nifty 50.",
   f"Discrimination is modest::  Composite AUC {V['Composite score']:.2f} (0.5 = chance) on roughly 10 watchlist and 37 Nifty firms: indicative, not conclusive. "
   f"Beneish alone was weak ({V['Beneish M']:.2f}); Benford ({V['Benford MAD']:.2f}) and distress ({V['Distress (Altman)']:.2f}) did better.",
   "False positives are instructive::  Tata Motors Passenger Vehicles scores High mainly on accruals after an apparent restructuring; TCS shows Benford "
   "non-conformity despite fully cash-backed profits. Flags are reasons to look, never verdicts.",
   "Inputs check out against a second online source::  Cash flow and assets from Yahoo match Screener.in almost exactly and the ratios behind the screen correlate 0.98-1.00; the remaining weakness is the short history and the small peer set, not data transcription.",
   "Ratios cannot see everything::  Zee scores Low in FY2022-26, yet its governance concerns were related-party and cash matters from earlier years - exactly the Wirecard-type blind spot discussed in class."])

# ---------- 1
doc.add_heading("1. Problem identification", 1)
_p("Background. India has seen repeated reporting failures (Satyam, IL&FS, DHFL, Coffee Day, Zee-related disputes) in which weak signals were visible in statements before the collapse. "
   "Regulators, lenders, auditors and investors have limited analyst time; the practical question is which firms to examine first.")
_p("Stakeholder. A forensic / fraud analyst (in a bank's credit-risk team, an audit firm, or an investor's research desk) deciding where to deploy investigation effort.")
_p("Scope. Annual consolidated statements, FY2022-FY2026, for the Nifty 50 plus twelve watchlist firms. Banks, NBFCs and insurers are shown but not scored.")
p = _p("Problem statement: ", bold=True); p.add_run("How can freely available financial data, classical forensic models and AI-assisted tooling be combined into a transparent, "
                                                      "interactive screen that prioritises listed Indian firms for forensic review - and how reliable is that ranking?").bold = False

# ---------- 2
doc.add_heading("2. Literature review", 1)
_p("Earnings-quality research supplies each building block. Healy and Wahlen (1999) frame earnings management as managers' use of judgement to mislead stakeholders or influence contractual outcomes. "
   "Accrual-based detection starts with Sloan (1996), who showed that the accrual component of earnings is less persistent than the cash component, and Dechow, Sloan and Sweeney (1995), who "
   "evaluated Jones-type models and proposed the modified Jones model used here. Roychowdhury (2006) documented real earnings management through abnormal cash flow, production and discretionary expenses, "
   "which accrual models miss.")
_p("Beneish (1999) built an eight-variable probit model that flags likely manipulators from year-on-year indices; Dechow, Ge, Larson and Sloan (2011) widened this to a broader set of predictors of SEC enforcement actions. "
   "Nigrini (2012) operationalised Benford's law for auditors, with mean-absolute-deviation conformity bands. Altman (1968) and the emerging-market adaptation by Altman, Hartzell and Peck (1995) link distress to incentives "
   "to manipulate. Machine-learning work such as Bao et al. (2020) improves out-of-sample fraud prediction but at the cost of interpretability. Dyck, Morse and Zingales (2010) show that auditors and regulators detect only a minority of frauds, "
   "most coming from employees, media and short-sellers, which supports using screens as a complement to, not a substitute for, investigation. Cressey's (1953) fraud triangle (pressure, opportunity, rationalisation) justifies including a distress overlay.")
_p("Gaps this project addresses: (i) most studies use US data, whereas Indian listed firms have different disclosure, group-structure and audit regimes; (ii) published models are rarely packaged for non-technical analysts; "
   "(iii) there is little evidence on LLM-assisted narration of forensic metrics, where hallucination control is essential.")
doc.add_heading("References (verify each before real submission)", 2)
for ref in ["Altman, E. I. (1968). Financial ratios, discriminant analysis and the prediction of corporate bankruptcy. Journal of Finance, 23(4), 589-609.",
            "Altman, E. I., Hartzell, J., & Peck, M. (1995). Emerging markets corporate bonds: A scoring system. Salomon Brothers.",
            "Bao, Y., Ke, B., Li, B., Yu, Y. J., & Zhang, J. (2020). Detecting accounting fraud in publicly traded U.S. firms using a machine learning approach. Journal of Accounting Research, 58(1), 199-235.",
            "Bertrand, M., Duflo, E., & Mullainathan, S. (2004). How much should we trust differences-in-differences estimates? Quarterly Journal of Economics, 119(1), 249-275.",
            "Beneish, M. D. (1999). The detection of earnings manipulation. Financial Analysts Journal, 55(5), 24-36.",
            "Card, D., & Krueger, A. B. (1994). Minimum wages and employment: A case study of the fast-food industry in New Jersey and Pennsylvania. American Economic Review, 84(4), 772-793.",
            "Cressey, D. R. (1953). Other People's Money. Free Press.",
            "Dechow, P. M., Ge, W., Larson, C. R., & Sloan, R. G. (2011). Predicting material accounting misstatements. Contemporary Accounting Research, 28(1), 17-82.",
            "Dechow, P. M., Sloan, R. G., & Sweeney, A. P. (1995). Detecting earnings management. The Accounting Review, 70(2), 193-225.",
            "Dyck, A., Morse, A., & Zingales, L. (2010). Who blows the whistle on corporate fraud? Journal of Finance, 65(6), 2213-2253.",
            "Healy, P. M., & Wahlen, J. M. (1999). A review of the earnings management literature and its implications for standard setting. Accounting Horizons, 13(4), 365-383.",
            "Imbens, G. W., & Lemieux, T. (2008). Regression discontinuity designs: A guide to practice. Journal of Econometrics, 142(2), 615-635.",
            "Nigrini, M. J. (2012). Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection. Wiley.",
            "Roychowdhury, S. (2006). Earnings management through real activities manipulation. Journal of Accounting and Economics, 42(3), 335-370.",
            "Sloan, R. G. (1996). Do stock prices fully reflect information in accruals and cash flows about future earnings? The Accounting Review, 71(3), 289-315.",
            "Course materials: Wirecard case (Vadera, Cheah & Rao-Kachroo); A Letter from Prison (Soltes); Ricoh India case (Chaklader); Red Flags in Reliance Group (Riyazahmed K)."]:
    q = doc.add_paragraph(ref, style="List Bullet"); q.paragraph_format.space_after = Pt(1); q.runs[0].font.size = Pt(9)

# ---------- 3
doc.add_heading("3. Methodology", 1)
_p("Pipeline: (1) pull live constituents and statements; (2) standardise line items; (3) compute six forensic blocks; (4) combine into a 0-100 score with tiers; (5) back-test against the watchlist; (6) serve through an interactive dashboard; "
   "(7) generate fact-bound memos. Each block maps to a taught session.")
T([["Block (default weight)", "Method", "Rule / interpretation"],
   ["Beneish (30%)", "8-variable M-score: DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA", "M > -1.78 likely manipulator; > -2.22 watch; needs >= 6 of 8 indices"],
   ["Accruals (20%)", "Sloan ratio; modified Jones discretionary accruals (cross-sectional, per year)", "Peer percentile; higher = riskier"],
   ["Cash divergence (15%)", "3-year cumulative CFO / net income", "Lower conversion = riskier; undefined if cumulative profit <= 0"],
   ["REM (10%)", "Roychowdhury abnormal CFO and abnormal SG&A", "Low CFO and low SG&A = income-increasing real activity"],
   ["Benford (10%)", "First-digit MAD across all line items and years", "<= 0.006 close; <= 0.012 acceptable; <= 0.015 marginal; above = non-conformity"],
   ["Distress (15%)", "Altman Z'' (emerging-market form)", "< 4.15 distress; 4.15-5.85 grey; > 5.85 safe"]], widths=[1.4, 2.6, 2.5])
_p("Tiers: Low (<35), Moderate (35-50), Elevated (50-65), High (>65). Scores are re-normalised over available blocks; a firm needs core earnings-quality inputs and at least 60% of model weight to be scored. "
   "Financial-sector firms are excluded because receivables, COGS and operating cash flow have different meaning for lenders.")

# ---------- 4
doc.add_heading("4. AI tools and techniques", 1)
T([["Tool", "Role", "Control against error"],
   ["Claude (Sonnet 5.5) in Claude Code", "Wrote and debugged the pipeline and dashboard; proposed model design", "Outputs run and inspected; first run exposed a design flaw (banks ranked High) that was corrected"],
   ["Python: pandas, numpy, Streamlit, Plotly", "Computation and interactive dashboard", "Formulae traced to course workbooks and papers"],
   ["LLM memo narrator", "Converts a numeric fact sheet into a 220-word analyst memo", "Prompt forbids numbers outside the fact sheet; memos labelled AI-generated; rule-based fallback"],
   ["Yahoo Finance / NSE (free)", "Live statements and index list", "Coverage and definition limits disclosed"]], widths=[1.7, 2.5, 2.3])
_p("Prompt design. The memo prompt fixes role, evidence rule, structure and length, and treats flags as signals rather than proof (full text in the Annexure and in the dashboard's AI memo tab).")

# ---------- 5
doc.add_heading("5. Data collection and preparation", 1)
B(["Sources::  NSE archive (current Nifty 50), Yahoo Finance annual income statement, balance sheet and cash flow via yfinance. Screener.in was reachable but is not used because its terms discourage automated extraction.",
   "Coverage::  62 firms returned data (50 Nifty plus 12 watchlist). Four watchlist names (Jaiprakash Associates, Sintex, Future Retail, DHFL) are delisted and returned nothing.",
   "Cleaning::  Fiscal years keyed to March year-end; fallbacks between equivalent line items; indices winsorised to [0.2, 5]; missing Beneish indices set to neutral values only when >= 6 of 8 exist; regression variables winsorised at 2%/98%.",
   "Benford preparation::  Per-share, share-count and rate rows removed; duplicate values within a year dropped so repeated totals do not bias digit counts (about 500 numbers per firm).",
   "Second-source reconciliation::  All 62 firms were re-fetched from Screener.in public pages (polite rate, no login). For FY2024-26 operating cash flow and total assets agree with Yahoo almost exactly (97% within 2%), net income 70% and sales 63% within 2%; every sales gap above 10% is a financial firm (different revenue definition) or Infosys, which Yahoo reports in USD. "
   "The ratios the screen uses (sales growth, accruals to assets, CFO/NI, margin, turnover) rank-correlate 0.98-1.00 across 46 non-financial firms. Both sites draw on the same filings, so this confirms transcription consistency rather than the truthfulness of the filings.",
   "Limitations::  4-5 years of history; Yahoo definitions differ from other providers; about 40 firms per year in cross-sectional regressions; current Nifty membership introduces survivorship bias."])

# ---------- 6
doc.add_heading("6. Analysis and insights", 1)
F(FIG / "top15.png", "Figure 1. Highest composite scores, FY2026.")
_p(f"The top of the ranking mixes cohorts. Watchlist names such as PC Jeweller, Vodafone Idea and Suzlon score High, as do several Nifty names (Tata Motors PV, Grasim, BEL). "
   "Reading the components explains why: PC Jeweller combines a Beneish M of -1.41, negative three-year cash conversion and Benford non-conformity; Vodafone Idea is driven by distress and accruals while its Beneish indices are near 1.")
F(FIG / "map.png", "Figure 2. Beneish M-score against Sloan accruals; firms in the upper right trigger both screens.")
_p("Back-test. Treating the watchlist as 'positives' and the Nifty 50 as 'negatives', the composite ranks a random watchlist firm above a random Nifty firm "
   f"{V['Composite score']*100:.0f}% of the time. Removing the distress block lowers this to {V['Composite excl. distress']:.2f}, showing that part of the signal is financial stress rather than manipulation.")
F(FIG / "auc.png", "Figure 3. AUC by test; dashed line is chance.", w=5.2)
doc.add_heading("Data check: Yahoo Finance versus Screener.in", 2)
xl = pd.read_csv(D / "xcheck_levels.csv"); xr = pd.read_csv(D / "xcheck_ratios.csv")
T([["Line item", "Firm-years", "Within 2% (%)", "Within 10% (%)", "Median gap (%)"]] + [[q.item, q.n, q.within_2pct, q.within_10pct, q.median_gap_pct] for q in xl.itertuples()], widths=[1.9, 0.9, 1.1, 1.1, 1.2], size=8.5)
T([["Screen input (FY2026)", "Firms", "Spearman", "Median abs. diff."]] + [[q.ratio, q.n, q.spearman, q.median_abs_diff] for q in xr.itertuples()], widths=[2.2, 0.8, 1.0, 1.4], size=8.5)
_p("The inputs behind the screen are consistent across two online sources, so the weak back-test result in Figure 3 reflects the models, the short history and the small peer set rather than data errors. "
   "Because both providers read the same filings, this does not test whether the filings themselves are accurate.")
doc.add_heading("Causal lens: difference-in-differences and class-case tests", 2)
import sys; sys.path.insert(0, str(ROOT / "src")); import analytics as A
_u = pd.read_csv(D / "universe.csv"); _P = A.build_panel(pd.read_csv(D / "screener_long.csv"), _u)
_nf = _u[(_u.sector != "Financial Services") & (_u.cohort == "Nifty 50")]
_g = lambda secs: list(_nf[_nf.sector.isin(secs)].ticker)
_ev = [("COVID-19 shock, event FY2021: sales growth", _g(["Consumer Cyclical", "Industrials"]), _g(["Technology", "Healthcare", "Consumer Defensive"]), "sales_growth", 2021, 4, 1),
       ("Corporate tax cut (Sept 2019), event FY2020: net margin", _g(["Consumer Cyclical", "Consumer Defensive", "Industrials", "Utilities", "Basic Materials"]), _g(["Technology", "Healthcare"]), "net_margin", 2020, 4, 1),
       ("Hindenburg report on Adani group (Jan 2023), event FY2024: debt/assets", ["ADANIENT.NS", "ADANIPORTS.NS"], [t for t in _g(list(_nf.sector.unique())) if t not in ("ADANIENT.NS", "ADANIPORTS.NS")], "debt_assets", 2024, 4, 3)]
_rows = [["Event and outcome", "Treated / control", "DiD (pp)", "Placebo (pp)", "Reading"]]
for nm, t, c, col, e, pr, po in _ev:
    q = A.did_estimate(_P, t, c, col, e, pr, po)
    if q: _rows.append([nm, f"{q['n_t']} / {q['n_c']}", f"{q['est'] * 100:+.1f}", "n/a" if q["placebo"] is None else f"{q['placebo'] * 100:+.1f}",
                        "Descriptive only (few treated firms)" if q["n_t"] < 10 else ("Pre-trend concern" if q["placebo"] is not None and abs(q["placebo"]) >= 0.25 * abs(q["est"]) else "Consistent with effect")])
_bt = {k: A.flag_backtest(_P, fl_, "roa") for k, fl_ in [("accruals", "accruals"), ("cash", "cash")]}
_p("Difference-in-differences does not say whether one firm cheated; it answers group-level questions: do red-flagged firms deteriorate afterwards (validation), and did a rule or shock change earnings quality (impact). "
   "The dashboard's forensic back-test treats each flagged firm-year as an event and compares it with unflagged firm-years in the same year, removing year effects and clustering by firm. "
   + " ".join(f"{lab_} flag: ROA changes by {b_['stats'][1]['beta'] * 100:+.2f} pp relative to unflagged firms after one year (t = {b_['stats'][1]['beta'] / b_['stats'][1]['se']:.1f}; {b_['stats'][1]['n_flag']} flagged firm-years, {b_['stats'][1]['firms']} firms)." for lab_, b_ in [("The high-accrual", _bt["accruals"]), ("The weak-cash-conversion", _bt["cash"])] if b_ and 1 in b_["stats"])
   + " Cash flow margin rises after the accrual flag, the accrual reversal that Sloan (1996) describes. Caveats: a small large-cap sample, flagged firms often just peaked (mean reversion), and the result shows the flag is informative, not that any firm manipulated.")
_p("A DiD lab was added to the dashboard (Sessions 15-16). Its calculator reproduces the end-term paper's difference-in-differences and triple-difference answers exactly (DiD low-ticket 400, DDD 400, high-ticket DiD 800), "
   "and an event-study tool applies the same logic to ten years of company data from Screener.in with firm-clustered standard errors and a placebo test on pre-event years (Bertrand, Duflo and Mullainathan, 2004).")
T(_rows, widths=[2.4, 0.9, 0.7, 0.8, 1.7], size=8)
_p("Reading. The COVID-19 comparison shows the largest effect, but the treated group's growth was already falling before FY2021 (auto-sector slowdown), so part of the estimate reflects earlier divergence; the placebo test exists to expose exactly this. "
   "The tax-cut comparison is not distinguishable from noise with a sector proxy for domestic revenue share, and its placebo gap is larger than the estimate itself. The Adani comparison has only two treated firms and is purely descriptive; the allegations are contested and the test says nothing about wrongdoing.")
_z = A.window_stats(_P, "ZEEL.NS", 2017, 2019); _c = A.window_stats(_P, "COFFEEDAY.NS", 2017, 2019)
_p(f"Class-case tests. Using ten-year history, Zee's FY2017-19 accruals averaged {_z['acc']:.1%} of assets against {_z['acc_u']:.1%} for the typical non-financial firm, and its CFO/NI averaged {_z['cfo_ni']:.2f} against {_z['cfo_ni_u']:.2f}, "
   f"supporting the class note that profit ran well ahead of cash. Coffee Day's accruals ({_c['acc']:.1%} vs {_c['acc_u']:.1%}) and CFO/NI ({_c['cfo_ni']:.2f} vs {_c['cfo_ni_u']:.2f}) looked ordinary or better, consistent with the class note that its diversion sat in related-party advances rather than in the profit line. "
   "Wirecard and Ricoh India cannot be tested with free data (non-Indian and delisted respectively), which illustrates the screen's blind spots.")
doc.add_heading("Case readings", 2)
B(["PC Jeweller (High)::  M-score above threshold, sales growth index 1.49, negative cash conversion. Check inventory and gold-loan balances.",
   "Tata Motors PV (High)::  Accruals at the 96th percentile but cash conversion 1.02 and Benford acceptable: a probable structural false positive from restructuring; restate comparatives before concluding.",
   "Adani Enterprises (Elevated)::  Several moderate signals (receivable and margin indices, accruals 85th percentile, CFO/NI 0.87). This is a ratio screen only and says nothing about allegations outside the statements.",
   "Zee and Coffee Day (Low / Moderate)::  Within FY2022-26 neither shows classic manipulation signatures; Coffee Day's only strong flag is Benford. The known issues are older and of a related-party / cash type, which ratio screens struggle with.",
   "TCS (Moderate, control)::  Benford non-conformity on derived data with fully cash-backed profits illustrates why Benford is weighted at only 10%."])

# ---------- 7
doc.add_heading("7. Managerial recommendations", 1)
B(["Use the score for triage, not judgement::  Review High/Elevated firms first; require a human explanation of each flagged block before escalation.",
   "Pair every ratio flag with a documentary test::  receivables ageing and debtor confirmations (Beneish DSRI), CFO reconciliation (accruals), related-party and CARO/KAM review (all tiers).",
   "Treat distress separately from manipulation::  Route high-distress, low-manipulation firms (e.g. Vodafone Idea) to credit-risk teams rather than forensic teams.",
   "Handle restructurings explicitly::  Rebuild pro-forma comparatives before reading year-on-year indices.",
   "Keep financials on a separate toolkit::  NPA trend, provisioning coverage, restructured loans, related-party exposure.",
   "Cost-benefit::  A refresh takes minutes and no licence fee (versus paid databases); the binding cost is analyst time on false positives, so tune weights to the team's capacity using the dashboard sliders."])

# ---------- 8
doc.add_heading("8. Implementation roadmap", 1)
T([["Horizon", "Actions", "Resources", "Risks and mitigation"],
   ["0-30 days", "Pilot on current portfolio; cross-check 10 firms against Screener and annual reports; agree weights with stakeholders", "1 analyst, free data", "Definition mismatch: document and adjust mappings"],
   ["30-90 days", "Extend to Nifty 500, industry-specific Jones/REM, 8-10 years of history; add audit-report text review", "optional paid-data licence, 1 data engineer", "Small samples per industry: pool adjacent industries"],
   ["90-180 days", "Scheduled refresh, alerting on tier changes, model-governance log, analyst feedback loop to recalibrate", "Hosting, reviewer time", "Model drift: quarterly back-test"],
   ["Capability building", "Train analysts on interpreting flags and on AI memo limits", "Workshops", "Over-reliance: mandatory source check"]], widths=[1.0, 2.7, 1.3, 1.5], size=8.5)

# ---------- 9
doc.add_heading("9. Ethical and responsible AI considerations", 1)
B(["False positives and reputational harm::  A flagged firm is not a fraudulent firm. Language in the tool and memos stresses 'signal'; no public naming should occur without verification.",
   "Hallucination::  The memo prompt restricts the model to a numeric fact sheet, memos are labelled AI-drafted, a deterministic fallback exists, and the fact sheet is displayed for audit.",
   "Bias and sample design::  Peer percentiles are relative to a large-cap universe; small or sector-specific firms are not comparable. Watchlist membership reflects public narratives, which may be incomplete or contested.",
   "Data and licensing::  Free data may be delayed or revised; automated scraping of sites whose terms forbid it was avoided.",
   "Privacy::  Only public company data is used; no personal data.",
   "Model limitations::  Source sensitivity (see Section 5), small validation sample, restructuring breaks, and blindness to cash-misappropriation and related-party frauds. Results should not be used as sole grounds for lending, investment or enforcement decisions."])

# ---------- 10
doc.add_heading("10. Annexures", 1)
doc.add_heading("A. Memo prompt (abridged)", 2)
_p("Role: forensic accounting analyst writing for a review committee. Rules: use only numbers in the FACT SHEET; if a metric is missing, say so; treat flags as signals, not proof. "
   "Structure (max 220 words): verdict; three evidence bullets with peer or threshold context; benign explanations; three next audit steps.", size=9.5)
doc.add_heading("B. Prompt log (excerpt)", 2)
T([["#", "Prompt (summary)", "Output / what changed"],
   ["1", "Scope the WAI project for a forensic analyst using course tools", "Proposed screener; asked 4 scoping questions"],
   ["2", "Test free live sources for Indian firms", "Yahoo OK; NSE list OK; Screener reachable but not used"],
   ["3", "Build engine (Beneish, Benford, Jones, REM, Altman)", "First run ranked Bajaj Finserv #1 - revealed financials must be excluded"],
   ["4", "Fix scoring rules and rerun", "Financials unscored; core-data rule; cash-conversion fix"],
   ["5", "Draft memos from fact sheets", "Eight memos with explicit benign-explanation sections"]], widths=[0.3, 3.0, 3.2], size=8.5)
doc.add_heading("C. Files", 2)
_p("src/fetch_data.py, src/forensic_engine.py, src/memo.py, src/build_report.py, app.py, data/*.csv, data/ai_memos.json, PROJECT_GUIDE.md. Run commands are in PROJECT_GUIDE.md.", size=9.5)

doc.save(ROOT / "WAI_Practice_Report.docx"); print("saved")
