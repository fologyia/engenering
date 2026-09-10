"""Testes do que guia o preenchimento do projeto.

A queixa que originou estes testes era de usabilidade: o cadastro exigia
sair da tela para descobrir o que faltava e voltar caçando o campo. O que
precisa ficar travado aqui é a **fonte única** — a interface e a validação
leem a mesma lista de campos — e o fato de que criar um projeto pelo caminho
normal não o deixa bloqueado por falta de campo.
"""

import unittest

from core.project_store import novo_projeto_documento
from core.project_validation import (
    CAMPOS_BASE,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RESPONSABILIDADE,
    estado_de_preenchimento,
    pendencias_de_preenchimento,
    validar_projeto,
)


def projeto_novo(**campos):
    return novo_projeto_documento(campos.pop("nome", "Projeto de teste"), **campos)


class FonteUnicaTests(unittest.TestCase):
    def test_estado_cobre_todos_os_campos_cobrados(self):
        estado = estado_de_preenchimento(projeto_novo())
        esperados = {
            campo
            for campo, _rotulo, _sev in (
                *CAMPOS_IDENTIFICACAO,
                *CAMPOS_RESPONSABILIDADE,
                *CAMPOS_BASE,
            )
        }
        self.assertEqual(set(estado), esperados)

    def test_severidades_batem_com_as_da_validacao(self):
        # Se a interface mostrasse "pendência" onde a validação gera
        # "bloqueio", ela estaria mentindo sobre o que impede a emissão.
        # O construtor exige nome; para exercitar a severidade do campo
        # "nome", ele é esvaziado depois da criação.
        vazio = projeto_novo()
        vazio["nome"] = ""
        achados = {
            achado["titulo"]: achado["severidade"]
            for achado in validar_projeto(vazio)["achados"]
        }
        for campo, rotulo, severidade in CAMPOS_IDENTIFICACAO:
            with self.subTest(campo=campo):
                titulo = f"Falta informar {rotulo}"
                if titulo in achados:
                    self.assertEqual(achados[titulo], severidade)

    def test_campo_preenchido_sai_das_pendencias(self):
        antes = {item["campo"] for item in pendencias_de_preenchimento(projeto_novo())}
        self.assertIn("objetivo", antes)
        com_objetivo = projeto_novo()
        com_objetivo["objetivo"] = "Verificar a viga"
        depois = {
            item["campo"] for item in pendencias_de_preenchimento(com_objetivo)
        }
        self.assertNotIn("objetivo", depois)

    def test_pendencias_vem_ordenadas_por_gravidade(self):
        pendencias = pendencias_de_preenchimento(projeto_novo())
        severidades = [item["severidade"] for item in pendencias]
        ordem = {"Bloqueio": 0, "Pendência": 1, "Atenção": 2}
        self.assertEqual(severidades, sorted(severidades, key=ordem.get))

    def test_campos_da_base_sao_lidos_de_base_projeto(self):
        projeto = projeto_novo()
        projeto["base_projeto"]["criterio_aceitacao"] = "NBR 8800"
        estado = estado_de_preenchimento(projeto)
        self.assertTrue(estado["criterio_aceitacao"]["preenchido"])
        self.assertEqual(estado["criterio_aceitacao"]["grupo"], "base")


class CriacaoDeProjetoTests(unittest.TestCase):
    def test_objetivo_pode_ser_informado_na_criacao(self):
        # Antes o construtor não aceitava objetivo, então todo projeto nascia
        # com um bloqueio que o formulário de criação nem mencionava.
        projeto = novo_projeto_documento(
            "Viga", codigo="PRJ-01", objetivo="Verificar a viga"
        )
        self.assertEqual(projeto["objetivo"], "Verificar a viga")

    def test_os_tres_campos_removem_os_bloqueios_de_identificacao(self):
        projeto = novo_projeto_documento(
            "Viga", codigo="PRJ-01", objetivo="Verificar a viga"
        )
        bloqueios = [
            achado
            for achado in validar_projeto(projeto)["achados"]
            if achado["severidade"] == "Bloqueio"
        ]
        self.assertEqual(
            [achado for achado in bloqueios if achado["categoria"] == "Identificação"],
            [],
        )

    def test_bloqueios_de_conteudo_permanecem_e_sao_de_outras_categorias(self):
        # O diálogo de criação promete resolver os bloqueios de CAMPO; os de
        # conteúdo (escopo, normas, cálculo) continuam e têm de ser
        # apresentados como tais, senão a promessa seria falsa.
        projeto = novo_projeto_documento(
            "Viga", codigo="PRJ-01", objetivo="Verificar a viga"
        )
        categorias = {
            achado["categoria"]
            for achado in validar_projeto(projeto)["achados"]
            if achado["severidade"] == "Bloqueio"
        }
        self.assertEqual(categorias, {"Escopo físico", "Normas", "Cálculos"})

    def test_projeto_sem_objetivo_continua_bloqueado(self):
        projeto = novo_projeto_documento("Viga", codigo="PRJ-01")
        titulos = [
            achado["titulo"]
            for achado in validar_projeto(projeto)["achados"]
            if achado["severidade"] == "Bloqueio"
        ]
        self.assertIn("Falta informar objetivo do projeto", titulos)


class IndiceDocumentalTests(unittest.TestCase):
    def test_indice_cresce_conforme_o_preenchimento(self):
        projeto = novo_projeto_documento("Viga", codigo="PRJ-01")
        inicial = validar_projeto(projeto)["indice_documental"]
        projeto["objetivo"] = "Verificar a viga"
        projeto["responsavel"] = "Eng. responsável"
        projeto["base_projeto"]["criterio_aceitacao"] = "NBR 8800"
        self.assertGreater(validar_projeto(projeto)["indice_documental"], inicial)

    def test_contagem_de_campos_do_painel_bate_com_o_estado(self):
        projeto = novo_projeto_documento("Viga", codigo="PRJ-01")
        estado = estado_de_preenchimento(projeto)
        pendentes = pendencias_de_preenchimento(projeto)
        preenchidos = sum(1 for dados in estado.values() if dados["preenchido"])
        self.assertEqual(preenchidos + len(pendentes), len(estado))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
