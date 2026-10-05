import math
import unittest

from core import bolt_design as bolts


class BoltCatalogTests(unittest.TestCase):
    def test_metric_catalog_matches_known_m10_area(self):
        rosca = bolts.obter_rosca("M10")
        self.assertEqual(rosca.diametro_mm, 10.0)
        self.assertEqual(rosca.passo_mm, 1.5)
        self.assertEqual(rosca.area_tracao_mm2, 58.0)

    def test_approximate_stress_area_is_close_to_table(self):
        aproximada = bolts.area_tensao_aproximada(10.0, 1.5)
        self.assertAlmostEqual(aproximada, 58.0, delta=0.2)

    def test_property_class_changes_above_m16(self):
        menor = bolts.obter_classe("8.8", 16.0)
        maior = bolts.obter_classe("8.8", 20.0)
        self.assertEqual(menor.resistencia_prova_MPa, 580.0)
        self.assertEqual(maior.resistencia_prova_MPa, 600.0)
        self.assertEqual(maior.ruptura_min_MPa, 830.0)

    def test_class_98_is_limited_to_16_mm(self):
        with self.assertRaises(ValueError):
            bolts.obter_classe("9.8", 20.0)


class BoltGroupTests(unittest.TestCase):
    def test_direct_loads_split_equally(self):
        grupo = bolts.distribuir_cargas_grupo_circular(
            4, 50.0, carga_axial_N=40_000.0, carga_cortante_N=20_000.0
        )
        self.assertTrue(all(abs(v - 10_000.0) < 1e-9 for v in grupo.forcas_axiais_N))
        self.assertTrue(all(abs(v - 5_000.0) < 1e-9 for v in grupo.forcas_cisalhantes_N))

    def test_overturning_moment_load_distribution(self):
        grupo = bolts.distribuir_cargas_grupo_circular(4, 50.0, momento_tombamento_Nmm=1_000_000.0)
        # Soma x² = 2R²; o parafuso em x=R recebe M/(2R).
        self.assertAlmostEqual(grupo.maior_tracao_N, 10_000.0)
        self.assertAlmostEqual(sum(grupo.forcas_axiais_N), 0.0)

    def test_torsion_is_equal_for_circular_pattern(self):
        grupo = bolts.distribuir_cargas_grupo_circular(6, 40.0, torque_grupo_Nmm=240_000.0)
        self.assertTrue(all(abs(v - 1_000.0) < 1e-9 for v in grupo.forcas_cisalhantes_N))

    def test_zero_radius_rejects_moment(self):
        with self.assertRaises(ValueError):
            bolts.distribuir_cargas_grupo_circular(1, 0.0, momento_tombamento_Nmm=10.0)


