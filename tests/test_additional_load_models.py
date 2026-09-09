import math
import unittest

from components import load_models as catalogo
from core import additional_load_models as modelos
from core import materials


class AdditionalLoadModelsTests(unittest.TestCase):
    def test_hollow_shaft_matches_section_properties(self):
        de, di = 40.0, 20.0
        estado = modelos.eixo_circular_vazado(
            de, di, 10_000.0, 200_000.0, 100_000.0, "tracionada"
        )
        area = math.pi * (de**2 - di**2) / 4.0
        inercia = math.pi * (de**4 - di**4) / 64.0
        self.assertAlmostEqual(
            estado.sigma_x, 10_000.0 / area + 200_000.0 * (de / 2) / inercia
        )
        self.assertAlmostEqual(
            estado.tau_xy, 100_000.0 * (de / 2) / (2.0 * inercia)
        )

    def test_hollow_shaft_rejects_invalid_diameters(self):
        with self.assertRaises(ValueError):
            modelos.eixo_circular_vazado(20, 20, 0, 0, 0)

    def test_biaxial_bending_signs(self):
        estado = modelos.secao_retangular_flexao_biaxial(
            largura_mm=40.0,
            altura_mm=60.0,
            coordenada_y_mm=30.0,
            coordenada_z_mm=20.0,
            forca_axial_N=0.0,
            momento_y_Nmm=100_000.0,
            momento_z_Nmm=200_000.0,
        )
        iy = 60.0 * 40.0**3 / 12.0
        iz = 40.0 * 60.0**3 / 12.0
        esperado = 100_000.0 * 20.0 / iy - 200_000.0 * 30.0 / iz
        self.assertAlmostEqual(estado.sigma_x, esperado)

    def test_i_section_inertia_and_surface_stress(self):
        estado = modelos.secao_i_flexao(
            altura_total_mm=200.0,
            largura_mesa_mm=100.0,
            espessura_mesa_mm=10.0,
            espessura_alma_mm=6.0,
            coordenada_y_mm=100.0,
            forca_axial_N=0.0,
            momento_fletor_Nmm=5_000_000.0,
        )
        inercia = (100.0 * 200.0**3 - 94.0 * 180.0**3) / 12.0
        self.assertAlmostEqual(
            estado.sigma_x, -5_000_000.0 * 100.0 / inercia
        )

    def test_pin_double_shear(self):
        estado = modelos.pino_cisalhamento(
            forca_N=20_000.0,
            diametro_mm=10.0,
            numero_pinos=2,
            numero_planos_corte=2,
        )
        esperado = 20_000.0 / (4.0 * math.pi * 10.0**2 / 4.0)
        self.assertAlmostEqual(estado.tau_xy, esperado)

    def test_thin_tube_combines_pressure_axial_and_torsion(self):
        estado = modelos.tubo_fino_pressao_axial_torcao(
            pressao_MPa=2.0,
            diametro_medio_mm=500.0,
            espessura_mm=5.0,
            extremidades_fechadas=True,
            forca_axial_N=10_000.0,
            torque_Nmm=1_000_000.0,
        )
        self.assertAlmostEqual(estado.sigma_y, 100.0)
        self.assertAlmostEqual(
            estado.sigma_x, 50.0 + 10_000.0 / (math.pi * 500.0 * 5.0)
        )
        self.assertAlmostEqual(
            estado.tau_xy, 2_000_000.0 / (math.pi * 500.0**2 * 5.0)
        )

    def test_thin_sphere_is_equibiaxial(self):
        estado = modelos.vaso_esferico_parede_fina(2.0, 500.0, 5.0)
        self.assertAlmostEqual(estado.sigma_x, 50.0)
        self.assertAlmostEqual(estado.sigma_y, 50.0)
        self.assertEqual(estado.tau_xy, 0.0)


