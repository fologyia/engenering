"""Circuito fechado: desenhe o circuito (tubos, bomba, fonte de calor, dry cooler, chiller, válvula,
filtro, tanque e o vaso de expansão), com ramais em paralelo, e veja a hidráulica, as temperaturas
em regime e o circuito no tempo, em animação.

O desenho mora em ``st.session_state`` e três lugares o mudam: a prancheta, o painel do item
selecionado e as tabelas, todos por callback, antes de o script rodar. ``circ_versao`` conta as
mudanças: a prancheta ignora um desenho mais velho que o dela.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.animacao_ui import tocador
from components.circuito_help import AJUDA
from components.prancheta_circuito_ui import prancheta_do_circuito
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import circuito as ci
from core import circuito_cenas as cc
from core import circuito_termico as cte
from core import montador_fluidos as fl
from core.animacao import tempo_em_texto, unidade_de_tempo

ICONE = ":material/autorenew:"
configurar_pagina("Circuito fechado", ICONE)
cabecalho_pagina(
    "Circuito fechado",
    "Desenhe o circuito de resfriamento (ou de aquecimento): tubos, bomba, a fonte de calor, dry "
    "cooler, chiller, válvulas, filtro, tanque e o vaso de expansão, com ramais em paralelo. A "
    "página dá a vazão de cada ramal, a pressão de cada ponto, as temperaturas e o circuito no "
    "tempo, da partida a frio até estabilizar.",
    categoria="Mecânica",
    icone=ICONE,
    modulo_id=cc.MODULO_ID,
)

DADOS = "circ_dados"
VERSAO = "circ_versao"
AJUSTE = "circ_ajuste"
SELECAO = "circ_selecao"
REVISAO = "circ_tabela_rev"
CHAVE_PRANCHETA = "circ_prancheta"
MATERIAIS = list(fl.RUGOSIDADES)
CONTROLES = {
    "Sempre ligado": ci.SEMPRE,
    "Liga e desliga": ci.LIGA_DESLIGA,
    "Proporcional": ci.PROPORCIONAL,
}
_N = ci._n
estado = st.session_state

#: Campos do painel por tipo: (campo, rótulo, formato ou o tipo do campo).
CAMPOS: dict[str, list[tuple[str, str, str]]] = {
    ci.TUBO: [
        ("diametro_mm", "Diâmetro interno (mm)", "%.1f"),
        ("material", "Material", "material"),
        ("comprimento", "Comprimento real (m)", "comprimento"),
        ("k_local", "ΣK das peças", "%.2f"),
        ("perde_calor", "Perde calor para o ar", "liga"),
        ("isolamento_mm", "Isolamento (mm)", "%.1f"),
        ("k_isolamento", "k do isolamento (W/(m·K))", "%.4f"),
        ("h_externo", "h de fora (W/(m²·K))", "%.1f"),
    ],
    ci.BOMBA: [
        ("h0_m", "Altura com vazão zero (m)", "%.2f"),
        ("qmax_m3h", "Vazão com altura zero (m³/h)", "%.2f"),
        ("rendimento", "Rendimento (0 a 1)", "%.2f"),
        ("npsh_requerido_m", "NPSH pedido (m)", "%.2f"),
        ("ligada", "Ligada", "liga"),
    ],
    ci.FONTE: [
        ("potencia_kW", "Potência (kW)", "%.2f"),
        ("t_maxima", "Temperatura máxima de saída (°C)", "%.1f"),
        ("massa_kg", "Massa do equipamento (kg)", "%.1f"),
        ("calor_especifico_massa", "c da massa (J/(kg·K))", "%.0f"),
        ("volume_L", "Fluido dentro (L)", "%.1f"),
        ("dp_kPa", "Perda de carga (kPa)", "%.1f"),
        ("q_nominal_m3h", "Na vazão de (m³/h)", "%.2f"),
    ],
    ci.DRY_COOLER: [
        ("q_catalogo_kW", "Capacidade do catálogo (kW)", "%.2f"),
        ("t_entrada_catalogo", "Líquido entrando, catálogo (°C)", "%.1f"),
        ("t_ar_catalogo", "Ar entrando, catálogo (°C)", "%.1f"),
        ("vazao_liquido_catalogo_m3h", "Vazão de líquido, catálogo (m³/h)", "%.2f"),
        ("vazao_ar_catalogo_m3h", "Vazão de ar, catálogo (m³/h)", "%.0f"),
        ("potencia_ventilador_kW", "Ventiladores (kW)", "%.2f"),
        ("controle", "Controle do ventilador", "controle"),
        ("t_ajuste", "Saída ajustada (°C)", "%.1f"),
        ("volume_L", "Fluido dentro (L)", "%.1f"),
        ("dp_kPa", "Perda de carga (kPa)", "%.1f"),
        ("q_nominal_m3h", "Na vazão de (m³/h)", "%.2f"),
    ],
    ci.CHILLER: [
        ("capacidade_kW", "Capacidade (kW)", "%.2f"),
        ("t_ajuste", "Saída ajustada (°C)", "%.1f"),
        ("cop", "COP", "%.2f"),
        ("volume_L", "Fluido dentro (L)", "%.1f"),
        ("dp_kPa", "Perda de carga (kPa)", "%.1f"),
        ("q_nominal_m3h", "Na vazão de (m³/h)", "%.2f"),
    ],
    ci.VALVULA: [("k_local", "K da válvula", "%.2f"), ("diametro_mm", "Diâmetro (mm)", "%.1f")],
    ci.FILTRO: [
        ("dp_kPa", "Perda de carga (kPa)", "%.1f"),
        ("q_nominal_m3h", "Na vazão de (m³/h)", "%.2f"),
        ("volume_L", "Fluido dentro (L)", "%.1f"),
    ],
    ci.TANQUE: [
        ("volume_L", "Volume (L)", "%.0f"),
        ("ua_W_K", "UA para o ar (W/K)", "%.2f"),
        ("diametro_mm", "Diâmetro da ligação (mm)", "%.1f"),
    ],
}
CAMPOS_DO_VASO = [
    ("vaso_volume_L", "Volume do vaso (L)", "%.1f"),
    ("vaso_precarga_bar", "Pré-carga (bar)", "%.2f"),
    ("vaso_enchimento_bar", "Enchimento a frio (bar)", "%.2f"),
    ("vaso_maxima_bar", "Pressão máxima (bar)", "%.2f"),
]
_PADROES = ci.Elemento("", "", ci.TUBO, "", "")


def _trocar(dados: Mapping[str, Any], *, versao: int | None = None, ajustar: bool = False) -> None:
    estado[DADOS] = {
        "nos": [dict(n) for n in dados.get("nos") or ()],
        "trechos": [dict(t) for t in dados.get("trechos") or ()],
    }
    estado[VERSAO] = estado.get(VERSAO, 0) + 1 if versao is None else versao
    estado[REVISAO] = estado.get(REVISAO, 0) + 1
    if ajustar:
        estado[AJUSTE] = estado.get(AJUSTE, 0) + 1


if not isinstance(estado.get(DADOS), dict):
    _trocar(ci.exemplo_desenhado(), versao=0, ajustar=True)


def _ao_desenhar() -> None:
    evento = getattr(estado.get(CHAVE_PRANCHETA), "edicao", None)
    if not evento:
        return
    dados = evento.get("dados") or {}
    if not isinstance(dados.get("nos"), list) or not isinstance(dados.get("trechos"), list):
        return
    _trocar(dados, versao=int(evento.get("versao", 0)))


def _ao_selecionar() -> None:
    selecao = getattr(estado.get(CHAVE_PRANCHETA), "selecao", None)
    estado[SELECAO] = dict(selecao) if isinstance(selecao, Mapping) else None


def _ao_mudar_campo(lista: str, id_: str, campo: str, chave: str) -> None:
    dados = {k: [dict(x) for x in v] for k, v in estado[DADOS].items()}
    for item in dados[lista]:
        if item.get("id") == id_:
            valor = estado.get(chave)
            if campo == "controle":
                valor = CONTROLES.get(str(valor), ci.SEMPRE)
            item[campo] = valor
    _trocar(dados)


def _voltar_ao_exemplo() -> None:
    estado[SELECAO] = None
    _trocar(ci.exemplo_desenhado(), ajustar=True)


def _limpar() -> None:
    estado[SELECAO] = None
    _trocar({"nos": [], "trechos": []}, ajustar=True)


def _valor_padrao(item: Mapping[str, Any], campo: str) -> Any:
    if item.get(campo) is not None:
        return item[campo]
    return getattr(_PADROES, campo, None)


def _campo(
    lista: str, item: Mapping[str, Any], campo: str, rotulo: str, formato: str, versao: int
) -> None:
    chave = f"circ_sel_{item['id']}_{versao}_{campo}"
    opcoes = {"key": chave, "on_change": _ao_mudar_campo, "args": (lista, item["id"], campo, chave)}
    ajuda = AJUDA.get(f"c_{campo}", AJUDA["c_nome"])
    if formato == "liga":
        st.toggle(rotulo, value=bool(_valor_padrao(item, campo)), help=ajuda, **opcoes)
    elif formato == "material":
        atual = str(item.get("material") or MATERIAIS[0])
        st.selectbox(
            rotulo,
            MATERIAIS,
            index=MATERIAIS.index(atual) if atual in MATERIAIS else 0,
            help=ajuda,
            **opcoes,
        )
    elif formato == "controle":
        nomes = list(CONTROLES)
        atual = next((k for k, v in CONTROLES.items() if v == item.get("controle")), nomes[0])
        st.selectbox(rotulo, nomes, index=nomes.index(atual), help=ajuda, **opcoes)
    elif formato == "comprimento":
        desenhado = ci.comprimento_desenhado(estado[DADOS], item)
        real = item.get("comprimento")
        st.number_input(
            rotulo, value=None if real in (None, "") else float(real), min_value=0.0, step=1.0, format="%.2f",
            placeholder=f"{desenhado:.2f} pelo desenho".replace(".", ","), help=ajuda, **opcoes,
        )  # fmt: skip
    else:
        st.number_input(
            rotulo,
            value=float(_valor_padrao(item, campo) or 0.0),
            format=formato,
            help=ajuda,
            **opcoes,
        )


# ============================================================ condições
with st.container(border=True), secao_protegida("Fluido e condições"):
    st.subheader("Fluido e condições de projeto", help=AJUDA["sec_condicoes"])
    colunas = st.columns(5)
    fluido = colunas[0].selectbox(
        "Fluido", list(ci.FLUIDOS), key="circ_fluido", persist_state="session", help=AJUDA["fluido"]
    )
    t_ar = colunas[1].number_input(
        "Ar de projeto (°C)",
        value=30.0,
        step=1.0,
        key="circ_t_ar",
        persist_state="session",
        help=AJUDA["t_ar"],
    )
    t_inicial = colunas[2].number_input(
        "Circuito frio (°C)",
        value=25.0,
        step=1.0,
        key="circ_t0",
        persist_state="session",
        help=AJUDA["t_inicial"],
    )
    p_min = colunas[3].number_input(
        "Pressão mínima (bar)",
        value=0.0,
        step=0.1,
        key="circ_pmin",
        persist_state="session",
        help=AJUDA["p_min"],
    )
    v_max = colunas[4].number_input(
        "Velocidade máxima (m/s)",
        min_value=0.1,
        value=3.0,
        step=0.1,
        key="circ_vmax",
        persist_state="session",
        help=AJUDA["v_max"],
    )

dados = estado[DADOS]
circuito = ci.circuito_do_desenho(dados, fl.RUGOSIDADES, str(fluido))
erros = ci.problemas(circuito)

# ============================================================ tempo (antes da conta, que usa os perfis)
with st.container(border=True), secao_protegida("Ao longo do tempo"):
    st.subheader("Da partida ao regime, e ao longo do dia", help=AJUDA["sec_tempo"])
    colunas = st.columns([1.2, 1, 1.6])
    modo = colunas[0].radio(
        "Duração", ["Automático", "Informar (h)"], key="circ_dur_modo", help=AJUDA["duracao_modo"]
    )
    duracao = None
    if modo != "Automático":
        duracao = 3600.0 * float(
            colunas[1].number_input(
                "Horas", min_value=0.01, value=2.0, step=0.5, key="circ_dur", help=AJUDA["duracao"]
            )
        )
    dia = colunas[2].toggle(
        "Variar o ar e a carga ao longo do dia", key="circ_dia", help=AJUDA["dia"]
    )
    perfil_ar: tuple[float, ...] = ()
    perfil_carga: tuple[float, ...] = ()
    if dia:
        base = pd.DataFrame(
            {
                "Hora": [f"{h:02d}h" for h in range(24)],
                "Ar (°C)": [float(t_ar)] * 24,
                "Carga": [1.0] * 24,
            }
        )
        tabela = st.data_editor(
            base, key="circ_perfil", hide_index=True, num_rows="fixed", width="stretch", height=240, disabled=["Hora"],
            column_config={
                "Hora": st.column_config.TextColumn(help=AJUDA["perfil"]),
                "Ar (°C)": st.column_config.NumberColumn(format="%.1f", help=AJUDA["perfil"]),
                "Carga": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help=AJUDA["perfil"]),
            },
        )  # fmt: skip
        perfil_ar = tuple(float(v) for v in tabela["Ar (°C)"])
        perfil_carga = tuple(float(v) for v in tabela["Carga"])

condicoes = cte.Condicoes(
    t_ar=float(t_ar), t_inicial=float(t_inicial), perfil_ar=perfil_ar, perfil_carga=perfil_carga,
    pressao_minima_bar=float(p_min), velocidade_maxima=float(v_max),
)  # fmt: skip


@st.cache_data(show_spinner=False, max_entries=4)
def _calcular(c: ci.Circuito, cond: cte.Condicoes, duracao_: float | None) -> cc.Resultado:
    return cc.calcular(c, cond, duracao_)


resultado: cc.Resultado | None = None
falha = ""
if not erros:
    try:
        resultado = _calcular(circuito, condicoes, duracao)
    except (ci.ErroDoCircuito, cte.ErroTermico) as erro:
        falha = str(erro)

# ============================================================ prancheta + selecionado
with st.container(border=True):
    st.subheader("Desenho do circuito", help=AJUDA["sec_desenho"])
    prancha, lateral = st.columns([2.7, 1], gap="small")
    with prancha:
        prancheta_do_circuito(
            {
                "dados": dados,
                "versao": estado[VERSAO],
                "ajustar": estado.get(AJUSTE, 0),
                "marcas": None if resultado is None else cc.marcas_para_o_desenho(resultado),
            },
            key=CHAVE_PRANCHETA,
            ao_desenhar=_ao_desenhar,
            ao_selecionar=_ao_selecionar,
        )
    with lateral, st.container(border=True, height=520):
        selecao = estado.get(SELECAO) or {}
        versao = estado[VERSAO]
        lista = "nos" if selecao.get("tipo") == "no" else "trechos"
        item = (
            next((x for x in dados[lista] if x.get("id") == selecao.get("id")), None)
            if selecao
            else None
        )
        if item is None:
            st.markdown("**Nada selecionado**")
            st.caption(AJUDA["sel_nada"])
        elif lista == "nos":
            st.markdown(
                f"**Ponto {item.get('nome')}**"
                + (" · vaso de expansão" if item.get("vaso") else "")
            )
            st.text_input("Nome", value=str(item.get("nome") or ""), key=f"circ_sel_{item['id']}_{versao}_nome", on_change=_ao_mudar_campo,
                          args=("nos", item["id"], "nome", f"circ_sel_{item['id']}_{versao}_nome"), help=AJUDA["c_nome"])  # fmt: skip
            _campo("nos", item, "cota", "Cota (m)", "%.2f", versao)
            if item.get("vaso"):
                for campo, rotulo, formato in CAMPOS_DO_VASO:
                    _campo("nos", item, campo, rotulo, formato, versao)
            if resultado is not None and item["id"] in resultado.hidraulica.pressoes:
                t = resultado.regime.temperaturas.get(item["id"])
                st.caption(
                    f"Pressão {_N(resultado.hidraulica.pressao_bar(item['id']), 2)} bar"
                    + ("" if t is None else f" · {_N(t, 1)} °C em regime")
                )
        else:
            tipo = str(item.get("tipo") or ci.TUBO)
            st.markdown(f"**{ci.NOMES.get(tipo, tipo)} {item.get('nome')}**")
            st.text_input("Nome", value=str(item.get("nome") or ""), key=f"circ_sel_{item['id']}_{versao}_nome", on_change=_ao_mudar_campo,
                          args=("trechos", item["id"], "nome", f"circ_sel_{item['id']}_{versao}_nome"), help=AJUDA["c_nome"])  # fmt: skip
            for campo, rotulo, formato in CAMPOS.get(tipo, []):
                _campo("trechos", item, campo, rotulo, formato, versao)
            if resultado is not None:
                e_id = item["id"]
                q = resultado.hidraulica.vazoes.get(e_id, 0.0)
                texto = f"Vazão {_N(abs(q) * 3600.0, 2)} m³/h"
                if e_id in resultado.regime.saidas:
                    texto += f" · {_N(resultado.regime.entradas[e_id], 1)} → {_N(resultado.regime.saidas[e_id], 1)} °C"
                st.caption(texto)
    botoes = st.columns([1, 1, 4])
    botoes[0].button(
        "Voltar ao exemplo",
        key="circ_exemplo",
        on_click=_voltar_ao_exemplo,
        help=AJUDA["exemplo"],
        icon=":material/restart_alt:",
        width="stretch",
    )
    botoes[1].button(
        "Limpar o desenho",
        key="circ_limpar",
        on_click=_limpar,
        help=AJUDA["limpar"],
        icon=":material/delete_sweep:",
        width="stretch",
    )


# ============================================================ tabelas, só para completar
def _ao_editar_tabela(lista: str, chave: str, colunas_: Mapping[str, str], ids: list[str]) -> None:
    mudancas = estado.get(chave) or {}
    dados_ = {k: [dict(x) for x in v] for k, v in estado[DADOS].items()}
    por_id = {x["id"]: x for x in dados_[lista]}
    for indice, campos in (mudancas.get("edited_rows") or {}).items():
        i = int(indice)
        if not 0 <= i < len(ids):
            continue
        for rotulo, valor in campos.items():
            campo = colunas_.get(rotulo)
            if campo is None:
                continue
            if isinstance(valor, float) and valor != valor:
                valor = None
            por_id[ids[i]][campo] = valor
    _trocar(dados_)


COLUNAS_PONTOS = {"Ponto": "nome", "Cota (m)": "cota"}
COLUNAS_TUBOS = {
    "Tubo": "nome",
    "Diâmetro interno (mm)": "diametro_mm",
    "Material": "material",
    "Comprimento real (m)": "comprimento",
    "ΣK": "k_local",
}
with st.container(border=True), secao_protegida("Completar nas tabelas"):
    st.subheader("Completar nas tabelas", help=AJUDA["sec_tabelas"])
    if not dados["nos"]:
        st.caption("O desenho está vazio: as tabelas aparecem quando houver pontos.")
    else:
        lado = st.columns([1, 2.2])
        ids_nos = [str(n["id"]) for n in dados["nos"]]
        chave = f"circ_tab_nos_{estado[REVISAO]}"
        lado[0].data_editor(
            pd.DataFrame([{"Ponto": n.get("nome"), "Cota (m)": float(n.get("cota") or 0.0)} for n in dados["nos"]]),
            key=chave, hide_index=True, num_rows="fixed", width="stretch",
            on_change=_ao_editar_tabela, args=("nos", chave, COLUNAS_PONTOS, ids_nos),
            column_config={"Ponto": st.column_config.TextColumn(help=AJUDA["c_nome"]), "Cota (m)": st.column_config.NumberColumn(format="%.2f", help=AJUDA["c_cota"])},
        )  # fmt: skip
        tubos = [t for t in dados["trechos"] if (t.get("tipo") or ci.TUBO) == ci.TUBO]
        if tubos:
            ids_tubos = [str(t["id"]) for t in tubos]
            chave = f"circ_tab_tubos_{estado[REVISAO]}"
            lado[1].data_editor(
                pd.DataFrame(
                    [
                        {
                            "Tubo": t.get("nome"),
                            "Diâmetro interno (mm)": float(t.get("diametro_mm") or 0.0),
                            "Material": t.get("material") or MATERIAIS[0],
                            "Desenhado (m)": round(ci.comprimento_desenhado(dados, t), 2),
                            "Comprimento real (m)": None if t.get("comprimento") in (None, "") else float(t["comprimento"]),
                            "ΣK": float(t.get("k_local") or 0.0),
                        }
                        for t in tubos
                    ]
                ).astype({"Comprimento real (m)": "float64"}),
                key=chave, hide_index=True, num_rows="fixed", width="stretch", disabled=["Desenhado (m)"],
                on_change=_ao_editar_tabela, args=("trechos", chave, COLUNAS_TUBOS, ids_tubos),
                column_config={
                    "Tubo": st.column_config.TextColumn(help=AJUDA["c_nome"]),
                    "Diâmetro interno (mm)": st.column_config.NumberColumn(min_value=0.0, format="%.1f", help=AJUDA["c_diametro_mm"]),
                    "Material": st.column_config.SelectboxColumn(options=MATERIAIS, help=AJUDA["c_material"]),
                    "Desenhado (m)": st.column_config.NumberColumn(format="%.2f", help=AJUDA["c_comprimento"]),
                    "Comprimento real (m)": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help=AJUDA["c_comprimento"]),
                    "ΣK": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help=AJUDA["c_k_local"]),
                },
            )  # fmt: skip

# ============================================================ resultado
with st.container(border=True), secao_protegida("Resultado do circuito"):
    st.subheader("Resultado do circuito", help=AJUDA["sec_resultado"])
    for erro in erros:
        st.error(erro, icon=":material/error:")
    if falha:
        st.error(falha, icon=":material/error:")
    if resultado is not None:
        r = resultado
        if r.status == "OK":
            st.success(
                "O circuito atende: pressões, velocidades, temperaturas e vaso dentro dos limites.",
                icon=":material/check_circle:",
            )
        elif r.status == "ALERTA":
            st.warning(
                "O circuito funciona, mas pede atenção: veja os alertas na tabela de verificação.",
                icon=":material/warning:",
            )
        else:
            st.error(
                "O circuito não atende em algum ponto: o que não passa está em vermelho no desenho e NÃO OK na tabela.",
                icon=":material/error:",
            )
        bombas = [e for e in r.circuito.elementos if e.tipo == ci.BOMBA and e.ligada]
        fontes = [e for e in r.circuito.elementos if e.tipo == ci.FONTE and e.id in r.regime.saidas]
        metricas = st.columns(4)
        metricas[0].metric(
            "Vazão da bomba",
            f"{_N(sum(abs(r.hidraulica.vazoes[e.id]) for e in bombas) * 3600.0, 2)} m³/h",
            help=AJUDA["res_vazao"],
        )
        if fontes:
            quente = max(fontes, key=lambda e: r.regime.saidas[e.id])
            metricas[1].metric(
                "Saída mais quente",
                f"{_N(r.regime.saidas[quente.id], 1)} °C ({quente.nome})",
                help=AJUDA["res_fonte"],
            )
        if r.tempo is not None and r.tempo.vaso:
            metricas[2].metric(
                "Vaso de expansão",
                f"até {_N(max(s.pressao_bar for s in r.tempo.vaso), 2)} bar",
                help=AJUDA["res_vaso"],
            )
            u = unidade_de_tempo(r.tempo.duracao)
            metricas[3].metric(
                "Estabiliza em",
                "—" if r.tempo.estabiliza is None else tempo_em_texto(r.tempo.estabiliza, u),
                help=AJUDA["res_estabiliza"],
            )
        for aviso in (*r.hidraulica.avisos, *r.regime.avisos, *(r.tempo.avisos if r.tempo else ())):
            st.warning(aviso, icon=":material/warning:")
        if r.tempo is not None:
            tocador(cc.cena_do_circuito(r), key="circ_tocador")
        st.dataframe(
            pd.DataFrame(cc.linhas_dos_elementos(r), columns=list(cc.COLUNAS_ELEMENTOS)),
            hide_index=True,
            width="stretch",
        )
        st.dataframe(
            pd.DataFrame(cc.linhas_dos_pontos(r), columns=list(cc.COLUNAS_PONTOS)),
            hide_index=True,
            width="stretch",
        )
        mostrar_tabela_verificacoes(list(r.verificacoes))
        with st.expander("Hipóteses da conta"):
            for linha in cc.premissas(r):
                st.markdown(f"- {linha}")
        st.subheader("Registrar no projeto", help=AJUDA["registrar"])
        botao_registrar_calculo(
            cc.registro(r),
            key="registrar_circuito",
            rotulo="Registrar o circuito no projeto ativo",
            identificar_peca=False,
        )
