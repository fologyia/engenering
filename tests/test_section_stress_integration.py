"""Testes do núcleo compartilhado de tensões e do repasse entre módulos.

O valor destes testes está em travar a *concordância* entre partes do
programa que antes calculavam a mesma coisa em separado: o assistente de
cargas e a análise de vigas precisam devolver a mesma tensão para a mesma
seção, e o estado plano que sai da viga precisa ser o mesmo contrato que o
Círculo de Mohr e a Análise estática já consomem.
"""

import math
import unittest

from core import beam_analysis as vb
from core import load_to_stress as cargas
from core import section_stress as ss
from core.sensitivity import sugerir_de_registro

E_MPA = 200_000.0
G_MPA = 77_000.0


class NucleoCompartilhadoTests(unittest.TestCase):
    def test_secao_de_viga_satisfaz_o_protocolo(self):
        secao = vb.secao_retangular(100, 200)
        esforcos = ss.EsforcosSecao(normal_N=10_000.0, momento_Nmm=5e6)
        # Sem herança nem adaptação: a SecaoViga é aceita diretamente.
        tensoes = ss.tensoes_combinadas(esforcos, secao)
        self.assertAlmostEqual(tensoes.axial_MPa, 10_000.0 / secao.area_mm2)

    def test_momento_positivo_comprime_a_fibra_superior(self):
        secao = vb.secao_retangular(100, 200)
        tensoes = ss.tensoes_combinadas(ss.EsforcosSecao(momento_Nmm=5e6), secao)
        self.assertLess(tensoes.flexao_superior_MPa, 0.0)
        self.assertGreater(tensoes.flexao_inferior_MPa, 0.0)
        self.assertAlmostEqual(
            tensoes.flexao_inferior_MPa, 5e6 * 100.0 / secao.inercia_mm4
        )

    def test_cisalhamento_cai_para_a_area_quando_nao_ha_momento_estatico(self):
        com_q = ss.PropriedadesSecao(
            area_mm2=2_000.0,
            inercia_mm4=1e7,
            c_superior_mm=50.0,
            c_inferior_mm=50.0,
            momento_estatico_mm3=125_000.0,
            espessura_cisalhamento_mm=10.0,
        )
        sem_q = ss.PropriedadesSecao(
            area_mm2=2_000.0,
            inercia_mm4=1e7,
            c_superior_mm=50.0,
            c_inferior_mm=50.0,
            area_cisalhamento_mm2=1_000.0,
        )
        esforcos = ss.EsforcosSecao(cortante_N=20_000.0)
        self.assertAlmostEqual(
            ss.tensao_cisalhamento(esforcos, com_q),
            20_000.0 * 125_000.0 / (1e7 * 10.0),
        )
        self.assertAlmostEqual(ss.tensao_cisalhamento(esforcos, sem_q), 20.0)

    def test_torcao_usa_o_modulo_de_torcao(self):
        secao = vb.secao_circular_macica(60)
        tensoes = ss.tensoes_combinadas(ss.EsforcosSecao(torque_Nmm=2e6), secao)
        self.assertAlmostEqual(tensoes.torcao_MPa, 16.0 * 2e6 / (math.pi * 60**3))

    def test_ponto_critico_e_o_de_maior_von_mises(self):
        secao = vb.secao_retangular(100, 200)
        tensoes = ss.tensoes_combinadas(
            ss.EsforcosSecao(momento_Nmm=5e7, cortante_N=1_000.0), secao
        )
        self.assertEqual(tensoes.critico.nome, ss.NOME_INFERIOR)
        for ponto in tensoes.pontos:
            self.assertLessEqual(
                ponto.von_mises_MPa, tensoes.critico.von_mises_MPa + 1e-9
            )

    def test_ponto_inexistente_e_recusado(self):
        secao = vb.secao_retangular(100, 200)
        tensoes = ss.tensoes_combinadas(ss.EsforcosSecao(), secao)
        with self.assertRaises(KeyError):
            tensoes.ponto("fibra do meio")

    def test_na_linha_neutra_cortante_e_torcao_somam_em_modulo(self):
        # Num eixo, τ de V e τ de T são paralelas na linha neutra: de um
        # lado da seção somam, do outro subtraem. O sinal relativo entre V
        # e T é só convenção de eixos — não pode reduzir a tensão de projeto.
        secao = vb.secao_circular_macica(60)
        mesmo_sinal = ss.tensoes_combinadas(
            ss.EsforcosSecao(cortante_N=10_000.0, torque_Nmm=1.5e6), secao
        )
        sinais_opostos = ss.tensoes_combinadas(
            ss.EsforcosSecao(cortante_N=10_000.0, torque_Nmm=-1.5e6), secao
        )
        neutra_a = mesmo_sinal.ponto(ss.NOME_NEUTRA)
        neutra_b = sinais_opostos.ponto(ss.NOME_NEUTRA)
        esperado = abs(mesmo_sinal.cisalhamento_MPa) + abs(mesmo_sinal.torcao_MPa)
        self.assertAlmostEqual(abs(neutra_a.tau_MPa), esperado)
        self.assertAlmostEqual(abs(neutra_b.tau_MPa), esperado)
        self.assertAlmostEqual(neutra_a.von_mises_MPa, neutra_b.von_mises_MPa)
        # O sinal segue a parcela dominante (aqui a torção), para o estado
        # plano repassado ao Círculo de Mohr manter a orientação.
        self.assertGreater(abs(mesmo_sinal.torcao_MPa), abs(mesmo_sinal.cisalhamento_MPa))
        self.assertLess(neutra_b.tau_MPa, 0.0)

    def test_von_mises_da_viga_nao_depende_do_sentido_do_torque(self):
        # Eixo biapoiado com carga transversal e torque: inverter o sentido
        # do torque não muda a física, então não pode mudar o pior ponto.
        def eixo(sentido: float) -> vb.ResultadoViga:
            return vb.analisar_viga(
                vb.Viga(
                    comprimento_mm=1_000.0,
                    secao=vb.secao_circular_macica(40),
                    material=vb.MaterialViga("Aço", E_MPA, G_MPA, 350.0),
                    apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(1_000.0, "rolete")),
                    cargas_pontuais=(vb.CargaPontual(500.0, -30_000.0),),
                    torques=(vb.Torque(0.0, sentido * 2e6), vb.Torque(1_000.0, -sentido * 2e6)),
                )
            )

        direto, invertido = eixo(1.0), eixo(-1.0)
        self.assertAlmostEqual(
            direto.extremos["von_mises"].valor, invertido.extremos["von_mises"].valor
        )
        for a, b in zip(direto.pontos, invertido.pontos, strict=True):
            self.assertAlmostEqual(a.von_mises_MPa, b.von_mises_MPa, places=9)