class ExpandedMaterialsTests(unittest.TestCase):
    def test_material_database_is_expanded_and_valid(self):
        df = materials.carregar_materiais()
        self.assertGreaterEqual(len(df), 30)
        self.assertIn("Aço inoxidável duplex 2205 solubilizado", set(df["nome"]))
        self.assertIn("Alumínio 7075-T6 chapa", set(df["nome"]))
        self.assertIn(
            "Ferro fundido nodular ASTM A536 65-45-12", set(df["nome"])
        )


class EccentricBarTests(unittest.TestCase):
    def test_centered_load_is_uniform(self):
        estado = modelos.barra_axial_excentrica(
            12_000.0, 40.0, 60.0, 0.0, 0.0, 30.0, 20.0
        )
        self.assertAlmostEqual(estado.sigma_x, 12_000.0 / 2_400.0)

    def test_eccentricity_adds_bending_on_the_loaded_side(self):
        forca, largura, altura, ey = 10_000.0, 40.0, 60.0, 10.0
        lado_carga = modelos.barra_axial_excentrica(
            forca, largura, altura, ey, 0.0, altura / 2.0, 0.0
        )
        lado_oposto = modelos.barra_axial_excentrica(
            forca, largura, altura, ey, 0.0, -altura / 2.0, 0.0
        )
        area = largura * altura
        inercia = largura * altura**3 / 12.0
        flexao = forca * ey * (altura / 2.0) / inercia
        self.assertAlmostEqual(lado_carga.sigma_x, forca / area + flexao)
        self.assertAlmostEqual(lado_oposto.sigma_x, forca / area - flexao)

    def test_kern_limit_marks_sign_reversal(self):
        # No limite do núcleo a tensão na face oposta é exatamente zero.
        largura, altura = 40.0, 60.0
        limite = altura / 6.0
        self.assertAlmostEqual(
            modelos.fator_nucleo_central(largura, altura, limite, 0.0), 1.0
        )
        estado = modelos.barra_axial_excentrica(
            10_000.0, largura, altura, limite, 0.0, -altura / 2.0, 0.0
        )
        self.assertAlmostEqual(estado.sigma_x, 0.0)
        self.assertGreater(
            modelos.fator_nucleo_central(largura, altura, limite, 1.0), 1.0
        )

    def test_point_outside_the_section_is_rejected(self):
        with self.assertRaises(ValueError):
            modelos.barra_axial_excentrica(
                1_000.0, 40.0, 60.0, 0.0, 0.0, 31.0, 0.0
            )


class RectangularTubeTests(unittest.TestCase):
    def test_bending_matches_hollow_section_properties(self):
        largura, altura, espessura = 60.0, 100.0, 5.0
        momento = 2_000_000.0
        estado = modelos.secao_tubular_retangular(
            largura, altura, espessura, altura / 2.0, 0.0, momento, 0.0
        )
        inercia = (
            largura * altura**3
            - (largura - 2 * espessura) * (altura - 2 * espessura) ** 3
        ) / 12.0
        self.assertAlmostEqual(
            estado.sigma_x, -momento * (altura / 2.0) / inercia
        )

    def test_torsion_follows_bredt(self):
        largura, altura, espessura, torque = 60.0, 100.0, 5.0, 500_000.0
        estado = modelos.secao_tubular_retangular(
            largura, altura, espessura, 0.0, 0.0, 0.0, torque
        )
        area_media = (largura - espessura) * (altura - espessura)
        self.assertAlmostEqual(
            estado.tau_xy, torque / (2.0 * area_media * espessura)
        )

    def test_wall_thicker_than_half_the_side_is_rejected(self):
        with self.assertRaises(ValueError):
            modelos.secao_tubular_retangular(
                40.0, 100.0, 20.0, 0.0, 0.0, 0.0, 0.0
            )


