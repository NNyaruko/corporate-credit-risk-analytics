# Methodology and interpretation

This independent work sample uses entirely synthetic borrowers, financial statements,
repayment indicators and macroeconomic observations. It is not employer work product,
a reconstruction of a bank portfolio, or evidence of any institution's performance.
The default rates are chosen for a useful classification exercise and are not
representative of a real commercial bank.

## Cohort and source reconciliation

`src/pipeline.py` generates 200 independent borrower observations for each quarter
from 2017 through 2024 using NumPy seed 2026. There is one snapshot per borrower,
so this is a pooled cross-sectional model with quarterly covariates, not a panel
fixed-effects model. Source controls are:

| Reconciliation step | Records |
|---|---:|
| Raw financial rows | 6,401 |
| Exact duplicate removed | 1 |
| Unique borrower/date keys | 6,400 |
| Incomplete financial records excluded | 2 |
| Complete model records | 6,398 |

Financial and repayment tables join one-to-one on borrower/date. Macro observations
join many-to-one on snapshot date. Conflicting duplicates or missing joins stop the
pipeline. One identical financial row is deliberately duplicated. The final two
borrowers have a missing EBITDA or debt-service value and are excluded using a
complete-case rule. These exceptions are recorded with their borrower IDs.
Debt exposure reconciles before and after exclusion in `outputs/reconciliation.json`.
No learned imputation, winsorization or scaling is used.

## Outcome maturity and chronology

The binary target is a simulated default event during the twelve months following
the snapshot. All outcomes are available as of December 31, 2025. To avoid learning
from default outcomes that would not yet exist at a decision date, the workflow
uses two full calendar-year gaps:

| Role | Snapshot dates | Records | When outcomes are fully available | Use |
|---|---|---:|---|---|
| Training | 2017–2019 | 2,400 | End of 2020 | Estimate logistic coefficients and fit all candidate trees |
| Embargo | 2020 | 800 | End of 2021 | Retained for lineage; never used for fitting, selection or performance metrics |
| Validation | 2021 | 800 | End of 2022 | Select tree complexity and classification thresholds |
| Embargo | 2022 | 800 | End of 2023 | Retained for lineage; never used for fitting, selection or performance metrics |
| Test | 2023–2024 | 1,598 | End of 2025 | Final frozen evaluation and conditional scenarios |

Training fits can be available January 1, 2021. All selection is frozen January 1,
2023, before the first test snapshot. Coefficients and trees are not refitted after
validation. Borrowers do not overlap across partitions. The `split` field is the
authoritative partition, including `embargo` rows in the processed data.

## Synthetic data-generating process

Assets follow a lognormal distribution. Leverage follows a beta distribution with
a small sector adjustment. Revenue is a multiple of assets, EBITDA is a proportion
of revenue, and debt service is calculated from a simulated coverage ratio.
Borrower interest rates combine a simulated quarterly base rate, leverage,
past-due status and independent noise. GDP growth follows a fabricated cyclical
series; it is not retrieved historical data.

The event generator uses a Bernoulli draw with log odds:

```text
-2.4 + 3.4*leverage - 0.65*dscr + 0.22*interest_rate_pct
     - 0.12*gdp_growth_pct + 1.2*past_due_30d
```

The true generating probabilities are not present in the modeling data. Simulation
is intentionally compatible with a logistic specification, so a favorable logistic
result does not establish superiority for real credit portfolios. Displayed model
results are estimates, not the generating coefficients.

## Logistic specification and inference

Five snapshot-time predictors are used, with an intercept:

```text
PD_i = 1 / (1 + exp(-x_i' beta))
x_i = [1, leverage, dscr, interest_rate_pct, gdp_growth_pct, past_due_30d]
```

Interest rate and GDP growth are in percentage points (5.0 means 5%), while
leverage is a decimal ratio and DSCR is a multiple. Sector is retained for reporting
but is not a model predictor. Outcome, split, borrower ID and snapshot date are
not predictors.

The Python reference estimates unpenalized maximum likelihood using SciPy
`minimize(method="trust-exact")`, with analytic gradient and Hessian. Stable
`logaddexp` evaluates the likelihood. The optimizer uses a gradient tolerance of
1e-6. The run additionally checks a maximum absolute score below 1e-5, finite
coefficients, and a positive-definite Hessian. Tests compare coefficients and
held-out probabilities with scikit-learn's independent Newton-Cholesky solver.

