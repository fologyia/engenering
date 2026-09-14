import json

import pytest

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
    assert [item["revisao"] for item in historico_revisoes(projeto["id"], caminho_banco=banco)] == [
        1,
        0,
    ]

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


def test_excluir_projeto_apaga_revisoes_e_limpa_ativo(tmp_path):
    import pytest

    from core.project_store import ProjetoPersistenciaErro, excluir_projeto, obter_projeto

    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto("Para apagar", codigo="PRJ-DEL", caminho_banco=banco)
    assert len(historico_revisoes(projeto["id"], caminho_banco=banco)) >= 1
    assert obter_projeto_ativo(caminho_banco=banco)["id"] == projeto["id"]

    excluir_projeto(projeto["id"], caminho_banco=banco)

    assert obter_projeto(projeto["id"], caminho_banco=banco) is None
    assert historico_revisoes(projeto["id"], caminho_banco=banco) == []
    assert obter_projeto_ativo(caminho_banco=banco) is None
    assert listar_projetos(incluir_arquivados=True, caminho_banco=banco) == []
    with pytest.raises(ProjetoPersistenciaErro):
        excluir_projeto(projeto["id"], caminho_banco=banco)


# ----------------------------------------------------------- onde fica o banco


def test_caminho_padrao_respeita_a_variavel_de_ambiente(tmp_path, monkeypatch):
    from core.project_store import VARIAVEL_BANCO, caminho_banco_padrao

    monkeypatch.setenv(VARIAVEL_BANCO, str(tmp_path / "equipe" / "carteira.sqlite3"))
    assert caminho_banco_padrao() == tmp_path / "equipe" / "carteira.sqlite3"


def test_caminho_padrao_fica_na_pasta_de_dados_do_usuario_e_fora_do_repositorio(monkeypatch):
    from core.project_store import (
        RAIZ_PROJETO,
        VARIAVEL_BANCO,
        caminho_banco_padrao,
        pasta_dados_usuario,
    )

    monkeypatch.delenv(VARIAVEL_BANCO, raising=False)
    padrao = caminho_banco_padrao()
    assert padrao.parent == pasta_dados_usuario()
    assert padrao.name == "projetos_industriais.sqlite3"
    # O repositório costuma viver numa pasta sincronizada; o banco, não.
    assert RAIZ_PROJETO not in padrao.parents
    # E nunca em AppData: aplicativos empacotados (MSIX) virtualizam essa
    # pasta, e o banco gravado por eles some para um terminal comum.
    assert "AppData" not in padrao.parts


def test_banco_antigo_em_data_e_migrado_uma_vez_e_renomeado(tmp_path, monkeypatch):
    """O banco que ficava em ``data/`` vai para o novo lugar na primeira abertura."""
    from core import project_store

    legado = tmp_path / "data" / "projetos_industriais.sqlite3"
    novo = tmp_path / "perfil" / "MecanicaToolkit" / "projetos_industriais.sqlite3"
    criar_projeto("Herdado", codigo="LEG-1", caminho_banco=legado)

    monkeypatch.delenv(project_store.VARIAVEL_BANCO, raising=False)
    monkeypatch.setattr(project_store, "BANCO_LEGADO", legado)
    monkeypatch.setattr(project_store, "_BANCO_INSTALACAO", novo)
    monkeypatch.setattr(project_store, "BANCO_PADRAO", novo)

    assert [item["codigo"] for item in listar_projetos()] == ["LEG-1"]
    assert novo.exists()
    assert not legado.exists()
    assert legado.with_name("projetos_industriais.sqlite3.migrado").exists()

    # Segunda abertura: nada a migrar, e o que foi gravado no novo banco fica.
    criar_projeto("Novo", codigo="NEW-1")
    assert {item["codigo"] for item in listar_projetos()} == {"LEG-1", "NEW-1"}


def test_migracao_nao_toca_num_banco_apontado_pela_variavel_de_ambiente(tmp_path, monkeypatch):
    from core import project_store

    legado = tmp_path / "data" / "projetos_industriais.sqlite3"
    escolhido = tmp_path / "escolhido.sqlite3"
    criar_projeto("Herdado", codigo="LEG-1", caminho_banco=legado)

    monkeypatch.setenv(project_store.VARIAVEL_BANCO, str(escolhido))
    monkeypatch.setattr(project_store, "BANCO_LEGADO", legado)
    monkeypatch.setattr(project_store, "_BANCO_INSTALACAO", escolhido)
    monkeypatch.setattr(project_store, "BANCO_PADRAO", escolhido)

    assert listar_projetos() == []
    assert legado.exists()


# ------------------------------------------------------- gravações concorrentes


