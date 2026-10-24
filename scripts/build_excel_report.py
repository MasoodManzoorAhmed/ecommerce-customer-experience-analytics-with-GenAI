"""Build the Excel monthly management report: excel/Monthly_CX_Report.xlsx.

The workbook is built BY Excel (through its COM automation interface), so PivotTables,
PivotCharts, slicers and What-If Data Tables are real Excel objects, not static copies.
Data comes from sql/08_excel_report.sql; every ratio in the workbook is a formula over
additive counts, and a Checks sheet reconciles the totals with powerbi/expected_values.csv.

Windows + Microsoft Excel required.

    python scripts/build_db.py              # first, if the database isn't built
    python scripts/build_excel_report.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make the src package importable when run as a script

from src.db import connect, load_named_sql  # noqa: E402

OUT_PATH = ROOT / "excel" / "Monthly_CX_Report.xlsx"
EXPECTED_CSV = ROOT / "powerbi" / "expected_values.csv"
FIRST_MONTH, LAST_MONTH = "2017-01", "2018-08"  # usable window (see the data-quality report)

# Same palette as the Power BI report
INK, TEAL, CORAL, LIGHT_TEAL = "0B3C49", "0B6E7A", "E4572E", "7FB7BE"
GREY, PALE, BAND = "5C6B70", "E9F2F3", "F5F9FA"
INPUT_FILL, INPUT_FONT, INPUT_EDGE = "FFF2CC", "1F4E9A", "BF9000"
GOOD, BAD, LOW, HIGH = "1E7B34", "C0392B", "F8C9BC", "BFE3E6"

FMT_MONEY = '"R$" #,##0'
FMT_MONEY2 = '"R$" #,##0.00'
FMT_INT = "#,##0"
FMT_PCT = "0.0%"
FMT_PCT2 = "0.00%"
FMT_STARS = "0.00"
FMT_DPCT = "+0.0%;-0.0%;0.0%"
FMT_DPTS = '+0.0" pts";-0.0" pts";0.0" pts"'
FMT_DSTARS = "+0.00;-0.00;0.00"
FMT_DDAYS = '+0.0" d";-0.0" d";0.0" d"'

# Formula pieces reused across sheets
PREV_MONTH = 'IF(RIGHT(m,2)="01",(LEFT(m,4)-1)&"-12",LEFT(m,5)&TEXT(RIGHT(m,2)-1,"00"))'
LAST_YEAR = "(LEFT(m,4)-1)&RIGHT(m,3)"


# ----------------------------------------------------------------------------- small helpers
def rgb(hex_color: str) -> int:
    """'RRGGBB' -> the BGR integer Excel's COM interface expects."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return r + g * 256 + b * 65536


def col_letter(n: int) -> str:
    """1 -> A, 27 -> AA."""
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def a1(row: int, col: int) -> str:
    return f"{col_letter(col)}{row}"


def area(row: int, col: int, n_rows: int, n_cols: int) -> str:
    """A1-style address of a block starting at (row, col)."""
    return f"{a1(row, col)}:{a1(row + n_rows - 1, col + n_cols - 1)}"


def months_between(first: str, last: str) -> list[str]:
    """['2017-01', ..., '2018-08'] inclusive."""
    return [p.strftime("%Y-%m") for p in pd.period_range(first, last, freq="M")]


def expand_sumifs(formula: str) -> str:
    """S(col) -> SUMIFS of that data column for this row's month and the chosen state."""
    return re.sub(
        r"S\((\w+)\)",
        r"SUMIFS(tbl_month_state[\1],tbl_month_state[year_month],[@Month],"
        r"tbl_month_state[customer_state],state_crit)",
        formula,
    )


def rows_for_excel(df: pd.DataFrame) -> list[tuple]:
    """Header + rows as plain Python values (COM can't take numpy types)."""
    body = [
        tuple(v.item() if hasattr(v, "item") else v for v in row)
        for row in df.itertuples(index=False)
    ]
    return [tuple(df.columns), *body]


# ----------------------------------------------------------------------------- data
def extract() -> dict[str, pd.DataFrame]:
    """Run the named queries of sql/08_excel_report.sql."""
    with connect(read_only=True) as con:
        return {q.name: con.execute(q.sql).df() for q in load_named_sql("08_excel_report.sql")}


def expected_values() -> dict[str, float]:
    """check name -> expected value, from the Power BI reconciliation file (computed with SQL)."""
    df = pd.read_csv(EXPECTED_CSV)
    return dict(zip(df["check"], df["expected_value"].astype(float), strict=True))


