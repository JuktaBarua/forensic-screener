# Data & calculation dictionary

This pack lets a reviewer verify where every number comes from and how every score is calculated.

## Files
| File | Content | Source |
|---|---|---|
| `universe.csv` | Companies: ticker, name, sector, industry, reporting currency, cohort (Nifty 50 / Watchlist) | NSE India constituent list; Yahoo Finance profile |
| `raw_long.csv` | Annual statements, one row per (ticker, statement, line item, fiscal year). IS = income statement, BS = balance sheet, CF = cash flow. Values in reporting currency units | Yahoo Finance (yfinance) |
| `metrics_year.csv` | One row per company-year: standardised inputs, ratios, every test, block scores, composite score, anomaly and priority fields | Calculated by `src/forensic_engine.py` |
| `scores.csv` | Latest year per company from `metrics_year.csv` | Calculated |
| `benford_digits.csv` | Observed vs expected first-digit shares per company | Calculated from `raw_long.csv` |
| `screener_long.csv` | 10+ years of Sales, Net profit, Depreciation, Interest, Total assets, Borrowings, Operating cash flow (Rs crore) | Screener.in public pages |
| `xcheck_*.csv` | Yahoo vs Screener.in agreement tests | Calculated by `src/crosscheck_screener.py` |
| `validation.csv` | Back-test AUCs of each test vs watchlist | Calculated |
| `ai_memos.json` | Claude-drafted memos with model name and date | Claude, from the fact sheet |

Fiscal year = year ending 31 March (FY2026 = April 2025 to March 2026).

## Standardised inputs (columns in `metrics_year.csv`)
`sales` Total revenue · `cogs` Cost of revenue · `sga` Selling, general and administration · `dep` Depreciation and amortisation · `ni` Net income · `ebit` EBIT · `recv` Accounts receivable · `inv` Inventory · `ta` Total assets · `ppe` Net PPE · `ca` Current assets · `cl` Current liabilities · `tl` Total liabilities · `ltd` Long-term debt · `debt` Total debt · `re` Retained earnings · `equity` Stockholders' equity · `cfo` Operating cash flow · `capex` Capital expenditure.

## Formulas
**Beneish M-score (8 variables)**
- DSRI = (Receivables/Sales)t ÷ (Receivables/Sales)t-1
- GMI = [(Sales−COGS)/Sales]t-1 ÷ [(Sales−COGS)/Sales]t
- AQI = [1 − (CurrentAssets+PPE)/TotalAssets]t ÷ same t-1
- SGI = Salest ÷ Salest-1
- DEPI = [Dep/(Dep+PPE)]t-1 ÷ [Dep/(Dep+PPE)]t
- SGAI = (SGA/Sales)t ÷ (SGA/Sales)t-1
- LVGI = [(CurrentLiabilities+LongTermDebt)/TotalAssets]t ÷ same t-1
- TATA = (NetIncome − OperatingCashFlow) ÷ TotalAssetst
- **M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI**
- Indices winsorised to [0.2, 5], TATA to [−0.5, 0.5]; a missing index is set to neutral (1, or 0 for TATA); M requires at least 6 of 8 indices. Flag: M > −1.78 likely manipulator; −2.22 to −1.78 watch.

**Accruals**: Sloan ratio = (NetIncome − CFO) ÷ average total assets. Modified Jones discretionary accruals (DA): residual of TA/At-1 = a1(1/At-1) + a2((ΔSales−ΔReceivables)/At-1) + a3(PPE/At-1), estimated cross-sectionally each year on non-financial firms.

**Real earnings management (REM)**: Roychowdhury abnormal CFO (CFO/At-1 on 1/At-1, S/At-1, ΔS/At-1) and abnormal discretionary expense (SG&A/At-1 on 1/At-1, St-1/At-1); REM = −abnormal CFO − abnormal discretionary expense.

**Cash conversion** = 3-year cumulative CFO ÷ 3-year cumulative net income (undefined if cumulative profit ≤ 0).

**Altman Z″ (emerging markets)** = 3.25 + 6.56·(CA−CL)/TA + 3.26·RE/TA + 6.72·EBIT/TA + 1.05·Equity/TL. Distress < 4.15; grey 4.15 to 5.85; safe > 5.85.

**Benford** = mean absolute deviation (MAD) between observed first-digit shares and log10(1+1/d) over all statement line items and years (duplicate values removed). Nigrini bands: ≤0.006 close, ≤0.012 acceptable, ≤0.015 marginal, above non-conformity.

## Scores
**Block scores (0 to 100, higher = worse)**: Beneish = scale(M, −3 to −1); Accruals = mean percentile of Sloan and DA; Cash divergence = inverse percentile of cash conversion; REM = percentile of REM; Benford = scale(MAD, 0.006 to 0.015); Distress = scale(−Altman, −7 to −3).

**Risk score** = weighted average of available block scores (default weights Beneish 30, Accruals 20, Cash divergence 15, REM 10, Benford 10, Distress 15), requiring at least 60% of weight and core earnings-quality inputs. Tiers: Low < 35 ≤ Moderate < 50 ≤ Elevated < 65 ≤ High. Banks, NBFCs and insurers are not scored.

**Corroboration** = number of block scores ≥ 60 ("red zone") out of blocks available (`red_n`, `red_of`).

**AI anomaly percentile** (`anomaly_pct`): Isolation Forest (400 trees, seed 7) on 14 robust-standardised features (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA, Sloan, DA, REM, debt/assets, ROA, cash conversion) for all scored company-years; percentile within fiscal year. `anomaly_drivers` lists the two features with the largest robust z-scores (|z| ≥ 1.5).

**Forensic Priority Index (FPI)** = 0.50 × Risk score + 25 × (red_n ÷ red_of) + 0.25 × anomaly percentile. Range 0 to 100.

**Recommended action**: bands on the Forensic Priority Index: 65 or more = Investigate, 50 to 65 = Review, 35 to 50 = Monitor, below 35 = Routine. Banks, NBFCs and insurers = Not scored.
