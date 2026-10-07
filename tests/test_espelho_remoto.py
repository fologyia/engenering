"""O espelho remoto: cliente da API de conteúdo do GitHub e fila de pendências.

Roda contra ``github_falso.GitHubFalso``, que guarda os arquivos e repete as regras do GitHub
(``sha`` obrigatório para atualizar, ``sha`` velho recusado, 404 para repositório sem acesso).
"""

from __future__ import annotations

import base64
import json

import pytest

from core import espelho_remoto as er
from core.espelho_remoto import ConfiguracaoGitHub, EspelhoErro, EspelhoGitHub

RAIZ = "mecanica_toolkit"


def configuracao(github, **extra) -> ConfiguracaoGitHub:
    return ConfiguracaoGitHub(
        repositorio=extra.pop("repositorio", github.repositorio),
        token=extra.pop("token", github.token),
        api=github.url,
        **extra,
    )


class TestConfiguracao:
    def test_sem_variaveis_o_espelho_nao_liga(self):
        assert er.configuracao_do_ambiente({}) is None

    def test_le_as_variaveis_de_ambiente(self):
        config = er.configuracao_do_ambiente(
            {
                er.VARIAVEL_REPOSITORIO: " fologyia/dados ",
                er.VARIAVEL_TOKEN: "segredo",
                er.VARIAVEL_RAMO: "armazem",
                er.VARIAVEL_PASTA: "/meus/dados/",
            }
        )
        assert config is not None
        assert (config.repositorio, config.ramo, config.pasta) == (
            "fologyia/dados",
            "armazem",
            "meus/dados",
        )
        assert config.api == "https://api.github.com"

    def test_configuracao_pela_metade_levanta_erro_que_diz_o_que_falta(self):
        with pytest.raises(EspelhoErro, match=er.VARIAVEL_REPOSITORIO):
            er.configuracao_do_ambiente({er.VARIAVEL_TOKEN: "segredo"})
        with pytest.raises(EspelhoErro, match=er.VARIAVEL_TOKEN):
            er.configuracao_do_ambiente({er.VARIAVEL_REPOSITORIO: "fologyia/dados"})

    def test_repositorio_fora_do_formato_dono_nome_e_recusado(self):
        with pytest.raises(EspelhoErro, match="dono/nome"):
            ConfiguracaoGitHub(repositorio="fologyia", token="segredo")
        with pytest.raises(EspelhoErro, match="dono/nome"):
            ConfiguracaoGitHub(repositorio="https://github.com/fologyia/dados", token="segredo")

    def test_o_token_nunca_aparece_na_representacao_do_objeto(self):
        config = ConfiguracaoGitHub(repositorio="fologyia/dados", token="segredo-muito-secreto")
        assert "segredo-muito-secreto" not in repr(config)

    def test_a_api_so_aceita_http_para_o_proprio_computador(self):
        with pytest.raises(EspelhoErro, match="https"):
            ConfiguracaoGitHub(repositorio="a/b", token="t", api="http://exemplo.com")
        ConfiguracaoGitHub(repositorio="a/b", token="t", api="http://127.0.0.1:9999")

    def test_a_situacao_mostra_a_configuracao_pela_metade(self, monkeypatch):
        er.redefinir()  # o conftest fixa "sem espelho"; aqui vale o que está no ambiente
        monkeypatch.setenv(er.VARIAVEL_TOKEN, "segredo")
        situacao = er.situacao()
        assert not situacao.configurado
        assert er.VARIAVEL_REPOSITORIO in situacao.problema_de_configuracao
        assert er.VARIAVEL_REPOSITORIO in situacao.ultimo_erro

    def test_o_espelho_vem_do_ambiente_quando_nada_o_substitui(self, monkeypatch):
        er.redefinir()
        monkeypatch.setenv(er.VARIAVEL_REPOSITORIO, "fologyia/dados")
        monkeypatch.setenv(er.VARIAVEL_TOKEN, "segredo")
        espelho = er.obter_espelho()
        assert espelho is not None and espelho.configuracao.repositorio == "fologyia/dados"
        assert er.obter_espelho() is espelho  # o mesmo cliente enquanto a configuração não muda
        assert er.situacao().destino == "fologyia/dados"