def test_gravacao_por_cima_de_outra_sessao_e_recusada(tmp_path):
    from core.project_store import ProjetoConflitoErro, obter_projeto

    banco = tmp_path / "projetos.sqlite3"
    criado = criar_projeto("Compartilhado", codigo="PRJ-C", caminho_banco=banco)
    assert criado["gravacao"] == 0

    aba_a = obter_projeto(criado["id"], caminho_banco=banco)
    aba_b = obter_projeto(criado["id"], caminho_banco=banco)
    assert aba_a["gravacao"] == aba_b["gravacao"] == 0

    aba_a["objetivo"] = "Objetivo escrito na aba A"
    salvo_a = salvar_projeto(aba_a, motivo="Aba A", caminho_banco=banco)
    assert salvo_a["gravacao"] == 1

    aba_b["objetivo"] = "Objetivo escrito na aba B, sem ver o da A"
    with pytest.raises(ProjetoConflitoErro, match="outra sessão"):
        salvar_projeto(aba_b, motivo="Aba B", caminho_banco=banco)
    assert (
        obter_projeto(criado["id"], caminho_banco=banco)["objetivo"] == "Objetivo escrito na aba A"
    )

    # A aba B recarrega e aí consegue gravar; a A, agora defasada, é recusada.
    aba_b = obter_projeto(criado["id"], caminho_banco=banco)
    aba_b["objetivo"] = "Objetivo revisto pela aba B"
    salvo_b = salvar_projeto(aba_b, motivo="Aba B", caminho_banco=banco)
    assert salvo_b["gravacao"] == 2
    with pytest.raises(ProjetoConflitoErro):
        salvar_projeto(salvo_a, motivo="Aba A de novo", caminho_banco=banco)

    # O documento *devolvido* por um salvamento serve para o próximo; o que
    # foi passado continua com o contador antigo e seria recusado.
    assert salvar_projeto(salvo_b, motivo="Aba B de novo", caminho_banco=banco)["gravacao"] == 3
    with pytest.raises(ProjetoConflitoErro):
        salvar_projeto(aba_b, motivo="Documento defasado", caminho_banco=banco)


def test_restaurar_revisao_e_sobrescrita_deliberada(tmp_path):
    """A fotografia de uma revisão não carrega contador: restaurar é escolha."""
    from core.project_store import obter_projeto

    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto("Restauravel", codigo="PRJ-R", caminho_banco=banco)
    projeto["objetivo"] = "Marco"
    projeto = salvar_projeto(projeto, motivo="Marco", criar_revisao=True, caminho_banco=banco)
    projeto["objetivo"] = "Depois do marco"
    salvar_projeto(projeto, motivo="Edição", caminho_banco=banco)

    restaurado = restaurar_revisao(projeto["id"], 1, caminho_banco=banco)
    assert restaurado["objetivo"] == "Marco"
    assert restaurado["gravacao"] == obter_projeto(projeto["id"], caminho_banco=banco)["gravacao"]


def test_banco_criado_antes_do_contador_ganha_a_coluna_na_abertura(tmp_path):
    """Um banco do esquema anterior (sem ``write_seq``) continua abrindo."""
    import sqlite3

    from core.project_store import novo_projeto_documento, obter_projeto

    banco = tmp_path / "antigo.sqlite3"
    documento = novo_projeto_documento("Antigo", codigo="PRJ-A")
    with sqlite3.connect(banco) as conexao:
        conexao.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, code TEXT NOT NULL,
                status TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        conexao.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
            (
                documento["id"],
                documento["nome"],
                documento["codigo"],
                documento["status"],
                documento["criado_em"],
                documento["atualizado_em"],
                json.dumps(documento, ensure_ascii=False),
            ),
        )

    lido = obter_projeto(documento["id"], caminho_banco=banco)
    assert lido["gravacao"] == 0
    lido["objetivo"] = "Atualizado no esquema novo"
    assert salvar_projeto(lido, motivo="Primeira gravação", caminho_banco=banco)["gravacao"] == 1


def test_contador_de_gravacoes_nao_vaza_para_exportacoes_nem_fotografias(tmp_path):
    from core.project_store import obter_revisao

    banco = tmp_path / "projetos.sqlite3"
    projeto = criar_projeto("Sem token", codigo="PRJ-T", caminho_banco=banco)
    projeto = salvar_projeto(projeto, motivo="Marco", criar_revisao=True, caminho_banco=banco)

    pacote = json.loads(exportar_projeto(projeto["id"], caminho_banco=banco))
    assert "gravacao" not in pacote["projeto"]
    assert "gravacao" not in obter_revisao(projeto["id"], 1, caminho_banco=banco)


# ---------------------------------------------------------- backup e carteira


