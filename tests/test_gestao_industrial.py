"""Testes da camada de gestão industrial: prazos, fluxo, diff, registros e carteira.

Os módulos aqui não fazem cálculo de engenharia; fazem gestão do projeto.
O que se testa é a leitura que eles produzem — um item vencido é vencido,
um projeto com bloqueio não pode ser emitido, uma revisão comparada mostra
exatamente o que mudou — porque é nessa leitura que a pessoa vai confiar
para decidir o que fazer em seguida.
"""

from __future__ import annotations

import json
import unittest
from datetime import date, timedelta

from core.project_checklist import (
    SITUACAO_FECHADO,
    SITUACAO_HOJE,
    SITUACAO_ILEGIVEL,
    SITUACAO_NO_PRAZO,
    SITUACAO_PROXIMO,
    SITUACAO_SEM_PRAZO,
    SITUACAO_VENCIDO,
    formatar_prazo,
    interpretar_prazo,
    resumo_checklist,
    situacao_prazo,
)
from core.project_dependencies import (
    STATUS_AUSENTE,
    STATUS_DESATUALIZADO,
    preparar_registro_dependencias,
)
from core.project_diff import (
    TIPO_ALTERADO,
    TIPO_INCLUIDO,
    TIPO_REMOVIDO,
    comparar_documentos,
    resumir_diferencas,
)
from core.project_portfolio import (
    proximos_passos,
    resumir_carteira,
    resumir_projeto,
    vencimentos_da_carteira,
)
from core.project_records import (
    STATUS_SUPERADO,
    remover_registro,
    resumir_registros,
    superar_registro,
)
from core.project_store import (
    EVENTO_CRIACAO,
    EVENTO_REGISTRO,
    EVENTO_REVISAO,
    EVENTO_SITUACAO,
    adicionar_registro_tecnico,
    arquivar_projeto,
    carregar_projetos,
    criar_item,
    criar_projeto,
    exportar_projeto,
    historico_eventos,
    novo_projeto_documento,
    obter_revisao,
    salvar_projeto,
)
from core.project_validation import validar_projeto
from core.project_workflow import (
    ARQUIVADO,
    EM_ELABORACAO,
    EM_VERIFICACAO,
    EMITIDO,
    SUSPENSO,
    avaliar_todas_transicoes,
    avaliar_transicao,
    transicoes_possiveis,
)
from core.validation_plugins import executar_regras

HOJE = date(2026, 9, 11)


def achados_da_regra(projeto, regra_id: str) -> list:
    for regra, resultado in executar_regras(projeto):
        if regra.id == regra_id:
            return list(resultado.achados)
    raise AssertionError(f"Regra {regra_id!r} não está registrada.")


def projeto_documentado() -> dict:
    """Projeto que passa na validação sem bloqueios, para os testes de fluxo."""
    projeto = novo_projeto_documento(
        "Suporte do transportador CV-204",
        codigo="PRJ-2026-014",
        cliente="Mineração Norte",
        unidade_industrial="Planta Sul",
        area="Expedição",
        tag_equipamento="CV-204",
        objetivo="Verificar a estrutura de suporte para a nova carga.",
    )
    projeto.update(
        {
            "responsavel": "Eng. Ana",
            "verificador": "Eng. Bruno",
            "aprovador": "Eng. Carla",
        }
    )
    projeto["base_projeto"] = {
        "referencias_desenho": "DE-1042 rev. C",
        "base_carregamentos": "Folha de dados do fabricante",
        "condicoes_operacao": "Ambiente externo",
        "criterio_aceitacao": "NBR 8800",
        "vida_requerida": "20 anos",
        "limitacoes": "Fundação fora do escopo",
    }
    componente = criar_item(
        tag="CV-204-SUP-01",
        descricao="Suporte principal",
        material="ASTM A572 Gr. 50",
        fonte_material="Certificado MTR 88213",
        desenho="DE-1042 rev. C",
        criticidade="Alta",
    )
    projeto["componentes"] = [componente]
    projeto["normas"] = [
        criar_item(codigo="ABNT NBR 8800", edicao="2024", escopo="Barras", conferida=True, obrigatoria=True)
    ]
    projeto["registros_tecnicos"] = [
        criar_item(
            modulo="Análise estática",
            modulo_id="analise_estatica",
            titulo="Ponto crítico P1",
            status="Atende",
            resumo="von Mises",
            metodo="Estado plano",
            entradas={"sigma_x_MPa": 120.0},
            resultados={"fator_seguranca": 2.1, "fator_seguranca_minimo": 1.5},
            premissas=["Estado plano"],
            referencias=["DE-1042"],
            conclusao="Atende.",
            componentes_ids=[componente["id"]],
        )
    ]
    return projeto