class TestCliente:
    def test_cria_atualiza_le_lista_e_apaga(self, github_falso):
        espelho = EspelhoGitHub(configuracao(github_falso))
        espelho.gravar("projetos/a.json", b'{"v": 1}', "cria")
        assert github_falso.arquivos[f"{RAIZ}/projetos/a.json"] == b'{"v": 1}'

        espelho.gravar(
            "projetos/a.json", b'{"v": 2}', "atualiza"
        )  # usa o sha que ele mesmo guardou
        assert github_falso.arquivos[f"{RAIZ}/projetos/a.json"] == b'{"v": 2}'
        assert espelho.ler("projetos/a.json") == b'{"v": 2}'
        assert set(espelho.listar("projetos")) == {"a.json"}

        espelho.apagar("projetos/a.json", "apaga")
        assert github_falso.arquivos == {}
        assert espelho.ler("projetos/a.json") is None
        assert [c[0] for c in github_falso.commits] == ["PUT", "PUT", "DELETE"]
        assert [c[2] for c in github_falso.commits] == ["cria", "atualiza", "apaga"]

    def test_cabecalhos_e_corpo_da_requisicao(self, github_falso):
        EspelhoGitHub(configuracao(github_falso)).gravar("projetos/a.json", "açã".encode(), "msg")
        pedido = github_falso.requisicoes[-1]
        assert pedido["metodo"] == "PUT"
        assert pedido["caminho"] == f"/repos/dono/dados/contents/{RAIZ}/projetos/a.json"
        assert pedido["cabecalhos"]["authorization"] == "Bearer token-de-teste"
        assert pedido["cabecalhos"]["x-github-api-version"] == "2022-11-28"
        assert pedido["cabecalhos"]["user-agent"] == "mecanica-toolkit"
        assert base64.b64decode(pedido["corpo"]["content"]).decode() == "açã"
        assert pedido["corpo"]["message"] == "msg"
        assert "branch" not in pedido["corpo"] and "sha" not in pedido["corpo"]

    def test_o_ramo_configurado_vai_na_gravacao_e_na_leitura(self, github_falso):
        github_falso.ramo = "armazem"
        espelho = EspelhoGitHub(configuracao(github_falso, ramo="armazem"))
        espelho.gravar("projetos/a.json", b"{}", "msg")
        assert github_falso.requisicoes[-1]["corpo"]["branch"] == "armazem"
        espelho.ler("projetos/a.json")
        assert github_falso.requisicoes[-1]["consulta"] == {"ref": "armazem"}

    def test_a_pasta_configurada_e_o_prefixo_de_todos_os_caminhos(self, github_falso):
        EspelhoGitHub(configuracao(github_falso, pasta="outra/pasta")).gravar("a.json", b"1", "m")
        assert list(github_falso.arquivos) == ["outra/pasta/a.json"]

    def test_arquivo_que_ja_existe_e_atualizado_sem_o_cliente_conhecer_o_sha(self, github_falso):
        github_falso.arquivos[f"{RAIZ}/projetos/a.json"] = b"antigo"
        espelho = EspelhoGitHub(configuracao(github_falso))  # cliente novo: cache de sha vazio
        espelho.gravar("projetos/a.json", b"novo", "msg")
        assert github_falso.arquivos[f"{RAIZ}/projetos/a.json"] == b"novo"
        # PUT recusado (422, sem sha), consulta do sha, PUT aceito.
        assert [r["metodo"] for r in github_falso.requisicoes] == ["PUT", "GET", "PUT"]

    def test_sha_velho_ganha_uma_nova_tentativa_com_o_sha_atual(self, github_falso):
        espelho = EspelhoGitHub(configuracao(github_falso))
        espelho.gravar("projetos/a.json", b"v1", "msg")
        github_falso.arquivos[f"{RAIZ}/projetos/a.json"] = b"alterado por fora"
        espelho.gravar("projetos/a.json", b"v2", "msg")
        assert github_falso.arquivos[f"{RAIZ}/projetos/a.json"] == b"v2"

    def test_conflito_que_persiste_vira_erro(self, github_falso):
        github_falso.falhas += [("PUT", 409), ("PUT", 409)]
        with pytest.raises(EspelhoErro, match="409"):
            EspelhoGitHub(configuracao(github_falso)).gravar("a.json", b"1", "msg")

    def test_apagar_o_que_nao_existe_conta_como_apagado(self, github_falso):
        EspelhoGitHub(configuracao(github_falso)).apagar("projetos/nao-existe.json", "msg")
        assert github_falso.commits == []

    def test_listar_uma_pasta_que_nao_existe_devolve_vazio(self, github_falso):
        assert EspelhoGitHub(configuracao(github_falso)).listar("projetos") == {}

    def test_ler_pede_o_conteudo_bruto_para_nao_esbarrar_no_limite_de_1_mb(self, github_falso):
        github_falso.arquivos[f"{RAIZ}/projetos/a.json"] = b"x" * 5000
        espelho = EspelhoGitHub(configuracao(github_falso))
        assert espelho.ler("projetos/a.json") == b"x" * 5000
        assert "raw" in github_falso.requisicoes[-1]["cabecalhos"]["accept"]

    @pytest.mark.parametrize(
        ("preparar", "trecho"),
        [
            (lambda g, c: c.update(token="tok-secreto-xyz"), "recusou o token"),
            (lambda g, c: setattr(g, "pode_gravar", False), "Contents: Read and write"),
            (lambda g, c: c.update(repositorio="dono/outro"), "não encontrou o repositório"),
            (lambda g, c: g.falhas.append(("PUT", 500)), "erro 500"),
        ],
        ids=["401", "403", "404", "500"],
    )
    def test_erros_do_github_viram_mensagens_que_dizem_o_que_fazer(
        self, github_falso, preparar, trecho
    ):
        extra: dict = {}
        preparar(github_falso, extra)
        with pytest.raises(EspelhoErro) as erro:
            EspelhoGitHub(configuracao(github_falso, **extra)).gravar("a.json", b"1", "msg")
        assert trecho in str(erro.value)
        # Nenhuma mensagem de erro (que vai para a tela) pode carregar o token.
        assert "tok-secreto-xyz" not in str(erro.value)
        assert github_falso.token not in str(erro.value)

    def test_sem_conexao_a_mensagem_diz_isso(self, github_falso):
        espelho = EspelhoGitHub(configuracao(github_falso), tempo_limite=2.0)
        github_falso.parar()  # a porta deixa de atender
        with pytest.raises(EspelhoErro, match="Sem conexão com o GitHub"):
            espelho.gravar("a.json", b"1", "msg")

    def test_resposta_que_nao_e_json_vira_erro_claro(self, github_falso):
        espelho = EspelhoGitHub(configuracao(github_falso))
        github_falso.falhas.append(("GET", 200))
        with pytest.raises(EspelhoErro, match="não é a esperada"):
            espelho.listar("projetos")
        github_falso.falhas.append(("GET", 200))
        with pytest.raises(EspelhoErro, match="não é a esperada"):
            espelho.testar()

    def test_gravacao_com_resposta_ilegivel_nao_e_erro_e_o_proximo_envio_consulta_o_sha(
        self, github_falso
    ):
        espelho = EspelhoGitHub(configuracao(github_falso))
        espelho.gravar("a.json", b"1", "cria")  # guarda o sha
        github_falso.falhas.append(("PUT", 200))  # a gravação "passa", mas a resposta é HTML
        espelho.gravar("a.json", b"2", "atualiza")
        assert espelho._shas.get("a.json") is None  # o atalho do sha foi descartado

    def test_testar_confere_repositorio_e_permissao(self, github_falso):
        espelho = EspelhoGitHub(configuracao(github_falso))
        assert espelho.testar() == "Conectado a dono/dados (privado)."
        github_falso.privado = False
        assert "PÚBLICO" in espelho.testar()
        github_falso.pode_gravar = False
        with pytest.raises(EspelhoErro, match="não pode gravar"):
            espelho.testar()
        with pytest.raises(EspelhoErro, match="não encontrou"):
            EspelhoGitHub(configuracao(github_falso, repositorio="dono/outro")).testar()