class ThickWallCylinderTests(unittest.TestCase):
    def test_inner_radial_stress_equals_minus_internal_pressure(self):
        sigma_r, sigma_theta, sigma_long = modelos.tensoes_lame(
            50.0, 0.0, 50.0, 80.0, 50.0
        )
        self.assertAlmostEqual(sigma_r, -50.0)
        # Equilíbrio de Lamé: σr + σθ é constante ao longo da parede.
        externa = modelos.tensoes_lame(50.0, 0.0, 50.0, 80.0, 80.0)
        self.assertAlmostEqual(sigma_r + sigma_theta, externa[0] + externa[1])
        self.assertAlmostEqual(externa[0], 0.0)
        self.assertAlmostEqual(sigma_long, (sigma_r + sigma_theta) / 2.0)

    def test_open_ends_drop_the_longitudinal_stress(self):
        *_, sigma_long = modelos.tensoes_lame(
            50.0, 0.0, 50.0, 80.0, 50.0, extremidades_fechadas=False
        )
        self.assertEqual(sigma_long, 0.0)

    def test_thin_wall_limit_approaches_the_membrane_solution(self):
        pressao, raio_interno, espessura = 2.0, 247.5, 5.0
        raio_externo = raio_interno + espessura
        _, sigma_theta, _ = modelos.tensoes_lame(
            pressao,
            0.0,
            raio_interno,
            raio_externo,
            (raio_interno + raio_externo) / 2.0,
        )
        diametro_medio = raio_interno + raio_externo
        membrana = pressao * diametro_medio / (2.0 * espessura)
        # Com D/t = 100 a solução exata fica ~1% abaixo da de membrana.
        self.assertAlmostEqual(sigma_theta, membrana, delta=membrana * 0.02)

    def test_plane_choice_selects_which_stress_goes_forward(self):
        comum = (50.0, 0.0, 50.0, 80.0, 50.0, True)
        radial = modelos.cilindro_parede_espessa(
            *comum, plano="radial-circunferencial"
        )
        longitudinal = modelos.cilindro_parede_espessa(
            *comum, plano="longitudinal-circunferencial"
        )
        sigma_r, sigma_theta, sigma_long = modelos.tensoes_lame(*comum)
        self.assertAlmostEqual(radial.sigma_x, sigma_r)
        self.assertAlmostEqual(longitudinal.sigma_x, sigma_long)
        self.assertAlmostEqual(radial.sigma_y, sigma_theta)
        self.assertAlmostEqual(longitudinal.sigma_y, sigma_theta)
        self.assertEqual(radial.tau_xy, 0.0)

    def test_invalid_geometry_and_plane_are_rejected(self):
        with self.assertRaises(ValueError):
            modelos.tensoes_lame(10.0, 0.0, 80.0, 50.0, 60.0)
        with self.assertRaises(ValueError):
            modelos.tensoes_lame(10.0, 0.0, 50.0, 80.0, 90.0)
        with self.assertRaises(ValueError):
            modelos.cilindro_parede_espessa(
                10.0, 0.0, 50.0, 80.0, 50.0, True, "axial"
            )


class HelicalSpringTests(unittest.TestCase):
    def test_wahl_factor_matches_closed_form(self):
        indice = modelos.indice_mola(40.0, 5.0)
        self.assertAlmostEqual(indice, 8.0)
        esperado = (4.0 * 8.0 - 1.0) / (4.0 * 8.0 - 4.0) + 0.615 / 8.0
        self.assertAlmostEqual(modelos.fator_wahl(indice), esperado)

    def test_shear_uses_the_corrected_torsion_formula(self):
        forca, diametro_medio, diametro_fio = 500.0, 40.0, 5.0
        estado = modelos.mola_helicoidal(forca, diametro_medio, diametro_fio)
        fator = modelos.fator_wahl(modelos.indice_mola(40.0, 5.0))
        esperado = (
            fator * 8.0 * forca * diametro_medio / (math.pi * diametro_fio**3)
        )
        self.assertAlmostEqual(estado.tau_xy, esperado)
        self.assertEqual(estado.sigma_x, 0.0)
        self.assertEqual(estado.sigma_y, 0.0)

    def test_without_wahl_the_stress_is_lower(self):
        com = modelos.mola_helicoidal(500.0, 40.0, 5.0, True)
        sem = modelos.mola_helicoidal(500.0, 40.0, 5.0, False)
        self.assertGreater(com.tau_xy, sem.tau_xy)

    def test_wire_thicker_than_the_coil_is_rejected(self):
        with self.assertRaises(ValueError):
            modelos.mola_helicoidal(500.0, 5.0, 5.0)