# ----------------------------------------------------------------------------- workbook
class Book:
    """An Excel workbook plus the formatting conventions used on every sheet."""

    def __init__(self, xl, c):
        self.xl, self.c = xl, c
        self.wb = xl.Workbooks.Add()
        self._unused = self.wb.Worksheets(1)

    def sheet(self, name: str, tab: str):
        if self._unused is not None:
            ws, self._unused = self._unused, None
        else:
            ws = self.wb.Worksheets.Add(After=self.wb.Worksheets(self.wb.Worksheets.Count))
        ws.Name = name
        ws.Tab.Color = rgb(tab)
        ws.Cells.Font.Name = "Segoe UI"
        ws.Cells.Font.Size = 10
        return ws

    def view(self, ws, gridlines: bool = False, freeze: str | None = None):
        ws.Activate()
        win = self.xl.ActiveWindow
        win.DisplayGridlines = gridlines
        if freeze:
            ws.Range(freeze).Select()
            win.FreezePanes = True
        ws.Range("A1").Select()

    def name(self, name: str, refers_to: str):
        self.wb.Names.Add(Name=name, RefersTo=refers_to)

    @staticmethod
    def title(ws, text: str, subtitle: str, row: int = 2, col: int = 2):
        t = ws.Range(a1(row, col))
        t.Value = text
        t.Font.Size = 18
        t.Font.Bold = True
        t.Font.Color = rgb(INK)
        s = ws.Range(a1(row + 1, col))
        s.Value = subtitle
        s.Font.Color = rgb(GREY)
        s.Font.Italic = True

    @staticmethod
    def header(rng, fill: str = TEAL):
        rng.Font.Bold = True
        rng.Font.Color = rgb("FFFFFF")
        rng.Interior.Color = rgb(fill)

    @staticmethod
    def section(cell, text: str):
        cell.Value = text
        cell.Font.Bold = True
        cell.Font.Size = 12
        cell.Font.Color = rgb(TEAL)

    @staticmethod
    def note(cell, text: str):
        cell.Value = text
        cell.Font.Color = rgb(GREY)
        cell.Font.Italic = True

    @staticmethod
    def input_cell(rng):
        """Financial-model convention: inputs have a yellow fill and a blue font."""
        rng.Interior.Color = rgb(INPUT_FILL)
        rng.Font.Color = rgb(INPUT_FONT)
        rng.Font.Bold = True
        for edge in (7, 8, 9, 10):  # left, top, bottom, right
            rng.Borders(edge).Color = rgb(INPUT_EDGE)

    def color_scale(self, rng, scope_pivot: bool = False):
        cs = rng.FormatConditions.AddColorScale(3)
        for i, color in enumerate((LOW, "FFFFFF", HIGH), start=1):
            cs.ColorScaleCriteria(i).FormatColor.Color = rgb(color)
        if scope_pivot:
            cs.ScopeType = self.c.xlDataFieldScope
        return cs

    def data_table(self, ws, df: pd.DataFrame, name: str, formats: dict[str, str]):
        rows = rows_for_excel(df)
        rng = ws.Range(area(1, 1, len(rows), len(rows[0])))
        rng.Value = rows
        lo = ws.ListObjects.Add(self.c.xlSrcRange, rng, None, self.c.xlYes)
        lo.Name = name
        lo.TableStyle = "TableStyleLight9"
        for col, fmt in formats.items():
            lo.ListColumns(col).DataBodyRange.NumberFormat = fmt
        rng.Columns.AutoFit()
        return lo

    def pivot(self, cache, ws, cell: str, name: str):
        pt = cache.CreatePivotTable(TableDestination=ws.Range(cell), TableName=name)
        pt.RowAxisLayout(self.c.xlTabularRow)
        pt.TableStyle2 = "PivotStyleLight16"
        return pt

    def slicer(self, pivots, field: str, ws, caption: str, left: float, top: float, w=190, h=130):
        sc = self.wb.SlicerCaches.Add2(pivots[0], field)
        for pt in pivots[1:]:
            sc.PivotTables.AddPivotTable(pt)
        sl = sc.Slicers.Add(
            SlicerDestination=ws, Caption=caption, Top=top, Left=left, Width=w, Height=h
        )
        return sl

    def empty_chart(self, ws, chart_type, left, top, width, height):
        """A chart with no series (Excel would otherwise guess from the current selection)."""
        ws.Activate()
        ws.Range("A1").Select()
        chart = ws.Shapes.AddChart2(-1, chart_type, left, top, width, height).Chart
        while chart.SeriesCollection().Count:
            chart.SeriesCollection(1).Delete()
        return chart

    def style_chart(self, chart, title: str, legend: bool = True):
        chart.HasTitle = True
        chart.ChartTitle.Text = title
        chart.ChartTitle.Format.TextFrame2.TextRange.Font.Size = 11
        chart.HasLegend = legend
        if legend:
            chart.Legend.Position = self.c.xlLegendPositionBottom


# ----------------------------------------------------------------------------- sheets
def build_readme(bk: Book, data: dict[str, pd.DataFrame], months: list[str]) -> None:
    ws = bk.sheet("Read me", INK)
    ws.Columns("A").ColumnWidth = 2
    ws.Columns("B").ColumnWidth = 18
    ws.Columns("C").ColumnWidth = 110
    bk.title(
        ws,
        "Olist customer experience: monthly management report",
        "Brazilian marketplace · ~96k delivered orders · built from the project's DuckDB star "
        "schema",
    )
    sections = [
        (
            "Purpose",
            "Monthly view of sales, delivery and review KPIs for managers, with drill-down by "
            "state "
            "and category, and a what-if estimate of what better on-time delivery is worth in "
            "reviews.",
        ),
        (
            "Period",
            f"Monthly KPIs: {months[0]} to {months[-1]}. 2016 (a few hundred orders) and Sep-Oct "
            "2018 "
            "(data cut-off) are too thin for monthly figures; they stay in the data sheets and "
            "pivots "
            "so totals reconcile.",
        ),
        (
            "Definitions",
            "Delivered order = delivered with a delivery date. Revenue = item price of delivered "
            "orders, "
            "excluding freight, by purchase month. On-time = delivered on or before the estimated "
            "date. "
            "Average review = delivered orders with a review. AOV = revenue / delivered orders. "
            "Payment instalments are out of scope.",
        ),
        (
            "How to use",
            "Summary: pick a month and a customer state in the yellow cells. Categories and "
            "States: use "
            "the slicers. What-if: change the yellow assumptions. Yellow fill + blue font = input; "
            "everything else is calculated.",
        ),
        (
            "Sheets",
            "Summary (KPIs vs previous month and last year, key messages, charts) · Monthly (KPI "
            "table "
            "for the chosen state) · Categories (PivotTables, PivotChart, slicers) · States "
            "(PivotTable "
            "with calculated fields, PivotChart, slicer) · What-if (assumptions, results, Data "
            "Tables) · "
            "Checks (reconciliation) · Data_MonthState, Data_Category (source data as Excel "
            "tables).",
        ),
        (
            "Data",
            f"Data_MonthState: {len(data['excel_monthly_state']):,} rows (month x state). "
            "Data_Category: "
            f"{len(data['excel_category']):,} rows (month x state x category). Only additive "
            "counts and "
            "sums: every ratio is rebuilt by formula, so it stays correct under any filter or "
            "slicer.",
        ),
        (
            "Quality",
            "The Checks sheet compares workbook formulas with values computed independently in SQL "
            "(the same values the Power BI report is reconciled against). All must show PASS.",
        ),
        (
            "Refresh",
            "python scripts/build_excel_report.py rebuilds this file from data/olist.duckdb "
            "(needs Windows + Excel). SQL: sql/08_excel_report.sql.",
        ),
    ]
    for i, (label, text) in enumerate(sections):
        r = 6 + i
        lab, txt = ws.Range(f"B{r}"), ws.Range(f"C{r}")
        lab.Value = label
        lab.Font.Bold = True
        lab.Font.Color = rgb(TEAL)
        txt.Value = text
        txt.WrapText = True
        ws.Range(f"B{r}:C{r}").VerticalAlignment = -4160  # top
    bk.view(ws)