# ---------------------------------------------------------------------------
# Prazos do checklist
# ---------------------------------------------------------------------------


class PrazosTests(unittest.TestCase):
    def test_interpreta_formatos_usuais_e_iso(self):
        esperado = date(2026, 3, 15)
        for texto in ("2026-03-15", "15/03/2026", "15-03-2026", "15.03.2026", "2026-03-15T10:00:00", "15/03/26"):
            with self.subTest(texto=texto):
                self.assertEqual(interpretar_prazo(texto), esperado)
        self.assertEqual(interpretar_prazo(esperado), esperado)

    def test_texto_livre_nao_vira_data(self):
        self.assertIsNone(interpretar_prazo("após a parada"))
        self.assertIsNone(interpretar_prazo(""))
        self.assertIsNone(interpretar_prazo(None))
        self.assertEqual(formatar_prazo("após a parada"), "após a parada")
        self.assertEqual(formatar_prazo("2026-03-15"), "15/03/2026")

    def test_classifica_em_relacao_a_hoje(self):
        casos = {
            (HOJE - timedelta(days=3)).isoformat(): SITUACAO_VENCIDO,
            HOJE.isoformat(): SITUACAO_HOJE,
            (HOJE + timedelta(days=5)).isoformat(): SITUACAO_PROXIMO,
            (HOJE + timedelta(days=30)).isoformat(): SITUACAO_NO_PRAZO,
            "": SITUACAO_SEM_PRAZO,
            "quando der": SITUACAO_ILEGIVEL,
        }
        for prazo, situacao in casos.items():
            with self.subTest(prazo=prazo):
                avaliacao = situacao_prazo({"item": "x", "prazo": prazo, "estado": "Aberto"}, hoje=HOJE)
                self.assertEqual(avaliacao["situacao"], situacao)

    def test_item_concluido_nunca_esta_vencido(self):
        item = {"item": "x", "prazo": "2020-01-01", "estado": "Concluído"}
        self.assertEqual(situacao_prazo(item, hoje=HOJE)["situacao"], SITUACAO_FECHADO)
        item["estado"] = "Não aplicável"
        self.assertEqual(situacao_prazo(item, hoje=HOJE)["situacao"], SITUACAO_FECHADO)

    def test_resumo_ordena_vencidos_do_mais_atrasado_para_o_menos(self):
        checklist = [
            {"item": "Recente", "prazo": (HOJE - timedelta(days=1)).isoformat(), "estado": "Aberto"},
            {"item": "Antigo", "prazo": (HOJE - timedelta(days=40)).isoformat(), "estado": "Aberto", "critico": True},
            {"item": "Feito", "prazo": (HOJE - timedelta(days=40)).isoformat(), "estado": "Concluído"},
            {"item": "Semana", "prazo": (HOJE + timedelta(days=2)).isoformat(), "estado": "Em andamento"},
            {"item": "Sem data", "prazo": "", "estado": "Aberto"},
        ]
        resumo = resumo_checklist(checklist, hoje=HOJE)
        self.assertEqual([linha["item"] for linha in resumo["vencidos"]], ["Antigo", "Recente"])
        self.assertEqual([linha["item"] for linha in resumo["proximos"]], ["Semana"])
        self.assertEqual(resumo["total"], 5)
        self.assertEqual(resumo["concluidos"], 1)
        self.assertEqual(resumo["abertos"], 4)
        self.assertEqual(resumo["criticos_abertos"], 1)
        self.assertEqual(resumo["percentual_concluido"], 20)
        self.assertEqual(resumo["vencidos"][0]["dias"], -40)


