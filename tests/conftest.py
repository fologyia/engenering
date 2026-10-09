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
from github_falso import GitHubFalso

from core import acesso, armazenamento, atualizacao_de_codigo, espelho_remoto, project_store
from core.espelho_remoto import ConfiguracaoGitHub, EspelhoGitHub
from core.project_records import superar_registro
from core.project_store import (
    adicionar_registro_tecnico,
    criar_item,
    criar_projeto,
    salvar_projeto,
)

# `--basetemp=tmp/pytest` (pyproject.toml) pede que `tmp/` já exista; num checkout limpo, como o do
# CI, ela não existe (está no .gitignore) e todo teste que usa tmp_path falharia no setup.
Path(__file__).resolve().parent.parent.joinpath("tmp").mkdir(exist_ok=True)


@pytest.fixture(scope="session", autouse=True)
def _banco_da_sessao_isolado(tmp_path_factory):
    """Rede de proteção: a suíte inteira roda contra um banco temporário."""
    banco = tmp_path_factory.mktemp("banco_sessao") / "projetos_sessao.sqlite3"
    # O app.py descarta os módulos do programa quando o código em disco mudou desde a última
    # execução. Sem esta declaração a primeira execução do app numa suíte trataria os módulos já
    # importados (e isolados pelos testes) como velhos e os reimportaria sem o isolamento.
    atualizacao_de_codigo.registrar_codigo_atual()
    with pytest.MonkeyPatch.context() as ambiente:
        # A variável de ambiente é a rede que sobrevive à reimportação: se o guarda do app.py
        # descartar os módulos (código editado com a suíte rodando), o ``core.project_store``
        # reimportado calcula o banco padrão por ela — e nunca cai no banco real do usuário.
        ambiente.setenv(project_store.VARIAVEL_BANCO, str(banco))
        ambiente.setattr(project_store, "BANCO_PADRAO", banco)
        yield banco


@pytest.fixture(autouse=True)
def _codigo_em_disco_declarado():
    """Editar o código com a suíte rodando não troca os módulos isolados no meio dela.

    Sem isto, a primeira execução do ``app.py`` depois de uma edição descartava os módulos do
    programa (``core/atualizacao_de_codigo.py``) e os reimportava sem o banco temporário, o espelho
    falso e as demais fixtures — e os testes seguintes gravavam no banco de trabalho do usuário.
    """
    atualizacao_de_codigo.registrar_codigo_atual()


@pytest.fixture
def banco_isolado(tmp_path, monkeypatch) -> Path:
    """Banco vazio e exclusivo deste teste, já como padrão do módulo."""
    banco = tmp_path / "projetos.sqlite3"
    monkeypatch.setattr(project_store, "BANCO_PADRAO", banco)
    return banco


@pytest.fixture(autouse=True)
def _espelho_remoto_desligado(monkeypatch):
    """Nenhum teste fala com o GitHub de verdade nem herda a configuração de quem roda a suíte.

    Quem tem os segredos do espelho no ambiente (para usar o programa) não pode, ao rodar os
    testes, empurrar projetos de teste para o repositório de dados real. Os testes do espelho
    ligam o servidor falso por cima, com a fixture ``espelho_github``.
    """
    for variavel in (*espelho_remoto.VARIAVEIS, "MECANICA_TOOLKIT_AMBIENTE", acesso.VARIAVEL_SENHA):
        monkeypatch.delenv(variavel, raising=False)
    espelho_remoto.redefinir()
    armazenamento.redefinir()
    espelho_remoto.definir_espelho(None)
    yield
    espelho_remoto.redefinir()
    armazenamento.redefinir()


@pytest.fixture
def github_falso():
    """Servidor local que imita a API de conteúdo do GitHub (ver ``github_falso.py``)."""
    servidor = GitHubFalso()
    servidor.iniciar()
    yield servidor
    servidor.parar()


@pytest.fixture
def espelho_github(github_falso) -> EspelhoGitHub:
    """Espelho ligado ao servidor falso: o que o programa gravar aparece em ``github_falso``."""
    espelho = EspelhoGitHub(
        ConfiguracaoGitHub(
            repositorio=github_falso.repositorio,
            token=github_falso.token,
            api=github_falso.url,
        )
    )
    espelho_remoto.definir_espelho(espelho)
    return espelho


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