def build_summary_inputs(bk: Book) -> None:
    """Summary sheet title and the two inputs (created first: other sheets use their names)."""
    ws = bk.sheet("Summary", TEAL)
    ws.Columns("A").ColumnWidth = 2
    ws.Columns("B").ColumnWidth = 28
    for col in "CDEFG":
        ws.Columns(col).ColumnWidth = 15
    ws.Columns("H").ColumnWidth = 12
    bk.title(
        ws,
        "Olist customer experience: monthly management report",
        "Delivered orders · revenue = item price excl. freight · by purchase month · "
        "source: DuckDB star schema (sql/08_excel_report.sql)",
    )
    ws.Range("B5").Value = "Month"
    ws.Range("C5").NumberFormat = "@"
    ws.Range("C5").Value = LAST_MONTH
    ws.Range("E5").Value = "Customer state"
    ws.Range("F5").Value = "All"
    ws.Range("B5,E5").Font.Bold = True
    bk.input_cell(ws.Range("C5"))
    bk.input_cell(ws.Range("F5"))
    bk.note(ws.Range("G5"), "◄ choose (yellow = input)")
    bk.name("sel_month", "=Summary!$C$5")
    bk.name("sel_state", "=Summary!$F$5")
    helper = ws.Range("J5")
    helper.Formula = '=IF(sel_state="All","*",sel_state)'  # SUMIFS wildcard for "All"
    helper.Font.Color = rgb("FFFFFF")
    bk.name("state_crit", "=Summary!$J$5")


def build_data_sheets(bk: Book, data: dict[str, pd.DataFrame]) -> None:
    ms = data["excel_monthly_state"]
    ws = bk.sheet("Data_MonthState", "A6A6A6")
    text_cols = ("year_month", "year", "customer_state", "state_500_plus", "revenue")
    formats = {c: FMT_INT for c in ms.columns if c not in text_cols}
    formats["revenue"] = FMT_MONEY2
    bk.data_table(ws, ms, "tbl_month_state", formats)
    bk.view(ws, gridlines=True, freeze="A2")

    ws = bk.sheet("Data_Category", "A6A6A6")
    formats = {"orders": FMT_INT, "items": FMT_INT, "revenue": FMT_MONEY2}
    bk.data_table(ws, data["excel_category"], "tbl_category", formats)
    bk.view(ws, gridlines=True, freeze="A2")

    ws = bk.sheet("Lists", "A6A6A6")
    ws.Range("A1").Value = "Customer states for the Summary drop-down"
    ws.Range("A2").Formula2 = '=VSTACK("All",SORT(UNIQUE(tbl_month_state[customer_state])))'
    bk.name("list_states", "=Lists!$A$2#")


MONTHLY_COLUMNS = [
    # header, number format, formula; S(x) = SUMIFS of data column x for the row's month + state
    ("Month", "@", None),
    ("Revenue", FMT_MONEY, "=S(revenue)"),
    ("Delivered orders", FMT_INT, "=S(delivered_orders)"),
    ("AOV", FMT_MONEY2, '=IFERROR([@Revenue]/[@[Delivered orders]],"")'),
    ("Late orders", FMT_INT, "=S(late_orders)"),
    ("On-time %", FMT_PCT2, '=IFERROR(1-[@[Late orders]]/[@[Delivered orders]],"")'),
    ("Late rate %", FMT_PCT2, '=IFERROR([@[Late orders]]/[@[Delivered orders]],"")'),
    ("Avg review", FMT_STARS, '=IFERROR(S(review_sum)/S(reviews),"")'),
    ("Avg review on time", FMT_STARS, '=IFERROR(S(review_sum_on_time)/S(reviews_on_time),"")'),
    ("Avg review late", FMT_STARS, '=IFERROR(S(review_sum_late)/S(reviews_late),"")'),
    (
        "1-2 star share",
        FMT_PCT,
        "=IFERROR((S(low_ratings_on_time)+S(low_ratings_late))"
        '/(S(reviews_on_time)+S(reviews_late)),"")',
    ),
    ("Avg delivery days", "0.0", '=IFERROR(S(delivery_days_sum)/S(delivery_days_n),"")'),
    (
        "Revenue MoM %",
        FMT_DPCT,
        f'=LET(m,[@Month],v,XLOOKUP({PREV_MONTH},[Month],[Revenue],""),IF(v="","",[@Revenue]/v-1))',
    ),
    (
        "Revenue YoY %",
        FMT_DPCT,
        f'=LET(m,[@Month],v,XLOOKUP({LAST_YEAR},[Month],[Revenue],""),IF(v="","",[@Revenue]/v-1))',
    ),
]


def build_monthly(bk: Book, months: list[str]) -> None:
    ws = bk.sheet("Monthly", LIGHT_TEAL)
    bk.title(
        ws,
        "Monthly KPIs",
        f"{months[0]} to {months[-1]} · follows the customer state chosen on the Summary sheet · "
        "every value is a formula over Data_MonthState",
        row=1,
        col=1,
    )
    headers = [h for h, _, _ in MONTHLY_COLUMNS]
    top = 5
    ws.Range(area(top, 1, 1, len(headers))).Value = tuple(headers)
    month_rng = ws.Range(area(top + 1, 1, len(months), 1))
    month_rng.NumberFormat = "@"
    month_rng.Value = [(m,) for m in months]
    rng = ws.Range(area(top, 1, len(months) + 1, len(headers)))
    lo = ws.ListObjects.Add(bk.c.xlSrcRange, rng, None, bk.c.xlYes)
    lo.Name = "tbl_monthly"
    lo.TableStyle = "TableStyleLight9"
    for header, fmt, formula in MONTHLY_COLUMNS:
        body = lo.ListColumns(header).DataBodyRange
        body.NumberFormat = fmt
        if formula:
            body.Formula2 = expand_sumifs(formula)
    rng.Columns.ColumnWidth = 13
    hdr = ws.Range(area(top, 1, 1, len(headers)))
    hdr.WrapText = True
    hdr.RowHeight = 30
    bar = lo.ListColumns("Revenue").DataBodyRange.FormatConditions.AddDatabar()
    bar.BarColor.Color = rgb(LIGHT_TEAL)
    bar.BarFillType = 0  # solid
    bk.note(
        ws.Range("A3"),
        "Revenue YoY % is inflated in early 2018: the marketplace was still ramping up in early "
        "2017 "
        "(Jan 2017: 750 delivered orders vs 7,069 in Jan 2018). Read it from about May 2018 "
        "onwards.",
    )
    for col in ("On-time %", "Avg review"):
        bk.color_scale(lo.ListColumns(col).DataBodyRange)
    bk.name("list_months", "=Monthly!$A$6:$A$" + str(top + len(months)))
    bk.view(ws, freeze="B6")


