"""Testes dos provedores de seção do memorial.

`report_plugins` é o ponto de extensão que permite um módulo novo entrar no
memorial sem alterar o orquestrador — e até agora não tinha teste próprio.
O caso central aqui é o de ponta a ponta: uma viga calculada de verdade,
registrada no projeto, precisa chegar ao memorial com a seção que a governou
e com a combinação que a produziu.
"""

import unittest

from core import beam_analysis as vb
from core import beam_script as bs
from core.project_report import SECOES_RELATORIO, montar_modelo_relatorio
from core.report_plugins import (
    ProvedorSecaoRelatorio,
    listar_provedores,
    registrar_provedor,
    titulos_secoes_extensao,
)
from core.technical_modules import obter_modulo
from core.technical_records import criar_registro_tecnico


def projeto_minimo(*registros) -> dict:
    return {
        "nome": "Projeto de teste",
        "codigo": "PT-1",
        "objetivo": "Verificar a integração do memorial",
        "descricao": "Projeto usado apenas nos testes",
        "registros_tecnicos": list(registros),
    }


def registro_de_viga(script: str, *, titulo="Viga do mezanino", com_envoltoria=False):
    """Registra uma viga calculada de verdade, não um dicionário inventado."""
    viga = bs.interpretar(script)
    resultado = vb.analisar_viga(viga)
    verificacao = vb.verificar_flecha(resultado)
    extremos = resultado.extremos

    resultados = {
        "reacoes": vb.resumo_reacoes(resultado),
        "cortante_maximo_kN": extremos["cortante"].valor / 1_000.0,
        "cortante_maximo_x_m": extremos["cortante"].x_mm / 1_000.0,
        "momento_maximo_kNm": extremos["momento"].valor / 1e6,
        "momento_maximo_x_m": extremos["momento"].x_mm / 1_000.0,
        "normal_maximo_kN": extremos["normal"].valor / 1_000.0,
        "torque_maximo_kNm": extremos["torque"].valor / 1e6,
        "flecha_maxima_mm": extremos["flecha"].valor,
        "flecha_maxima_x_m": extremos["flecha"].x_mm / 1_000.0,
        "tensao_normal_extrema_MPa": extremos["tensao_normal"].valor,
        "von_mises_maximo_MPa": extremos["von_mises"].valor,
        "fator_seguranca_escoamento": resultado.fator_seguranca_escoamento,
        "fator_seguranca_minimo": 1.5,
        "flecha_admissivel_mm": verificacao["flecha_admissivel_mm"],
        "criterio_flecha": verificacao["criterio"],
        "grau_hiperestaticidade": resultado.grau_hiperestaticidade,
    }
    if com_envoltoria:
        envoltoria = vb.analisar_envoltoria(viga, bs.combinacoes_do_script(script))
        resultados["envoltoria_governantes"] = vb.resumo_governantes(envoltoria)
        resultados["envoltoria_combinacoes"] = [
            {"nome": item.nome, "fatores": item.fatores}
            for item in envoltoria.combinacoes
        ]

    return criar_registro_tecnico(
        modulo="Vigas e eixos",
        modulo_id="vigas_eixos",
        titulo=titulo,
        status="Atende",
        resumo="Análise linear de barra reta",
        entradas={
            "comprimento_mm": viga.comprimento_mm,
            "secao": {"nome": viga.secao.nome},
            "material": {"nome": viga.material.nome, "fonte": viga.material.fonte},
            "apoios": [
                {"x_mm": apoio.x_mm, "tipo": apoio.tipo} for apoio in viga.apoios
            ],
        },
        resultados=resultados,
        conclusao="Verificação concluída",
    )


SCRIPT_SIMPLES = """
viga 6
secao retangular 150 300
material catalogo ASTM A36 aço estrutural
apoio 0 pino
apoio 6 rolete
q 0 6 15 baixo
"""

SCRIPT_COMBINADO = """
viga 8
secao retangular 200 500
material catalogo ASTM A572 grau 50
apoio 0 pino
apoio 8 rolete
q 0 8 12 baixo
q 0 8 20 baixo caso=Sobrecarga
combinacao ELU Permanente=1.4 Sobrecarga=1.5
combinacao ELS Permanente=1.0 Sobrecarga=1.0
"""


class RegistroDeProvedoresTests(unittest.TestCase):
    def test_provedor_de_vigas_esta_registrado_apos_os_registros(self):
        ids = [item.id for item in listar_provedores(apos="registros")]
        self.assertIn("vigas_eixos", ids)

    def test_titulo_entra_no_catalogo_de_secoes(self):
        self.assertIn("vigas_eixos", titulos_secoes_extensao())
        self.assertIn("vigas_eixos", SECOES_RELATORIO)

    def test_contrato_do_modulo_aponta_para_o_provedor(self):
        # O campo existe para ligar módulo e seção do memorial; se ele
        # apontasse para um provedor inexistente, ninguém perceberia.
        modulo = obter_modulo("vigas_eixos")
        self.assertEqual(modulo.provedor_relatorio, "vigas_eixos")
        self.assertIn(modulo.provedor_relatorio, titulos_secoes_extensao())

    def test_provedor_duplicado_e_recusado(self):
        with self.assertRaises(ValueError):
            registrar_provedor(
                ProvedorSecaoRelatorio(
                    id="vigas_eixos",
                    titulo="Duplicado",
                    apos="registros",
                    ordem=1,
                    construir=lambda projeto, contexto: {},
                )
            )


