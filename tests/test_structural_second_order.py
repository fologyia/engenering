"""Segunda ordem, carga nocional e deslocabilidade no pórtico 2D.

A referência é a teoria clássica de coluna-viga: o balanço comprimido com
força horizontal na ponta tem momento na base ``H·L·tan(kL)/(kL)`` e a
carga crítica de Euler é ``π²EI/(KL)²``. O pórtico deslocável é conferido
por propriedades: a razão Δ2/Δ1 cresce com a compressão, a carga nocional
vale 0,3 % da gravitacional e H/400 lê o deslocamento de segunda ordem.
"""

import math
import unittest

from core import structural_2d as portico

E = 200_000.0
AREA = 5_000.0
INERCIA = 2.0e7  # mm⁴
L = 4_000.0


def coluna_balanco(compressao_N: float, horizontal_N: float, divisoes: int = 8):
    """Coluna vertical engastada na base, livre no topo, dividida em ``divisoes``."""
    nos = []
    for indice in range(divisoes + 1):
        topo = indice == divisoes
        nos.append(
            portico.NoPortico(
                id=indice + 1,
                x_mm=0.0,
                y_mm=L * indice / divisoes,
                restringe_x=indice == 0,
                restringe_y=indice == 0,
                restringe_rotacao=indice == 0,
                fx_N=horizontal_N if topo else 0.0,
                fy_N=-compressao_N if topo else 0.0,
            )
        )
    elementos = [
        portico.ElementoPortico(
            id=indice + 1,
            no_i=indice + 1,
            no_j=indice + 2,
            area_mm2=AREA,
            inercia_mm4=INERCIA,
            modulo_elasticidade_MPa=E,
        )
        for indice in range(divisoes)
    ]
    return nos, elementos


class SegundaOrdemTests(unittest.TestCase):
    def test_primeira_ordem_continua_igual_sem_opcoes(self):
        nos, elementos = coluna_balanco(0.0, 1_000.0, divisoes=1)
        resultado = portico.analisar_portico(nos, elementos)
        self.assertFalse(resultado.segunda_ordem)
        self.assertIsNone(resultado.fator_carga_critica)
        self.assertAlmostEqual(
            resultado.deslocamento_horizontal_1a_ordem_mm, 1_000.0 * L**3 / (3 * E * INERCIA)
        )

    def test_balanco_comprimido_reproduz_tan_kl_sobre_kl(self):
        euler = math.pi**2 * E * INERCIA / (2.0 * L) ** 2
        for fracao in (0.2, 0.5):
            with self.subTest(fracao=fracao):
                compressao, horizontal = fracao * euler, 1_000.0
                nos, elementos = coluna_balanco(compressao, horizontal)
                resultado = portico.analisar_portico(nos, elementos, segunda_ordem=True)
                k = math.sqrt(compressao / (E * INERCIA))
                momento_esperado = horizontal * L * math.tan(k * L) / (k * L)
                base = next(r for r in resultado.reacoes_nodais if r["no"] == 1)
                self.assertAlmostEqual(
                    abs(base["mz_Nmm"]), momento_esperado, delta=2e-3 * momento_esperado
                )
                flecha_esperada = horizontal * (math.tan(k * L) - k * L) / (E * INERCIA * k**3)
                self.assertAlmostEqual(
                    resultado.deslocamento_horizontal_2a_ordem_mm,
                    flecha_esperada,
                    delta=2e-3 * flecha_esperada,
                )
                self.assertGreater(resultado.razao_delta2_delta1, 1.0)
                self.assertGreaterEqual(resultado.iteracoes, 1)

    def test_fator_de_carga_critica_reproduz_euler_do_balanco(self):
        euler = math.pi**2 * E * INERCIA / (2.0 * L) ** 2
        nos, elementos = coluna_balanco(0.25 * euler, 1.0)
        resultado = portico.analisar_portico(nos, elementos)
        self.assertAlmostEqual(resultado.fator_carga_critica, 4.0, delta=4e-3)

    def test_carga_acima_da_critica_e_recusada_na_segunda_ordem(self):
        euler = math.pi**2 * E * INERCIA / (2.0 * L) ** 2
        nos, elementos = coluna_balanco(1.2 * euler, 1.0)
        with self.assertRaises(ValueError) as contexto:
            portico.analisar_portico(nos, elementos, segunda_ordem=True)
        self.assertIn("carga crítica", str(contexto.exception))
        primeira = portico.analisar_portico(nos, elementos)
        self.assertTrue(any("ultrapassam" in aviso for aviso in primeira.avisos))

    def test_tracao_enrijece_e_nao_gera_fator_critico(self):
        nos, elementos = coluna_balanco(-100_000.0, 1_000.0)
        resultado = portico.analisar_portico(nos, elementos, segunda_ordem=True)
        self.assertIsNone(resultado.fator_carga_critica)
        self.assertLess(resultado.razao_delta2_delta1, 1.0)

    def test_esforcos_de_extremidade_fecham_o_equilibrio_do_no_em_segunda_ordem(self):
        euler = math.pi**2 * E * INERCIA / (2.0 * L) ** 2
        nos, elementos = coluna_balanco(0.5 * euler, 1_000.0, divisoes=4)
        resultado = portico.analisar_portico(nos, elementos, segunda_ordem=True)
        esforcos = {item["elemento"]: item for item in resultado.esforcos_elementos}
        # No nó interno 3, o momento que o elemento 2 entrega tem de ser o que
        # o elemento 3 recebe: soma nula (sem momento aplicado no nó).
        soma = esforcos[2]["Mj_Nmm"] + esforcos[3]["Mi_Nmm"]
        escala = max(abs(esforcos[2]["Mj_Nmm"]), 1.0)
        self.assertAlmostEqual(soma, 0.0, delta=1e-9 * escala)


