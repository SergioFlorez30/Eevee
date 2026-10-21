"""Generate uat/Eevee_UAT.xlsx and the UAT test data (uat/test-data/*.csv).

Mirrors the format of the CM UAT ("UAT CM.xlsx"): HOME sheet with summary,
one sheet per Key User with Test Type / ID / Scenario / Action / Expected
Result / Real Result / Test Result, and per-category scores.

Usage:  python uat/build_uat.py
"""
import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

UAT_DIR = Path(__file__).resolve().parent
DATA_DIR = UAT_DIR / "test-data"
FIXTURES = UAT_DIR.parent / "tests" / "fixtures"

KEY_USERS = [("PLANNER_TEST", "Planner"), ("TRADER_TEST", "Trader"), ("DIGITAL_EXPERT_TEST", "Digital Expert")]

D = "Data Validation"
T = "Tool Functionality"
W = "Workflow/Integration Verification"
CATEGORIES = [D, T, W]

NAVY = "FF002060"
TITLE_BLUE = "FF0F4761"
YELLOW = "FFFFFF00"
FONT = "Aptos Narrow"

# (test type, id, scenario, action, expected result)
SCENARIOS = [
    (D, "1.1", "Validate Required Fields",
     "Upload UAT_MX_01_tiktok_completo.csv in Eevee and download the Excel.",
     "All ALFRED mandatory fields are populated (COUNTRY, SUB_SECTOR, BRAND, SUB_BRAND, INITIATIVE, CAMPAIGN_TAXO, LEVEL, ID, PLATFORM, TYPE, "
     "START/END DAY-MONTH-YEAR, BUDGET, TOTAL_BUDGET, GENDER, AGE_RANGE, MONTH, STAGE, PRICE_TYPE, PRICING_MODEL, BUY_TYPE, REGION, AUDIENCE). "
     "No 'Errores' sheet is created. 5 rows are generated."),
    (D, "1.2", "Validate Missing Mandatory Fields",
     "Upload UAT_MX_02_campos_faltantes.csv (rows without Target Audience, valid Media Objective, Cost Type, Brand, valid Start Date or Billable Budget).",
     "10 errors are reported with their row: Row 1 GENDER + AGE_RANGE, Row 2 STAGE, Row 3 PRICING_MODEL, Row 4 BRAND, "
     "Row 5 START_DAY + START_MONTH + START_YEAR + MONTH, Row 6 BUDGET. They also appear in the 'Errores' sheet and the Excel can still be downloaded."),
    (D, "1.3", "Validate Manual Fields",
     "Upload UAT_MX_06_multiplataforma_dv360_meta.csv and review the preview and the Excel.",
     "CAMPAIGN_GOAL, PO, FREQUENCY, STATUS, IMP_STATUS and BID_TYPE_OPTIMIZATION_TYPE (all platforms), BID_VALUE/KPI_VALUE (DV360 except Campaign), "
     "BID_VALUE (TikTok) and BUDGET_TYPE (Meta/TikTok) are empty for the user to fill, are highlighted as manual in the preview and are NOT reported as errors."),
    (D, "1.4", "Date Transformation",
     "Upload UAT_MX_03_casteo_valores.csv (dates in dd/mm/yyyy and yyyy-mm-dd).",
     "START_DAY/START_MONTH/START_YEAR and END_DAY/END_MONTH/END_YEAR are numeric and keep the same date as CM. "
     "MONTH shows the ALFRED code of the start month (SEP)."),
    (D, "1.5", "Budget Transformation",
     "Upload UAT_MX_03_casteo_valores.csv (budgets as $1,234.50 and 1.500,25; Allocated Coupons (Planned) = 25).",
     "BUDGET = 1234.5 and TOTAL_BUDGET = 1500.25 as numbers (not text). BONO = 25 (Allocated Coupons (Planned)). "
     "The amount never changes, only its format."),
    (D, "1.6", "Audience & Stage Transformation",
     "Upload UAT_MX_03_casteo_valores.csv and check GENDER, AGE_RANGE and STAGE.",
     "M_25-44 -> GENDER = Male, AGE_RANGE = 25-44. P_18-65 -> People, 18-65. W_ -> Female. "
     "Media Objective -> STAGE (Consideration, Conversion)."),
    (D, "1.7", "Country from File Name",
     "Upload any test file whose name contains MX. Then upload a copy renamed without a country code (e.g. Plan_test.csv).",
     "With MX in the name, COUNTRY = MX in every row. Without a country code, COUNTRY is empty and reported as an error "
     "(Eevee must never assign a different country)."),
    (D, "1.8", "Fixed & Default Values",
     "Upload UAT_MX_01_tiktok_completo.csv and UAT_MX_04_dv360_completo.csv.",
     "BUY_TYPE = Auction, IRA_VERSION = V1, REGION = National, AUDIENCE = Demo, BROADCAST = NA in all rows. "
     "PACING = Daily_Even in DV360. AUTOBIDDERS = No by default."),
    (D, "1.9", "Platform Normalization",
     "Upload UAT_MX_07_meta_campaign_duplicada.csv (Platform = Facebook).",
     "PLATFORM = Meta in all rows (Facebook / Instagram / Messenger are mapped to Meta). IDs use the prefix M."),
    (D, "1.10", "DV360 Hierarchy Completion",
     "Upload UAT_MX_04_dv360_completo.csv (Line Items without Campaign, IO or Ad Group rows).",
     "Eevee builds Campaign -> Insertion Order -> Line Item -> Ad Group: DV1, DV1-1, DV1-1-1, DV1-1-1-1, DV1-1-2, DV1-1-2-1. "
     "Generated Ad Groups inherit the LI data with BUDGET, TOTAL_BUDGET and BONO = 0. Generated Campaign/IO/Ad Group rows have empty "
     "CAMPAIGN_TAXO (to be completed by the user; reported as error, download still allowed)."),
    (D, "1.11", "DV360 Orphan IOs",
     "Upload UAT_MX_05_dv360_io_huerfanos.csv (2 IOs without Campaign).",
     "Only ONE Campaign is generated for both IOs. Its BUDGET (300), TOTAL_BUDGET (300) and BONO (7) are the sum of its direct children. "
     "Each IO gets its LI and Ad Group (DV1-1-1-1, DV1-2-1-1). LIs whose name has no known format keep TYPE empty and are reported."),
    (D, "1.12", "Duplicate IO / LI Rows",
     "Upload UAT_MX_08_dv360_li_repetido.csv (same IO and LI repeated twice).",
     "Both Line Items keep their own Ad Group (DV1-1-1-1 and DV1-1-2-1). No ID is duplicated and no row is lost."),
    (D, "1.13", "Duplicate Campaign Cleanup",
     "Upload UAT_MX_07_meta_campaign_duplicada.csv (Campaign M1 repeated, one copy without children; Campaign M2 alone).",
     "The duplicate Campaign without children is removed. Result: M1, M1-1, M2. A unique Campaign without children (M2) is kept."),
    (D, "1.14", "ID Generation",
     "Upload UAT_MX_01_tiktok_completo.csv and UAT_MX_09_multiplataforma.csv.",
     "TikTok IDs: TK1, TK1-1, TK2, TK2-1, TK2-2 (counter restarts per parent). Prefixes: DV360 = DV, Meta = M, TikTok = TK, "
     "Pinterest = P, Google Ads = S, Amazon Prime = A. No duplicated IDs."),
    (D, "1.15", "TYPE Inference",
     "Upload UAT_MX_06_multiplataforma_dv360_meta.csv.",
     "DV360 IO = Youtube or Programmatic according to OU Planning Level. LI = Non-Skip / Bumper / OX Display according to the Line Item name "
     "(Non-Skip is never read as Skip). Meta Campaign = Meta, Meta Ad Group = NA."),
    (D, "1.16", "Multi-platform File",
     "Upload UAT_MX_09_multiplataforma.csv (Pinterest, Google Ads, Amazon Prime).",
     "Each platform keeps its own hierarchy and IDs (P1, P1-1, S1, S1-1, A1, A1-1). No errors. "
     "BUDGET_TYPE, PACING, BID_VALUE and KPI_VALUE are not required for these platforms."),
    (T, "2.1", "Tool Loading",
     "Open the Eevee URL in Edge or Chrome on the P&G network.",
     "The page loads and shows 'Motor Python listo' without errors. Write the loading time in Real Result."),
    (T, "2.2", "Upload CSV",
     "Upload a CSV with drag & drop and again with the file selector.",
     "Both methods work. File name and size are displayed and processing starts automatically."),
    (T, "2.3", "Reject Non-CSV Files",
     "Try to upload an .xlsx (CM export without conversion) and a .txt file.",
     "Eevee shows 'Por favor selecciona un archivo .csv' and does not process the file."),
    (T, "2.4", "Preview",
     "Upload UAT_MX_04_dv360_completo.csv and review the preview.",
     "The preview shows the first rows with ALFRED columns, manual fields are highlighted and the total row count is correct (6 rows)."),
    (T, "2.5", "Download Excel",
     "Click the download button after processing UAT_MX_01_tiktok_completo.csv.",
     "File ALFRED_UAT_MX_01_tiktok_completo.xlsx is downloaded with the 'ALFRED' sheet and the 61 columns in ALFRED order."),
    (T, "2.6", "Replace File / Reset",
     "Process one file and then upload a different one (or reset).",
     "Preview, row count, errors and download correspond only to the last file. No data from the previous file remains."),
    (T, "2.7", "Empty or Unrecognized File",
     "Upload UAT_MX_10_vacio.csv (header only) and a CSV that is not a CM export.",
     "Eevee does not freeze or crash and clearly informs that no rows could be transformed."),
    (T, "2.8", "Special Characters",
     "Upload UAT_MX_11_caracteres_especiales.csv (accents, ñ, apostrophe and backslash). Also upload a copy whose file name has an apostrophe.",
     "The file is processed and texts keep exactly the same characters as CM (Niño's, Línea\\A Ñandú)."),
    (T, "2.9", "Large File",
     "Upload UAT_MX_12_volumen_5000_filas.csv.",
     "5,000 rows are processed without freezing the browser. Write the processing time in Real Result."),
    (T, "2.10", "Error Visibility",
     "Upload UAT_MX_02_campos_faltantes.csv.",
     "Errors are visible on screen in Spanish with the row and the missing field, and are also listed in the 'Errores' sheet of the Excel."),
    (W, "3.1", "Excel Integrity",
     "Open the Excel downloaded from UAT_MX_06_multiplataforma_dv360_meta.csv in desktop Excel.",
     "The file opens without the 'We found a problem with some content... repair' message."),
    (W, "3.2", "Excel Dropdowns",
     "In the downloaded Excel open the dropdowns of STATUS, IMP_STATUS, STAGE, TYPE, PACING, BUDGET_TYPE, AUTOBIDDERS, CAMPAIGN_GOAL, "
     "PRICING_MODEL and BID_TYPE_OPTIMIZATION_TYPE.",
     "Each dropdown shows only valid ALFRED options for the row (TYPE per platform/level, CAMPAIGN_GOAL per STAGE, PACING only DV360, "
     "BUDGET_TYPE only Meta/TikTok, AUTOBIDDERS Yes/No)."),
    (W, "3.3", "ALFRED Upload",
     "Transform a real CM export of your market, complete the manual fields in the Excel and upload it to ALFRED.",
     "ALFRED accepts the file without rejections or format errors."),
    (W, "3.4", "Data Consistency CM vs ALFRED",
     "Compare 5 random rows of the real CM export against ALFRED after the upload (budget, dates, brand, initiative, hierarchy).",
     "Values are identical to CM (only the format changes). Parent Campaign totals match the sum of their direct children."),
    (W, "3.5", "End-to-End Time",
     "Measure the time from the CM export to the file ready to upload in ALFRED using Eevee.",
     "Time is 30 minutes or less (baseline: 2 hours manual). Write the measured time in Real Result."),
]


