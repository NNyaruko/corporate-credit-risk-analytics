Attribute VB_Name = "CreditReviewAutomation"
Option Explicit

' Optional Excel VBA source. Import only into a separate .xlsm copy.
' This module is not embedded in the distributed .xlsx file.
Public Sub RefreshAndExportSummary()
    Dim ws As Worksheet
    Dim qt As QueryTable
    Dim formulaCells As Range
    Dim cell As Range
    Dim reportSheet As Worksheet
    Dim outputPath As String
    Dim stem As String
    Dim suffix As Long
    Dim previousScreenUpdating As Boolean

    On Error GoTo Failed
    previousScreenUpdating = Application.ScreenUpdating
    If Len(ThisWorkbook.Path) = 0 Then
        Err.Raise vbObjectError + 1001, , "Save the .xlsm workbook before exporting."
    End If
    Set reportSheet = ThisWorkbook.Worksheets("Summary")
    Application.ScreenUpdating = False

    ' Make worksheet query refreshes synchronous where Excel supports it.
    For Each ws In ThisWorkbook.Worksheets
        For Each qt In ws.QueryTables
            qt.BackgroundQuery = False
        Next qt
    Next ws
    ThisWorkbook.RefreshAll
    Application.CalculateUntilAsyncQueriesDone
    Application.CalculateFull

    ' Stop if any workbook formula contains an Excel error.
    For Each ws In ThisWorkbook.Worksheets
        Set formulaCells = Nothing
        On Error Resume Next
        Set formulaCells = ws.UsedRange.SpecialCells(xlCellTypeFormulas)
        On Error GoTo Failed
        If Not formulaCells Is Nothing Then
            For Each cell In formulaCells.Cells
                If IsError(cell.Value) Then
                    Err.Raise vbObjectError + 1002, , _
                        "Formula error at " & ws.Name & "!" & cell.Address(False, False)
                End If
            Next cell
        End If
    Next ws

    stem = ThisWorkbook.Path & Application.PathSeparator & _
        "Credit_Review_" & Format$(Now, "yyyymmdd_hhnnss")
    outputPath = stem & ".pdf"
    suffix = 1
    Do While Len(Dir$(outputPath)) > 0
        outputPath = stem & "_" & CStr(suffix) & ".pdf"
        suffix = suffix + 1
    Loop

    With reportSheet.PageSetup
        .Orientation = xlLandscape
        .Zoom = False
        .FitToPagesWide = 1
        .FitToPagesTall = 1
    End With
    reportSheet.ExportAsFixedFormat Type:=xlTypePDF, Filename:=outputPath, _
        Quality:=xlQualityStandard, IncludeDocProperties:=True, _
        IgnorePrintAreas:=False, OpenAfterPublish:=False
    Application.ScreenUpdating = previousScreenUpdating
    MsgBox "Summary exported to:" & vbCrLf & outputPath, vbInformation
    Exit Sub

Failed:
    Application.ScreenUpdating = previousScreenUpdating
    MsgBox "Export stopped: " & Err.Description, vbExclamation
End Sub