class SecaoDeVigasTests(unittest.TestCase):
    def secao(self, projeto) -> dict:
        modelo = montar_modelo_relatorio(projeto)
        for secao in modelo["secoes"]:
            if "Vigas e eixos" in secao.get("titulo", ""):
                return secao
        self.fail("seção de vigas ausente do memorial")

    def test_projeto_sem_vigas_gera_secao_vazia_sem_quebrar(self):
        secao = self.secao(projeto_minimo())
        self.assertIn("0 análise(s)", " ".join(secao["paragrafos"]))
        for tabela in secao["tabelas"]:
            self.assertTrue(tabela["linhas"])

    def test_viga_registrada_aparece_com_a_secao_governante(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        texto = str(secao)
        self.assertIn("Viga do mezanino", texto)
        self.assertIn("Retangular", texto)
        # M = wL²/8 = 15 × 6² / 8 = 67,5 kN·m, no meio do vão.
        self.assertIn("67,5", texto)
        self.assertIn("x = 3", texto)

    def test_reacoes_entram_na_tabela(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        tabela = next(t for t in secao["tabelas"] if "Reações" in t["legenda"])
        self.assertEqual(len(tabela["linhas"]), 2)
        # wL/2 = 45 kN em cada apoio.
        self.assertTrue(any("45" in str(celula) for celula in tabela["linhas"][0]))

    def test_material_rastreavel_chega_ao_memorial(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertIn("Catálogo orientativo", str(secao))

    def test_criterio_de_flecha_aparece_com_a_situacao(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        tabela = next(t for t in secao["tabelas"] if "Verificação" in t["legenda"])
        celula = tabela["linhas"][0][-1]
        self.assertIn("L/350", celula)
        self.assertIn(celula.splitlines()[-1], {"Atende", "Excedida"})

    def test_envoltoria_vira_tabela_de_combinacoes_governantes(self):
        secao = self.secao(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        tabela = next(t for t in secao["tabelas"] if "Envoltória" in t["legenda"])
        self.assertTrue(any("ELU" in str(linha) for linha in tabela["linhas"]))
        self.assertIn("governa cada grandeza", " ".join(secao["paragrafos"]))

    def test_sem_combinacoes_a_tabela_de_envoltoria_nao_aparece(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertFalse(any("Envoltória" in t["legenda"] for t in secao["tabelas"]))

    def test_varias_barras_sao_listadas_juntas(self):
        secao = self.secao(
            projeto_minimo(
                registro_de_viga(SCRIPT_SIMPLES, titulo="Viga A"),
                registro_de_viga(SCRIPT_COMBINADO, titulo="Viga B", com_envoltoria=True),
            )
        )
        tabela = next(t for t in secao["tabelas"] if "Barras analisadas" in t["legenda"])
        self.assertEqual(len(tabela["linhas"]), 2)
        self.assertIn("2 análise(s)", " ".join(secao["paragrafos"]))

    def test_registro_de_outro_modulo_e_ignorado(self):
        alheio = criar_registro_tecnico(
            modulo="Análise estática",
            modulo_id="analise_estatica",
            titulo="Estado plano",
            status="Atende",
            resumo="",
            entradas={},
            resultados={"von_mises_MPa": 100.0},
        )
        secao = self.secao(projeto_minimo(alheio, registro_de_viga(SCRIPT_SIMPLES)))
        self.assertIn("1 análise(s)", " ".join(secao["paragrafos"]))
        self.assertNotIn("Estado plano", str(secao))

    def test_registro_incompleto_nao_derruba_o_memorial(self):
        # Registros antigos ou truncados precisam degradar para "não
        # informado" em vez de impedir a emissão do memorial inteiro.
        truncado = criar_registro_tecnico(
            modulo="Vigas e eixos",
            modulo_id="vigas_eixos",
            titulo="Registro antigo",
            status="Calculado",
            resumo="",
            entradas={},
            resultados={},
        )
        secao = self.secao(projeto_minimo(truncado))
        self.assertIn("Registro antigo", str(secao))
        self.assertIn("Não informado", str(secao))

    def test_nota_declara_os_limites_do_modelo(self):
        secao = self.secao(projeto_minimo(registro_de_viga(SCRIPT_SIMPLES)))
        self.assertIn("P–Δ", secao["nota"])
        self.assertIn("flambagem", secao["nota"])


class LarguraDasTabelasTests(unittest.TestCase):
    def test_larguras_batem_com_a_largura_util_da_pagina(self):
        # Todas as tabelas do memorial somam 9360 twips; uma soma diferente
        # desalinha a coluna no Word em relação às demais seções.
        modelo = montar_modelo_relatorio(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        for secao in modelo["secoes"]:
            for tabela in secao.get("tabelas", []):
                larguras = tabela.get("larguras")
                if not larguras:
                    continue
                with self.subTest(tabela=tabela.get("legenda")):
                    self.assertEqual(sum(larguras), 9_360)
                    self.assertEqual(len(larguras), len(tabela["cabecalhos"]))

    def test_cada_linha_tem_o_numero_de_colunas_do_cabecalho(self):
        modelo = montar_modelo_relatorio(
            projeto_minimo(registro_de_viga(SCRIPT_COMBINADO, com_envoltoria=True))
        )
        for secao in modelo["secoes"]:
            for tabela in secao.get("tabelas", []):
                esperado = len(tabela["cabecalhos"])
                for linha in tabela["linhas"]:
                    with self.subTest(tabela=tabela.get("legenda")):
                        self.assertEqual(len(linha), esperado)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