class BoltJointTests(unittest.TestCase):
    def setUp(self):
        self.rosca = bolts.obter_rosca("M10")
        self.classe = bolts.obter_classe("8.8", 10.0)

    def _resultado(self, **mudancas):
        entradas = dict(
            rosca=self.rosca,
            classe=self.classe,
            numero_parafusos=4,
            raio_grupo_mm=50.0,
            carga_axial_N=40_000.0,
            carga_cortante_N=20_000.0,
            momento_tombamento_Nmm=0.0,
            torque_grupo_Nmm=0.0,
            fracao_pre_carga_prova=0.75,
            fator_porcar_K=0.2,
            incerteza_pre_carga=0.25,
            perda_pre_carga=0.05,
            constante_rigidez_C=0.25,
            rosca_no_plano_corte=True,
            coeficiente_atrito_junta=0.2,
            numero_interfaces_atrito=1,
            espessura_chapa_mm=10.0,
            diametro_furo_mm=11.0,
            distancia_centro_borda_mm=20.0,
            limite_esmagamento_MPa=250.0,
            escoamento_chapa_MPa=250.0,
        )
        entradas.update(mudancas)
        return bolts.avaliar_junta(**entradas)

    def test_preload_and_torque(self):
        resultado = self._resultado()
        carga_prova = 580.0 * 58.0
        self.assertAlmostEqual(resultado.carga_prova_N, carga_prova)
        self.assertAlmostEqual(resultado.pre_carga_nominal_N, 0.75 * carga_prova)
        self.assertAlmostEqual(
            resultado.torque_nominal_Nm,
            0.2 * resultado.pre_carga_nominal_N * 10.0 / 1_000.0,
        )

    def test_external_load_fraction_increases_bolt_load(self):
        resultado = self._resultado()
        esperado = resultado.pre_carga_maxima_N + 0.25 * 10_000.0
        self.assertAlmostEqual(resultado.carga_maxima_parafuso_N, esperado)

    def test_no_external_shear_has_infinite_slip_factor(self):
        resultado = self._resultado(carga_cortante_N=0.0)
        self.assertTrue(math.isinf(resultado.fator_deslizamento))
        self.assertTrue(math.isinf(resultado.fator_esmagamento))
        self.assertTrue(math.isinf(resultado.fator_rasgamento_borda))

    def test_combined_stress_uses_von_mises(self):
        resultado = self._resultado()
        esperado = math.sqrt(
            resultado.tensao_axial_MPa**2 + 3.0 * resultado.tensao_cisalhante_MPa**2
        )
        self.assertAlmostEqual(resultado.tensao_von_mises_MPa, esperado)

    def test_fatigue_goodman(self):
        fadiga = bolts.avaliar_fadiga_axial(
            self.rosca,
            self.classe,
            pre_carga_nominal_N=20_000.0,
            constante_rigidez_C=0.25,
            carga_externa_minima_por_parafuso_N=0.0,
            carga_externa_maxima_por_parafuso_N=10_000.0,
            fator_concentracao_fadiga_Kf=2.0,
            limite_fadiga_parafuso_MPa=160.0,
        )
        self.assertGreater(fadiga.tensao_alternada_MPa, 0.0)
        self.assertGreater(fadiga.tensao_media_MPa, 0.0)
        self.assertGreater(fadiga.fator_goodman, 0.0)


class BoltDiagnosticTests(unittest.TestCase):
    """O diagnóstico nunca sai vazio: solicitante, resistente, status, fórmula e fonte."""

    def setUp(self):
        self.rosca = bolts.obter_rosca("M10")
        self.classe = bolts.obter_classe("8.8", 10.0)

    def _resultado(self, **mudancas):
        entradas = dict(
            rosca=self.rosca,
            classe=self.classe,
            numero_parafusos=4,
            raio_grupo_mm=50.0,
            carga_axial_N=40_000.0,
            carga_cortante_N=20_000.0,
            momento_tombamento_Nmm=0.0,
            torque_grupo_Nmm=0.0,
            fracao_pre_carga_prova=0.75,
            fator_porcar_K=0.2,
            incerteza_pre_carga=0.25,
            perda_pre_carga=0.05,
            constante_rigidez_C=0.25,
            rosca_no_plano_corte=True,
            coeficiente_atrito_junta=0.2,
            numero_interfaces_atrito=1,
            espessura_chapa_mm=10.0,
            diametro_furo_mm=11.0,
            distancia_centro_borda_mm=20.0,
            limite_esmagamento_MPa=250.0,
            escoamento_chapa_MPa=250.0,
        )
        entradas.update(mudancas)
        return bolts.avaliar_junta(**entradas)

    def test_cada_linha_traz_solicitante_resistente_formula_e_fonte(self):
        resultado = self._resultado()
        linhas = bolts.diagnostico_junta(resultado, self.rosca, self.classe, 0.25, 1.5)
        self.assertEqual(len(linhas), 7)
        for linha in linhas:
            self.assertNotEqual(linha.status, "N/A")
            self.assertIsNotNone(linha.solicitante)
            self.assertIsNotNone(linha.resistente)
            self.assertTrue(linha.formula and linha.referencia and linha.unidade)

    def test_aproveitamento_e_o_inverso_do_fator(self):
        resultado = self._resultado()
        prova, *_ = bolts.diagnostico_junta(resultado, self.rosca, self.classe, 0.25, 1.5)
        self.assertAlmostEqual(prova.aproveitamento, 1.0 / resultado.fator_prova)
        self.assertAlmostEqual(prova.solicitante, resultado.carga_maxima_parafuso_N / 1000.0)
        self.assertAlmostEqual(prova.resistente, resultado.carga_prova_N / 1000.0)

    def test_status_segue_o_fator_e_a_meta(self):
        # pré-carga de 75% da prova + carga externa passam da prova (n < 1): NÃO OK
        reprovado = self._resultado()
        self.assertLess(reprovado.fator_prova, 1.0)
        linhas = bolts.diagnostico_junta(reprovado, self.rosca, self.classe, 0.25, 1.5)
        self.assertEqual(linhas[0].status, "NÃO OK")
        self.assertGreater(linhas[0].aproveitamento, 1.0)
        # com 50% da prova há folga (n > 1): ALERTA abaixo da meta, OK acima dela
        resultado = self._resultado(fracao_pre_carga_prova=0.5)
        self.assertGreater(resultado.fator_prova, 1.0)
        meta_alta = bolts.diagnostico_junta(
            resultado, self.rosca, self.classe, 0.25, resultado.fator_prova + 1.0
        )
        self.assertEqual(meta_alta[0].status, "ALERTA")
        self.assertIn("abaixo da meta", meta_alta[0].formula)
        folgado = bolts.diagnostico_junta(resultado, self.rosca, self.classe, 0.25, 1.0)
        self.assertEqual(folgado[0].status, "OK")

    def test_modo_sem_solicitacao_vira_na_com_explicacao(self):
        resultado = self._resultado(carga_cortante_N=0.0)
        por_nome = {
            linha.nome: linha
            for linha in bolts.diagnostico_junta(resultado, self.rosca, self.classe, 0.25, 1.5)
        }
        deslizamento = por_nome["Deslizamento por atrito"]
        self.assertEqual(deslizamento.status, "N/A")
        self.assertIn("sem solicitação", deslizamento.formula)

    def test_fadiga_entra_quando_avaliada(self):
        resultado = self._resultado()
        fadiga = bolts.avaliar_fadiga_axial(
            self.rosca, self.classe, 20_000.0, 0.25, 0.0, 10_000.0, 2.0, 160.0
        )
        linhas = bolts.diagnostico_junta(resultado, self.rosca, self.classe, 0.25, 1.5, fadiga)
        self.assertEqual(linhas[-1].nome, "Fadiga axial (Goodman)")
        self.assertAlmostEqual(linhas[-1].aproveitamento, 1.0 / fadiga.fator_goodman)