class RegraPrazosTests(unittest.TestCase):
    def test_vencido_vira_atencao_e_proximo_vira_informacao(self):
        hoje = date.today()
        projeto = {
            "checklist": [
                {"item": "Atrasado", "prazo": (hoje - timedelta(days=2)).isoformat(), "estado": "Aberto"},
                {"item": "Semana", "prazo": (hoje + timedelta(days=3)).isoformat(), "estado": "Aberto"},
                {"item": "Texto", "prazo": "após a parada", "estado": "Aberto"},
                {"item": "Feito", "prazo": (hoje - timedelta(days=9)).isoformat(), "estado": "Concluído"},
            ]
        }
        achados = achados_da_regra(projeto, "prazos-checklist")
        por_titulo = {achado.titulo: achado.severidade for achado in achados}
        self.assertEqual(por_titulo.get("Prazo vencido: Atrasado"), "Atenção")
        self.assertEqual(por_titulo.get("Vence em breve: Semana"), "Informação")
        self.assertEqual(por_titulo.get("Prazo não interpretável: Texto"), "Informação")
        self.assertFalse(any("Feito" in titulo for titulo in por_titulo))

    def test_checklist_sem_prazos_nao_gera_achado(self):
        projeto = {"checklist": [{"item": "Aberto sem prazo", "estado": "Aberto"}]}
        self.assertEqual(achados_da_regra(projeto, "prazos-checklist"), [])


# ---------------------------------------------------------------------------
# Fluxo de situação
# ---------------------------------------------------------------------------


class FluxoSituacaoTests(unittest.TestCase):
    def test_transicoes_declaradas_por_situacao(self):
        self.assertEqual(transicoes_possiveis({"status": EM_ELABORACAO}), (EM_VERIFICACAO, SUSPENSO, ARQUIVADO))
        self.assertIn(EM_ELABORACAO, transicoes_possiveis({"status": EMITIDO}))
        self.assertNotIn(EMITIDO, transicoes_possiveis({"status": EM_ELABORACAO}))
        # Situação desconhecida é tratada como Em elaboração, não como beco.
        self.assertEqual(transicoes_possiveis({"status": "qualquer"}), transicoes_possiveis({"status": EM_ELABORACAO}))

    def test_nao_ha_atalho_de_elaboracao_para_emitido(self):
        resultado = avaliar_transicao(projeto_documentado(), EMITIDO)
        self.assertFalse(resultado["permitida"])
        self.assertTrue(any("passagem direta" in texto for texto in resultado["impedimentos"]))

    def test_verificacao_exige_verificador_e_registro(self):
        projeto = projeto_documentado()
        self.assertTrue(avaliar_transicao(projeto, EM_VERIFICACAO)["permitida"])
        projeto["verificador"] = ""
        resultado = avaliar_transicao(projeto, EM_VERIFICACAO)
        self.assertFalse(resultado["permitida"])
        self.assertTrue(any("Verificador" in texto for texto in resultado["impedimentos"]))
        projeto["verificador"] = "Eng. Bruno"
        projeto["registros_tecnicos"] = []
        resultado = avaliar_transicao(projeto, EM_VERIFICACAO)
        self.assertFalse(resultado["permitida"])

    def test_bloqueio_aberto_so_avisa_na_verificacao_mas_trava_a_emissao(self):
        projeto = projeto_documentado()
        projeto["normas"] = []  # matriz normativa vazia é bloqueio
        para_verificacao = avaliar_transicao(projeto, EM_VERIFICACAO)
        self.assertTrue(para_verificacao["permitida"])
        self.assertTrue(any("bloqueio" in texto for texto in para_verificacao["avisos"]))
        projeto["status"] = EM_VERIFICACAO
        para_emissao = avaliar_transicao(projeto, EMITIDO)
        self.assertFalse(para_emissao["permitida"])
        self.assertTrue(any("bloqueio" in texto for texto in para_emissao["impedimentos"]))

    def test_emissao_exige_aprovador_e_calculos_atualizados(self):
        projeto = projeto_documentado()
        projeto["status"] = EM_VERIFICACAO
        resultado = avaliar_transicao(projeto, EMITIDO)
        self.assertTrue(resultado["permitida"], resultado["impedimentos"])
        self.assertTrue(resultado["cria_revisao"])

        projeto["aprovador"] = ""
        self.assertFalse(avaliar_transicao(projeto, EMITIDO)["permitida"])
        projeto["aprovador"] = "Eng. Carla"

        # Um cálculo cuja fonte mudou depois do registro trava a emissão.
        material = {"id": "MAT-1", "nome": "Aço A36", "propriedades": {"Sy_MPa": 250.0}}
        projeto["materiais_projeto"] = [material]
        registro = preparar_registro_dependencias(
            projeto,
            {
                "modulo": "Análise estática",
                "modulo_id": "analise_estatica",
                "titulo": "Com material",
                "status": "Atende",
                "resumo": "x",
                "metodo": "y",
                "entradas": {"a": 1},
                "resultados": {"fator_seguranca": 2.0},
                "premissas": ["p"],
                "referencias": ["r"],
                "conclusao": "ok",
                "materiais_ids": ["MAT-1"],
            },
        )
        projeto["registros_tecnicos"].append(registro)
        self.assertTrue(avaliar_transicao(projeto, EMITIDO)["permitida"])
        material["propriedades"]["Sy_MPa"] = 345.0
        resultado = avaliar_transicao(projeto, EMITIDO)
        self.assertFalse(resultado["permitida"])
        self.assertTrue(any("desatualizados" in texto for texto in resultado["impedimentos"]))

    def test_reabrir_emitido_cria_revisao_e_avisa(self):
        projeto = projeto_documentado()
        projeto["status"] = EMITIDO
        resultado = avaliar_transicao(projeto, EM_ELABORACAO)
        self.assertTrue(resultado["permitida"])
        self.assertTrue(resultado["cria_revisao"])
        self.assertTrue(resultado["avisos"])

    def test_mesma_situacao_e_recusada(self):
        self.assertFalse(avaliar_transicao(projeto_documentado(), EM_ELABORACAO)["permitida"])

    def test_avaliacao_completa_cobre_todos_os_destinos(self):
        projeto = projeto_documentado()
        destinos = [item["destino"] for item in avaliar_todas_transicoes(projeto)]
        self.assertEqual(tuple(destinos), transicoes_possiveis(projeto))


