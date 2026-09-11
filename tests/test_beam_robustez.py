"""Testes de robustez da análise de vigas e eixos.

Cobrem o que a revisão de robustez travou: seções monossimétricas do
catálogo com o centroide no lugar certo, validação que recusa entradas
silenciosamente erradas, solver escalonado que não confunde mau
condicionamento de unidades com mecanismo, e o texto do modelo que volta
exatamente igual depois de escrito e relido.
"""

import math
import unittest

from core import beam_analysis as vb
from core import beam_script as bs
from core import steel_sections as secoes
from tests.test_beam_analysis import L_MM, viga_padrao

E_MPA = 200_000.0
G_MPA = 77_000.0


class PerfisMonossimetricosTests(unittest.TestCase):
    def test_perfil_t_em_x_usa_o_centroide_e_nao_a_meia_altura(self):
        h, bf, tw, tf = 200.0, 150.0, 8.0, 12.0
        perfil = secoes.perfil_t("T teste", h, bf, tw, tf)
        secao = vb.secao_de_perfil_catalogo(perfil, eixo="x")
        area_mesa, area_alma = bf * tf, tw * (h - tf)
        do_topo = (area_mesa * tf / 2 + area_alma * (tf + (h - tf) / 2)) / (area_mesa + area_alma)
        self.assertAlmostEqual(secao.c_superior_mm, do_topo, places=9)
        self.assertAlmostEqual(secao.c_inferior_mm, h - do_topo, places=9)
        # O talão fica bem mais longe do centroide do que h/2 diria.
        self.assertGreater(secao.c_inferior_mm, 1.3 * h / 2)
        self.assertIn("talão", secao.descricao)

    def test_perfil_t_em_y_continua_simetrico(self):
        perfil = secoes.perfil_t("T teste", 200.0, 150.0, 8.0, 12.0)
        secao = vb.secao_de_perfil_catalogo(perfil, eixo="y")
        self.assertAlmostEqual(secao.c_superior_mm, 75.0)
        self.assertAlmostEqual(secao.c_inferior_mm, 75.0)

    def test_perfil_u_em_y_usa_o_centroide_deslocado(self):
        h, bf, tw, tf = 200.0, 75.0, 6.0, 10.0
        perfil = secoes.perfil_u("U teste", h, bf, tw, tf)
        secao = vb.secao_de_perfil_catalogo(perfil, eixo="y")
        area_alma, area_mesas = h * tw, 2 * (bf - tw) * tf
        do_dorso = (area_alma * tw / 2 + area_mesas * (tw + (bf - tw) / 2)) / (area_alma + area_mesas)
        self.assertAlmostEqual(secao.c_inferior_mm, do_dorso, places=9)
        self.assertAlmostEqual(secao.c_superior_mm, bf - do_dorso, places=9)
        self.assertGreater(secao.c_superior_mm, bf / 2)

    def test_perfil_u_em_x_e_perfis_simetricos_mantem_meia_altura(self):
        u = vb.secao_de_perfil_catalogo(secoes.perfil_u("U", 200.0, 75.0, 6.0, 10.0), eixo="x")
        self.assertAlmostEqual(u.c_superior_mm, 100.0)
        self.assertAlmostEqual(u.c_inferior_mm, 100.0)
        i = vb.secao_de_perfil_catalogo(secoes.perfil_i_simetrico("I", 300.0, 150.0, 8.0, 12.0))
        self.assertAlmostEqual(i.c_superior_mm, 150.0)
        tubo = vb.secao_de_perfil_catalogo(secoes.tubo_retangular("Tubo", 200.0, 100.0, 6.0))
        # "Tubo" começa com T, mas não é um perfil T.
        self.assertAlmostEqual(tubo.c_superior_mm, 100.0)
        self.assertAlmostEqual(tubo.c_inferior_mm, 100.0)

    def test_eixo_invalido_no_script_vira_erro_de_script(self):
        nome = next(iter(__import__("core.section_catalog", fromlist=["listar_perfis"]).listar_perfis()))
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.interpretar(
                f'viga 6\nsecao perfil "{nome}" eixo=z\nmaterial aco\napoio 0 pino\napoio 6 rolete'
            )
        self.assertIn("eixo", str(contexto.exception))