class BoltRectangularGridTests(unittest.TestCase):
    """Grade retangular: o 2×2 de 70 × 70 mm NÃO é um círculo de 70 mm de diâmetro."""

    S = G = 70.0

    def grade(self):
        # n_col = 2 ao longo de x (passo s), n_lin = 2 ao longo de y (passo g)
        return [(i * self.S, j * self.G) for i in range(2) for j in range(2)]

    def test_circular_e_o_caso_particular_do_grupo_geral(self):
        circular = bolts.distribuir_cargas_grupo_circular(
            6, 40.0, 12_000.0, 6_000.0, 900_000.0, 240_000.0
        )
        geral = bolts.distribuir_cargas_grupo(
            bolts.coordenadas_circulares(6, 40.0), 12_000.0, 6_000.0, 900_000.0, 240_000.0
        )
        for a, b in zip(circular.forcas_axiais_N, geral.forcas_axiais_N, strict=True):
            self.assertAlmostEqual(a, b, places=9)
        for a, b in zip(circular.forcas_cisalhantes_N, geral.forcas_cisalhantes_N, strict=True):
            self.assertAlmostEqual(a, b, places=9)

    def test_origem_das_coordenadas_nao_importa(self):
        deslocada = [(x + 500.0, y - 300.0) for x, y in self.grade()]
        a = bolts.distribuir_cargas_grupo(
            self.grade(), momento_tombamento_Nmm=1e6, torque_grupo_Nmm=5e5
        )
        b = bolts.distribuir_cargas_grupo(
            deslocada, momento_tombamento_Nmm=1e6, torque_grupo_Nmm=5e5
        )
        self.assertAlmostEqual(a.maior_tracao_N, b.maior_tracao_N, places=6)
        self.assertAlmostEqual(a.maior_cisalhamento_N, b.maior_cisalhamento_N, places=6)

    def test_torque_no_2x2_usa_o_raio_de_49_5_mm(self):
        raio = math.hypot(self.S, self.G) / 2.0  # √(s²+g²)/2 = 49,497 mm
        torque = 4.0 * raio * 1_000.0  # cada parafuso recebe T/(4r) = 1 000 N
        grupo = bolts.distribuir_cargas_grupo(self.grade(), torque_grupo_Nmm=torque)
        for forca in grupo.forcas_cisalhantes_N:
            self.assertAlmostEqual(forca, 1_000.0, places=6)

    def test_momento_no_2x2_distribui_pela_coordenada_x(self):
        grupo = bolts.distribuir_cargas_grupo(self.grade(), momento_tombamento_Nmm=1_000_000.0)
        # x = ±35 mm do centroide: M·x/Σx² = 1e6·35/(4·35²)
        self.assertAlmostEqual(grupo.maior_tracao_N, 1e6 / (4 * 35.0), places=6)
        self.assertAlmostEqual(sum(grupo.forcas_axiais_N), 0.0, places=9)

    def test_grade_com_uma_coluna_nao_resiste_a_momento_em_x(self):
        coluna = [(0.0, 0.0), (0.0, 70.0)]
        with self.assertRaises(ValueError):
            bolts.distribuir_cargas_grupo(coluna, momento_tombamento_Nmm=1.0)

    def test_um_parafuso_nao_resiste_a_torque(self):
        with self.assertRaises(ValueError):
            bolts.distribuir_cargas_grupo([(0.0, 0.0)], torque_grupo_Nmm=1.0)

    def test_junta_com_grade_equivale_ao_circulo_de_diametro_equivalente_em_torque(self):
        entradas = dict(
            rosca=bolts.obter_rosca("M10"),
            classe=bolts.obter_classe("8.8", 10.0),
            numero_parafusos=4,
            carga_axial_N=0.0,
            carga_cortante_N=0.0,
            momento_tombamento_Nmm=0.0,
            torque_grupo_Nmm=200_000.0,
            fracao_pre_carga_prova=0.7,
            fator_porcar_K=0.2,
            incerteza_pre_carga=0.25,
            perda_pre_carga=0.05,
            constante_rigidez_C=0.25,
            rosca_no_plano_corte=True,
            coeficiente_atrito_junta=0.2,
            numero_interfaces_atrito=1,
            espessura_chapa_mm=10.0,
            diametro_furo_mm=11.0,
            distancia_centro_borda_mm=20.0,
            limite_esmagamento_MPa=250.0,
            escoamento_chapa_MPa=250.0,
        )
        grade = bolts.avaliar_junta(raio_grupo_mm=0.0, coordenadas_mm=self.grade(), **entradas)
        circulo = bolts.avaliar_junta(raio_grupo_mm=math.hypot(self.S, self.G) / 2.0, **entradas)
        self.assertAlmostEqual(
            grade.distribuicao.maior_cisalhamento_N,
            circulo.distribuicao.maior_cisalhamento_N,
            places=6,
        )
        self.assertAlmostEqual(grade.fator_deslizamento, circulo.fator_deslizamento, places=6)
        # O erro corrigido: lançar 70 mm como DIÂMETRO do círculo dá um raio de 35 mm.
        errado = bolts.avaliar_junta(raio_grupo_mm=35.0, **entradas)
        self.assertGreater(
            errado.distribuicao.maior_cisalhamento_N, 1.4 * grade.distribuicao.maior_cisalhamento_N
        )

    def test_numero_de_parafusos_deve_coincidir_com_as_coordenadas(self):
        with self.assertRaises(ValueError):
            bolts.avaliar_junta(
                rosca=bolts.obter_rosca("M10"),
                classe=bolts.obter_classe("8.8", 10.0),
                numero_parafusos=3,
                raio_grupo_mm=0.0,
                carga_axial_N=0.0,
                carga_cortante_N=0.0,
                momento_tombamento_Nmm=0.0,
                torque_grupo_Nmm=0.0,
                fracao_pre_carga_prova=0.7,
                fator_porcar_K=0.2,
                incerteza_pre_carga=0.25,
                perda_pre_carga=0.05,
                constante_rigidez_C=0.25,
                rosca_no_plano_corte=True,
                coeficiente_atrito_junta=0.2,
                numero_interfaces_atrito=1,
                espessura_chapa_mm=10.0,
                diametro_furo_mm=11.0,
                distancia_centro_borda_mm=20.0,
                limite_esmagamento_MPa=250.0,
                escoamento_chapa_MPa=250.0,
                coordenadas_mm=self.grade(),
            )


if __name__ == "__main__":
    unittest.main()
