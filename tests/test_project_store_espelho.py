"""O banco de projetos com o espelho remoto: cada gravação sai, cada reinício volta.

O servidor falso do GitHub (``github_falso.py``) faz o papel do repositório de dados. O "disco
apagado" do Streamlit Cloud é simulado trocando o arquivo SQLite por outro, vazio.
"""

from __future__ import annotations

import json

from core import espelho_remoto as er
from core.project_store import (
    FORMATO_ESPELHO,
    adicionar_registro_tecnico,
    arquivar_projeto,
    criar_item,
    criar_projeto,
    duplicar_projeto,
    enviar_projetos_ao_espelho,
    excluir_projeto,
    exportar_carteira,
    exportar_projeto,
    historico_eventos,
    historico_revisoes,
    importar_carteira,
    importar_projeto,
    listar_projetos,
    obter_projeto,
    restaurar_projetos_do_espelho,
    salvar_projeto,
)

RAIZ = "mecanica_toolkit/projetos"


def caminho_remoto(projeto: dict) -> str:
    return f"{RAIZ}/{projeto['id']}.json"


def projeto_cheio(banco, *, nome="Mezanino da britagem", codigo="PRJ-1"):
    """Projeto com componente, duas revisões e um registro técnico: o suficiente para conferir o histórico."""
    projeto = criar_projeto(nome, codigo=codigo, objetivo="Verificar.", caminho_banco=banco)
    projeto["componentes"] = [criar_item(tag="P1", descricao="Pilar", material="A572 Gr.50")]
    projeto = salvar_projeto(
        projeto, motivo="Escopo cadastrado", criar_revisao=True, caminho_banco=banco
    )
    return adicionar_registro_tecnico(
        projeto["id"],
        {
            "modulo": "Flambagem de colunas",
            "titulo": "Pilar P1",
            "status": "Atende",
            "entradas": {"L_mm": 3000.0},
            "resultados": {"aproveitamento": 0.6},
            "conclusao": "Atende.",
        },
        caminho_banco=banco,
    )


