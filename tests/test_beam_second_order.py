"""Testes do efeito de segunda ordem (P–Δ) e da carga crítica elástica.

A referência é a teoria clássica: a carga crítica sai de `π²EI/(KL)²` e a
amplificação da flecha de `1/(1 − P/Pcr)`. O que precisa ficar travado é
que a compressão amolece a barra, que a tração a enrijece, que o modelo
recusa a análise quando a carga já passou da crítica, e que ligar a segunda
ordem **não** altera nada quando não há esforço normal.
"""

import math
import unittest
from dataclasses import replace

from core import beam_analysis as vb
from core import beam_script as bs

E_MPA = 200_000.0
G_MPA = 77_000.0
L_MM = 4_000.0
W_N_MM = -5.0


def secao() -> vb.SecaoViga:
    return vb.secao_retangular(100, 200)


def carga_critica_euler(k: float = 1.0) -> float:
    return math.pi**2 * E_MPA * secao().inercia_mm4 / (k * L_MM) ** 2


def coluna_viga(compressao_N: float, **extras) -> vb.Viga:
    parametros = {
        "comprimento_mm": L_MM,
        "secao": secao(),
        "material": vb.MaterialViga("Aço", E_MPA, G_MPA, 250.0),
        "apoios": (vb.Apoio(0.0, "pino"), vb.Apoio(L_MM, "rolete")),
        "cargas_distribuidas": (vb.CargaDistribuida(0.0, L_MM, W_N_MM),),
        "cargas_axiais": (vb.CargaAxial(L_MM, -compressao_N),),
    }
    parametros.update(extras)
    return vb.Viga(**parametros)


class CargaCriticaTests(unittest.TestCase):
    def test_biapoiada_reproduz_euler(self):
        critica = carga_critica_euler()
        resultado = vb.analisar_viga(coluna_viga(critica * 0.25))
        # O fator multiplica as cargas axiais: 0,25 Pcr cabe 4 vezes em Pcr.
        self.assertAlmostEqual(resultado.fator_carga_critica, 4.0, places=2)

    def test_engaste_livre_reproduz_k_igual_a_dois(self):
        resultado = vb.analisar_viga(
            vb.Viga(
                comprimento_mm=L_MM,
                secao=secao(),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA),
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_pontuais=(vb.CargaPontual(L_MM, -100.0),),
                cargas_axiais=(vb.CargaAxial(L_MM, -1_000.0),),
            )
        )
        esperado = carga_critica_euler(k=2.0) / 1_000.0
        self.assertAlmostEqual(
            resultado.fator_carga_critica, esperado, delta=esperado * 1e-3
        )

    def test_o_fator_escala_com_a_compressao(self):
        critica = carga_critica_euler()
        meia = vb.analisar_viga(coluna_viga(critica * 0.25)).fator_carga_critica
        dobro = vb.analisar_viga(coluna_viga(critica * 0.50)).fator_carga_critica
        self.assertAlmostEqual(meia / dobro, 2.0, places=6)

    def test_sem_compressao_nao_ha_carga_critica(self):
        sem_axial = vb.analisar_viga(
            vb.Viga(
                comprimento_mm=L_MM,
                secao=secao(),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA),
                apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(L_MM, "rolete")),
                cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, W_N_MM),),
            )
        )
        self.assertIsNone(sem_axial.fator_carga_critica)

    def test_tracao_pura_nao_tem_carga_critica(self):
        tracionada = vb.analisar_viga(coluna_viga(-carga_critica_euler() * 0.4))
        self.assertIsNone(tracionada.fator_carga_critica)

    def test_compressao_proxima_da_critica_gera_aviso(self):
        resultado = vb.analisar_viga(coluna_viga(carga_critica_euler() * 0.3))
        self.assertTrue(resultado.avisos)
        self.assertIn("segunda ordem", resultado.avisos[0])

    def test_compressao_folgada_nao_polui_com_aviso(self):
        resultado = vb.analisar_viga(coluna_viga(carga_critica_euler() * 0.01))
        self.assertEqual(resultado.avisos, ())


