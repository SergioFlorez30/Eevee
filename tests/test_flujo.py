"""End-to-end flow tests: CM CSV -> transform() -> ALFRED rows."""
import pytest

from config.mapping import ALFRED_COLUMN_ORDER
from scripts.transform import parse_csv, run, transform
from tests.conftest import build_csv, cm_row, load_fixture, run_transform, summary


def transform_fixture(name, filename="Plan_MX.csv"):
    return transform(parse_csv(load_fixture(name)), filename)


class TestTargetAudienceJerarquia:
    @pytest.mark.parametrize("platform", ["Meta", "TikTok"])
    @pytest.mark.parametrize(
        "audiences, expected",
        [
            (["Female 18+"], ("Female", "18+")),
            (["Female 18+", "Female 18+"], ("Female", "18+")),
            (["HM_18-65", "People 18-65"], ("People", "18-65")),
            (["Female 18+", "Male 18+"], ("", "")),
            (["Female 18+", "Female 25-44"], ("", "")),
            (["Female 18+", ""], ("Female", "18+")),
        ],
    )
    def test_padre_vacio_toma_consenso_de_hijos(self, platform, audiences, expected):
        rows, errors = run_transform([
            cm_row(platform, "Hair Care -> CMP_1", **{"Target Audience": ""}),
            *[
                cm_row(platform, f"Hair Care -> CMP_1 -> ADG{i}_a",
                       **{"Target Audience": audience})
                for i, audience in enumerate(audiences, start=1)
            ],
        ])
        assert (rows[0]["GENDER"], rows[0]["AGE_RANGE"]) == expected
        if expected == ("", ""):
            assert "Row 1: Missing mandatory field 'GENDER'" in errors
            assert "Row 1: Missing mandatory field 'AGE_RANGE'" in errors
        if audiences[-1] == "":
            assert (rows[-1]["GENDER"], rows[-1]["AGE_RANGE"]) == expected

    def test_padre_con_audiencia_propia_prevalece_ante_hijos_diferentes(self):
        rows, _ = run_transform([
            cm_row("TikTok", "CMP_1", **{"Target Audience": "People 18+"}),
            cm_row("TikTok", "CMP_1 -> ADG1_a", **{"Target Audience": "Female 18+"}),
            cm_row("TikTok", "CMP_1 -> ADG2_a", **{"Target Audience": "Male 25-44"}),
        ])
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows] == [
            ("People", "18+"), ("Female", "18+"), ("Male", "25-44"),
        ]

    def test_conflicto_en_una_rama_no_se_oculta_con_consenso_de_otra(self):
        paths_and_audiences = [
            ("CMP_1", ""),
            ("CMP_1 -> IO1_a", ""),
            ("CMP_1 -> IO1_a -> LI1_a", ""),
            ("CMP_1 -> IO1_a -> LI1_a -> ADG1_a", "Female 18+"),
            ("CMP_1 -> IO1_a -> LI1_a -> ADG2_a", "Male 18+"),
            ("CMP_1 -> IO2_a", ""),
            ("CMP_1 -> IO2_a -> LI2_a", ""),
            ("CMP_1 -> IO2_a -> LI2_a -> ADG3_a", "Female 18+"),
        ]
        rows, _ = run_transform([
            cm_row("DV360", path, **{"Target Audience": audience})
            for path, audience in paths_and_audiences
        ])
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows[:3]] == [("", "")] * 3
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows[5:]] == [("Female", "18+")] * 3

    @pytest.mark.parametrize("second", ["Female 18+", "Male 18+"])
    @pytest.mark.parametrize("explicit_parents", [True, False])
    def test_consenso_dv360_multinivel_incluye_padres_generados(self, second, explicit_parents):
        sources = []
        if explicit_parents:
            sources = [
                cm_row("DV360", path, **{"Target Audience": ""})
                for path in ["CMP_1", "CMP_1 -> IO1_a", "CMP_1 -> IO1_a -> LI1_a"]
            ]
        sources += [
            cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG1_a",
                   **{"Target Audience": "Female 18+"}),
            cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG2_a",
                   **{"Target Audience": second}),
        ]
        rows, _ = run_transform(sources)
        expected = ("Female", "18+") if second == "Female 18+" else ("", "")
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows[:3]] == [expected] * 3
        assert (rows[3]["GENDER"], rows[3]["AGE_RANGE"]) == ("Female", "18+")
        assert rows[4]["GENDER"] == ("Female" if second == "Female 18+" else "Male")

    @pytest.mark.parametrize("audience", ["Female 18+", "HM_18-65"])
    @pytest.mark.parametrize("platform", ["DV360", "Meta", "TikTok"])
    def test_hijos_sin_audiencia_heredan_del_padre(self, audience, platform):
        paths = ["Hair Care -> CMP_1"]
        if platform == "DV360":
            paths += [paths[-1] + " -> IO1_a", paths[-1] + " -> IO1_a -> LI1_a"]
        paths.append(paths[-1] + " -> ADG1_a")
        rows, errors = run_transform([
            cm_row(platform, path, **{"Target Audience": audience if i == 0 else ""})
            for i, path in enumerate(paths)
        ])
        expected = ("Female", "18+") if audience == "Female 18+" else ("People", "18-65")
        assert len(rows) == len(paths)
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows] == [expected] * len(paths)
        assert not any("GENDER" in error or "AGE_RANGE" in error for error in errors)

    def test_ancestro_mas_cercano_sin_reemplazar_hijo_ni_cruzar_ramas(self):
        rows, errors = run_transform([
            cm_row("DV360", "CMP_1", **{"Target Audience": "Female 18+"}),
            cm_row("DV360", "CMP_1 -> IO1_a", **{"Target Audience": "HM_18-65"}),
            cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a", **{"Target Audience": ""}),
            cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG1_a",
                   **{"Target Audience": "Male 25-44"}),
            cm_row("DV360", "CMP_1 -> IO1_a -> LI1_a -> ADG2_a",
                   **{"Target Audience": ""}),
            cm_row("DV360", "CMP_1 -> IO2_a", **{"Target Audience": ""}),
            cm_row("DV360", "CMP_1 -> IO2_a -> LI2_a", **{"Target Audience": ""}),
            cm_row("DV360", "CMP_1 -> IO2_a -> LI2_a -> ADG3_a",
                   **{"Target Audience": ""}),
        ])
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows] == [
            ("Female", "18+"), ("People", "18-65"), ("People", "18-65"),
            ("Male", "25-44"), ("People", "18-65"),
            ("Female", "18+"), ("Female", "18+"), ("Female", "18+"),
        ]
        assert not any("GENDER" in error or "AGE_RANGE" in error for error in errors)

    def test_sin_audiencia_en_la_rama_no_inventa_valores(self):
        rows, errors = run_transform([
            cm_row("TikTok", "Hair Care -> CMP_1", **{"Target Audience": "Female 18+"}),
            cm_row("TikTok", "Hair Care -> CMP_2", **{"Target Audience": ""}),
            cm_row("TikTok", "Hair Care -> CMP_2 -> ADG1_a",
                   **{"Target Audience": ""}),
        ])
        assert [(r["GENDER"], r["AGE_RANGE"]) for r in rows] == [
            ("Female", "18+"), ("", ""), ("", ""),
        ]
        assert "Row 2: Missing mandatory field 'GENDER'" in errors
        assert "Row 3: Missing mandatory field 'AGE_RANGE'" in errors


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
        line_item = "Oral Care Launch -> IO1_A -> LI1_Skip"
        rows, _ = run_transform([
            cm_row("DV360", line_item, **{"Billable Budget": "100"}),
            cm_row("DV360", line_item, **{"Billable Budget": "200"}),
        ])
        ad_groups = [r["ID"] for r in rows if r["LEVEL"] == "Ad Group"]
        assert ad_groups == ["DV1-1-1-1", "DV1-1-2-1"]
        ids = [r["ID"] for r in rows]
        assert len(ids) == len(set(ids)), "IDs duplicados"

    def test_io_li_repetido_identico_sale_una_vez(self):
        rows, _ = transform_fixture("dv360_io_li_repetido.csv")
        assert [r["ID"] for r in rows if r["LEVEL"] == "Ad Group"] == ["DV1-1-1-1"]

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
    def test_plataforma_desconocida_se_omite_con_aviso(self):
        rows, errors = run_transform([
            cm_row("Pinterest", "Hair Care -> CMP_1"),
            cm_row("Snapchat", "Hair Care -> CMP_2"),
        ])
        assert [r["ID"] for r in rows] == ["P1"]
        assert errors == [
            "CM row 2: Platform 'Snapchat' is not supported by Eevee; the row was not included"
        ]

    def test_line_item_sin_codigo_se_omite_con_aviso(self):
        rows, errors = run_transform([
            cm_row("Meta", "Hair Care -> CMP_1"),
            cm_row("Meta", "Hair Care sin codigo"),
        ])
        assert [r["ID"] for r in rows] == ["M1"]
        assert errors == [
            "CM row 2: Line Item 'Hair Care sin codigo' has no level code (CMP/ADG/IO/LI); the row was not included"
        ]

    def test_fila_sin_line_item_ni_plataforma_no_genera_aviso(self):
        _, errors = run_transform([
            cm_row("Meta", "Hair Care -> CMP_1"),
            cm_row("", "", Brand="Total"),
        ])
        assert errors == []

    def test_avisos_no_impiden_el_excel(self):
        result = run(build_csv([cm_row("Snapchat", "Hair Care -> CMP_1")]), "Plan_MX.csv")
        assert result["has_errors"] is True
        assert result["excel_bytes"]

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
    @pytest.mark.parametrize("filename", ["export.csv", "ZZ_2026.csv", "MX_CO.csv"])
    def test_pais_invalido_queda_vacio_con_error_y_excel(self, filename):
        from io import BytesIO
        from openpyxl import load_workbook

        result = run(load_fixture("tiktok_ids.csv"), filename)
        assert result["has_errors"] is True
        assert result["row_count"] == 5
        assert result["excel_bytes"]
        assert result["errors"] == [
            f"Row {n}: Missing mandatory field 'COUNTRY'" for n in range(1, 6)
        ]
        wb = load_workbook(BytesIO(result["excel_bytes"]))
        ws = wb["ALFRED"]
        country_index = [c.value for c in ws[1]].index("COUNTRY")
        assert all(row[country_index] is None for row in ws.iter_rows(min_row=2, values_only=True))
        assert "Errores" in wb.sheetnames

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