def write_test_data():
    """Create the CSV files referenced by the UAT scenarios."""
    DATA_DIR.mkdir(exist_ok=True)
    header = (FIXTURES / "tiktok_ids.csv").read_text(encoding="utf-8").splitlines()[0].split(",")

    def row(platform, line_item, **overrides):
        values = {
            "Platform": platform, "Line Item": line_item, "Start Date": "01/09/2026", "End Date": "30/09/2026",
            "Brand": "Pantene", "Sub Brand": "Pro-V", "Total Budget": "1000", "Billable Budget": "1000",
            "Target Audience": "W_18-34", "Media Objective": "Awareness", "Initiative": "Launch",
            "Cost Type": "CPM", "Publisher": "", "Allocated Coupons (Planned)": "0", "OU Planning Level": "",
        }
        values.update(overrides)
        return values

    def write(name, rows):
        with open(DATA_DIR / name, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)

    copies = {
        "UAT_MX_01_tiktok_completo.csv": "tiktok_ids.csv",
        "UAT_MX_04_dv360_completo.csv": "dv360_completo.csv",
        "UAT_MX_05_dv360_io_huerfanos.csv": "dv360_io_huerfanos.csv",
        "UAT_MX_07_meta_campaign_duplicada.csv": "meta_campaign_duplicada.csv",
        "UAT_MX_08_dv360_li_repetido.csv": "dv360_io_li_repetido.csv",
        "UAT_MX_09_multiplataforma.csv": "multiplataforma.csv",
    }
    for target, source in copies.items():
        (DATA_DIR / target).write_bytes((FIXTURES / source).read_bytes())

    write("UAT_MX_02_campos_faltantes.csv", [
        row("Pinterest", "Hair Care -> CMP_1", **{"Target Audience": ""}),
        row("Pinterest", "Hair Care -> CMP_2", **{"Media Objective": "Otro"}),
        row("Pinterest", "Hair Care -> CMP_3", **{"Cost Type": "N/A"}),
        row("Pinterest", "Hair Care -> CMP_4", Brand=""),
        row("Pinterest", "Hair Care -> CMP_5", **{"Start Date": "fecha"}),
        row("Pinterest", "Hair Care -> CMP_6", **{"Billable Budget": "N/A"}),
    ])
    write("UAT_MX_03_casteo_valores.csv", [
        row("TikTok", "Hair Care -> CMP_1", **{
            "Start Date": "2026-09-05", "End Date": "30/09/2026", "Billable Budget": "$1,234.50",
            "Total Budget": "1.500,25", "Target Audience": "M_25-44", "Media Objective": "Consideration",
            "Allocated Coupons (Planned)": "25"}),
        row("TikTok", "Hair Care -> CMP_1 -> ADG1_a", **{
            "Start Date": "05/09/2026", "End Date": "2026-09-30", "Billable Budget": "1234.5",
            "Total Budget": "1500.25", "Target Audience": "P_18-65", "Media Objective": "Conversion"}),
    ])
    write("UAT_MX_06_multiplataforma_dv360_meta.csv", [
        row("DV360", "Hair Care Launch -> IO1_YT -> LI1_NonSkip", **{"OU Planning Level": "DV360 YT"}),
        row("DV360", "Hair Care Launch -> IO1_YT -> LI2_Bumper", **{"OU Planning Level": "DV360 YT"}),
        row("DV360", "Hair Care Launch -> IO2_PG -> LI1_OX_Display", **{"OU Planning Level": "DV360 Programmatic"}),
        row("Meta", "Hair Care -> CMP_M1"),
        row("Meta", "Hair Care -> CMP_M1 -> ADG1_a"),
        row("TikTok", "Hair Care -> CMP_T1"),
        row("TikTok", "Hair Care -> CMP_T1 -> ADG1_a"),
    ])
    write("UAT_MX_10_vacio.csv", [])
    write("UAT_MX_11_caracteres_especiales.csv", [
        row("Meta", "Hair Care -> CMP_1", Brand="Niño's", Initiative="Línea\\A Ñandú"),
        row("Meta", "Hair Care -> CMP_1 -> ADG1_a", Brand="Niño's", Initiative="Línea\\A Ñandú"),
    ])
    big = []
    for c in range(1, 201):
        big.append(row("TikTok", f"Hair Care -> CMP_{c}"))
        big.extend(row("TikTok", f"Hair Care -> CMP_{c} -> ADG{a}_x") for a in range(1, 25))
    write("UAT_MX_12_volumen_5000_filas.csv", big)


