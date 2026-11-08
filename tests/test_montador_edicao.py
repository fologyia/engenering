"""Item 4 do Montador na página: o número no cartão, um Ctrl+Z só para tudo, e copiar e colar.

A prancheta não roda no AppTest. O gesto dela entra como entra no navegador: o callback roda com o
evento no estado da sessão, antes do script, e depois a página roda inteira.
"""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from streamlit.testing.v1 import AppTest

from components import montador_ui as ui
from core import montador_blocos as mb
from core import montador_modelos as mm

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SOLIDOS = mm.PARTE_SOLIDOS
FLUIDOS = mm.PARTE_FLUIDOS


def abrir(parte: mm.Parte) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(
        "app_pages/montador_formulas.py" if parte is SOLIDOS else "app_pages/montador_fluidos.py"
    )
    at.run()
    assert not at.exception
    return at


def _no_callback(at: AppTest, parte: mm.Parte, chamada, **evento) -> None:
    """Roda o callback como o Streamlit roda, e devolve à sessão o que ele trocou."""
    original = dict(at.session_state.filtered_state)
    estado = dict(original)
    estado[parte.k("prancheta")] = SimpleNamespace(**evento)
    with mock.patch.object(ui.st, "session_state", estado):
        chamada()
    for chave, valor in estado.items():
        if chave != parte.k("prancheta") and (
            chave not in original or original[chave] is not valor
        ):
            at.session_state[chave] = valor
    for chave in original:
        if chave not in estado:
            del at.session_state[chave]


def _comandos(at: AppTest, parte: mm.Parte, *itens: dict, repetir: tuple = ()) -> None:
    """Pedidos numerados, como a fila da prancheta manda. ``repetir`` volta a mandar os de antes."""
    n = at.session_state[parte.k("comandos")] if parte.k("comandos") in at.session_state else 0
    lista = [dict(x) for x in repetir]
    for item in itens:
        n += 1
        lista.append({**item, "n": n})
    _no_callback(at, parte, lambda: ui._ao_comandar(parte), comando={"lista": lista})
    at.run()
    assert not at.exception


def _editar(at: AppTest, parte: mm.Parte, grafo: dict, **extra) -> None:
    versao = at.session_state[parte.k("versao")] + 1
    evento = {"grafo": grafo, "versao": versao, "so_posicao": False, **extra}
    _no_callback(at, parte, lambda: ui._ao_editar(parte), edicao=evento)
    at.run()
    assert not at.exception


def _valores(at: AppTest, parte: mm.Parte) -> dict:
    return at.session_state[parte.k("valores")]


def _origens(at: AppTest, parte: mm.Parte) -> dict:
    return at.session_state[parte.k("origens")]


def _aviso(at: AppTest, parte: mm.Parte) -> str:
    return at.session_state[parte.k("aviso_historia")]["texto"]


def _desfazer(at: AppTest, parte: mm.Parte) -> None:
    v = at.session_state[parte.k("versao")]
    _comandos(at, parte, {"acao": "desfazer", "versao": v})


# ---------------------------------------------------------------------------
# O número no cartão
# ---------------------------------------------------------------------------


def test_numero_digitado_no_cartao_entra_na_conta_na_unidade_da_tela():
    at = abrir(SOLIDOS)
    antes = next(s.value for s in at.success)
    _comandos(
        at,
        SOLIDOS,
        {"acao": "valor", "chave": "S_y", "valor": 350.0, "unidade": "MPa"},
        {"acao": "valor", "chave": "M_x", "valor": 3.0, "unidade": "kN·m"},
    )
    assert _valores(at, SOLIDOS)["S_y"] == 350.0
    assert _valores(at, SOLIDOS)["M_x"] == 3e6  # kN·m na tela, N·mm na conta
    assert _origens(at, SOLIDOS)["M_x"] == "Digitado"
    assert next(s.value for s in at.success) != antes
    # O inspetor mostra o número novo: o campo foi refeito com a revisão.
    campo = next(n for n in at.number_input if n.label.startswith("S_y"))
    assert campo.value == 350.0


def test_cartao_nao_grava_com_unidade_velha_nem_na_letra_pedida():
    at = abrir(SOLIDOS)
    _comandos(
        at,
        SOLIDOS,
        {"acao": "valor", "chave": "S_y", "valor": 0.35, "unidade": "GPa"},
        {"acao": "valor", "chave": "h", "valor": 40.0, "unidade": "mm"},
        {"acao": "valor", "chave": "nao_existe", "valor": 1.0, "unidade": ""},
    )
    assert _valores(at, SOLIDOS)["S_y"] == 250.0
    assert _valores(at, SOLIDOS).get("h") is None