# ---------------------------------------------------------------------------
# Comparação de revisões
# ---------------------------------------------------------------------------


class ComparacaoTests(unittest.TestCase):
    def test_documentos_iguais_nao_tem_diferenca(self):
        projeto = projeto_documentado()
        self.assertEqual(comparar_documentos(projeto, projeto), [])

    def test_campos_administrativos_sao_ignorados(self):
        antes = projeto_documentado()
        depois = json.loads(json.dumps(antes))
        depois["atualizado_em"] = "2030-01-01T00:00:00+00:00"
        depois["revisao"] = 7
        depois["registros_tecnicos"][0]["hash_calculo"] = "outro"
        depois["registros_tecnicos"][0]["estado_dependencias"] = {"status": "Desatualizado"}
        self.assertEqual(comparar_documentos(antes, depois), [])

    def test_detecta_alteracao_inclusao_e_remocao(self):
        antes = projeto_documentado()
        depois = json.loads(json.dumps(antes))
        depois["objetivo"] = "Verificar para 12 t."
        depois["base_projeto"]["criterio_aceitacao"] = "NBR 8800 e L/350"
        depois["componentes"][0]["material"] = "ASTM A36"
        depois["componentes"].append(criar_item(tag="CV-204-SUP-02", descricao="Suporte secundário"))
        del depois["normas"][0]
        depois["criterios_projeto"] = {"seguranca": {"fator_seguranca_minimo": 2.0}}
        depois["registros_tecnicos"][0]["resultados"]["fator_seguranca"] = 1.2

        diferencas = comparar_documentos(antes, depois)
        por_chave = {(item["secao"], item["item"], item["campo"]): item for item in diferencas}

        objetivo = por_chave[("Identificação", "", "Objetivo")]
        self.assertEqual(objetivo["tipo"], TIPO_ALTERADO)
        self.assertEqual(objetivo["depois"], "Verificar para 12 t.")
        self.assertIn(("Base de projeto", "", "Critérios de aceitação"), por_chave)
        self.assertEqual(
            por_chave[("Escopo físico", "CV-204-SUP-01 · Suporte principal", "material")]["depois"],
            "ASTM A36",
        )
        incluido = por_chave[("Escopo físico", "CV-204-SUP-02 · Suporte secundário", "")]
        self.assertEqual(incluido["tipo"], TIPO_INCLUIDO)
        removido = por_chave[("Matriz normativa", "ABNT NBR 8800 · 2024", "")]
        self.assertEqual(removido["tipo"], TIPO_REMOVIDO)
        criterio = por_chave[("Critérios do projeto", "", "seguranca.fator_seguranca_minimo")]
        self.assertEqual(criterio["tipo"], TIPO_INCLUIDO)
        self.assertEqual(criterio["depois"], "2")
        fator = por_chave[("Registros técnicos", "Ponto crítico P1 · Análise estática", "resultados.fator_seguranca")]
        self.assertEqual((fator["antes"], fator["depois"]), ("2.1", "1.2"))

        resumo = resumir_diferencas(diferencas)
        self.assertEqual(resumo["total"], len(diferencas))
        self.assertEqual(resumo["por_tipo"][TIPO_INCLUIDO], 2)
        self.assertEqual(resumo["por_tipo"][TIPO_REMOVIDO], 1)
        self.assertEqual(resumo["por_secao"]["Escopo físico"], 2)

    def test_numeros_equivalentes_nao_sao_diferenca(self):
        antes = {"componentes": [{"id": "a", "tag": "T", "valor": 1}]}
        depois = {"componentes": [{"id": "a", "tag": "T", "valor": 1.0}]}
        self.assertEqual(comparar_documentos(antes, depois), [])


