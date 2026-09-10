"""Testes das combinações de carga e da envoltória de vigas.

A envoltória é o ponto em que o modelo deixa de ser "uma viga com cargas" e
passa a ser "uma viga sob cenários": o que precisa ficar travado é que cada
combinação escala as cargas certas, que a faixa envelopada contém de fato
todas as combinações, e que um caso escrito errado não vira carga zerada em
silêncio.
"""

import unittest

from core import beam_analysis as vb
from core import beam_script as bs

L_MM = 8_000.0


def viga_de_tres_casos(**extras) -> vb.Viga:
    parametros = {
        "comprimento_mm": L_MM,
        "secao": vb.secao_retangular(150, 400),
        "material": vb.MaterialViga("Aço", 200_000.0, 77_000.0, 345.0),
        "apoios": (vb.Apoio(0.0, "pino"), vb.Apoio(L_MM, "rolete")),
        "cargas_distribuidas": (
            vb.CargaDistribuida(0.0, L_MM, -12.0),  # caso padrão: Permanente
            vb.CargaDistribuida(0.0, L_MM, -20.0, caso="Sobrecarga"),
            vb.CargaDistribuida(0.0, L_MM, 8.0, caso="Vento"),
        ),
    }
    parametros.update(extras)
    return vb.Viga(**parametros)


class CasosDeCargaTests(unittest.TestCase):
    def test_carga_sem_caso_e_permanente(self):
        carga = vb.CargaPontual(1_000.0, -5_000.0)
        self.assertEqual(carga.caso, vb.CASO_PADRAO)
        self.assertEqual(vb.CASO_PADRAO, "Permanente")

    def test_casos_declarados_preserva_a_ordem_de_aparicao(self):
        self.assertEqual(
            vb.casos_declarados(viga_de_tres_casos()),
            ("Permanente", "Sobrecarga", "Vento"),
        )

    def test_peso_proprio_entra_como_permanente(self):
        viga = vb.Viga(
            comprimento_mm=L_MM,
            secao=vb.secao_retangular(150, 400),
            material=vb.MaterialViga("Aço", 200_000.0, 77_000.0),
            apoios=(vb.Apoio(0.0, "pino"), vb.Apoio(L_MM, "rolete")),
            considerar_peso_proprio=True,
        )
        self.assertEqual(vb.casos_declarados(viga), ("Permanente",))

    def test_fator_ignora_maiusculas(self):
        combinacao = vb.CombinacaoCarga("C", {"Sobrecarga": 1.5})
        self.assertEqual(combinacao.fator("sobrecarga"), 1.5)
        self.assertEqual(combinacao.fator("SOBRECARGA"), 1.5)

    def test_caso_ausente_da_combinacao_tem_fator_zero(self):
        combinacao = vb.CombinacaoCarga("C", {"Permanente": 1.4})
        self.assertEqual(combinacao.fator("Vento"), 0.0)


class ViaCombinacaoTests(unittest.TestCase):
    def test_cargas_sao_escaladas_pelo_fator_do_seu_caso(self):
        combinada = vb.viga_da_combinacao(
            viga_de_tres_casos(),
            vb.CombinacaoCarga("ELU", {"Permanente": 1.4, "Sobrecarga": 1.5}),
        )
        intensidades = [
            carga.w_inicial_N_mm for carga in combinada.cargas_distribuidas
        ]
        self.assertAlmostEqual(intensidades[0], -12.0 * 1.4)
        self.assertAlmostEqual(intensidades[1], -20.0 * 1.5)
        # Vento não participa desta combinação.
        self.assertAlmostEqual(intensidades[2], 0.0)

    def test_geometria_e_apoios_nao_mudam(self):
        original = viga_de_tres_casos()
        combinada = vb.viga_da_combinacao(
            original, vb.CombinacaoCarga("ELU", {"Permanente": 1.4})
        )
        self.assertEqual(combinada.comprimento_mm, original.comprimento_mm)
        self.assertEqual(combinada.apoios, original.apoios)
        self.assertEqual(combinada.secao, original.secao)

    def test_peso_proprio_e_escalado_junto_com_o_permanente(self):
        viga = viga_de_tres_casos(considerar_peso_proprio=True)
        combinada = vb.viga_da_combinacao(
            viga, vb.CombinacaoCarga("ELU", {"Permanente": 1.4})
        )
        peso = viga.secao.area_mm2 * 1e-6 * 7_850.0 * vb.GRAVIDADE_M_S2 / 1_000.0
        # O peso próprio foi materializado como distribuída e escalado.
        self.assertFalse(combinada.considerar_peso_proprio)
        self.assertAlmostEqual(
            combinada.cargas_distribuidas[-1].w_inicial_N_mm, -peso * 1.4
        )

    def test_momento_da_combinacao_confere_com_a_formula_fechada(self):
        combinacao = vb.CombinacaoCarga("ELU", {"Permanente": 1.4, "Sobrecarga": 1.5})
        resultado = vb.analisar_viga(
            vb.viga_da_combinacao(viga_de_tres_casos(), combinacao)
        )
        w = 12.0 * 1.4 + 20.0 * 1.5
        self.assertAlmostEqual(
            resultado.extremos["momento"].valor,
            w * L_MM**2 / 8,
            delta=1e-9 * w * L_MM**2 / 8,
        )