class TestDuplicadosIgnorados:
    """CM repeats rows once per Publisher ID; Eevee ignores that column, so they collapse."""

    def _bloque(self, publisher_id, cpm=""):
        extra = {"Publisher ID": publisher_id, "Planned CPM": cpm}
        return [
            cm_row("TikTok", "Hair Care -> CMP_1", **extra),
            cm_row("TikTok", "Hair Care -> CMP_1 -> ADG1_a", **extra),
        ]

    def test_filas_que_solo_difieren_en_publisher_id_salen_una_vez(self):
        rows, errors = run_transform(
            self._bloque("1.87732E+15") + self._bloque("1.87725E+15", cpm="0")
            + self._bloque("1.87763E+15")
        )
        assert summary(rows) == [("TikTok", "Campaign", "TK1"), ("TikTok", "Ad Group", "TK1-1")]
        assert errors == []

    def test_filas_identicas_salen_una_vez(self):
        rows, _ = run_transform([cm_row("DV360", "CMP_1 -> IO1 -> LI1")] * 2)
        assert len({r["ID"] for r in rows}) == len(rows)
        assert len(rows) == len(run_transform([cm_row("DV360", "CMP_1 -> IO1 -> LI1")])[0])

    def test_presupuesto_no_se_duplica_en_el_padre(self):
        rows, _ = run_transform([
            cm_row("Meta", "Hair Care -> CMP_1", **{"Billable Budget": "0", "Total Budget": "0"}),
            cm_row("Meta", "Hair Care -> CMP_1 -> ADG1_a", **{"Publisher ID": "A"}),
            cm_row("Meta", "Hair Care -> CMP_1 -> ADG1_a", **{"Publisher ID": "B"}),
        ])
        assert [r["LEVEL"] for r in rows] == ["Campaign", "Ad Group"]
        assert rows[0]["BUDGET"] == rows[1]["BUDGET"]

    def test_filas_con_un_dato_usado_distinto_se_conservan(self):
        rows, _ = run_transform([
            cm_row("TikTok", "Hair Care -> CMP_1"),
            cm_row("TikTok", "Hair Care -> CMP_1 -> ADG1_a", **{"Billable Budget": "100"}),
            cm_row("TikTok", "Hair Care -> CMP_1 -> ADG1_a", **{"Billable Budget": "200"}),
        ])
        assert [r["ID"] for r in rows] == ["TK1", "TK1-1", "TK1-2"]
