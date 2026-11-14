"""
AI RED-FLAG NARRATOR
Three layers, from safest to most 'creative':
  1. rule_based_memo()  - deterministic text built only from computed numbers (no hallucination possible)
  2. ai_memos.json      - memos drafted by Claude from the SAME fact sheet (pre-generated, human-review label)
  3. live_claude_memo() - optional: calls the Anthropic API if ANTHROPIC_API_KEY is set

All layers receive the same `fact_sheet()`; the prompt forbids using any number that is not in it.
"""
import os, json
import numpy as np, pandas as pd

BENEISH_BAR, BENEISH_WATCH = -1.78, -2.22

PROMPT = """You are a forensic accounting analyst writing a short risk memo for a credit/forensic review committee.
Use ONLY the numbers in the FACT SHEET below. Do not invent figures, events, auditors' remarks or news.
If a metric is missing, say it is unavailable. Treat every flag as a *screening signal*, never as proof of fraud.

Structure (max 220 words):
1. Verdict (one sentence: tier + the 2 strongest signals)
2. Evidence (3 bullets, each citing a metric and its peer/threshold context)
3. Alternative (benign) explanations to check first
4. Next audit steps (3 concrete procedures, e.g. receivables ageing, related-party loans, cash confirmations)

FACT SHEET (JSON):
{facts}
"""


def _f(x, d=2):
    return "n/a" if x is None or pd.isna(x) else f"{x:,.{d}f}"


