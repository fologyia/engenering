"""Montador: a biblioteca esconde o que não cabe na seção, no tipo de peça ou no fluido."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import montador_blocos as mb
from core import montador_conjuntos as mc
from core import montador_modelos as mm
from core import montador_uso as mu
from core.montador import CONJUNTO

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CATALOGO = mb.catalogo_para_tela(mb.SOLIDOS)
CHAVES = [item["chave"] for item in CATALOGO]
SECOES = [b.chave for b in mb.POR_CHAVE.values() if b.grupo == mb.GRUPO_SECAO]
PECAS_DO_EIXO = [b.chave for b in mb.POR_CHAVE.values() if b.grupo == mb.GRUPO_PECAS]
#: Blocos que servem em qualquer peça: nunca podem sumir por causa da seção.
GERAIS = (
    "flexao",
    "flexao_y",
    "normal",
    "cortante",
    "cortante_x",
    "torcao",
    "concentracao",
    "material",
    "von_mises",
    "tresca",
    "rankine",
    "goodman",
    "limite_fadiga",
    "flecha",
    "giro",
    "biapoiada_central",
    "balanco_ponta",
    mb.RESULTADO,
    mb.FORMULA,
    mb.REFERENCIA,
)


def _dados(*itens) -> dict:
    nos = []
    for i, item in enumerate(itens):
        tipo, opcoes = item if isinstance(item, tuple) else (item, {})
        nos.append({"id": f"n{i}", "tipo": tipo, "opcoes": opcoes, "x": 0, "y": 0})
    return {"nos": nos, "fios": []}


def _fora(*itens) -> dict[str, str]:
    return mu.escondidos(_dados(*itens), CATALOGO)


def test_toda_linha_da_tabela_e_um_bloco_que_existe():
    assert set(mu.USOS) <= set(mb.POR_CHAVE)
    assert set(SECOES) <= {c for c, u in mu.USOS.items() if u.forma}
    assert set(PECAS_DO_EIXO) <= {c for c, u in mu.USOS.items() if u.familia == mu.EIXO}


def test_montagem_vazia_mostra_tudo():
    assert mu.escondidos({"nos": [], "fios": []}, CATALOGO) == {}
    assert mu.escondidos({}, CATALOGO) == {}


def test_perfil_i_com_euler_esconde_pressao_e_pecas_do_eixo():
    """O exemplo do pedido: perfil I e flambagem de Euler."""
    fora = _fora("perfil_i", "flambagem")
    assert "pressao_interna" in fora
    assert "tubo circular" in fora["pressao_interna"]
    for chave in (*PECAS_DO_EIXO, "engrenagem", "polia", "engrenagem_conica", "potencia"):
        assert chave in fora, chave
        assert "Perfil I" in fora[chave]
    for chave in (*GERAIS, *SECOES):
        assert chave not in fora, chave


def test_secao_redonda_esconde_so_a_pressao():
    assert set(_fora("circular", "flexao", "torcao")) == {"pressao_interna"}


def test_euler_numa_barra_redonda_esconde_as_pecas_do_eixo():
    fora = _fora("circular", "flambagem")
    assert "chaveta" in fora and "coluna comprimida" in fora["chaveta"]
    assert "rolamento" in fora and "engrenagem" in fora
    assert "entalhe" not in fora  # um pino com ressalto também flamba
    assert not set(SECOES) & set(fora)


def test_peca_de_eixo_esconde_secao_que_nao_e_redonda_e_a_coluna():
    fora = _fora("engrenagem")
    assert {"retangular", "perfil_i", "desenhada"} <= set(fora)
    assert "circular" not in fora and "tubo_parede" not in fora
    assert "flambagem" in fora and "pressao_interna" in fora
    assert "Engrenagem" in fora["perfil_i"]


def test_tubo_com_pressao_aceita_flambagem():
    """A camisa de um cilindro hidráulico tem pressão por dentro e flamba."""
    fora = _fora("tubo_parede", "pressao_interna")
    assert "flambagem" not in fora
    assert {"circular", "retangular", "perfil_i", "desenhada"} <= set(fora)
    assert "tubo_relacao" not in fora
    assert "engrenagem" in fora and "chaveta" in fora


def test_duas_secoes_valem_as_duas():
    """A viga em perfil I e o pino redondo que a segura cabem na mesma montagem."""
    fora = _fora("perfil_i", "circular")
    assert set(fora) == {"pressao_interna"}
    assert "as seções da montagem são Circular maciça e Perfil I" in fora["pressao_interna"]


def test_fadiga_com_eixo_girando_vira_peca_de_eixo():
    assert "perfil_i" not in _fora("circular", "goodman")
    fora = _fora("circular", ("goodman", {"esforcos": mb.EIXO_GIRANDO}))
    assert "perfil_i" in fora and "eixo girando" in fora["perfil_i"]
    assert "flambagem" in fora


def test_bloco_dentro_de_um_conjunto_conta():
    dados = mc.agrupar(_dados("perfil_i", "flexao", "von_mises"), ["n0", "n1"], "Viga")
    assert any(no["tipo"] == CONJUNTO for no in dados["nos"])
    fora = mu.escondidos(dados, CATALOGO)
    assert "chaveta" in fora and "pressao_interna" in fora


def test_conjunto_salvo_some_quando_um_bloco_dele_nao_cabe():
    com_pressao = {"chave": "conjunto:Tubo", "conjunto": {"grafo": _dados("pressao_interna")}}
    so_flexao = {"chave": "conjunto:Fila", "conjunto": {"grafo": _dados("flexao", "cortante")}}
    fora = mu.escondidos(_dados("perfil_i"), [com_pressao, so_flexao])
    assert set(fora) == {"conjunto:Tubo"}


def test_bloco_desconhecido_e_no_quebrado_nao_atrapalham():
    dados = {"nos": [{"tipo": "nao_existe"}, "lixo", {"tipo": "perfil_i", "opcoes": "x"}]}
    assert "pressao_interna" in mu.escondidos(dados, CATALOGO)
    assert mu.escondidos(dados, [{"chave": "nao_existe"}]) == {}


def test_blocos_escondidos_por_chave():
    assert mu.blocos_escondidos(_dados("perfil_i"), ["flexao", "pressao_interna"]) == {
        "pressao_interna": _fora("perfil_i")["pressao_interna"]
    }


_DAS_CORRENTES = (*mm.MODELOS_FLUIDOS, *mm.MODELOS_TERMICOS, *mm.MODELOS_DE_PROCESSOS)


@pytest.mark.parametrize("modelo", _DAS_CORRENTES, ids=lambda m: m.nome)
def test_modelos_de_fluidos_e_termica_nao_tem_bloco_escondido(modelo):
    """Os modelos são montagens certas: nenhum bloco deles fica fora pelo fluido da montagem."""
    dados = modelo.grafo()
    tipos = [no["tipo"] for no in dados["nos"]]
    assert mu.blocos_escondidos(dados, tipos) == {}


def test_gas_esconde_a_bomba_e_liquido_esconde_o_gas_no_tubo():
    catalogo = mb.catalogo_para_tela(mb.FLUIDOS)
    gas = mm.PARTE_FLUIDOS.por_nome["Gás natural: diâmetro do tubo"].grafo()
    fora = mu.escondidos(gas, catalogo)
    assert {"npsh", "potencia_bomba", "valvula_controle", "golpe"} <= set(fora)
    assert "gas_no_tubo" not in fora and "medidor" not in fora
    agua = mm.PARTE_FLUIDOS.por_nome["Potência da bomba"].grafo()
    assert set(mu.escondidos(agua, catalogo)) == {"gas_no_tubo"}


def test_termico_pelo_fluido_do_estado():
    catalogo = mb.catalogo_para_tela(mb.TERMICO)
    ar = mm.PARTE_TERMICA.por_nome["Compressor de ar: pressão máxima"].grafo()
    fora = mu.escondidos(ar, catalogo)
    assert {"bomba_termica", "titulo_minimo", "cop"} <= set(fora)
    assert "compressor" not in fora and "turbina" not in fora
    rankine = mm.PARTE_TERMICA.por_nome["Ciclo Rankine simples"].grafo()
    assert mu.escondidos(rankine, catalogo) == {}
    # Óleo e água no trocador: basta um fluido servir.
    trocador = mm.PARTE_TERMICA.por_nome["Trocador: tamanho para resfriar óleo"].grafo()
    assert mu.escondidos(trocador, catalogo) == {}


def test_fluido_informado_nao_esconde_nada():
    catalogo = mb.catalogo_para_tela(mb.FLUIDOS)
    dados = {
        "nos": [{"id": "n1", "tipo": "fluido", "opcoes": {"fluido": "Informar as propriedades"}}]
    }
    assert mu.escondidos(dados, catalogo) == {}


def test_motivo_do_fluido_em_frase_inteira():
    gas = mm.PARTE_FLUIDOS.por_nome["Gás natural: diâmetro do tubo"].grafo()
    for motivo in mu.escondidos(gas, mb.catalogo_para_tela(mb.FLUIDOS)).values():
        assert motivo[0].isupper() and motivo.endswith("."), motivo


@pytest.mark.parametrize("modelo", mm.MODELOS, ids=lambda m: m.nome)
def test_nenhum_modelo_pronto_tem_bloco_que_a_regra_esconderia(modelo):
    """Os modelos são montagens certas: nenhum bloco deles pode estar fora do uso do resto."""
    dados = modelo.grafo()
    for no in dados["nos"]:
        resto = {"nos": [n for n in dados["nos"] if n is not no]}
        if no["tipo"] == CONJUNTO:
            item = {"chave": "conjunto", "conjunto": {"grafo": no["grafo"]}}
        else:
            item = {"chave": no["tipo"]}
        assert mu.escondidos(resto, [item]) == {}, no["tipo"]


@pytest.mark.parametrize(
    "montagem",
    [
        ("perfil_i", "flambagem"),
        ("engrenagem",),
        ("tubo_parede", "pressao_interna"),
        ("circular", ("goodman", {"esforcos": mb.EIXO_GIRANDO})),
    ],
)
def test_motivo_em_frase_inteira(montagem):
    proibidas = ("bloqueio", "Snapshot", "Apêndice", "Não informado", "sem valor normativo")
    for motivo in _fora(*montagem).values():
        assert motivo[0].isupper() and motivo.endswith("."), motivo
        assert not any(p in motivo for p in proibidas)


def test_inspetor_da_ligacao_deixa_de_fora_o_que_nao_serve():
    """O modelo que abre a página é retangular: a pressão interna cabe no fio, mas não serve."""
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    at.session_state["mf_selecao"] = {
        "tipo": "fio",
        "caminho": [],
        "de": "n3",
        "saida": "saida",
        "para": "n4",
        "entrada": "entrada",
    }
    at.run()
    assert not at.exception
    opcoes = at.selectbox(key="mf_inserir_bloco").options
    nomes = [mb.POR_CHAVE[c].nome for c in ("concentracao", "torcao")]
    assert all(nome in opcoes for nome in nomes)
    assert mb.POR_CHAVE["pressao_interna"].nome not in opcoes
    assert any("fica de fora" in c.value for c in at.caption)
