"""
DECISION LAYER for the forensic analyst
  action_for()  : Forensic Priority Index bands -> Investigate / Review / Monitor / Routine  (+ why, + first checks)
  build_alerts(): year-on-year triggers (score jumps, threshold crossings, new distress, anomalies)
"""
import numpy as np, pandas as pd

LEVELS = ["Routine", "Monitor", "Review", "Investigate"]
ICON = {"Investigate": "🔴", "Review": "🟠", "Monitor": "🟡", "Routine": "🟢", "Not scored": "⚪", "Insufficient data": "⚪"}
BASE = {"Low": 0, "Moderate": 1, "Elevated": 2, "High": 3}
MEANING = {"Investigate": "Open a forensic review now.", "Review": "Analyst desk review this quarter.", "Monitor": "Watch next filing; check the cause of mild signals.", "Routine": "No action beyond routine monitoring.",
           "Not scored": "Use bank / insurer specific checks.", "Insufficient data": "Obtain the filing before judging."}
CHECKS = {"Beneish": "Age receivables and confirm top debtors; read revenue-recognition notes",
          "Accruals": "Reconcile profit to operating cash flow; test provisions and accruals",
          "Cash divergence": "Bridge profit to cash: working-capital build, capitalised costs",
          "REM": "Look for discretionary-spend cuts, channel discounts, overproduction",
          "Benford": "Test source ledgers for duplicates and round numbers (weak signal)",
          "Distress": "Read going-concern, covenant and refinancing notes; related-party loans"}


BANDS = [(65, "Investigate"), (50, "Review"), (35, "Monitor"), (0, "Routine")]


def action_for(row):
    """Action from the Forensic Priority Index bands: 65+ Investigate, 50-65 Review, 35-50 Monitor, below 35 Routine.
    Returns (level, reason, first_checks). `row` needs fin, fpi_w, score_w, tier_w, red_n, red_of, anomaly_pct and s_* block scores."""
    if bool(row.get("fin")): return "Not scored", "Bank / NBFC / insurer: the tests assume an operating business.", "NPA trend, provisioning cover, restructured loans, related-party exposure"
    if pd.isna(row.get("score_w")) or pd.isna(row.get("fpi_w")): return "Insufficient data", "Core inputs missing from the data source.", "Obtain the annual report"
    f = float(row["fpi_w"]); lvl = next(n for lo, n in BANDS if f >= lo)
    why = f"priority index {f:.0f}: risk score {row['score_w']:.0f} ({row['tier_w']}), {int(row['red_n'])} of {int(row['red_of'])} tests in the red zone"
    if pd.notna(row.get("anomaly_pct")): why += f", AI outlier {row['anomaly_pct']:.0f}th percentile"
    blocks = sorted([(k, row.get("s_" + k)) for k in CHECKS if pd.notna(row.get("s_" + k))], key=lambda x: (x[0] == "Benford", -x[1]))   # weakest evidence (Benford) always last
    first = "; ".join(CHECKS[k] for k, v in blocks[:3] if v >= 50) or "Confirm the cause of the mild signals in the notes"
    return lvl, why, first


def build_alerts(mall, fy):
    """Year-on-year triggers for every scored firm. Uses columns score_w, MScore, Altman_zone, cfo_cum_ni, anomaly_pct, benford_label."""
    cur = mall[mall.fy == fy].set_index("ticker"); prv = mall[mall.fy == fy - 1].set_index("ticker")
    rows = []
    for t, r in cur.iterrows():
        if bool(r.get("fin")) or pd.isna(r.get("score_w")): continue
        p = prv.loc[t] if t in prv.index else None
        def add(sev, text, act): rows.append(dict(ticker=t, name=r["name"], severity=sev, alert=text, action=act))
        if p is not None and pd.notna(p.get("score_w")) and r.score_w - p.score_w >= 10:
            big = r.score_w - p.score_w >= 30
            add("High", f"Risk score jumped {r.score_w - p.score_w:+.0f} points ({p.score_w:.0f} to {r.score_w:.0f})" + (" (very large: check for a merger, demerger or restatement)" if big else ""),
                "Check for restructuring first, then find which test moved" if big else "Find which test moved; read the notes behind it")
        if p is not None and pd.notna(p.get("MScore")) and pd.notna(r.get("MScore")) and p.MScore <= -1.78 < r.MScore:
            add("High", f"Beneish M crossed the manipulator threshold ({p.MScore:.2f} to {r.MScore:.2f})", "Age receivables; test revenue recognition")
        if p is not None and str(r.get("Altman_zone")) == "Distress" and str(p.get("Altman_zone")) != "Distress" and pd.notna(r.get("Altman")):
            z = r.get("Altman"); bord = pd.notna(z) and abs(z - 4.15) < 0.5
            add("Medium" if bord else "High", f"Moved into the Altman distress zone (Z″ {z:.2f} vs 4.15 cut-off" + (", borderline)" if bord else ")"),
                "Read covenant and refinancing disclosures" + ("; Altman often understates capital-intensive utilities and infrastructure" if bord else ""))
        if pd.notna(r.get("cfo_cum_ni")) and r.cfo_cum_ni < 0.6 and not (p is not None and pd.notna(p.get("cfo_cum_ni")) and p.cfo_cum_ni < 0.6):
            add("Medium", f"3-year cash conversion fell to {r.cfo_cum_ni:.2f} (profit not turning into cash)", "Bridge profit to operating cash flow")
        if pd.notna(r.get("anomaly_pct")) and r.anomaly_pct >= 90:
            add("Medium", f"Statistical outlier vs peers: {r.get('anomaly_drivers') or 'unusual combination of signals'}", "Compare with closest peers; check for restructuring")
        if str(r.get("benford_label")) == "Non-conformity" and not any(x["ticker"] == t for x in rows):
            add("Low", f"Benford digit pattern non-conforming (MAD {r.benford_mad:.4f})", "Weak signal; test source ledgers")
    out = pd.DataFrame(rows)
    if out.empty: return out
    out["_o"] = out.severity.map({"High": 0, "Medium": 1, "Low": 2})
    return out.sort_values(["_o", "name"]).drop(columns="_o").reset_index(drop=True)