class TestFilaDePendencias:
    def test_sem_espelho_nada_acontece(self):
        assert er.obter_espelho() is None
        assert er.enviar("a.json", b"1", "msg") is False
        assert er.apagar("a.json", "msg") is False
        assert er.reenviar_pendentes() == 0
        assert er.baixar("projetos") == ({}, {})
        assert not er.situacao().configurado

    def test_envio_bem_sucedido_atualiza_a_situacao(self, espelho_github, github_falso):
        assert er.enviar("projetos/x.json", b'{"a": 1}', "msg") is True
        situacao = er.situacao()
        assert situacao.configurado and situacao.destino == "dono/dados"
        assert (situacao.enviados, situacao.pendentes, situacao.ultimo_erro) == (1, 0, "")
        assert situacao.ultimo_envio.endswith("+00:00")
        assert github_falso.documento(f"{RAIZ}/projetos/x.json") == {"a": 1}

    def test_envio_que_falha_fica_na_fila_e_nao_levanta(self, espelho_github, github_falso):
        github_falso.falhas.append(("PUT", 500))
        assert er.enviar("projetos/x.json", b"{}", "msg") is False
        situacao = er.situacao()
        assert situacao.pendentes == 1 and "500" in situacao.ultimo_erro
        assert github_falso.arquivos == {}

        assert er.reenviar_pendentes() == 0
        assert list(github_falso.arquivos) == [f"{RAIZ}/projetos/x.json"]
        assert er.situacao().ultimo_erro == ""

    def test_um_envio_que_da_certo_reenvia_o_que_ficou_para_tras(
        self, espelho_github, github_falso
    ):
        github_falso.falhas.append(("PUT", 503))
        er.enviar("projetos/a.json", b"1", "msg")
        assert er.situacao().pendentes == 1
        er.enviar("projetos/b.json", b"2", "msg")
        assert er.situacao().pendentes == 0
        assert github_falso.caminhos(f"{RAIZ}/projetos") == [
            f"{RAIZ}/projetos/a.json",
            f"{RAIZ}/projetos/b.json",
        ]

    def test_a_pendencia_mais_nova_substitui_a_antiga(self, espelho_github, github_falso):
        github_falso.falhas += [("PUT", 500), ("PUT", 500)]
        er.enviar("projetos/a.json", b"versao 1", "msg")
        er.enviar("projetos/a.json", b"versao 2", "msg")
        assert er.situacao().pendentes == 1
        er.reenviar_pendentes()
        assert github_falso.arquivos[f"{RAIZ}/projetos/a.json"] == b"versao 2"

    def test_exclusao_que_falha_tambem_fica_na_fila(self, espelho_github, github_falso):
        er.enviar("projetos/a.json", b"1", "cria")
        github_falso.falhas.append(("DELETE", 500))
        assert er.apagar("projetos/a.json", "apaga") is False
        assert er.situacao().pendentes == 1
        assert f"{RAIZ}/projetos/a.json" in github_falso.arquivos
        assert er.reenviar_pendentes() == 0
        assert github_falso.arquivos == {}

    def test_baixar_traz_so_os_json_e_separa_o_que_falhou(self, espelho_github, github_falso):
        pasta = f"{RAIZ}/projetos"
        github_falso.arquivos |= {
            f"{pasta}/a.json": b'{"n": 1}',
            f"{pasta}/b.json": b'{"n": 2}',
            f"{pasta}/c.json": b'{"n": 3}',
            f"{pasta}/leia-me.txt": b"ignorado",
        }
        github_falso.falhas_de_leitura[f"{pasta}/c.json"] = 500
        conteudos, erros = er.baixar("projetos")
        assert {n: json.loads(c) for n, c in conteudos.items()} == {
            "a.json": {"n": 1},
            "b.json": {"n": 2},
        }
        assert list(erros) == ["c.json"] and "500" in erros["c.json"]

    def test_falha_ao_listar_a_pasta_levanta_o_erro_para_quem_restaura_decidir(
        self, espelho_github, github_falso
    ):
        github_falso.falhas.append(("GET", 500))
        with pytest.raises(EspelhoErro, match="500"):
            er.baixar("projetos")

    def test_testar_conexao_sem_espelho_explica_o_que_configurar(self):
        with pytest.raises(EspelhoErro, match=er.VARIAVEL_REPOSITORIO):
            er.testar_conexao()


class TestNuncaLevanta:
    """O disco já foi gravado quando o envio começa: nada do espelho pode derrubar quem salva."""

    @pytest.fixture
    def quebrado(self, espelho_github, monkeypatch):
        def explodir(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(EspelhoGitHub, "gravar", explodir)
        monkeypatch.setattr(EspelhoGitHub, "apagar", explodir)

    def test_excecao_inesperada_no_envio_vira_pendencia_e_mensagem(self, quebrado):
        assert er.enviar("projetos/a.json", b"1", "msg") is False
        situacao = er.situacao()
        assert situacao.pendentes == 1
        assert "RuntimeError" in situacao.ultimo_erro and "boom" in situacao.ultimo_erro

    def test_excecao_inesperada_na_exclusao_e_na_fila(self, quebrado):
        assert er.apagar("projetos/a.json", "msg") is False
        assert er.situacao().pendentes == 1
        assert er.reenviar_pendentes() == 1  # tenta de novo e continua falhando, sem levantar