class TestGravacaoVaiParaOEspelho:
    def test_cada_operacao_de_escrita_aparece_no_repositorio(
        self, tmp_path, espelho_github, github_falso
    ):
        banco = tmp_path / "p.sqlite3"
        projeto = criar_projeto("Mezanino", codigo="PRJ-1", caminho_banco=banco)
        remoto = github_falso.documento(caminho_remoto(projeto))
        assert remoto["formato"] == FORMATO_ESPELHO
        assert remoto["projeto"]["nome"] == "Mezanino"
        assert [r["revisao"] for r in remoto["revisoes"]] == [0]
        assert [e["tipo"] for e in remoto["eventos"]] == ["criacao"]

        projeto["objetivo"] = "Verificar a estrutura."
        projeto = salvar_projeto(
            projeto, motivo="Objetivo definido", criar_revisao=True, caminho_banco=banco
        )
        remoto = github_falso.documento(caminho_remoto(projeto))
        assert remoto["projeto"]["objetivo"] == "Verificar a estrutura."
        assert remoto["projeto"]["revisao"] == 1
        assert [r["revisao"] for r in remoto["revisoes"]] == [0, 1]
        assert github_falso.commits[-1][2] == "Projeto PRJ-1: Revisão 01: Objetivo definido"

        copia = duplicar_projeto(projeto["id"], novo_nome="Cópia", caminho_banco=banco)
        assert github_falso.documento(caminho_remoto(copia))["projeto"]["nome"] == "Cópia"

        importado = importar_projeto(
            exportar_projeto(projeto["id"], caminho_banco=banco), caminho_banco=banco
        )
        assert github_falso.documento(caminho_remoto(importado))["projeto"]["nome"].endswith(
            "importado"
        )

        arquivar_projeto(copia["id"], caminho_banco=banco)
        arquivado = github_falso.documento(caminho_remoto(copia))
        assert arquivado["projeto"]["status"] == "Arquivado"
        assert arquivado["eventos"][-1]["tipo"] == "situacao"

        excluir_projeto(copia["id"], caminho_banco=banco)
        assert caminho_remoto(copia) not in github_falso.arquivos
        assert caminho_remoto(projeto) in github_falso.arquivos
        assert er.situacao().pendentes == 0

    def test_o_arquivo_do_espelho_e_o_mesmo_item_da_carteira_exportada(
        self, tmp_path, espelho_github, github_falso
    ):
        banco = tmp_path / "p.sqlite3"
        projeto = projeto_cheio(banco)
        remoto = github_falso.documento(caminho_remoto(projeto))
        item = json.loads(exportar_carteira(caminho_banco=banco))["projetos"][0]
        assert {chave: remoto[chave] for chave in ("projeto", "revisoes", "eventos")} == item

    def test_a_mensagem_do_commit_nomeia_o_projeto_e_o_motivo(
        self, tmp_path, espelho_github, github_falso
    ):
        banco = tmp_path / "p.sqlite3"
        projeto_cheio(banco, codigo="PRJ-77")
        mensagens = [m for _, _, m in github_falso.commits]
        assert mensagens[0] == "Projeto PRJ-77: Criação do projeto"
        assert all(m.startswith("Projeto PRJ-77: ") for m in mensagens)
        assert any("Registro técnico incluído" in m for m in mensagens)

    def test_o_salvamento_local_nao_depende_do_espelho(
        self, tmp_path, espelho_github, github_falso
    ):
        banco = tmp_path / "p.sqlite3"
        projeto = criar_projeto("Mezanino", codigo="PRJ-1", caminho_banco=banco)
        github_falso.falhas.append(("PUT", 500))
        projeto["objetivo"] = "Objetivo novo."
        salvo = salvar_projeto(projeto, motivo="Objetivo", caminho_banco=banco)

        assert obter_projeto(salvo["id"], caminho_banco=banco)["objetivo"] == "Objetivo novo."
        situacao = er.situacao()
        assert situacao.pendentes == 1 and "500" in situacao.ultimo_erro
        # O arquivo do espelho ainda está na versão anterior...
        assert github_falso.documento(caminho_remoto(salvo))["projeto"]["objetivo"] == ""
        # ...até a próxima oportunidade, que reenvia o que ficou para trás.
        assert er.reenviar_pendentes() == 0
        assert (
            github_falso.documento(caminho_remoto(salvo))["projeto"]["objetivo"] == "Objetivo novo."
        )

    def test_com_o_github_fora_do_ar_nada_do_programa_quebra(
        self, tmp_path, espelho_github, github_falso
    ):
        github_falso.parar()
        banco = tmp_path / "p.sqlite3"
        projeto = criar_projeto("Mezanino", codigo="PRJ-1", caminho_banco=banco)
        projeto["objetivo"] = "Mesmo assim."
        salvar_projeto(projeto, caminho_banco=banco)
        assert listar_projetos(caminho_banco=banco)[0]["nome"] == "Mezanino"
        assert "Sem conexão" in er.situacao().ultimo_erro

    def test_sem_espelho_configurado_nenhuma_requisicao_e_feita(self, tmp_path, github_falso):
        banco = tmp_path / "p.sqlite3"
        projeto_cheio(banco)
        assert github_falso.requisicoes == []