class IsectionShearTests(unittest.TestCase):
    def test_shear_is_zero_at_the_extreme_fibre(self):
        estado = modelos.secao_i_flexao(
            200.0, 100.0, 10.0, 6.0, 100.0, 0.0, 0.0, 50_000.0
        )
        self.assertAlmostEqual(estado.tau_xy, 0.0)

    def test_shear_peaks_at_the_centroid(self):
        comum = (200.0, 100.0, 10.0, 6.0)
        no_centroide = modelos.secao_i_flexao(
            *comum, 0.0, 0.0, 0.0, 50_000.0
        )
        na_alma = modelos.secao_i_flexao(*comum, 60.0, 0.0, 0.0, 50_000.0)
        self.assertGreater(no_centroide.tau_xy, na_alma.tau_xy)

        altura, mesa, t_mesa, t_alma = comum
        altura_alma = altura - 2.0 * t_mesa
        inercia = (
            mesa * altura**3 - (mesa - t_alma) * altura_alma**3
        ) / 12.0
        momento_estatico = (
            mesa * t_mesa * (altura - t_mesa) / 2.0
            + t_alma * (altura_alma / 2.0) ** 2 / 2.0
        )
        self.assertAlmostEqual(
            no_centroide.tau_xy,
            50_000.0 * momento_estatico / (inercia * t_alma),
        )

    def test_shear_jumps_between_web_and_flange(self):
        comum = (200.0, 100.0, 10.0, 6.0)
        # Logo acima e logo abaixo da junção alma/mesa, a largura resistente
        # muda de tw para b e a tensão cai na mesma proporção.
        na_alma = modelos.secao_i_flexao(*comum, 89.9, 0.0, 0.0, 50_000.0)
        na_mesa = modelos.secao_i_flexao(*comum, 90.1, 0.0, 0.0, 50_000.0)
        self.assertAlmostEqual(
            na_alma.tau_xy / na_mesa.tau_xy, 100.0 / 6.0, delta=0.3
        )

    def test_default_keeps_the_previous_behaviour(self):
        estado = modelos.secao_i_flexao(200.0, 100.0, 10.0, 6.0, 0.0, 0.0, 0.0)
        self.assertEqual(estado.tau_xy, 0.0)


class ChannelSectionTests(unittest.TestCase):
    # Referência: UPN 200 (h=200, bf=75, tf=11.5, tw=8.5), cujos valores
    # tabelados são A = 32.2 cm² e Ix = 1910 cm⁴. O modelo idealiza mesas
    # paralelas e cantos vivos, então a diferença esperada é pequena.
    UPN200 = (200.0, 75.0, 11.5, 8.5)

    def test_properties_match_the_rolled_section_table(self):
        propriedades = modelos.propriedades_perfil_u(*self.UPN200)
        self.assertAlmostEqual(propriedades["area"] / 100.0, 32.2, delta=0.3)
        self.assertAlmostEqual(
            propriedades["inercia_z"] / 1e4, 1910.0, delta=40.0
        )
        self.assertLess(propriedades["inercia_y"], propriedades["inercia_z"])

    def test_shear_centre_sits_outside_the_web(self):
        propriedades = modelos.propriedades_perfil_u(*self.UPN200)
        excentricidade = propriedades["excentricidade_centro_cisalhamento"]
        self.assertGreater(excentricidade, self.UPN200[3] / 2.0)
        # Para espessura uniforme a fórmula recai em e = 3b²/(6b + h).
        uniforme = modelos.propriedades_perfil_u(200.0, 75.0, 8.0, 8.0)
        b_medio, h_medio = 75.0 - 4.0, 200.0 - 8.0
        self.assertAlmostEqual(
            uniforme["excentricidade_centro_cisalhamento"],
            3.0 * b_medio**2 / (6.0 * b_medio + h_medio),
        )

    def test_bending_and_shear_follow_the_same_law_as_the_i_section(self):
        estado = modelos.secao_u_flexao(
            *self.UPN200, 100.0, 0.0, 10e6, 0.0
        )
        propriedades = modelos.propriedades_perfil_u(*self.UPN200)
        self.assertAlmostEqual(
            estado.sigma_x, -10e6 * 100.0 / propriedades["inercia_z"]
        )
        self.assertEqual(estado.tau_xy, 0.0)

        no_centroide = modelos.secao_u_flexao(
            *self.UPN200, 0.0, 0.0, 0.0, 60_000.0
        )
        na_fibra = modelos.secao_u_flexao(
            *self.UPN200, 100.0, 0.0, 0.0, 60_000.0
        )
        self.assertGreater(no_centroide.tau_xy, 0.0)
        self.assertAlmostEqual(na_fibra.tau_xy, 0.0)

    def test_invalid_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            modelos.propriedades_perfil_u(20.0, 75.0, 11.5, 8.5)
        with self.assertRaises(ValueError):
            modelos.propriedades_perfil_u(200.0, 8.0, 11.5, 8.5)
        with self.assertRaises(ValueError):
            modelos.secao_u_flexao(*self.UPN200, 120.0, 0.0, 0.0, 0.0)


