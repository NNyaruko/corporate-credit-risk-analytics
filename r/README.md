# R replication

`credit_risk.R` uses base R (`stats` and `utils`, bundled with R). It independently fits the unpenalized binary logistic model to the frozen training split, computes HC1 standard errors and training-only VIF, chooses an F1 threshold on validation, evaluates the untouched test cohort, and rescoring uses the same fitted coefficients for three conditional scenarios.

```bash
# Run the Python pipeline first to materialize the shared input CSV.
Rscript r/credit_risk.R
python r/compare_outputs.py --engine r
```

Alternatively pass the repository directory as the first argument to the R script. Outputs are isolated under `outputs/r/`; the reference results are never overwritten. The Python pipeline provides the decision-tree benchmark. This R script replicates the logistic analysis only.

**Execution status:** R was unavailable in the creation environment. The script was inspected, but neither runtime success nor numerical parity is claimed. `compare_outputs.py` deliberately fails when R output files do not exist. Use it after executing R locally and retain `outputs/r/sessionInfo.txt` with any published parity results.

See [cross-tool validation](../docs/CROSS_TOOL_VALIDATION.md) for model, unit, inference and tolerance details.