Let `H = X' W X`, `W_ii = p_i(1-p_i)` and `s_i = x_i(y_i-p_i)`. Reported covariance is:

```text
V_HC1 = n/(n-k) * inverse(H) * sum(s_i s_i') * inverse(H)
```

Here `k=6` includes the intercept. Standard errors, two-sided normal Wald p-values
and 95% coefficient intervals follow from this covariance. Odds ratios are
`exp(beta)` per one unit of each input. For a ten-percentage-point leverage change,
the odds ratio is `exp(0.10*beta_leverage)`, not `exp(beta_leverage)`.

HC1 covers independent-observation score variation. It does not correct for
unmodeled within-quarter dependence, establish causality, or validate the model
for a real lending population. There are only twelve distinct macro observations
in training. The estimated interest-rate coefficient has p=0.058 and GDP-growth
coefficient p=0.174, so neither meets a 5% significance threshold in this sample.
VIF is calculated using training predictors only; the largest VIF is about 1.42.
Low VIF does not eliminate omitted-variable or specification risk.

## Decision-tree benchmark and thresholds

Candidate trees use maximum depths 2, 3, 4 and 5, crossed with minimum leaf sizes
40, 80 and 120. All twelve candidates fit training data only. Highest validation
ROC-AUC determines the chosen tree; ties favor the shallower tree, then the larger
leaf. This run selects depth 5 and minimum leaf size 80.

For each model, a fixed probability grid from 0.01 through 0.80 in steps of 0.01
is scored on validation F1. Exact ties choose the highest threshold. The selected
thresholds are 0.25 for logistic regression and 0.21 for the tree. A predicted
default is `PD >= threshold`. F1 is an illustrative selection objective; it does
not represent actual underwriting costs, policy, or capital requirements.

Final reports include test ROC-AUC, average precision, Brier score, log loss,
precision, recall, F1, confusion counts and quantile-binned calibration. Model
selection and threshold selection never use test outcomes. A single validation
cohort and a single test window leave sampling uncertainty and sensitivity to
time periods unresolved.

## Risk bands and conditional scenarios

Display bands use `Low: PD < 5%`, `Moderate: 5% <= PD < 15%`,
`Elevated: 15% <= PD < 30%`, `High: PD >= 30%`. They are illustrative labels,
distinct from the 25% logistic classification threshold, and not bank ratings.

| Input change | Base | Adverse | Severe |
|---|---:|---:|---:|
| Leverage additive change | 0.00 | +0.05 | +0.10 |
| DSCR multiplier | 1.00 | 0.85 | 0.70 |
| Interest-rate addition, percentage points | 0 | +1 | +2 |
| GDP-growth addition, percentage points | 0 | -2 | -4 |

Leverage is clipped to [0,1]. The past-due indicator stays fixed. Scenario
probabilities reuse the frozen logistic coefficients and the identical test
borrowers. These are conditional feature shocks, not a causal macroeconomic
forecast, a dynamically linked balance-sheet model, or a regulatory stress test.
The stressed leverage ratio is a model input; source debt and assets are not
reconstructed from that ratio.

Borrower debt is an illustrative EAD proxy held constant in every scenario.
LGD is an assumed 45%. The twelve-month loss proxy is `sum(PD * debt * 0.45)`
in CNY million. It excludes discounting, collateral recovery models, commitments,
staging and lifetime loss, so it is not an IFRS 9 or regulatory capital calculation.
`scenario_support.csv` reports feature values outside training ranges. Particularly
severe shocks can involve extrapolation and should be interpreted accordingly.

## Reference sources and execution

The following primary documentation informed the implementation. All project data
are generated locally and do not come from these sources.

- [SciPy minimize](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html)
- [scikit-learn threshold tuning](https://scikit-learn.org/1.8/modules/classification_threshold.html)
- [scikit-learn precision–recall](https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html)
- [sandwich HC covariance documentation](https://sandwich.r-forge.r-project.org/reference/vcovHC.html)

The Python reference was executed with Python 3.12.14 and the versions in
`requirements.txt`; exact runtime metadata are in `outputs/run_environment.json`.
The ten tests in `tests/test_pipeline.py` cover maturity gaps, duplicate failure,
reconciliation, independent MLE comparison, covariance, feature leakage,
validation thresholds, rank-formula AUC, confusion totals and scenario calculations.
R/SAS execution and native Office feature status are documented separately; their
presence in this repository does not imply they were executed in this environment.