class EqualLegAngleTests(unittest.TestCase):
    # Referência: L 100x100x10, com A = 19.2 cm², Ix = 177 cm⁴,
    # Imax = 281 cm⁴, Imin = 72.9 cm⁴ e centroide a 2.82 cm.
    L100 = (100.0, 10.0)

    def test_properties_match_the_rolled_section_table(self):
        p = modelos.propriedades_cantoneira_abas_iguais(*self.L100)
        self.assertAlmostEqual(p["area"] / 100.0, 19.2, delta=0.4)
        self.assertAlmostEqual(p["centroide"] / 10.0, 2.82, delta=0.1)
        self.assertAlmostEqual(p["inercia_z"] / 1e4, 177.0, delta=5.0)
        self.assertAlmostEqual(p["inercia_maxima"] / 1e4, 281.0, delta=8.0)
        self.assertAlmostEqual(p["inercia_minima"] / 1e4, 72.9, delta=2.0)

    def test_equal_legs_give_equal_inertias_and_a_negative_product(self):
        p = modelos.propriedades_cantoneira_abas_iguais(*self.L100)
        self.assertAlmostEqual(p["inercia_y"], p["inercia_z"])
        # Com as abas em +y e +z a partir do canto, o produto é negativo.
        self.assertLess(p["produto_inercia"], 0.0)
        self.assertAlmostEqual(
            p["inercia_maxima"] + p["inercia_minima"],
            p["inercia_y"] + p["inercia_z"],
        )

    def test_neutral_axis_tilts_under_a_single_moment(self):
        p = modelos.propriedades_cantoneira_abas_iguais(*self.L100)
        inclinacao = modelos.angulo_linha_neutra(
            0.0, 1e6, p["inercia_y"], p["inercia_z"], p["produto_inercia"]
        )
        # tan(α) = Iyz/Iy para Mz puro numa seção de abas iguais.
        esperado = math.degrees(
            math.atan(p["produto_inercia"] / p["inercia_y"])
        )
        self.assertAlmostEqual(inclinacao, esperado, places=6)
        self.assertLess(inclinacao, -25.0)
        self.assertGreater(inclinacao, -35.0)

    def test_symmetric_section_keeps_the_neutral_axis_horizontal(self):
        # Sem produto de inércia a flexão é reta: 0° sob Mz puro.
        self.assertAlmostEqual(
            modelos.angulo_linha_neutra(0.0, 1e6, 500.0, 900.0, 0.0), 0.0
        )

    def test_unsymmetric_formula_reduces_to_the_principal_axes_case(self):
        # Com Iyz = 0 deve coincidir com o modelo de flexão biaxial.
        largura, altura = 40.0, 60.0
        y, z, forca, my, mz = 30.0, 20.0, 5_000.0, 100_000.0, 200_000.0
        referencia = modelos.secao_retangular_flexao_biaxial(
            largura, altura, y, z, forca, my, mz
        )
        geral = modelos.tensao_flexao_assimetrica(
            forca,
            largura * altura,
            my,
            mz,
            altura * largura**3 / 12.0,
            largura * altura**3 / 12.0,
            0.0,
            y,
            z,
        )
        self.assertAlmostEqual(geral, referencia.sigma_x)

    def test_axial_only_load_is_uniform_across_the_section(self):
        p = modelos.propriedades_cantoneira_abas_iguais(*self.L100)
        esperado = 20_000.0 / p["area"]
        for ponto in (
            (100.0 - p["centroide"], -p["centroide"]),
            (-p["centroide"], 100.0 - p["centroide"]),
            (-p["centroide"], -p["centroide"]),
        ):
            estado = modelos.cantoneira_abas_iguais(
                *self.L100, *ponto, 20_000.0, 0.0, 0.0
            )
            self.assertAlmostEqual(estado.sigma_x, esperado)

    def test_point_outside_the_section_is_rejected(self):
        p = modelos.propriedades_cantoneira_abas_iguais(*self.L100)
        with self.assertRaises(ValueError):
            modelos.cantoneira_abas_iguais(
                *self.L100, 100.0 - p["centroide"] + 1.0, 0.0, 0.0, 0.0, 0.0
            )

    def test_degenerate_inertia_is_rejected(self):
        with self.assertRaises(ValueError):
            modelos.tensao_flexao_assimetrica(
                0.0, 100.0, 1.0, 1.0, 100.0, 100.0, 100.0, 1.0, 1.0
            )
        with self.assertRaises(ValueError):
            modelos.propriedades_cantoneira_abas_iguais(10.0, 10.0)


