"""Fixtures compartilhadas: nenhum teste toca o banco de trabalho do usuário.

``core.project_store`` resolve o banco na hora da chamada (``_banco``), então
redirecionar ``BANCO_PADRAO`` basta para isolar tudo o que não passa um
``caminho_banco`` explícito — inclusive as páginas abertas pelo ``AppTest``,
que rodam no mesmo processo e enxergam o mesmo módulo.

A rede de proteção é a fixture de sessão abaixo: mesmo um teste novo que
esqueça de pedir ``banco_isolado`` cai num arquivo temporário, e não em
``%LOCALAPPDATA%``. As fixtures de função criam bancos próprios por cima
dela, para cada teste começar do estado que declara — vazio ou com um
projeto cheio — sem depender da ordem de execução.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from core import project_store
from core.project_records import superar_registro
from core.project_store import (
    adicionar_registro_tecnico,
    criar_item,
    criar_projeto,
    salvar_projeto,
)


@pytest.fixture(scope="session", autouse=True)
def _banco_da_sessao_isolado(tmp_path_factory):
    """Rede de proteção: a suíte inteira roda contra um banco temporário."""
    banco = tmp_path_factory.mktemp("banco_sessao") / "projetos_sessao.sqlite3"
    with pytest.MonkeyPatch.context() as ambiente:
        ambiente.setattr(project_store, "BANCO_PADRAO", banco)
        yield banco


@pytest.fixture
def banco_isolado(tmp_path, monkeypatch) -> Path:
    """Banco vazio e exclusivo deste teste, já como padrão do módulo."""
    banco = tmp_path / "projetos.sqlite3"
    monkeypatch.setattr(project_store, "BANCO_PADRAO", banco)
    return banco


@pytest.fixture
def banco_com_projeto(banco_isolado) -> Path:
    """Banco com um projeto cheio, ativo, para as páginas terem o que mostrar.

    Escopo, normas, documentos (um superado, um aguardando), critérios,
    dois registros (um superado), checklist com prazo vencido e a vencer, e
    uma revisão controlada — o conjunto que exercita todas as abas e leituras
    de gestão.
    """
    projeto = criar_projeto(
        "Suporte do transportador CV-204",
        codigo="PRJ-2026-014",
        cliente="Mineração Norte",
        unidade_industrial="Planta Sul",
        area="Expedição",
        tag_equipamento="CV-204",
        objetivo="Verificar a estrutura de suporte para a nova carga.",
    )
    projeto.update(
        {"responsavel": "Eng. Ana", "verificador": "Eng. Bruno", "aprovador": "Eng. Carla"}
    )
    componente = criar_item(
        tag="CV-204-SUP-01",
        descricao="Suporte principal",
        material="ASTM A572 Gr. 50",
        fonte_material="Certificado MTR 88213",
        desenho="DE-1042 rev. B",
        criticidade="Alta",
    )
    projeto["componentes"] = [componente]
    projeto["normas"] = [
        criar_item(codigo="ABNT NBR 8800", edicao="2024", escopo="Barras", conferida=True)
    ]
    projeto["anexos"] = [
        criar_item(
            codigo="DE-1042",
            titulo="Arranjo geral",
            tipo="Desenho",
            revisao="B",
            situacao="Superado",
        ),
        criar_item(
            codigo="FD-77",
            titulo="Folha de dados",
            tipo="Folha de dados",
            revisao="",
            situacao="Aguardando recebimento",
        ),
    ]
    projeto["criterios_projeto"] = {
        "seguranca": {"fator_seguranca_minimo": 1.8},
        "normativo": {"norma_principal": "ABNT NBR 8800", "criterio_aceitacao": "ELU/ELS"},
    }
    projeto["checklist"] = [
        criar_item(
            item="Cobrar folha de dados",
            responsavel="Eng. Ana",
            prazo=(date.today() - timedelta(days=3)).isoformat(),
            estado="Aberto",
            critico=True,
        ),
        criar_item(item="Revisão independente", prazo="após a parada", estado="Aberto"),
        criar_item(
            item="Conferir desenho",
            prazo=(date.today() + timedelta(days=2)).isoformat(),
            estado="Em andamento",
        ),
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
    documento = superar_registro(
        projeto,
        antigo,
        motivo="Refeito",
        substituto_id=projeto["registros_tecnicos"][0]["id"],
    )
    salvar_projeto(documento, motivo="Registro superado")
    return banco_isolado
