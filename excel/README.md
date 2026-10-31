# Excel credit review

Open [`../outputs/Credit_Risk_Review.xlsx`](../outputs/Credit_Risk_Review.xlsx). It contains the complete 1,598-borrower held-out cohort and works without Python, R, SAS, macros, or any data connection.

## Explore the workbook

1. Start on **Summary**. The borrower counts, debt-weighted probability of default, loss proxy, risk-band table, sector table, and chart are formula-driven.
2. Change **Assumptions!D4**: `1` = Base, `2` = Adverse, `3` = Severe. The same borrower-level calculation updates for the chosen case.
3. Edit the amber case inputs or LGD. The active driver is selected once for each variable. Source financial data and fitted coefficients remain fixed.
4. Inspect **Scoring** to trace each borrower's adjusted predictors, logit, probability, risk band, and loss proxy. Filter the Excel table to review a sector or high-risk borrowers. Summary formulas represent the full cohort; table filters do not change the Summary totals.
5. Review **Checks** under the original Base assumptions. It compares every workbook probability with the separately calculated Python probability. Adverse and Severe cases show `n.a.` for baseline probability differences because those scenarios deliberately change the input features.

The **Source** table preserves the imported CSV values. Model coefficients are on **Assumptions!H8:I13**. The model was estimated on 2017–2019 observations; the test cohort contains 2023–2024 snapshots. The aggregate debt combines multiple snapshot dates and is not an actual loan-book balance at one date.

## Methods and interpretation

- Probability: `1 / (1 + EXP(-logit))`, where `logit` is the fixed intercept plus the five predictor contributions.
- Loss proxy: borrower debt × estimated PD × editable LGD. Debt is an illustrative exposure proxy; LGD defaults to 45%.
- Risk bands: Low `<5%`, Moderate `5% to <15%`, Elevated `15% to <30%`, High `>=30%`. These are demonstration segments, not a bank rating scale.
- Scenario shocks are conditional sensitivities. They are not causal estimates, regulatory stress scenarios, or forecasts. The past-due indicator remains fixed.
- The benchmark statistics on Summary are the original held-out Python results. They do not change with scenario assumptions; scenario outcomes have no observed labels for re-estimating model performance.
- Blank selected assumptions surface an error. Blank assumptions in unselected cases do not invalidate the active result. Valid zero shocks are retained.

## Optional advanced Office source

[`OFFICE_EXTENSIONS.md`](OFFICE_EXTENSIONS.md) explains the supplied Power Query import, DAX measures, and VBA refresh/PDF export module. These are separate source examples. They are **not embedded** in the `.xlsx` and were not executed in native Excel here.

## Rebuild and validation

`build_workbook.mjs` is the workbook authoring source. It requires the OpenAI artifact-tool authoring runtime; that runtime is **not needed to open or use the delivered workbook**. The Python command in the main repository README regenerates analytical CSVs and charts, but does not rebuild this Office binary.

The builder writes all borrower-level formulas, recalculates them, compares Base probabilities and the loss total against Python outputs, tests an Adverse case plus missing selected and unselected assumptions, restores Base, scans errors, and renders each worksheet before exporting. Native Microsoft Excel/LibreOffice compatibility and the optional M/DAX/VBA integrations were not tested in this environment.

When a changed dataset has a different cohort or row count, rebuild the workbook. Merely refreshing a separately installed Power Query does not resize this delivered model's formula ranges.

This is an independent portfolio demonstration with fully synthetic data. It contains no bank data, bank branding, or representation of an employer's production model.
