import math
import unittest

from core import column_buckling as flambagem
from core import steel_sections as secoes


class GeometriaColunaTests(unittest.TestCase):
    def test_retangular_raio_giracao(self):
        geo = flambagem.geometria_retangular(50.0, 100.0)
        # r = h/sqrt(12) para o lado usado como espessura do eixo correspondente
        self.assertAlmostEqual(geo.raio_giracao_x_mm, 100.0 / math.sqrt(12.0))
        self.assertAlmostEqual(geo.raio_giracao_y_mm, 50.0 / math.sqrt(12.0))
        self.assertAlmostEqual(geo.area_mm2, 5_000.0)

    def test_circular_macica_area_e_raio(self):
        geo = flambagem.geometria_circular_macica(40.0)
        area_esperada = math.pi * 40.0**2 / 4.0
        self.assertAlmostEqual(geo.area_mm2, area_esperada)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, geo.raio_giracao_y_mm)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, 40.0 / 4.0)

    def test_circular_vazada_rejeita_diametro_interno_maior(self):
        with self.assertRaises(ValueError):
            flambagem.geometria_circular_vazada(40.0, 50.0)

    def test_circular_vazada_area_positiva(self):
        geo = flambagem.geometria_circular_vazada(60.0, 40.0)
        area_esperada = math.pi / 4.0 * (60.0**2 - 40.0**2)
        self.assertAlmostEqual(geo.area_mm2, area_esperada)

    def test_perfil_catalogo_usa_rx_ry(self):
        perfil = secoes.perfil_i_simetrico("I", 200, 100, 6, 10)
        geo = flambagem.geometria_perfil_catalogo(perfil)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, perfil.rx_mm)
        self.assertAlmostEqual(geo.raio_giracao_y_mm, perfil.ry_mm)

    def test_direta_replica_mesmo_raio_quando_nao_informado(self):
        geo = flambagem.geometria_direta(1_000.0, 12.0)
        self.assertEqual(geo.raio_giracao_x_mm, geo.raio_giracao_y_mm)


class VerificarFlambagemTests(unittest.TestCase):
    def setUp(self):
        self.geometria = flambagem.geometria_circular_macica(50.0)

    def _verificar(self, comprimento_mm, **overrides):
        parametros = dict(
            geometria=self.geometria,
            comprimento_mm=comprimento_mm,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=200_000.0,
            escoamento_MPa=250.0,
            forca_solicitante_N=10_000.0,
            fator_seguranca_desejado=2.0,
        )
        parametros.update(overrides)
        return flambagem.verificar_flambagem(**parametros)

    def test_coluna_longa_usa_euler(self):
        resultado = self._verificar(3_000.0)
        self.assertIn("Euler", resultado.regime)
        self.assertGreaterEqual(resultado.esbeltez_governante, resultado.esbeltez_transicao)
        self.assertAlmostEqual(
            resultado.tensao_critica_MPa, resultado.carga_critica_euler_N / self.geometria.area_mm2
        )

    def test_coluna_curta_usa_johnson(self):
        resultado = self._verificar(200.0)
        self.assertIn("Johnson", resultado.regime)
        self.assertLess(resultado.esbeltez_governante, resultado.esbeltez_transicao)
        # Johnson nunca deve prever tensão crítica acima do escoamento.
        self.assertLessEqual(resultado.tensao_critica_MPa, 250.0)

    def test_coluna_mais_longa_tem_carga_critica_menor(self):
        curta = self._verificar(500.0)
        longa = self._verificar(3_000.0)
        self.assertLess(longa.carga_critica_N, curta.carga_critica_N)

    def test_engastada_livre_reduz_carga_critica_frente_a_biapoiada(self):
        biapoiada = self._verificar(2_000.0, kx=1.0, ky=1.0)
        engastada_livre = self._verificar(2_000.0, kx=2.0, ky=2.0)
        self.assertLess(engastada_livre.carga_critica_N, biapoiada.carga_critica_N)

    def test_fator_seguranca_infinito_sem_solicitacao(self):
        resultado = self._verificar(2_000.0, forca_solicitante_N=0.0)
        self.assertTrue(math.isinf(resultado.fator_seguranca))
        self.assertEqual(resultado.utilizacao, 0.0)

    def test_eixo_governante_e_o_mais_esbelto(self):
        geometria = flambagem.geometria_retangular(20.0, 80.0)
        resultado = flambagem.verificar_flambagem(
            geometria=geometria,
            comprimento_mm=2_000.0,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=200_000.0,
            escoamento_MPa=250.0,
            forca_solicitante_N=5_000.0,
        )
        self.assertEqual(resultado.eixo_governante, "y")
        self.assertGreater(resultado.esbeltez_y, resultado.esbeltez_x)

    def test_transicao_depende_de_e_e_sy(self):
        resultado = self._verificar(2_000.0, escoamento_MPa=500.0)
        self.assertAlmostEqual(
            resultado.esbeltez_transicao,
            math.sqrt(2.0 * math.pi**2 * 200_000.0 / 500.0),
        )

    def test_rejeita_entradas_nao_positivas(self):
        with self.assertRaises(ValueError):
            self._verificar(0.0)
        with self.assertRaises(ValueError):
            self._verificar(2_000.0, modulo_elasticidade_MPa=-1.0)
        with self.assertRaises(ValueError):
            self._verificar(2_000.0, forca_solicitante_N=-1.0)

    def test_caso_normal_nao_gera_aviso_nem_secante(self):
        resultado = self._verificar(2_000.0)
        self.assertEqual(resultado.avisos, ())
        self.assertIsNone(resultado.carga_escoamento_secante_N)
        self.assertIsNone(resultado.tensao_maxima_secante_MPa)
        self.assertEqual(resultado.eixo_excentricidade, "")