# ---------------------------------------------------------------------------
# Registros técnicos: superar e remover
# ---------------------------------------------------------------------------


class RegistrosTests(unittest.TestCase):
    def _projeto_com_reprovado(self) -> dict:
        projeto = projeto_documentado()
        reprovado = criar_item(
            modulo="Análise estática",
            modulo_id="analise_estatica",
            titulo="Ponto P2 antigo",
            status="Não atende",
            resumo="x",
            metodo="y",
            entradas={"a": 1},
            resultados={"fator_seguranca": 0.8, "utilizacao_maxima": 1.3},
            premissas=["p"],
            referencias=["r"],
            conclusao="Não atende.",
        )
        projeto["registros_tecnicos"].append(reprovado)
        return projeto

    def test_registro_superado_deixa_de_bloquear(self):
        projeto = self._projeto_com_reprovado()
        self.assertGreater(validar_projeto(projeto)["contagens"]["Bloqueio"], 0)
        alvo = projeto["registros_tecnicos"][1]["id"]
        substituto = projeto["registros_tecnicos"][0]["id"]
        documento = superar_registro(projeto, alvo, motivo="Refeito com a carga correta", substituto_id=substituto)
        superado = next(item for item in documento["registros_tecnicos"] if item["id"] == alvo)
        self.assertEqual(superado["status"], STATUS_SUPERADO)
        self.assertEqual(superado["status_anterior"], "Não atende")
        self.assertEqual(superado["superado_por"], substituto)
        self.assertEqual(validar_projeto(documento)["contagens"]["Bloqueio"], 0)
        # O conteúdo técnico continua íntegro: a assinatura foi recalculada.
        from core.technical_records import avaliar_contrato_registro

        self.assertTrue(avaliar_contrato_registro(superado)["assinatura_valida"])

    def test_superar_por_si_mesmo_ou_inexistente_e_recusado(self):
        projeto = projeto_documentado()
        alvo = projeto["registros_tecnicos"][0]["id"]
        with self.assertRaises(ValueError):
            superar_registro(projeto, alvo, substituto_id=alvo)
        with self.assertRaises(ValueError):
            superar_registro(projeto, "nao-existe")

    def test_remover_registro_deixa_dependentes_com_referencia_ausente(self):
        projeto = projeto_documentado()
        origem = projeto["registros_tecnicos"][0]
        dependente = preparar_registro_dependencias(
            projeto,
            {
                "modulo": "Análise de fadiga",
                "modulo_id": "analise_fadiga",
                "titulo": "Fadiga a partir de P1",
                "status": "Atende",
                "entradas": {"registro_origem": origem["id"]},
                "resultados": {"fator_seguranca": 1.8},
            },
        )
        projeto["registros_tecnicos"].append(dependente)
        projeto["configuracao_relatorio"]["registros_incluidos"] = [origem["id"], dependente["id"]]
        documento = remover_registro(projeto, origem["id"])
        self.assertEqual([item["id"] for item in documento["registros_tecnicos"]], [dependente["id"]])
        estado = documento["registros_tecnicos"][0]["estado_dependencias"]["status"]
        self.assertEqual(estado, STATUS_AUSENTE)
        self.assertEqual(documento["configuracao_relatorio"]["registros_incluidos"], [dependente["id"]])

    def test_superar_origem_deixa_dependente_desatualizado(self):
        projeto = projeto_documentado()
        origem = projeto["registros_tecnicos"][0]
        dependente = preparar_registro_dependencias(
            projeto,
            {
                "modulo": "Análise de fadiga",
                "modulo_id": "analise_fadiga",
                "titulo": "Fadiga a partir de P1",
                "status": "Atende",
                "entradas": {"registro_origem": origem["id"]},
                "resultados": {"fator_seguranca": 1.8},
            },
        )
        projeto["registros_tecnicos"].append(dependente)
        documento = superar_registro(projeto, origem["id"])
        estados = {item["id"]: item["estado_dependencias"]["status"] for item in documento["registros_tecnicos"]}
        self.assertEqual(estados[dependente["id"]], STATUS_DESATUALIZADO)

    def test_resumo_traz_peca_fator_utilizacao_e_atualidade(self):
        projeto = self._projeto_com_reprovado()
        linhas = {linha["titulo"]: linha for linha in resumir_registros(projeto)}
        p1 = linhas["Ponto crítico P1"]
        self.assertEqual(p1["peca"], "CV-204-SUP-01 · Suporte principal")
        self.assertEqual(p1["menor_fator"], 2.1)
        self.assertTrue(p1["atualizado"])
        p2 = linhas["Ponto P2 antigo"]
        self.assertEqual(p2["menor_fator"], 0.8)
        self.assertEqual(p2["utilizacao"], 1.3)
        self.assertFalse(p2["superado"])


