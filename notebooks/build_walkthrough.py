"""Build a portable notebook from executed, standard-Python calculation cells.

No notebook tooling is required to regenerate the committed walkthrough:
    python notebooks/build_walkthrough.py
Run the pipeline first. Existing analytic files are read, never overwritten here.
"""
from pathlib import Path
import base64
import contextlib
import io
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
cells = []
namespace = {}
execution_count = 0


def markdown(source):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)})


def code(source):
    global execution_count
    execution_count += 1
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(source, f"walkthrough_cell_{execution_count}", "exec"), namespace)
    outputs = []
    if output.getvalue():
        outputs.append({"output_type": "stream", "name": "stdout", "text": output.getvalue().splitlines(True)})
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": execution_count,
                  "source": source.splitlines(True), "outputs": outputs})


markdown("""# Corporate credit risk: a reproducible walkthrough

**Independent work sample; all borrower and macroeconomic data are synthetic.**
This notebook follows the committed data from source reconciliation to logistic estimation,
out-of-time validation and conditional scenario scoring. The Python pipeline is the executed
reference. Separate R and SAS implementations have not been run in their native environments.

Run `python -m src.pipeline` from the repository root to recreate the inputs and reference outputs.
Cells below can then be rerun in Jupyter. This notebook is built by executing the calculation
cells in sequence; figures are embedded from the pipeline's saved charts.
""")
code("""from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss

ROOT = Path.cwd() if (Path.cwd() / "src").exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from src.pipeline import FEATURES, SCENARIOS, LGD, fit_logistic, predict_logistic, stress_frame

data = pd.read_csv(ROOT / "data/processed/model_data.csv")
summary = json.loads((ROOT / "outputs/metrics.json").read_text())
print(f"Complete records: {len(data):,}; unique borrowers: {data.borrower_id.nunique():,}")
print("Predictors:", ", ".join(FEATURES))
""")
markdown("""## 1. Reconcile the sources before fitting

The generator intentionally inserts one exact duplicate and two missing financial values.
Complete-case exclusions follow a fixed rule; there is no label-driven selection.
Financial and repayment tables join one-to-one on borrower/date. The macro table joins
many-to-one on date. Conflicting duplicate keys cause a failure.
""")
code("""audit = pd.read_csv(ROOT / "outputs/data_quality_audit.csv")
recon = json.loads((ROOT / "outputs/reconciliation.json").read_text())
print(audit[["step", "count"]].to_string(index=False))
assert recon["raw_rows"] - recon["exact_duplicate_rows"] - recon["excluded_incomplete"] == len(data)
debt_gap = recon["unique_debt_cny_m"] - recon["excluded_debt_cny_m"] - data.debt_cny_m.sum()
assert abs(debt_gap) < 1e-6
print(f"Debt reconciliation difference: {debt_gap:.9f} CNY million")
""")
markdown("""## 2. Respect outcome availability

Each row has a forward 12-month default label. Training snapshots end in 2019, their labels
mature in 2020, validation occurs in 2021, and its labels mature in 2022. The models and
thresholds are frozen before the 2023–2024 test snapshots. Embargo years are not used for
model fitting, threshold selection or performance evaluation. All test labels mature by end-2025.
""")
code("""train = data.loc[data.split.eq("train")].copy()
validation = data.loc[data.split.eq("validation")].copy()
test = data.loc[data.split.eq("test")].copy()
print(data.groupby("split").agg(records=("borrower_id", "size"),
      first_snapshot=("snapshot_date", "min"), last_snapshot=("snapshot_date", "max")).to_string())
assert set(train.borrower_id).isdisjoint(test.borrower_id)
assert pd.to_datetime(train.snapshot_date).max() + pd.DateOffset(years=1) < pd.to_datetime(validation.snapshot_date).min()
assert pd.to_datetime(validation.snapshot_date).max() + pd.DateOffset(years=1) < pd.to_datetime(test.snapshot_date).min()
""")
markdown("""## 3. Estimate the multivariable logistic model

The model estimates one binary response using five numeric predictors. The fit uses
unpenalized maximum likelihood with explicit gradient and Hessian. HC1 standard errors
use an independent-observation sandwich estimator. The coefficients describe a synthetic
predictive association, not a causal relationship or a bank policy.

Interest rate and GDP growth use percentage-point units. Leverage and DSCR use ratio units.
""")
code("""beta, coefficients, diagnostics = fit_logistic(train)
print(coefficients[["term", "coefficient", "std_error", "p_value", "odds_ratio"]].round(5).to_string(index=False))
print("Maximum absolute score:", f"{diagnostics['max_absolute_score']:.3g}")
print("Minimum Hessian eigenvalue:", round(diagnostics["minimum_hessian_eigenvalue"], 4))
print("Maximum training VIF:", round(summary["maximum_training_vif"], 3))
""")
markdown("""## 4. Check the untouched test cohort

The decision tree is selected using validation AUC. Each classifier's threshold maximizes
validation F1 on a fixed grid from 0.01 to 0.80, with the larger threshold breaking ties.
The test set is not used to select parameters or thresholds. AUC measures ranking; Brier
score and calibration examine probability quality. Neither establishes business usefulness alone.
""")
code("""reference = pd.read_csv(ROOT / "outputs/test_predictions.csv")
recomputed = predict_logistic(test, beta)
assert reference.borrower_id.tolist() == test.borrower_id.tolist()
assert np.max(np.abs(recomputed - reference.pd_logistic.to_numpy())) < 1e-7
metrics = pd.read_csv(ROOT / "outputs/model_metrics.csv")
columns = ["model", "n", "roc_auc", "average_precision", "brier_score", "threshold", "precision", "recall"]
print(metrics.loc[metrics.split.eq("test"), columns].round(4).to_string(index=False))
print("Observed test default rate:", f"{test.default_12m.mean():.2%}")
print("Recomputed logistic AUC:", round(roc_auc_score(test.default_12m, recomputed), 6))
print("Recomputed logistic Brier:", round(brier_score_loss(test.default_12m, recomputed), 6))
""")
markdown("""![Test ROC, precision-recall and calibration](../outputs/charts/model_validation.png)

The outcome generator has a logistic form, so the experiment favors that specification.
The high simulated default prevalence was not calibrated to an actual bank. The comparison
demonstrates evaluation mechanics and cannot establish real-world model superiority.
""")
markdown("""## 5. Re-score explicit scenarios

Scenario shocks modify features for the same test borrowers while coefficients, exposure
and past delinquency stay fixed. Mean PD is an unweighted average; the loss proxy weights
each borrower's PD by their debt. LGD is an assumed 45%. This is a conditional sensitivity
exercise, not a causal macro forecast, lending recommendation or complete IFRS 9 model.
""")
code("""scenario_rows = []
for name, shock in SCENARIOS.items():
    changed = stress_frame(test, shock)
    probabilities = predict_logistic(changed, beta)
    scenario_rows.append({"scenario": name, "borrowers": len(changed),
        "mean_pd": probabilities.mean(),
        "loss_proxy_cny_m": np.sum(test.debt_cny_m.to_numpy() * probabilities * LGD)})
scenario_table = pd.DataFrame(scenario_rows)
print(scenario_table.round(4).to_string(index=False))
print("Assumptions:")
print(pd.DataFrame(SCENARIOS).T.to_string())
""")
markdown("""![Conditional scenarios](../outputs/charts/stress_scenarios.png)

## 6. Follow the result into Office

- [Excel review](../outputs/Credit_Risk_Review.xlsx): inspect formulas, change the active scenario and trace summaries to rows.
- [Word memorandum](../outputs/Credit_Risk_Memo.docx): review model results and limitations.
- [PowerPoint deck](../outputs/Credit_Risk_Review.pptx): present the analytical findings.
- [Optional Office modules](../excel/OFFICE_EXTENSIONS.md): manually install Power Query, DAX and VBA examples.

The native R, SAS and Office extension runtimes were not available for execution. Their source
and setup instructions are supplied without claiming verified cross-engine equivalence.
""")

# Embed each chart in place, so portable notebook viewers do not need relative files.
for cell in cells:
    if cell["cell_type"] != "markdown":
        continue
    source = "".join(cell["source"])
    for filename in ["model_validation.png", "stress_scenarios.png"]:
        relative = f"../outputs/charts/{filename}"
        if relative in source:
            source = source.replace(relative, f"attachment:{filename}")
            cell.setdefault("attachments", {})[filename] = {"image/png": base64.b64encode((ROOT / "outputs/charts" / filename).read_bytes()).decode("ascii")}
    cell["source"] = source.splitlines(True)

notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": sys.version.split()[0]},
    "execution_note": "Calculation cells executed sequentially by build_walkthrough.py; no notebook kernel tooling required."},
    "nbformat": 4, "nbformat_minor": 4}
target = ROOT / "notebooks/credit_risk_walkthrough.ipynb"
target.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
print(f"Built {target.name}: {execution_count} calculation cells executed successfully")
