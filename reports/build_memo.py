"""Build the Word memorandum from the committed analytical results.

Run from the repository root: python reports/build_memo.py
Requires python-docx and pandas. All tables use the pipeline outputs directly.
The PDF is a separately rendered copy of the DOCX, not a separate analysis.
"""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
NAVY = "17354A"
GRAY = "EDF2F4"


def shade(cell, fill):
    el = OxmlElement("w:shd")
    el.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(el)


def set_cell_margins(cell):
    tcpr = cell._tc.get_or_add_tcPr()
    margins = OxmlElement("w:tcMar")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), "90")
        el.set(qn("w:type"), "dxa")
        margins.append(el)
    tcpr.append(margins)
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "D9D9D9")
        borders.append(el)
    tcpr.append(borders)


def table(doc, headers, rows, widths):
    tab = doc.add_table(rows=1, cols=len(headers))
    tab.alignment = WD_TABLE_ALIGNMENT.CENTER
    tab.autofit = False
    for col, width in zip(tab.columns, widths):
        col.width = Inches(width)
    for cell, width in zip(tab.rows[0].cells, widths):
        cell.width = Inches(width)
    for i, head in enumerate(headers):
        tab.rows[0].cells[i].text = head
    hdr = OxmlElement("w:tblHeader")
    tab.rows[0]._tr.get_or_add_trPr().append(hdr)
    for row in rows:
        cells = tab.add_row().cells
        for cell, val, width in zip(cells, row, widths):
            cell.text = str(val)
            cell.width = Inches(width)
    for ri, row in enumerate(tab.rows):
        for ci, cell in enumerate(row.cells):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if ri == 0:
                shade(cell, NAVY)
            elif ri % 2 == 0:
                shade(cell, GRAY)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.06
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.size = Pt(9.5)
                    run.font.color.rgb = RGBColor.from_string("FFFFFF" if ri == 0 else "172B3A")
                    run.bold = ri == 0
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return tab


def para(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    if text.startswith("Under the adverse inputs"):
        p.paragraph_format.space_before = Pt(6)
    if bold_prefix and text.startswith(bold_prefix):
        p.add_run(bold_prefix).bold = True
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)
    return p


