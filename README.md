# Forensic Earnings-Quality Screener

Streamlit dashboard for forensic / fraud analysts (IIM Ranchi, FSAFA - WAI practice project).
Screens the Nifty 50 plus a watchlist of Indian listed firms using Beneish M-score, accruals (Sloan / modified Jones),
real earnings management, Benford's law and Altman Z''. Data: Yahoo Finance + NSE, cross-checked against Screener.in.

Screening signals only - a flag is a reason to investigate, never evidence of fraud.

Run locally: `pip install -r requirements.txt` then `streamlit run app.py`.
Full method, results and caveats: see `PROJECT_GUIDE.md` and `WAI_Practice_Report.docx`.
