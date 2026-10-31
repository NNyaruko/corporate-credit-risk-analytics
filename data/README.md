# Data dictionary and lineage

All records are synthetic and use invented borrower IDs. No customer records,
bank identifiers, account numbers or real macroeconomic observations are included.
Monetary amounts are CNY million; no FX conversion is involved.

## Raw sources

| File | Grain | Key | Purpose |
|---|---|---|---|
| `raw/financials.csv` | Borrower snapshot | borrower_id + snapshot_date | Financial balances and snapshot interest rate; contains one exact duplicate and two intentionally missing cells |
| `raw/repayments.csv` | Borrower snapshot | borrower_id + snapshot_date | Historical arrears flag, subsequent default outcome and maturity date |
| `raw/macro.csv` | Quarter | snapshot_date | Invented GDP-growth series shared by borrowers in that quarter |

The combined modeling file is `processed/model_data.csv`. Financials and
repayments use a validated one-to-one join. Macro uses a validated many-to-one
join. A nonidentical duplicate key or unmatched key raises an error.

## Processed fields

| Field | Type / units | Meaning / source |
|---|---|---|
| borrower_id | text | Synthetic unique identifier; one observation per borrower |
| snapshot_date | ISO date | Quarter-end feature observation date, 2017–2024 |
| sector | categorical | Synthetic sector; reporting dimension, not a predictor |
| revenue_cny_m | CNY million | Historical annual revenue at the snapshot |
| debt_cny_m | CNY million | Outstanding borrower debt; used as illustrative EAD proxy |
| total_assets_cny_m | CNY million | Snapshot total assets |
| ebitda_cny_m | CNY million | Historical annual EBITDA |
| debt_service_cny_m | CNY million | Historical annual interest and principal service |
| leverage | decimal ratio | debt_cny_m / total_assets_cny_m; 0.50 means 50% |
| dscr | multiple | ebitda_cny_m / debt_service_cny_m; 1.50 means 1.5x |
| interest_rate_pct | percentage points | Borrower's snapshot annual borrowing rate; 5.0 means 5% |
| gdp_growth_pct | percentage points | Fabricated quarterly GDP-growth covariate; 5.0 means 5% |
| past_due_30d | integer 0/1 | Snapshot flag for at least 30 days past due in historical repayment records; not the future outcome |
| default_12m | integer 0/1 | Simulated default event during the twelve months after the snapshot |
| split | categorical | train, validation, test or embargo; fixed before modeling |

`outcome_window_end` exists only in repayments and equals the snapshot plus one
year. It is not a model predictor. `source` in macro records the synthetic origin.
The data do not simulate an operational delinquency event history or a particular
bank's formal default policy.

## Processed cohort

6,401 financial rows reconcile to 6,400 unique borrower/date keys after removing
one identical copy of `SYN-000101`. Incomplete records `SYN-006399` and
`SYN-006400` are excluded, leaving 6,398 model rows. Complete-case exclusions
are specified without considering target labels. There is no imputation.

| split | Dates | Count |
|---|---|---:|
| train | 2017–2019 | 2,400 |
| embargo | 2020 and 2022 | 1,600 |
| validation | 2021 | 800 |
| test | 2023–2024 | 1,598 |

Embargo rows are kept for auditability but never used to fit, tune or evaluate.
See [chronology and methods](../docs/METHODOLOGY.md) for outcome-availability dates.

## Main output lineage

| Output | Derivation |
|---|---|
| `outputs/data_quality_audit.csv` | Step counts from deterministic preparation |
| `outputs/data_quality_exceptions.csv` | Removed duplicate and missing-value borrower IDs |
| `outputs/reconciliation.json` | Unique-source debt = retained model debt + excluded debt |
| `outputs/coefficients.csv` | Training-only logistic MLE; HC1 standard errors and Wald intervals |
| `outputs/model_parameters.json` | Exact coefficients, input order, thresholds, scenario definitions |
| `outputs/test_predictions.csv` | All 1,598 test rows plus logistic/tree probabilities, display band and loss proxy |
| `outputs/validation_predictions.csv` | Validation rows and frozen logistic probabilities for replication |
| `outputs/model_metrics.csv` | Training, validation and held-out test metrics by model |
| `outputs/scenario_predictions.csv` | Borrower/scenario probabilities and constant-EAD loss proxy |
| `outputs/scenario_summary.csv` | Aggregate scenario probabilities, exposure-weighted PD and loss proxy |
| `outputs/scenario_support.csv` | Scenario feature values outside training min/max |
| `outputs/sector_summary.csv` | Test cohort sector counts, observed rates, predicted rates and loss proxy |
| `outputs/workbook_data.json` | Machine-readable inputs for the Excel/report builders |

Prediction columns are `pd_logistic` and `pd_tree` (probabilities in [0,1]).
`risk_band` is a descriptive probability bin. `ecl_proxy_cny_m` is
`pd_logistic * debt_cny_m * 0.45`, a simplified twelve-month loss proxy.
Every rerun deterministically recreates the raw sources and outputs; edit the
generation script to create a different demonstration rather than overwriting a
committed source file and expecting it to survive a pipeline rerun.