class CentroideDoCatalogoTests(unittest.TestCase):
    """As fábricas guardam o centroide; o módulo de vigas usa o valor exato."""

    def test_fabricas_monossimetricas_guardam_o_centroide(self):
        u = secoes.perfil_u("U", 200.0, 75.0, 6.0, 10.0)
        self.assertGreater(u.centroide_x_mm, 0.0)
        self.assertLess(u.centroide_x_mm, 75.0 / 2)
        self.assertAlmostEqual(u.centroide_y_mm, 100.0)
        t = secoes.perfil_t("T", 200.0, 150.0, 8.0, 12.0)
        self.assertGreater(t.centroide_y_mm, 100.0)  # mesa em cima puxa o centroide para cima
        self.assertAlmostEqual(t.centroide_x_mm, 75.0)
        c = secoes.perfil_c_enrijecido("C", 75.0, 40.0, 15.0, 2.0)
        self.assertGreater(c.centroide_x_mm, 0.0)
        self.assertLess(c.centroide_x_mm, 20.0)

    def test_perfis_simetricos_ficam_com_o_meio(self):
        w = secoes.perfil_i_simetrico("I", 300.0, 150.0, 8.0, 12.0)
        self.assertEqual(w.distancias_fibras_x_mm, (150.0, 150.0))
        self.assertEqual(w.distancias_fibras_y_mm, (75.0, 75.0))
        self.assertAlmostEqual(w.sx_mm3, w.ix_mm4 / 150.0)

    def test_modulo_elastico_usa_a_fibra_mais_afastada(self):
        c = secoes.perfil_c_enrijecido("C", 75.0, 40.0, 15.0, 2.0)
        # bf/2 = 20 mm superestimava Sy em ~20 %: a ponta das mesas está a
        # 40 − x̄ ≈ 24 mm do centroide.
        self.assertAlmostEqual(c.sy_mm3, c.iy_mm4 / (40.0 - c.centroide_x_mm))
        self.assertLess(c.sy_mm3, c.iy_mm4 / 20.0)

    def test_viga_usa_o_centroide_cadastrado_em_vez_da_estimativa(self):
        c = secoes.perfil_c_enrijecido("C", 75.0, 40.0, 15.0, 2.0)
        secao = vb.secao_de_perfil_catalogo(c, eixo="y")
        self.assertAlmostEqual(secao.c_superior_mm, 40.0 - c.centroide_x_mm)
        self.assertAlmostEqual(secao.c_inferior_mm, c.centroide_x_mm)
        self.assertIn("cadastrado", secao.descricao)
        t = secoes.perfil_t("T", 200.0, 150.0, 8.0, 12.0)
        secao_t = vb.secao_de_perfil_catalogo(t, eixo="x")
        self.assertAlmostEqual(secao_t.c_inferior_mm, t.centroide_y_mm)
        self.assertAlmostEqual(secao_t.c_superior_mm, 200.0 - t.centroide_y_mm)

    def test_centroide_fora_do_perfil_e_ignorado_com_aviso(self):
        from dataclasses import replace

        from core import section_catalog as catalogo

        u = replace(secoes.perfil_u("U", 200.0, 75.0, 6.0, 10.0), centroide_x_mm=90.0)
        self.assertEqual(u.distancias_fibras_y_mm, (37.5, 37.5))
        self.assertTrue(any("centroide" in aviso for aviso in catalogo.conferir_coerencia(u)))

    def test_perfil_de_dicionario_le_e_grava_o_centroide(self):
        from dataclasses import asdict

        from core import section_catalog as catalogo

        original = secoes.perfil_u("U", 200.0, 75.0, 6.0, 10.0)
        relido = catalogo.perfil_de_dicionario(asdict(original))
        self.assertAlmostEqual(relido.centroide_x_mm, original.centroide_x_mm)
        # Um dicionário antigo, sem os campos, continua válido: centroide no meio.
        antigo = {k: v for k, v in asdict(original).items() if not k.startswith("centroide")}
        self.assertEqual(catalogo.perfil_de_dicionario(antigo).centroide_x_mm, 0.0)


class FlambagemForaDoPlanoTests(unittest.TestCase):
    def test_perfil_i_comprimido_avisa_do_eixo_fraco(self):
        perfil = secoes.perfil_i_simetrico("I", 300.0, 150.0, 8.0, 12.0)
        secao = vb.secao_de_perfil_catalogo(perfil)
        resultado = vb.analisar_viga(
            viga_padrao(
                secao=secao,
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -5.0),),
                cargas_axiais=(vb.CargaAxial(L_MM, -50_000.0),),
            )
        )
        esperado = resultado.fator_carga_critica * perfil.iy_mm4 / perfil.ix_mm4
        self.assertAlmostEqual(resultado.fator_carga_critica_transversal, esperado, places=9)
        self.assertLess(resultado.fator_carga_critica_transversal, resultado.fator_carga_critica)
        self.assertTrue(any("Fora do plano" in aviso for aviso in resultado.avisos))

    def test_secoes_com_inercia_transversal_igual_ou_maior_nao_avisam(self):
        for secao in (
            vb.secao_circular_macica(60),
            # Retangular fletida em torno do eixo fraco: I⊥ > I, o plano da
            # flexão já é o crítico.
            vb.secao_retangular(200, 100),
        ):
            with self.subTest(secao=secao.nome):
                resultado = vb.analisar_viga(
                    viga_padrao(
                        secao=secao,
                        cargas_pontuais=(vb.CargaPontual(L_MM / 2, -1_000.0),),
                        cargas_axiais=(vb.CargaAxial(L_MM, -1_000.0),),
                    )
                )
                self.assertIsNone(resultado.fator_carga_critica_transversal)
                self.assertFalse(any("Fora do plano" in aviso for aviso in resultado.avisos))

    def test_sem_compressao_nao_ha_fator_transversal(self):
        resultado = vb.analisar_viga(
            viga_padrao(cargas_pontuais=(vb.CargaPontual(L_MM / 2, -1_000.0),))
        )
        self.assertIsNone(resultado.fator_carga_critica_transversal)

    def test_secao_manual_aceita_iy_e_o_script_o_preserva(self):
        viga = bs.interpretar(
            "viga 6\nsecao manual A=5000 I=2.5e7 c=100 Av=3000 Iy=4e6\n"
            "material aco\napoio 0 pino\napoio 6 rolete\nN 6 20 compressao"
        )
        self.assertAlmostEqual(viga.secao.inercia_transversal_mm4, 4e6)
        reconstruida = bs.interpretar(bs.gerar_script(viga))
        self.assertEqual(reconstruida.secao, viga.secao)
        self.assertIsNotNone(vb.analisar_viga(viga).fator_carga_critica_transversal)