class ConcordanciaEntreModulosTests(unittest.TestCase):
    """A mesma seção precisa dar a mesma resposta nos dois caminhos."""

    def test_eixo_do_assistente_bate_com_a_viga(self):
        diametro, comprimento = 60.0, 1_200.0
        forca, torque = -8_000.0, 1.5e6
        # Balanço com carga na ponta: o momento no engaste é conhecido.
        resultado = vb.analisar_viga(
            vb.Viga(
                comprimento_mm=comprimento,
                secao=vb.secao_circular_macica(diametro),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA, 350.0),
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_pontuais=(vb.CargaPontual(comprimento, forca),),
                torques=(vb.Torque(comprimento, torque),),
            )
        )
        engaste = vb.ponto_em(resultado, 0.0)
        momento = abs(engaste.momento_Nmm)

        # O assistente pergunta ao usuário de que lado está a fibra; a viga
        # sabe pelo sinal de M. Num balanço o momento no engaste é negativo,
        # ou seja, quem traciona é a fibra superior.
        self.assertLess(engaste.momento_Nmm, 0.0)
        tracionada, comprimida = ss.NOME_SUPERIOR, ss.NOME_INFERIOR

        for face, ponto in (("tracionada", tracionada), ("comprimida", comprimida)):
            with self.subTest(face=face):
                pelo_assistente = cargas.eixo_circular_macico(
                    diametro_mm=diametro,
                    forca_axial_N=0.0,
                    momento_fletor_Nmm=momento,
                    torque_Nmm=torque,
                    face_flexao=face,
                )
                pela_viga = vb.estado_plano_da_secao(resultado, 0.0, ponto=ponto)
                self.assertAlmostEqual(
                    pela_viga.sigma_x, pelo_assistente.sigma_x, places=9
                )
                self.assertAlmostEqual(
                    pela_viga.tau_xy, pelo_assistente.tau_xy, places=9
                )
                self.assertEqual(pela_viga.sigma_y, 0.0)

    def test_viga_retangular_do_assistente_bate_na_fibra_inferior(self):
        base, altura, comprimento = 100.0, 200.0, 4_000.0
        w = -15.0
        resultado = vb.analisar_viga(
            vb.Viga(
                comprimento_mm=comprimento,
                secao=vb.secao_retangular(base, altura),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA, 250.0),
                apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(comprimento, "rolete")),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, comprimento, w),),
            )
        )
        meio = vb.ponto_em(resultado, comprimento / 2.0)
        pelo_assistente = cargas.viga_retangular(
            base,
            altura,
            -altura / 2.0,  # fibra inferior
            0.0,
            meio.momento_Nmm,
            meio.cortante_N,
        )
        self.assertAlmostEqual(
            pelo_assistente.sigma_x, meio.tensao_normal_inferior_MPa, places=9
        )


