"""Onde os dados ficam: ambiente, estado do espelho, restauração na partida e avisos na tela.

A tela é exercitada com ``AppTest.from_function`` sobre as funções de ``components/armazenamento_ui``:
os testes cobrem o que o usuário lê — o aviso de dados temporários, o estado do GitHub, os botões —
sem depender de como o ``app.py`` as encadeia.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import armazenamento as arm
from core import espelho_remoto as er
from core import material_catalog, section_catalog
from core.project_store import (
    criar_projeto,
    listar_projetos,
    salvar_projeto,
)

RAIZ_REMOTA = "mecanica_toolkit"
PERFIL = {
    "nome": "W teste 200 x 20",
    "familia": "W (mesa larga)",
    "area_mm2": 2_550.0,
    "ix_mm4": 1.66e7,
    "iy_mm4": 1.15e6,
    "zx_mm3": 1.9e5,
    "zy_mm3": 3.6e4,
    "j_mm4": 6.0e4,
    "cw_mm6": 1.1e10,
    "altura_mm": 203.0,
    "largura_mm": 102.0,
    "espessura_alma_mm": 5.8,
    "espessura_mesa_mm": 6.5,
    "area_cisalhamento_mm2": 1_177.0,
    "massa_kg_m": 20.0,
    "descricao": "Perfil usado nos testes",
}
MATERIAL = {
    "nome": "ASTM A992 (teste)",
    "categoria": "aco",
    "Sy_MPa": 345.0,
    "Sut_MPa": 450.0,
    "origem_propriedades": "ASTM A992/A992M — mínimos especificados",
    "aplicacoes": ["Perfis laminados"],
}


@pytest.fixture
def nuvem(monkeypatch):
    monkeypatch.setenv(arm.VARIAVEL_AMBIENTE, "nuvem")


@pytest.fixture
def catalogos_isolados(tmp_path, monkeypatch):
    perfis = tmp_path / "perfis_usuario.json"
    materiais = tmp_path / "materiais_usuario.json"
    monkeypatch.setattr(section_catalog, "ARQUIVO_USUARIO", perfis)
    monkeypatch.setattr(material_catalog, "ARQUIVO_USUARIO", materiais)
    return perfis, materiais


def projeto_no_espelho(tmp_path, nome="Mezanino", codigo="PRJ-1"):
    """Cria um projeto num disco que depois será "apagado": só o espelho guarda a cópia."""
    banco = tmp_path / f"descartado-{codigo}.sqlite3"
    projeto = criar_projeto(nome, codigo=codigo, objetivo="Verificar.", caminho_banco=banco)
    return salvar_projeto(projeto, motivo="Marco", criar_revisao=True, caminho_banco=banco)


class TestAmbiente:
    def test_o_streamlit_cloud_monta_o_codigo_em_mount_src(self):
        assert arm.ambiente(Path("/mount/src/engenering")) == arm.AMBIENTE_NUVEM
        assert arm.ambiente(Path("/mount/src")) == arm.AMBIENTE_NUVEM

    def test_um_computador_comum_e_local(self):
        assert arm.ambiente(Path("/home/gabriel/mecanica_toolkit")) == arm.AMBIENTE_LOCAL
        assert arm.ambiente(Path("/mount/srcx/outro")) == arm.AMBIENTE_LOCAL
        assert arm.ambiente(Path("C:/Users/Gabriel/Programa/mecanica_toolkit")) == "local"

    def test_a_variavel_de_ambiente_manda_mais_que_o_caminho(self, monkeypatch):
        monkeypatch.setenv(arm.VARIAVEL_AMBIENTE, "nuvem")
        assert arm.ambiente(Path("/home/gabriel/x")) == arm.AMBIENTE_NUVEM
        monkeypatch.setenv(arm.VARIAVEL_AMBIENTE, " LOCAL ")
        assert arm.ambiente(Path("/mount/src/engenering")) == arm.AMBIENTE_LOCAL
        monkeypatch.setenv(arm.VARIAVEL_AMBIENTE, "marte")  # valor desconhecido: ignora
        assert arm.ambiente(Path("/mount/src/engenering")) == arm.AMBIENTE_NUVEM


class TestSituacao:
    def test_no_computador_do_usuario_nao_ha_o_que_avisar(self):
        estado = arm.situacao()
        assert estado.nivel == arm.NIVEL_LOCAL and not estado.exige_atencao
        assert not estado.disco_descartavel
        assert arm.texto_de_confirmacao() == "Salvo no banco local."
        assert "banco local" in arm.frase_de_persistencia()

    def test_na_nuvem_sem_espelho_os_dados_sao_temporarios(self, nuvem):
        estado = arm.situacao()
        assert estado.nivel == arm.NIVEL_TEMPORARIO and estado.exige_atencao
        assert estado.disco_descartavel
        assert "temporários" in estado.titulo
        assert "apagado" in estado.detalhe and "carteira" in estado.detalhe
        assert "temporariamente" in arm.texto_de_confirmacao()
        assert "temporários" in arm.frase_de_persistencia()

    def test_na_nuvem_com_o_espelho_funcionando_os_dados_estao_protegidos(
        self, nuvem, espelho_github, github_falso, tmp_path
    ):
        estado = arm.situacao()
        assert estado.nivel == arm.NIVEL_PROTEGIDO and not estado.exige_atencao
        assert "dono/dados" in estado.detalhe and "Nenhuma gravação" in estado.detalhe
        projeto_no_espelho(tmp_path)
        assert "Último envio" in arm.situacao().detalhe
        assert arm.texto_de_confirmacao() == "Salvo e copiado para o GitHub."
        assert "GitHub" in arm.frase_de_persistencia()

    def test_espelho_com_falha_e_pendencias_vira_alerta_que_diz_o_que_fazer(
        self, nuvem, espelho_github, github_falso, tmp_path
    ):
        # As duas gravações do projeto (criação e revisão) falham: o mesmo arquivo fica na fila.
        github_falso.falhas += [("PUT", 500), ("PUT", 500)]
        projeto_no_espelho(tmp_path)
        estado = arm.situacao()
        assert estado.nivel == arm.NIVEL_FALHA and estado.exige_atencao
        assert "500" in estado.detalhe and "baixe a carteira" in estado.detalhe
        assert "cópia no GitHub falhou" in arm.texto_de_confirmacao()
        assert "problema" in arm.frase_de_persistencia()
        # Tudo reenviado: volta ao normal.
        arm.reenviar_pendencias(intervalo_s=0)
        assert arm.situacao().nivel == arm.NIVEL_PROTEGIDO

    def test_configuracao_pela_metade_aparece_como_problema_e_nao_some_em_silencio(
        self, monkeypatch
    ):
        er.redefinir()
        monkeypatch.setenv(er.VARIAVEL_TOKEN, "segredo")
        estado = arm.situacao()
        assert estado.nivel == arm.NIVEL_FALHA
        assert er.VARIAVEL_REPOSITORIO in estado.detalhe

    def test_fora_da_nuvem_o_espelho_tambem_e_mostrado(self, espelho_github):
        assert arm.situacao().nivel == arm.NIVEL_PROTEGIDO


class TestRestauracao:
    def test_sem_espelho_nao_ha_o_que_restaurar(self):
        assert arm.restaurar_do_espelho() is None
        assert not arm.restauracao_pendente()

    def test_o_disco_novo_recebe_os_projetos_uma_vez_por_processo(
        self, banco_isolado, espelho_github, github_falso, tmp_path
    ):
        projeto_no_espelho(tmp_path, "Mezanino", "PRJ-1")
        projeto_no_espelho(tmp_path, "Escada", "PRJ-2")
        assert arm.restauracao_pendente()
        assert listar_projetos() == []

        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and resultado.ok
        assert sorted(resultado.projetos) == ["PRJ-1", "PRJ-2"]
        assert {p["codigo"] for p in listar_projetos()} == {"PRJ-1", "PRJ-2"}
        assert not arm.restauracao_pendente()
        assert arm.restaurar_do_espelho() is None  # já feito neste processo

        again = arm.restaurar_do_espelho(forcar=True)  # "Recarregar do GitHub"
        assert again is not None and again.projetos == []

    def test_falha_na_leitura_vira_aviso_e_a_nova_tentativa_espera(
        self, banco_isolado, espelho_github, github_falso, tmp_path, monkeypatch
    ):
        projeto_no_espelho(tmp_path)
        github_falso.falhas.append(("GET", 503))
        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and not resultado.ok and "503" in resultado.erro
        estado = arm.situacao()
        assert estado.nivel == arm.NIVEL_FALHA and "carregar os dados do GitHub" in estado.detalhe
        assert arm.restauracao_pendente()

        assert arm.restaurar_do_espelho() is None  # dentro do intervalo: não insiste
        monkeypatch.setattr(arm, "INTERVALO_NOVA_TENTATIVA_S", 0.0)
        segunda = arm.restaurar_do_espelho()
        assert segunda is not None and segunda.ok and segunda.projetos == ["PRJ-1"]
        assert arm.situacao().nivel == arm.NIVEL_PROTEGIDO  # o erro antigo foi limpo

    def test_resposta_estranha_do_github_na_abertura_nao_derruba_o_aplicativo(
        self, banco_isolado, espelho_github, github_falso
    ):
        github_falso.falhas.append(("GET", 200))  # portal de rede em vez de JSON
        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and not resultado.ok
        assert "não é a esperada" in arm.situacao().detalhe

    def test_erro_inesperado_na_restauracao_vira_aviso_e_nao_excecao(
        self, banco_isolado, espelho_github, monkeypatch
    ):
        from core import project_store

        def quebrar(**_):
            raise RuntimeError("quebrou por dentro")

        monkeypatch.setattr(project_store, "restaurar_projetos_do_espelho", quebrar)
        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and not resultado.ok
        assert "RuntimeError: quebrou por dentro" in arm.situacao().detalhe

    def test_arquivo_ilegivel_e_relatado_mas_os_outros_voltam(
        self, banco_isolado, espelho_github, github_falso, tmp_path
    ):
        projeto_no_espelho(tmp_path)
        github_falso.arquivos[f"{RAIZ_REMOTA}/projetos/lixo.json"] = b"nao e json"
        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and not resultado.ok
        assert resultado.projetos == ["PRJ-1"] and list(resultado.falhas) == ["lixo.json"]
        assert "lixo.json" in arm.situacao().detalhe

    def test_catalogos_do_usuario_voltam_sem_sobrescrever_o_que_existe(
        self, banco_isolado, espelho_github, github_falso, catalogos_isolados
    ):
        perfis, materiais = catalogos_isolados
        github_falso.arquivos[f"{RAIZ_REMOTA}/catalogos/perfis_usuario.json"] = json.dumps(
            {"schema": section_catalog.SCHEMA, "origem": "", "perfis": []}
        ).encode()
        github_falso.arquivos[f"{RAIZ_REMOTA}/catalogos/materiais_usuario.json"] = b"{corrompido"
        materiais.write_text("{}", encoding="utf-8")  # já existe no disco: fica como está

        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and resultado.catalogos == ["perfis_usuario.json"]
        assert json.loads(perfis.read_text(encoding="utf-8"))["perfis"] == []
        assert materiais.read_text(encoding="utf-8") == "{}"

    def test_catalogo_corrompido_no_espelho_nao_vira_o_catalogo_do_programa(
        self, banco_isolado, espelho_github, github_falso, catalogos_isolados
    ):
        perfis, _ = catalogos_isolados
        github_falso.arquivos[f"{RAIZ_REMOTA}/catalogos/perfis_usuario.json"] = b"{corrompido"
        resultado = arm.restaurar_do_espelho()
        assert resultado is not None and resultado.catalogos == []
        assert not perfis.exists()


class TestCatalogosVaoParaOEspelho:
    def test_perfil_e_material_cadastrados_ganham_copia_no_github(
        self, espelho_github, github_falso, catalogos_isolados
    ):
        section_catalog.salvar_perfil(PERFIL)
        material_catalog.salvar_material(MATERIAL)
        perfis = github_falso.documento(f"{RAIZ_REMOTA}/catalogos/perfis_usuario.json")
        materiais = github_falso.documento(f"{RAIZ_REMOTA}/catalogos/materiais_usuario.json")
        assert [p["nome"] for p in perfis["perfis"]] == ["W teste 200 x 20"]
        assert [m["nome"] for m in materiais["materiais"]] == ["ASTM A992 (teste)"]

        section_catalog.remover_perfil("W teste 200 x 20")
        assert (
            github_falso.documento(f"{RAIZ_REMOTA}/catalogos/perfis_usuario.json")["perfis"] == []
        )

    def test_gravar_outro_arquivo_nao_e_espelhado(self, espelho_github, github_falso, tmp_path):
        section_catalog._gravar_arquivo(tmp_path / "qualquer.json", {"a": 1})
        assert github_falso.requisicoes == []


class TestEnvioCompleto:
    def test_enviar_tudo_leva_projetos_e_catalogos_que_existem(
        self, banco_isolado, espelho_github, github_falso, catalogos_isolados
    ):
        er.definir_espelho(None)  # o projeto e o catálogo nascem antes de o espelho existir
        criar_projeto("Mezanino", codigo="PRJ-1")
        perfis, _ = catalogos_isolados
        perfis.write_text(json.dumps({"schema": "x", "perfis": []}), encoding="utf-8")
        assert github_falso.requisicoes == []

        er.definir_espelho(espelho_github)
        resumo = arm.enviar_tudo()
        assert resumo == {"projetos": 1, "catalogos": 1, "pendentes": 0}
        assert len(github_falso.caminhos(f"{RAIZ_REMOTA}/projetos")) == 1
        assert github_falso.caminhos(f"{RAIZ_REMOTA}/catalogos") == [
            f"{RAIZ_REMOTA}/catalogos/perfis_usuario.json"
        ]

    def test_reenviar_pendencias_respeita_o_intervalo(self, espelho_github, github_falso, tmp_path):
        github_falso.falhas += [("PUT", 500), ("PUT", 500)]
        projeto_no_espelho(tmp_path)
        assert er.situacao().pendentes == 1

        # Acabou de tentar de novo: com intervalo longo não bate no GitHub outra vez.
        github_falso.falhas.append(("PUT", 500))
        assert arm.reenviar_pendencias(intervalo_s=0) == 1  # tentou e falhou
        pedidos = len(github_falso.requisicoes)
        assert arm.reenviar_pendencias(intervalo_s=3600) == 1
        assert len(github_falso.requisicoes) == pedidos  # não tentou

        assert arm.reenviar_pendencias(intervalo_s=0) == 0  # agora o GitHub responde
        assert er.situacao().pendentes == 0

    def test_sem_pendencias_nao_ha_o_que_reenviar(self, espelho_github, github_falso):
        assert arm.reenviar_pendencias(intervalo_s=0) == 0
        assert github_falso.requisicoes == []


# ---------------------------------------------------------------------------
# A tela
# ---------------------------------------------------------------------------


def _painel():
    from components.armazenamento_ui import painel_de_armazenamento

    painel_de_armazenamento()


def _lateral():
    import streamlit as st

    # Fora do app.py não há navegação multipágina para o st.page_link resolver: troca por um
    # texto com o mesmo rótulo, só para conferir que o link é oferecido.
    st.page_link = lambda pagina, label="", **_: st.markdown(f"link: {label}")
    from components.armazenamento_ui import situacao_na_lateral

    situacao_na_lateral()


def _preparar():
    from components.armazenamento_ui import preparar_armazenamento

    preparar_armazenamento()


def _aviso():
    from components.armazenamento_ui import aviso_de_armazenamento

    aviso_de_armazenamento()


def rodar(funcao) -> AppTest:
    teste = AppTest.from_function(funcao, default_timeout=60)
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def textos(elementos) -> str:
    return " ".join(str(e.value) for e in elementos)


class TestTela:
    def test_no_computador_do_usuario_a_tela_nao_acrescenta_avisos(self):
        for funcao in (_lateral, _aviso):
            teste = rodar(funcao)
            assert not teste.warning and not teste.error and not teste.sidebar.warning
        painel = rodar(_painel)
        assert not painel.warning and not painel.error and not painel.button

    def test_na_nuvem_sem_espelho_a_lateral_avisa_e_oferece_a_carteira(self, nuvem):
        teste = rodar(_lateral)
        avisos = textos(teste.sidebar.warning)
        assert "Versão web: dados temporários" in avisos
        assert "Baixe a carteira ao terminar" in avisos
        assert len(teste.sidebar.get("download_button")) == 1
        assert "link: Como guardar os projetos" in textos(teste.sidebar.markdown)

    def test_na_nuvem_sem_espelho_a_pagina_mostra_o_aviso_completo(self, nuvem):
        teste = rodar(_aviso)
        assert "apagado quando o aplicativo reinicia" in textos(teste.warning)

    def test_o_painel_explica_como_ligar_o_espelho_com_o_modelo_dos_segredos(self, nuvem):
        teste = rodar(_painel)
        assert "Versão web: dados temporários" in textos(teste.warning)
        codigo = textos(teste.code)
        assert er.VARIAVEL_REPOSITORIO in codigo and er.VARIAVEL_TOKEN in codigo
        passos = textos(teste.markdown)
        assert "repositório **privado**" in passos and "Contents: Read and write" in passos
        assert not teste.button  # sem espelho, nada para enviar nem testar

    def test_com_o_espelho_funcionando_a_lateral_so_confirma_em_uma_linha(
        self, nuvem, espelho_github
    ):
        teste = rodar(_lateral)
        assert not teste.sidebar.warning
        assert "Projetos sincronizados com o GitHub" in textos(teste.sidebar.caption)

    def test_o_painel_do_espelho_testa_a_conexao_e_envia_tudo(
        self, nuvem, espelho_github, github_falso, banco_isolado
    ):
        criar_projeto("Mezanino", codigo="PRJ-1")
        github_falso.arquivos.clear()  # "esqueceu" de enviar: o botão tem de levar tudo
        teste = rodar(_painel)
        assert "Projetos sincronizados com o GitHub" in textos(teste.success)

        teste.button(key="armazenamento_testar").click().run()
        assert "Conectado a dono/dados (privado)." in textos(teste.success)

        teste.button(key="armazenamento_enviar_tudo").click().run()
        assert not teste.exception
        assert len(github_falso.caminhos(f"{RAIZ_REMOTA}/projetos")) == 1
        assert "1 projeto(s) e 0 catálogo(s) enviados ao GitHub; 0 pendente(s)." in textos(
            teste.success
        )

    def test_teste_de_conexao_com_token_errado_mostra_a_causa(
        self, nuvem, espelho_github, github_falso
    ):
        github_falso.token = "outro-token"
        teste = rodar(_painel)
        teste.button(key="armazenamento_testar").click().run()
        assert "recusou o token" in textos(teste.error)

    def test_recarregar_do_github_traz_o_que_falta(
        self, nuvem, espelho_github, github_falso, banco_isolado, tmp_path
    ):
        projeto_no_espelho(tmp_path)
        teste = rodar(_painel)
        assert listar_projetos() == []
        teste.button(key="armazenamento_recarregar").click().run()
        assert [p["codigo"] for p in listar_projetos()] == ["PRJ-1"]
        assert "1 projeto(s) trazido(s) do GitHub." in textos(teste.success)

    def test_a_falha_do_espelho_aparece_em_vermelho_com_a_causa(
        self, nuvem, espelho_github, github_falso, tmp_path
    ):
        github_falso.falhas += [("PUT", 500), ("PUT", 500)]  # criação e revisão do projeto
        projeto_no_espelho(tmp_path)
        painel = rodar(_painel)
        assert "Sincronização com o GitHub com problema" in textos(painel.error)
        lateral = rodar(_lateral)
        assert "500" in textos(lateral.sidebar.warning)
        assert len(lateral.sidebar.get("download_button")) == 1

    def test_ao_abrir_o_aplicativo_o_que_o_disco_perdeu_volta_do_github(
        self, nuvem, espelho_github, github_falso, banco_isolado, tmp_path
    ):
        projeto_no_espelho(tmp_path, "Mezanino", "PRJ-1")
        projeto_no_espelho(tmp_path, "Escada", "PRJ-2")
        assert listar_projetos() == []

        teste = rodar(_preparar)
        assert {p["codigo"] for p in listar_projetos()} == {"PRJ-1", "PRJ-2"}
        assert "2 projeto(s) e 0 catálogo(s) carregado(s) do GitHub." in textos(teste.toast)

        again = rodar(_preparar)  # outra execução da página: não restaura nem avisa de novo
        assert not again.toast

    def test_os_segredos_do_streamlit_viram_a_configuracao_do_espelho(self, monkeypatch):
        er.redefinir()  # o conftest fixa "sem espelho"; aqui vale o que vier dos segredos
        teste = AppTest.from_function(_preparar, default_timeout=60)
        teste.secrets[er.VARIAVEL_REPOSITORIO] = "fologyia/dados"
        teste.secrets[er.VARIAVEL_TOKEN] = "segredo"
        # A restauração tentaria falar com o GitHub de verdade: aponta para uma porta fechada.
        teste.secrets[er.VARIAVEL_API] = "http://127.0.0.1:9"
        teste.run()
        import os

        try:
            assert os.environ[er.VARIAVEL_REPOSITORIO] == "fologyia/dados"
            assert os.environ[er.VARIAVEL_TOKEN] == "segredo"
            assert er.obter_espelho() is not None
            assert er.obter_espelho().configuracao.repositorio == "fologyia/dados"
        finally:
            for variavel in er.VARIAVEIS:
                monkeypatch.delenv(variavel, raising=False)
                os.environ.pop(variavel, None)

    def test_variavel_de_ambiente_ja_definida_ganha_dos_segredos(self, monkeypatch):
        er.redefinir()
        monkeypatch.setenv(er.VARIAVEL_REPOSITORIO, "ja/definido")
        monkeypatch.setenv(er.VARIAVEL_TOKEN, "do-ambiente")
        monkeypatch.setenv(er.VARIAVEL_API, "http://127.0.0.1:9")
        teste = AppTest.from_function(_preparar, default_timeout=60)
        teste.secrets[er.VARIAVEL_REPOSITORIO] = "do/segredo"
        teste.run()
        import os

        assert os.environ[er.VARIAVEL_REPOSITORIO] == "ja/definido"