class TorcaoDePerfilDoCatalogoTests(unittest.TestCase):
    """Wt = J/t_máx só vale para perfil aberto; tubo e barra têm fórmula própria."""

    def test_tubo_circular_usa_j_sobre_raio(self):
        perfil = secoes.tubo_circular("TC", 168.3, 8.0)
        secao = vb.secao_de_perfil_catalogo(perfil)
        self.assertAlmostEqual(secao.modulo_torcao_mm3, perfil.j_mm4 / (168.3 / 2))
        # A fórmula de perfil aberto dava um Wt dez vezes maior — τ dez vezes menor.
        self.assertLess(secao.modulo_torcao_mm3, 0.2 * perfil.j_mm4 / 8.0)

    def test_tubo_retangular_usa_bredt(self):
        perfil = secoes.tubo_retangular("TR", 200.0, 100.0, 6.0)
        secao = vb.secao_de_perfil_catalogo(perfil)
        self.assertAlmostEqual(secao.modulo_torcao_mm3, 2.0 * (100.0 - 6.0) * (200.0 - 6.0) * 6.0)

    def test_barras_macicas_usam_as_formulas_fechadas(self):
        redonda = vb.secao_de_perfil_catalogo(secoes.barra_circular("BR", 40.0))
        self.assertAlmostEqual(redonda.modulo_torcao_mm3, math.pi * 40.0**3 / 16.0)
        chata = vb.secao_de_perfil_catalogo(secoes.barra_retangular("BC", 60.0, 20.0))
        self.assertAlmostEqual(chata.modulo_torcao_mm3, 60.0**2 * 20.0**2 / (3 * 60.0 + 1.8 * 20.0))

    def test_perfil_aberto_mantem_j_sobre_t_max(self):
        perfil = secoes.perfil_i_simetrico("I", 300.0, 150.0, 8.0, 12.0)
        secao = vb.secao_de_perfil_catalogo(perfil)
        self.assertAlmostEqual(secao.modulo_torcao_mm3, perfil.j_mm4 / 12.0)
        self.assertNotIn("perfil aberto", secao.descricao)

    def test_familia_desconhecida_avisa_na_descricao(self):
        from dataclasses import replace

        perfil = replace(secoes.perfil_i_simetrico("X", 300.0, 150.0, 8.0, 12.0), familia="Personalizado")
        secao = vb.secao_de_perfil_catalogo(perfil)
        self.assertIn("perfil aberto", secao.descricao)


class CisalhamentoEmYTests(unittest.TestCase):
    """Na flexão em torno de y o cortante é resistido pelas mesas, não pela alma."""

    def test_perfil_i_usa_as_duas_mesas(self):
        perfil = secoes.perfil_i_simetrico("I", 300.0, 150.0, 8.0, 12.0)
        em_x = vb.secao_de_perfil_catalogo(perfil, eixo="x")
        em_y = vb.secao_de_perfil_catalogo(perfil, eixo="y")
        self.assertAlmostEqual(em_x.area_cisalhamento_mm2, perfil.area_cisalhamento_mm2)
        self.assertAlmostEqual(em_y.area_cisalhamento_mm2, 2 * 150.0 * 12.0)
        self.assertLessEqual(em_y.area_cisalhamento_mm2, perfil.area_mm2)

    def test_perfil_t_usa_uma_mesa_e_tubo_retangular_as_paredes_horizontais(self):
        t = vb.secao_de_perfil_catalogo(secoes.perfil_t("T", 200.0, 150.0, 8.0, 12.0), eixo="y")
        self.assertAlmostEqual(t.area_cisalhamento_mm2, 150.0 * 12.0)
        tubo = vb.secao_de_perfil_catalogo(secoes.tubo_retangular("TR", 200.0, 100.0, 6.0), eixo="y")
        self.assertAlmostEqual(tubo.area_cisalhamento_mm2, 2 * 6.0 * (100.0 - 12.0))

    def test_secoes_simetricas_mantem_a_area_tabelada(self):
        barra = secoes.barra_circular("BR", 40.0)
        self.assertAlmostEqual(
            vb.secao_de_perfil_catalogo(barra, eixo="y").area_cisalhamento_mm2,
            barra.area_cisalhamento_mm2,
        )

    def test_familia_desconhecida_mantem_a_alma_e_avisa(self):
        from dataclasses import replace

        perfil = replace(secoes.perfil_i_simetrico("X", 300.0, 150.0, 8.0, 12.0), familia="Personalizado")
        secao = vb.secao_de_perfil_catalogo(perfil, eixo="y")
        self.assertAlmostEqual(secao.area_cisalhamento_mm2, perfil.area_cisalhamento_mm2)
        self.assertIn("conservadora", secao.descricao)


