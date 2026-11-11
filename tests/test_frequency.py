import pytest

from config.mapping import ALFRED_COLUMN_ORDER
from scripts.transform import format_frequency
from tests.conftest import build_csv, cm_row, run_transform


@pytest.mark.parametrize(
    "value, expected",
    [("1", "1x7"), ("3", "3x7"), (" 2 ", "2x7"), ("1.5", "1.5x7"),
     (0, "0x7"), ("", ""), (None, "")],
)
def test_formato(value, expected):
    assert format_frequency(value) == expected


@pytest.mark.parametrize("value", ["abc", "1x7", "-1"])
def test_frecuencia_invalida_se_reporta(value):
    rows, errors = run_transform([
        cm_row("TikTok", "CMP_1", Frequency=value),
    ])
    assert rows[0]["FREQUENCY"] == ""
    assert any("Invalid Frequency" in error for error in errors)


@pytest.mark.parametrize("platform", ["DV360", "Meta", "TikTok"])
@pytest.mark.parametrize(
    "parent, children, expected",
    [
        ("1", ["", ""], ["1x7", "1x7", "1x7"]),
        ("", ["2", "2"], ["2x7", "2x7", "2x7"]),
        ("", ["1", "2"], ["", "1x7", "2x7"]),
        ("3", ["1", "2"], ["3x7", "1x7", "2x7"]),
        ("", ["2", ""], ["2x7", "2x7", "2x7"]),
        ("", ["", ""], ["", "", ""]),
    ],
)
def test_herencia_bidireccional(platform, parent, children, expected):
    rows, _ = run_transform([
        cm_row(platform, "CMP_1", Frequency=parent),
        cm_row(platform, "CMP_1 -> ADG1_a", Frequency=children[0]),
        cm_row(platform, "CMP_1 -> ADG2_a", Frequency=children[1]),
    ])
    real_rows = [row for row in rows if row["LEVEL"] in ["Campaign", "Ad Group"]]
    assert [row["FREQUENCY"] for row in real_rows] == expected


@pytest.mark.parametrize("second", ["2", "3"])
def test_padres_generados_dv360_respetan_consenso(second):
    rows, _ = run_transform([
        cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG1_a", Frequency="2"),
        cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG2_a", Frequency=second),
    ])
    assert [row["FREQUENCY"] for row in rows[:3]] == (["2x7"] * 3 if second == "2" else [""] * 3)
    assert [row["FREQUENCY"] for row in rows[3:]] == ["2x7", f"{second}x7"]


def test_ancestro_mas_cercano_sin_contaminar_otras_ramas():
    rows, _ = run_transform([
        cm_row("DV360", "CMP_1", Frequency="1"),
        cm_row("DV360", "CMP_1 -> IO1_a", Frequency="2"),
        cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a", Frequency=""),
        cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG1_a", Frequency=""),
        cm_row("DV360", "CMP_1 -> IO2_a", Frequency=""),
        cm_row("DV360", "CMP_1 -> IO2_a -> LI2_a", Frequency=""),
        cm_row("DV360", "CMP_1 -> IO2_a -> LI2_a -> ADG2_a", Frequency=""),
        cm_row("TikTok", "CMP_2", Frequency=""),
    ])
    assert [row["FREQUENCY"] for row in rows] == [
        "1x7", "2x7", "2x7", "2x7", "1x7", "1x7", "1x7", "",
    ]


def test_distinta_frecuencia_no_se_deduplica():
    rows, _ = run_transform([
        cm_row("TikTok", "CMP_1", Frequency="1"),
        cm_row("TikTok", "CMP_1", Frequency="2"),
    ])
    assert [row["FREQUENCY"] for row in rows] == ["1x7", "2x7"]


def test_excel_frecuencia_como_texto_y_vacio_editable(excel_from):
    _, wb = excel_from(build_csv([
        cm_row("TikTok", "CMP_1", Frequency="1"),
        cm_row("TikTok", "CMP_2", Frequency=""),
    ]))
    ws = wb["ALFRED"]
    column = ALFRED_COLUMN_ORDER.index("FREQUENCY") + 1
    filled, empty = ws.cell(2, column), ws.cell(3, column)
    assert filled.value == "1x7"
    assert filled.data_type == "s"
    assert filled.fill.fgColor.rgb != "00FFF2CC"
    assert empty.value is None
    assert empty.fill.fgColor.rgb == "00FFF2CC"