def test_campo_esvaziado_no_cartao_volta_a_ser_letra():
    at = abrir(SOLIDOS)
    _comandos(at, SOLIDOS, {"acao": "valor", "chave": "M_x", "valor": None, "unidade": "kN·m"})
    assert _valores(at, SOLIDOS)["M_x"] is None
    assert any("preencha M_x" in i.value for i in at.info)


def test_pedido_repetido_pela_fila_nao_e_feito_de_novo():
    at = abrir(SOLIDOS)
    primeiro = {"acao": "valor", "chave": "S_y", "valor": 300.0, "unidade": "MPa"}
    _comandos(at, SOLIDOS, primeiro)
    feito = {**primeiro, "n": at.session_state[SOLIDOS.k("comandos")]}
    _comandos(at, SOLIDOS, {"acao": "valor", "chave": "S_y", "valor": 400.0, "unidade": "MPa"})
    # A prancheta não viu a confirmação e manda o primeiro de novo, junto com um novo.
    _comandos(
        at, SOLIDOS, {"acao": "valor", "chave": "n", "valor": 2.0, "unidade": ""}, repetir=(feito,)
    )
    assert _valores(at, SOLIDOS)["S_y"] == 400.0
    assert _valores(at, SOLIDOS)["n"] == 2.0


def test_cartao_mostra_os_numeros_do_criterio_e_quem_se_muda():
    at = abrir(SOLIDOS)
    estado = at.session_state
    base = ui.mt.montar(ui.mt.grafo_de_dados(estado[SOLIDOS.k("grafo")]))
    u = ui.Unidades(SOLIDOS.sistema, tuple(estado[SOLIDOS.k("unidades")]))
    campos = ui._campos_do_cartao(base, estado[SOLIDOS.k("valores")], {}, "h", u)
    assert campos["M_x"]["v"] == 2.0 and campos["M_x"]["u"] == "kN·m"
    assert campos["h"]["alvo"] and not campos["b"]["alvo"]
    resposta = ui.mt.isolar(base, "h", estado[SOLIDOS.k("valores")])
    faces, _ = ui._faces(
        base.grafo, estado[SOLIDOS.k("grafo")], base, resposta, estado[SOLIDOS.k("valores")], "h", u
    )
    criterio = faces["n4"]  # von Mises
    assert criterio["a"].startswith("Utilização")  # o Word continua com o uso
    assert [c for _, c in criterio["p"]] == ["", "S_y", "n"]


# ---------------------------------------------------------------------------
# Um Ctrl+Z só, na ordem em que as coisas foram feitas
# ---------------------------------------------------------------------------


def _sem_cortante(grafo: dict) -> dict:
    grafo = copy.deepcopy(grafo)
    grafo["nos"] = [n for n in grafo["nos"] if n["id"] != "n3"]
    grafo["fios"] = [f for f in grafo["fios"] if "n3" not in (f["de"], f["para"])]
    grafo["fios"].append({"de": "n2", "saida": "saida", "para": "n4", "entrada": "entrada"})
    return grafo


def test_ctrl_z_desfaz_bloco_numero_e_lugar_na_ordem():
    at = abrir(SOLIDOS)
    original = copy.deepcopy(at.session_state[SOLIDOS.k("grafo")])
    _editar(at, SOLIDOS, _sem_cortante(original))  # 1: tira a cortante
    _comandos(at, SOLIDOS, {"acao": "valor", "chave": "S_y", "valor": 350.0, "unidade": "MPa"})
    movido = copy.deepcopy(at.session_state[SOLIDOS.k("grafo")])
    movido["nos"][0]["x"] += 60
    _editar(at, SOLIDOS, movido, so_posicao=True)  # 3: arrasta um bloco

    _desfazer(at, SOLIDOS)
    assert at.session_state[SOLIDOS.k("grafo")]["nos"][0]["x"] == original["nos"][0]["x"]
    assert _valores(at, SOLIDOS)["S_y"] == 350.0
    assert _aviso(at, SOLIDOS) == "Desfeito: os blocos voltaram ao lugar."

    _desfazer(at, SOLIDOS)
    assert _valores(at, SOLIDOS)["S_y"] == 250.0
    assert not any(n["id"] == "n3" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])
    assert _aviso(at, SOLIDOS) == "Desfeito: S_y voltou a 250 MPa."

    _desfazer(at, SOLIDOS)
    assert any(n["id"] == "n3" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])
    assert _aviso(at, SOLIDOS) == f"Desfeito: o bloco {mb.POR_CHAVE['cortante'].nome} voltou."

    v = at.session_state[SOLIDOS.k("versao")]
    _comandos(at, SOLIDOS, {"acao": "refazer", "versao": v})
    assert not any(n["id"] == "n3" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])
    assert _aviso(at, SOLIDOS).startswith("Refeito: o bloco")