class SanidadeDaSecaoTests(unittest.TestCase):
    def secao(self, **alteracoes):
        base = dict(
            nome="teste",
            area_mm2=2_000.0,
            inercia_mm4=1.0e6,
            c_superior_mm=50.0,
            c_inferior_mm=50.0,
            momento_estatico_mm3=1.0e4,
            espessura_cisalhamento_mm=10.0,
            constante_torcao_mm4=1.0e5,
            modulo_torcao_mm3=1.0e3,
        )
        base.update(alteracoes)
        return vb.SecaoViga(**base)

    def test_secao_coerente_e_aceita(self):
        self.secao()

    def test_inercia_maior_que_a_c2_e_recusada(self):
        # I em cm⁴ digitado como mm⁴, por exemplo: 2000 × 50² = 5e6 é o teto.
        with self.assertRaises(ValueError) as contexto:
            self.secao(inercia_mm4=6.0e6)
        self.assertIn("A·c²", str(contexto.exception))

    def test_momento_estatico_maior_que_a_c_sobre_2_e_recusado(self):
        with self.assertRaises(ValueError):
            self.secao(momento_estatico_mm3=6.0e4)

    def test_area_de_cisalhamento_maior_que_a_area_e_recusada(self):
        with self.assertRaises(ValueError):
            self.secao(area_cisalhamento_mm2=2_500.0)

    def test_todas_as_fabricas_e_o_catalogo_passam_na_sanidade(self):
        from core import section_catalog as catalogo

        for perfil in catalogo.listar_perfis().values():
            for eixo in ("x", "y"):
                vb.secao_de_perfil_catalogo(perfil, eixo=eixo)
        vb.secao_retangular(100, 200)
        vb.secao_circular_macica(60)
        vb.secao_tubo_circular(60.3, 54.3)
        vb.secao_tubo_retangular(100, 200, 6)
        vb.secao_i_simetrica(300, 150, 8, 12)


class AvisosDeMaterialTests(unittest.TestCase):
    def analisar(self, material):
        return vb.analisar_viga(
            viga_padrao(
                material=material,
                cargas_pontuais=(vb.CargaPontual(L_MM / 2, -1_000.0),),
            )
        )

    def test_material_normal_nao_gera_aviso(self):
        self.assertEqual(self.analisar(vb.MaterialViga("Aço", 200_000.0, 77_000.0, 250.0)).avisos, ())

    def test_e_em_mpa_digitado_como_gpa_e_apontado(self):
        # "material E=200000": mil vezes maior do que qualquer material.
        avisos = self.analisar(vb.MaterialViga("?", 2.0e8, 7.7e7, 250.0)).avisos
        self.assertTrue(any("GPa" in aviso and "E =" in aviso for aviso in avisos))

    def test_g_maior_que_e_sobre_2_e_apontado(self):
        avisos = self.analisar(vb.MaterialViga("?", 200_000.0, 150_000.0, 250.0)).avisos
        self.assertTrue(any("Poisson" in aviso for aviso in avisos))

    def test_escoamento_implausivel_e_apontado(self):
        avisos = self.analisar(vb.MaterialViga("?", 200_000.0, 77_000.0, 25_000.0)).avisos
        self.assertTrue(any("Sy" in aviso for aviso in avisos))

    def test_avisos_sao_so_avisos_e_o_calculo_sai(self):
        resultado = self.analisar(vb.MaterialViga("madeira", 11_000.0, 700.0, 40.0))
        self.assertTrue(resultado.pontos)


