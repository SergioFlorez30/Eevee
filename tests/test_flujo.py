"""End-to-end flow tests: CM CSV -> transform() -> ALFRED rows."""
import pytest

from config.mapping import ALFRED_COLUMN_ORDER
from scripts.transform import parse_csv, run, transform
from tests.conftest import cm_row, load_fixture, run_transform, summary


def transform_fixture(name, filename="Plan_MX.csv"):
    return transform(parse_csv(load_fixture(name)), filename)


class TestDV360:
    def test_jerarquia_completa_con_ad_groups_generados(self):
        rows, _ = transform_fixture("dv360_completo.csv")
        assert summary(rows) == [
            ("DV360", "Campaign", "DV1"),
            ("DV360", "Insertion Order", "DV1-1"),
            ("DV360", "Line Item", "DV1-1-1"),
            ("DV360", "Ad Group", "DV1-1-1-1"),
            ("DV360", "Line Item", "DV1-1-2"),
            ("DV360", "Ad Group", "DV1-1-2-1"),
        ]

    def test_ad_group_generado_hereda_del_li_con_montos_en_cero(self):
        rows, _ = transform_fixture("dv360_completo.csv")
        li, adg = rows[2], rows[3]
        assert (adg["BUDGET"], adg["TOTAL_BUDGET"], adg["BONO"]) == (0, 0, 0)
        assert adg["CAMPAIGN_TAXO"] == ""
        for field in ["BRAND", "SUB_BRAND", "INITIATIVE", "TYPE", "START_DAY", "END_DAY", "GENDER"]:
            assert adg[field] == li[field], field

    def test_campaign_generada_sin_taxo_y_suma_hijos_directos(self):
        rows, errors = transform_fixture("dv360_io_huerfanos.csv")
        campaigns = [r for r in rows if r["LEVEL"] == "Campaign"]
        ios = [r for r in rows if r["LEVEL"] == "Insertion Order"]
        assert len(campaigns) == 1, "Todos los IO huerfanos comparten una sola Campaign"
        campaign = campaigns[0]
        assert campaign["CAMPAIGN_TAXO"] == ""
        assert campaign["BUDGET"] == pytest.approx(sum(float(r["BUDGET"]) for r in ios))
        assert campaign["TOTAL_BUDGET"] == pytest.approx(300)
        assert campaign["BONO"] == pytest.approx(7)
        assert "Row 1: Missing mandatory field 'CAMPAIGN_TAXO'" in errors

    def test_io_huerfanos_completan_li_y_ad_group(self):
        rows, _ = transform_fixture("dv360_io_huerfanos.csv")
        assert [r["ID"] for r in rows] == [
            "DV1", "DV1-1", "DV1-1-1", "DV1-1-1-1", "DV1-2", "DV1-2-1", "DV1-2-1-1",
        ]

    def test_regresion_io_li_repetido_no_omite_ad_group(self):
        """Regression for commit 0ee3b54."""
        rows, _ = transform_fixture("dv360_io_li_repetido.csv")
        ad_groups = [r["ID"] for r in rows if r["LEVEL"] == "Ad Group"]
        assert ad_groups == ["DV1-1-1-1", "DV1-1-2-1"]
        ids = [r["ID"] for r in rows]
        assert len(ids) == len(set(ids)), "IDs duplicados"

    def test_pacing_por_defecto(self):
        rows, _ = transform_fixture("dv360_completo.csv")
        assert all(r["PACING"] == "Daily_Even" for r in rows)

    def test_bono_desde_allocated_coupons(self):
        rows, _ = transform_fixture("dv360_completo.csv")
        assert rows[2]["BONO"] == "10"
        assert rows[4]["BONO"] == "5"


class TestPlataformasDosNiveles:
    def test_regresion_ids_tiktok_reinician_por_padre(self):
        rows, errors = transform_fixture("tiktok_ids.csv")
        assert [r["ID"] for r in rows] == ["TK1", "TK1-1", "TK2", "TK2-1", "TK2-2"]
        assert errors == []

    def test_meta_elimina_campaign_duplicada_vacia_y_conserva_unica(self):
        rows, errors = transform_fixture("meta_campaign_duplicada.csv")
        assert summary(rows) == [
            ("Meta", "Campaign", "M1"),
            ("Meta", "Ad Group", "M1-1"),
            ("Meta", "Campaign", "M2"),
        ]
        assert errors == []

    def test_alias_facebook_se_normaliza_a_meta(self):
        rows, _ = transform_fixture("meta_campaign_duplicada.csv")
        assert {r["PLATFORM"] for r in rows} == {"Meta"}

    def test_multiplataforma_sin_cruce_de_ids(self):
        rows, errors = transform_fixture("multiplataforma.csv")
        assert [r["ID"] for r in rows] == ["P1", "P1-1", "S1", "S1-1", "A1", "A1-1"]
        assert errors == []

    def test_nivel_no_depende_de_plan_level(self):
        rows, _ = run_transform([
            cm_row("Meta", "Hair Care -> CMP_1", **{"Plan Level": "true"}),
            cm_row("Meta", "Hair Care -> CMP_1 -> ADG1_a", **{"Plan Level": "false"}),
        ])
        assert [r["LEVEL"] for r in rows] == ["Campaign", "Ad Group"]