def source(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_after = Pt(6)
    for r in p.runs:
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor.from_string("63727B")
    return p


def pct(x, digits=1):
    return f"{float(x):.{digits}%}"


def main():
    data = pd.read_csv(ROOT / "data/processed/model_data.csv")
    pred = pd.read_csv(OUT / "test_predictions.csv")
    metrics = pd.read_csv(OUT / "model_metrics.csv")
    coef = pd.read_csv(OUT / "coefficients.csv")
    scenarios = pd.read_csv(OUT / "scenario_summary.csv")
    meta = json.loads((OUT / "metrics.json").read_text())
    # Analytical schema is kept explicit here so changed pipeline outputs fail loudly.
    logistic = metrics[(metrics["model"] == "Logistic") & (metrics["split"] == "test")].iloc[0]
    tree = metrics[(metrics["model"] == "Decision tree") & (metrics["split"] == "test")].iloc[0]
    base = scenarios.iloc[0]
    adverse = scenarios.iloc[1]
    severe = scenarios.iloc[2]
    observed = pred.default_12m.mean()
    mean_pd = pred.pd_logistic.mean()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin = Inches(.62), Inches(.60)
    sec.left_margin, sec.right_margin = Inches(.75), Inches(.75)
    sec.header_distance, sec.footer_distance = Inches(.25), Inches(.25)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(11)
    styles["Normal"].font.color.rgb = RGBColor(0, 0, 0)
    styles["Normal"].paragraph_format.space_after = Pt(7)
    styles["Normal"].paragraph_format.line_spacing = 1.07
    for name, size in [("Title", 25), ("Heading 1", 16), ("Heading 2", 12)]:
        styles[name].font.name = "Arial"
        styles[name].font.size = Pt(size)
        styles[name].font.color.rgb = RGBColor(0, 0, 0)
        styles[name].font.bold = name != "Title"
        styles[name].paragraph_format.space_before = Pt(10 if name != "Title" else 0)
        styles[name].paragraph_format.space_after = Pt(7)
    for style in styles:
        for border in style._element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
        for fonts in style._element.xpath(".//w:rFonts"):
            for attr in list(fonts.attrib):
                if "theme" in attr.lower():
                    del fonts.attrib[attr]
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("Independent demonstration  /  ")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string("63727B")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer._p.append(fld)
    doc.core_properties.title = "Corporate credit risk assessment"
    doc.core_properties.subject = "Synthetic portfolio model review and conditional sensitivity analysis"
    doc.core_properties.author = "Portfolio work sample"
    doc.core_properties.keywords = "synthetic data, credit risk, logistic regression, validation, Excel"
    doc.add_paragraph("Corporate credit risk assessment", "Title")
    para(doc, "Portfolio model review  |  Independent work sample")
    source(doc, "Audience: technical reviewers and credit analysts. All borrowers and financial observations are synthetic.")
    doc.add_heading("Assessment", 1)
    ranking = "more effectively" if logistic.roc_auc > tree.roc_auc else "less effectively"
    para(doc, f"The logistic model ranks defaults {ranking} than the benchmark tree in the held-out cohort: ROC-AUC is {logistic.roc_auc:.3f} versus {tree.roc_auc:.3f}. Its mean predicted default probability is {pct(mean_pd)}, compared with an observed 12-month default rate of {pct(observed)}. The transparent logistic specification remains the demonstration model for scenario analysis.")
    para(doc, "The exercise demonstrates a reproducible analytical workflow using synthetic data. The generator uses a logistic relationship, which favors the fitted logistic model. The results cannot establish production model validity or the credit quality of any real institution or borrower.")
    doc.add_heading("Population and validation design", 1)
    rows = []
    for key, label, period in [("train", "Training", "2017 to 2019"), ("validation", "Validation", "2021"), ("test", "Held-out test", "2023 to 2024")]:
        subset = data[data.split == key]
        rows.append([label, period, f"{len(subset):,}", pct(subset.default_12m.mean())])
    rows.append(["Maturity embargo", "2020 and 2022", f"{len(data[data.split == 'embargo']):,}", "Excluded"])
    table(doc, ["Cohort", "Snapshot years", "Borrowers", "Default rate"], rows, [1.65, 1.8, 1.4, 1.9])
    para(doc, "Each borrower appears once. The target records default during the next 12 months, with test outcomes matured by the end of 2025. Maturity embargoes exclude 2020 and 2022 snapshots so training and validation outcomes finish before the next evaluation period. The workflow joins financial, repayment and macroeconomic records using explicit keys and records reconciliation exceptions.")
    doc.add_heading("Held out model comparison", 1)
    table(doc, ["Measure", "Logistic", "Decision tree"], [["ROC-AUC", f"{logistic.roc_auc:.3f}", f"{tree.roc_auc:.3f}"], ["Average precision", f"{logistic.average_precision:.3f}", f"{tree.average_precision:.3f}"], ["Brier score", f"{logistic.brier_score:.4f}", f"{tree.brier_score:.4f}"], ["Classification threshold", f"{logistic.threshold:.3f}", f"{tree.threshold:.3f}"]], [3.35, 1.7, 1.7])
    source(doc, "Sources: data/processed/model_data.csv; outputs/model_metrics.csv; outputs/test_predictions.csv. Lower Brier scores indicate less squared probability error.")
    doc.add_heading("Statistical validation", 1).paragraph_format.page_break_before = True
    para(doc, "The logistic specification uses debt-to-assets leverage, debt-service coverage, borrowing interest rate, GDP growth and a prior 30-day delinquency indicator. Maximum-likelihood estimation fits the training sample only. HC1 standard errors describe the fitted synthetic sample. They do not establish causal effects or account for all dependence from shared macroeconomic conditions.")
    doc.add_heading("Coefficient diagnostics", 2)
    labels = {"intercept": "Intercept", "const": "Intercept", "leverage": "Leverage", "dscr": "Debt-service coverage", "interest_rate_pct": "Borrowing rate", "gdp_growth_pct": "GDP growth", "past_due_30d": "Prior 30-day delinquency"}
    crows = []
    for row in coef.itertuples():
        pv = "<0.001" if row.p_value < .001 else f"{row.p_value:.3f}"
        crows.append([labels.get(row.term, row.term), f"{row.coefficient:.3f}", f"{row.std_error:.3f}", pv])
    table(doc, ["Predictor", "Coefficient", "HC1 SE", "p value"], crows, [3.15, 1.25, 1.25, 1.1])
    source(doc, "Source: outputs/coefficients.csv. Rates enter in percentage points. Leverage is debt/assets; DSCR is EBITDA/debt service. Coefficients operate on log-odds.")
    doc.add_heading("Probability calibration", 2)
    bins = pd.read_csv(OUT / "calibration_bins.csv")
    chart = OUT / "charts/memo_calibration.png"
    fig, ax = plt.subplots(figsize=(7.3, 3.5))
    for model, color in [("Logistic", "#087E8B"), ("Decision tree", "#CB8423")]:
        sub = bins[bins.model == model]
        ax.plot(sub.mean_pd, sub.observed_default_rate, "o-", label=model, color=color, linewidth=2)
    ax.plot([0, .65], [0, .65], "--", color="#A7B3BC", linewidth=1, label="Perfect calibration")
    ax.set(xlabel="Mean predicted default probability", ylabel="Observed 12-month default rate", xlim=(0, .65), ylim=(0, .65))
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=.18)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(chart, dpi=180, facecolor="white")
    plt.close(fig)
    if chart.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(chart), width=Inches(6.5))
    logistic_bins = bins[bins.model == "Logistic"]
    top_bin = logistic_bins.iloc[-1]
    para(doc, f"The overall prediction gap is {(mean_pd-observed)*100:+.2f} percentage points. Logistic probability groups contain {logistic_bins.n.min()} to {logistic_bins.n.max()} borrowers. The highest group averages {pct(top_bin.mean_pd)} predicted default versus {pct(top_bin.observed_default_rate)} observed. Maximum training VIF is {meta['maximum_training_vif']:.2f}; the borrowing-rate and GDP coefficients have HC1 p values above 0.05.")
    source(doc, "Sources: outputs/calibration_bins.csv; outputs/coefficients.csv; outputs/metrics.json. Thresholds and tree settings use validation data only. HC1 inference assumes independent borrower observations.")
    doc.add_heading("Conditional stress review", 1).paragraph_format.page_break_before = True
    para(doc, "The scenarios rescore the same held-out borrowers with frozen logistic coefficients. They change observable features directly and quantify conditional model sensitivity. They do not forecast macroeconomic transmission or simulate accounting cash flows.")
    table(doc, ["Driver", "Base", "Adverse", "Severe"], [["Leverage", "Unchanged", "+0.05", "+0.10"], ["Debt-service coverage", "Unchanged", "Multiply by 0.85", "Multiply by 0.70"], ["Borrowing rate", "Unchanged", "+1 pp", "+2 pp"], ["GDP growth", "Unchanged", "−2 pp", "−4 pp"]], [2.55, 1.25, 1.475, 1.475])
    source(doc, "Illustrative analyst assumptions. Leverage is bounded to [0,1]. Prior delinquency is unchanged. pp denotes percentage points.")
    # Field names are assigned to the pipeline schema below.
    table(doc, ["Scenario", "Mean PD", "Loss proxy\nCNY million", "Change vs base"], [[r.scenario, pct(r.mean_pd), f"{r.ecl_proxy_cny_m:,.1f}", f"{(r.ecl_proxy_cny_m/base.ecl_proxy_cny_m-1):+.1%}" if i else "—"] for i, r in enumerate(scenarios.itertuples())], [1.75, 1.4, 2.0, 1.6])
    para(doc, f"Under the adverse inputs, the expected-loss proxy increases from CNY {base.ecl_proxy_cny_m:,.1f} million to CNY {adverse.ecl_proxy_cny_m:,.1f} million. The severe inputs produce CNY {severe.ecl_proxy_cny_m:,.1f} million. These comparisons hold debt balances and the 45% loss-given-default assumption constant.")
    para(doc, "The proxy sums borrower debt multiplied by modeled 12-month default probability and assumed loss given default. Debt substitutes for exposure at default. The calculation excludes undrawn commitments, collateral recoveries, discounting, staging and lifetime losses. It is not an IFRS 9 or regulatory capital calculation.")
    doc.add_heading("Review implications", 1)
    support = pd.read_csv(OUT / "scenario_support.csv")
    gdp_outside = int(support.loc[(support.scenario == "Base") & (support.feature == "gdp_growth_pct"), "outside_training_range_n"].iloc[0])
    para(doc, f"GDP growth lies outside the training range for {gdp_outside:,} of {len(pred):,} base-case borrowers and every borrower under the adverse and severe scenarios. These predictions therefore involve extrapolation. Before operational use, real data would require independent outcome verification, segment validation, recalibration and a separately justified exposure and recovery model.")
    doc.add_heading("Reproduction and scope", 1)
    para(doc, "Run python -m src.pipeline from the repository root to rebuild the analytical outputs. Run python reports/build_memo.py to regenerate this memo. The Excel file exposes scoring formulas and scenario controls. The repository documents execution status for optional R and SAS implementations.")
    source(doc, "Sources: outputs/scenario_summary.csv; outputs/scenario_support.csv; outputs/coefficients.csv. All figures refer to the fixed held-out cohort. Rounding may affect displayed sums.")
    OUT.mkdir(exist_ok=True)
    path = OUT / "Credit_Risk_Memo.docx"
    doc.save(path)
    print(path)


if __name__ == "__main__":
    main()