class MalhaTests(unittest.TestCase):
    def test_cargas_quase_coincidentes_nao_viram_mecanismo_falso(self):
        # Antes, duas cargas a 0,1 mm uma da outra numa viga de 6 m criavam
        # um elemento minúsculo, a matriz perdia o condicionamento e o solver
        # acusava "instável". Agora elas caem no mesmo nó.
        inercia = vb.secao_retangular(100, 200).inercia_mm4
        exato = 2 * 10_000.0 * L_MM**3 / (48 * 200_000.0 * inercia)
        for delta in (0.1, 1e-3, 1e-5):
            with self.subTest(delta=delta):
                resultado = vb.analisar_viga(
                    viga_padrao(
                        cargas_pontuais=(
                            vb.CargaPontual(L_MM / 2, -10_000.0),
                            vb.CargaPontual(L_MM / 2 + delta, -10_000.0),
                        )
                    )
                )
                self.assertAlmostEqual(resultado.extremos["flecha"].valor, -exato, places=6)
                # O modelo devolvido mostra a posição em que a carga foi aplicada.
                self.assertAlmostEqual(resultado.viga.cargas_pontuais[1].x_mm, L_MM / 2)
                self.assertLess(vb.conferir_equilibrio(resultado)["residuo_relativo"], 1e-9)

    def test_cargas_distintas_continuam_distintas(self):
        resultado = vb.analisar_viga(
            viga_padrao(
                cargas_pontuais=(
                    vb.CargaPontual(2_000.0, -10_000.0),
                    vb.CargaPontual(2_010.0, -10_000.0),
                )
            )
        )
        self.assertAlmostEqual(resultado.viga.cargas_pontuais[1].x_mm, 2_010.0)
        self.assertEqual(resultado.numero_elementos, 3)

    def test_distribuida_mais_curta_que_a_tolerancia_e_recusada_com_clareza(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(
                    cargas_distribuidas=(vb.CargaDistribuida(3_000.0, 3_000.2, -10.0),)
                )
            )
        self.assertIn("carga pontual", str(contexto.exception))

    def test_refino_e_proporcional_ao_comprimento_do_trecho(self):
        # Uma carga a 20 mm do apoio: o trecho curto recebe um elemento, não
        # oito lascas de 2,5 mm ao lado de elementos de 750 mm.
        resultado = vb.analisar_viga(
            viga_padrao(
                cargas_pontuais=(vb.CargaPontual(20.0, -10_000.0),),
                cargas_axiais=(vb.CargaAxial(L_MM, -50_000.0),),
                considerar_segunda_ordem=True,
            )
        )
        self.assertLessEqual(resultado.numero_elementos, 20)
        self.assertGreaterEqual(resultado.numero_elementos, 15)
        # E a carga crítica continua a de Euler para a barra inteira.
        euler = math.pi**2 * 200_000.0 * vb.secao_retangular(100, 200).inercia_mm4 / L_MM**2
        self.assertAlmostEqual(resultado.fator_carga_critica, euler / 50_000.0, delta=euler / 50_000.0 * 1e-3)

    def test_malha_acima_do_teto_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(viga_padrao(divisoes_por_trecho=vb.ELEMENTOS_MAXIMOS + 1))
        self.assertIn("divisoes", str(contexto.exception))

    def test_refino_automatico_se_adapta_a_muitos_trechos_e_avisa(self):
        cargas = tuple(vb.CargaPontual(20.0 * (i + 1), -100.0) for i in range(299))
        resultado = vb.analisar_viga(
            viga_padrao(
                cargas_pontuais=cargas,
                cargas_axiais=(vb.CargaAxial(L_MM, -1_000.0),),
            )
        )
        self.assertLessEqual(resultado.numero_elementos, vb.ELEMENTOS_MAXIMOS)
        self.assertTrue(any("limitada" in aviso for aviso in resultado.avisos))

    def test_amostragem_e_limitada_em_malhas_grandes(self):
        resultado = vb.analisar_viga(
            viga_padrao(
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -10.0),),
                divisoes_por_trecho=500,
            )
        )
        self.assertEqual(resultado.numero_elementos, 500)
        self.assertLess(len(resultado.pontos), 1.2 * vb.PONTOS_TOTAIS_ALVO)
        # Os extremos não dependem da densidade: continuam exatos (a menos
        # do arredondamento que 500 elementos acumulam, ~1e-8).
        inercia = vb.secao_retangular(100, 200).inercia_mm4
        esperado = 5 * -10.0 * L_MM**4 / (384 * 200_000.0 * inercia)
        self.assertAlmostEqual(
            resultado.extremos["flecha"].valor, esperado, delta=1e-6 * abs(esperado)
        )

    def test_extremo_interno_de_v_numa_trapezoidal_que_troca_de_sinal(self):
        # Balanço engastado na direita com w de −12 a +12 N/mm: V parte de
        # zero na ponta livre, é máximo onde w = 0 (meio do vão) e volta a
        # zero no engaste — um ponto que amostras igualmente espaçadas não
        # acertam. Com 4 amostras por elemento, sem a raiz o pico sairia 11 %
        # baixo.
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(L_MM, "engaste"),),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -12.0, 12.0),),
            ),
            pontos_por_elemento=4,
        )
        # V(x) = ∫₀ˣ w = −12x + 12x²/L → |V|máx = 3L em x = L/2.
        self.assertAlmostEqual(resultado.extremos["cortante"].x_mm, L_MM / 2, places=6)
        self.assertAlmostEqual(abs(resultado.extremos["cortante"].valor), 3.0 * L_MM, places=6)