def portal(
    compressao_por_coluna_N: float,
    horizontal_N: float,
    altura_mm: float = 4_000.0,
    vao_mm: float = 5_000.0,
):
    """Dois pilares engastados na base ligados por uma viga: nós móveis."""
    nos = [
        portico.NoPortico(1, 0.0, 0.0, True, True, True),
        portico.NoPortico(2, 0.0, altura_mm, fx_N=horizontal_N, fy_N=-compressao_por_coluna_N),
        portico.NoPortico(3, vao_mm, altura_mm, fy_N=-compressao_por_coluna_N),
        portico.NoPortico(4, vao_mm, 0.0, True, True, True),
    ]
    elementos = [
        portico.ElementoPortico(1, 1, 2, AREA, INERCIA, E),
        portico.ElementoPortico(2, 2, 3, AREA, 4 * INERCIA, E),
        portico.ElementoPortico(3, 3, 4, AREA, INERCIA, E),
    ]
    return nos, elementos


class DeslocabilidadeTests(unittest.TestCase):
    def test_razao_delta2_delta1_cresce_com_a_compressao_e_classifica(self):
        leve = portico.analisar_portico(*portal(20_000.0, 5_000.0), segunda_ordem=True)
        pesado = portico.analisar_portico(*portal(400_000.0, 5_000.0), segunda_ordem=True)
        self.assertGreater(pesado.razao_delta2_delta1, leve.razao_delta2_delta1)
        self.assertIn("deslocabilidade", leve.classificacao_deslocabilidade)
        self.assertEqual(portico.classificar_deslocabilidade(1.05), "pequena deslocabilidade")
        self.assertEqual(portico.classificar_deslocabilidade(1.25), "média deslocabilidade")
        self.assertEqual(portico.classificar_deslocabilidade(1.6), "grande deslocabilidade")

    def test_b2_aproxima_a_razao_exata(self):
        resultado = portico.analisar_portico(*portal(200_000.0, 5_000.0), segunda_ordem=True)
        self.assertIsNotNone(resultado.coeficiente_b2)
        # B2 é a estimativa de norma da amplificação; deve ficar próximo de Δ2/Δ1.
        self.assertAlmostEqual(resultado.coeficiente_b2, resultado.razao_delta2_delta1, delta=0.15)
        self.assertAlmostEqual(resultado.carga_gravitacional_total_N, 400_000.0)
        self.assertAlmostEqual(resultado.carga_horizontal_total_N, 5_000.0)

    def test_carga_nocional_vale_a_fracao_da_gravitacional(self):
        sem = portico.analisar_portico(*portal(100_000.0, 0.0))
        com = portico.analisar_portico(
            *portal(100_000.0, 0.0), carga_nocional=portico.CARGA_NOCIONAL_PADRAO
        )
        self.assertEqual(sem.deslocamento_horizontal_1a_ordem_mm, 0.0)
        self.assertAlmostEqual(com.carga_nocional_total_N, 0.003 * 200_000.0)
        self.assertGreater(com.deslocamento_horizontal_1a_ordem_mm, 0.0)
        invertida = portico.analisar_portico(
            *portal(100_000.0, 0.0),
            carga_nocional=portico.CARGA_NOCIONAL_PADRAO,
            sentido_nocional=-1,
        )
        self.assertAlmostEqual(invertida.carga_horizontal_total_N, -com.carga_horizontal_total_N)

    def test_reducao_de_rigidez_amplia_o_deslocamento(self):
        integral = portico.analisar_portico(*portal(100_000.0, 5_000.0))
        reduzida = portico.analisar_portico(*portal(100_000.0, 5_000.0), reducao_rigidez=0.8)
        self.assertAlmostEqual(
            reduzida.deslocamento_horizontal_1a_ordem_mm,
            integral.deslocamento_horizontal_1a_ordem_mm / 0.8,
            delta=1e-9 * integral.deslocamento_horizontal_1a_ordem_mm,
        )
        self.assertEqual(reduzida.reducao_rigidez, 0.8)

    def test_media_deslocabilidade_pede_rigidez_reduzida(self):
        # Compressão alta o bastante para Δ2/Δ1 cair na faixa média.
        resultado = None
        for compressao in (100_000.0, 200_000.0, 300_000.0, 400_000.0, 500_000.0):
            candidato = portico.analisar_portico(*portal(compressao, 5_000.0), segunda_ordem=True)
            if candidato.classificacao_deslocabilidade.startswith("média"):
                resultado = candidato
                break
        self.assertIsNotNone(resultado, "nenhuma compressão testada deu média deslocabilidade")
        self.assertTrue(any("80 %" in aviso for aviso in resultado.avisos))
        com_reducao = portico.analisar_portico(
            *portal(resultado.carga_gravitacional_total_N / 2, 5_000.0),
            segunda_ordem=True,
            reducao_rigidez=0.8,
        )
        self.assertFalse(any("80 %" in aviso for aviso in com_reducao.avisos))

    def test_verificacao_h_400_usa_a_segunda_ordem(self):
        resultado = portico.analisar_portico(*portal(200_000.0, 20_000.0), segunda_ordem=True)
        verificacao = portico.verificar_deslocamento_horizontal(resultado, divisor=400.0)
        self.assertAlmostEqual(verificacao["limite_mm"], 4_000.0 / 400.0)
        self.assertAlmostEqual(
            verificacao["deslocamento_mm"], resultado.deslocamento_horizontal_2a_ordem_mm
        )
        self.assertEqual(verificacao["ordem"], "2ª ordem")
        self.assertEqual(
            verificacao["atende"], verificacao["deslocamento_mm"] <= verificacao["limite_mm"]
        )
        primeira = portico.verificar_deslocamento_horizontal(
            portico.analisar_portico(*portal(200_000.0, 20_000.0)), altura_mm=3_000.0, divisor=300.0
        )
        self.assertEqual(primeira["criterio"], "H/300")
        self.assertAlmostEqual(primeira["limite_mm"], 10.0)


if __name__ == "__main__":
    unittest.main()