class EnvoltoriaTests(unittest.TestCase):
    def combinacoes(self):
        return [
            vb.CombinacaoCarga("ELU_gravidade", {"Permanente": 1.4, "Sobrecarga": 1.5}),
            vb.CombinacaoCarga("ELU_vento", {"Permanente": 1.0, "Vento": 1.4}),
            vb.CombinacaoCarga("ELS_rara", {"Permanente": 1.0, "Sobrecarga": 1.0}),
        ]

    def test_envoltoria_contem_todas_as_combinacoes(self):
        envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), self.combinacoes())
        for ponto in envoltoria.pontos:
            for resultado in envoltoria.resultados.values():
                individual = vb.ponto_em(resultado, ponto.x_mm)
                self.assertLessEqual(
                    individual.momento_Nmm, ponto.momento_max_Nmm + 1e-6
                )
                self.assertGreaterEqual(
                    individual.momento_Nmm, ponto.momento_min_Nmm - 1e-6
                )
                self.assertLessEqual(
                    individual.deslocamento_mm, ponto.flecha_max_mm + 1e-9
                )

    def test_combinacao_governante_e_identificada(self):
        envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), self.combinacoes())
        nome, extremo = envoltoria.governante("momento")
        self.assertEqual(nome, "ELU_gravidade")
        w = 12.0 * 1.4 + 20.0 * 1.5
        self.assertAlmostEqual(extremo.valor, w * L_MM**2 / 8, delta=1.0)

    def test_todas_as_combinacoes_compartilham_a_malha(self):
        envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), self.combinacoes())
        # A envoltória só é comparável ponto a ponto se as abscissas forem as
        # mesmas; a interseção não pode ficar vazia nem degenerada.
        self.assertGreater(len(envoltoria.pontos), 30)
        for ponto in envoltoria.pontos:
            self.assertGreaterEqual(ponto.momento_max_Nmm, ponto.momento_min_Nmm)
            self.assertGreaterEqual(ponto.flecha_max_mm, ponto.flecha_min_mm)

    def test_uma_unica_combinacao_reproduz_a_analise_simples(self):
        combinacao = vb.CombinacaoCarga(
            "unica", {"Permanente": 1.0, "Sobrecarga": 1.0, "Vento": 1.0}
        )
        envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), [combinacao])
        direto = vb.analisar_viga(viga_de_tres_casos())
        self.assertAlmostEqual(
            envoltoria.governante("momento")[1].valor,
            direto.extremos["momento"].valor,
            delta=1e-6,
        )

    def test_caso_inexistente_e_recusado(self):
        with self.assertRaises(ValueError) as contexto:
            vb.analisar_envoltoria(
                viga_de_tres_casos(),
                [vb.CombinacaoCarga("X", {"Permanente": 1.4, "Neve": 1.5})],
            )
        self.assertIn("Neve", str(contexto.exception))

    def test_nomes_duplicados_sao_recusados(self):
        with self.assertRaises(ValueError):
            vb.analisar_envoltoria(
                viga_de_tres_casos(),
                [
                    vb.CombinacaoCarga("A", {"Permanente": 1.0}),
                    vb.CombinacaoCarga("A", {"Sobrecarga": 1.0}),
                ],
            )

    def test_lista_vazia_e_recusada(self):
        with self.assertRaises(ValueError):
            vb.analisar_envoltoria(viga_de_tres_casos(), [])

    def test_resumo_de_governantes_cobre_todas_as_grandezas(self):
        envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), self.combinacoes())
        resumo = vb.resumo_governantes(envoltoria)
        self.assertEqual(len(resumo), 5)
        for linha in resumo:
            self.assertIn(linha["Combinação governante"], envoltoria.resultados)
            self.assertGreaterEqual(linha["x (m)"], 0.0)

    def test_tabela_em_unidades_de_engenharia(self):
        envoltoria = vb.analisar_envoltoria(viga_de_tres_casos(), self.combinacoes())
        linhas = vb.tabela_envoltoria(envoltoria)
        self.assertAlmostEqual(linhas[0]["x (m)"], 0.0)
        self.assertAlmostEqual(linhas[-1]["x (m)"], L_MM / 1_000.0)
        self.assertIn("M máx (kN·m)", linhas[0])


