"""Testes da análise de vigas e eixos.

A referência de cada caso é a solução fechada clássica (Hibbeler/Shigley),
não um valor colhido do próprio programa: se o solver mudar e continuar
passando, é porque continua reproduzindo a teoria.
"""

import math
import unittest

from core import beam_analysis as vb
from core import beam_script as bs

E_MPA = 200_000.0
G_MPA = 77_000.0
L_MM = 6_000.0


class CasoDeViga(unittest.TestCase):
    """Base com comparação relativa.

    ``assertAlmostEqual`` compara com 7 casas *absolutas*, o que é inútil para
    momentos em N·mm (da ordem de 1e8): um erro de arredondamento de 1e-16
    relativo já reprova. ``assertProximo`` compara em escala.
    """

    def assertProximo(self, obtido, esperado, *, relativo=1e-9, msg=None):
        limite = relativo * max(abs(float(esperado)), 1.0)
        self.assertAlmostEqual(float(obtido), float(esperado), delta=limite, msg=msg)


def viga_padrao(**extras) -> vb.Viga:
    secao = vb.secao_retangular(100, 200)
    material = vb.MaterialViga("Aço", E_MPA, G_MPA, 250.0)
    parametros = {
        "comprimento_mm": L_MM,
        "secao": secao,
        "material": material,
        "apoios": (vb.Apoio(0.0, "pino"), vb.Apoio(L_MM, "rolete")),
    }
    parametros.update(extras)
    return vb.Viga(**parametros)


class SecoesTests(CasoDeViga):
    def test_retangular_reproduz_formulas_fechadas(self):
        secao = vb.secao_retangular(100, 200)
        self.assertAlmostEqual(secao.area_mm2, 20_000.0)
        self.assertProximo(secao.inercia_mm4, 100 * 200**3 / 12)
        self.assertProximo(secao.momento_estatico_mm3, 100 * 200**2 / 8)
        self.assertProximo(secao.modulo_resistencia_inferior_mm3, 100 * 200**2 / 6)

    def test_circular_tem_j_igual_ao_dobro_de_i(self):
        secao = vb.secao_circular_macica(60)
        self.assertProximo(secao.constante_torcao_mm4, 2 * secao.inercia_mm4)
        self.assertProximo(secao.modulo_torcao_mm3, math.pi * 60**3 / 16)

    def test_tubo_recusa_diametro_interno_maior(self):
        with self.assertRaises(ValueError):
            vb.secao_tubo_circular(50, 60)

    def test_perfil_i_tem_inercia_maior_que_retangulo_de_mesma_area(self):
        perfil = vb.secao_i_simetrica(300, 150, 8, 12)
        equivalente = vb.secao_retangular(perfil.area_mm2 / 300, 300)
        self.assertGreater(perfil.inercia_mm4, 0)
        self.assertProximo(perfil.area_mm2, equivalente.area_mm2)
        # A área do I está concentrada longe da linha neutra.
        self.assertGreater(perfil.inercia_mm4, equivalente.inercia_mm4)

    def test_secao_sem_caminho_de_cisalhamento_e_recusada(self):
        with self.assertRaises(ValueError):
            vb.SecaoViga(
                nome="inválida",
                area_mm2=100.0,
                inercia_mm4=1_000.0,
                c_superior_mm=10.0,
                c_inferior_mm=10.0,
                momento_estatico_mm3=0.0,
                espessura_cisalhamento_mm=0.0,
                constante_torcao_mm4=0.0,
                modulo_torcao_mm3=0.0,
            )

    def test_perfil_do_catalogo_usa_area_de_cisalhamento(self):
        from core import steel_sections as secoes

        perfil = secoes.obter_perfil("C ideal 200×75×20×3")
        secao = vb.secao_de_perfil_catalogo(perfil)
        self.assertProximo(secao.inercia_mm4, perfil.ix_mm4)
        self.assertProximo(secao.area_cisalhamento_mm2, perfil.area_cisalhamento_mm2)
        self.assertEqual(secao.momento_estatico_mm3, 0.0)


