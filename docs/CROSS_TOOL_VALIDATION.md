# Cross-tool validation protocol

This repository separates **executed reference results** from **unexecuted replication source**. Python generated the committed analytical outputs. R and SAS were not available in the creation environment. No R/SAS result file or parity certificate is supplied.

## Shared analytical contract

| Item | Contract |
|---|---|
| Input | `data/processed/model_data.csv`, generated from entirely synthetic records |
| Population | One snapshot per unique borrower; no borrower is shared between cohorts |
| Response | Numeric `default_12m`, default = 1, non-default = 0 |
| Cohorts | The supplied `split` column; `embargo` rows are excluded |
| Fit | Unpenalized maximum-likelihood logistic regression with intercept |
| Predictors | `leverage`, `dscr`, `interest_rate_pct`, `gdp_growth_pct`, `past_due_30d` |
| Units | Leverage as a fraction; DSCR as a ratio; interest/GDP as percentage points; past-due flag as 0/1 |
| Missing values | Processed input must be complete; no engine silently drops rows |
| Model changes | No scaling, weighting, selection, balancing, or validation/test refitting |
| Class threshold | F1 maximum on validation over 0.01–0.80 in increments of 0.01; exact ties choose the largest threshold |
| Test scores | Probability of default = 1, joined by `borrower_id`, never by row position |
| Scenarios | Fixed test cohort and exposure, frozen fitted coefficients, three specified feature-shock vectors |
| ECL proxy | `sum(debt_cny_m * PD * 0.45)`; synthetic debt is a fixed exposure proxy |

## How to run and compare

```bash
python -m src.pipeline
Rscript r/credit_risk.R
python r/compare_outputs.py --engine r
# Run sas/credit_risk.sas in SAS after setting its root directory, then:
python r/compare_outputs.py --engine sas
```

The comparison requires exact coefficient-name sets and borrower-ID sets. It rejects duplicate keys. Absolute tolerances are `1e-5` for coefficients and `1e-6` for held-out probabilities, allowing ordinary optimizer and floating-point differences. It exits with an error when any required engine result is absent. A passing comparison proves only coefficient and test-score agreement for those files; it does not validate every diagnostic or the SAS/R runtime as a whole.

After a local run, also inspect optimizer convergence, sample counts, threshold search, confusion matrices, ROC-AUC, Brier score and scenario tables. Save the execution log and software versions. A material difference should be investigated through units, cohort rows, missingness, the modeled outcome, and coefficient precision before relaxing tolerances.

## Inference differences

Python and R use the independent-observation HC1 sandwich covariance:

`V = n/(n-k) * inv(H) * crossprod(X * (y-p)) * inv(H)`

where `H = X' diag(p*(1-p)) X` and `k` includes the intercept. R computes this directly after `glm`. SAS `PROC LOGISTIC` exports its ordinary model-based covariance results. Therefore SAS and Python/R p-values are not promised to agree. HC1 is not a correction for clustered time dependence, and the synthetic associations do not establish causal macroeconomic effects.

## Official implementation references

- [R `glm` documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/glm.html): binomial model specification, model matrix and convergence controls.
- [SAS `PROC LOGISTIC`: scoring data sets](https://support.sas.com/documentation/cdl/en/statug/63962/HTML/default/statug_logistic_sect050.htm): held-out scoring and saved-model rescoring without refitting.
- [SAS `SCORE` statement](https://support.sas.com/documentation/cdl/en/statug/68162/HTML/default/statug_logistic_syntax31.htm): predicted probabilities and output behavior.

These references document the APIs; they are not evidence that the optional scripts executed in this environment.