def test_ctrl_z_desfaz_o_numero_digitado_no_inspetor():
    at = abrir(SOLIDOS)
    campo = next(n for n in at.number_input if n.label.startswith("S_y"))
    campo.set_value(400.0).run()
    assert _valores(at, SOLIDOS)["S_y"] == 400.0
    _desfazer(at, SOLIDOS)
    assert _valores(at, SOLIDOS)["S_y"] == 250.0
    assert next(n for n in at.number_input if n.label.startswith("S_y")).value == 250.0


def test_ctrl_z_traz_o_gesto_que_se_perdeu_antes_de_desfazer():
    """O desenho do gesto de logo antes vem junto do Ctrl+Z: é ele que se desfaz, e não o anterior."""
    at = abrir(SOLIDOS)
    _comandos(at, SOLIDOS, {"acao": "valor", "chave": "S_y", "valor": 350.0, "unidade": "MPa"})
    perdido = _sem_cortante(at.session_state[SOLIDOS.k("grafo")])
    v = at.session_state[SOLIDOS.k("versao")] + 1
    _comandos(at, SOLIDOS, {"acao": "desfazer", "versao": v, "grafo": perdido})
    assert any(n["id"] == "n3" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])
    assert _valores(at, SOLIDOS)["S_y"] == 350.0  # o número digitado antes continua


def test_arrumacao_automatica_e_desfazer_sem_passo_nao_quebram():
    at = abrir(SOLIDOS)
    passos = len(at.session_state[SOLIDOS.k("historico")]["passado"])
    arrumado = copy.deepcopy(at.session_state[SOLIDOS.k("grafo")])
    arrumado["nos"][0]["y"] += 200
    _editar(at, SOLIDOS, arrumado, so_posicao=True, automatico=True)
    assert len(at.session_state[SOLIDOS.k("historico")]["passado"]) == passos
    for _ in range(passos + 3):  # mais Ctrl+Z do que passos
        _desfazer(at, SOLIDOS)
    assert at.success


def test_ctrl_z_da_troca_de_modelo_diz_que_a_montagem_voltou():
    at = abrir(SOLIDOS)
    antes = copy.deepcopy(at.session_state[SOLIDOS.k("grafo")])
    at.selectbox(key=SOLIDOS.k("modelo")).set_value(mm.MODELOS[1].nome).run()
    assert at.session_state[SOLIDOS.k("grafo")] != antes
    _desfazer(at, SOLIDOS)
    assert [n["tipo"] for n in at.session_state[SOLIDOS.k("grafo")]["nos"]] == [
        n["tipo"] for n in antes["nos"]
    ]
    assert _aviso(at, SOLIDOS) == "Desfeito: a montagem voltou como estava."


def test_limpar_se_desfaz_com_ctrl_z():
    at = abrir(SOLIDOS)
    at.button(key=SOLIDOS.k("limpar")).click().run()
    assert not at.session_state[SOLIDOS.k("grafo")]["nos"]
    _desfazer(at, SOLIDOS)
    assert at.session_state[SOLIDOS.k("grafo")]["nos"]
    assert _valores(at, SOLIDOS)["S_y"] == 250.0


def test_agrupar_pela_fila_e_pelo_pedido_antigo():
    at = abrir(SOLIDOS)
    v = at.session_state[SOLIDOS.k("versao")]
    _comandos(at, SOLIDOS, {"acao": "agrupar", "ids": ["n2", "n3"], "caminho": [], "versao": v})
    assert any(n["tipo"] == "conjunto" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])
    _desfazer(at, SOLIDOS)
    assert not any(n["tipo"] == "conjunto" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])
    pedido = {"acao": "agrupar", "ids": ["n2", "n3"], "caminho": [], "versao": v + 5}
    _no_callback(at, SOLIDOS, lambda: ui._ao_comandar(SOLIDOS), comando=pedido)
    at.run()
    assert any(n["tipo"] == "conjunto" for n in at.session_state[SOLIDOS.k("grafo")]["nos"])


# ---------------------------------------------------------------------------
# Copiar e colar
# ---------------------------------------------------------------------------


def _colar_o_trecho(at: AppTest) -> str:
    """Como a prancheta cola: o trecho n6 entra na fila depois do n2, com a senha da colagem."""
    grafo = copy.deepcopy(at.session_state[FLUIDOS.k("grafo")])
    original = next(n for n in grafo["nos"] if n["id"] == "n2")
    grafo["nos"].append({**copy.deepcopy(original), "id": "n6", "y": original["y"] + 150})
    fio = next(f for f in grafo["fios"] if f["de"] == "n2")
    grafo["fios"].remove(fio)
    grafo["fios"] += [
        {"de": "n2", "saida": "saida", "para": "n6", "entrada": "entrada"},
        {"de": "n6", "saida": "saida", "para": fio["para"], "entrada": fio["entrada"]},
    ]
    senha = str(at.session_state[FLUIDOS.k("versao")] + 1)
    _editar(at, FLUIDOS, grafo, colados={senha: {"n6": "n2"}})
    return senha