SUMMARY_ROWS = [
    # label, Monthly column, number format, change type, better when
    ("Revenue", "Revenue", FMT_MONEY, "pct", "Higher"),
    ("Delivered orders", "Delivered orders", FMT_INT, "pct", "Higher"),
    ("Average order value", "AOV", FMT_MONEY2, "pct", "Higher"),
    ("On-time delivery %", "On-time %", FMT_PCT, "pts", "Higher"),
    ("Late orders", "Late orders", FMT_INT, "pct", "Lower"),
    ("Average review (stars)", "Avg review", FMT_STARS, "stars", "Higher"),
    ("1-2 star review share", "1-2 star share", FMT_PCT, "pts", "Lower"),
    ("Average delivery days", "Avg delivery days", "0.0", "days", "Lower"),
]
CHANGE = {
    # % change for amounts; percentage-point / star / day differences for rates and averages
    # rounded to the displayed precision, so a "-0.00" change is neutral rather than red
    "pct": ('=IF(OR({a}="",{b}=""),"",ROUND({a}/{b}-1,3))', FMT_DPCT),
    "pts": ('=IF(OR({a}="",{b}=""),"",ROUND(({a}-{b})*100,1))', FMT_DPTS),
    "stars": ('=IF(OR({a}="",{b}=""),"",ROUND({a}-{b},2))', FMT_DSTARS),
    "days": ('=IF(OR({a}="",{b}=""),"",ROUND({a}-{b},1))', FMT_DDAYS),
}


def build_summary(bk: Book) -> None:
    ws = bk.wb.Worksheets("Summary")
    for cell, source in (("C5", "=list_months"), ("F5", "=list_states")):
        v = ws.Range(cell).Validation
        v.Delete()
        v.Add(Type=bk.c.xlValidateList, AlertStyle=bk.c.xlValidAlertStop, Formula1=source)

    bk.note(ws.Range("B7"), "Selected month vs previous month and the same month last year")
    hdr = ws.Range("B8:H8")
    hdr.Value = ("Metric", "", "", "Change", "", "Change", "Better when")
    ws.Range("C8").Formula = "=sel_month"
    ws.Range("D8").Formula2 = f"=LET(m,sel_month,{PREV_MONTH})"
    ws.Range("F8").Formula2 = f"=LET(m,sel_month,{LAST_YEAR})"
    bk.name("prev_month", "=Summary!$D$8")
    bk.name("ly_month", "=Summary!$F$8")
    bk.header(hdr)
    ws.Range("C8:H8").HorizontalAlignment = -4152  # right, over the numbers

    first = 9
    for i, (label, col, fmt, kind, better) in enumerate(SUMMARY_ROWS):
        r = first + i
        ws.Range(f"B{r}").Value = label
        for out, key in (("C", "sel_month"), ("D", "prev_month"), ("F", "ly_month")):
            cell = ws.Range(f"{out}{r}")
            cell.Formula2 = f'=XLOOKUP({key},tbl_monthly[Month],tbl_monthly[{col}],"")'
            cell.NumberFormat = fmt
        formula, dfmt = CHANGE[kind]
        for out, a, b in (("E", "C", "D"), ("G", "C", "F")):
            cell = ws.Range(f"{out}{r}")
            cell.Formula = formula.format(a=f"{a}{r}", b=f"{b}{r}")
            cell.NumberFormat = dfmt
        ws.Range(f"H{r}").Value = better
    last = first + len(SUMMARY_ROWS) - 1
    ws.Range(f"B{first}:H{last}").RowHeight = 20
    ws.Range(f"B{first}:H{last}").VerticalAlignment = -4108
    ws.Range(f"C{first}:C{last}").Font.Bold = True
    ws.Range(f"C{first}:C{last}").Font.Size = 11
    ws.Range(f"H{first}:H{last}").Font.Color = rgb(GREY)
    ws.Range(f"H{first}:H{last}").HorizontalAlignment = -4152
    for r in range(first, last + 1, 2):
        ws.Range(f"B{r}:H{r}").Interior.Color = rgb(BAND)
    # Green when a change moves the right way for that metric, red when it moves the wrong way
    for col in ("E", "G"):
        rng = ws.Range(f"{col}{first}:{col}{last}")
        for color, test in ((GOOD, ">"), (BAD, "<")):
            fc = rng.FormatConditions.Add(
                Type=bk.c.xlExpression,
                Formula1=(
                    f'=AND(ISNUMBER({col}{first}),IF($H{first}="Higher",'
                    f"{col}{first}{test}0,{col}{first}{'<' if test == '>' else '>'}0))"
                ),
            )
            fc.Font.Color = rgb(color)
            fc.Font.Bold = True

    # Key messages: formulas, so they follow the chosen month and state
    bk.section(ws.Range("B19"), "Key messages")
    scope = '" ("&IF(sel_state="All","all states",sel_state)&")"'
    messages = [
        '="Revenue in "&sel_month&' + scope + '&": R$ "&TEXT(C9,"#,##0")'
        '&IF(ISNUMBER(E9),", "&IF(E9>=0,"up ","down ")&TEXT(ABS(E9),"0.0%")&" on "&prev_month,"")'
        '&IF(ISNUMBER(G9),", "&IF(G9>=0,"up ","down ")&TEXT(ABS(G9),"0.0%")&" on "&ly_month,"")'
        '&"."',
        '="On-time delivery "&TEXT(C12,"0.0%")&" ("&TEXT(C13,"#,##0")&" late orders)"'
        '&IF(ISNUMBER(E12),", "&TEXT(E12,"+0.0;-0.0")&" pts vs "&prev_month,"")&"."',
        '=IFERROR("Average review "&TEXT(C14,"0.00")&" stars: late orders were rated "'
        '&TEXT(XLOOKUP(sel_month,tbl_monthly[Month],tbl_monthly[Avg review late]),"0.00")'
        '&" vs "&TEXT(XLOOKUP(sel_month,tbl_monthly[Month],tbl_monthly[Avg review on time]),"0.00")'
        '&" on time.","Average review: too few reviews in this selection.")',
    ]
    for i, formula in enumerate(messages):
        cell = ws.Range(f"B{20 + i}")
        cell.Formula2 = formula
        cell.Font.Size = 11

    # Charts from the Monthly table
    lo = bk.wb.Worksheets("Monthly").ListObjects("tbl_monthly")

    def col(header: str):
        return lo.ListColumns(header).DataBodyRange

    top, left = ws.Range("B26").Top, ws.Range("B26").Left
    specs = [
        (
            "Revenue (bars) and on-time % (line)",
            "Revenue",
            "On-time %",
            TEAL,
            INK,
            '"R$" #,##0,"k"',
            "0%",
            (0.75, 1.0),
        ),
        (
            "Late rate % (bars) and average review (line)",
            "Late rate %",
            "Avg review",
            CORAL,
            TEAL,
            "0%",
            "0.0",
            (3.5, 4.5),
        ),
    ]
    for i, (title, bars, line, bar_color, line_color, fmt1, fmt2, scale) in enumerate(specs):
        ch = bk.empty_chart(ws, bk.c.xlColumnClustered, left + i * 470, top, 455, 270)
        s1 = ch.SeriesCollection().NewSeries()
        s1.Name = bars
        s1.Values = col(bars)
        s1.XValues = col("Month")
        s1.Format.Fill.ForeColor.RGB = rgb(bar_color)
        s2 = ch.SeriesCollection().NewSeries()
        s2.Name = line
        s2.Values = col(line)
        s2.XValues = col("Month")
        s2.ChartType = bk.c.xlLine
        s2.AxisGroup = bk.c.xlSecondary
        s2.Format.Line.ForeColor.RGB = rgb(line_color)
        s2.Format.Line.Weight = 2.25
        bk.style_chart(ch, title)
        ch.Axes(bk.c.xlValue, bk.c.xlPrimary).TickLabels.NumberFormat = fmt1
        sec = ch.Axes(bk.c.xlValue, bk.c.xlSecondary)
        sec.TickLabels.NumberFormat = fmt2
        sec.MinimumScale, sec.MaximumScale = scale
    bk.note(ws.Range("B25"), "Trend, Jan 2017 - Aug 2018 (follows the customer state chosen above)")
    ps = ws.PageSetup
    ps.Orientation = bk.c.xlLandscape
    ps.Zoom = False
    ps.FitToPagesWide = 1
    ps.FitToPagesTall = 1
    bk.view(ws)


