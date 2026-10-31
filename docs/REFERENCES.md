# Implementation references

These are software references for the methods implemented here. No external borrower records, bank models, or empirical research findings were copied into the synthetic dataset.

| Topic | Primary reference | Use in this repository |
|---|---|---|
| Leakage and model evaluation | [scikit-learn: Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) | Keep fitting, validation-based selection and final evaluation separate. |
| Probability calibration | [scikit-learn: Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) | Assess probability quality using calibration curves alongside ranking metrics. |
| Numerical maximum likelihood | [SciPy: minimize](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html) | Minimize the logistic negative log-likelihood with explicit derivatives. |
| R generalized linear models | [R: glm](https://search.r-project.org/R/refmans/stats/html/glm.html) | Independent binomial-logit implementation. |
| R probability predictions | [R: predict.glm](https://search.r-project.org/R/refmans/stats/html/predict.glm.html) | Use response-scale predictions for default probabilities. |
| SAS classification | [SAS: LOGISTIC classification table](https://support.sas.com/documentation/cdl/en/statug/68162/HTML/default/statug_logistic_details26.htm) | Define the event and classify using a specified probability cutoff. |
| CSV imports | [Microsoft: Csv.Document](https://learn.microsoft.com/en-us/powerquery-m/csv-document) | Import UTF-8 CSV with explicit types in Power Query. |

The repository's own source files define the actual defaults, splits, parameter choices and formulas. Documentation availability does not imply that every optional software environment was available for execution; see the execution status in the main README.