class TestRestauracao:
    def test_um_disco_novo_recupera_projetos_revisoes_e_linha_do_tempo(
        self, tmp_path, espelho_github, github_falso
    ):
        antigo = tmp_path / "antes.sqlite3"
        a = projeto_cheio(antigo, nome="Mezanino", codigo="PRJ-1")
        b = projeto_cheio(antigo, nome="Escada", codigo="PRJ-2")
        revisoes_a = historico_revisoes(a["id"], caminho_banco=antigo)
        eventos_a = historico_eventos(a["id"], caminho_banco=antigo)
        envios_antes = len(github_falso.commits)

        novo = tmp_path / "depois.sqlite3"  # o disco apagado do Streamlit Cloud
        resultado = restaurar_projetos_do_espelho(caminho_banco=novo)

        assert sorted(resultado["importados"]) == ["PRJ-1", "PRJ-2"]
        assert resultado["falhas"] == {}
        assert {p["id"] for p in listar_projetos(caminho_banco=novo)} == {a["id"], b["id"]}
        restaurado = obter_projeto(a["id"], caminho_banco=novo)
        assert restaurado["nome"] == "Mezanino"
        assert len(restaurado["registros_tecnicos"]) == 1
        assert historico_revisoes(a["id"], caminho_banco=novo) == revisoes_a
        # Nem o evento "Restaurado…" nem um envio de volta: o que veio de lá já está lá.
        assert historico_eventos(a["id"], caminho_banco=novo) == eventos_a
        assert len(github_falso.commits) == envios_antes

    def test_restaurar_de_novo_nao_duplica_nem_sobrescreve(
        self, tmp_path, espelho_github, github_falso
    ):
        antigo = tmp_path / "antes.sqlite3"
        a = projeto_cheio(antigo)
        novo = tmp_path / "depois.sqlite3"
        restaurar_projetos_do_espelho(caminho_banco=novo)

        # Trabalho feito no disco novo enquanto o espelho estava desligado.
        er.definir_espelho(None)
        trabalho = obter_projeto(a["id"], caminho_banco=novo)
        trabalho["objetivo"] = "Alteração local ainda não enviada."
        salvar_projeto(trabalho, caminho_banco=novo)
        er.definir_espelho(espelho_github)

        segunda = restaurar_projetos_do_espelho(caminho_banco=novo)
        assert segunda["importados"] == []
        assert len(listar_projetos(caminho_banco=novo)) == 1
        assert (
            obter_projeto(a["id"], caminho_banco=novo)["objetivo"]
            == "Alteração local ainda não enviada."
        )

    def test_arquivo_ilegivel_nao_impede_os_demais(self, tmp_path, espelho_github, github_falso):
        antigo = tmp_path / "antes.sqlite3"
        projeto_cheio(antigo, nome="Bom", codigo="PRJ-OK")
        github_falso.arquivos[f"{RAIZ}/lixo.json"] = b"isto nao e json"
        github_falso.arquivos[f"{RAIZ}/outro.json"] = json.dumps({"formato": "qualquer"}).encode()
        github_falso.arquivos[f"{RAIZ}/sem-acesso.json"] = b"{}"
        github_falso.falhas_de_leitura[f"{RAIZ}/sem-acesso.json"] = 500

        resultado = restaurar_projetos_do_espelho(caminho_banco=tmp_path / "novo.sqlite3")
        assert resultado["importados"] == ["PRJ-OK"]
        assert set(resultado["falhas"]) == {"lixo.json", "outro.json", "sem-acesso.json"}
        assert "invalido" in resultado["falhas"]["lixo.json"].lower()
        assert "500" in resultado["falhas"]["sem-acesso.json"]

    def test_sem_espelho_a_restauracao_nao_faz_nada(self, tmp_path):
        resultado = restaurar_projetos_do_espelho(caminho_banco=tmp_path / "novo.sqlite3")
        assert resultado == {"importados": [], "falhas": {}}

    def test_falha_de_acesso_sobe_para_quem_chamou_avisar(
        self, tmp_path, espelho_github, github_falso
    ):
        github_falso.token = "outro-token"  # o do cliente passa a ser recusado (401)
        import pytest

        with pytest.raises(er.EspelhoErro, match="recusou o token"):
            restaurar_projetos_do_espelho(caminho_banco=tmp_path / "novo.sqlite3")


class TestEnvioCompleto:
    def test_enviar_tudo_leva_inclusive_os_arquivados(self, tmp_path, github_falso):
        banco = tmp_path / "p.sqlite3"
        a = projeto_cheio(banco, nome="A", codigo="PRJ-A")
        b = projeto_cheio(banco, nome="B", codigo="PRJ-B")
        arquivar_projeto(b["id"], caminho_banco=banco)
        assert github_falso.requisicoes == []  # espelho ainda desligado

        er.definir_espelho(
            er.EspelhoGitHub(
                er.ConfiguracaoGitHub(
                    repositorio=github_falso.repositorio,
                    token=github_falso.token,
                    api=github_falso.url,
                )
            )
        )
        resultado = enviar_projetos_ao_espelho(caminho_banco=banco)
        assert resultado == {"projetos": 2, "pendentes": 0}
        assert caminho_remoto(a) in github_falso.arquivos
        assert github_falso.documento(caminho_remoto(b))["projeto"]["status"] == "Arquivado"

    def test_importar_carteira_envia_mas_a_restauracao_do_espelho_nao(
        self, tmp_path, espelho_github, github_falso
    ):
        origem = tmp_path / "origem.sqlite3"
        er.definir_espelho(None)
        projeto = projeto_cheio(origem)
        pacote = exportar_carteira(caminho_banco=origem)
        er.definir_espelho(espelho_github)

        importar_carteira(pacote, caminho_banco=tmp_path / "destino.sqlite3")
        assert caminho_remoto(projeto) in github_falso.arquivos
        n = len(github_falso.commits)
        importar_carteira(
            pacote,
            caminho_banco=tmp_path / "outro.sqlite3",
            registrar_evento=False,
            espelhar=False,
        )
        assert len(github_falso.commits) == n