def fact_sheet(row: pd.Series, peers: pd.DataFrame) -> dict:
    """Numbers + peer context for one company-year. `peers` = same-year non-financial universe."""
    pct = lambda c: None if pd.isna(row.get(c)) else round(float((peers[c] < row[c]).mean() * 100))
    f = {"company": row["name"], "ticker": row["ticker"], "fiscal_year": int(row["fy"]), "sector": row["sector"],
         "cohort": row["cohort"], "financial_sector_not_scored": bool(row["fin"]),
         "risk_score_0_100": None if pd.isna(row.get("score")) else round(float(row["score"]), 1),
         "risk_tier": None if pd.isna(row.get("tier")) else str(row["tier"]),
         "beneish_m": None if pd.isna(row.get("MScore")) else round(float(row["MScore"]), 2),
         "beneish_thresholds": {"likely_manipulator_above": BENEISH_BAR, "watch_above": BENEISH_WATCH},
         "beneish_components": {k: None if pd.isna(row.get(k)) else round(float(row[k]), 2)
                                for k in ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA"]},
         "sloan_accrual_ratio": None if pd.isna(row.get("sloan")) else round(float(row["sloan"]), 3),
         "sloan_peer_percentile": pct("sloan"),
         "jones_discretionary_accruals": None if pd.isna(row.get("DA")) else round(float(row["DA"]), 3),
         "jones_da_peer_percentile": pct("DA"),
         "real_earnings_mgmt_index": None if pd.isna(row.get("REM")) else round(float(row["REM"]), 3),
         "cfo_to_net_income_3yr": None if pd.isna(row.get("cfo_cum_ni")) else round(float(row["cfo_cum_ni"]), 2),
         "dso_days": None if pd.isna(row.get("dso")) else round(float(row["dso"]), 0),
         "altman_z_em": None if pd.isna(row.get("Altman")) else round(float(row["Altman"]), 2),
         "altman_zone": None if pd.isna(row.get("Altman_zone")) else str(row["Altman_zone"]),
         "benford_mad": None if pd.isna(row.get("benford_mad")) else round(float(row["benford_mad"]), 4),
         "benford_verdict": None if pd.isna(row.get("benford_label")) else row["benford_label"],
         "benford_n_numbers": None if pd.isna(row.get("benford_n")) else int(row["benford_n"]),
         "data_coverage_pct_of_model": None if pd.isna(row.get("coverage")) else int(row["coverage"])}
    return f


def rule_based_memo(row: pd.Series, peers: pd.DataFrame) -> str:
    f = fact_sheet(row, peers)
    if f["financial_sector_not_scored"]:
        return (f"**{f['company']}** is a financial-sector entity. Beneish, Jones and Altman assume an operating business "
                "(receivables, inventory, COGS), so the composite score is deliberately **not computed**. "
                f"Only the Benford first-digit test is shown ({f['benford_verdict']}, MAD {_f(f['benford_mad'], 4)}). "
                "Use bank-specific red flags instead: gross/net NPA trend, provisioning coverage, restructured-book share, "
                "loan growth vs deposit growth, and related-party exposure.")
    if f["risk_score_0_100"] is None:
        return (f"**{f['company']}**: insufficient data to score (coverage {f['data_coverage_pct_of_model']}%). "
                "Yahoo Finance lacked required line items; obtain the filing or a second data source before drawing conclusions.")
    sig, ok = [], []
    m = f["beneish_m"]
    if m is not None:
        (sig if m > BENEISH_WATCH else ok).append(
            f"Beneish M-score {_f(m)} is {'above the -1.78 manipulator threshold' if m > BENEISH_BAR else 'in the watch zone (-2.22 to -1.78)' if m > BENEISH_WATCH else 'below the -2.22 watch level'}")
    c = f["beneish_components"]
    for k, lim, txt in [("DSRI", 1.3, "receivables growing faster than sales (DSRI {v})"),
                        ("AQI", 1.3, "rising share of non-current, non-PPE assets (AQI {v}) - possible cost capitalisation"),
                        ("GMI", 1.2, "gross margin deteriorating (GMI {v}) - pressure to manage earnings"),
                        ("SGI", 1.5, "very rapid sales growth (SGI {v}) - growth firms face expectation pressure"),
                        ("TATA", 0.05, "high total accruals to assets (TATA {v})")]:
        if c.get(k) is not None and c[k] > lim:
            sig.append(txt.format(v=_f(c[k])))
    if f["sloan_peer_percentile"] is not None and f["sloan_peer_percentile"] >= 80:
        sig.append(f"accruals in the top {100 - f['sloan_peer_percentile']}% of peers (Sloan ratio {_f(f['sloan_accrual_ratio'], 3)})")
    if f["cfo_to_net_income_3yr"] is not None:
        (sig if f["cfo_to_net_income_3yr"] < 0.8 else ok).append(
            f"3-year cash conversion (CFO/NI) is {_f(f['cfo_to_net_income_3yr'])}" + (" - profits not backed by cash" if f["cfo_to_net_income_3yr"] < 0.8 else " - profits largely cash-backed"))
    if f["benford_verdict"] in ("Marginal", "Non-conformity"):
        sig.append(f"Benford first-digit conformity is '{f['benford_verdict']}' (MAD {_f(f['benford_mad'], 4)}, n={f['benford_n_numbers']})")
    if f["altman_zone"] == "Distress":
        sig.append(f"Altman Z'' of {_f(f['altman_z_em'])} sits in the distress zone - incentive to window-dress")
    lines = [f"**{f['company']} ({f['fiscal_year']}) - {f['risk_tier']} risk, score {_f(f['risk_score_0_100'], 0)}/100.**", ""]
    lines.append("**Signals raised:** " + ("; ".join(sig) + "." if sig else "none of the major screens fired."))
    if ok: lines.append("**Reassuring:** " + "; ".join(ok) + ".")
    lines += ["", "**Check first (benign explanations):** acquisitions/demergers (structural breaks distort year-on-year indices), "
              "change in business mix, new accounting standards (Ind AS), seasonal sales timing, one-off provisions.",
              "**Next steps:** receivables ageing and top-10 debtor confirmations; reconcile CFO to profit; review related-party "
              "notes and auditor's CARO/KAM remarks; check capitalised expenses and capital WIP ageing.",
              "", "_Screening output only - a flag is a reason to investigate, never evidence of fraud._"]
    return "\n".join(lines)


def live_claude_memo(row: pd.Series, peers: pd.DataFrame, model="claude-sonnet-5-5") -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic
    msg = anthropic.Anthropic(api_key=key).messages.create(
        model=model, max_tokens=700,
        messages=[{"role": "user", "content": PROMPT.format(facts=json.dumps(fact_sheet(row, peers), indent=1))}])
    return msg.content[0].text