class CondicoesDeApoioTests(unittest.TestCase):
    def test_k_recomendado_cobre_os_mesmos_casos_e_nunca_e_menor(self):
        self.assertEqual(
            set(flambagem.CONDICOES_APOIO), set(flambagem.CONDICOES_APOIO_RECOMENDADAS)
        )
        for nome, teorico in flambagem.CONDICOES_APOIO.items():
            with self.subTest(apoio=nome):
                self.assertGreaterEqual(flambagem.CONDICOES_APOIO_RECOMENDADAS[nome], teorico)

    def test_valores_teoricos_classicos(self):
        self.assertEqual(flambagem.CONDICOES_APOIO["Biapoiada (pino-pino)"], 1.0)
        self.assertEqual(flambagem.CONDICOES_APOIO["Engastada-livre (em balanço)"], 2.0)
        self.assertEqual(flambagem.CONDICOES_APOIO["Biengastada"], 0.5)
        self.assertAlmostEqual(flambagem.CONDICOES_APOIO_RECOMENDADAS["Biengastada"], 0.65)


class AvisosTests(unittest.TestCase):
    def _verificar(self, geometria, comprimento_mm, **overrides):
        parametros = dict(
            geometria=geometria,
            comprimento_mm=comprimento_mm,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=200_000.0,
            escoamento_MPa=250.0,
            forca_solicitante_N=10_000.0,
        )
        parametros.update(overrides)
        return flambagem.verificar_flambagem(**parametros)

    def test_esbeltez_acima_de_200_e_apontada(self):
        geometria = flambagem.geometria_circular_macica(20.0)  # r = 5 mm
        resultado = self._verificar(geometria, 1_500.0)  # λ = 300
        self.assertGreater(resultado.esbeltez_governante, flambagem.ESBELTEZ_MAXIMA_USUAL)
        self.assertTrue(any("200" in aviso for aviso in resultado.avisos))
        curta = self._verificar(geometria, 500.0)  # λ = 100
        self.assertFalse(any("200" in aviso for aviso in curta.avisos))

    def test_k_fora_da_faixa_fisica_e_apontado(self):
        geometria = flambagem.geometria_circular_macica(50.0)
        resultado = self._verificar(geometria, 2_000.0, kx=0.2, ky=5.0)
        self.assertTrue(any("Kx" in aviso for aviso in resultado.avisos))
        self.assertTrue(any("Ky" in aviso for aviso in resultado.avisos))

    def test_unidades_implausiveis_de_e_e_sy_sao_apontadas(self):
        geometria = flambagem.geometria_circular_macica(50.0)
        # "E = 200" (GPa digitado no campo em MPa) e Sy/E absurdo.
        resultado = self._verificar(
            geometria, 2_000.0, modulo_elasticidade_MPa=200.0, escoamento_MPa=250.0
        )
        self.assertTrue(any("GPa" in aviso for aviso in resultado.avisos))
        self.assertTrue(any("Sy/E" in aviso for aviso in resultado.avisos))

    def test_tubo_de_parede_fina_avisa_flambagem_local(self):
        # D/t = 100 > 0,11·E/Sy = 88 → a parede flamba antes da coluna.
        fino = flambagem.geometria_circular_vazada(200.0, 196.0)
        resultado = self._verificar(fino, 2_000.0)
        self.assertTrue(any("Flambagem local" in aviso for aviso in resultado.avisos))
        # D/t = 20: compacto, sem aviso.
        compacto = flambagem.geometria_circular_vazada(200.0, 180.0)
        self.assertFalse(
            any("Flambagem local" in aviso for aviso in self._verificar(compacto, 2_000.0).avisos)
        )

    def test_perfil_i_de_mesa_esbelta_avisa_e_o_compacto_nao(self):
        # b/2t = 150/8 = 18,75 > 0,56·√(E/Sy) = 15,8.
        esbelto = flambagem.geometria_perfil_catalogo(
            secoes.perfil_i_simetrico("I", 300, 300, 6, 8)
        )
        avisos = self._verificar(esbelto, 3_000.0).avisos
        self.assertTrue(any("mesa" in aviso for aviso in avisos))
        compacto = flambagem.geometria_perfil_catalogo(
            secoes.perfil_i_simetrico("I", 300, 150, 8, 12)
        )
        self.assertFalse(
            any("Flambagem local" in aviso for aviso in self._verificar(compacto, 3_000.0).avisos)
        )

    def test_barras_macicas_nao_tem_parede_a_conferir(self):
        self.assertEqual(flambagem.geometria_retangular(50.0, 100.0).elementos_locais, ())
        self.assertEqual(
            flambagem.geometria_perfil_catalogo(secoes.barra_circular("BR", 40.0)).elementos_locais,
            (),
        )


