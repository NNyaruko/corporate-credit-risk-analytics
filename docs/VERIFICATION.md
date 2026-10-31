# Execution and verification record

Prepared on October 31, 2026. This record separates executed checks from optional source that still requires its native environment.

## Executed reference analysis

The Python pipeline completed using Python 3.12.14 and the exact versions in `requirements.txt`. The environment is recorded in `outputs/run_environment.json`. The logistic optimizer reports success, with maximum absolute score below 1e-6 and a positive-definite observed information matrix.

Ten automated checks passed using `python -m unittest discover -s tests -v`:

1. Borrower separation and 12-month outcome-maturity gaps.
2. Duplicate/exclusion reconciliation and source debt totals.
3. Logistic coefficient and probability agreement with an independent scikit-learn solver.
4. MLE first-order conditions and an independently recomputed HC1 covariance.
5. Predictors excluding outcomes, split labels and snapshot dates.
6. Validation-only threshold selection and deterministic tie handling.
7. Rank-based AUC, Brier calculations and confusion-matrix totals.
8. Scenario transformations preserving cohort, exposure and prior delinquency.
9. Exact risk-band boundaries.
10. Conflicting duplicate keys failing instead of being silently discarded.

The notebook generator executed its six standard-Python calculation cells sequentially and saved their output. The notebook does not claim a separate native Jupyter-kernel execution. No R or SAS output was fabricated or substituted for engine execution.

## Excel

The authoring engine recalculated all five worksheets. Base-case scores for all 1,598 test borrowers agree with the Python probabilities to a maximum absolute difference of approximately 1.7e-16. The active Adverse case produced mean PD 0.3197254818; Base was restored before delivery.

Selected and unselected blank assumptions were tested. Formula error scans and the exported XML contained no cached error cells. Each worksheet was rendered and visually reviewed. Exported native tables and the source-linked chart were checked structurally.

Native Microsoft Excel recalculation was not tested. Power Query M, Power Pivot/DAX and VBA are optional source examples, not embedded or executed features of the delivered `.xlsx`. Refreshing an optional query does not rebuild the workbook's fixed formula ranges.

## Word and PowerPoint

The Word memorandum contains three pages. The PowerPoint deck contains five slides. Both use the committed analytical results. All pages/slides were rendered and visually reviewed; PDF copies are provided. PowerPoint tables and charts are native editable objects with embedded chart data.

Native desktop Microsoft Word and PowerPoint rendering was not tested. Office sources requiring the artifact-tool authoring runtime are supplied for transparency; that runtime is not needed to open the deliverables.

## Optional replication

R and SAS source was inspected but not executed because the runtimes were unavailable. Cross-tool coefficient and probability parity remains **unverified**. `r/compare_outputs.py` intentionally fails if the chosen engine's files are missing, duplicated, nonfinite or outside the stated tolerances.

## Scope of the evidence

These checks establish the internal consistency of this synthetic work sample. They do not establish performance on real bank data. The generator favors a logistic specification, macro effects are predictive rather than causal, several scenarios extrapolate beyond training support, and the loss proxy omits the components of a full accounting or regulatory credit-risk model.