def build_categories(bk: Book) -> None:
    ws = bk.sheet("Categories", LIGHT_TEAL)
    bk.title(
        ws,
        "Revenue by month and category",
        "PivotTables on Data_Category · filter with the slicers · top categories by revenue",
        row=1,
        col=1,
    )
    cache = bk.wb.PivotCaches().Create(SourceType=bk.c.xlDatabase, SourceData="tbl_category")

    pt = bk.pivot(cache, ws, "A26", "pt_category_month")
    month = pt.PivotFields("year_month")
    month.Orientation = bk.c.xlRowField
    month.Caption = "Month"
    cat = pt.PivotFields("category")
    cat.Orientation = bk.c.xlColumnField
    cat.Caption = "Category"
    rev = pt.AddDataField(pt.PivotFields("revenue"), "Revenue (R$)", bk.c.xlSum)
    rev.NumberFormat = FMT_MONEY
    cat.PivotFilters.Add2(Type=bk.c.xlTopCount, DataField=rev, Value1=8)
    cat.AutoSort(bk.c.xlDescending, "Revenue (R$)")
    ws.Range("A24").Value = "Revenue by month, top 8 categories"

    pt2 = bk.pivot(cache, ws, "M26", "pt_category_rank")
    cat2 = pt2.PivotFields("category")
    cat2.Orientation = bk.c.xlRowField
    cat2.Caption = "Category"
    rev2 = pt2.AddDataField(pt2.PivotFields("revenue"), "Revenue ", bk.c.xlSum)
    rev2.NumberFormat = FMT_MONEY
    share = pt2.AddDataField(pt2.PivotFields("revenue"), "Share of revenue", bk.c.xlSum)
    share.Calculation = bk.c.xlPercentOfTotal
    share.NumberFormat = FMT_PCT
    orders = pt2.AddDataField(pt2.PivotFields("orders"), "Orders with category", bk.c.xlSum)
    orders.NumberFormat = FMT_INT
    cat2.AutoSort(bk.c.xlDescending, "Revenue ")
    ws.Range("M24").Value = "All categories ranked by revenue (share of the selection's total)"
    ws.Range("A24,M24").Font.Bold = True
    ws.Range("A24,M24").Font.Color = rgb(TEAL)

    bk.slicer([pt, pt2], "year", ws, "Year", left=10, top=40, h=110)
    states = bk.slicer(
        [pt, pt2], "customer_state", ws, "Customer state", left=10, top=160, w=390, h=170
    )
    states.NumberOfColumns = 6

    ch = bk.empty_chart(ws, bk.c.xlColumnStacked, 420, 40, 620, 290)
    ch.SetSourceData(pt.TableRange1)
    ch.ShowAllFieldButtons = False
    bk.style_chart(ch, "Revenue by month, top 8 categories (PivotChart)")
    ch.Legend.Position = bk.c.xlLegendPositionRight
    ch.Axes(bk.c.xlValue).TickLabels.NumberFormat = '"R$" #,##0,"k"'
    bk.view(ws)


