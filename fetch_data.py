"""
STEP 1 - DATA COLLECTION (live, free sources)

Sources
  * NSE India archive  -> current Nifty 50 constituents (official CSV, no login)
  * Yahoo Finance      -> annual income statement / balance sheet / cash flow
                          (via the open-source `yfinance` library) + sector tag
  * A hand-picked "watchlist" of Indian listed firms with publicly reported
    governance / distress episodes (incl. cases from the FSAFA course).
    This list is a *validation cohort*, NOT an accusation of fraud.

Output  data/raw_long.csv   (ticker, statement, item, fy, value)
        data/universe.csv   (ticker, name, sector, industry, cohort)
Re-run any time to refresh ("live" = refresh on demand).
"""
import io, sys, time, datetime as dt
from pathlib import Path
import pandas as pd, requests, yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)

NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
HDR = {"User-Agent": "Mozilla/5.0 (academic practice project)"}

# Watchlist: (Yahoo ticker, why it is on the list)
WATCHLIST = {
    "ZEEL.NS":       "Zee Entertainment - course case (Zee)",
    "COFFEEDAY.NS":  "Coffee Day Enterprises - course case (CCD)",
    "RELINFRA.NS":   "Reliance Infrastructure - course case (Reliance Group red flags)",
    "YESBANK.NS":    "Yes Bank - 2020 reconstruction",
    "IDEA.NS":       "Vodafone Idea - severe leverage / distress",
    "RPOWER.NS":     "Reliance Power - group distress",
    "RCOM.NS":       "Reliance Communications - insolvency",
    "SUZLON.NS":     "Suzlon Energy - debt restructuring history",
    "GTLINFRA.NS":   "GTL Infrastructure - high leverage",
    "JPASSOCIAT.NS": "Jaiprakash Associates - insolvency proceedings",
    "PCJEWELLER.NS": "PC Jeweller - governance / lender issues",
    "SINTEX.NS":     "Sintex Industries - insolvency",
    "FRETAIL.NS":    "Future Retail - insolvency",
    "UNITECH.NS":    "Unitech - governance / insolvency",
    "ERISMEDIA.NS":  "placeholder",   # dropped automatically if no data
    "DHFL.NS":       "Dewan Housing Finance - fraud proceedings",
    "RHFL.NS":       "Reliance Home Finance - distress",
    "ADANIENT.NS":   "(already Nifty50) governance allegations 2023 - tagged below",
}
WATCHLIST.pop("ERISMEDIA.NS")


def nifty50():
    r = requests.get(NSE_URL, headers=HDR, timeout=20); r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    return {f"{s}.NS": n for s, n in zip(df["Symbol"], df["Company Name"])}


def pull(ticker, retries=3):
    for i in range(retries):
        try:
            k = yf.Ticker(ticker)
            frames = []
            for stmt, attr in [("IS", "income_stmt"), ("BS", "balance_sheet"), ("CF", "cashflow")]:
                d = getattr(k, attr)
                if d is None or d.empty:
                    continue
                d = d.copy(); d.columns = [c.year if c.month <= 3 else c.year + 1 for c in d.columns]  # FY end-year (Mar-31 -> that year)
                long = d.reset_index().melt(id_vars="index", var_name="fy", value_name="value")
                long.columns = ["item", "fy", "value"]; long["statement"] = stmt; long["ticker"] = ticker
                frames.append(long)
            info = {}
            try: info = k.info or {}
            except Exception: pass
            if frames:
                return pd.concat(frames), info
        except Exception as e:
            print(f"  retry {ticker}: {e}", file=sys.stderr)
        time.sleep(2 * (i + 1))
    return None, {}


def main():
    n50 = nifty50()
    uni = {t: (name, "Nifty 50") for t, name in n50.items()}
    for t, why in WATCHLIST.items():
        uni[t] = (why, "Nifty 50" if t in n50 else "Watchlist")
    if "ADANIENT.NS" in n50:
        uni["ADANIENT.NS"] = (n50["ADANIENT.NS"], "Nifty 50")  # keep in main cohort; flagged in report text only

    rows, longs = [], []
    for i, (t, (name, cohort)) in enumerate(uni.items(), 1):
        df, info = pull(t)
        ok = df is not None
        print(f"[{i}/{len(uni)}] {t:15s} {'OK ' if ok else 'NO DATA'} {cohort}")
        if not ok:
            continue
        longs.append(df)
        rows.append(dict(ticker=t, name=info.get("longName") or name, sector=info.get("sector", "Unknown"),
                         industry=info.get("industry", "Unknown"), currency=info.get("financialCurrency", "INR"), cohort=cohort, note=name if cohort == "Watchlist" else ""))
        time.sleep(0.4)
    pd.concat(longs).to_csv(DATA / "raw_long.csv", index=False)
    pd.DataFrame(rows).to_csv(DATA / "universe.csv", index=False)
    (DATA / "last_refresh.txt").write_text(dt.datetime.now().isoformat(timespec="seconds"))
    print("saved", len(rows), "companies")


if __name__ == "__main__":
    main()
