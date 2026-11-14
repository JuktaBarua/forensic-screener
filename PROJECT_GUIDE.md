# WAI Practice Project: Forensic Earnings-Quality Screener

**Course:** FSAFA, IIM Ranchi, Term V. **WAI** = "Working with AI" (25% mid-term).
**Stakeholder:** forensic / fraud analyst. **Universe:** Nifty 50 + a watchlist of Indian firms with publicly reported governance or distress episodes.

Legend: 🧑 **YOU** = the thinking and judgement your grade depends on in the real project. 🤖 **CLAUDE** = what I did in this practice run. In the real project you will do both columns, with AI as your assistant.

---
## The 10 report sections → what the professor expects → where it lives here

| # | Rubric section | 🤖 What Claude did here | 🧑 What YOU must do on the real project |
|---|---|---|---|
| 1 | Problem identification | Framed: *"Which listed firms deserve forensic scrutiny first, with limited analyst time?"* | Pick **your own** problem; get real evidence (a scandal, an RBI/SEBI order); name stakeholders; write a 1-sentence problem statement. Choose a problem you personally care about, because the professor can tell. |
| 2 | Literature review (8–10 sources) | Drafted 12 candidate sources in the report | **Open every source, read the abstract/intro, and verify the citation.** AI can invent or garble references. Add 2–3 Indian/practitioner sources (SEBI, ICAI, case PDFs from class). |
| 3 | Methodology | Pipeline: fetch → clean → score → dashboard → AI memo | Draw your own flowchart; justify each method with a *course session*. |
| 4 | AI tools & techniques | Claude (code, analysis), LLM narrator, prompt design | Keep a **prompt log from day 1** (what you asked, what came back, what you changed). |
| 5 | Data collection & prep | `src/fetch_data.py` (NSE + Yahoo); cleaning rules in `forensic_engine.py` | Use a primary source plus an independent second source, and document missing values and why. |
| 6 | Analysis & insights | `forensic_engine.py` + `app.py` dashboard | Interpret in business language: *so what for the analyst?* Don't just paste charts. |
| 7 | Managerial recommendations | Drafted in the report | Make them specific and costed: who does what, and how many analyst-hours? |
| 8 | Implementation roadmap | Drafted (30/60/90-day) | Keep it realistic. Professors penalise wishlists. |
| 9 | Ethics & responsible AI | Listed: false positives, defamation risk, hallucination, data licensing | Add your own examples and say what you did to mitigate them. |
| 10 | Annexures | Prompt log, code, screenshots, memo prompt | Collect as you go. Don't rebuild at the end. |

**Deliverables checklist:** report 10–12 pp · prompt log · code · dashboard · deck 8–10 slides · 3-min video · organised data/repo link.

---
## Step-by-step workflow (what a good student does)

### Step 0: Scope (🧑 YOU decide, 🤖 asked you 4 questions)
Stakeholder, universe, data, AI role. **Lesson:** decide this *before* touching data. Mine: forensic analyst · Nifty 50 + watchlist · Yahoo (live) · Claude-built + LLM narrator.

### Step 1: Data (`src/fetch_data.py`)
- 🤖 Pulled the live Nifty 50 list from NSE, 4–5 years of statements per firm from Yahoo Finance, and tagged each firm's sector. Four watchlist names (Jaiprakash, Sintex, Future Retail, DHFL) were **delisted → no data**; I dropped them and said so.
- 🧑 In the real project: *always reconcile your companies against a second source*. Done here in Step 3b (Screener.in).

### Step 2: Metrics (`src/forensic_engine.py`), each tied to a session
| Tool | Session | Idea |
|---|---|---|
| Ratios, DuPont | 2–4 | profitability and leverage context |
| Cash conversion (CFO/NI), Sloan accruals | 4–5 | profit without cash is a red flag |
| Beneish M-score | 7–8 | 8 indices: receivables, margins, asset quality, growth, depreciation, SG&A, leverage, accruals |
| Benford's law | 11–12 | leading digits of reported numbers should follow log10(1+1/d) |
| Modified Jones (AEM), Roychowdhury (REM) | AEM / REM sessions | discretionary accruals; abnormal CFO and discretionary spend |
| Altman Z″ | credit | distress raises the incentive to manipulate |