def style_header(cell):
    cell.font = Font(name=FONT, bold=True, color="FFFFFFFF")
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(vertical="center", wrap_text=True)


def build_user_sheet(wb, title, role):
    ws = wb.create_sheet(title)
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    category_fill = PatternFill("solid", fgColor="FFDDEBF7")

    for r, label in enumerate(["Key User", "Market / Brand", "CM File Used", "Test Date"], start=1):
        cell = ws.cell(r, 1, label)
        cell.fill = PatternFill("solid", fgColor=YELLOW)
        cell.font = Font(name=FONT, bold=True)
    ws["B1"] = role

    header_row = 6
    headers = ["Test Type", "ID", "Scenario Name", "Action", "Expected Result",
               "Real Result (if fail)", "Test Result", "Comments"]
    for col, text in enumerate(headers, start=1):
        style_header(ws.cell(header_row, col, text))

    first = header_row + 1
    ranges = {}
    for offset, (ttype, sid, name, action, expected) in enumerate(SCENARIOS):
        r = first + offset
        for col, value in enumerate([ttype, sid, name, action, expected, None, None, None], start=1):
            cell = ws.cell(r, col, value)
            cell.font = Font(name=FONT)
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(r, 1).fill = category_fill
        ws.cell(r, 2).number_format = "@"
        ranges.setdefault(ttype, [r, r])[1] = r
    last = first + len(SCENARIOS) - 1

    dv = DataValidation(type="list", formula1="HOME!$S$1:$S$2", allow_blank=True)
    dv.add(f"G{first}:G{last}")
    ws.add_data_validation(dv)
    ws.conditional_formatting.add(f"G{first}:G{last}", CellIsRule(
        operator="equal", formula=['"pass"'], fill=PatternFill("solid", fgColor="FFC6EFCE"), font=Font(color="FF006100")))
    ws.conditional_formatting.add(f"G{first}:G{last}", CellIsRule(
        operator="equal", formula=['"fail"'], fill=PatternFill("solid", fgColor="FFFFC7CE"), font=Font(color="FF9C0006")))

    summary_row = last + 3
    score_cells = {}
    for i, category in enumerate(CATEGORIES):
        start, end = ranges[category]
        r = summary_row + i
        ws.cell(r, 6, category).font = Font(name=FONT)
        cell = ws.cell(r, 7, f'=COUNTIF($G${start}:$G${end},"pass")/{end - start + 1}')
        cell.number_format = "0%"
        score_cells[category] = f"G{r}"
    r = summary_row + len(CATEGORIES)
    ws.cell(r, 6, "SCORE")
    ws.cell(r, 7, f'=COUNTIF($G${first}:$G${last},"pass")/{len(SCENARIOS)}').number_format = "0%"
    for col in (6, 7):
        style_header(ws.cell(r, col))
    score_cells["SCORE"] = f"G{r}"

    for col, width in zip("ABCDEFGH", [18.4, 6, 26, 70.4, 72.4, 30, 14, 40]):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = f"A{first}"
    return score_cells


