"""Unit tests: CM value normalization into ALFRED format."""
import pytest

from scripts.transform import (
    clean_currency,
    extract_age_range,
    extract_country_from_filename,
    extract_gender,
    extract_sub_sector,
    normalize_platform,
    normalize_stage,
    parse_date,
    resolve_pricing_model,
)


class TestParseDate:
    @pytest.mark.parametrize("value", ["2026-01-15", "15/01/2026"])
    def test_formatos_soportados(self, value):
        assert parse_date(value) == (15, 1, 2026)

    def test_fecha_ambigua_se_interpreta_dd_mm(self):
        assert parse_date("03/04/2026") == (3, 4, 2026)

    def test_mm_dd_cuando_dia_mayor_a_12(self):
        assert parse_date("01/31/2026") == (31, 1, 2026)

    @pytest.mark.parametrize("value", ["", None, "   ", "abc", "32/01/2026"])
    def test_invalida_devuelve_vacio(self, value):
        assert parse_date(value) == (None, None, None)


class TestCleanCurrency:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("$1,234.56", 1234.56),
            ("1.234,56", 1234.56),
            ("1000", 1000.0),
            ("0", 0.0),
            (" $ 500 ", 500.0),
            ("-50", -50.0),
        ],
    )
    def test_formatos(self, value, expected):
        assert clean_currency(value) == pytest.approx(expected)

    @pytest.mark.parametrize("value", ["", None, "N/A", "USD 500", "abc"])
    def test_invalido_devuelve_none(self, value):
        assert clean_currency(value) is None


class TestCountry:
    @pytest.mark.parametrize(
        "filename, expected",
        [("Plan_MX.csv", "MX"), ("plan_co_2026.csv", "CO"), ("", "")],
    )
    def test_extrae_pais(self, filename, expected):
        assert extract_country_from_filename(filename) == expected


class TestTargetAudience:
    @pytest.mark.parametrize(
        "audience, gender",
        [("W_18-34", "Female"), ("M_25-44", "Male"), ("H_25-44", "Male"),
         ("HM_18-65", "Male"), ("P_18-65", "People"), ("X_18-34", ""), ("", "")],
    )
    def test_gender(self, audience, gender):
        assert extract_gender(audience) == gender

    @pytest.mark.parametrize(
        "audience, age", [("W_18-34", "18-34"), ("W", ""), ("", "")]
    )
    def test_age_range(self, audience, age):
        assert extract_age_range(audience) == age


class TestStage:
    @pytest.mark.parametrize(
        "objective, stage",
        [("Awareness", "Awareness"), ("Performance", "Awareness"),
         ("Data Gathering", "Awareness"), (" consideration ", "Consideration"),
         ("Conversion", "Conversion"), ("Desconocido", ""), ("", "")],
    )
    def test_normalize_stage(self, objective, stage):
        assert normalize_stage(objective) == stage


class TestPlatform:
    @pytest.mark.parametrize(
        "platform, publisher, ou, expected",
        [
            ("DV360", "", "", "DV360"),
            ("Facebook", "", "", "Meta"),
            ("Instagram", "", "", "Meta"),
            ("Facebook/Instagram/Messenger", "", "", "Meta"),
            ("", "TikTok", "", "TikTok"),
            ("", "Messenger", "", "Meta"),
            ("Otro", "", "Google Ads", "Google Ads"),
            ("Otro", "", "DV360 YT", "DV360"),
            ("Otro", "", "DV360 Programmatic", "DV360"),
            ("Otro", "", "Amazon Prime Video", "Amazon Prime"),
            ("Otro", "", "Pinterest", "Pinterest"),
        ],
    )
    def test_normaliza_y_hace_fallback(self, platform, publisher, ou, expected):
        assert normalize_platform(platform, publisher, ou) == expected

    def test_desconocida_devuelve_valor_original(self):
        assert normalize_platform("Snapchat") == "Snapchat"


class TestOtros:
    def test_sub_sector(self):
        assert extract_sub_sector("Oral Care Launch -> IO1_A") == "Oral Care"
        assert extract_sub_sector("Sin sector") == ""

    @pytest.mark.parametrize(
        "cost_type, expected",
        [("CPM", "CPM"), (" CPV ", "CPV"), ("N/A", ""), ("NA", ""), ("", "")],
    )
    def test_pricing_model(self, cost_type, expected):
        assert resolve_pricing_model({"Cost Type": cost_type}) == expected