def test_backup_e_uma_copia_integra_que_nunca_sobrescreve(tmp_path):
    from core.project_store import ProjetoPersistenciaErro, fazer_backup, listar_backups

    banco = tmp_path / "dados" / "projetos.sqlite3"
    criar_projeto("Para o backup", codigo="PRJ-B", caminho_banco=banco)

    primeiro = fazer_backup(caminho_banco=banco)
    segundo = fazer_backup(caminho_banco=banco)
    assert primeiro.parent == segundo.parent == banco.parent / "backups"
    assert primeiro != segundo
    assert [item["codigo"] for item in listar_projetos(caminho_banco=primeiro)] == ["PRJ-B"]

    nomes = {item["nome"] for item in listar_backups(caminho_banco=banco)}
    assert nomes == {primeiro.name, segundo.name}

    with pytest.raises(ProjetoPersistenciaErro, match="nao sobrescreve"):
        fazer_backup(primeiro, caminho_banco=banco)

    # O banco original continua íntegro e gravável depois do VACUUM INTO.
    criar_projeto("Depois do backup", codigo="PRJ-B2", caminho_banco=banco)
    assert len(listar_projetos(caminho_banco=banco)) == 2
    assert len(listar_projetos(caminho_banco=primeiro)) == 1


def test_carteira_exportada_restaura_identidade_revisoes_e_linha_do_tempo(tmp_path):
    from core.project_store import (
        ProjetoPersistenciaErro,
        exportar_carteira,
        historico_eventos,
        importar_carteira,
        obter_projeto,
        obter_revisao,
    )

    origem = tmp_path / "origem.sqlite3"
    alfa = criar_projeto("Alfa", codigo="PRJ-ALFA", caminho_banco=origem)
    alfa["objetivo"] = "Marco do alfa"
    alfa = salvar_projeto(alfa, motivo="Marco", criar_revisao=True, caminho_banco=origem)
    beta = criar_projeto("Beta", codigo="PRJ-BETA", caminho_banco=origem)
    arquivar_projeto(beta["id"], caminho_banco=origem)

    pacote = exportar_carteira(caminho_banco=origem)
    conteudo = json.loads(pacote)
    assert conteudo["formato"] == "mecanica-toolkit-carteira"
    assert {item["projeto"]["codigo"] for item in conteudo["projetos"]} == {"PRJ-ALFA", "PRJ-BETA"}
    assert all("gravacao" not in item["projeto"] for item in conteudo["projetos"])

    destino = tmp_path / "destino.sqlite3"
    resultado = importar_carteira(pacote, caminho_banco=destino)
    assert sorted(resultado["importados"]) == ["PRJ-ALFA", "PRJ-BETA"]
    assert resultado["ignorados"] == []

    restaurado = obter_projeto(alfa["id"], caminho_banco=destino)
    assert restaurado["codigo"] == "PRJ-ALFA"
    assert restaurado["nome"] == "Alfa"
    assert restaurado["revisao"] == 1
    assert restaurado["objetivo"] == "Marco do alfa"
    revisoes = historico_revisoes(alfa["id"], caminho_banco=destino)
    assert [item["revisao"] for item in revisoes] == [1, 0]
    assert obter_revisao(alfa["id"], 0, caminho_banco=destino)["objetivo"] == ""
    tipos = [evento["tipo"] for evento in historico_eventos(alfa["id"], caminho_banco=destino)]
    assert tipos[0] == "administracao"
    assert "criacao" in tipos
    assert "revisao" in tipos
    assert obter_projeto(beta["id"], caminho_banco=destino)["status"] == "Arquivado"
    assert obter_projeto_ativo(caminho_banco=destino) is None

    # Restaurar de novo não duplica nem sobrescreve.
    repetido = importar_carteira(pacote, caminho_banco=destino)
    assert repetido == {"importados": [], "ignorados": ["PRJ-ALFA", "PRJ-BETA"]}
    assert len(listar_projetos(incluir_arquivados=True, caminho_banco=destino)) == 2

    # Um projeto individual não é carteira, e vice-versa.
    individual = exportar_projeto(alfa["id"], caminho_banco=origem)
    with pytest.raises(ProjetoPersistenciaErro, match="carteira"):
        importar_carteira(individual, caminho_banco=destino)
    with pytest.raises(ProjetoPersistenciaErro):
        importar_projeto(pacote, caminho_banco=destino)


def test_carteira_malformada_nao_deixa_metade_dos_projetos_no_banco(tmp_path):
    from core.project_store import ProjetoPersistenciaErro, exportar_carteira, importar_carteira

    origem = tmp_path / "origem.sqlite3"
    criar_projeto("Um", codigo="PRJ-1", caminho_banco=origem)
    criar_projeto("Dois", codigo="PRJ-2", caminho_banco=origem)
    conteudo = json.loads(exportar_carteira(caminho_banco=origem))
    # A revisão do segundo projeto perde a fotografia: o pacote é inválido.
    conteudo["projetos"][1]["revisoes"][0].pop("documento")

    destino = tmp_path / "destino.sqlite3"
    with pytest.raises(ProjetoPersistenciaErro, match="sem documento"):
        importar_carteira(json.dumps(conteudo), caminho_banco=destino)
    assert listar_projetos(incluir_arquivados=True, caminho_banco=destino) == []