class ValidacaoDeEntradaTests(unittest.TestCase):
    def test_divisoes_invalidas_sao_recusadas_no_modelo(self):
        for ruim in (0, -3, 2.5):
            with self.subTest(divisoes=ruim):
                with self.assertRaises(ValueError):
                    viga_padrao(divisoes_por_trecho=ruim)

    def test_mola_rotacional_sobre_rotula_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(
                    apoios=(
                        vb.Apoio(0.0, "pino"),
                        vb.Apoio(3_000.0, "mola", rigidez_rotacional_Nmm_rad=1e9),
                        vb.Apoio(L_MM, "rolete"),
                    ),
                    rotulas=(vb.Rotula(3_000.0),),
                    cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -10.0),),
                )
            )
        self.assertIn("kr", str(contexto.exception))

    def test_secao_manual_com_q_sem_t_e_recusada(self):
        # Antes, t = 1 mm entrava em silêncio e τ = V·Q/(I·1) saía absurdo.
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.interpretar(
                "viga 6\nsecao manual A=5000 I=2.5e7 c=100 Q=250000\n"
                "material aco\napoio 0 pino\napoio 6 rolete"
            )
        self.assertIn("t", str(contexto.exception))

    def test_secao_manual_so_com_av_e_aceita(self):
        viga = bs.interpretar(
            "viga 6\nsecao manual A=5000 I=2.5e7 c=100 Av=3000\n"
            "material aco\napoio 0 pino\napoio 6 rolete"
        )
        self.assertEqual(viga.secao.momento_estatico_mm3, 0.0)
        self.assertEqual(viga.secao.espessura_cisalhamento_mm, 0.0)
        self.assertAlmostEqual(viga.secao.area_cisalhamento_mm2, 3_000.0)

    def test_flecha_admissivel_ignora_apoios_que_nao_seguram_na_vertical(self):
        # Trava axial no meio não define vão: o vão é entre os dois roletes.
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(
                    vb.Apoio(0.0, "rolete"),
                    vb.Apoio(L_MM / 2, "apoio horizontal"),
                    vb.Apoio(L_MM, "rolete"),
                ),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -10.0),),
            )
        )
        self.assertAlmostEqual(vb.verificar_flecha(resultado)["vao_mm"], L_MM)
        # Balanço com trava axial na ponta livre: continua sendo o comprimento total.
        balanco = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"), vb.Apoio(L_MM, "apoio horizontal")),
                cargas_pontuais=(vb.CargaPontual(L_MM, -5_000.0),),
            )
        )
        self.assertAlmostEqual(vb.verificar_flecha(balanco)["vao_mm"], L_MM)


class SolverEscalonadoTests(unittest.TestCase):
    def test_barra_longa_e_flexivel_com_malha_fina_nao_e_confundida_com_mecanismo(self):
        # 40 m de barra fina em 400 elementos: o modo mais flexível tem
        # rigidez minúscula frente à rotação de cada nó — sem escalonar a
        # matriz, o teste de posto acusava um mecanismo que não existe.
        comprimento = 40_000.0
        viga = vb.Viga(
            comprimento_mm=comprimento,
            secao=vb.secao_circular_macica(20.0),
            material=vb.MaterialViga("Aço", E_MPA, G_MPA),
            apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(comprimento, "rolete")),
            cargas_distribuidas=(vb.CargaDistribuida(0.0, comprimento, -0.001),),
            divisoes_por_trecho=400,
        )
        resultado = vb.analisar_viga(viga, pontos_por_elemento=3)
        inercia = viga.secao.inercia_mm4
        self.assertAlmostEqual(
            resultado.extremos["flecha"].valor,
            5 * -0.001 * comprimento**4 / (384 * E_MPA * inercia),
            delta=1e-6 * abs(5 * 0.001 * comprimento**4 / (384 * E_MPA * inercia)),
        )
        # O condicionamento cresce com n⁴: em 400 elementos o resíduo de
        # arredondamento fica na casa de 1e-9, ainda sem significado físico.
        self.assertLess(vb.conferir_equilibrio(resultado)["residuo_relativo"], 1e-7)

    def test_mecanismo_continua_sendo_detectado_apos_o_escalonamento(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(
                    apoios=(vb.Apoio(0.0, "rolete"), vb.Apoio(L_MM, "rolete")),
                    rotulas=(vb.Rotula(L_MM / 2),),
                    cargas_pontuais=(vb.CargaPontual(L_MM / 4, -1_000.0),),
                )
            )
        self.assertIn("instável", str(contexto.exception))

    def test_carga_critica_com_mola_e_rotula_sai_positiva_e_finita(self):
        # Só a forma simétrica do problema de autovalor garante autovalores
        # reais; aqui a matriz mistura molas, rótula e compressão parcial.
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(
                    vb.Apoio(0.0, "pino"),
                    vb.Apoio(L_MM / 2, "mola", rigidez_vertical_N_mm=2_000.0),
                    vb.Apoio(L_MM, "rolete"),
                ),
                rotulas=(vb.Rotula(L_MM / 4),),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -5.0),),
                cargas_axiais=(vb.CargaAxial(L_MM, -50_000.0),),
            )
        )
        self.assertIsNotNone(resultado.fator_carga_critica)
        self.assertTrue(math.isfinite(resultado.fator_carga_critica))
        self.assertGreater(resultado.fator_carga_critica, 0.0)

    def test_raiz_do_cortante_e_encontrada_em_barra_muito_curta_e_muito_longa(self):
        # A mudança de variável t = x/L mantém as raízes bem condicionadas
        # em qualquer escala: o pico de M da carga triangular continua em L/√3.
        for comprimento in (50.0, 60_000.0):
            with self.subTest(comprimento=comprimento):
                resultado = vb.analisar_viga(
                    vb.Viga(
                        comprimento_mm=comprimento,
                        secao=vb.secao_retangular(20, 40),
                        material=vb.MaterialViga("Aço", E_MPA, G_MPA),
                        apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(comprimento, "rolete")),
                        cargas_distribuidas=(vb.CargaDistribuida(0.0, comprimento, 0.0, -12.0),),
                    )
                )
                self.assertAlmostEqual(
                    resultado.extremos["momento"].x_mm / comprimento, 1 / math.sqrt(3), places=9
                )