class FlexaoIsostaticaTests(CasoDeViga):
    def test_biapoiada_carga_central(self):
        carga = -20_000.0
        resultado = vb.analisar_viga(
            viga_padrao(cargas_pontuais=(vb.CargaPontual(L_MM / 2, carga),))
        )
        inercia = resultado.viga.secao.inercia_mm4
        self.assertProximo(resultado.extremos["momento"].valor, -carga * L_MM / 4)
        self.assertAlmostEqual(resultado.extremos["momento"].x_mm, L_MM / 2)
        self.assertAlmostEqual(
            resultado.extremos["flecha"].valor,
            carga * L_MM**3 / (48 * E_MPA * inercia),
        )
        self.assertAlmostEqual(resultado.reacoes[0].fy_N, -carga / 2)
        self.assertAlmostEqual(resultado.reacoes[1].fy_N, -carga / 2)
        self.assertEqual(resultado.grau_hiperestaticidade, 0)

    def test_biapoiada_uniformemente_distribuida(self):
        w = -15.0
        resultado = vb.analisar_viga(
            viga_padrao(cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, w),))
        )
        inercia = resultado.viga.secao.inercia_mm4
        self.assertProximo(resultado.extremos["momento"].valor, -w * L_MM**2 / 8)
        self.assertProximo(abs(resultado.extremos["cortante"].valor), abs(w) * L_MM / 2)
        self.assertAlmostEqual(
            resultado.extremos["flecha"].valor,
            5 * w * L_MM**4 / (384 * E_MPA * inercia),
        )

    def test_balanco_engastado_com_carga_na_ponta(self):
        carga = -20_000.0
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_pontuais=(vb.CargaPontual(L_MM, carga),),
            )
        )
        inercia = resultado.viga.secao.inercia_mm4
        self.assertProximo(resultado.extremos["momento"].valor, carga * L_MM)
        self.assertAlmostEqual(
            resultado.extremos["flecha"].valor, carga * L_MM**3 / (3 * E_MPA * inercia)
        )
        self.assertAlmostEqual(resultado.reacoes[0].fy_N, -carga)
        self.assertProximo(resultado.reacoes[0].mz_Nmm, -carga * L_MM)

    def test_carga_triangular_tem_maximo_em_l_sobre_raiz_de_tres(self):
        w = -12.0
        resultado = vb.analisar_viga(
            viga_padrao(cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, 0.0, w),))
        )
        self.assertProximo(
            abs(resultado.extremos["momento"].valor),
            abs(w) * L_MM**2 / (9 * math.sqrt(3)),
        )
        # A malha inclui a raiz de V(x) = 0, então o pico não depende do
        # refinamento da amostragem.
        self.assertAlmostEqual(resultado.extremos["momento"].x_mm, L_MM / math.sqrt(3), places=6)
        self.assertAlmostEqual(resultado.reacoes[0].fy_N, -w * L_MM / 6)
        self.assertAlmostEqual(resultado.reacoes[1].fy_N, -w * L_MM / 3)

    def test_momento_concentrado_gera_salto_de_valor_igual(self):
        aplicado = 30e6
        resultado = vb.analisar_viga(
            viga_padrao(momentos=(vb.MomentoConcentrado(L_MM / 2, aplicado),))
        )
        no_ponto = [
            ponto.momento_Nmm
            for ponto in resultado.pontos
            if abs(ponto.x_mm - L_MM / 2) < 1e-9
        ]
        self.assertEqual(len(no_ponto), 2)
        self.assertProximo(no_ponto[0] - no_ponto[1], aplicado)
        # Binário puro: as reações formam um par de forças opostas.
        self.assertAlmostEqual(resultado.reacoes[0].fy_N, aplicado / L_MM)
        self.assertAlmostEqual(resultado.reacoes[1].fy_N, -aplicado / L_MM)