def build_states(bk: Book) -> None:
    ws = bk.sheet("States", LIGHT_TEAL)
    bk.title(
        ws,
        "On-time delivery by customer state",
        "PivotTable on Data_MonthState · states with 500+ delivered orders · worst first",
        row=1,
        col=1,
    )
    cache = bk.wb.PivotCaches().Create(SourceType=bk.c.xlDatabase, SourceData="tbl_month_state")
    pt = bk.pivot(cache, ws, "A14", "pt_state")
    # Calculated fields work on SUMS, so each state's rate = its on-time orders / its orders
    pt.CalculatedFields().Add("OnTimeRate", "=on_time_orders/delivered_orders", True)
    pt.CalculatedFields().Add("LateRate", "=late_orders/delivered_orders", True)
    pt.CalculatedFields().Add("AvgReview", "=review_sum/reviews", True)

    def setup(p, fields):
        flag = p.PivotFields("state_500_plus")
        flag.Orientation = bk.c.xlPageField
        flag.CurrentPage = "yes"
        st = p.PivotFields("customer_state")
        st.Orientation = bk.c.xlRowField
        st.Caption = "Customer state"
        added = {}
        for source, caption, fmt in fields:
            df = p.AddDataField(p.PivotFields(source), caption, bk.c.xlSum)
            df.NumberFormat = fmt
            added[caption] = df
        return st, added

    st, fields = setup(
        pt,
        [
            ("delivered_orders", "Delivered orders", FMT_INT),
            ("OnTimeRate", "On-time %", FMT_PCT),
            ("LateRate", "Late rate %", FMT_PCT),
            ("AvgReview", "Avg review", FMT_STARS),
        ],
    )
    st.AutoSort(bk.c.xlAscending, "On-time %")
    bk.color_scale(fields["On-time %"].DataRange, scope_pivot=True)
    ws.Range("A11").Value = "States with 500+ delivered orders, sorted by on-time %"
    ws.Range("A11").Font.Bold = True
    ws.Range("A11").Font.Color = rgb(TEAL)

    # Second pivot on the same cache, on-time % only: the PivotChart's source
    pt2 = bk.pivot(cache, ws, "Z14", "pt_state_chart")
    st2, _ = setup(pt2, [("OnTimeRate", "On-time % ", FMT_PCT)])
    st2.AutoSort(bk.c.xlAscending, "On-time % ")
    bk.note(ws.Range("Z11"), "Chart source for the PivotChart (same data, on-time % only)")

    bk.slicer([pt, pt2], "year", ws, "Year", left=10, top=40, h=110)

    ch = bk.empty_chart(ws, bk.c.xlBarClustered, 470, 40, 430, 460)
    ch.SetSourceData(pt2.TableRange1)
    ch.ShowAllFieldButtons = False
    bk.style_chart(ch, "On-time % by state, worst first (PivotChart)", legend=False)
    ch.Axes(bk.c.xlCategory).ReversePlotOrder = True
    ch.Axes(bk.c.xlValue).TickLabels.NumberFormat = "0%"
    ch.Axes(bk.c.xlValue).MinimumScale = 0.75
    ch.Axes(bk.c.xlValue).MaximumScale = 1
    ch.SeriesCollection(1).Format.Fill.ForeColor.RGB = rgb(TEAL)
    bk.view(ws)