class IdaEVoltaDoScriptTests(unittest.TestCase):
    def test_todos_os_exemplos_voltam_identicos(self):
        # Não só os resultados: o próprio modelo (nome, seção, material,
        # cargas) é reconstruído igual, campo a campo.
        for nome, script in bs.EXEMPLOS.items():
            with self.subTest(exemplo=nome):
                original = bs.interpretar(script)
                reconstruida = bs.interpretar(bs.gerar_script(original))
                self.assertEqual(reconstruida, original)

    def test_nome_do_modelo_e_da_secao_sobrevivem(self):
        viga = bs.interpretar(
            'nome "Viga do mezanino — eixo 3"\nviga 6\nsecao retangular 100 200\n'
            "material aco\napoio 0 pino\napoio 6 rolete\nq 0 6 15 baixo"
        )
        self.assertEqual(viga.nome, "Viga do mezanino — eixo 3")
        reconstruida = bs.interpretar(bs.gerar_script(viga))
        self.assertEqual(reconstruida.nome, viga.nome)
        self.assertEqual(reconstruida.secao.nome, "Retangular")
        self.assertEqual(reconstruida.secao.descricao, viga.secao.descricao)
        self.assertEqual(reconstruida.material.nome, "aco")

    def test_numeros_nao_perdem_precisao_na_ida_e_volta(self):
        # ":g" cortava em seis algarismos: 12,3457 m e 123,4567 kN voltavam
        # diferentes. O texto agora reconstrói o double exatamente.
        viga = viga_padrao(
            comprimento_mm=12_345.6789,
            apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(12_345.6789, "rolete")),
            cargas_pontuais=(vb.CargaPontual(7_654.321, -123_456.78),),
            cargas_distribuidas=(vb.CargaDistribuida(0.0, 12_345.6789, -1.234567, -9.87654321),),
        )
        reconstruida = bs.interpretar(bs.gerar_script(viga))
        self.assertEqual(reconstruida.comprimento_mm, viga.comprimento_mm)
        self.assertEqual(reconstruida.cargas_pontuais[0].fy_N, viga.cargas_pontuais[0].fy_N)
        self.assertAlmostEqual(
            reconstruida.cargas_pontuais[0].x_mm, viga.cargas_pontuais[0].x_mm, places=9
        )
        self.assertEqual(
            reconstruida.cargas_distribuidas[0].w_final, viga.cargas_distribuidas[0].w_final
        )

    def test_aspas_protegem_espacos_virgulas_e_cerquilha(self):
        tokens = bs._tokenizar('secao manual A=1 nome="W 200 x 46,1 (H)" descricao="tem # e = dentro" # fora')
        self.assertEqual(
            tokens,
            ["secao", "manual", "A=1", "nome=W 200 x 46,1 (H)", "descricao=tem # e = dentro"],
        )
        self.assertEqual(bs._tokenizar('nome “Viga do mezanino”'), ["nome", "Viga do mezanino"])

    def test_caso_com_espaco_sobrevive_a_ida_e_volta(self):
        viga = viga_padrao(
            cargas_pontuais=(vb.CargaPontual(2_000.0, -5_000.0, caso="Peso próprio"),),
            cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -3.0, caso="Sobrecarga de uso"),),
        )
        texto = bs.gerar_script(viga)
        self.assertIn('caso="Peso próprio"', texto)
        reconstruida = bs.interpretar(texto)
        self.assertEqual(vb.casos_declarados(reconstruida), ("Peso próprio", "Sobrecarga de uso"))

    def test_axial_excentrica_vira_axial_mais_momento(self):
        # Compressão de 100 kN entrando 50 mm acima do centroide, na ponta
        # direita: M = −e·Fx = −50·(−100 000) = +5 kN·m (anti-horário).
        viga = bs.interpretar(
            "viga 4\nsecao retangular 100 200\nmaterial aco\napoio 0 pino\napoio 4 rolete\n"
            "N 4 100 compressao e=50 caso=Sobrecarga"
        )
        self.assertAlmostEqual(viga.cargas_axiais[0].fx_N, -100_000.0)
        self.assertEqual(len(viga.momentos), 1)
        self.assertAlmostEqual(viga.momentos[0].mz_Nmm, 5.0e6)
        self.assertAlmostEqual(viga.momentos[0].x_mm, 4_000.0)
        self.assertEqual(viga.momentos[0].caso, "Sobrecarga")
        # Excentricidade nula não cria momento fantasma.
        sem = bs.interpretar(
            "viga 4\nsecao retangular 100 200\nmaterial aco\napoio 0 pino\napoio 4 rolete\nN 4 100 e=0"
        )
        self.assertEqual(sem.momentos, ())

    def test_sinal_de_menos_tipografico_e_aceito(self):
        viga = bs.interpretar(
            "viga 6\nsecao retangular 100 200\nmaterial aco\napoio 0 pino\napoio 6 rolete\n"
            "P 3 −20\nq 0 6 –1,5"
        )
        self.assertAlmostEqual(viga.cargas_pontuais[0].fy_N, -20_000.0)
        self.assertAlmostEqual(viga.cargas_distribuidas[0].w_inicial_N_mm, -1.5)

    def test_erro_na_envoltoria_diz_qual_combinacao_falhou(self):
        # A combinação "ELU" leva a compressão acima da carga crítica; a
        # mensagem precisa apontá-la, não só descrever o problema.
        critica = math.pi**2 * 200_000.0 * vb.secao_retangular(100, 200).inercia_mm4 / L_MM**2
        viga = viga_padrao(
            cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -1.0),),
            cargas_axiais=(vb.CargaAxial(L_MM, -0.8 * critica, caso="Compressão"),),
            considerar_segunda_ordem=True,
        )
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_envoltoria(
                viga,
                [
                    vb.CombinacaoCarga("ELS", {"Permanente": 1.0, "Compressão": 1.0}),
                    vb.CombinacaoCarga("ELU", {"Permanente": 1.4, "Compressão": 1.5}),
                ],
            )
        self.assertIn("'ELU'", str(contexto.exception))
        self.assertIn("carga crítica", str(contexto.exception))

    def test_nomes_de_bitola_com_aspas_de_polegada_sobrevivem(self):
        # 28 bitolas do catálogo têm `"` no nome (I 3" x 8,48): entre aspas
        # tipográficas o nome chega intacto, e a busca ignora aspas.
        self.assertEqual(bs.texto_entre_aspas('I 3" x 8,48'), "“I 3\" x 8,48”")
        self.assertEqual(bs._tokenizar('secao perfil “I 3" x 8,48” eixo=x'), ["secao", "perfil", 'I 3" x 8,48', "eixo=x"])
        for linha in (
            'secao perfil “I 3" x 8,48”',
            'secao perfil I 3" x 8,48',
            "secao perfil I 3'' x 8,48",
            "secao perfil I 3 x 8,48",
        ):
            with self.subTest(linha=linha):
                viga = bs.interpretar(f"viga 3\n{linha}\nmaterial aco\napoio 0 pino\napoio 3 rolete")
                self.assertEqual(viga.secao.nome, 'I 3" x 8,48')

    def test_todo_perfil_do_catalogo_passa_pelo_caminho_do_formulario(self):
        # O formulário escreve `secao perfil "<nome>" eixo=<eixo>`; nenhum
        # nome do catálogo pode quebrar essa linha, e a ida e volta do
        # modelo tem de devolver a mesma seção.
        from core import section_catalog as catalogo

        for nome, perfil in catalogo.listar_perfis().items():
            for eixo in ("x", "y"):
                with self.subTest(perfil=nome, eixo=eixo):
                    linha = f"secao perfil {bs.texto_entre_aspas(nome)} eixo={eixo}"
                    viga = bs.interpretar(
                        f"viga 3\n{linha}\nmaterial aco\napoio 0 pino\napoio 3 rolete\nP 1.5 1 baixo"
                    )
                    self.assertEqual(viga.secao, vb.secao_de_perfil_catalogo(perfil, eixo=eixo))
                    self.assertEqual(bs.interpretar(bs.gerar_script(viga)).secao, viga.secao)

    def test_formatar_numero_e_exato_e_legivel(self):
        for valor in (0.1, 4.0, -5.0, 1.5e-5, 4_000.0 / 3.0, 1e16, 123_456.789):
            with self.subTest(valor=valor):
                texto = bs.formatar_numero(valor)
                self.assertEqual(float(texto), valor)
                self.assertFalse(texto.endswith(".0"))
        self.assertEqual(bs.formatar_numero(4.0), "4")
        self.assertEqual(bs.formatar_numero(0.1), "0.1")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