class TestCasteoDeValores:
    def test_fechas_montos_y_catalogos(self):
        rows, _ = run_transform([
            cm_row("TikTok", "Hair Care -> CMP_1",
                   **{"Start Date": "2026-09-05", "End Date": "30/09/2026",
                      "Billable Budget": "$1,234.50", "Total Budget": "1.500,25",
                      "Target Audience": "M_25-44", "Media Objective": "Consideration"}),
        ], filename="Plan_PE_Sep.csv")
        row = rows[0]
        assert (row["START_DAY"], row["START_MONTH"], row["START_YEAR"]) == (5, 9, 2026)
        assert (row["END_DAY"], row["END_MONTH"], row["END_YEAR"]) == (30, 9, 2026)
        assert row["MONTH"] == "SEP"
        assert row["BUDGET"] == pytest.approx(1234.5)
        assert row["TOTAL_BUDGET"] == pytest.approx(1500.25)
        assert (row["GENDER"], row["AGE_RANGE"], row["STAGE"]) == ("Male", "25-44", "Consideration")
        assert row["COUNTRY"] == "PE"
        assert row["SUB_SECTOR"] == "Hair Care"

    def test_valores_fijos(self):
        rows, _ = run_transform([cm_row("Pinterest", "Hair Care -> CMP_1")])
        row = rows[0]
        assert (row["BUY_TYPE"], row["IRA_VERSION"], row["REGION"], row["AUDIENCE"], row["BROADCAST"]) == (
            "Auction", "V1", "National", "Demo", "NA")

    @pytest.mark.parametrize("raw, expected", [("Yes", "Yes"), ("sí", "Yes"), ("1", "Yes"), ("No", "No"), ("", "No")])
    def test_autobidders(self, raw, expected):
        rows, _ = run_transform([cm_row("Meta", "Hair Care -> CMP_1", **{"Autobidder Activation Flag": raw})])
        assert rows[0]["AUTOBIDDERS"] == expected

    def test_columnas_condicionales_por_plataforma(self):
        rows, _ = transform_fixture("multiplataforma.csv")
        conditional = {"BUDGET_TYPE", "PACING", "BID_VALUE", "KPI_VALUE"}
        for row in rows:
            missing = [c for c in ALFRED_COLUMN_ORDER if c not in row and c not in conditional]
            assert not missing, missing


class TestValidacionObligatorios:
    @pytest.mark.parametrize(
        "override, field",
        [
            ({"Target Audience": ""}, "GENDER"),
            ({"Target Audience": "W"}, "AGE_RANGE"),
            ({"Media Objective": "Otro"}, "STAGE"),
            ({"Cost Type": "N/A"}, "PRICING_MODEL"),
            ({"Brand": ""}, "BRAND"),
            ({"Start Date": "abc"}, "START_DAY"),
            ({"Billable Budget": "N/A"}, "BUDGET"),
        ],
    )
    def test_campo_faltante_genera_error(self, override, field):
        _, errors = run_transform([cm_row("Pinterest", "Hair Care -> CMP_1", **override)])
        assert f"Row 1: Missing mandatory field '{field}'" in errors

    def test_pais_ausente_en_nombre_de_archivo(self):
        _, errors = run_transform([cm_row("Pinterest", "Hair Care -> CMP_1")], filename="")
        assert "Row 1: Missing mandatory field 'COUNTRY'" in errors

    def test_campos_manuales_no_bloquean(self):
        _, errors = transform_fixture("tiktok_ids.csv")
        assert not any("BUDGET_TYPE" in e or "BID_VALUE" in e for e in errors)

    def test_budget_type_solo_aplica_a_meta_y_tiktok(self):
        _, errors = transform_fixture("multiplataforma.csv")
        assert not any("BUDGET_TYPE" in e for e in errors)


class TestRun:
    def test_resultado_ok(self):
        result = run(load_fixture("tiktok_ids.csv"), "Plan_MX.csv")
        assert result["has_errors"] is False
        assert result["row_count"] == 5
        assert result["excel_bytes"]

    def test_con_errores_igual_genera_excel(self):
        result = run(load_fixture("dv360_io_huerfanos.csv"), "Plan_MX.csv")
        assert result["has_errors"] is True
        assert result["excel_bytes"], "Por negocio, un archivo con errores se puede descargar"

    @pytest.mark.parametrize("csv_text", ["", "Platform,Line Item\n", "texto,sin,sentido\n1,2,3\n"])
    def test_entradas_vacias_o_irreconocibles_no_rompen(self, csv_text):
        result = run(csv_text, "Plan_MX.csv")
        assert result["row_count"] == 0
        assert result["excel_bytes"]

    def test_excepcion_interna_se_reporta_como_error(self, monkeypatch):
        import scripts.transform as module

        def boom(*_):
            raise RuntimeError("boom")

        monkeypatch.setattr(module, "transform", boom)
        result = module.run("x", "Plan_MX.csv")
        assert result == {
            "excel_bytes": None,
            "errors": ["Fatal error: boom"],
            "row_count": 0,
            "has_errors": True,
        }

    def test_volumen_grande(self):
        rows = []
        for c in range(1, 201):
            rows.append(cm_row("TikTok", f"Hair Care -> CMP_{c}"))
            for a in range(1, 25):
                rows.append(cm_row("TikTok", f"Hair Care -> CMP_{c} -> ADG{a}_x"))
        output, errors = run_transform(rows)
        assert len(output) == 5000
        assert errors == []
        assert output[-1]["ID"] == "TK200-24"