class LoadModelCatalogTests(unittest.TestCase):
    def test_every_model_belongs_to_a_listed_group(self):
        self.assertEqual(
            sorted(catalogo.CATALOGO),
            sorted(
                chave
                for modelos_do_grupo in catalogo.GRUPOS.values()
                for chave in modelos_do_grupo
            ),
        )
        for grupo, chaves in catalogo.GRUPOS.items():
            self.assertTrue(chaves, f"grupo vazio: {grupo}")

    def test_catalog_entries_are_complete(self):
        for chave, modelo in catalogo.CATALOGO.items():
            self.assertEqual(modelo.chave, chave)
            self.assertTrue(modelo.resumo.strip())
            self.assertTrue(modelo.descricao.strip())
            self.assertTrue(modelo.entradas)
            self.assertTrue(modelo.saidas)
            self.assertTrue(modelo.formula.strip())
            self.assertIn("<", modelo.croqui)
            svg = catalogo.montar_svg(modelo)
            self.assertTrue(svg.startswith("<svg "))
            self.assertIn("xmlns", svg)
            self.assertTrue(svg.endswith("</svg>"))

    def test_legacy_labels_still_resolve(self):
        self.assertEqual(
            catalogo.resolver_chave("Seção I sob força axial e flexão"),
            catalogo.MODELO_SECAO_I,
        )
        self.assertEqual(
            catalogo.resolver_chave("Barra sob carga axial"),
            "Barra sob carga axial",
        )
        self.assertEqual(
            catalogo.resolver_chave("modelo inexistente"),
            catalogo.MODELO_PADRAO,
        )
        self.assertEqual(catalogo.resolver_chave(None), catalogo.MODELO_PADRAO)

    def test_comparison_table_covers_every_model(self):
        linhas = catalogo.tabela_comparativa()
        self.assertEqual(len(linhas), len(catalogo.CATALOGO))
        self.assertEqual(
            {linha["Modelo"] for linha in linhas}, set(catalogo.CATALOGO)
        )


if __name__ == "__main__":
    unittest.main()