def build_workbook():
    wb = Workbook()
    home = wb.active
    home.title = "HOME"
    home["A1"] = "Test Scenarios Eevee (CM → ALFRED)"
    home["A1"].font = Font(name="Aptos Display", size=20, color=TITLE_BLUE)
    home.merge_cells("A1:G1")
    home.row_dimensions[1].height = 38.1
    home["S1"], home["S2"] = "pass", "fail"

    home["A3"] = ("How to use: each Key User fills in their sheet. Run each Action with the files in uat/test-data, "
                  "compare against the Expected Result, select pass/fail in Test Result and describe the Real Result when it fails.")
    home["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    home.merge_cells("A3:G4")
    home.row_dimensions[3].height = 30

    user_scores = [build_user_sheet(wb, title, role) for title, role in KEY_USERS]

    header_row = 7
    style_header(home.cell(header_row, 1, "TEST RESULTS"))
    for col, (_, role) in enumerate(KEY_USERS, start=2):
        style_header(home.cell(header_row, col, role))
    avg_col = len(KEY_USERS) + 2
    style_header(home.cell(header_row, avg_col, "Average"))

    first_letter, last_letter = get_column_letter(2), get_column_letter(avg_col - 1)
    for i, category in enumerate(CATEGORIES + ["SCORE"]):
        r = header_row + 1 + i
        home.cell(r, 1, category)
        for col, ((sheet, _), cells) in enumerate(zip(KEY_USERS, user_scores), start=2):
            home.cell(r, col, f"='{sheet}'!{cells[category]}").number_format = "0%"
        home.cell(r, avg_col, f"=AVERAGE({first_letter}{r}:{last_letter}{r})").number_format = "0%"
        if category == "SCORE":
            for col in range(1, avg_col + 1):
                home.cell(r, col).font = Font(name=FONT, bold=True)

    home.column_dimensions["A"].width = 34
    for col in range(2, avg_col + 1):
        home.column_dimensions[get_column_letter(col)].width = 18
    home.column_dimensions["S"].hidden = True

    wb.save(UAT_DIR / "Eevee_UAT.xlsx")


if __name__ == "__main__":
    write_test_data()
    build_workbook()
    print(f"UAT generated: {UAT_DIR / 'Eevee_UAT.xlsx'} ({len(SCENARIOS)} scenarios)")