class ScriptDeCombinacoesTests(unittest.TestCase):
    SCRIPT = """
    viga 8
    secao retangular 150 400
    material aco
    apoio 0 pino
    apoio 8 rolete
    q 0 8 12 baixo
    q 0 8 20 baixo caso=Sobrecarga
    q 0 8 8 cima caso=Vento
    combinacao ELU Permanente=1.4 Sobrecarga=1.5
    combinacao ELS Permanente=1.0 Sobrecarga=1.0
    """

    def test_casos_e_combinacoes_sao_lidos(self):
        viga = bs.interpretar(self.SCRIPT)
        self.assertEqual(
            vb.casos_declarados(viga), ("Permanente", "Sobrecarga", "Vento")
        )
        combinacoes = bs.combinacoes_do_script(self.SCRIPT)
        self.assertEqual([c.nome for c in combinacoes], ["ELU", "ELS"])
        self.assertAlmostEqual(combinacoes[0].fator("Sobrecarga"), 1.5)

    def test_grafia_do_caso_e_preservada(self):
        # O fator precisa casar com o `caso=` escrito nas cargas.
        combinacoes = bs.combinacoes_do_script(self.SCRIPT)
        self.assertIn("Sobrecarga", combinacoes[0].fatores)

    def test_combinacao_sem_fator_e_recusada(self):
        with self.assertRaises(bs.ErroDeScript) as contexto:
            bs.combinacoes_do_script("combinacao ELU")
        self.assertIn("fator", str(contexto.exception))

    def test_combinacao_duplicada_e_recusada(self):
        with self.assertRaises(bs.ErroDeScript):
            bs.combinacoes_do_script(
                "combinacao ELU Permanente=1.4\ncombinacao ELU Permanente=1.0"
            )

    def test_leitura_de_combinacoes_ignora_o_resto_do_modelo(self):
        # Serve para a página decidir se mostra a envoltória sem ter de
        # interpretar (e validar) o modelo inteiro antes.
        combinacoes = bs.combinacoes_do_script("combinacao X A=1.0\nlixo qualquer aqui")
        self.assertEqual(len(combinacoes), 1)

    def test_ida_e_volta_preserva_os_casos(self):
        viga = bs.interpretar(self.SCRIPT)
        reconstruida = bs.interpretar(bs.gerar_script(viga))
        self.assertEqual(
            vb.casos_declarados(reconstruida), vb.casos_declarados(viga)
        )

    def test_exemplo_de_envoltoria_resolve(self):
        script = bs.EXEMPLOS["Envoltória de combinações (viga de piso)"]
        envoltoria = vb.analisar_envoltoria(
            bs.interpretar(script), bs.combinacoes_do_script(script)
        )
        self.assertEqual(len(envoltoria.combinacoes), 3)
        self.assertEqual(envoltoria.governante("momento")[0], "ELU_gravidade")


class PonteComOProjetoTests(unittest.TestCase):
    def casos_e_combinacoes(self):
        casos = [
            {"id": "c1", "nome": "Peso próprio"},
            {"id": "c2", "nome": "Sobrecarga"},
        ]
        combinacoes = [
            {"nome": "ELU 1", "fatores": {"c1": 1.4, "c2": 1.5}, "ativo": True},
            {"nome": "Desativada", "fatores": {"c1": 1.0}, "ativo": False},
        ]
        return casos, combinacoes

    def test_fatores_por_id_viram_nomes_de_caso(self):
        casos, combinacoes = self.casos_e_combinacoes()
        linhas = bs.linhas_de_combinacoes_do_projeto(casos, combinacoes)
        self.assertEqual(len(linhas), 1)
        # Espaço vira "_" para o nome caber num único campo do modelo.
        self.assertIn("Peso_próprio=1.4", linhas[0])
        self.assertIn("Sobrecarga=1.5", linhas[0])
        self.assertTrue(linhas[0].startswith("combinacao ELU_1"))

    def test_combinacao_desativada_e_ignorada(self):
        casos, combinacoes = self.casos_e_combinacoes()
        linhas = bs.linhas_de_combinacoes_do_projeto(casos, combinacoes)
        self.assertFalse(any("Desativada" in linha for linha in linhas))

    def test_linhas_geradas_sao_interpretaveis(self):
        casos, combinacoes = self.casos_e_combinacoes()
        linhas = bs.linhas_de_combinacoes_do_projeto(casos, combinacoes)
        lidas = bs.combinacoes_do_script("\n".join(linhas))
        self.assertEqual(len(lidas), 1)
        self.assertAlmostEqual(lidas[0].fator("Peso_próprio"), 1.4)

    def test_id_sem_caso_correspondente_vira_o_proprio_id(self):
        linhas = bs.linhas_de_combinacoes_do_projeto(
            [], [{"nome": "C", "fatores": {"orfao": 1.0}}]
        )
        self.assertIn("orfao=1", linhas[0])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
