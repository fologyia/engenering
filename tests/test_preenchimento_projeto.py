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
    CAMPOS_COMPONENTE,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RESPONSABILIDADE,
    diagnostico_componente,
    diagnostico_norma,
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


class DiagnosticoPorLinhaTests(unittest.TestCase):
    """As tabelas avisam o que falta em cada linha, ali mesmo.

    Antes, um componente sem material só aparecia como pendência depois de
    sair da tela e abrir a Central de Validação.
    """

    def test_componente_completo_nao_gera_aviso(self):
        completo = {
            "tag": "CV-204-SUP-01",
            "descricao": "Suporte do transportador",
            "material": "ASTM A572 Gr. 50",
            "fonte_material": "Certificado MTR 88213",
        }
        self.assertEqual(diagnostico_componente(completo), [])

    def test_campos_cobrados_do_componente_geram_aviso(self):
        vazio: dict = {}
        mensagens = [mensagem for _sev, mensagem in diagnostico_componente(vazio)]
        for _campo, rotulo, _sev in CAMPOS_COMPONENTE:
            with self.subTest(campo=rotulo):
                self.assertIn(f"{rotulo} ausente", mensagens)

    def test_material_sem_fonte_e_apontado(self):
        # O caso que separa um valor de catálogo de um dado do lote.
        item = {
            "tag": "T1",
            "descricao": "Item",
            "material": "ASTM A36",
            "fonte_material": "",
        }
        severidades = dict(
            (mensagem, severidade) for severidade, mensagem in diagnostico_componente(item)
        )
        self.assertTrue(any("sem a fonte" in mensagem for mensagem in severidades))
        for mensagem, severidade in severidades.items():
            if "sem a fonte" in mensagem:
                self.assertEqual(severidade, "Atenção")

    def test_sem_material_nao_cobra_a_fonte(self):
        # Cobrar a fonte de um material que não existe seria ruído.
        item = {"tag": "T1", "descricao": "Item"}
        mensagens = [mensagem for _sev, mensagem in diagnostico_componente(item)]
        self.assertFalse(any("sem a fonte" in mensagem for mensagem in mensagens))

    def test_norma_completa_nao_gera_aviso(self):
        completa = {"codigo": "ABNT NBR 8800", "edicao": "2024", "conferida": True}
        self.assertEqual(diagnostico_norma(completa), [])

    def test_norma_nao_conferida_e_pendencia(self):
        item = {"codigo": "ABNT NBR 8800", "edicao": "2024", "conferida": False}
        self.assertEqual(diagnostico_norma(item), [("Pendência", "ainda não conferida no documento-fonte")])

    def test_norma_sem_edicao_e_atencao(self):
        item = {"codigo": "ABNT NBR 8800", "conferida": True}
        self.assertEqual(
            diagnostico_norma(item), [("Atenção", "edição ou revisão não informada")]
        )

    def test_linha_semeada_de_norma_nasce_pendente_de_conferencia(self):
        # O botão de exemplo não pode marcar como conferida uma norma que o
        # usuário não abriu; a pendência tem de continuar aparecendo.
        semeada = {
            "codigo": "ABNT NBR 8800",
            "edicao": "2024",
            "escopo": "Dimensionamento das barras",
            "obrigatoria": True,
            "conferida": False,
        }
        problemas = diagnostico_norma(semeada)
        self.assertEqual(len(problemas), 1)
        self.assertIn("conferida", problemas[0][1])

    def test_diagnostico_bate_com_a_validacao_completa(self):
        # Se a tabela dissesse uma coisa e a Central de Validação outra, o
        # usuário perderia a confiança nas duas.
        projeto = novo_projeto_documento("Viga", codigo="PRJ-01", objetivo="x")
        projeto["componentes"] = [{"tag": "T1", "descricao": "", "material": ""}]
        achados = [
            achado
            for achado in validar_projeto(projeto)["achados"]
            if achado["categoria"] == "Escopo físico"
            and achado["titulo"].startswith("T1:")
        ]
        da_linha = diagnostico_componente(projeto["componentes"][0])
        self.assertEqual(len(achados), len(da_linha))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
