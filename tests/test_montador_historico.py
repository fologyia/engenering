"""O histórico do Montador, o número que segue o bloco e a cópia que nasce com os números do original."""

from __future__ import annotations

import copy

from core import montador as mt
from core import montador_historico as mh
from core import montador_modelos as mm


def _linha_com_dois_trechos() -> dict:
    """Fluido → trecho n2 → trecho n6 → perdas → carga → resultado."""
    dados = mm.MODELOS_FLUIDOS[0].grafo()
    fio = next(f for f in dados["fios"] if f["de"] == "n2")
    dados["fios"].remove(fio)
    dados["nos"].append({"id": "n6", "tipo": "trecho", "opcoes": {}, "x": 0, "y": 0})
    dados["fios"] += [
        {"de": "n2", "saida": "saida", "para": "n6", "entrada": "entrada"},
        {"de": "n6", "saida": "saida", "para": fio["para"], "entrada": fio["entrada"]},
    ]
    return dados


def _sem_o_primeiro(dados: dict) -> dict:
    dados = copy.deepcopy(dados)
    dados["nos"] = [n for n in dados["nos"] if n["id"] != "n2"]
    dados["fios"] = [f for f in dados["fios"] if "n2" not in (f["de"], f["para"])]
    dados["fios"].append({"de": "n1", "saida": "saida", "para": "n6", "entrada": "entrada"})
    return dados


def _letras(dados: dict) -> dict:
    return mh.letras_por_no(mt.montar(mt.grafo_de_dados(dados)))


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------


def test_desfaz_e_refaz_na_ordem():
    h = mh.novo({"v": 0})
    for v in (1, 2, 3):
        assert mh.registrar(h, {"v": v})
    assert not mh.registrar(h, {"v": 3})  # igual: não vira passo
    assert mh.desfazer(h) == {"v": 2}
    assert mh.desfazer(h) == {"v": 1}
    assert mh.refazer(h) == {"v": 2}
    mh.registrar(h, {"v": 9})  # mudança nova apaga o que dava para refazer
    assert mh.refazer(h) is None
    assert [x["v"] for x in h["passado"]] == [0, 1, 2]


def test_historico_tem_limite_e_nao_passa_do_comeco():
    h = mh.novo({"v": 0})
    for v in range(1, mh.LIMITE + 20):
        mh.registrar(h, {"v": v})
    assert len(h["passado"]) == mh.LIMITE
    while mh.desfazer(h) is not None:
        pass
    assert h["atual"] == {"v": 19}


def test_arrumacao_automatica_junta_com_o_passo_de_antes():
    h = mh.novo({"v": 0})
    mh.registrar(h, {"v": 1})
    mh.registrar(h, {"v": 1, "x": 30}, juntar=True)
    assert h["atual"] == {"v": 1, "x": 30}
    assert mh.desfazer(h) == {"v": 0}


def test_mudanca_separa_bloco_fio_numero_e_lugar():
    dados = mm.MODELOS[0].grafo()
    de = {"grafo": dados, "valores": {"S_y": 250.0}, "origens": {}, "alvo": "h", "adotado": None}
    para = copy.deepcopy(de)
    para["valores"]["S_y"] = 350.0
    m = mh.mudanca(de, para)
    assert m.valores == ("S_y",) and not m.fios and not m.lugares and not m.entraram
    para = copy.deepcopy(de)
    para["grafo"]["nos"][0]["x"] += 40
    assert mh.mudanca(de, para).lugares
    para = copy.deepcopy(de)
    para["grafo"]["nos"] = [n for n in para["grafo"]["nos"] if n["id"] != "n3"]
    assert mh.mudanca(de, para).sairam == ("n3",)
    para = copy.deepcopy(de)
    para["origens"] = {"S_y": "Digitado"}
    assert mh.mudanca(de, para).origens == ("S_y",)
    assert not mh.mudanca(de, para).tipos
    para = copy.deepcopy(de)
    para["grafo"]["nos"][1]["tipo"] = "torcao"  # o mesmo id com outro bloco, como num modelo
    assert mh.mudanca(de, para).tipos


# ---------------------------------------------------------------------------
# O número segue o bloco
# ---------------------------------------------------------------------------


def test_motor_diz_a_posicao_de_cada_bloco_numerado():
    dados = _linha_com_dois_trechos()
    indices = dict(mt.montar(mt.grafo_de_dados(dados)).indices)
    assert indices["n2"] == 1 and indices["n6"] == 2
    assert "n1" not in indices  # o fluido não numera letra


