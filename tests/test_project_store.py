import json

from core.project_store import (
    adicionar_registro_tecnico,
    arquivar_projeto,
    criar_item,
    criar_projeto,
    duplicar_projeto,
    exportar_projeto,
    historico_revisoes,
    importar_projeto,
    listar_projetos,
    obter_projeto_ativo,
    restaurar_revisao,
    salvar_projeto,
)


def test_ciclo_permanente_com_revisoes_exportacao_e_importacao(tmp_path):
    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto(
        "Adequação da linha L-101",
        codigo="PRJ-001",
        cliente="Unidade fabril",
        unidade_industrial="Planta Sul",
        area="Utilidades",
        tag_equipamento="L-101",
        caminho_banco=banco,
    )
    assert obter_projeto_ativo(caminho_banco=banco)["id"] == projeto["id"]
    assert projeto["materiais_projeto"] == []
    assert listar_projetos(caminho_banco=banco)[0]["codigo"] == "PRJ-001"

    projeto["objetivo"] = "Verificar a integridade para a nova condição operacional."
    projeto["componentes"].append(
        criar_item(tag="L-101", descricao="Linha industrial", material="Aço carbono")
    )
    projeto = salvar_projeto(
        projeto,
        motivo="Base consolidada",
        criar_revisao=True,
        caminho_banco=banco,
    )
    assert projeto["revisao"] == 1
    assert [item["revisao"] for item in historico_revisoes(projeto["id"], caminho_banco=banco)] == [1, 0]

    projeto = adicionar_registro_tecnico(
        projeto["id"],
        {
            "modulo": "Análise estática",
            "titulo": "Ponto P1",
            "status": "Atende",
            "entradas": {"sigma_x_MPa": 80.0},
            "resultados": {"fator_seguranca": 2.1, "fator_seguranca_minimo": 1.5},
            "premissas": ["Estado plano"],
            "referencias": ["Desenho D-001"],
            "conclusao": "Atende ao critério informado.",
        },
        caminho_banco=banco,
    )
    assert len(projeto["registros_tecnicos"]) == 1

    pacote = exportar_projeto(projeto["id"], caminho_banco=banco)
    assert json.loads(pacote)["formato"] == "mecanica-toolkit-project"
    importado = importar_projeto(pacote, caminho_banco=banco)
    assert importado["id"] != projeto["id"]
    assert importado["nome"].endswith("importado")

    copia = duplicar_projeto(projeto["id"], novo_nome="Cópia de trabalho", caminho_banco=banco)
    assert copia["id"] != projeto["id"]
    assert copia["nome"] == "Cópia de trabalho"

    arquivar_projeto(copia["id"], caminho_banco=banco)
    ids_visiveis = {item["id"] for item in listar_projetos(caminho_banco=banco)}
    assert copia["id"] not in ids_visiveis

    restaurado = restaurar_revisao(projeto["id"], 0, caminho_banco=banco)
    assert restaurado["revisao"] == 2
    assert restaurado["objetivo"] == ""


def test_banco_padrao_redirecionado_isola_de_verdade(tmp_path, monkeypatch):
    """Apontar BANCO_PADRAO para outro arquivo precisa ter efeito.

    Enquanto o caminho era argumento padrão (``= BANCO_PADRAO``), ele ficava
    congelado no momento do import: redirecionar o módulo não mudava nada e a
    escrita continuava indo para o banco real, sem aviso nenhum. Foi assim
    que projetos de teste acabaram no banco de trabalho.
    """
    from core import project_store

    alvo = tmp_path / "isolado.sqlite3"
    monkeypatch.setattr(project_store, "BANCO_PADRAO", alvo)

    criar_projeto("Isolado", codigo="ISO-1")

    assert alvo.exists()
    assert [item["codigo"] for item in listar_projetos()] == ["ISO-1"]