class SecanteTests(unittest.TestCase):
    """A fórmula da secante é conferida contra o módulo de vigas em 2ª ordem."""

    E_MPA = 200_000.0
    L_MM = 2_000.0

    def parametros(self, geometria, **extras):
        base = dict(
            area_mm2=geometria.area_mm2,
            raio_giracao_mm=geometria.raio_giracao_x_mm,
            distancia_fibra_mm=geometria.distancia_fibra_x_mm,
            comprimento_efetivo_mm=self.L_MM,
            excentricidade_mm=10.0,
            modulo_elasticidade_MPa=self.E_MPA,
        )
        base.update(extras)
        return base

    def test_tensao_maxima_bate_com_a_viga_em_segunda_ordem(self):
        from core import beam_analysis as vb

        carga, excentricidade = 100_000.0, 10.0
        geometria = flambagem.geometria_retangular(50.0, 100.0)
        secao = vb.secao_retangular(50, 100)
        momento = carga * excentricidade
        viga = vb.Viga(
            comprimento_mm=self.L_MM,
            secao=secao,
            material=vb.MaterialViga("Aço", self.E_MPA, 77_000.0, 250.0),
            apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(self.L_MM, "rolete")),
            cargas_axiais=(vb.CargaAxial(self.L_MM, -carga),),
            momentos=(
                vb.MomentoConcentrado(0.0, -momento),
                vb.MomentoConcentrado(self.L_MM, momento),
            ),
            considerar_segunda_ordem=True,
            divisoes_por_trecho=16,
        )
        tensao_viga = abs(vb.analisar_viga(viga).extremos["tensao_normal"].valor)
        tensao_secante = flambagem.tensao_maxima_secante(carga, **self.parametros(geometria))
        self.assertAlmostEqual(tensao_secante, tensao_viga, delta=1e-3 * tensao_viga)

    def test_carga_de_escoamento_leva_a_fibra_exatamente_a_sy(self):
        geometria = flambagem.geometria_retangular(50.0, 100.0)
        carga_y = flambagem.carga_de_escoamento_secante(250.0, **self.parametros(geometria))
        self.assertAlmostEqual(
            flambagem.tensao_maxima_secante(carga_y, **self.parametros(geometria)), 250.0, places=6
        )
        euler = (
            math.pi**2
            * self.E_MPA
            * geometria.area_mm2
            / (self.L_MM / geometria.raio_giracao_x_mm) ** 2
        )
        self.assertLess(carga_y, euler)
        self.assertLess(carga_y, 250.0 * geometria.area_mm2)

    def test_mais_excentricidade_menos_carga(self):
        geometria = flambagem.geometria_retangular(50.0, 100.0)
        cargas = [
            flambagem.carga_de_escoamento_secante(
                250.0, **self.parametros(geometria, excentricidade_mm=e)
            )
            for e in (1.0, 5.0, 20.0)
        ]
        self.assertGreater(cargas[0], cargas[1])
        self.assertGreater(cargas[1], cargas[2])

    def test_excentricidade_nula_recupera_euler_ou_esmagamento(self):
        longa = flambagem.geometria_circular_macica(20.0)
        euler = (
            math.pi**2 * self.E_MPA * longa.area_mm2 / (self.L_MM / longa.raio_giracao_x_mm) ** 2
        )
        self.assertAlmostEqual(
            flambagem.carga_de_escoamento_secante(
                250.0, **self.parametros(longa, excentricidade_mm=0.0)
            ),
            euler,
            delta=1e-9 * euler,
        )
        curta = flambagem.geometria_circular_macica(200.0)
        self.assertAlmostEqual(
            flambagem.carga_de_escoamento_secante(
                250.0, **self.parametros(curta, excentricidade_mm=0.0)
            ),
            250.0 * curta.area_mm2,
            delta=1e-6 * 250.0 * curta.area_mm2,
        )

    def test_verificacao_com_excentricidade_preenche_os_campos_e_avisa(self):
        geometria = flambagem.geometria_retangular(50.0, 100.0)
        resultado = flambagem.verificar_flambagem(
            geometria=geometria,
            comprimento_mm=self.L_MM,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=self.E_MPA,
            escoamento_MPa=250.0,
            forca_solicitante_N=400_000.0,
            fator_seguranca_desejado=2.0,
            excentricidade_mm=10.0,
            eixo_excentricidade="x",
        )
        self.assertEqual(resultado.eixo_excentricidade, "x")
        self.assertIsNotNone(resultado.carga_escoamento_secante_N)
        self.assertLess(resultado.fator_seguranca_secante, 2.0)
        self.assertTrue(any("excentricidade" in aviso for aviso in resultado.avisos))
        # No eixo governante (y, o mais esbelto) a carga de escoamento é menor ainda.
        governante = flambagem.verificar_flambagem(
            geometria=geometria,
            comprimento_mm=self.L_MM,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=self.E_MPA,
            escoamento_MPa=250.0,
            forca_solicitante_N=400_000.0,
            excentricidade_mm=10.0,
        )
        self.assertEqual(governante.eixo_excentricidade, "y")
        self.assertLess(governante.carga_escoamento_secante_N, resultado.carga_escoamento_secante_N)

    def test_geometria_sem_fibra_recusa_a_excentricidade_com_clareza(self):
        direta = flambagem.geometria_direta(1_000.0, 20.0)
        with self.assertRaises(ValueError) as contexto:
            flambagem.verificar_flambagem(
                geometria=direta,
                comprimento_mm=self.L_MM,
                kx=1.0,
                ky=1.0,
                modulo_elasticidade_MPa=self.E_MPA,
                escoamento_MPa=250.0,
                forca_solicitante_N=10_000.0,
                excentricidade_mm=5.0,
            )
        self.assertIn("fibra", str(contexto.exception))
        com_fibra = flambagem.geometria_direta(
            1_000.0, 20.0, distancia_fibra_x_mm=30.0, distancia_fibra_y_mm=30.0
        )
        resultado = flambagem.verificar_flambagem(
            geometria=com_fibra,
            comprimento_mm=self.L_MM,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=self.E_MPA,
            escoamento_MPa=250.0,
            forca_solicitante_N=10_000.0,
            excentricidade_mm=5.0,
        )
        self.assertIsNotNone(resultado.carga_escoamento_secante_N)

    def test_eixo_invalido_e_recusado(self):
        with self.assertRaises(ValueError):
            flambagem.verificar_flambagem(
                geometria=flambagem.geometria_circular_macica(50.0),
                comprimento_mm=self.L_MM,
                kx=1.0,
                ky=1.0,
                modulo_elasticidade_MPa=self.E_MPA,
                escoamento_MPa=250.0,
                forca_solicitante_N=10_000.0,
                excentricidade_mm=5.0,
                eixo_excentricidade="z",
            )

    def test_perfil_monossimetrico_usa_a_fibra_mais_afastada(self):
        perfil = secoes.perfil_t("T", 200.0, 150.0, 8.0, 12.0)
        geometria = flambagem.geometria_perfil_catalogo(perfil)
        self.assertAlmostEqual(geometria.distancia_fibra_x_mm, max(perfil.distancias_fibras_x_mm))
        self.assertGreater(geometria.distancia_fibra_x_mm, 100.0)
        self.assertAlmostEqual(geometria.distancia_fibra_y_mm, 75.0)


if __name__ == "__main__":
    unittest.main()