# ---------------------------------------------------------------------------
# Trilha de eventos e revisões no banco
# ---------------------------------------------------------------------------


def test_linha_do_tempo_registra_criacao_salvamento_situacao_e_registro(tmp_path):
    banco = tmp_path / "eventos.sqlite3"
    projeto = criar_projeto("Eventos", codigo="EV-1", objetivo="x", caminho_banco=banco)
    projeto["cliente"] = "Cliente"
    projeto = salvar_projeto(projeto, motivo="Cliente informado", caminho_banco=banco)
    projeto["status"] = EM_VERIFICACAO
    projeto = salvar_projeto(projeto, motivo="Enviado para verificação", caminho_banco=banco)
    projeto = adicionar_registro_tecnico(
        projeto["id"],
        {"modulo": "Análise estática", "titulo": "P1", "status": "Atende", "entradas": {}, "resultados": {}},
        caminho_banco=banco,
    )
    projeto = salvar_projeto(projeto, motivo="Marco de emissão", criar_revisao=True, caminho_banco=banco)

    eventos = historico_eventos(projeto["id"], caminho_banco=banco)
    tipos = [evento["tipo"] for evento in eventos]
    assert tipos[-1] == EVENTO_CRIACAO
    assert EVENTO_SITUACAO in tipos
    assert EVENTO_REGISTRO in tipos
    assert tipos[0] == EVENTO_REVISAO
    descricoes = [evento["descricao"] for evento in eventos]
    assert "Cliente informado" in descricoes
    assert "Situação alterada de Em elaboração para Em verificação" in descricoes
    assert any(texto.startswith("Registro técnico incluído: Análise estática · P1") for texto in descricoes)
    assert any(texto.startswith("Revisão 01: Marco de emissão") for texto in descricoes)
    assert eventos[0]["revisao"] == 1
    assert len(historico_eventos(projeto["id"], limite=2, caminho_banco=banco)) == 2

    # Exportação leva os eventos junto com o histórico de revisões.
    pacote = json.loads(exportar_projeto(projeto["id"], caminho_banco=banco))
    assert len(pacote["eventos"]) == len(eventos)