class RepasseTests(unittest.TestCase):
    def viga_exemplo(self) -> vb.ResultadoViga:
        return vb.analisar_viga(
            vb.Viga(
                comprimento_mm=6_000.0,
                secao=vb.secao_retangular(100, 200),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA, 250.0),
                apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(6_000.0, "rolete")),
                cargas_pontuais=(vb.CargaPontual(3_000.0, -20_000.0),),
            )
        )

    def test_ponto_em_escolhe_o_lado_mais_solicitado_da_descontinuidade(self):
        resultado = self.viga_exemplo()
        # Sob a carga concentrada há dois valores de V; o repasse deve levar
        # o de maior von Mises, não o primeiro da lista.
        no_ponto = [p for p in resultado.pontos if abs(p.x_mm - 3_000.0) < 1e-9]
        self.assertEqual(len(no_ponto), 2)
        escolhido = vb.ponto_em(resultado, 3_000.0)
        self.assertAlmostEqual(
            escolhido.von_mises_MPa, max(p.von_mises_MPa for p in no_ponto)
        )

    def test_ponto_em_aceita_posicao_intermediaria(self):
        resultado = self.viga_exemplo()
        ponto = vb.ponto_em(resultado, 1_234.0)
        self.assertLess(abs(ponto.x_mm - 1_234.0), 200.0)

    def test_estado_plano_usa_o_contrato_dos_outros_modulos(self):
        resultado = self.viga_exemplo()
        estado = vb.estado_plano_da_secao(resultado)
        self.assertIsInstance(estado, cargas.EstadoPlanoCalculado)
        self.assertEqual(estado.sigma_y, 0.0)
        self.assertTrue(estado.descricao)
        self.assertTrue(estado.hipoteses)
        # Por padrão leva a seção mais solicitada.
        critico = max(resultado.pontos, key=lambda p: p.von_mises_MPa)
        self.assertAlmostEqual(estado.sigma_x, critico.sigma_critico_MPa)
        self.assertAlmostEqual(estado.tau_xy, critico.tau_critico_MPa)

    def test_estado_plano_aceita_um_ponto_especifico(self):
        resultado = self.viga_exemplo()
        superior = vb.estado_plano_da_secao(resultado, 3_000.0, ponto=ss.NOME_SUPERIOR)
        inferior = vb.estado_plano_da_secao(resultado, 3_000.0, ponto=ss.NOME_INFERIOR)
        # Seção simétrica sem esforço axial: as fibras são opostas.
        self.assertAlmostEqual(superior.sigma_x, -inferior.sigma_x)

    def test_secoes_notaveis_apontam_para_dentro_da_barra(self):
        resultado = self.viga_exemplo()
        notaveis = vb.secoes_notaveis(resultado)
        self.assertIn("Seção mais solicitada (von Mises)", notaveis)
        for nome, x_mm in notaveis.items():
            with self.subTest(secao=nome):
                self.assertGreaterEqual(x_mm, 0.0)
                self.assertLessEqual(x_mm, resultado.viga.comprimento_mm)

    def test_eixo_girante_tem_flexao_totalmente_alternada(self):
        resultado = self.viga_exemplo()
        secao = resultado.viga.secao
        girando = vb.amplitudes_de_fadiga(resultado, 3_000.0, eixo_girante=True)
        momento = abs(vb.ponto_em(resultado, 3_000.0).momento_Nmm)
        self.assertAlmostEqual(
            girando["sigma_alternada_MPa"],
            momento * secao.c_inferior_mm / secao.inercia_mm4,
        )
        self.assertAlmostEqual(girando["sigma_media_MPa"], 0.0)

    def test_viga_fixa_nao_inventa_ciclo(self):
        resultado = self.viga_exemplo()
        parada = vb.amplitudes_de_fadiga(resultado, 3_000.0, eixo_girante=False)
        self.assertEqual(parada["sigma_alternada_MPa"], 0.0)
        # O momento estático vira tensão média, não amplitude.
        self.assertGreater(parada["sigma_media_MPa"], 0.0)

    def test_carga_axial_entra_como_tensao_media_no_eixo_girante(self):
        resultado = vb.analisar_viga(
            vb.Viga(
                comprimento_mm=1_200.0,
                secao=vb.secao_circular_macica(60),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA, 350.0),
                apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(1_200.0, "rolete")),
                cargas_pontuais=(vb.CargaPontual(600.0, -8_000.0),),
                cargas_axiais=(vb.CargaAxial(1_200.0, 25_000.0),),
            )
        )
        amplitudes = vb.amplitudes_de_fadiga(resultado, 600.0, eixo_girante=True)
        area = resultado.viga.secao.area_mm2
        self.assertAlmostEqual(amplitudes["sigma_media_MPa"], 25_000.0 / area)
        self.assertGreater(amplitudes["sigma_alternada_MPa"], 0.0)


class SensibilidadeTests(unittest.TestCase):
    def test_registro_de_viga_e_importavel_pela_sensibilidade(self):
        registro = {
            "modulo_id": "vigas_eixos",
            "entradas": {"material": {"escoamento_MPa": 250.0}},
            "resultados": {
                "tensao_normal_extrema_MPa": 180.0,
                "tensao_torcao_maxima_MPa": 40.0,
            },
        }
        sugestao = sugerir_de_registro(registro)
        self.assertIsNotNone(sugestao)
        self.assertEqual(sugestao["modelo_id"], "seguranca_vm")
        self.assertAlmostEqual(sugestao["entradas"]["sigma_x_MPa"], 180.0)
        self.assertAlmostEqual(sugestao["entradas"]["tau_xy_MPa"], 40.0)
        self.assertAlmostEqual(sugestao["entradas"]["Sy_MPa"], 250.0)

    def test_registro_sem_material_nao_quebra(self):
        registro = {
            "modulo_id": "vigas_eixos",
            "entradas": {},
            "resultados": {"tensao_normal_extrema_MPa": 100.0},
        }
        sugestao = sugerir_de_registro(registro)
        self.assertIsNotNone(sugestao)
        self.assertIsNone(sugestao["entradas"]["Sy_MPa"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
