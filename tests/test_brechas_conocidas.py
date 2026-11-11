"""Known gaps: these tests describe the desired behavior and fail today (xfail).

When a gap is fixed, the test passes, pytest reports XPASS and strict=True
fails the run: remove the xfail mark at that point.
"""
import pytest

from scripts.transform import clean_currency, extract_country_from_filename, parse_csv, parse_date, run
from tests.conftest import cm_row, run_transform, build_csv


@pytest.mark.xfail(strict=True, reason="Hallazgo 8: CSV con BOM pierde la columna Platform")
def test_csv_con_bom():
    rows = parse_csv("\ufeff" + build_csv([cm_row("Meta", "Hair Care -> CMP_1")]))
    assert rows[0]["Platform"] == "Meta"


@pytest.mark.xfail(strict=True, reason="Hallazgo 8: separador ';' no soportado")
def test_csv_con_punto_y_coma():
    csv_text = build_csv([cm_row("Meta", "Hair Care -> CMP_1")]).replace(",", ";")
    assert run(csv_text, "Plan_MX.csv")["row_count"] == 1


@pytest.mark.xfail(strict=True, reason="Hallazgo 5: formatos de fecha no soportados")
@pytest.mark.parametrize("value", ["2026-01-15 00:00:00", "15-Jan-2026", "Jan 15, 2026"])
def test_fechas_adicionales(value):
    assert parse_date(value) == (15, 1, 2026)


@pytest.mark.xfail(strict=True, reason="Hallazgo 4: '1,234' se interpreta como 1.234 (formato europeo)")
def test_miles_con_coma_sin_decimales():
    assert clean_currency("1,234") == 1234.0


def test_pais_no_se_confunde_con_palabras():
    assert extract_country_from_filename("Campaign_GT.csv") == "GT"


def test_archivo_sin_pais_no_asigna_el_salvador():
    assert extract_country_from_filename("export.csv") == ""


@pytest.mark.xfail(strict=True, reason="Hallazgo 6: el error cita la fila del output, no la del CSV de CM")
def test_error_cita_fila_del_csv_de_cm():
    rows = [cm_row("Snapchat", "Hair Care -> CMP_X"),
            cm_row("Pinterest", "Hair Care -> CMP_1", Brand="")]
    _, errors = run_transform(rows)
    assert [e for e in errors if "BRAND" in e] == ["Row 2: Missing mandatory field 'BRAND'"]


@pytest.mark.xfail(strict=True, reason="Hallazgo 7: mensajes de error en ingles")
def test_mensajes_en_espanol():
    _, errors = run_transform([cm_row("Pinterest", "Hair Care -> CMP_1", Brand="")])
    assert all("Missing" not in e for e in errors)


@pytest.mark.xfail(strict=True, reason="Excel limita las listas de validacion a 255 caracteres; BID_TYPE las excede")
def test_dropdowns_dentro_del_limite_de_excel(excel_from):
    from tests.conftest import load_fixture

    _, wb = excel_from(load_fixture("dv360_completo.csv"))
    for dv in wb["ALFRED"].data_validations.dataValidation:
        formula = str(dv.formula1)
        if formula.startswith('"'):
            assert len(formula) - 2 <= 255, formula[:60]