class AmplificacaoTests(unittest.TestCase):
    def test_flecha_segue_a_amplificacao_classica(self):
        critica = carga_critica_euler()
        sem_axial = vb.analisar_viga(coluna_viga(0.0, considerar_segunda_ordem=True))
        base = sem_axial.extremos["flecha"].valor
        for fracao in (0.2, 0.4, 0.6):
            with self.subTest(fracao=fracao):
                resultado = vb.analisar_viga(
                    coluna_viga(critica * fracao, considerar_segunda_ordem=True)
                )
                esperado = base / (1.0 - fracao)
                # 1/(1−P/Pcr) é ele próprio uma aproximação; o desvio cresce
                # com a carga e fica em torno de 0,2% em 0,6 Pcr.
                self.assertAlmostEqual(
                    resultado.extremos["flecha"].valor,
                    esperado,
                    delta=abs(esperado) * 5e-3,
                )

    def test_compressao_amplifica_tambem_o_momento(self):
        critica = carga_critica_euler()
        primeira = vb.analisar_viga(coluna_viga(critica * 0.4))
        segunda = vb.analisar_viga(
            coluna_viga(critica * 0.4, considerar_segunda_ordem=True)
        )
        self.assertGreater(
            abs(segunda.extremos["momento"].valor),
            abs(primeira.extremos["momento"].valor),
        )

    def test_momento_reproduz_a_solucao_fechada_de_coluna_viga(self):
        # Biapoiada com w uniforme e compressão P (Timoshenko & Gere):
        # M_máx = (wL²/8) · 2(sec u − 1)/u², com u = (L/2)·√(P/EI).
        ei = E_MPA * secao().inercia_mm4
        critica = carga_critica_euler()
        for fracao in (0.2, 0.4, 0.6, 0.8):
            with self.subTest(fracao=fracao):
                u = (L_MM / 2.0) * math.sqrt(fracao * critica / ei)
                esperado = abs(W_N_MM) * L_MM**2 / 8.0 * 2.0 * (1.0 / math.cos(u) - 1.0) / u**2
                resultado = vb.analisar_viga(
                    coluna_viga(critica * fracao, considerar_segunda_ordem=True)
                )
                # Com a malha padrão (8 divisões) o desvio fica abaixo de 0,02 %;
                # antes da recuperação consistente ele chegava a 1 %.
                self.assertAlmostEqual(
                    abs(resultado.extremos["momento"].valor),
                    esperado,
                    delta=esperado * 2e-4,
                )

    def test_balanco_reproduz_a_amplificacao_tan_kl_sobre_kl(self):
        # Engastada-livre com F transversal e P na ponta: M_base = F·L·tan(kL)/(kL).
        ei = E_MPA * secao().inercia_mm4
        forca = -100.0
        for fracao in (0.2, 0.5):
            with self.subTest(fracao=fracao):
                compressao = fracao * carga_critica_euler(k=2.0)
                k = math.sqrt(compressao / ei)
                esperado = abs(forca) * L_MM * math.tan(k * L_MM) / (k * L_MM)
                resultado = vb.analisar_viga(
                    vb.Viga(
                        comprimento_mm=L_MM,
                        secao=secao(),
                        material=vb.MaterialViga("Aço", E_MPA, G_MPA),
                        apoios=(vb.Apoio(0.0, "engaste"),),
                        cargas_pontuais=(vb.CargaPontual(L_MM, forca),),
                        cargas_axiais=(vb.CargaAxial(L_MM, -compressao),),
                        considerar_segunda_ordem=True,
                    )
                )
                self.assertAlmostEqual(
                    abs(resultado.extremos["momento"].valor), esperado, delta=esperado * 2e-4
                )
                # A reação de momento do engaste e o diagrama no mesmo ponto
                # são o mesmo número: os esforços recuperados estão em
                # equilíbrio com os nós na configuração deformada.
                self.assertAlmostEqual(
                    abs(resultado.reacoes[0].mz_Nmm), esperado, delta=esperado * 2e-4
                )

    def test_diagramas_de_segunda_ordem_sao_continuos_entre_elementos(self):
        # Sem a parcela geométrica nos esforços de extremidade, V e M davam
        # um salto em cada nó interno da malha refinada.
        resultado = vb.analisar_viga(
            coluna_viga(carga_critica_euler() * 0.6, considerar_segunda_ordem=True)
        )
        por_x: dict[float, list[vb.PontoDiagrama]] = {}
        for ponto in resultado.pontos:
            por_x.setdefault(round(ponto.x_mm, 6), []).append(ponto)
        escala_v = abs(resultado.extremos["cortante"].valor)
        escala_m = abs(resultado.extremos["momento"].valor)
        nos_internos = [x for x, grupo in por_x.items() if len(grupo) > 1 and 0 < x < L_MM]
        self.assertGreaterEqual(len(nos_internos), 7)
        for x in nos_internos:
            esquerda, direita = por_x[x][0], por_x[x][-1]
            self.assertAlmostEqual(
                esquerda.cortante_N, direita.cortante_N, delta=1e-9 * escala_v
            )
            self.assertAlmostEqual(
                esquerda.momento_Nmm, direita.momento_Nmm, delta=1e-9 * escala_m
            )

    def test_equilibrio_fecha_com_o_momento_p_delta(self):
        resultado = vb.analisar_viga(
            vb.Viga(
                comprimento_mm=L_MM,
                secao=secao(),
                material=vb.MaterialViga("Aço", E_MPA, G_MPA),
                apoios=(vb.Apoio(0.0, "engaste"),),
                cargas_pontuais=(vb.CargaPontual(L_MM, -100.0),),
                cargas_axiais=(vb.CargaAxial(L_MM, -0.3 * carga_critica_euler(k=2.0)),),
                considerar_segunda_ordem=True,
            )
        )
        residuos = vb.conferir_equilibrio(resultado)
        # O momento P·Δ não é zero — e é exatamente o que fecha ΣM.
        self.assertGreater(abs(residuos["momento_p_delta_Nmm"]), 1e3)
        self.assertLess(residuos["residuo_relativo"], 1e-9)

    def test_compressao_acima_da_critica_sem_segunda_ordem_avisa(self):
        resultado = vb.analisar_viga(coluna_viga(carga_critica_euler() * 1.2))
        self.assertLess(resultado.fator_carga_critica, 1.0)
        self.assertTrue(any("ultrapassa" in aviso for aviso in resultado.avisos))

    def test_tracao_enrijece_a_barra(self):
        critica = carga_critica_euler()
        sem_axial = vb.analisar_viga(coluna_viga(0.0, considerar_segunda_ordem=True))
        tracionada = vb.analisar_viga(
            coluna_viga(-critica * 0.4, considerar_segunda_ordem=True)
        )
        self.assertLess(
            abs(tracionada.extremos["flecha"].valor),
            abs(sem_axial.extremos["flecha"].valor),
        )

    def test_sem_esforco_normal_a_segunda_ordem_nao_muda_nada(self):
        viga = vb.Viga(
            comprimento_mm=L_MM,
            secao=secao(),
            material=vb.MaterialViga("Aço", E_MPA, G_MPA),
            apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(L_MM, "rolete")),
            cargas_distribuidas=(vb.CargaDistribuida(0.0, L_MM, W_N_MM),),
        )
        primeira = vb.analisar_viga(viga)
        segunda = vb.analisar_viga(replace(viga, considerar_segunda_ordem=True))
        for chave in ("momento", "cortante", "flecha"):
            with self.subTest(grandeza=chave):
                self.assertAlmostEqual(
                    primeira.extremos[chave].valor,
                    segunda.extremos[chave].valor,
                    delta=1e-9 * max(1.0, abs(primeira.extremos[chave].valor)),
                )

    def test_carga_acima_da_critica_e_recusada(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_viga(
                coluna_viga(carga_critica_euler() * 1.05, considerar_segunda_ordem=True)
            )
        self.assertIn("carga crítica", str(contexto.exception))

    def test_o_resultado_declara_se_a_segunda_ordem_entrou(self):
        self.assertFalse(vb.analisar_viga(coluna_viga(1_000.0)).segunda_ordem)
        self.assertTrue(
            vb.analisar_viga(
                coluna_viga(1_000.0, considerar_segunda_ordem=True)
            ).segunda_ordem
        )


class MalhaTests(unittest.TestCase):
    def test_refino_nao_altera_a_primeira_ordem(self):
        # A solução nodal de Euler-Bernoulli é exata em qualquer malha; se o
        # refino mudasse V, M ou a flecha, algo estaria errado na montagem.
        grosseira = vb.analisar_viga(coluna_viga(1_000.0, divisoes_por_trecho=1))
        fina = vb.analisar_viga(coluna_viga(1_000.0, divisoes_por_trecho=24))
        for chave in ("momento", "cortante", "flecha"):
            with self.subTest(grandeza=chave):
                self.assertAlmostEqual(
                    grosseira.extremos[chave].valor,
                    fina.extremos[chave].valor,
                    delta=1e-6 * max(1.0, abs(fina.extremos[chave].valor)),
                )

    def test_malha_e_refinada_quando_ha_carga_axial(self):
        # Com um elemento por trecho a carga crítica de uma coluna biapoiada
        # sai 21,6% alta — e alto é o lado inseguro.
        com_axial = vb.analisar_viga(coluna_viga(1_000.0, divisoes_por_trecho=1))
        self.assertGreater(len(com_axial.pontos), 8 * 40)

    def test_refino_manual_melhora_a_carga_critica(self):
        critica = carga_critica_euler()
        fina = vb.analisar_viga(
            coluna_viga(critica * 0.25, divisoes_por_trecho=32)
        ).fator_carga_critica
        self.assertAlmostEqual(fina, 4.0, places=4)


class ScriptTests(unittest.TestCase):
    def test_comando_liga_a_segunda_ordem(self):
        viga = bs.interpretar(
            """
            viga 4
            secao retangular 100 200
            material aco
            apoio 0 pino
            apoio 4 rolete
            q 0 4 5 baixo
            N 4 500 compressao
            segunda_ordem
            """
        )
        self.assertTrue(viga.considerar_segunda_ordem)

    def test_divisoes_sao_lidas(self):
        viga = bs.interpretar(
            """
            viga 4
            secao retangular 100 200
            material aco
            apoio 0 pino
            apoio 4 rolete
            divisoes 12
            """
        )
        self.assertEqual(viga.divisoes_por_trecho, 12)

    def test_divisoes_invalidas_sao_recusadas(self):
        for ruim in ("divisoes 0", "divisoes 2.5", "divisoes"):
            with self.subTest(linha=ruim):
                with self.assertRaises(bs.ErroDeScript):
                    bs.interpretar(
                        "viga 4\nsecao retangular 100 200\nmaterial aco\n"
                        "apoio 0 pino\napoio 4 rolete\n" + ruim
                    )

    def test_ida_e_volta_preserva_a_segunda_ordem(self):
        script = bs.EXEMPLOS["Coluna-viga com efeito P–Δ (segunda ordem)"]
        viga = bs.interpretar(script)
        reconstruida = bs.interpretar(bs.gerar_script(viga))
        self.assertTrue(reconstruida.considerar_segunda_ordem)
        self.assertAlmostEqual(
            vb.analisar_viga(viga).extremos["flecha"].valor,
            vb.analisar_viga(reconstruida).extremos["flecha"].valor,
            places=9,
        )

    def test_exemplo_amplifica_a_flecha(self):
        script = bs.EXEMPLOS["Coluna-viga com efeito P–Δ (segunda ordem)"]
        com = vb.analisar_viga(bs.interpretar(script))
        sem = vb.analisar_viga(
            replace(bs.interpretar(script), considerar_segunda_ordem=False)
        )
        amplificacao = com.extremos["flecha"].valor / sem.extremos["flecha"].valor
        self.assertGreater(amplificacao, 1.0)
        # A amplificação tem de bater com 1/(1 − 1/fator_crítico).
        self.assertAlmostEqual(
            amplificacao, 1.0 / (1.0 - 1.0 / sem.fator_carga_critica), places=2
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