def build_what_if(bk: Book) -> None:
    ws = bk.sheet("What-if", CORAL)
    ws.Columns("A").ColumnWidth = 2
    ws.Columns("B").ColumnWidth = 46
    for col in "CDEFGHIJKL":
        ws.Columns(col).ColumnWidth = 12
    bk.title(
        ws,
        "What if more orders arrived on time?",
        "Estimated effect on the average review score · all delivered orders · change the yellow "
        "cells",
    )

    def total(col: str) -> str:
        return f"SUM(tbl_month_state[{col}])"

    bk.section(ws.Range("B6"), "1. Today (calculated from the data)")
    baseline = [
        (
            "wi_ontime",
            "On-time rate",
            f"=1-{total('late_orders')}/{total('delivered_orders')}",
            FMT_PCT2,
        ),
        (
            "wi_rev_on",
            "Average review, on-time orders",
            f"={total('review_sum_on_time')}/{total('reviews_on_time')}",
            FMT_STARS,
        ),
        (
            "wi_rev_late",
            "Average review, late orders",
            f"={total('review_sum_late')}/{total('reviews_late')}",
            FMT_STARS,
        ),
        (
            "wi_rev_all",
            "Average review, all orders",
            f"={total('review_sum')}/{total('reviews')}",
            FMT_STARS,
        ),
        (
            "wi_low_on",
            "1-2 star share, on-time orders",
            f"={total('low_ratings_on_time')}/{total('reviews_on_time')}",
            FMT_PCT,
        ),
        (
            "wi_low_late",
            "1-2 star share, late orders",
            f"={total('low_ratings_late')}/{total('reviews_late')}",
            FMT_PCT,
        ),
        (
            "wi_orders",
            "Delivered orders per month (2018 average)",
            "=SUMIFS(tbl_month_state[delivered_orders],tbl_month_state[year],2018)"
            "/ROWS(UNIQUE(FILTER(tbl_month_state[year_month],tbl_month_state[year]=2018)))",
            FMT_INT,
        ),
    ]
    for i, (nm, label, formula, fmt) in enumerate(baseline):
        r = 7 + i
        ws.Range(f"B{r}").Value = label
        ws.Range(f"C{r}").Formula2 = formula
        ws.Range(f"C{r}").NumberFormat = fmt
        bk.name(nm, f"='What-if'!$C${r}")

    bk.section(ws.Range("B15"), "2. Assumptions (change these)")
    ws.Range("B16").Value = "Target on-time rate"
    ws.Range("C16").Value = 0.96
    ws.Range("C16").NumberFormat = FMT_PCT
    ws.Range("B17").Value = "Share of the review gap a rescued order recovers"
    ws.Range("C17").Value = 0.5
    ws.Range("C17").NumberFormat = "0%"
    bk.input_cell(ws.Range("C16"))
    bk.input_cell(ws.Range("C17"))
    bk.note(ws.Range("D16"), "today's rate is in C7; a target below it means no change")
    bk.note(
        ws.Range("D17"),
        "100% = a late order that becomes on time gets an on-time review (upper bound); 50% = half",
    )
    bk.name("wi_target", "='What-if'!$C$16")
    bk.name("wi_recovery", "='What-if'!$C$17")

    bk.section(ws.Range("B19"), "3. Result")
    results = [
        ("Late orders turned on-time, per month", "=MAX(0,wi_target-wi_ontime)*wi_orders", FMT_INT),
        (
            "New average review (stars)",
            "=wi_rev_all+MAX(0,wi_target-wi_ontime)*wi_recovery*(wi_rev_on-wi_rev_late)",
            "0.000",
        ),
        ("Change in average review (stars)", "=C21-wi_rev_all", "+0.000;-0.000;0.000"),
        (
            "1-2 star reviews avoided, per month",
            "=C20*wi_recovery*(wi_low_late-wi_low_on)",
            FMT_INT,
        ),
    ]
    for i, (label, formula, fmt) in enumerate(results):
        r = 20 + i
        ws.Range(f"B{r}").Value = label
        ws.Range(f"C{r}").Formula = formula
        ws.Range(f"C{r}").NumberFormat = fmt
        ws.Range(f"C{r}").Font.Bold = True
    ws.Range("B20:C23").Interior.Color = rgb(PALE)

    # Sensitivity grids: real Excel What-If Data Tables (Data > What-If Analysis > Data Table)
    targets = [0.94, 0.95, 0.96, 0.97, 0.98, 0.99]
    recoveries = [0.25, 0.5, 0.75, 1.0]
    for col0, title, output, fmt in (
        (3, "Sensitivity: new average review (stars)", "=C21", "0.00"),
        (9, "Sensitivity: 1-2 star reviews avoided per month", "=C23", FMT_INT),
    ):
        ws.Range(a1(26, col0)).Value = title
        ws.Range(a1(26, col0)).Font.Bold = True
        bk.note(
            ws.Range(a1(27, col0)), "rows: target on-time rate · columns: share of gap recovered"
        )
        top = 28
        grid = ws.Range(area(top, col0, len(targets) + 1, len(recoveries) + 1))
        corner = ws.Range(a1(top, col0))
        corner.Formula = output
        corner.NumberFormat = ";;;"  # the formula Excel needs in the corner, hidden
        for j, rec in enumerate(recoveries):
            ws.Range(a1(top, col0 + 1 + j)).Value = rec
        for i, t in enumerate(targets):
            ws.Range(a1(top + 1 + i, col0)).Value = t
        grid.Table(RowInput=ws.Range("C17"), ColumnInput=ws.Range("C16"))
        ws.Range(area(top, col0 + 1, 1, len(recoveries))).NumberFormat = "0%"
        ws.Range(area(top + 1, col0, len(targets), 1)).NumberFormat = FMT_PCT
        body = ws.Range(area(top + 1, col0 + 1, len(targets), len(recoveries)))
        body.NumberFormat = fmt
        bk.header(ws.Range(area(top, col0, 1, len(recoveries) + 1)))
        bk.header(ws.Range(area(top + 1, col0, len(targets), 1)), fill=LIGHT_TEAL)
        cs = body.FormatConditions.AddColorScale(2)
        cs.ColorScaleCriteria(1).FormatColor.Color = rgb("FFFFFF")
        cs.ColorScaleCriteria(2).FormatColor.Color = rgb(HIGH)
    ws.Columns("B").ColumnWidth = 46

    bk.section(ws.Range("B37"), "How to read this, and its limits")
    notes = [
        "Method: new average = today's average + (extra on-time share) x (share of gap recovered) "
        "x (on-time review - late review).",
        "The gap is large and consistent: late orders average about 2 stars less, and the gap "
        "holds "
        "inside every state (EDA notebook), so it isn't just geography.",
        "It is still an association, not an experiment: rescued orders may differ from typical "
        "on-time ones. That is why the default recovers only 50% of the gap.",
        "Treat the 100% column as an upper bound, plan on 25-50%, and confirm with an A/B test of "
        "the delivery fix before committing budget.",
    ]
    for i, text in enumerate(notes):
        bk.note(ws.Range(f"B{38 + i}"), "• " + text)
    bk.view(ws)