🧑 **Judgement calls I made, and you should challenge:**
1. **Banks/NBFCs/insurers are not scored.** The models assume receivables/COGS. Scoring them gave nonsense (Bajaj Finserv ranked #1!). I caught this in the first run and fixed it.
2. Firms with missing core inputs (Nestlé: no sales line) are labelled "insufficient data", never guessed.
3. Thresholds (−1.78, −2.22; Nigrini bands) come from the literature, not from me.
4. Weights (30/20/15/10/10/15) are my choice. The dashboard lets you change them live.

### Step 3: Validate (don't skip, most students do)
🤖 Back-tested: does the score rank the watchlist above the Nifty 50? **Composite AUC ≈ 0.65** (0.5 = coin flip) on ~10 vs ~37 firms. Modest, small sample, and mostly *distress* rather than *manipulation*. I report this honestly rather than hiding it. 🧑 A faculty member would rather see an honest 0.65 than an unexplained 0.95.

### Step 3b: Reconcile with a second online source (`src/crosscheck_screener.py`)
🤖 Re-fetched every firm from **Screener.in public pages** (polite: one request / 2 s, once; no login, no Excel) and compared with Yahoo:
- **Cash flow and total assets match almost exactly** (97% within 2%, median gap 0%). Net income 70% and sales 63% within 2%.
- **Every sales gap above 10% is explainable:** financial firms (a bank's "revenue" is defined differently) and Infosys (**Yahoo reports it in USD**: a real bug found by this check; ratios unaffected, rupee charts now currency-aware).
- **The ratios the screen uses agree:** sales growth 1.00, accruals/assets 0.99, CFO/NI 0.99, margin 0.98, asset turnover 1.00 (Spearman, 46 non-financial firms, FY2026).
- **Honest limit:** both sites read the same company filings, so this shows the *data transcription* is reliable, not that the filings themselves are truthful.
- Screener also offers **10 years** of history, which can fix the 4-5 year limit later.
🧑 **On the real project:** pick a second source *before* analysis, compare 4-5 line items across all firms, explain every gap above 10%, and write the result in your Data section. Check each site's terms of use before automated access.

### Step 4: Dashboard (`app.py`, Streamlit)
Dropdowns: year, cohort, sector, tier, company, metric, memo type. Sliders: top-N and model weights. Buttons: live refresh, CSV download. Five tabs: Screener · Deep-dive · Peer compare · AI memo · Method & validation.
🧑 **Design test for your own dashboard:** can the stakeholder answer *"who do I look at first, and why?"* in 30 seconds?

### Step 5: AI layer (`src/memo.py`, `data/ai_memos.json`)
Three layers: rule-based text → Claude-drafted memos → live API option. The prompt **forbids any number not in the fact sheet** (anti-hallucination design). 🧑 Always label AI text as AI text and check it against filings.

### Step 6: Report (`WAI_Practice_Report.docx`)

---
## Run it
```bash
cd WAI_Project
.venv/bin/python src/fetch_data.py        # refresh live data (~3 min)
.venv/bin/python src/forensic_engine.py   # recompute scores
.venv/bin/python -m streamlit run app.py  # dashboard on localhost:8501
```

## Known gaps / what to do next (🧑)
1. Add inventory, current assets/liabilities and depreciation detail from filings so Beneish and Altman can be cross-checked too.
2. Use 8–10 years of history so the watchlist is scored *before* its event year (Yahoo gives only 4–5).
3. Estimate Jones/REM **by industry** with a larger universe (Nifty 500) so peers are comparable.
4. Add a Nifty 500 / BSE 500 sample for a proper back-test.
5. Read the audit reports (CARO, KAM) of top-flagged firms: ratios say *where*, documents say *why*.
