"""ALFRED Excel output tests."""
from config.mapping import ALFRED_COLUMN_ORDER
from tests.conftest import load_fixture


def validations_by_column(ws):
    result = {}
    for dv in ws.data_validations.dataValidation:
        for cell_range in dv.sqref.ranges:
            column = "".join(ch for ch in cell_range.coord.split(":")[0] if ch.isalpha())
            result.setdefault(column, []).append(dv.formula1)
    return result


def column_letter(name):
    from openpyxl.utils import get_column_letter
    return get_column_letter(ALFRED_COLUMN_ORDER.index(name) + 1)


def test_encabezados_exactos_en_orden(excel_from):
    _, wb = excel_from(load_fixture("tiktok_ids.csv"))
    ws = wb["ALFRED"]
    assert len(ALFRED_COLUMN_ORDER) == 61
    assert [c.value for c in ws[1]] == ALFRED_COLUMN_ORDER


def test_una_fila_por_registro(excel_from):
    result, wb = excel_from(load_fixture("tiktok_ids.csv"))
    assert wb["ALFRED"].max_row == result["row_count"] + 1


def test_valores_en_celdas(excel_from):
    _, wb = excel_from(load_fixture("tiktok_ids.csv"))
    ws = wb["ALFRED"]
    header = [c.value for c in ws[1]]
    row = {header[i]: c.value for i, c in enumerate(ws[2])}
    assert row["ID"] == "TK1"
    assert row["COUNTRY"] == "MX"
    assert row["PLATFORM"] == "TikTok"
    assert isinstance(row["BUDGET"], (int, float)), "Los montos deben ser numericos"


def test_hoja_errores_solo_si_hay_errores(excel_from):
    _, wb_ok = excel_from(load_fixture("tiktok_ids.csv"))
    assert "Errores" not in wb_ok.sheetnames

    result, wb_err = excel_from(load_fixture("dv360_io_huerfanos.csv"))
    assert "Errores" in wb_err.sheetnames
    ws = wb_err["Errores"]
    assert [r[0] for r in ws.iter_rows(min_row=2, values_only=True)] == result["errors"]


def test_dropdowns_principales(excel_from):
    _, wb = excel_from(load_fixture("dv360_completo.csv"))
    validations = validations_by_column(wb["ALFRED"])
    expected = {
        "STATUS": '"ON,OFF"',
        "STAGE": '"Awareness,Consideration,Conversion"',
        "IMP_STATUS": '"Implemented,Pending,Manual Imp."',
        "AUTOBIDDERS": '"No,Yes"',
        "PRICING_MODEL": '"CPM,CPV,CPC,CPA,CPL"',
        "PACING": '"Flight_Ahead,Flight_Even,Daily_Asap,Daily_Even"',
    }
    for field, formula in expected.items():
        assert formula in validations.get(column_letter(field), []), field


def test_dropdown_type_por_fila(excel_from):
    _, wb = excel_from(load_fixture("dv360_completo.csv"))
    formulas = validations_by_column(wb["ALFRED"]).get(column_letter("TYPE"), [])
    assert len(formulas) == 6


def test_sin_named_ranges_ni_indirect(excel_from):
    """NamedRange and INDIRECT broke the Excel in Pyodide/openpyxl."""
    _, wb = excel_from(load_fixture("dv360_completo.csv"))
    assert len(wb.defined_names) == 0
    for ws in wb.worksheets:
        for dv in ws.data_validations.dataValidation:
            assert "INDIRECT" not in str(dv.formula1).upper()


def test_mas_de_26_columnas_usan_letras_dobles(excel_from):
    _, wb = excel_from(load_fixture("tiktok_ids.csv"))
    ws = wb["ALFRED"]
    assert ws["BI1"].value == ALFRED_COLUMN_ORDER[-1]