def test_obter_revisao_devolve_o_documento_fotografado(tmp_path):
    banco = tmp_path / "rev.sqlite3"
    projeto = criar_projeto("Revisões", codigo="RV-1", objetivo="antes", caminho_banco=banco)
    projeto["objetivo"] = "depois"
    projeto = salvar_projeto(projeto, motivo="Marco", criar_revisao=True, caminho_banco=banco)
    assert obter_revisao(projeto["id"], 0, caminho_banco=banco)["objetivo"] == "antes"
    assert obter_revisao(projeto["id"], 1, caminho_banco=banco)["objetivo"] == "depois"
    assert obter_revisao(projeto["id"], 9, caminho_banco=banco) is None
    diferencas = comparar_documentos(
        obter_revisao(projeto["id"], 0, caminho_banco=banco),
        obter_revisao(projeto["id"], 1, caminho_banco=banco),
    )
    assert [(item["campo"], item["antes"], item["depois"]) for item in diferencas] == [
        ("Objetivo", "antes", "depois")
    ]


def test_carregar_projetos_respeita_arquivados(tmp_path):
    banco = tmp_path / "carteira.sqlite3"
    a = criar_projeto("A", codigo="A-1", caminho_banco=banco)
    b = criar_projeto("B", codigo="B-1", caminho_banco=banco)
    arquivar_projeto(b["id"], caminho_banco=banco)
    assert [item["id"] for item in carregar_projetos(caminho_banco=banco)] == [a["id"]]
    todos = carregar_projetos(incluir_arquivados=True, caminho_banco=banco)
    assert {item["id"] for item in todos} == {a["id"], b["id"]}
    assert "componentes" in todos[0]
    # Arquivar deixa rastro na linha do tempo, com a mudança de situação.
    tipos = {evento["tipo"] for evento in historico_eventos(b["id"], caminho_banco=banco)}
    assert EVENTO_SITUACAO in tipos


# ---------------------------------------------------------------------------
# Carteira e próximos passos
# ---------------------------------------------------------------------------


class CarteiraTests(unittest.TestCase):
    def test_resumo_do_projeto_le_bloqueios_prazos_e_atualidade(self):
        projeto = projeto_documentado()
        projeto["checklist"] = [
            {"id": "c1", "item": "Vencido", "prazo": (HOJE - timedelta(days=10)).isoformat(), "estado": "Aberto", "critico": True},
            {"id": "c2", "item": "Feito", "prazo": "", "estado": "Concluído"},
        ]
        resumo = resumir_projeto(projeto, hoje=HOJE)
        self.assertEqual(resumo["codigo"], "PRJ-2026-014")
        self.assertEqual(resumo["status"], EM_ELABORACAO)
        self.assertEqual(resumo["registros"], 1)
        self.assertEqual(resumo["checklist_vencidos"], 1)
        self.assertEqual(resumo["criticos_abertos"], 1)
        self.assertEqual(resumo["checklist_percentual"], 50)
        self.assertFalse(resumo["criterios_definidos"])
        self.assertIn(resumo["prontidao"], {"Pronto para revisão", "Pronto com ressalvas", "Em consolidação", "Não pronto para emissão"})

    def test_carteira_agrega_por_situacao_e_urgencia(self):
        limpo = projeto_documentado()
        travado = projeto_documentado()
        travado["codigo"] = "PRJ-2"
        travado["status"] = EM_VERIFICACAO
        travado["normas"] = []
        travado["checklist"] = [
            {"id": "c", "item": "Cobrar", "prazo": (HOJE - timedelta(days=1)).isoformat(), "estado": "Aberto"}
        ]
        resumos = [resumir_projeto(limpo, hoje=HOJE), resumir_projeto(travado, hoje=HOJE)]
        carteira = resumir_carteira(resumos)
        self.assertEqual(carteira["total"], 2)
        self.assertEqual(carteira["por_situacao"], {EM_ELABORACAO: 1, EM_VERIFICACAO: 1})
        self.assertEqual(carteira["com_bloqueio"], 1)
        self.assertEqual(carteira["checklist_vencidos"], 1)
        vencimentos = vencimentos_da_carteira(resumos)
        self.assertEqual(len(vencimentos), 1)
        self.assertEqual(vencimentos[0]["projeto"], "PRJ-2 · Suporte do transportador CV-204")
        self.assertEqual(resumir_carteira([])["total"], 0)

    def test_proximos_passos_priorizam_o_que_destrava(self):
        projeto = projeto_documentado()
        projeto["normas"] = []
        projeto["checklist"] = [
            {"id": "c", "item": "Cobrar", "prazo": (date.today() - timedelta(days=1)).isoformat(), "estado": "Aberto"}
        ]
        passos = proximos_passos(projeto)
        titulos = [passo["titulo"] for passo in passos]
        self.assertEqual(titulos[0], "Cobrar itens vencidos do checklist")
        self.assertIn("Resolver bloqueios da validação", titulos)
        self.assertIn("Definir os critérios técnicos do projeto", titulos)
        self.assertTrue(all(passo["pagina"].startswith("app_pages/") for passo in passos))

    def test_projeto_limpo_sugere_verificacao_e_depois_emissao(self):
        projeto = projeto_documentado()
        projeto["criterios_projeto"] = {
            "normativo": {"norma_principal": "NBR 8800", "criterio_aceitacao": "ELU/ELS"},
            "combinacoes": {"referencia": "NBR 8681"},
            "operacao": {"temperatura_projeto_C": 40, "vida_util_anos": 20},
        }
        titulos = [passo["titulo"] for passo in proximos_passos(projeto)]
        self.assertIn("Enviar para verificação", titulos)
        projeto["status"] = EM_VERIFICACAO
        titulos = [passo["titulo"] for passo in proximos_passos(projeto)]
        self.assertIn("Emitir o memorial", titulos)
        projeto["status"] = SUSPENSO
        self.assertEqual([passo["titulo"] for passo in proximos_passos(projeto)], ["Retomar ou arquivar o projeto"])