class FlexaoHiperestaticaTests(CasoDeViga):
    def test_biengastada_com_distribuida(self):
        w = -15.0
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"), vb.Apoio(L_MM, "engaste")),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, w),),
            )
        )
        inercia = resultado.viga.secao.inercia_mm4
        self.assertProximo(resultado.extremos["momento"].valor, w * L_MM**2 / 12)
        self.assertAlmostEqual(
            resultado.extremos["flecha"].valor, w * L_MM**4 / (384 * E_MPA * inercia)
        )
        meio = min(resultado.pontos, key=lambda ponto: abs(ponto.x_mm - L_MM / 2))
        self.assertProximo(meio.momento_Nmm, -w * L_MM**2 / 24)
        self.assertEqual(resultado.grau_hiperestaticidade, 3)

    def test_continua_de_dois_vaos_iguais(self):
        vao, w = 5_000.0, -20.0
        resultado = vb.analisar_viga(
            viga_padrao(
                comprimento_mm=2 * vao,
                apoios=(
                    vb.Apoio(0.0, "pino"),
                    vb.Apoio(vao, "rolete"),
                    vb.Apoio(2 * vao, "rolete"),
                ),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, 2 * vao, w),),
            )
        )
        central = min(resultado.pontos, key=lambda ponto: abs(ponto.x_mm - vao))
        self.assertProximo(central.momento_Nmm, w * vao**2 / 8)
        self.assertAlmostEqual(resultado.reacoes[1].fy_N, -1.25 * w * vao)
        self.assertAlmostEqual(resultado.reacoes[0].fy_N, -0.375 * w * vao)


class RotulaTests(CasoDeViga):
    def test_momento_e_nulo_na_rotula(self):
        resultado = vb.analisar_viga(
            viga_padrao(
                comprimento_mm=9_000.0,
                apoios=(
                    vb.Apoio(0.0, "pino"),
                    vb.Apoio(6_000.0, "rolete"),
                    vb.Apoio(9_000.0, "rolete"),
                ),
                rotulas=(vb.Rotula(4_500.0),),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, 9_000.0, -10.0),),
            )
        )
        na_rotula = [
            ponto.momento_Nmm
            for ponto in resultado.pontos
            if abs(ponto.x_mm - 4_500.0) < 1e-9
        ]
        for momento in na_rotula:
            self.assertAlmostEqual(momento, 0.0, places=6)
        # Uma rótula consome exatamente um vínculo excedente.
        self.assertEqual(resultado.grau_hiperestaticidade, 0)

    def test_rotula_na_extremidade_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(viga_padrao(rotulas=(vb.Rotula(0.0),)))
        self.assertIn("extremidade", str(contexto.exception))

    def test_rotula_sobre_engaste_e_recusada(self):
        with self.assertRaises(ValueError):
            vb.analisar_viga(
                viga_padrao(
                    apoios=(
                        vb.Apoio(0.0, "pino"),
                        vb.Apoio(3_000.0, "engaste"),
                        vb.Apoio(L_MM, "rolete"),
                    ),
                    rotulas=(vb.Rotula(3_000.0),),
                )
            )