def test_trecho_colado_nasce_com_os_numeros_marcados():
    at = abrir(FLUIDOS)
    senha = _colar_o_trecho(at)
    valores, origens = _valores(at, FLUIDOS), _origens(at, FLUIDOS)
    assert valores["D_2"] == valores["D"] and valores["L_2"] == valores["L"] == 100.0
    assert origens["D_2"] == "Copiado de D" and origens["L_2"] == "Copiado de L"
    # A rugosidade é a da tabela nos dois: a cópia fica com a procedência da tabela.
    assert valores["varepsilon_2"] == valores["varepsilon"]
    assert origens["varepsilon_2"].startswith("Tabela")
    assert senha in at.session_state[FLUIDOS.k("colagens")]
    assert any(m.value.startswith("**Q") for m in at.success)
    documento = ui.rg.documento(
        FLUIDOS.dominio, at.session_state[FLUIDOS.k("grafo")], valores, origens, "Q", None, ()
    )
    assert documento["origens"]["L_2"] == "Copiado de L"  # vai assim para o arquivo e o Word


def test_inspetor_avisa_da_copia_e_confirma():
    at = abrir(FLUIDOS)
    _colar_o_trecho(at)
    at.session_state[FLUIDOS.k("selecao")] = {"tipo": "no", "id": "n6"}
    at.run()
    assert any("copiados de D, L" in c.value for c in at.caption)
    at.button(key=FLUIDOS.k("conferir_copias")).click().run()
    assert _origens(at, FLUIDOS)["D_2"] == "Digitado"
    assert not any("copiados de" in c.value for c in at.caption)


def test_enter_no_numero_copiado_confirma_e_colagem_repetida_nao_apaga_o_que_mudou():
    at = abrir(FLUIDOS)
    senha = _colar_o_trecho(at)
    _comandos(
        at,
        FLUIDOS,
        {"acao": "valor", "chave": "L_2", "valor": 30.0, "unidade": "m"},
        {"acao": "valor", "chave": "D_2", "valor": 100.0, "unidade": "mm", "conferir": True},
    )
    assert _valores(at, FLUIDOS)["L_2"] == 30.0
    assert _origens(at, FLUIDOS)["D_2"] == "Digitado"
    # A prancheta manda a mesma colagem de novo, sem ter visto a senha voltar.
    _editar(at, FLUIDOS, at.session_state[FLUIDOS.k("grafo")], colados={senha: {"n6": "n2"}})
    assert _valores(at, FLUIDOS)["L_2"] == 30.0


def test_ctrl_z_da_conferencia_volta_a_marca_de_copia():
    at = abrir(FLUIDOS)
    _colar_o_trecho(at)
    _comandos(
        at,
        FLUIDOS,
        {"acao": "valor", "chave": "D_2", "valor": 100.0, "unidade": "mm", "conferir": True},
    )
    _desfazer(at, FLUIDOS)
    assert _origens(at, FLUIDOS)["D_2"] == "Copiado de D"
    assert _aviso(at, FLUIDOS) == "Desfeito: D2 voltou a ficar marcado como cópia."


def test_apagar_o_primeiro_trecho_mantem_os_numeros_do_segundo():
    at = abrir(FLUIDOS)
    _colar_o_trecho(at)
    _comandos(
        at,
        FLUIDOS,
        {"acao": "valor", "chave": "D_2", "valor": 50.0, "unidade": "mm"},
        {"acao": "valor", "chave": "L_2", "valor": 10.0, "unidade": "m"},
    )
    grafo = copy.deepcopy(at.session_state[FLUIDOS.k("grafo")])
    grafo["nos"] = [n for n in grafo["nos"] if n["id"] != "n2"]
    grafo["fios"] = [f for f in grafo["fios"] if "n2" not in (f["de"], f["para"])]
    grafo["fios"].append({"de": "n1", "saida": "saida", "para": "n6", "entrada": "entrada"})
    _editar(at, FLUIDOS, grafo)
    valores = _valores(at, FLUIDOS)
    assert valores["D"] == 0.05 and valores["L"] == 10.0  # os do trecho que ficou
    assert "D_2" not in valores and "L_2" not in valores
    _desfazer(at, FLUIDOS)
    valores = _valores(at, FLUIDOS)
    assert valores["D"] == 0.1 and valores["D_2"] == 0.05  # tudo volta como era