def build_checks(bk: Book, expected: dict[str, float]) -> None:
    ws = bk.sheet("Checks", "7F7F7F")
    bk.title(
        ws,
        "Reconciliation checks",
        "Workbook formulas vs values computed independently with SQL (powerbi/expected_values.csv)",
        row=1,
        col=2,
    )

    def total(col: str) -> str:
        return f"SUM(tbl_month_state[{col}])"

    def in_month(col: str, m: str) -> str:
        return f'SUMIFS(tbl_month_state[{col}],tbl_month_state[year_month],"{m}")'

    def ratio(a: str, b: str) -> str:
        return f"={total(a)}/{total(b)}"

    external = [
        ("Delivered orders", f"={total('delivered_orders')}", "Delivered Orders", FMT_INT),
        ("Revenue", f"={total('revenue')}", "Revenue", FMT_MONEY2),
        ("Average order value", ratio("revenue", "delivered_orders"), "AOV", FMT_MONEY2),
        ("Late orders", f"={total('late_orders')}", "Late Orders", FMT_INT),
        (
            "On-time %",
            f"=1-{total('late_orders')}/{total('delivered_orders')}",
            "On-time %",
            FMT_PCT2,
        ),
        ("Average review", ratio("review_sum", "reviews"), "Avg Review", "0.0000"),
        (
            "Average delivery days",
            ratio("delivery_days_sum", "delivery_days_n"),
            "Avg Delivery Days",
            "0.0000",
        ),
        (
            "Review gap (on time - late)",
            f"={total('review_sum_on_time')}/{total('reviews_on_time')}"
            f"-{total('review_sum_late')}/{total('reviews_late')}",
            "Review Gap (on-time - late)",
            "0.0000",
        ),
        ("Revenue 2018-08", f"={in_month('revenue', '2018-08')}", "Revenue 2018-08", FMT_MONEY2),
        (
            "Revenue MoM % 2018-08",
            f"={in_month('revenue', '2018-08')}/{in_month('revenue', '2018-07')}-1",
            "Revenue MoM % 2018-08",
            FMT_PCT2,
        ),
        (
            "Revenue YoY % 2018-08",
            f"={in_month('revenue', '2018-08')}/{in_month('revenue', '2017-08')}-1",
            "Revenue YoY % 2018-08",
            FMT_PCT2,
        ),
        (
            "1-2 star share, on time",
            ratio("low_ratings_on_time", "reviews_on_time"),
            "Low Rating Share On Time (1-2 stars)",
            FMT_PCT2,
        ),
        (
            "1-2 star share, late",
            ratio("low_ratings_late", "reviews_late"),
            "Low Rating Share Late (1-2 stars)",
            FMT_PCT2,
        ),
        (
            "5-star share, on time",
            ratio("five_stars_on_time", "reviews_on_time"),
            "Five Star Share On Time",
            FMT_PCT2,
        ),
        (
            "5-star share, late",
            ratio("five_stars_late", "reviews_late"),
            "Five Star Share Late",
            FMT_PCT2,
        ),
    ]
    internal = [
        (
            "Category data revenue = month-state revenue",
            "=SUM(tbl_category[revenue])",
            f"={total('revenue')}",
            FMT_MONEY2,
        ),
        (
            "On-time + late reviews = all reviews",
            f"={total('reviews_on_time')}+{total('reviews_late')}",
            f"={total('reviews')}",
            FMT_INT,
        ),
        (
            "On-time + late orders = delivered orders",
            f"={total('on_time_orders')}+{total('late_orders')}",
            f"={total('delivered_orders')}",
            FMT_INT,
        ),
        (
            "Monthly sheet revenue = data for the same months (all states)",
            '=IF(sel_state="All",SUM(tbl_monthly[Revenue]),SUMIFS(tbl_month_state[revenue],'
            f'tbl_month_state[year_month],">={FIRST_MONTH}",tbl_month_state[year_month],"<={LAST_MONTH}"))',
            f'=SUMPRODUCT((tbl_month_state[year_month]>="{FIRST_MONTH}")'
            f'*(tbl_month_state[year_month]<="{LAST_MONTH}")*tbl_month_state[revenue])',
            FMT_MONEY2,
        ),
    ]
    hdr = ws.Range("B5:G5")
    hdr.Value = ("Check", "Workbook", "Expected", "Difference", "Status", "Source")
    bk.header(hdr)
    r = 6
    for label, formula, key, fmt in external:
        ws.Range(f"B{r}").Value = label
        ws.Range(f"C{r}").Formula = formula
        ws.Range(f"D{r}").Value = expected[key]
        ws.Range(f"G{r}").Value = f"SQL (expected_values.csv: {key})"
        ws.Range(f"C{r}:D{r}").NumberFormat = fmt
        r += 1
    for label, formula, exp_formula, fmt in internal:
        ws.Range(f"B{r}").Value = label
        ws.Range(f"C{r}").Formula = formula
        ws.Range(f"D{r}").Formula = exp_formula
        ws.Range(f"G{r}").Value = "internal consistency"
        ws.Range(f"C{r}:D{r}").NumberFormat = fmt
        r += 1
    last = r - 1
    ws.Range(f"E6:E{last}").Formula = "=C6-D6"
    ws.Range(f"E6:E{last}").NumberFormat = "0.000000"
    ws.Range(f"F6:F{last}").Formula = '=IF(ABS(C6-D6)<=1E-6*MAX(1,ABS(D6)),"PASS","FAIL")'
    ws.Range(f"F6:F{last}").Font.Bold = True
    ws.Range(f"F6:F{last}").HorizontalAlignment = -4108
    for status, color in (("PASS", GOOD), ("FAIL", BAD)):
        fc = ws.Range(f"F6:F{last}").FormatConditions.Add(
            Type=bk.c.xlCellValue, Operator=bk.c.xlEqual, Formula1=f'="{status}"'
        )
        fc.Font.Color = rgb(color)
    ws.Columns("A").ColumnWidth = 2
    ws.Columns("B").ColumnWidth = 54
    for col in "CDEF":
        ws.Columns(col).ColumnWidth = 16
    ws.Columns("G").ColumnWidth = 50
    bk.view(ws)

    # Status line on the Summary (written now that the Checks sheet exists)
    summary = bk.wb.Worksheets("Summary")
    cell = summary.Range("B23")
    cell.Formula = (
        f'="Data checks: "&COUNTIF(Checks!$F$6:$F${last},"PASS")&" of {last - 5} pass '
        '(see Checks sheet)"'
    )
    summary.Hyperlinks.Add(Anchor=cell, Address="", SubAddress="Checks!A1")
    cell.Font.Color = rgb(GREY)
    cell.Font.Italic = True
    cell.Font.Underline = False


# ----------------------------------------------------------------------------- main
SHEET_ORDER = [
    "Read me",
    "Summary",
    "Monthly",
    "Categories",
    "States",
    "What-if",
    "Checks",
    "Data_MonthState",
    "Data_Category",
    "Lists",
]


def main() -> int:
    import win32com.client as win32

    data = extract()
    expected = expected_values()
    months = months_between(FIRST_MONTH, LAST_MONTH)
    OUT_PATH.parent.mkdir(exist_ok=True)
    if OUT_PATH.exists():
        OUT_PATH.unlink()  # raises if the file is open in Excel: close it first

    xl = win32.gencache.EnsureDispatch("Excel.Application")
    c = win32.constants
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.ScreenUpdating = False
    try:
        bk = Book(xl, c)
        # Build order follows dependencies: names and tables exist before formulas use them
        build_readme(bk, data, months)
        build_summary_inputs(bk)
        build_data_sheets(bk, data)
        build_monthly(bk, months)
        build_summary(bk)
        build_categories(bk)
        build_states(bk)
        build_what_if(bk)
        build_checks(bk, expected)
        for prev, name in zip(SHEET_ORDER, SHEET_ORDER[1:], strict=False):
            bk.wb.Worksheets(name).Move(After=bk.wb.Worksheets(prev))
        bk.wb.Worksheets("Lists").Visible = c.xlSheetHidden
        bk.wb.RefreshAll()
        xl.CalculateFull()
        bk.wb.BuiltinDocumentProperties("Title").Value = "Olist CX monthly management report"
        bk.wb.Worksheets("Summary").Activate()
        bk.wb.SaveAs(str(OUT_PATH), FileFormat=51)  # 51 = .xlsx
        checks = bk.wb.Worksheets("Checks")
        status = [checks.Range(f"F{r}").Value for r in range(6, 40)]
        status = [s for s in status if s]
        print(
            f"Saved {OUT_PATH.relative_to(ROOT)} · checks: {status.count('PASS')} PASS, "
            f"{status.count('FAIL')} FAIL"
        )
        bk.wb.Close(SaveChanges=False)
    finally:
        xl.ScreenUpdating = True
        xl.DisplayAlerts = True
        xl.Quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