class AxialETorcaoTests(CasoDeViga):
    def test_tracao_pura(self):
        forca = 80_000.0
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_axiais=(vb.CargaAxial(L_MM, forca),),
            )
        )
        secao = resultado.viga.secao
        ponta = max(resultado.pontos, key=lambda ponto: ponto.x_mm)
        self.assertAlmostEqual(resultado.extremos["normal"].valor, forca)
        self.assertAlmostEqual(ponta.tensao_axial_MPa, forca / secao.area_mm2)
        self.assertAlmostEqual(
            ponta.deslocamento_axial_mm, forca * L_MM / (E_MPA * secao.area_mm2)
        )
        self.assertAlmostEqual(resultado.reacoes[0].fx_N, -forca)

    def test_torcao_pura(self):
        torque = 5e6
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"),),
                torques=(vb.Torque(L_MM, torque),),
            )
        )
        secao = resultado.viga.secao
        self.assertProximo(resultado.extremos["torque"].valor, torque)
        self.assertAlmostEqual(
            resultado.extremos["giro_torcao"].valor,
            torque * L_MM / (G_MPA * secao.constante_torcao_mm4),
        )
        self.assertAlmostEqual(
            resultado.extremos["tensao_torcao"].valor, torque / secao.modulo_torcao_mm3
        )
        self.assertProximo(resultado.reacoes[0].mt_Nmm, -torque)

    def test_carga_axial_sem_apoio_horizontal_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(
                    apoios=(vb.Apoio(0.0, "rolete"), vb.Apoio(L_MM, "rolete")),
                    cargas_axiais=(vb.CargaAxial(L_MM, 1_000.0),),
                )
            )
        self.assertIn("horizontal", str(contexto.exception))

    def test_par_de_torques_autoequilibrado_dispensa_apoio_torsional(self):
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "rolete"), vb.Apoio(L_MM, "rolete")),
                torques=(vb.Torque(2_000.0, 1e6), vb.Torque(4_000.0, -1e6)),
            )
        )
        self.assertProximo(abs(resultado.extremos["torque"].valor), 1e6)
        self.assertTrue(resultado.avisos)


class ApoioElasticoTests(CasoDeViga):
    def test_viga_sobre_duas_molas_iguais_reproduz_o_recalque(self):
        # Duas molas iguais sob carga central: cada uma recebe P/2 e recua
        # P/(2k). O deslocamento no meio é o recalque + a flecha da viga
        # biapoiada equivalente.
        carga, rigidez = -20_000.0, 500.0
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(
                    vb.Apoio(0.0, "mola", rigidez_vertical_N_mm=rigidez),
                    vb.Apoio(L_MM, "mola", rigidez_vertical_N_mm=rigidez),
                ),
                cargas_pontuais=(vb.CargaPontual(L_MM / 2, carga),),
            )
        )
        self.assertProximo(resultado.reacoes[0].fy_N, -carga / 2)
        self.assertProximo(resultado.reacoes[1].fy_N, -carga / 2)
        recalque = carga / (2 * rigidez)
        apoio_esquerdo = min(resultado.pontos, key=lambda ponto: ponto.x_mm)
        self.assertAlmostEqual(apoio_esquerdo.deslocamento_mm, recalque)

        inercia = resultado.viga.secao.inercia_mm4
        meio = min(resultado.pontos, key=lambda ponto: abs(ponto.x_mm - L_MM / 2))
        self.assertAlmostEqual(
            meio.deslocamento_mm,
            recalque + carga * L_MM**3 / (48 * E_MPA * inercia),
        )

    def test_mola_muito_rigida_converge_para_o_apoio_rigido(self):
        carga = -20_000.0
        rigida = vb.analisar_viga(
            viga_padrao(cargas_pontuais=(vb.CargaPontual(L_MM / 2, carga),))
        )
        elastica = vb.analisar_viga(
            viga_padrao(
                apoios=(
                    vb.Apoio(0.0, "mola", rigidez_vertical_N_mm=1e12),
                    vb.Apoio(L_MM, "mola", rigidez_vertical_N_mm=1e12),
                ),
                cargas_pontuais=(vb.CargaPontual(L_MM / 2, carga),),
            )
        )
        self.assertProximo(
            elastica.extremos["momento"].valor,
            rigida.extremos["momento"].valor,
            relativo=1e-6,
        )
        self.assertAlmostEqual(
            elastica.extremos["flecha"].valor,
            rigida.extremos["flecha"].valor,
            places=4,
        )

    def test_mola_sem_rigidez_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.Apoio(0.0, "mola")
        self.assertIn("kv", str(contexto.exception))

    def test_rigidez_em_grau_ja_travado_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.Apoio(0.0, "rolete", rigidez_vertical_N_mm=500.0)
        self.assertIn("mola", str(contexto.exception))
        with self.assertRaises(ValueError):
            vb.Apoio(0.0, "engaste", rigidez_rotacional_Nmm_rad=1e9)

    def test_mola_conta_como_reacao_no_grau_de_hiperestaticidade(self):
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(
                    vb.Apoio(0.0, "pino"),
                    vb.Apoio(L_MM / 2, "mola", rigidez_vertical_N_mm=800.0),
                    vb.Apoio(L_MM, "rolete"),
                ),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -15.0),),
            )
        )
        # pino (2) + mola (1) + rolete (1) - 3 equações = 1.
        self.assertEqual(resultado.grau_hiperestaticidade, 1)

    def test_script_aceita_apoio_elastico(self):
        viga = bs.interpretar(
            """
            viga 6
            secao retangular 100 200
            material aco
            apoio 0 pino
            apoio 6 mola kv=500
            q 0 6 15 baixo
            """
        )
        self.assertEqual(viga.apoios[1].tipo, "mola")
        self.assertAlmostEqual(viga.apoios[1].rigidez_vertical_N_mm, 500.0)
        reconstruida = bs.interpretar(bs.gerar_script(viga))
        self.assertAlmostEqual(reconstruida.apoios[1].rigidez_vertical_N_mm, 500.0)

    def test_rigidez_invalida_vira_erro_de_script(self):
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.interpretar(
                """
                viga 6
                secao retangular 100 200
                material aco
                apoio 0 pino
                apoio 6 mola kv=abc
                """
            )
        self.assertIn("kv", str(contexto.exception))


