# Reporting artifacts

The committed Word memorandum and PowerPoint deck summarize the same final
synthetic analysis. They contain no real borrower or employer information.
PDF copies allow review without Office software.

## Word memorandum

After running the main pipeline, install `python-docx` in the Python environment
containing the project's analytical dependencies, then run:

```bash
python reports/build_memo.py
```

The builder reads the processed cohort, metrics, coefficient estimates,
calibration bins and scenario outputs. It creates
`outputs/Credit_Risk_Memo.docx` and a calibration chart. Its tables remain
editable in Word. The chart is a high-resolution image.

To create a PDF locally, open the DOCX in Word or LibreOffice and export to PDF.
The committed PDF was rendered with LibreOffice and reviewed page by page.
Native Microsoft Word rendering was not tested.

## PowerPoint deck

`build_slides.mjs` documents the presentation construction. It uses the
`@oai/artifact-tool` package available in the authoring environment. This is an
optional authoring dependency and is not required to open, edit or review the
committed presentation. The main Python pipeline does not rebuild the deck.

Data tables and charts are editable native slide content. The deck reads
`outputs/metrics.json` and `outputs/calibration_bins.csv` directly.
Presentation rounding does not change the pipeline CSVs.

The deck's preview and structural checks validate the generated artifact.
Native desktop PowerPoint rendering was not tested. If the model or data
changes, refresh both the reporting inputs and the presentation before using its
figures.