# ---------------------------------------------------------------------------
# Regras de critérios e documentos de entrada
# ---------------------------------------------------------------------------


class RegrasGestaoTests(unittest.TestCase):
    def test_criterios_ausentes_sao_so_informacao(self):
        achados = achados_da_regra({}, "criterios-projeto")
        self.assertEqual([achado.severidade for achado in achados], ["Informação"])
        # Não muda a prontidão de um projeto documentado.
        resultado = validar_projeto(projeto_documentado())
        self.assertIn(resultado["prontidao"], {"Pronto para revisão", "Pronto com ressalvas"})

    def test_criterios_incompletos_viram_atencao(self):
        projeto = {"criterios_projeto": {"seguranca": {"fator_seguranca_minimo": 2.0}}}
        achados = achados_da_regra(projeto, "criterios-projeto")
        self.assertEqual(achados[0].severidade, "Atenção")
        self.assertIn("Norma", achados[0].detalhe)

    def test_criterios_completos_nao_geram_atencao(self):
        projeto = {
            "criterios_projeto": {
                "normativo": {"norma_principal": "NBR 8800", "criterio_aceitacao": "ELU"},
                "combinacoes": {"referencia": "NBR 8681"},
                "operacao": {"temperatura_projeto_C": 40, "vida_util_anos": 20},
            }
        }
        self.assertEqual(achados_da_regra(projeto, "criterios-projeto"), [])

    def test_documentos_aguardando_e_superados_citados(self):
        projeto = {
            "componentes": [{"id": "c1", "tag": "SUP-01", "desenho": "DE-1042 rev. B"}],
            "anexos": [
                {"id": "d1", "codigo": "DE-1042", "revisao": "B", "situacao": "Superado"},
                {"id": "d2", "codigo": "FD-77", "revisao": "0", "situacao": "Aguardando recebimento"},
                {"id": "d3", "codigo": "MTR-88213", "revisao": "", "situacao": "Vigente"},
                {"id": "d4", "codigo": "DE-2000", "revisao": "A", "situacao": "Vigente"},
            ],
        }
        achados = achados_da_regra(projeto, "documentos-entrada")
        por_titulo = {achado.titulo: achado.severidade for achado in achados}
        self.assertEqual(por_titulo["DE-1042: documento superado ainda citado no escopo"], "Atenção")
        self.assertEqual(por_titulo["FD-77: aguardando recebimento"], "Pendência")
        self.assertEqual(por_titulo["MTR-88213: revisão não informada"], "Atenção")
        self.assertFalse(any("DE-2000" in titulo for titulo in por_titulo))

    def test_sem_documentos_nao_ha_achado(self):
        self.assertEqual(achados_da_regra({"anexos": []}, "documentos-entrada"), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