def test_apagar_o_primeiro_trecho_leva_os_numeros_do_segundo_junto():
    dados = _linha_com_dois_trechos()
    antes = _letras(dados)
    assert antes["n6"][2][:3] == ["D_2", "L_2", "varepsilon_2"]
    depois = _letras(_sem_o_primeiro(dados))
    assert depois["n6"][2][:3] == ["D", "L", "varepsilon"]
    trocas = mh.renomes(antes, depois)
    assert trocas == {"D_2": "D", "L_2": "L", "varepsilon_2": "varepsilon"}
    valores = {"D": 0.1, "L": 100.0, "D_2": 0.05, "L_2": 10.0, "varepsilon_2": 1e-4}
    origens = {"D": "Exemplo do modelo", "D_2": "Digitado", "L_2": "Digitado"}
    mh.aplicar_renomes(trocas, depois, valores, origens)
    assert valores["D"] == 0.05 and valores["L"] == 10.0 and valores["varepsilon"] == 1e-4
    assert "D_2" not in valores and "L_2" not in valores
    assert origens["D"] == "Digitado" and "D_2" not in origens


def test_troca_de_lugar_entre_dois_trechos_nao_apaga_nenhum():
    antes = {"a": ["trecho", 1, ["L"]], "b": ["trecho", 2, ["L_2"]]}
    depois = {"a": ["trecho", 2, ["L_2"]], "b": ["trecho", 1, ["L"]]}
    valores = {"L": 1.0, "L_2": 2.0}
    mh.aplicar_renomes(mh.renomes(antes, depois), depois, valores)
    assert valores == {"L": 2.0, "L_2": 1.0}


def test_letra_de_outro_bloco_com_o_mesmo_nome_nao_muda():
    antes = {
        "t1": ["trecho", 1, ["L"]],
        "t2": ["trecho", 2, ["L_2"]],
        "viga": ["viga", 1, ["L"]],  # outro tipo, a mesma letra
    }
    depois = {"t2": ["trecho", 1, ["L"]], "viga": ["viga", 1, ["L"]]}
    assert mh.renomes(antes, depois) == {}


def test_agrupar_nao_perde_o_rastro_do_bloco():
    antes = {"n2": ["trecho", 2, ["L_2"]], "n9": ["trecho", 1, ["L"]]}
    depois = {"c1/n2": ["trecho", 1, ["L"]]}
    assert mh.renomes(antes, depois) == {"L_2": "L"}


# ---------------------------------------------------------------------------
# Cópia
# ---------------------------------------------------------------------------


def test_copia_acha_a_letra_pelo_nome_sem_numero():
    base = mt.montar(mt.grafo_de_dados(_linha_com_dois_trechos()))
    pares = mh.letras_da_copia(base, {"n6": "n2"})
    assert ("D_2", "D") in pares and ("L_2", "L") in pares
    assert all(copia != fonte for copia, fonte in pares)


def test_copia_dentro_de_conjunto_copiado():
    nos = (mt.No("c1/n2", "flexao"), mt.No("c9/n2", "flexao"), mt.No("c9/n1", "circular"))
    base = mt.Montagem(
        (),
        (),
        frozenset(),
        (),
        (),
        (),
        (),
        False,
        grafo=mt.Grafo(nos, ()),
        letras_do_bloco=(("c1/n2", ("M_x",)), ("c9/n2", ("M_x_2",)), ("c9/n1", ("d",))),
        indices=(("c1/n2", 1), ("c9/n2", 2)),
    )
    # O d da seção não numera: é a mesma letra nos dois, e não há o que copiar.
    assert mh.letras_da_copia(base, {"c9": "c1"}) == [("M_x_2", "M_x")]


def test_copiar_valores_marca_a_procedencia_e_deixa_o_padrao_em_paz():
    valores = {"D": 0.08, "L": 30.0, "varepsilon": 4.5e-5, "K": None}
    origens = {"D": "Digitado", "L": "Exemplo do modelo", "varepsilon": "Tabela: Aço comercial"}
    padroes = {"varepsilon": 4.5e-5}
    pares = [("D_2", "D"), ("L_2", "L"), ("varepsilon_2", "varepsilon"), ("K_2", "K")]
    copiadas = mh.copiar_valores(
        pares,
        valores,
        origens,
        padroes,
        {"varepsilon_2": 4.5e-5},
        lambda c: {"varepsilon_2": 4.5e-5}.get(c),
        lambda c: {"varepsilon": "ε"}.get(c, c),
    )
    assert copiadas == ["D_2", "L_2", "K_2"]
    assert valores["D_2"] == 0.08 and valores["L_2"] == 30.0
    assert origens["D_2"] == "Copiado de D" and origens["L_2"] == "Copiado de L"
    assert "varepsilon_2" not in valores  # a tela põe o padrão da tabela, com a procedência dela
    assert padroes["varepsilon_2"] == 4.5e-5
    assert valores["K_2"] is None  # campo vazio no original fica vazio na cópia
    assert mh.copiada(origens["D_2"]) == "D"
    assert mh.copiada("Digitado") == ""
