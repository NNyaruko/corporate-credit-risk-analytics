# Optional Office integrations

The delivered `Credit_Risk_Review.xlsx` is macro-free. The source files here demonstrate optional integrations; they are **not embedded or activated** in the workbook. Power Query, Power Pivot / DAX, and VBA have not been executed in native Excel in this build environment. Review and test them in your installed Excel edition before relying on their output.

All records are synthetic. The workbook and these extensions are independent portfolio examples and have no bank affiliation.

## Power Query

1. Extract the full repository and run the Python pipeline if you want to refresh its committed CSV outputs.
2. In a copy of the workbook, create a one-cell **workbook-scoped** named range `RepoPath`. Enter the absolute repository folder, for example `C:\Projects\corporate-credit-risk-analytics`. Do not enter the `outputs` folder itself.
3. Use **Data → Get Data → From Other Sources → Blank Query**, open the Advanced Editor, and paste `PowerQuery.m`.
4. Name the query `CreditData`. Load it to a new worksheet or select **Only Create Connection** plus **Add this data to the Data Model** when your Excel edition supports the model.
5. The query reads `outputs/test_predictions.csv`, checks schema, types, missing values, duplicate IDs, probability ranges, and the test-cohort label. It intentionally fails rather than silently dropping invalid records.

The query loads a separate table. It does **not** replace the delivered `Source` and `Scoring` sheets, resize their ranges, or rerun model estimation. Rebuild the workbook to incorporate a changed cohort into its scenario formulas.

## Power Pivot / DAX

Load the `CreditData` query into the Data Model. Create the measures from `measures.dax` **one at a time** using the measure names before `:=` and formulas after it. Excel's measure dialog may require only the formula beginning with `=`. The file uses conventional DAX documentation syntax, not an executable batch script.

Build a PivotTable with `sector` or `risk_band` on rows and the desired measures in Values. Counts and sums aggregate directly; the rate measures recompute within filter context. Monetary values are already in CNY millions. The fixed 45% LGD and total borrower debt used as the exposure proxy are illustrative assumptions.

These measures use the **base-case Python probabilities**. They do not respond to the review workbook's separate scenario selector. This distinction prevents a refreshed model table from being mistaken for the live Excel scenario build.

## VBA export

1. Save a **separate copy** as an Excel Macro-Enabled Workbook (`.xlsm`).
2. In the Visual Basic Editor, select **File → Import File** and import `RefreshAndExport.bas`.
3. Review the code, then run `RefreshAndExportSummary`.

The macro refreshes installed connections, waits for supported asynchronous queries, recalculates, checks workbook formula errors, and exports the `Summary` sheet to a timestamped PDF beside the workbook. If the filename already exists, it adds a numeric suffix. It sends nothing externally.

The macro cannot verify that an external refresh returned newly updated data. Check Excel's query refresh status and source dates before using the exported report. A workbook with no installed query connections can still export its existing scenario calculations. Connection support, query security prompts, Power Pivot availability, and PDF page setup depend on the installed Excel edition and need native testing.
