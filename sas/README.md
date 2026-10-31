# SAS replication

Open `credit_risk.sas` in SAS Studio or a local SAS session, set `root` to the uploaded/cloned repository path on that SAS host, then run the file. Base SAS and SAS/STAT are required. Run the Python pipeline first so that `data/processed/model_data.csv` exists.

The program validates input completeness and borrower uniqueness, fits `PROC LOGISTIC` on the training cohort, explicitly models `default_12m(event='1')`, saves the fitted model, selects the classification threshold using validation data, and evaluates test discrimination/calibration. It computes training VIF with `PROC REG`. Conditional scenarios use `INMODEL=` to rescore the frozen test cohort without refitting. The Python pipeline supplies the decision-tree benchmark.

`outputs/sas/` receives SAS data sets, an HTML analysis report and CSVs. Download that directory back to the same repository before running:

```bash
python r/compare_outputs.py --engine sas
```

**Execution status:** SAS was not installed in the creation environment. The code was inspected against official SAS documentation, but SAS execution and numerical parity remain unverified. Keep the SAS log and software version with any independently generated outputs.

SAS's `parameter_estimates_model_based_se.csv` contains ordinary maximum-likelihood standard errors; those are not the HC1 standard errors in Python/R. The comparison script checks coefficients and test PDs only. Do not compare the two SE columns as though they estimate the same covariance matrix.
