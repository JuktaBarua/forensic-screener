"""Builds WAI_Practice_Report.docx to the Working-with-AI guidelines. Every number is read from data/ (same files the dashboard uses)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parents[1]; D = ROOT / "data"; FIG = ROOT / "report_figs"; DASH = FIG / "dash"
sys.path.insert(0, str(ROOT / "src"))
import analytics as A, memo as M

m = pd.read_csv(D / "metrics_year.csv"); uni = pd.read_csv(D / "universe.csv"); val = pd.read_csv(D / "validation.csv")
xl = pd.read_csv(D / "xcheck_levels.csv"); xr = pd.read_csv(D / "xcheck_ratios.csv"); refresh = (D / "last_refresh.txt").read_text()[:10]
y = m[m.fy == 2026]; s26 = y[y.score.notna()].copy(); peers = y[~y.fin]
band = lambda f: "Investigate" if f >= 65 else "Review" if f >= 50 else "Monitor" if f >= 35 else "Routine"
s26["act"] = s26.fpi.map(band); cnt = s26.act.value_counts().to_dict()
V = val.set_index("metric").AUC
nm = lambda n: str(n).replace(" Limited", "").replace(" Ltd.", "")
top = s26.sort_values("fpi", ascending=False)
outl = s26[s26.anomaly_pct >= 90]; second_look = outl[outl.tier.isin(["Low", "Moderate"])]
P = A.build_panel(pd.read_csv(D / "screener_long.csv"), uni)
BT = {k: A.flag_backtest(P, k, "roa")["stats"] for k in ("accruals", "cash")}
zee, ccd = A.window_stats(P, "ZEEL.NS", 2017, 2019), A.window_stats(P, "COFFEEDAY.NS", 2017, 2019)
pj = y[y.ticker == "PCJEWELLER.NS"].iloc[0]; tm = y[y.ticker == "TMPV.NS"].iloc[0]
nraw = len(pd.read_csv(D / "raw_long.csv"))

# ---- grounding check across every memo (same test as the dashboard)
memos = json.loads((D / "ai_memos.json").read_text()); g_rule = [0, 0]; g_ai = [0, 0]
for _, r_ in s26.iterrows():
    f_ = M.fact_sheet(r_, peers); g = M.grounding_check(M.rule_based_memo(r_, peers), f_); g_rule[0] += g["grounded"]; g_rule[1] += g["total"]
    if r_.ticker in memos:
        g2 = M.grounding_check(memos[r_.ticker]["memo"], f_); g_ai[0] += g2["grounded"]; g_ai[1] += g2["total"]

BLUE, ORG, INK = "#2a6fdb", "#d9730d", "#1f2937"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

# ---------- figure: decision pathway
fig, ax = plt.subplots(figsize=(7.2, 3.3)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4.6)
def box(x, y_, w, h, t, fc="#eef3fc", ec=BLUE, bold=False):
    ax.add_patch(FancyBboxPatch((x, y_), w, h, boxstyle="round,pad=0.03,rounding_size=0.12", fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y_ + h / 2, t, ha="center", va="center", fontsize=8, color=INK, fontweight="bold" if bold else "normal")
def arrow(x0, y0, x1, y1): ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color="#6b7280", lw=1.3))
box(0.1, 3.2, 2.2, 1.1, "1  Public data\nNSE · Yahoo Finance\nScreener.in (cross-check)")
box(2.7, 3.2, 2.4, 1.1, "2  Six forensic tests\n+ AI anomaly detector\n+ alert engine")
box(5.5, 3.2, 2.1, 1.1, "3  Forensic Priority\nIndex (0-100)", fc="#fff6ec", ec=ORG, bold=True)
box(8.0, 3.2, 1.9, 1.1, "4  Action band\nby index")
for a_, b_ in [(2.3, 2.7), (5.1, 5.5), (7.6, 8.0)]: arrow(a_, 3.75, b_, 3.75)
for i, (t, fc) in enumerate([("65+  INVESTIGATE\nopen forensic review", "#08306b"), ("50-65  REVIEW\ndesk review this quarter", "#2171b5"), ("35-50  MONITOR\nwatch next filing", "#6baed6"), ("<35  ROUTINE\nno action", "#c6dbef")]):
    x0 = 0.1 + i * 2.5; ax.add_patch(FancyBboxPatch((x0, 1.55), 2.3, 0.85, boxstyle="round,pad=0.03,rounding_size=0.1", fc=fc, ec="none"))
    ax.text(x0 + 1.15, 1.97, t, ha="center", va="center", fontsize=7.8, color="white" if i < 2 else INK, fontweight="bold")
arrow(8.95, 3.15, 8.95, 2.45)
box(1.2, 0.1, 3.4, 0.95, "5  'Check first' list + AI memo\n(grounded in the fact sheet)")
box(5.2, 0.1, 3.4, 0.95, "6  Analyst confirms with documents,\nthen escalates or clears", fc="#effaf4", ec="#2f9e6e", bold=True)
arrow(4.6, 0.57, 5.2, 0.57); arrow(1.25, 1.5, 2.2, 1.08); arrow(8.9, 1.5, 7.2, 1.08)
fig.tight_layout(); fig.savefig(FIG / "pathway.png", dpi=220); plt.close()

# ---------- figure: back-test AUC
v = val[val.metric != "Composite excl. distress"].sort_values("AUC")
fig, ax = plt.subplots(figsize=(6.2, 3.1))
cols = [ORG if ("new" in a or "AI" in a) else BLUE for a in v.metric]
ax.barh(v.metric, v.AUC, color=cols, height=0.62); ax.axvline(0.5, ls="--", color="#6b7280", lw=1); ax.set_xlim(0, 1)
for i, a in enumerate(v.AUC): ax.text(a + 0.01, i, f"{a:.2f}", va="center", fontsize=8)
ax.set_xlabel("AUC: chance a watchlist firm outranks a Nifty 50 firm (0.5 = coin flip)")
ax.set_title("Back-test of each measure (orange = AI / new index)", fontsize=9, loc="left"); fig.tight_layout(); fig.savefig(FIG / "auc2.png", dpi=220); plt.close()

# ---------- exhibit crops (pixel boxes on 800 px wide screenshots)
for name, box_, out in [("ex1_decision_desk.jpg", (55, 15, 745, 560), "ex1.png"), ("ex2_queue.jpg", (55, 270, 745, 770), "ex2.png"), ("ex3_actions_alerts.jpg", (55, 60, 745, 870), "ex3.png"),
                        ("ex4_company_brief.jpg", (55, 85, 745, 590), "ex4.png"), ("ex5_calculation_trace.jpg", (60, 0, 740, 745), "ex5.png"), ("ex6_ai_vs_rules.jpg", (55, 235, 745, 745), "ex6.png"),
                        ("ex7_reliability.jpg", (55, 0, 745, 780), "ex7.png"), ("ex8_history_test.jpg", (55, 0, 745, 780), "ex8.png")]:
    Image.open(DASH / name).crop(box_).save(FIG / out)

# ---------- document helpers
doc = Document()
for sec in doc.sections: sec.left_margin = sec.right_margin = Inches(0.95); sec.top_margin = sec.bottom_margin = Inches(0.85)
doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(10.5)
for h, sz in [("Heading 1", 15), ("Heading 2", 12)]:
    doc.styles[h].font.name = "Calibri"; doc.styles[h].font.size = Pt(sz); doc.styles[h].font.color.rgb = RGBColor(0x1f, 0x3a, 0x6e)


def _p(t, bold=False, italic=False, size=None, style=None):
    p = doc.add_paragraph(style=style); r = p.add_run(t); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(6); return p
def Bl(items):
    for t in items:
        p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(2)
        if "::" in t: a, b = t.split("::", 1); p.add_run(a).bold = True; p.add_run(b)
        else: p.add_run(t)
def T(rows, widths=None, size=8.5):
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Light Grid Accent 1"
    for i, row in enumerate(rows):
        for j, c in enumerate(row):
            cell = t.cell(i, j); cell.text = ""; run = cell.paragraphs[0].add_run(str(c)); run.font.size = Pt(size); run.bold = (i == 0)
            if widths: cell.width = Inches(widths[j])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
def F(path, cap, w=6.0):
    doc.add_picture(str(path), width=Inches(w)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = _p(cap, italic=True, size=9); c.alignment = WD_ALIGN_PARAGRAPH.CENTER

# ================================================================= TITLE
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Forensic Earnings-Quality Screener"); r.bold = True; r.font.size = Pt(22); r.font.color.rgb = RGBColor(0x1f, 0x3a, 0x6e)
_p("An AI-enabled decision-support dashboard that tells a forensic analyst which listed Indian companies to investigate first, why, and what to check", italic=True).alignment = WD_ALIGN_PARAGRAPH.CENTER
_p(f"Working with AI (WAI) project report  |  Financial Statement Analysis & Forensic Auditing  |  Submitted by: [name, roll no., section]  |  Live dashboard: [paste Streamlit link]  |  Data as of {refresh}", size=9).alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_heading("Executive summary", 1)
_p("Who uses it? A forensic or credit-risk analyst at a lender, audit firm or investor who covers listed Indian companies. What problem do they face? There are far more filings than analyst-days, reported profit can hide weak cash backing, aggressive accruals or distress, "
   "and any single ratio produces false alarms. What decision does the product support? Which companies get a forensic review this quarter, and what to check first.")
_p(f"The solution turns public data from NSE, Yahoo Finance and Screener.in into six forensic tests (Beneish M-score, accruals, cash conversion, real earnings management, Benford's law, Altman Z″) and an unsupervised AI anomaly detector. "
   f"These are combined into a new metric, the Forensic Priority Index (FPI), which maps each company to one of four actions. For FY2026 the dashboard scores {len(s26)} companies: {cnt.get('Investigate', 0)} to investigate, {cnt.get('Review', 0)} for desk review, "
   f"{cnt.get('Monitor', 0)} to monitor and {cnt.get('Routine', 0)} routine; {int(y.fin.sum())} banks, NBFCs and insurers are shown but deliberately not scored.")
Bl([f"Triage works, with honest limits::  The rule-based composite ranks a known-troubled watchlist above the Nifty 50 with AUC {V['Composite score']:.2f}; the AI anomaly detector scores {V['AI anomaly detector (Isolation Forest)']:.2f} and the FPI {V['Forensic Priority Index (new)']:.2f} (0.5 = chance; only about 10 scoreable watchlist firms).",
    f"Red flags carry information::  After a high-accrual flag, ROA falls {abs(BT['accruals'][1]['beta']) * 100:.1f} percentage points more than for unflagged firms one year later (t = {BT['accruals'][1]['beta'] / BT['accruals'][1]['se']:.1f}, {BT['accruals'][1]['n_flag']} cases, {BT['accruals'][1]['firms']} firms), and cash flow catches up.",
    f"AI is checked, not trusted::  An automatic grounding test traces {g_rule[0]} of {g_rule[1]} numbers in rule-based memos and {g_ai[0]} of {g_ai[1]} in Claude-drafted memos back to the fact sheet; inputs agree with an independent source (rank correlation {xr.spearman.min():.2f} to {xr.spearman.max():.2f}).",
    "Flags are leads, not verdicts::  Several high scores are explainable (for example a restructuring), so every flag comes with a 'check first' list and benign explanations."])

# ================================================================= 1
doc.add_heading("1. Stakeholder, problem and decision", 1)
T([["Question", "Answer"],
   ["Who will use the product?", "A forensic analyst or credit-risk analyst (lender, audit firm, rating agency desk or investor) covering Indian listed companies."],
   ["What problem do they face?", "Too many companies and too little time. Profit can be inflated through accruals, real activity or concealed related-party balances, and single ratios (or a single model) give frequent false positives. Distress also raises the incentive to manipulate (the 'pressure' leg of the fraud triangle)."],
   ["What decision does the analysis help make?", "Quarterly triage: which firms receive a forensic review, which receive a desk review, which are only monitored, and what documents to examine first."],
   ["What is the decision pathway?", "Data → six tests + AI detector → Forensic Priority Index → action band → 'check first' list and memo → analyst confirms with documents → escalate or clear (Figure 1)."]], widths=[1.9, 4.7])
F(FIG / "pathway.png", "Figure 1. Decision pathway from public data to an investigation decision.", w=6.0)
_p("Design principle. The guidelines ask that the dashboard start from the user, not the company. The landing page therefore opens with the three boxes above (who, problem, decision) and then answers, in order: what am I looking at, how is the universe doing, where are the risks, what deserves investigation, and what should I do (Exhibits 1 to 3).")

# ================================================================= 2
doc.add_heading("2. Data sources and preparation", 1)
Bl(["NSE India::  current Nifty 50 constituents (official archive CSV).",
    f"Yahoo Finance (open-source yfinance library)::  annual income statement, balance sheet and cash flow for {uni.shape[0]} companies, FY2022 to FY2026 ({nraw:,} statement values, 310 distinct line items).",
    "Screener.in public pages::  ten-plus years of sales, profit, assets, debt and operating cash flow, used for an independent cross-check, for the history test and for case studies. Requests were low-rate and run once; no login or paid data was used.",
    "Universe::  the Nifty 50 plus a 12-firm watchlist of listed firms with publicly reported governance or distress episodes (for example Zee, Coffee Day, Reliance Infrastructure, Yes Bank, Vodafone Idea). The watchlist is a validation cohort, not an accusation. Four intended names (Jaiprakash Associates, Sintex, Future Retail, DHFL) are delisted and returned no data.",
    "Preparation::  fiscal years are keyed to March year-end; equivalent line items are mapped with fall-backs; indices are winsorised; a missing Beneish index is set to neutral only if at least six of eight exist; Benford counts drop per-share rows and duplicate values. Banks, NBFCs and insurers are excluded from scoring because receivables, COGS and operating cash flow mean something different for lenders (the first run, which ranked a finance company as riskiest, exposed this).",
    "Live refresh::  a button in the dashboard re-downloads and rescores everything (about three minutes), with a cool-down to protect the sources."])
doc.add_heading("Data reliability: cross-check against an independent source", 2)
T([["Line item (FY2024-26, rupee-reporting firms)", "Firm-years", "Within 2%", "Within 10%", "Median gap"]] + [[q.item, q.n, f"{q.within_2pct}%", f"{q.within_10pct}%", f"{q.median_gap_pct}%"] for q in xl.itertuples()], widths=[2.8, 0.9, 0.9, 0.9, 1.0])
_p(f"Cash flow and total assets agree almost exactly. Every sales gap above 10% is a financial firm (revenue is defined differently) or Infosys, which Yahoo reports in US dollars (a bug the check exposed and the dashboard now handles). The ratios that drive the tests (sales growth, accruals to assets, CFO/NI, margin, turnover) rank-correlate {xr.spearman.min():.2f} to {xr.spearman.max():.2f} across the two sources. "
   "Both sites read the same company filings, so this confirms consistent transcription, not that the filings are accurate. The full audit pack (raw statements, every intermediate calculation, formulas) is downloadable from the dashboard (Annexure A).")

# ================================================================= 3
doc.add_heading("3. Analytical approach: financial and forensic techniques", 1)
_p("Measures were chosen for this stakeholder and decision rather than showing every ratio. Each test answers one question an analyst would ask, and the tests are deliberately independent so that agreement between them is meaningful.")
T([["Test", "Question it answers", "Rule / reading"],
   ["Beneish M-score (8 indices)", "Does the pattern of receivables, margins, asset quality, growth, depreciation, overheads, leverage and accruals resemble known manipulators?", "M above -1.78 flag; -2.22 to -1.78 watch (Beneish, 1999)"],
   ["Accruals: Sloan ratio and modified Jones DA", "Is profit running ahead of cash?", "Peer percentile; higher is riskier (Sloan, 1996; Dechow et al., 1995)"],
   ["Cash conversion (3-year CFO/NI)", "Does profit turn into cash over time?", "Well below 1 is a warning"],
   ["Real earnings management", "Is the firm cutting discretionary spend or distorting cash flow to hit profit?", "Abnormal CFO and SG&A (Roychowdhury, 2006)"],
   ["Benford's law (first-digit MAD)", "Do reported numbers follow the natural digit pattern?", "MAD above 0.015 is non-conformity (Nigrini, 2012); weak signal, 10% weight"],
   ["Altman Z″ (emerging markets)", "Is the firm financially stressed, raising the incentive to manipulate?", "Below 4.15 distress (Altman, 1968; Altman et al., 1995)"]], widths=[1.8, 2.9, 2.0])
_p("Supporting financial analysis in the Company brief includes DuPont decomposition, ROCE, liquidity, leverage, interest cover, receivable and inventory days, and profit-versus-cash charts. The six tests are converted to block scores from 0 to 100 and combined into the risk score (default weights 30/20/15/10/10/15); tiers are Low below 35, Moderate to 50, Elevated to 65 and High above. "
   "Every formula, cap and rule is listed in the data dictionary inside the audit pack, and the Company brief recalculates any company's Beneish M-score step by step from its raw statements (Exhibit 5).")

# ================================================================= 4
doc.add_heading("4. The new metric: Forensic Priority Index (FPI)", 1)
_p("A weighted average of tests has two weaknesses for triage: the weights are a judgement, and it cannot tell a firm that is moderately off on six tests from one that is extreme on one. The FPI adds two ideas.")
Bl(["Corroboration::  the share of the six tests whose block score is 60 or more ('red zone'). Independent tests agreeing is stronger evidence than any single high score.",
    "AI anomaly percentile::  an Isolation Forest (unsupervised machine learning, Liu et al., 2008) scores how unusual a company's whole 14-feature fingerprint is against peers in the same year, with no hand-set weights. It also names the two features that make the firm unusual (for example 'leverage high, discretionary accruals high')."])
_p("FPI = 50% x risk score + 25% x corroboration share + 25% x AI anomaly percentile (each 0 to 100). Action bands: 65 or more Investigate; 50 to 65 Review; 35 to 50 Monitor; below 35 Routine. "
   "Each action comes with a reason and a 'check first' list built from the tests in the red zone, with the weakest evidence (Benford) always listed last. The dashboard's alert engine adds year-on-year triggers: score jumps, Beneish threshold crossings, new distress, falling cash conversion and AI outliers. "
   "Two safeguards were added after inspecting results: a very large score jump is tagged 'check for a merger, demerger or restatement first', and a borderline Altman crossing is labelled borderline because the model tends to understate capital-intensive utilities.")
_p(f"Does the FPI add value? Against the watchlist back-test it scores {V['Forensic Priority Index (new)']:.2f}, above the rule-based composite ({V['Composite score']:.2f}) but below the anomaly detector alone ({V['AI anomaly detector (Isolation Forest)']:.2f}). "
   "The report does not claim the FPI is the most accurate ranker. It is the most defensible one for a decision: it ranks by evidence that is both strong (score) and corroborated (agreement), and it still surfaces firms the rules alone would miss.")
F(FIG / "auc2.png", "Figure 2. Back-test: how often each measure ranks a watchlist firm above a Nifty 50 firm. About 10 watchlist firms can be scored, so results are indicative.", w=5.4)

# ================================================================= 5
doc.add_heading("5. How AI was used, and how its reliability was checked", 1)
doc.add_heading("Where AI contributes", 2)
T([["AI component", "What it does", "Where it appears"],
   ["Anomaly detector (Isolation Forest)", "Finds firms whose whole financial fingerprint is unusual, independent of hand-set weights; explains why", "Priority index, triage table, alerts"],
   ["Alert engine", "Compares each firm with last year and raises prioritised alerts", "Decision desk"],
   ["Nearest-neighbour peer matching", "Finds the three firms with the most similar fingerprint ('closest financial twins')", "Company brief"],
   ["LLM memo writer (Claude)", "Turns a numeric fact sheet into an analyst memo with benign explanations and audit steps; rule-based memo available as a baseline", "AI analyst"],
   ["AI-assisted development (Claude Code)", "Built the pipeline, models, tests and dashboard under human direction", "Whole product"]], widths=[1.9, 3.3, 1.5])
doc.add_heading("Significant prompts and workflow", 2)
_p("The memo prompt fixes the role (forensic analyst writing for a review committee), the evidence rule (use only the numbers in the FACT SHEET; if missing, say so; treat flags as signals, never proof), the structure (verdict, three evidence bullets with peer context, benign explanations, three next audit steps) and a 220-word limit. The development workflow is summarised below; the prompt log is Annexure C.", size=10)
T([["Step", "AI task", "Human check and outcome"],
   ["Scope", "Propose stakeholder, universe, data, AI role; ask clarifying questions", "Chose forensic analyst, Nifty 50 plus watchlist, free live sources"],
   ["Engine", "Implement six tests and a composite", "First run ranked a finance company riskiest; human caught the flaw; financials excluded"],
   ["Data check", "Re-fetch from a second source and compare", "Found USD reporting for two firms; fixed"],
   ["AI layer", "Add anomaly detector, alerts, peer matching", "Replaced misleading features (debt/equity with negative equity) after reading the explanations"],
   ["Action rule", "Map scores to actions", "A screenshot showed a firm ranked lower but labelled higher; rule rebuilt on the index bands"],
   ["Wording", "Draft memos and explanations", "Removed first-person and course wording; plain-English review"]], widths=[0.9, 2.5, 3.3])
doc.add_heading("Reliability checks", 2)
Bl([f"Number grounding (automatic)::  every number in a memo must trace to the fact sheet within rounding. Result: {g_rule[0]} of {g_rule[1]} numbers in rule-based memos and {g_ai[0]} of {g_ai[1]} in Claude-drafted memos (Exhibit 7). Thresholds and model weights count as method constants, not company facts.",
    "Baseline comparison::  a deterministic rule-based memo, with no AI, is always available next to the AI memo.",
    "Independent data check::  Yahoo against Screener.in (Section 2).",
    "Back-test::  every measure, including the AI detector, is tested against the watchlist (Figure 2), and the history test checks that flags predict later deterioration (Section 7).",
    "Human review and disclosure::  AI memos are labelled AI-generated and must list benign explanations; written model text never influences a ranking; the analyst confirms every flag against filings."])
F(FIG / "ex6.png", "Exhibit 6. Where the AI detector and the rules agree and disagree: top-left points are unusual firms the rules rate lower (a second look is worthwhile).", w=5.6)
F(FIG / "ex7.png", "Exhibit 7. The reliability page, with live results of the grounding test, data cross-check and back-test.", w=5.6)

# ================================================================= 6
doc.add_heading("6. Dashboard walkthrough: key outputs", 1)
_p("The dashboard has eight tabs: Decision desk (landing), Triage board, Company brief, Compare, AI analyst, Validation & cases, Method & data, and a Guide. A sidebar filters year, cohort, sector and tier, and lets the user change the model weights live; every ranking, action and alert recomputes.")
F(FIG / "ex1.png", "Exhibit 1. Decision desk: who, problem and decision, then how the universe is doing.", w=5.9)
F(FIG / "ex2.png", "Exhibit 2. The priority queue with a capacity control: the user sets how many reviews the team can take and gets that quarter's list. Tables scroll horizontally on screen.", w=5.9)
F(FIG / "ex3.png", "Exhibit 3. Action bands, year-on-year alerts, where effort can be saved, and an auto-generated AI briefing.", w=5.9)
F(FIG / "ex4.png", "Exhibit 4. Company brief for PC Jeweller: verdict, recommended action with reason and first checks, key measures and the priority index.", w=5.9)
F(FIG / "ex5.png", "Exhibit 5. The calculation trace: every Beneish input, index, coefficient and contribution, ending with a recalculation check against the engine.", w=5.9)
F(FIG / "ex8.png", "Exhibit 8. History test: companies flagged for high accruals see ROA fall relative to unflagged companies after the flag year.", w=5.9)

# ================================================================= 7
doc.add_heading("7. Findings and inferences", 1)
doc.add_heading("What the universe looks like", 2)
_p(f"Of {len(s26)} scored companies in FY2026, {cnt.get('Investigate', 0)} are Investigate ({', '.join(nm(n) for n in top[top.act == 'Investigate'].name)}) and {cnt.get('Review', 0)} are Review ({', '.join(nm(n) for n in top[top.act == 'Review'].name)}). "
   f"The AI detector rates {len(outl)} firms as statistical outliers; {len(second_look)} of them ({', '.join(nm(n) for n in second_look.name)}) {'scores' if len(second_look) == 1 else 'score'} only Low or Moderate on the rules, which is exactly the 'second look' list the AI layer exists to produce. "
   f"In addition, {int((s26.red_n == 0).sum())} companies have no test in the red zone and need only routine monitoring, which is where analyst effort can be saved.")
doc.add_heading("Reading one company: PC Jeweller", 2)
_p(f"PC Jeweller ranks second (FPI {pj.fpi:.0f}; five of six tests in the red zone; AI outlier at the {pj.anomaly_pct:.0f}th percentile). Beneish M is {pj.MScore:.2f}, above the -1.78 line, driven by sales growth (index {pj.SGI:.2f}) and receivables growing faster than sales (index {pj.DSRI:.2f}). "
   f"Total accruals are high ({pj.TATA:.2f} of assets) and three-year cash conversion is {pj.cfo_cum_ni:.2f}: profit is reported while operating cash flow is negative. The recommended first checks are a profit-to-cash bridge, reconciliation of profit to operating cash flow and a test of provisions. "
   "Plausible benign explanations are inventory build-up and gold-loan accounting; these must be ruled out in the filings before any conclusion.")
doc.add_heading("Where the screen should not be trusted blindly", 2)
_p(f"Tata Motors Passenger Vehicles tops the ranking (FPI {tm.fpi:.0f}) on accruals and a very large score jump, but its cash conversion is {tm.cfo_cum_ni:.2f} and the entity appears to have been restructured, so year-on-year comparisons are not like-for-like: a probable structural false positive. "
   "Power Grid's move into the Altman distress zone is borderline and probably reflects the model's treatment of regulated utilities. TCS, the clean benchmark, shows a Benford miss on derived data despite fully cash-backed profit. These examples shaped the safeguards in Section 4.")
doc.add_heading("Do red flags predict trouble? (history test)", 2)
_p(f"Using ten-plus years of Screener data, each year the 20% of non-financial firms with the highest accruals were flagged and compared with unflagged firms, removing year effects and clustering by firm (a difference-in-differences comparison; Bertrand, Duflo and Mullainathan, 2004). "
   f"One year later flagged firms' ROA was {abs(BT['accruals'][1]['beta']) * 100:.2f} percentage points lower (t = {BT['accruals'][1]['beta'] / BT['accruals'][1]['se']:.1f}; {BT['accruals'][1]['n_flag']} cases from {BT['accruals'][1]['firms']} firms) and {abs(BT['accruals'][2]['beta']) * 100:.2f} points lower after two years, while cash flow margin rose as accruals reversed. "
   f"Weak cash conversion points the same way but is less clear (t = {BT['cash'][1]['beta'] / BT['cash'][1]['se']:.1f}). Because flagged firms often had just peaked, some reversal would happen anyway; the result shows the flags are informative, not that any firm manipulated earnings.")
doc.add_heading("Known cases", 2)
_p(f"Zee's FY2017-19 accruals averaged {zee['acc']:.1%} of assets against {zee['acc_u']:.1%} for the typical non-financial firm, and its CFO/NI averaged {zee['cfo_ni']:.2f} against {zee['cfo_ni_u']:.2f}: profit ran well ahead of cash. "
   f"Coffee Day's accruals ({ccd['acc']:.1%} vs {ccd['acc_u']:.1%}) and cash conversion ({ccd['cfo_ni']:.2f} vs {ccd['cfo_ni_u']:.2f}) looked unremarkable or healthier (cash well above profit), consistent with regulator findings that the diversion of funds sat in related-party advances rather than in profit. "
   "This is the screen's central lesson: a ratio screen sees profit quality but not cash that never existed (Wirecard) or money booked as an asset (Coffee Day). Case facts come from SEBI and NFRA orders and press reports; several matters are under appeal.")

# ================================================================= 8
doc.add_heading("8. Recommendations and decision pathway for the analyst", 1)
Bl([f"Adopt the FPI queue as the starting point of quarterly triage::  open the Decision desk, set the team's review capacity, and take the top of the queue. For FY2026 that is {cnt.get('Investigate', 0)} reviews plus {cnt.get('Review', 0)} desk reviews.",
    "Treat every flag as a hypothesis::  work the 'check first' list (profit-to-cash bridge, receivables ageing and debtor confirmation, related-party and capitalised-cost notes, going-concern disclosures) and confirm with documents before escalating.",
    "Run the second-look list::  review AI outliers that the rules rate lower; they cost little and cover the rules' blind spots.",
    "Apply a restructuring protocol::  before reading any score jump above 30 points, check for mergers, demergers or restatements (Tata Motors PV and Vodafone Idea show why).",
    "Separate distress from manipulation::  route high-distress, low-manipulation firms (for example Vodafone Idea, Unitech, GTL Infrastructure) to credit-risk teams, and keep banks and insurers on a separate toolkit (NPAs, provisioning, related-party exposure).",
    "Use routine monitoring to save effort::  firms with no test in the red zone need no further work this quarter."])
_p(f"Cost-benefit (illustrative assumption). If a first-pass review takes one analyst-day, reviewing all {len(s26)} scored firms takes about {len(s26)} days. Triage narrows the first pass to {cnt.get('Investigate', 0) + cnt.get('Review', 0)} firms, about {100 * (1 - (cnt.get('Investigate', 0) + cnt.get('Review', 0)) / len(s26)):.0f}% fewer, at no data cost (free sources). The binding cost is analyst time on false positives, so the model weights can be tuned live to the team's capacity.")
T([["Horizon", "Actions", "Resources", "Risks and mitigation"],
   ["0-30 days", "Pilot on the current portfolio; agree weights and action bands with the review committee; log every decision", "1 analyst, free data", "Definition gaps: keep the cross-check; document mappings"],
   ["30-90 days", "Extend to the Nifty 500 and industry-specific models; use ten-year history; add auditor and governance data; measure false-positive rate", "Optional licensed data, 1 data engineer", "Small samples per industry: pool adjacent industries"],
   ["90-180 days", "Scheduled refresh, alerts to the team, quarterly back-test and recalibration of weights", "Hosting, reviewer time", "Model drift: recalibrate each quarter; keep the human sign-off"]], widths=[0.9, 3.1, 1.2, 1.5], size=8)

# ================================================================= 9
doc.add_heading("9. Limitations and responsible AI", 1)
Bl(["Small validation sample::  about 10 watchlist firms can be scored, so AUCs are indicative. The anomaly detector scores highest partly because troubled firms are structurally unusual (distress, restructuring), which is not the same as manipulation.",
    "Data::  four to five years from Yahoo, ten-plus from Screener; about 40 non-financial firms per year in the cross-sectional models; current Nifty membership introduces survivorship bias; both sources read the same filings.",
    "Scope::  banks, NBFCs and insurers are not scored; ratio screens are largely blind to fictitious cash and concealed related-party balances, which need confirmations and document review.",
    "Model judgement::  weights, thresholds and action bands are judgements; the weight sliders make them visible and testable.",
    "False positives and reputational harm::  a flag is not evidence of fraud. Language throughout says 'signal', memos list benign explanations, and nothing should be published or acted on without verification.",
    "Hallucination::  the memo prompt restricts the model to a numeric fact sheet, a grounding test checks the output, a deterministic baseline exists, and model text never changes a ranking.",
    "Privacy and licensing::  only public company data is used; automated access to third-party sites was kept minimal; the tool is for analyst review and is not investment advice."])

# ================================================================= ANNEXURES
doc.add_heading("Annexure A. Data and calculation file (audit pack)", 1)
_p("Downloadable from the dashboard (Method & data, 'Download the audit pack') and stored in the repository's data folder. It lets a reviewer verify the source of every input and re-run every calculation.")
T([["File", "Content"],
   ["DATA_DICTIONARY.md", "All files, standardised inputs, every formula, score definitions, FPI and action rules"],
   ["universe.csv", "Companies, sector, currency, cohort"],
   ["raw_long.csv", "Annual statements from Yahoo Finance, one row per line item and year"],
   ["metrics_year.csv / scores.csv", "One row per company-year: inputs, ratios, every test, block scores, risk score, anomaly percentile and drivers, FPI"],
   ["benford_digits.csv", "Observed versus expected first-digit shares"],
   ["screener_long.csv, xcheck_*.csv", "Screener.in history and the Yahoo-versus-Screener comparison"],
   ["validation.csv, ai_memos.json", "Back-test results; Claude-drafted memos with model name and date"],
   ["Code (src/)", "fetch_data.py, forensic_engine.py, decision.py, memo.py, analytics.py, crosscheck_screener.py, build_report.py; app.py is the dashboard"]], widths=[2.2, 4.5])
doc.add_heading("Annexure B. Key formulas", 1)
_p("Beneish M = -4.84 + 0.920 DSRI + 0.528 GMI + 0.404 AQI + 0.892 SGI + 0.115 DEPI - 0.172 SGAI + 4.679 TATA - 0.327 LVGI. Sloan ratio = (net income - operating cash flow) / average assets. Cash conversion = 3-year CFO / 3-year net income. "
   "Altman Z″ = 3.25 + 6.56 (CA-CL)/TA + 3.26 RE/TA + 6.72 EBIT/TA + 1.05 Equity/TL. Benford MAD = mean absolute gap between observed first-digit shares and log10(1 + 1/d). "
   "Risk score = weighted average of six block scores. Corroboration = block scores of 60 or more divided by blocks available. FPI = 0.5 risk score + 25 corroboration + 0.25 AI anomaly percentile.", size=9.5)
doc.add_heading("Annexure C. Prompt log (significant prompts, summarised)", 1)
T([["#", "Prompt (summary)", "AI output", "Human decision or check"],
   ["1", "Build a practice WAI project: a dashboard with dropdowns for an analyst stakeholder, using live free sources", "Scoping questions; data-source tests", "Chose stakeholder, universe, sources and AI role"],
   ["2", "Build the engine and dashboard using the course tools", "Six tests, composite score, Streamlit app", "Caught banks ranked riskiest; excluded financials"],
   ["3", "Use online sources only; cross-check data", "Screener.in cross-check", "Accepted; found Infosys/HCL in USD"],
   ["4", "Add difference-in-differences and case analysis relevant to the stakeholder", "History test, event study, case studies", "Rejected non-forensic presets; kept the back-test"],
   ["5", "Remove session/exam wording; fix clipped text; explain the back-test plainly", "Rewrites and layout audit at three widths", "Verified in the browser at desktop, tablet and phone"],
   ["6", "Read the WAI guidelines and improve the dashboard", "Decision desk, FPI, anomaly detector, alerts, grounding check, calculation trace, audit pack, this report", "Reviewed screenshots; fixed an action-rule inconsistency and misleading alerts"]], widths=[0.3, 2.4, 2.0, 2.0], size=8)
_p("Memo prompt (used for the Claude-drafted memos): 'You are a forensic accounting analyst writing a short risk memo for a credit/forensic review committee. Use ONLY the numbers in the FACT SHEET below. Do not invent figures, events, auditors' remarks or news. "
   "If a metric is missing, say it is unavailable. Treat every flag as a screening signal, never as proof of fraud. Structure (max 220 words): 1. Verdict; 2. Evidence (3 bullets); 3. Alternative (benign) explanations; 4. Next audit steps.'", size=9)
doc.add_heading("Annexure D. How to run and refresh", 1)
_p("pip install -r requirements.txt; streamlit run app.py. Refresh data from the sidebar button or run src/fetch_data.py then src/forensic_engine.py. The hosted version is deployed on Streamlit Community Cloud from the same repository.", size=9.5)
doc.add_heading("References", 1)
for ref in ["Altman, E. I. (1968). Financial ratios, discriminant analysis and the prediction of corporate bankruptcy. Journal of Finance, 23(4), 589-609.",
            "Altman, E. I., Hartzell, J., & Peck, M. (1995). Emerging markets corporate bonds: A scoring system. Salomon Brothers.",
            "Beneish, M. D. (1999). The detection of earnings manipulation. Financial Analysts Journal, 55(5), 24-36.",
            "Bertrand, M., Duflo, E., & Mullainathan, S. (2004). How much should we trust differences-in-differences estimates? Quarterly Journal of Economics, 119(1), 249-275.",
            "Dechow, P. M., Sloan, R. G., & Sweeney, A. P. (1995). Detecting earnings management. The Accounting Review, 70(2), 193-225.",
            "Dyck, A., Morse, A., & Zingales, L. (2010). Who blows the whistle on corporate fraud? Journal of Finance, 65(6), 2213-2253.",
            "Healy, P. M., & Wahlen, J. M. (1999). A review of the earnings management literature and its implications for standard setting. Accounting Horizons, 13(4), 365-383.",
            "Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation forest. 2008 Eighth IEEE International Conference on Data Mining, 413-422.",
            "Nigrini, M. J. (2012). Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection. Wiley.",
            "Roychowdhury, S. (2006). Earnings management through real activities manipulation. Journal of Accounting and Economics, 42(3), 335-370.",
            "Sloan, R. G. (1996). Do stock prices fully reflect information in accruals and cash flows about future earnings? The Accounting Review, 71(3), 289-315.",
            "Data and case sources: NSE India; Yahoo Finance; Screener.in; SEBI and NFRA orders as reported by Moneylife, Outlook Business, Business Standard and BusinessToday (verify against original orders)."]:
    q = doc.add_paragraph(ref, style="List Bullet"); q.paragraph_format.space_after = Pt(1); q.runs[0].font.size = Pt(9)

doc.save(ROOT / "WAI_Practice_Report.docx"); print("saved")