class TorcaoSemModuloTests(CasoDeViga):
    def test_torque_sem_modulo_de_torcao_e_recusado(self):
        secao = vb.SecaoViga(
            nome="sem Wt",
            area_mm2=1_000.0,
            inercia_mm4=1e6,
            c_superior_mm=25.0,
            c_inferior_mm=25.0,
            momento_estatico_mm3=0.0,
            espessura_cisalhamento_mm=0.0,
            constante_torcao_mm4=2e6,
            modulo_torcao_mm3=0.0,
            area_cisalhamento_mm2=800.0,
        )
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(secao=secao, torques=(vb.Torque(L_MM / 2, 1e6),))
            )
        self.assertIn("Wt", str(contexto.exception))


class CargasCombinadasTests(CasoDeViga):
    def test_flexao_axial_e_torcao_somam_em_von_mises(self):
        forca, axial, torque = -5_000.0, 40_000.0, 2e6
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_pontuais=(vb.CargaPontual(L_MM, forca),),
                cargas_axiais=(vb.CargaAxial(L_MM, axial),),
                torques=(vb.Torque(L_MM, torque),),
            )
        )
        secao = resultado.viga.secao
        sigma = axial / secao.area_mm2 + abs(forca) * L_MM * secao.c_inferior_mm / secao.inercia_mm4
        tau = torque / secao.modulo_torcao_mm3
        self.assertAlmostEqual(
            resultado.extremos["von_mises"].valor, math.sqrt(sigma**2 + 3 * tau**2)
        )
        self.assertAlmostEqual(
            resultado.fator_seguranca_escoamento, 250.0 / resultado.extremos["von_mises"].valor
        )

    def test_ponto_critico_reporta_o_par_sigma_tau_que_governou(self):
        resultado = vb.analisar_viga(
            viga_padrao(cargas_pontuais=(vb.CargaPontual(L_MM / 2, -20_000.0),))
        )
        critico = max(resultado.pontos, key=lambda ponto: ponto.von_mises_MPa)
        sigma, tau = vb.estado_no_ponto_critico(critico)
        self.assertAlmostEqual(critico.von_mises_MPa, math.sqrt(sigma**2 + 3 * tau**2))
        self.assertIn(critico.ponto_critico, {"Fibra superior", "Fibra inferior", "Linha neutra"})

    def test_peso_proprio_equivale_a_uma_distribuida(self):
        com_peso = vb.analisar_viga(viga_padrao(considerar_peso_proprio=True))
        secao = com_peso.viga.secao
        peso = secao.area_mm2 * 1e-6 * 7_850.0 * vb.GRAVIDADE_M_S2 / 1_000.0
        self.assertProximo(com_peso.extremos["momento"].valor, peso * L_MM**2 / 8)


