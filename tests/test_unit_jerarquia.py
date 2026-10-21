"""Unit tests: CSV parsing, level/TYPE inference and IDs."""
import pytest

from scripts.transform import (
    determine_level_dv360,
    determine_level_two_tier,
    generate_ids,
    get_bid_type_options_for_row,
    infer_type,
    normalize_bid_type_key,
    parse_csv,
)


class TestParseCsv:
    def test_vacio(self):
        assert parse_csv("") == []
        assert parse_csv(None) == []
        assert parse_csv("\n , \n") == []

    def test_solo_encabezado(self):
        assert parse_csv("Platform,Line Item\n") == []

    def test_fila_decorativa_y_plan_level(self):
        rows = parse_csv("Reporte CM\nPlatform,Line Item,Plan level\nMeta,a,true\n")
        assert rows == [{"Platform": "Meta", "Line Item": "a", "Plan Level": "true"}]

    def test_encabezado_duplicado_conserva_primer_no_vacio(self):
        rows = parse_csv("Platform,Publisher,Publisher\nMeta,,Facebook\n")
        assert rows[0]["Publisher"] == "Facebook"

    def test_fila_corta_se_completa(self):
        rows = parse_csv("Platform,Line Item,Brand\nMeta,a\n")
        assert rows[0]["Brand"] == ""

    def test_comas_dentro_de_comillas(self):
        rows = parse_csv('Platform,Line Item\nMeta,"a, b"\n')
        assert rows[0]["Line Item"] == "a, b"


class TestNiveles:
    @pytest.mark.parametrize(
        "line_item, level",
        [
            ("Oral Care -> CMP_1", "Campaign"),
            ("Oral Care -> IO1_A", "Insertion Order"),
            ("Oral Care -> IO1_A -> LI1_B", "Line Item"),
            ("Oral Care -> IO1_A -> LI1_B -> ADG1_C", "Ad Group"),
            ("Solo texto sin codigo", None),
            ("", None),
        ],
    )
    def test_dv360(self, line_item, level):
        assert determine_level_dv360(line_item)[0] == level

    @pytest.mark.parametrize(
        "line_item, level",
        [("Hair Care -> CMP_1", "Campaign"),
         ("Hair Care -> CMP_1 -> ADG1_a", "Ad Group"),
         ("Hair Care", None)],
    )
    def test_dos_niveles(self, line_item, level):
        assert determine_level_two_tier(line_item) == level


class TestInferType:
    def test_nonskip_antes_que_skip(self):
        row = {"Line Item": "Oral Care -> IO1_A -> LI1_NonSkip"}
        assert infer_type("DV360", "Line Item", row) == "Non-Skip"

    def test_skip(self):
        row = {"Line Item": "Oral Care -> IO1_A -> LI1_Skip"}
        assert infer_type("DV360", "Line Item", row) == "Skip"

    @pytest.mark.parametrize("ou, expected", [("DV360 YT", "Youtube"), ("DV360 Programmatic", "Programmatic")])
    def test_io_por_ou_planning_level(self, ou, expected):
        row = {"Line Item": "x -> IO1_A", "OU Planning Level": ou}
        assert infer_type("DV360", "Insertion Order", row) == expected

    def test_opcion_unica(self):
        assert infer_type("Meta", "Campaign", {}) == "Meta"

    def test_fallback_na(self):
        assert infer_type("TikTok", "Ad Group", {"Line Item": "x"}) == "NA"

    def test_sin_inferencia(self):
        assert infer_type("DV360", "Line Item", {"Line Item": "x"}) == ""

    def test_plataforma_sin_opciones(self):
        assert infer_type("Snapchat", "Campaign", {}) == ""


class TestBidType:
    @pytest.mark.parametrize(
        "value, key",
        [("VV", "Video Views"), ("Video Views", "Video Views"), ("Non-Skip", "Non_Skip"),
         ("Skip", "Skip"), ("PMP Non Guaranteed", "PMP_Non_Guaranteed"), ("otro", "")],
    )
    def test_normalize_key(self, value, key):
        assert normalize_bid_type_key(value) == key

    def test_opciones_por_fila(self):
        assert get_bid_type_options_for_row({"PLATFORM": "DV360", "TYPE": "Skip"}) == ["Fixed"]
        assert get_bid_type_options_for_row({"PLATFORM": "TikTok", "CAMPAIGN_GOAL": "Reach"}) == ["Reach"]
        assert get_bid_type_options_for_row({"PLATFORM": "Pinterest", "TYPE": "NA"}) == []
        assert get_bid_type_options_for_row({}) == []


class TestGenerateIds:
    def test_contador_se_reinicia_por_padre(self):
        rows = [
            (0, {"PLATFORM": "TikTok", "_code_parts": ["C1"]}),
            (1, {"PLATFORM": "TikTok", "_code_parts": ["C1", "A1"]}),
            (2, {"PLATFORM": "TikTok", "_code_parts": ["C2"]}),
            (3, {"PLATFORM": "TikTok", "_code_parts": ["C2", "A1"]}),
            (4, {"PLATFORM": "TikTok", "_code_parts": ["C2", "A2"]}),
        ]
        assert generate_ids(rows) == {0: "TK1", 1: "TK1-1", 2: "TK2", 3: "TK2-1", 4: "TK2-2"}

    def test_prefijos_por_plataforma(self):
        rows = [(i, {"PLATFORM": p, "_code_parts": ["C"]})
                for i, p in enumerate(["DV360", "Meta", "TikTok", "Pinterest", "Google Ads", "Amazon Prime"])]
        assert list(generate_ids(rows).values()) == ["DV1", "M1", "TK1", "P1", "S1", "A1"]

    def test_fila_sin_codigo_no_recibe_id(self):
        assert generate_ids([(0, {"PLATFORM": "Meta", "_code_parts": []})]) == {}
