// Optional Power Query example. Import into Excel as the query CreditData.
// This source is not embedded in Credit_Risk_Review.xlsx.
let
    NamedPath = try Excel.CurrentWorkbook(){[Name="RepoPath"]}[Content],
    PathTable = if NamedPath[HasError] then
        error "Create a one-cell named range RepoPath containing the repository's absolute path."
        else NamedPath[Value],
    PathValue = try Text.From(Record.FieldValues(PathTable{0}){0}),
    Root = if PathValue[HasError] then error "RepoPath must contain one text path."
        else Text.TrimEnd(Text.Trim(PathValue[Value]), {"/", "\"}),
    FilePath = if Root = null or Root = "" then error "RepoPath is blank."
        else Root & "/outputs/test_predictions.csv",
    Source = Csv.Document(File.Contents(FilePath),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Required = {
        "borrower_id", "snapshot_date", "sector", "revenue_cny_m",
        "debt_cny_m", "total_assets_cny_m", "ebitda_cny_m", "debt_service_cny_m",
        "leverage", "dscr", "interest_rate_pct", "gdp_growth_pct",
        "past_due_30d", "default_12m", "split", "pd_logistic", "pd_tree", "risk_band"
    },
    Missing = List.Difference(Required, Table.ColumnNames(Headers)),
    Selected = if List.Count(Missing) > 0 then
        error ("Missing required columns: " & Text.Combine(Missing, ", "))
        else Table.SelectColumns(Headers, Required),
    Typed = Table.TransformColumnTypes(Selected, {
        {"borrower_id", type text}, {"snapshot_date", type date}, {"sector", type text},
        {"revenue_cny_m", type number}, {"debt_cny_m", type number},
        {"total_assets_cny_m", type number}, {"ebitda_cny_m", type number},
        {"debt_service_cny_m", type number}, {"leverage", type number},
        {"dscr", type number}, {"interest_rate_pct", type number},
        {"gdp_growth_pct", type number}, {"past_due_30d", type number},
        {"default_12m", type number}, {"split", type text},
        {"pd_logistic", type number}, {"pd_tree", type number}, {"risk_band", type text}
    }, "en-US"),
    Buffered = Table.Buffer(Typed),
    ErrorRows = Table.RowCount(Table.SelectRowsWithErrors(Buffered)),
    CheckedTypes = if ErrorRows > 0 then error "CSV contains type-conversion errors."
        else Buffered,
    MissingValues = Table.RowCount(Table.SelectRows(CheckedTypes,
        each List.NonNullCount(Record.FieldValues(_)) <> List.Count(Required))),
    Complete = if MissingValues > 0 then error "Required values are missing."
        else CheckedTypes,
    BlankIDs = Table.RowCount(Table.SelectRows(Complete, each Text.Trim([borrower_id]) = "")),
    DuplicateIDs = Table.RowCount(Complete) - Table.RowCount(Table.Distinct(Complete, {"borrower_id"})),
    Invalid = Table.RowCount(Table.SelectRows(Complete, each
        Text.Trim([sector]) = "" or Text.Trim([risk_band]) = "" or
        [debt_cny_m] < 0 or [total_assets_cny_m] <= 0 or [debt_service_cny_m] <= 0 or
        [leverage] < 0 or [leverage] > 1 or [dscr] <= 0 or
        [pd_logistic] < 0 or [pd_logistic] > 1 or [pd_tree] < 0 or [pd_tree] > 1 or
        not List.Contains({0,1}, [default_12m]) or not List.Contains({0,1}, [past_due_30d]) or
        [split] <> "test")),
    Validated = if Table.RowCount(Complete) = 0 then error "The test cohort is empty."
        else if BlankIDs > 0 then error "Borrower identifiers are blank."
        else if DuplicateIDs > 0 then error "Borrower identifiers are duplicated."
        else if Invalid > 0 then error "Invalid financial values, probability, outcome, or cohort."
        else Complete,
    CreditData = Table.TransformColumnTypes(Validated,
        {{"past_due_30d", Int64.Type}, {"default_12m", Int64.Type}})
in
    CreditData
