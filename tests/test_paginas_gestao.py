"""As páginas de gestão precisam abrir com um projeto de verdade carregado.

`test_paginas_carregam` abre cada página com o banco do usuário — que pode
estar vazio, e aí a página de projetos para no aviso inicial sem exercitar
nenhuma aba. Aqui o banco é temporário e recebe um projeto cheio: escopo,
normas, documentos, critérios, registros (um superado), checklist com
prazo vencido e revisão controlada. Todas as abas, o painel e as centrais
têm de renderizar sem exceção sobre esse projeto.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import project_store
from core.project_records import superar_registro
from core.project_store import (
    adicionar_registro_tecnico,
    criar_item,
    criar_projeto,
    salvar_projeto,
)

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")

PAGINAS_GESTAO = (
    "app_pages/painel_industrial.py",
    "app_pages/gestao_projetos.py",
    "app_pages/central_validacao.py",
    "app_pages/central_relatorios.py",
    "app_pages/inicio.py",
)


@pytest.fixture
def banco_com_projeto(tmp_path, monkeypatch):
    banco = tmp_path / "gestao.sqlite3"
    monkeypatch.setattr(project_store, "BANCO_PADRAO", banco)
    projeto = criar_projeto(
        "Suporte do transportador CV-204",
        codigo="PRJ-2026-014",
        cliente="Mineração Norte",
        unidade_industrial="Planta Sul",
        area="Expedição",
        tag_equipamento="CV-204",
        objetivo="Verificar a estrutura de suporte para a nova carga.",
    )
    projeto.update({"responsavel": "Eng. Ana", "verificador": "Eng. Bruno", "aprovador": "Eng. Carla"})
    componente = criar_item(
        tag="CV-204-SUP-01",
        descricao="Suporte principal",
        material="ASTM A572 Gr. 50",
        fonte_material="Certificado MTR 88213",
        desenho="DE-1042 rev. B",
        criticidade="Alta",
    )
    projeto["componentes"] = [componente]
    projeto["normas"] = [criar_item(codigo="ABNT NBR 8800", edicao="2024", escopo="Barras", conferida=True)]
    projeto["anexos"] = [
        criar_item(codigo="DE-1042", titulo="Arranjo geral", tipo="Desenho", revisao="B", situacao="Superado"),
        criar_item(codigo="FD-77", titulo="Folha de dados", tipo="Folha de dados", revisao="", situacao="Aguardando recebimento"),
    ]
    projeto["criterios_projeto"] = {
        "seguranca": {"fator_seguranca_minimo": 1.8},
        "normativo": {"norma_principal": "ABNT NBR 8800", "criterio_aceitacao": "ELU/ELS"},
    }
    projeto["checklist"] = [
        criar_item(item="Cobrar folha de dados", responsavel="Eng. Ana", prazo=(date.today() - timedelta(days=3)).isoformat(), estado="Aberto", critico=True),
        criar_item(item="Revisão independente", prazo="após a parada", estado="Aberto"),
        criar_item(item="Conferir desenho", prazo=(date.today() + timedelta(days=2)).isoformat(), estado="Em andamento"),
        criar_item(item="Feito", estado="Concluído"),
    ]
    projeto = salvar_projeto(projeto, motivo="Marco inicial", criar_revisao=True)
    projeto = adicionar_registro_tecnico(
        projeto["id"],
        {
            "modulo": "Análise estática",
            "modulo_id": "analise_estatica",
            "titulo": "Ponto crítico P1",
            "status": "Atende",
            "resumo": "von Mises",
            "metodo": "Estado plano",
            "entradas": {"sigma_x_MPa": 120.0},
            "resultados": {"fator_seguranca": 2.1, "fator_seguranca_minimo": 1.5},
            "premissas": ["Estado plano"],
            "referencias": ["DE-1042"],
            "conclusao": "Atende.",
            "componentes_ids": [componente["id"]],
        },
    )
    projeto = adicionar_registro_tecnico(
        projeto["id"],
        {
            "modulo": "Análise estática",
            "modulo_id": "analise_estatica",
            "titulo": "Ponto P1 antigo",
            "status": "Não atende",
            "entradas": {"sigma_x_MPa": 400.0},
            "resultados": {"fator_seguranca": 0.7},
            "conclusao": "Não atende.",
        },
    )
    antigo = projeto["registros_tecnicos"][1]["id"]
    documento = superar_registro(projeto, antigo, motivo="Refeito", substituto_id=projeto["registros_tecnicos"][0]["id"])
    salvar_projeto(documento, motivo="Registro superado")
    return banco


@pytest.mark.parametrize("pagina", PAGINAS_GESTAO)
def test_paginas_de_gestao_abrem_com_projeto_carregado(banco_com_projeto, pagina):
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(pagina)
    teste.run()
    assert not teste.exception, f"{pagina}: {[str(e.value) for e in teste.exception]}"


def test_pagina_de_projetos_mostra_as_leituras_de_gestao(banco_com_projeto):
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/gestao_projetos.py")
    teste.run()
    assert not teste.exception
    rotulos = {metrica.label for metrica in teste.metric}
    assert {"Situação", "Prazos vencidos", "Bloqueios"} <= rotulos
    vencidos = next(metrica for metrica in teste.metric if metrica.label == "Prazos vencidos")
    assert str(vencidos.value) == "1"
    textos = " ".join(str(item.value) for item in teste.markdown)
    assert "Próximos passos sugeridos" in textos
    assert "Comparar revisões" in " ".join(str(item.value) for item in teste.subheader)


def test_painel_lista_o_projeto_e_seus_alertas(banco_com_projeto):
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/painel_industrial.py")
    teste.run()
    assert not teste.exception
    rotulos = {metrica.label for metrica in teste.metric}
    assert {"Projetos", "Vencidos", "Desatualizados"} <= rotulos
    projetos = next(metrica for metrica in teste.metric if metrica.label == "Projetos")
    assert str(projetos.value) == "1"
    textos = " ".join(str(item.value) for item in teste.markdown)
    assert "PRJ-2026-014" in textos
    assert "prazo(s) vencido(s)" in textos


@pytest.fixture
def banco_com_projeto_vazio(tmp_path, monkeypatch):
    banco = tmp_path / "vazio.sqlite3"
    monkeypatch.setattr(project_store, "BANCO_PADRAO", banco)
    projeto = criar_projeto(
        "Mezanino da britagem",
        codigo="PRJ-MEZ-01",
        objetivo="Verificar o mezanino.",
        tipo_projeto="Estrutura metálica",
    )
    projeto.update({"responsavel": "Eng. Ana", "verificador": "Eng. Bruno"})
    salvar_projeto(projeto)
    return projeto["id"]


def test_aba_checklist_semeia_o_modelo_do_tipo_do_projeto(banco_com_projeto_vazio):
    from core.checklist_templates import obter_modelo
    from core.project_store import historico_eventos, obter_projeto

    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/gestao_projetos.py")
    teste.run()
    assert not teste.exception

    modelo = obter_modelo("estrutura_metalica")
    botao = next(
        botao for botao in teste.button if botao.label.startswith("Adicionar") and "do modelo" in botao.label
    )
    assert botao.label.startswith(f"Adicionar {len(modelo.itens)} item")
    botao.click()
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]

    projeto = obter_projeto(banco_com_projeto_vazio)
    assert len(projeto["checklist"]) == len(modelo.itens)
    origens = {item["origem_modelo"] for item in projeto["checklist"]}
    assert all(origem.startswith("estrutura_metalica:") for origem in origens)
    responsaveis = {item["responsavel"] for item in projeto["checklist"]}
    assert {"Eng. Ana", "Eng. Bruno", ""} == responsaveis  # aprovador ainda vazio
    assert any("do modelo Estrutura metálica" in evento["descricao"] for evento in historico_eventos(banco_com_projeto_vazio))

    # Depois de semear, o botão some: nada mais a acrescentar deste modelo.
    teste.run()
    assert not any("do modelo" in botao.label for botao in teste.button if botao.label.startswith("Adicionar"))