class ValidacaoTests(CasoDeViga):
    def test_viga_sem_apoio_e_recusada(self):
        with self.assertRaises(ValueError):
            vb.analisar_viga(viga_padrao(apoios=()))

    def test_apoio_insuficiente_identifica_o_mecanismo(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(
                    apoios=(vb.Apoio(0.0, "rolete"),),
                    cargas_pontuais=(vb.CargaPontual(L_MM, -1_000.0),),
                )
            )
        self.assertIn("instável", str(contexto.exception))

    def test_carga_fora_da_viga_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                viga_padrao(cargas_pontuais=(vb.CargaPontual(L_MM * 2, -1_000.0),))
            )
        self.assertIn("fora da viga", str(contexto.exception))

    def test_dois_apoios_na_mesma_posicao_sao_recusados(self):
        with self.assertRaises(ValueError):
            vb.analisar_viga(
                viga_padrao(apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(0.0, "rolete")))
            )

    def test_distribuida_invertida_e_recusada(self):
        with self.assertRaises(ValueError):
            vb.CargaDistribuida(3_000.0, 1_000.0, -10.0)

    def test_equilibrio_global_fecha_em_todos_os_exemplos(self):
        for nome, script in bs.EXEMPLOS.items():
            with self.subTest(exemplo=nome):
                resultado = vb.analisar_viga(bs.interpretar(script))
                residuos = vb.conferir_equilibrio(resultado)
                self.assertLess(residuos["residuo_relativo"], 1e-9)


class VerificacaoDeFlechaTests(CasoDeViga):
    def test_criterio_usa_o_vao_entre_apoios(self):
        resultado = vb.analisar_viga(
            viga_padrao(cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -15.0),))
        )
        verificacao = vb.verificar_flecha(resultado, limite_vao=350.0)
        self.assertAlmostEqual(verificacao["vao_mm"], L_MM)
        self.assertAlmostEqual(verificacao["flecha_admissivel_mm"], L_MM / 350.0)
        self.assertEqual(
            verificacao["atende"],
            verificacao["flecha_mm"] <= verificacao["flecha_admissivel_mm"],
        )

    def test_balanco_usa_o_comprimento_total(self):
        resultado = vb.analisar_viga(
            viga_padrao(
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_pontuais=(vb.CargaPontual(L_MM, -5_000.0),),
            )
        )
        self.assertAlmostEqual(vb.verificar_flecha(resultado)["vao_mm"], L_MM)


class ScriptTests(CasoDeViga):
    def test_exemplo_minimo_e_interpretado(self):
        viga = bs.interpretar(
            """
            viga 6
            secao retangular 100 200
            material aco
            apoio 0 pino
            apoio 6 rolete
            q 0 6 15 baixo
            P 3 20 baixo
            """
        )
        self.assertAlmostEqual(viga.comprimento_mm, 6_000.0)
        self.assertEqual(len(viga.apoios), 2)
        # O sufixo "baixo" inverte o sinal do valor digitado.
        self.assertAlmostEqual(viga.cargas_pontuais[0].fy_N, -20_000.0)
        self.assertAlmostEqual(viga.cargas_distribuidas[0].w_inicial_N_mm, -15.0)

    def test_comentarios_e_separadores_sao_tolerados(self):
        viga = bs.interpretar(
            "viga 4  # comprimento\n"
            "secao circular 50\n"
            "material aco\n"
            "apoio 0, pino\n"
            "apoio 4; rolete\n"
            "P 2 -10\n"
        )
        self.assertEqual(len(viga.apoios), 2)
        self.assertAlmostEqual(viga.cargas_pontuais[0].fy_N, -10_000.0)

    def test_virgula_decimal_e_aceita(self):
        viga = bs.interpretar(
            "viga 4,5\nsecao circular 50\nmaterial aco\napoio 0 pino\napoio 4,5 rolete\n"
        )
        self.assertAlmostEqual(viga.comprimento_mm, 4_500.0)

    def test_perfil_do_catalogo_aceita_x_no_lugar_do_sinal_de_multiplicacao(self):
        viga = bs.interpretar(
            "viga 6\nsecao perfil C ideal 200x75x20x3\nmaterial aco\napoio 0 pino\napoio 6 rolete\n"
        )
        from core import steel_sections as secoes

        self.assertProximo(
            viga.secao.inercia_mm4, secoes.obter_perfil("C ideal 200×75×20×3").ix_mm4
        )

    def test_g_e_estimado_quando_nao_informado(self):
        viga = bs.interpretar(
            "viga 4\nsecao circular 50\nmaterial E=200\napoio 0 pino\napoio 4 rolete\n"
        )
        # G = E / (2(1+ν)) com ν = 0,3.
        self.assertAlmostEqual(viga.material.modulo_cisalhamento_MPa, 200_000.0 / 2.6)

    def test_erro_traz_o_numero_da_linha(self):
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.interpretar("viga 6\nsecao retangular 100 200\nmaterial aco\nP abc 10")
        self.assertEqual(contexto.exception.linha, 4)
        self.assertIn("Linha 4", str(contexto.exception))

    def test_comando_desconhecido_sugere_o_parecido(self):
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.interpretar("vigaa 6")
        self.assertIn("viga", str(contexto.exception))

    def test_modelo_incompleto_lista_o_que_falta(self):
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.interpretar("viga 6\nsecao retangular 100 200\nmaterial aco")
        self.assertIn("apoio", str(contexto.exception))

    def test_script_vazio_e_recusado(self):
        with self.assertRaises(bs.ErroDeScript):
            bs.interpretar("   \n\n")

    def test_todos_os_exemplos_resolvem(self):
        for nome, script in bs.EXEMPLOS.items():
            with self.subTest(exemplo=nome):
                resultado = vb.analisar_viga(bs.interpretar(script))
                self.assertGreater(len(resultado.pontos), 10)
                self.assertTrue(resultado.reacoes)

    def test_ida_e_volta_preserva_os_resultados(self):
        for nome, script in bs.EXEMPLOS.items():
            with self.subTest(exemplo=nome):
                original = bs.interpretar(script)
                reconstruida = bs.interpretar(bs.gerar_script(original))
                antes = vb.analisar_viga(original)
                depois = vb.analisar_viga(reconstruida)
                for chave, extremo in antes.extremos.items():
                    self.assertAlmostEqual(
                        extremo.valor,
                        depois.extremos[chave].valor,
                        delta=1e-9 * max(1.0, abs(extremo.valor)),
                        msg=f"{nome}: {chave}",
                    )


class TabelasTests(CasoDeViga):
    def test_tabela_de_diagramas_usa_unidades_de_engenharia(self):
        resultado = vb.analisar_viga(
            viga_padrao(cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, -15.0),))
        )
        linhas = vb.tabela_diagramas(resultado)
        self.assertAlmostEqual(linhas[0]["x (m)"], 0.0)
        self.assertAlmostEqual(linhas[-1]["x (m)"], L_MM / 1_000.0)
        self.assertAlmostEqual(max(abs(linha["V (kN)"]) for linha in linhas), 45.0)
        self.assertIn("Ponto crítico", linhas[0])

    def test_resumo_de_reacoes_converte_para_kn(self):
        resultado = vb.analisar_viga(
            viga_padrao(cargas_pontuais=(vb.CargaPontual(L_MM / 2, -20_000.0),))
        )
        resumo = vb.resumo_reacoes(resultado)
        self.assertEqual(len(resumo), 2)
        self.assertAlmostEqual(resumo[0]["Fy (kN)"], 10.0)
        self.assertEqual(resumo[0]["Apoio"], "pino")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
